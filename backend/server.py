import asyncio
from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, UploadFile, File, Form, Response, Header, Query
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr
from typing import Optional
import logging
import uuid
import re
import bcrypt
import jwt
import requests
from client_search import build_client_search_queries, NUMERIC_CLIENT_SEARCH_FIELDS
from client_portal import is_client_upload_path, public_client_messages
from password_reset import admin_reset_nonce_hash, reset_lookup_hash, reset_rate_key, reset_token_hash, trusted_reset_origin
import io
import zipfile
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

# ---------------- DB ----------------
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

PRIVATE_MODE = os.environ.get("DNS_ENERGY_PRIVATE_MODE", "false").strip().lower() in ("1", "true", "yes", "on")
app = FastAPI(
    docs_url=None if PRIVATE_MODE else "/docs",
    redoc_url=None if PRIVATE_MODE else "/redoc",
    openapi_url=None if PRIVATE_MODE else "/openapi.json",
)
api_router = APIRouter(prefix="/api")

@app.get("/healthz", include_in_schema=False)
async def healthz():
    return {"status": "ok"}


@app.get("/readyz", include_in_schema=False)
async def readyz():
    try:
        await asyncio.wait_for(client.admin.command("ping"), timeout=5.0)
    except Exception:
        raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": {"mongodb": "unavailable"}})
    return {"status": "ready", "checks": {"mongodb": "ok"}}


# Existing Render service was provisioned with /docs as its health check.
# In private mode FastAPI's interactive docs are disabled, so keep this path
# as a harmless health alias until the service configuration is updated.
if PRIVATE_MODE:
    app.add_api_route("/docs", readyz, methods=["GET"], include_in_schema=False, name="render_health_compat")


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("d-energy")

# ---------------- Auth helpers ----------------
JWT_ALGORITHM = "HS256"

def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

def create_access_token(user_id: str, email: str, token_version: int = 0) -> str:
    payload = {"sub": user_id, "email": email,
               "ver": token_version, "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "access"}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Neautentificat")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload["sub"]})
        if not user:
            raise HTTPException(status_code=401, detail="Utilizator inexistent")
        if int(payload.get("ver", 0)) != int(user.get("token_version", 0)):
            raise HTTPException(status_code=401, detail="Sesiunea a fost revocată. Autentifică-te din nou.")
        if os.environ.get("DNS_ENERGY_PRIVATE_MODE", "false").strip().lower() in ("1", "true", "yes", "on"):
            admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
            if not admin_email or user.get("email", "").lower() != admin_email or user.get("role") != "admin":
                raise HTTPException(status_code=403, detail="Acces permis exclusiv administratorului DNS Energy")
        user.pop("password_hash", None)
        user.pop("_id", None)
        if user.get("status", "active") != "active":
            raise HTTPException(status_code=403, detail=STATUS_MSG.get(user.get("status"), "Cont inactiv"))
        return await finish_user(user)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesiune expirată")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalid")

PLATFORM = {"id": None}
ALL_FEATURES = {"prosumator": "Dosare de prosumator", "diu": "Dosar instalație de utilizare (DI-U)", "mono": "Scheme monofilare (modul)",
                "panels": "Tablouri electri