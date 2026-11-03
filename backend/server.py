Warning: truncated output (original token count: 52241)
Total output lines: 3488

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
import io
import zipfile
from datetime import datetime, timezone, timedelta

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
    app.add_api_route("/docs", healthz, methods=["GET"], include_in_schema=False, name="render_health_compat")


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

def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email,
               "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "access"}
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
                "panels": "Tablouri electrice", "anti": "Antiinsularizare", "pram": "Buletine PRAM", "equipment": "Echipamente",
                "power": "Spor de putere / BMP", "atr": "Cerere ATR (aviz tehnic de racordare)", "works": "Gestionarea lucrărilor", "projects": "Simulare proiect", "sign_remote": "Semnare la distanță",
                "ai_extract": "Import automat din documente (AI)", "ai_gpt": "Asistent AI ChatGPT (chat, verificare dosar, redactare, import)", "oferte": "Oferte de preț și contracte"}
MODULE_FEATURE = {"clients": "prosumator", "prosumator": "prosumator", "documents": "prosumator", "archived_dossiers": "prosumator", "catalog": "prosumator", "staff": "prosumator",
                  "instruments": "prosumator", "diu": "diu", "mono": "mono", "panels": "panels", "anti": "anti", "pram": "pram",
                  "equipment": "equipment", "power": "power", "atr": "atr", "works": "works", "projects": "projects"}
DEFAULT_PLANS = [
    {"code": "start", "name": "START", "price": 250.0, "features": ["prosumator"], "max_inverters": 1, "order": 1,
     "description": "Dosare de prosumator simple, maximum un invertor per dosar."},
    {"code": "pro", "name": "PRO", "price": 500.0, "features": ["prosumator", "diu"], "max_inverters": 0, "order": 2,
     "description": "Toate funcțiile START + dosare de prosumator fără limită de invertoare + modulul DI-U."},
    {"code": "full", "name": "FULL", "price": 1000.0, "features": ["*"], "max_inverters": 0, "order": 3,
     "description": "Acces complet la toate modulele și funcțiile platformei, inclusiv cele adăugate ulterior."}]

async def billing_cfg() -> dict:
    return await db.billing_config.find_one({"id": "main"}, {"_id": 0}) or {"vat_rate": 21.0, "expired_policy": "read_only"}

async def plan_info(user: dict) -> dict:
    if user["id"] == PLATFORM["id"]:
        return {"code": "full", "name": "FULL", "exempt": True, "active": True, "status": "echipa platformei", "features": ["*"], "max_inverters": 0, "policy": "full"}
    sub = await db.subscriptions.find_one({"tenant": user["id"]}, {"_id": 0}) or {}
    plan = await db.plans.find_one({"code": sub.get("plan")}, {"_id": 0}) if sub.get("plan") else None
    today = datetime.now(timezone.utc).date().isoformat()
    status = sub.get("status") or "fără abonament"
    if status == "activ" and (sub.get("valid_until") or "") < today:
        status = "expirat"
    active = bool(plan) and status == "activ"
    cfg = await billing_cfg()
    op = await db.operators.find_one({"tenant": user["id"]}, {"_id": 0, "status": 1, "attest_valid": 1}) or {}
    ost = op.get("status") or "lipsă"
    if ost == "aprobat" and op.get("attest_valid") and op["attest_valid"] < today:
        ost = "expirat"
    owner = user if user.get("uid", user["id"]) == user["id"] else (await db.users.find_one({"id": user["id"]}, {"created_at": 1}) or {})
    legacy = not cfg.get("attest_block_existing") and (owner.get("created_at") or "") < (cfg.get("attest_cutoff") or "") and ost in ("lipsă", "în așteptare")
    attest_ok = ost == "aprobat" or legacy
    if active and not attest_ok:
        active, status = False, f"atestat ANRE {ost if ost != 'lipsă' else 'netrimis'} — acces blocat până la aprobare"
    return {"code": plan["code"] if plan else None, "name": plan["name"] if plan else "Fără abonament", "exempt": False, "active": active,
            "attest": ost, "attest_legacy": legacy,
            "status": status, "valid_until": sub.get("valid_until"), "features": (plan or {}).get("features", []) if active else [],
            "max_inverters": int((plan or {}).get("max_inverters") or 0), "policy": cfg.get("expired_policy", "read_only")}

async def finish_user(user: dict) -> dict:
    user["uid"] = user["id"]
    user["id"] = user.get("tenant") or user["id"]
    user.setdefault("role", "admin")
    user["plan"] = await plan_info(user)
    pm = await db.platform_modules.find_one({"id": "main"}, {"_id": 0}) or {}
    user["plan"]["disabled"] = [] if user["uid"] == PLATFORM["id"] else [f for f in pm.get("disabled", []) if f in ALL_FEATURES]
    return user

def has_feature(user: dict, feat: Optional[str]) -> bool:
    p = user.get("plan") or {}
    return p.get("exempt") or not feat or "*" in p.get("features", []) or feat in p.get("features", [])

def need(user: dict, feat: Optional[str], write: bool = False):
    p = user.get("plan") or {}
    if feat and feat in p.get("disabled", []):
        raise HTTPException(status_code=403, detail=f"Modulul „{ALL_FEATURES.get(feat, feat)}” este indisponibil momentan (dezactivat de administratorul platformei).")
    if p.get("exempt"):
        return
    if not p.get("active"):
        if write or p.get("policy") == "blocked":
            raise HTTPException(status_code=402, detail=f"Abonamentul nu este activ ({p.get('status')}). Datele dvs. sunt păstrate; " +
                                ("le puteți consulta, dar " if p.get("policy") != "blocked" else "") + "pentru a crea sau modifica dosare activați un abonament din pagina „Abonament”.")
        return
    if not has_feature(user, feat):
        raise HTTPException(status_code=402, detail=f"Modulul „{ALL_FEATURES.get(feat, feat)}” nu este inclus în abonamentul {p.get('name')}. Treceți la un abonament superior din pagina „Abonament”.")

def inv_count(d: dict) -> int:
    inverters = (d.get("cef") or {}).get("inverters") or []
    if not inverters:
        return 1 if d.get("inverter") else 0
    total = 0
    for inverter in inverters:
        raw_count = inverter.get("count", inverter.get("quantity", 1))
        try:
            count = float(raw_count or 1)
        except (TypeError, ValueError):
            count = 1
        # Quantities are physical units; round a malformed fractional value up
        # so it cannot bypass a plan limit.
        total += max(1, int(count) + (1 if count > int(count) else 0))
    return total

def check_inverters(user: dict, d: dict):
    mx = (user.get("plan") or {}).get("max_inverters") or 0
    if not (user.get("plan") or {}).get("exempt") and mx and inv_count(d) > mx:
        raise HTTPException(status_code=402, detail=f"Abonamentul {user['plan']['name']} permite maximum {mx} invertor per dosar (dosarul are {inv_count(d)}). "
                            "Dosarul nu poate fi salvat sau finalizat — treceți la abonamentul PRO sau FULL pentru dosare cu mai multe invertoare.")

# ---------------- Object storage ----------------
# New files use MongoDB GridFS; legacy files are read-through migrated only when the old source remains accessible.
from gridfs_storage import init_storage, put_object, get_object, has_gridfs_object, LegacyObjectUnavailable

@app.exception_handler(LegacyObjectUnavailable)
async def legacy_file_unavailable(request: Request, exc: LegacyObjectUnavailable):
    return JSONResponse(status_code=410, content={"detail": str(exc)})


# Namespace used for uploaded file keys in MongoDB GridFS.
APP_NAME = os.environ.get("APP_NAME", "dns-energy").strip("/") or "dns-energy"

MIME_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif",
              "webp": "image/webp", "heic": "image/heic", "heif": "image/heif", "pdf": "application/pdf", "doc": "application/msword",
              "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
              "xls": "application/vnd.ms-excel",
              "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def validate_upload_payload(filename: str, declared_type: str | None, data: bytes) -> str:
    """Validate the uploaded bytes against their extension and MIME type before storage or parsing."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    expected = MIME_TYPES.get(ext)
    if not expected:
        raise HTTPException(status_code=415, detail="Tipul fișierului nu este acceptat")
    declared = str(declared_type or "").split(";", 1)[0].strip().lower()
    allowed_declared = {expected, "application/octet-stream"}
    if ext == "heic":
        allowed_declared.add("image/heic-sequence")
    if ext == "heif":
        allowed_declared.add("image/heif-sequence")
    if declared and declared not in allowed_declared:
        raise HTTPException(status_code=415, detail="Tipul fișierului nu corespunde extensiei")
    if not data:
        raise HTTPException(status_code=400, detail="Fișierul este gol")

    signatures = {
        "jpg": data.startswith(b"\xff\xd8\xff"),
        "jpeg": data.startswith(b"\xff\xd8\xff"),
        "png": data.startswith(b"\x89PNG\r\n\x1a\n"),
        "gif": data.startswith((b"GIF87a", b"GIF89a")),
        "webp": len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP",
        "pdf": data.startswith(b"%PDF-"),
        "doc": data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"),
        "xls": data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"),
        "heic": len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in {b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1", b"heics", b"heifs"},
        "heif": len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in {b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1", b"heics", b"heifs"},
    }
    if ext in ("docx", "xlsx"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                total_uncompressed = sum(entry.file_size for entry in entries)
                required_part = "word/document.xml" if ext == "docx" else "xl/workbook.xml"
                valid = (len(entries) <= 5000 and total_uncompressed <= MAX_UPLOAD_BYTES * 8
                         and "[Content_Types].xml" in archive.namelist() and required_part in archive.namelist())
        except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile):
            valid = False
        signatures[ext] = valid
    if not signatures.get(ext, False):
        raise HTTPException(status_code=415, detail="Conținutul fișierului nu este valid pentru tipul declarat")
    return expected


# ---------------- Models ----------------
class RegisterReq(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None
    billing: Optional[dict] = None

class LoginReq(BaseModel):
    email: EmailStr
    password: str

class PasswordChangeReq(BaseModel):
    current_password: str
    new_password: str

# ---------------- Auth routes ----------------
STATUS_MSG = {"pending": "Contul așteaptă aprobarea administratorului", "suspended": "Contul este suspendat — contactați administratorul",
              "disabled": "Contul este dezactivat"}
ROLES = {"admin": "Administrator", "inginer": "Inginer / proiectant", "electrician": "Electrician autorizat", "instalator": "Instalator", "limitat": "Acces limitat"}
EDIT_ROLES = ("admin", "inginer", "electrician", "instalator")

def pub_user(u: dict) -> dict:
    return {"id": u.get("uid") or u["id"], "email": u["email"], "name": u.get("name"), "role": u.get("role", "admin"), "status": u.get("status", "active"),
            "phone": u.get("phone"), "function": u.get("function"), "staff_id": u.get("staff_id"), "account_type": u.get("account_type") or ("team" if u.get("tenant") else "owner"),
            "plan": u.get("plan"), "platform": bool(PLATFORM["id"]) and (u.get("uid") or u["id"]) == PLATFORM["id"]}

@api_router.post("/auth/register")
async def register(body: RegisterReq, request: Request):
    # Private test mode: only permit one-time bootstrap for the configured admin email.
    # Once any platform admin exists, public self-registration is permanently closed.
    email = body.email.lower()
    configured_admin = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    existing_admin = await db.users.find_one({"role": "admin", "tenant": {"$in": [None, ""]}})
    if not configured_admin or email != configured_admin or existing_admin:
        raise HTTPException(status_code=403, detail="Înregistrarea publică este dezactivată. Accesul este permis numai administratorului DNS Energy.")
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email deja înregistrat")
    if len(body.password or "") < 8:
        raise HTTPException(status_code=400, detail="Parola trebuie să aibă minimum 8 caractere")
    admin = await db.users.find_one({"email": os.environ["ADMIN_EMAIL"].lower()}) or await db.users.find_one({"role": "admin", "tenant": {"$in": [None, ""]}}, sort=[("created_at", 1)])
    import billing_routes as BR
    prof = BR.validate_profile(body.billing or {}, email) if admin else None
    uid = str(uuid.uuid4())
    doc = {"id": uid, "email": email, "password_hash": hash_password(body.password), "name": body.name or email.split("@")[0],
           "role": "admin", "status": "pending" if admin else "active", "tenant": None, "account_type": "subscriber" if admin else "owner",
           "created_at": datetime.now(timezone.utc).isoformat()}
    await db.users.insert_one(doc)
    if admin:
        await BR.save_profile(uid, prof, email, {})
        await db.audit.insert_one({"owner": admin["id"], "user": email, "action": "înregistrare cont (în așteptare)", "module": "users", "item_id": uid, "fields": [], "at": doc["created_at"]})
        return {"pending": True, "message": STATUS_MSG["pending"]}
    return {"access_token": create_access_token(uid, email), "user": pub_user(doc)}

@api_router.post("/auth/login")
async def login(body: LoginReq, request: Request):
    email = body.email.lower()
    ident = f"login:{email}"
    att = await db.login_attempts.find_one({"identifier": ident})
    if att and att.get("count", 0) >= 5 and att.get("until", "") > datetime.now(timezone.utc).isoformat():
        raise HTTPException(status_code=429, detail="Prea multe încercări eșuate. Încercați din nou peste 15 minute.")
    private_mode = os.environ.get("DNS_ENERGY_PRIVATE_MODE", "false").strip().lower() in ("1", "true", "yes", "on")
    admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    if private_mode and (not admin_email or email != admin_email):
        raise HTTPException(status_code=403, detail="Acces permis exclusiv administratorului DNS Energy")
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        await db.login_attempts.update_one({"identifier": ident}, {"$inc": {"count": 1}, "$set": {"until": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}}, upsert=True)
        raise HTTPException(status_code=401, detail="Email sau parolă incorectă")
    await db.login_attempts.delete_many({"identifier": ident})
    if user.get("status", "active") != "active":
        raise HTTPException(status_code=403, detail=STATUS_MSG.get(user.get("status"), "Cont inactiv"))
    tok = create_access_token(user["id"], email)
    return {"access_token": tok, "user": pub_user(await finish_user(user))}

@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return pub_user(user)

@api_router.post("/auth/change-password")
async def change_password(body: PasswordChangeReq, user: dict = Depends(get_current_user)):
    current = body.current_password or ""
    new = body.new_password or ""
    if len(new) < 12:
        raise HTTPException(status_code=400, detail="Parola nouă trebuie să aibă cel puțin 12 caractere")
    if len(new.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Parola nouă este prea lungă; limita este 72 de octeți")
    if current == new:
        raise HTTPException(status_code=400, detail="Alege o parolă diferită de cea actuală")
    account = await db.users.find_one({"id": user["uid"]}, {"_id": 0, "password_hash": 1, "email": 1})
    try:
        valid = bool(account and verify_password(current, account.get("password_hash") or ""))
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise HTTPException(status_code=400, detail="Parola actuală este incorectă")
    await db.users.update_one({"id": user["uid"]}, {"$set": {
        "password_hash": hash_password(new), "password_changed_at": datetime.now(timezone.utc).isoformat()
    }})
    await db.login_attempts.delete_many({"identifier": f"login:{account['email'].lower()}"})
    await audit(user, "schimbare parolă", "auth", user["uid"], [])
    return {"ok": True}

def require(user: dict, *roles):
    if user.get("role", "admin") not in roles:
        raise HTTPException(status_code=403, detail="Nu aveți dreptul pentru această acțiune")

def is_admin(user: dict) -> bool:
    return user.get("role", "admin") == "admin"

SCOPED = ("clients", "prosumator", "diu", "mono", "panels", "anti", "pram", "equipment", "power", "atr", "works", "projects", "documents")

def scope_q(user: dict, module: str) -> dict:
    q = {"owner": user["id"]}
    if not is_admin(user) and module in SCOPED:
        q["$or"] = [{"created_by": {"$in": [user["uid"], user.get("email")]}}, {"assigned_to": user["uid"]}]
    return q

async def check_access(user: dict, module: str, item_id: str) -> dict:
    need(user, MODULE_FEATURE.get(module))
    rec = await db[module].find_one({**scope_q(user, module), "id": item_id}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Înregistrare inexistentă sau fără drept de acces")
    return rec

@api_router.get("/admin/users")
async def admin_users(user: dict = Depends(get_current_user)):
    require(user, "admin")
    us = await db.users.find({"$or": [{"tenant": user["id"]}, {"id": user["id"]}]}, {"_id": 0, "password_hash": 0}).sort("created_at", 1).to_list(500)
    return {"users": [pub_user(u) | {"created_at": u.get("created_at")} for u in us], "roles": ROLES}

@api_router.put("/admin/users/{uid}")
async def admin_user_update(uid: str, request: Request, user: dict = Depends(get_current_user)):
    require(user, "admin")
    b = await request.json()
    u = await db.users.find_one({"id": uid, "tenant": user["id"]})
    if not u:
        raise HTTPException(status_code=404, detail="Utilizator inexistent (administratorul principal nu poate fi modificat aici)")
    upd = {k: b[k] for k in ("name", "phone", "function", "staff_id") if k in b}
    if "role" in b:
        if b["role"] not in ROLES:
            raise HTTPException(status_code=400, detail="Rol invalid")
        upd["role"] = b["role"]
    if "status" in b:
        if b["status"] not in ("pending", "active", "suspended", "disabled"):
            raise HTTPException(status_code=400, detail="Stare invalidă")
        upd["status"] = b["status"]
    await db.users.update_one({"id": uid}, {"$set": upd})
    await audit(user, "cont utilizator", "users", uid, list(upd.keys()) + [str(upd.get("status") or ""), str(upd.get("role") or "")])
    return {"ok": True}

@api_router.put("/auth/profile")
async def my_profile(request: Request, user: dict = Depends(get_current_user)):
    b = await request.json()
    upd = {k: b[k] for k in ("name", "phone", "function") if k in b}
    await db.users.update_one({"id": user["uid"]}, {"$set": upd})
    return {"ok": True}

@api_router.post("/auth/logout")
async def logout(user: dict = Depends(get_current_user)):
    return {"ok": True}

# ---------------- Generic module CRUD ----------------
MODULES = ["clients", "prosumator", "diu", "mono", "panels", "anti", "pram", "equipment", "power", "atr", "works", "projects", "documents", "archived_dossiers", "catalog", "staff", "instruments"]

def clean(doc: dict) -> dict:
    doc.pop("_id", None)
    if isinstance(doc.get("atr_track"), dict):
        doc["atr_track"] = {k: v for k, v in doc["atr_track"].items() if k != "token"}
    return doc


QUICK_SEARCH_MODULES = [
    ("clients", "Client", "client_name", ["name", "phone", "email", "cnp", "idcode", "cui", "regcom", "id_series", "id_number", "pod", "address", "locality", "county"], "/clienti"),
    ("prosumator", "Dosar prosumator", "client_name", ["client_name", "number", "pod", "address", "locality", "county", "operator"], "/prosumator"),
    ("atr", "Cerere ATR", "client_name", ["client_name", "number", "pod", "address", "status", "operator"], "/cerere-atr"),
    ("power", "Spor de putere", "client_name", ["client_name", "number", "pod", "address", "status", "operator"], "/spor-putere"),
    ("diu", "Dosar DIU", "client_name", ["client_name", "number", "pod", "address", "status", "operator"], "/diu"),
    ("documents", "Document", "client_name", ["client_name", "title", "name", "filename", "original_filename", "doc_type", "kind", "type", "pod"], "/documente"),
    ("catalog", "Echipament catalog", "brand_model", ["brand_model", "category", "supplier"], "/catalog-echipamente"),
]


@api_router.get("/quick-search")
async def quick_search(q: str = Query(..., min_length=2, max_length=80), user: dict = Depends(get_current_user)):
    """Search the signed-in tenant's client and dossier records without loading whole collections."""
    term = q.strip()
    if len(term) < 2:
        return {"results": []}
    pattern = re.compile(re.escape(term), re.IGNORECASE)

    async def search_module(spec):
        module, label, name_key, fields, route = spec
        try:
            guard(module, user)
        except HTTPException:
            return []
        field_query = {"$or": [{field: pattern} for field in fields]}
        query = {"$and": [scope_q(user, module), field_query]}
        rows = await db[module].find(query, {"_id": 0, "id": 1, "name": 1, "client_name": 1, "client_id": 1,
                                             "number": 1, "original_filename": 1, "doc_type": 1, "kind": 1,
                                             "brand_model": 1, "category": 1, "supplier": 1,
                                             "pod": 1, "address": 1, "locality": 1, "county": 1, "phone": 1, "email": 1, "cui": 1, "regcom": 1,
                                             "operator": 1, "title": 1, "filename": 1, "type": 1,
                                             "is_test": 1}).sort("updated_at", -1).limit(5).to_list(5)
        matches = []
        for row in rows:
            if row.get("is_test") or re.search(r"\bTEST\b", " ".join(str(row.get(k) or "") for k in ("name", "client_name", "number")), re.I):
                continue
            item_id = str(row.get("id") or "")
            if not item_id:
                continue
            client_name = row.get(name_key) or row.get("name") or "Înregistrare fără nume"
            detail = " · ".join(str(row.get(k)) for k in ("number", "pod", "phone", "email", "cui", "regcom", "locality", "county", "operator") if row.get(k))
            title = client_name
            href = f"{route}?edit={item_id}"
            if module == "catalog":
                title = row.get("brand_model") or client_name
                detail = " · ".join(str(value) for value in (row.get("category"), row.get("supplier")) if value)
                href = f"/catalog-echipamente?q={_q(str(row.get('brand_model') or ''))}&category={_q(str(row.get('category') or 'Invertor'))}"
            if module == "documents":
                title = row.get("original_filename") or row.get("title") or row.get("filename") or row.get("doc_type") or row.get("kind") or client_name
                detail = " · ".join(str(value) for value in (client_name, row.get("doc_type") or row.get("kind"), detail) if value)
                href = f"{route}?docId={item_id}"
            matches.append({"id": item_id, "module": module, "label": label, "title": title,
                            "detail": detail, "href": href})
        return matches

    module_matches = await asyncio.gather(*(search_module(spec) for spec in QUICK_SEARCH_MODULES), return_exceptions=True)
    collections = []
    unavailable = []
    for spec, matches in zip(QUICK_SEARCH_MODULES, module_matches):
        if isinstance(matches, Exception):
            logger.warning("Quick search collection failed: %s", type(matches).__name__)
            collections.append([])
            unavailable.append(spec[1])
            continue
        collections.append(matches)

    # Interleave collections so a busy client/dossier module cannot hide every
    # equipment or document result behind the global 24-result cap.
    results = []
    depth = max((len(items) for items in collections), default=0)
    for index in range(depth):
        for items in collections:
            if index < len(items):
                results.append(items[index])
                if len(results) >= 24:
                    return {"results": results, "unavailable": unavailable}
    return {"results": results, "unavailable": unavailable}

@api_router.get("/clients/search")
async def quick_client_search(q: str = Query(..., min_length=2, max_length=80), user: dict = Depends(get_current_user)):
    """Search only the signed-in tenant's clients for the dashboard typeahead."""
    term = q.strip()
    if len(term) < 2:
        return {"results": [], "unavailable": []}
    guard("clients", user)
    queries = build_client_search_queries(scope_q(user, "clients"), term)
    projection = {"_id": 0, "id": 1, "name": 1, "pod": 1, "phone": 1, "email": 1,
                  "address": 1, "locality": 1, "county": 1, "cui": 1, "regcom": 1, "is_test": 1, "updated_at": 1}

    async def fetch_matches(query: dict, indexed_field: str | None = None):
        cursor = db.clients.find(query, projection)
        if indexed_field:
            # Keep prefix searches on owner+field indexes. Without the hint,
            # the planner may choose owner+updated_at and scan every client
            # belonging to this tenant before applying the identifier filter.
            cursor = cursor.hint(f"owner_{indexed_field}")
        return await cursor.sort("updated_at", -1).limit(8).to_list(8)

    if term.isdigit():
        query_rows = await asyncio.gather(*(
            fetch_matches(query, field)
            for query, field in zip(queries, NUMERIC_CLIENT_SEARCH_FIELDS)
        ))
    else:
        query_rows = await asyncio.gather(*(fetch_matches(query) for query in queries))
    by_id = {}
    for rows in query_rows:
        for row in rows:
            item_id = str(row.get("id") or "")
            if not item_id:
                continue
            previous = by_id.get(item_id)
            if previous is None or str(row.get("updated_at") or "") > str(previous.get("updated_at") or ""):
                by_id[item_id] = row

    results = []
    for row in sorted(by_id.values(), key=lambda item: str(item.get("updated_at") or ""), reverse=True)[:8]:
        name = str(row.get("name") or "")
        if row.get("is_test") or re.search(r"\bTEST\b", name, re.I):
            continue
        item_id = str(row.get("id") or "")
        detail = " · ".join(str(row.get(k)) for k in ("pod", "phone", "email", "cui", "regcom", "address", "locality", "county") if row.get(k))
        results.append({"id": item_id, "module": "clients", "label": "Client",
                        "title": name or "Client fără nume", "detail": detail,
                        "href": f"/clienti?edit={item_id}"})
    return {"results": results, "unavailable": []}


@api_router.get("/data/{module}")
async def list_items(module: str, q: Optional[str] = None, user: dict = Depends(get_current_user)):
    if module not in MODULES:
        raise HTTPException(status_code=404, detail="Modul inexistent")
    guard(module, user)
    query = scope_q(user, module)
    if module == "catalog":
        await seed_catalog(user["id"])
    search_fields = {
        "clients": ("name", "phone", "email", "cnp", "idcode", "id_number", "pod", "address", "locality", "county", "cui", "regcom"),
        "prosumator": ("client_name", "number", "pod", "address", "locality", "county", "operator", "status", "request_type"),
        "diu": ("client_name", "number", "pod", "address", "locality", "county", "operator", "status", "pros_id"),
        "atr": ("client_name", "number", "pod", "address", "locality", "county", "operator", "status", "request_type"),
        "power": ("client_name", "number", "pod", "address", "locality", "county", "operator", "status", "request_type"),
        "documents": ("client_name", "title", "name", "filename", "original_filename", "doc_type", "kind", "type", "pod"),
        "catalog": ("brand_model", "category", "supplier", "manufacturer", "model"),
        "projects": ("name", "number", "client_name", "address", "locality", "county", "status"),
        "works": ("name", "number", "client_name", "address", "locality", "county", "status"),
        "mono": ("client_name", "number", "title", "address", "pod", "status"),
        "panels": ("client_name", "number", "title", "address", "pod", "status"),
        "anti": ("client_name", "number", "title", "address", "pod", "status"),
        "pram": ("client_name", "number", "title", "pod", "instrument", "status"),
        "equipment": ("name", "brand_model", "category", "serial", "manufacturer"),
        "archived_dossiers": ("client_name", "number", "title", "address", "pod", "operator"),
        "staff": ("name", "email", "phone", "function", "staff_id"),
        "instruments": ("name", "model", "serial", "type", "manufacturer"),
    }
    term = str(q or "").strip()
    if term and module in search_fields:
        # Apply the filter in MongoDB. Avoid transferring large dossier rows and
        # embedded file metadata to the browser just to search their JSON text.
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        query = {"$and": [query, {"$or": [{field: pattern} for field in search_fields[module]]}]}
        return [clean(i) for i in await db[module].find(query).sort("created_at", -1).limit(2000).to_list(2000)]
    items = await db[module].find(query).sort("created_at", -1).limit(2000).to_list(2000)
    items = [clean(i) for i in items]
    if term:
        ql = term.lower()
        items = [i for i in items if ql in str(i).lower()]
    return items

@api_router.post("/data/{module}")
async def create_item(module: str, request: Request, user: dict = Depends(get_current_user)):
    if module not in MODULES:
        raise HTTPException(status_code=404, detail="Modul inexistent")
    data = await request.json()
    data = await apply_selected_client_defaults(user["id"], module, data)
    data.pop("_id", None)
    data.pop("atr_track", None)
    data["id"] = str(uuid.uuid4())
    data["owner"] = user["id"]
    data["created_at"] = datetime.now(timezone.utc).isoformat()
    data["updated_at"] = data["created_at"]
    guard(module, user, write=True)
    if module == "prosumator":
        check_inverters(user, data)
    data["created_by"] = user["uid"]
    data["created_by_email"] = user.get("email")
    if not is_admin(user):
        data.pop("assigned_to", None)
    await db[module].insert_one(dict(data))
    await audit(user, "creare", module, data["id"], list(data.keys()))
    if module == "prosumator":
        try:
            await sync_catalog_files_to_documents(user, data)
            data = await db[module].find_one({"id": data["id"], "owner": user["id"]}) or data
        except Exception as e:
            # The dossier is already saved; optional catalog documents must not turn
            # a successful create into a client-visible failure.
            logger.exception("Catalog document sync failed after prosumer dossier create: %s", e)
    return clean(data)

@api_router.get("/data/{module}/{item_id}")
async def get_item(module: str, item_id: str, user: dict = Depends(get_current_user)):
    if module not in MODULES:
        raise HTTPException(status_code=404, detail="Modul inexistent")
    guard(module, user)
    doc = await db[module].find_one({**scope_q(user, module), "id": item_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Înregistrare inexistentă")
    return clean(doc)

@api_router.put("/data/{module}/{item_id}")
async def update_item(module: str, item_id: str, request: Request, user: dict = Depends(get_current_user)):
    if module not in MODULES:
        raise HTTPException(status_code=404, detail="Modul inexistent")
    guard(module, user, write=True)
    cur = await check_access(user, module, item_id)
    data = await request.json()
    data.pop("_id", None); data.pop("id", None)
    data.pop("atr_track", None); data.pop("owner", None); data.pop("created_at", None); data.pop("created_by", None); data.pop("created_by_email", None)
    if module == "prosumator":
        data.pop("pif", None)
    if module in ("prosumator", "diu"):
        data.pop("ai_precheck", None); data.pop("signed", None)
    if module == "clients" and isinstance(data.get("docs"), dict):
        data["docs"]["semnate"] = (cur.get("docs") or {}).get("semnate") or []
    data["updated_by"] = user.get("email")
    if not is_admin(user):
        data.pop("assigned_to", None)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    if module == "prosumator":
        data = derive_cef(data)
        data.pop("opis", None); data.pop("snapshot", None); data.pop("snapshot_history", None); data.pop("sld", None)
        check_inverters(user, {**cur, **data})
        if data.get("client_name"):
            c = await db.clients.find_one({**scope_q(user, "clients"), "name": data["client_name"]}, {"id": 1})
            if c:
                data["client_id"] = c["id"]
    res = await db[module].update_one({"id": item_id, "owner": user["id"]}, {"$set": data})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Înregistrare inexistentă")
    await audit(user, "modificare", module, item_id, list(data.keys()))
    if module == "prosumator":
        try:
            await request_approval(user, item_id, request.headers.get("origin") or "", True)
        except HTTPException:
            pass
        except Exception as e:
            logger.error(f"auto approval request: {e}")
    doc = await db[module].find_one({"id": item_id, "owner": user["id"]})
    if module == "prosumator":
        await sync_catalog_files_to_documents(user, doc)
        doc = await db[module].find_one({"id": item_id, "owner": user["id"]})
    return clean(doc)

@api_router.patch("/data/{module}/{item_id}/status")
async def update_dossier_workflow_status(module: str, item_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Update a dashboard workflow label without overwriting the dossier's technical/operator status."""
    if module not in ("prosumator", "atr", "power", "diu", "mono"):
        raise HTTPException(status_code=404, detail="Modulul nu acceptă stadii de lucru rapide")
    guard(module, user, write=True)
    rec = await check_access(user, module, item_id)
    body = await request.json()
    status = str(body.get("status") or "").strip()
    if not status or len(status) > 80:
        raise HTTPException(status_code=400, detail="Stadiul trebuie să conțină între 1 și 80 de caractere.")
    previous = str(rec.get("workflow_status") or rec.get("status") or rec.get("operator_stage") or "În lucru").strip()
    if status == previous:
        return {"ok": True, "id": item_id, "module": module, "status": status, "updated_at": rec.get("updated_at"), "history_entry": None}
    updated_at = datetime.now(timezone.utc).isoformat()
    history_entry = {"from": previous, "to": status, "at": updated_at, "by": user.get("email") or user.get("id")}
    result = await db[module].update_one(
        {**scope_q(user, module), "id": item_id},
        {"$set": {"workflow_status": status, "updated_at": updated_at, "updated_by": user.get("email")},
         "$push": {"workflow_history": {"$each": [history_entry], "$slice": -500}}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
    await audit(user, "actualizare stadiu flux", module, item_id, ["workflow_status"])
    return {"ok": True, "id": item_id, "module": module, "status": status, "updated_at": updated_at, "history_entry": history_entry}


@api_router.delete("/data/{module}/{item_id}")
async def delete_item(module: str, item_id: str, user: dict = Depends(get_current_user)):
    if module not in MODULES:
        raise HTTPException(status_code=404, detail="Modul inexistent")
    guard(module, user, write=True)
    if not is_admin(user) and module in ("prosumator", "clients"):
        raise HTTPException(status_code=403, detail="Doar administratorul poate șterge dosare și clienți")
    await check_access(user, module, item_id)
    await db[module].delete_one({"id": item_id, "owner": user["id"]})
    await audit(user, "ștergere", module, item_id, [])
    if module == "prosumator":
        for m in ("works", "mono", "equipment"):
            await db[m].delete_many({"owner": user["id"], "pros_ref": item_id})
    return {"ok": True}

# ---------------- Dashboard ----------------
@api_router.get("/stats/dashboard")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    owner = scope_q(user, "diu")
    test_dossier_filter = {"$and": [
        {"is_test": {"$ne": True}},
        {"$nor": [
            {"client_name": {"$regex": r"^TEST", "$options": "i"}},
            {"number": {"$regex": r"^TEST[-_]", "$options": "i"}},
            {"company.name": {"$regex": r"^TEST", "$options": "i"}},
        ]},
    ]}
    client_test_filter = {"$and": [
        {"is_test": {"$ne": True}},
        {"$nor": [
            {"name": {"$regex": r"^TEST", "$options": "i"}},
            {"client_name": {"$regex": r"^TEST", "$options": "i"}},
            {"company_name": {"$regex": r"^TEST", "$options": "i"}},
        ]},
    ]}
    clients = await db.clients.count_documents({**scope_q(user, "clients"), **client_test_filter})
    diu = await db.diu.count_documents({**owner, **test_dossier_filter})
    mono = await db.mono.count_documents({**scope_q(user, "mono"), **test_dossier_filter})
    recent = await db.diu.find({**owner, **test_dossier_filter}).sort("created_at", -1).to_list(5)

    # A compact, actionable work inbox inspired by the reference app's dossier list.
    # Every query stays inside the signed-in user's existing module scope.
    inbox_modules = [
        ("prosumator", "Dosar prosumator"),
        ("atr", "Cerere ATR"),
        ("power", "Spor de putere"),
        ("diu", "Dosar DI-U"),
        ("mono", "Schemă monofilară"),
        ("anre_dossiers", "Dosar ANRE"),
    ]
    inbox = []
    projection = {"_id": 0, "id": 1, "client_name": 1, "number": 1,
                  "pod": 1, "operator": 1, "operator_name": 1, "distributor": 1,
                  "company.name": 1,
                  "kwp": 1, "inverter_kw": 1, "status": 1, "workflow_status": 1, "operator_stage": 1,
                  "next_action": 1, "next_action_due": 1,
                  "updated_at": 1, "created_at": 1}
    for module, label in inbox_modules:
        module_scope = {**scope_q(user, module), **test_dossier_filter}
        recent_rows = await db[module].find(module_scope, projection).sort("updated_at", -1).limit(5).to_list(5)
        scheduled_rows = await db[module].find(
            {**module_scope, "next_action": {"$exists": True, "$nin": [None, ""]}}, projection
        ).sort("next_action_due", 1).limit(5).to_list(5)
        rows = list({row.get("id"): row for row in [*recent_rows, *scheduled_rows] if row.get("id")}.values())
        for row in rows:
            inbox.append({
                "id": row.get("id"),
                "module": module,
                "label": label,
                "client_name": row.get("client_name") or (row.get("company") or {}).get("name") or "",
                "number": row.get("number") or "",
                "pod": row.get("pod") or row.get("pod_number") or "",
                "operator": row.get("operator") or row.get("operator_name") or row.get("distributor") or "",
                "kwp": row.get("kwp") or row.get("panel_kwp") or "",
                "inverter_kw": row.get("inverter_kw") or row.get("power_kw") or "",
                "status": row.get("workflow_status") or row.get("status") or row.get("operator_stage") or "În lucru",
                "next_action": row.get("next_action") or "",
                "next_action_due": row.get("next_action_due") or "",
                "updated_at": row.get("updated_at") or row.get("created_at") or "",
            })
    # Prioritize scheduled work. The user enters both action and due date; we do not infer either.
    inbox.sort(key=lambda item: (
        not bool(item.get("next_action")),
        str(item.get("next_action_due") or "9999-12-31"),
        str(item.get("updated_at") or ""),
    ))

    # Full workload summaries for the dashboard; unlike the inbox, these are
    # aggregate counts over every non-test record in the user's own scope.
    stage_counts = {}
    operator_counts = {}
    stage_expr = {"$let": {"vars": {"value": {"$ifNull": ["$workflow_status", {"$ifNull": ["$status", "$operator_stage"]}]}},
                           "in": {"$cond": [{"$or": [{"$eq": ["$$value", None]}, {"$eq": ["$$value", ""]}]}, "În lucru", "$$value"]}}}
    operator_expr = {"$let": {"vars": {"value": {"$ifNull": ["$operator", {"$ifNull": ["$operator_name", "$distributor"]}]}},
                              "in": {"$cond": [{"$or": [{"$eq": ["$$value", None]}, {"$eq": ["$$value", ""]}]}, "Operator necompletat", "$$value"]}}}
    for module, _label in inbox_modules:
        match = {**scope_q(user, module), **test_dossier_filter}
        for row in await db[module].aggregate([
            {"$match": match},
            {"$project": {"group": stage_expr}},
            {"$group": {"_id": "$group", "count": {"$sum": 1}}},
        ]).to_list(length=None):
            stage = str(row.get("_id") or "În lucru")
            stage_counts[stage] = stage_counts.get(stage, 0) + int(row.get("count") or 0)
        if module == "anre_dossiers":
            continue
        for row in await db[module].aggregate([
            {"$match": match},
            {"$project": {"group": operator_expr}},
            {"$group": {"_id": "$group", "count": {"$sum": 1}}},
        ]).to_list(length=None):
            operator = str(row.get("_id") or "Operator necompletat")
            operator_counts[operator] = operator_counts.get(operator, 0) + int(row.get("count") or 0)

    # Count work that still needs attention across every dossier module shown
    # in the inbox, not just DI-U. A separate workflow_status takes precedence
    # over the technical or operator status stored in `status`.
    attention_stages = {
        "În lucru", "Documente de completat", "În verificare", "Documente lipsă",
        "În completare", "Ciornă", "Așteaptă depunere", "Pregătit pentru depunere",
        "Pregătit pentru semnare", "PV Teste / PIF",
    }
    pending = sum(count for stage, count in stage_counts.items() if stage in attention_stages)

    return {"clients": clients, "diu": diu, "mono": mono, "pending": pending,
            "recent": [clean(r) for r in recent], "inbox": inbox[:24],
            "total_dossiers": sum(stage_counts.values()),
            "stage_counts": dict(sorted(stage_counts.items(), key=lambda item: (-item[1], item[0]))),
            "operator_counts": dict(sorted(operator_counts.items(), key=lambda item: (-item[1], item[0])))}

# ---------------- Settings (singleton per owner) ----------------
PRIVATE = ("staff", "instruments")

def guard(module: str, user: dict, write: bool = False):
    need(user, MODULE_FEATURE.get(module), write)
    role = user.get("role", "admin")
    if module in PRIVATE and write and role != "admin":
        raise HTTPException(status_code=403, detail="Doar administratorul poate modifica personalul și aparatele de măsură")
    if module in PRIVATE and role not in ("admin", "inginer", "electrician", "instalator"):
        raise HTTPException(status_code=403, detail="Acces restricționat la documentele personalului")
    if write and role not in EDIT_ROLES:
        raise HTTPException(status_code=403, detail="Contul are acces limitat (doar consultare)")
    if write and module == "catalog" and role not in ("admin", "inginer"):
        raise HTTPException(status_code=403, detail="Doar administratorul / inginerul modifică catalogul")

async def audit(user: dict, action: str, module: str, item_id: str, fields: list):
    await db.audit.insert_one({"owner": user["id"], "user": user.get("email"), "action": action, "module": module, "item_id": item_id,
                               "fields": [f for f in fields if f not in ("updated_at", "owner", "id", "created_at")][:40],
                               "at": datetime.now(timezone.utc).isoformat()})

@api_router.get("/audit")
async def audit_log(module: Optional[str] = None, item_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {"owner": user["id"]}
    if not is_admin(user):
        if not item_id:
            raise HTTPException(status_code=403, detail="Jurnalul complet este disponibil doar administratorului")
        await check_access(user, module or "prosumator", item_id)
    if module:
        q["module"] = module
    if item_id:
        q["item_id"] = item_id
    return await db.audit.find(q, {"_id": 0}).sort("at", -1).to_list(300)

@api_router.get("/settings")
async def get_settings(user: dict = Depends(get_current_user)):
    doc = await db.settings.find_one({"owner": user["id"]})
    if not doc:
        return {"company": "DNS HOSTESS S.R.L.", "brand": "D-ENERGY", "rep": "", "phone": "", "address": ""}
    return clean(doc)

@api_router.put("/settings")
async def save_settings(request: Request, user: dict = Depends(get_current_user)):
    require(user, "admin")
    data = await request.json()
    data.pop("_id", None)
    data["owner"] = user["id"]
    await db.settings.update_one({"owner": user["id"]}, {"$set": data}, upsert=True)
    await audit(user, "modificare", "settings", user["id"], list(data.keys()))
    doc = await db.settings.find_one({"owner": user["id"]})
    return clean(doc)

# ---------------- File upload / download ----------------
@api_router.post("/upload")
async def upload(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    need(user, None, True)
    filename = str(file.filename or "document")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Fișierul depășește limita de 25 MB")
    expected_type = validate_upload_payload(filename, file.content_type, data)
    path = f"{APP_NAME}/uploads/{user['id']}/{uuid.uuid4()}.{ext}"
    result = put_object(path, data, expected_type)
    return {"storage_path": result["path"], "original_filename": filename[:255],
            "content_type": expected_type, "size": result.get("size", len(data))}

@api_router.get("/catalog/supplier-search")
async def catalog_supplier_search(
    q: str = Query(""), category: str = Query("Invertor"),
    offset: int = Query(0, ge=0, le=10000), limit: int = Query(24, ge=1, le=48),
    user: dict = Depends(get_current_user),
):
    """Search public product listings in bounded pages from the configured suppliers."""
    guard("catalog", user)
    return await SUPPLIER_CATALOG.search_supplier_products(q, category, offset=offset, limit=limit)


@api_router.get("/catalog/document-feedback")
async def list_catalog_document_feedback(user: dict = Depends(get_current_user)):
    """List pending technical-document corrections for the signed-in DNS tenant."""
    guard("catalog", user)
    rows = await db.catalog_document_feedback.find(
        {"owner": user["id"], "status": "pending"}, {"_id": 0}
    ).sort("created_at", -1).limit(100).to_list(100)
    return rows


@api_router.post("/catalog/{item_id}/document-feedback")
async def create_catalog_document_feedback(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Record a team suggestion for a missing or incorrect equipment document."""
    from urllib.parse import urlparse
    guard("catalog", user, write=True)
    item = await db.catalog.find_one({"id": item_id, "owner": user["id"]}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Modelul nu există în catalogul acestui cont")
    body = await request.json()
    kind = str(body.get("kind") or "").strip()
    suggested_url = str(body.get("suggested_url") or "").strip()
    note = str(body.get("note") or "").strip()
    if kind not in ("datasheet", "conformity"):
        raise HTTPException(status_code=400, detail="Alege fișa tehnică sau documentul de conformitate")
    if len(suggested_url) > 2048 or len(note) > 1000:
        raise HTTPException(status_code=400, detail="Linkul sau observația depășește limita permisă")
    if not suggested_url and not note:
        raise HTTPException(status_code=400, detail="Adaugă un link oficial sau o observație")
    if suggested_url:
        parsed = urlparse(suggested_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise HTTPException(status_code=400, detail="Linkul propus trebuie să fie HTTPS și fără date de autentificare")
    now = datetime.now(timezone.utc).isoformat()
    document = item.get(kind)
    document_url = document.get("source_url") if isinstance(document, dict) else ""
    record = {
        "id": str(uuid.uuid4()), "owner": user["id"], "item_id": item_id,
        "brand_model": str(item.get("brand_model") or "")[:255],
        "category": str(item.get("category") or "")[:80], "kind": kind,
        "current_url": str(document_url or item.get(kind + "_url") or item.get(kind + "_source_url") or "")[:2048],
        "suggested_url": suggested_url, "note": note, "status": "pending",
        "submitted_by": str(user.get("email") or user.get("name") or "")[:255],
        "created_at": now, "updated_at": now,
    }
    await db.catalog_document_feedback.insert_one(dict(record))
    await audit(user, "propunere document catalog", "catalog", item_id, [kind, "suggested_url", "note"])
    return {"ok": True, "id": record["id"], "status": "pending"}


@api_router.patch("/catalog/document-feedback/{feedback_id}")
async def update_catalog_document_feedback(feedback_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Mark a tenant's catalog-document suggestion as accepted, reviewed, or dismissed."""
    guard("catalog", user, write=True)
    body = await request.json()
    status = str(body.get("status") or "").strip()
    if status not in ("accepted", "reviewed", "dismissed"):
        raise HTTPException(status_code=400, detail="Starea propunerii nu este validă")
    record = await db.catalog_document_feedback.find_one(
        {"id": feedback_id, "owner": user["id"]}, {"_id": 0}
    )
    if not record:
        raise HTTPException(status_code=404, detail="Propunerea nu există în acest cont")
    now = datetime.now(timezone.utc).isoformat()
    await db.catalog_document_feedback.update_one(
        {"id": feedback_id, "owner": user["id"]},
        {"$set": {"status": status, "review_note": str(body.get("review_note") or "")[:1000],
                  "reviewed_by": str(user.get("email") or user.get("name") or "")[:255],
                  "updated_at": now}}
    )
    await audit(user, "revizuire propunere document catalog", "catalog", record["item_id"], [status])
    return {"ok": True, "id": feedback_id, "status": status}


@api_router.post("/catalog/supplier-import")
async def catalog_supplier_import(request: Request, user: dict = Depends(get_current_user)):
    """Import verified public product data and linked official PDFs into the owner's catalog."""
    from urllib.parse import urlparse
    guard("catalog", user, write=True)
    body = await request.json()
    supplier = str(body.get("supplier") or "")
    category = str(body.get("category") or "")
    product_url = str(body.get("product_url") or "")
    product = await SUPPLIER_CATALOG.get_public_product(supplier, category, product_url)
    if not product:
        raise HTTPException(status_code=400, detail="Produsul nu mai poate fi verificat la sursa publică")
    existing = await db.catalog.find_one({"owner": user["id"], "category": category, "source_url": product_url}, {"_id": 0})
    if existing:
        return {"ok": True, "existing": True, "item": clean(existing)}

    allowed = ("p_nom_kw", "p_max_kw", "vdc_max", "mppt_min", "mppt_max", "mppt_count", "imax_mppt",
               "w", "voc", "coef_voc", "coef_vmp", "temp_pmax", "vmp", "isc", "imp", "kwh", "ah", "voltage", "i_max", "p_max_w", "max_devices")
    item = {"category": category, "brand_model": product["brand_model"], "supplier": supplier,
            "source_url": product_url, "source_price": product.get("price_text", ""),
            "source_availability": product.get("availability", ""),
            "notes": "Importat din pagina publică a furnizorului. Valorile tehnice sunt completate numai când sunt publicate explicit și neambiguu.",
            **{key: product[key] for key in allowed if key in product}}
    now = datetime.now(timezone.utc).isoformat()
    for kind in ("datasheet", "conformity"):
        doc_url = product.get(kind + "_url") or ""
        host = (urlparse(doc_url).hostname or "").lower().rstrip(".")
        source_host = SUPPLIER_CATALOG.SOURCES[supplier]["host"]
        if not doc_url or not SUPPLIER_CATALOG._safe_document(doc_url, source_host):
            continue
        try:
            import httpx
            async with httpx.AsyncClient(timeout=20, follow_redirects=False, headers={"User-Agent": "DNS-Energy-Document-Importer/1.0", "Accept": "application/pdf"}) as client:
                response = await client.get(doc_url)
            data = response.content
            if response.status_code != 200 or len(data) > MAX_UPLOAD_BYTES or not data.startswith(b"%PDF-"):
                continue
            path = f"{APP_NAME}/uploads/{user['id']}/{uuid.uuid4()}.pdf"
            stored = put_object(path, data, "application/pdf")
            item[kind] = {"storage_path": stored["path"], "original_filename": f"{product['brand_model']} — {kind}.pdf",
                          "content_type": "application/pdf", "size": len(data), "source_url": doc_url,
                          "source_host": host, "imported_at": now}
            item[…22241 tokens truncated…
                        if official_name.lower().endswith(".pdf"):
                            completed_data, filled_fields = _prefill_official_pdf(
                                official_data, rec, client, pros or {})
                            parts.append(completed_data if filled_fields else official_data)
                            if not filled_fields:
                                annex_registry_issue = (
                                    f"Formularul oficial PDF pentru Anexa {annex_no} nu are câmpuri text compatibile "
                                    "pentru precompletare. PDF-ul include formularul original și fișa DNS de precompletare; "
                                    "completați și verificați formularul oficial înainte de depunere."
                                )
                        else:
                            annex_registry_issue = f"Formularul oficial pentru Anexa {annex_no} este disponibil ca {official_name}; originalul se găsește în pachetul ZIP, nu în PDF-ul combinat."
                    except Exception as exc:
                        logger.warning("ATR official annex PDF include failed: %s", exc)
                        annex_registry_issue = f"Formularul oficial pentru Anexa {annex_no} nu a putut fi descărcat la generare; verificați pachetul ZIP și registrul formularelor."
            else:
                annex_registry_issue = "Tipul cererii nu are o mapare de anexă verificată pentru operatorul selectat."
        else:
            annex_registry_issue = "Operatorul de distribuție nu este selectat; anexa oficială aplicabilă nu poate fi stabilită."
    unavailable = list(client_document_issues)
    if full:
        for k, title, _ in ATR.DOCS:
            for f in att.get(k) or []:
                try:
                    data, ct = get_object(f["storage_path"])
                    parts.append(OPIS.file_pdf(data, ct))
                except Exception as e:
                    logger.error(f"atr attach {k}: {e}")
                    unavailable.append(f"{title} — {f.get('original_filename') or 'fișier atașat'}")
            # Catalog sheets are model-linked evidence and must be included even when
            # the user also attached a manual file under the same checklist item.
            if not att.get(k) or k == "fise":
                for p in auto.get(k) or []:
                    try:
                        if p:
                            parts += await OPIS.position_pdf(p, pros, client, base, info["titles"], get_object)
                    except Exception as e:
                        logger.error(f"atr auto {k}: {e}")
                        unavailable.append(p.get("title") or title)
        for document in client_documents:
            try:
                parts.append(OPIS.file_pdf(document["data"], document["content_type"]))
            except Exception as exc:
                logger.warning("ATR client document could not be merged (%s): %s", document["name"], exc)
                unavailable.append(f"{document['label']} — {document['name']}")
        for document in atr_catalog_files:
            try:
                data, content_type = get_object(document["storage_path"])
                parts.append(OPIS.file_pdf(data, content_type or document.get("content_type") or "application/pdf"))
            except Exception as exc:
                logger.warning("ATR catalog document could not be merged (%s): %s", document.get("catalog_id"), exc)
                unavailable.append(f"{document.get('kind') or 'Document catalog'} — {document.get('model') or 'echipament'}")
    miss = [k for k in ATR.required(rec) if k not in attached]
    request_type_missing = not ATR.rtype(rec)
    doc_titles = {k: title for k, title, _ in ATR.DOCS}
    missing_titles = [f"Document obligatoriu lipsă: {doc_titles.get(k, k)}" for k in miss]
    if request_type_missing:
        missing_titles.insert(0, "Tipul solicitării ATR nu este selectat sau nu este recunoscut")
    annex_issues = ATR.deer_annex_issues(rec, pros or {})
    missing_titles.extend(annex_issues)
    if annex_registry_issue:
        missing_titles.append(annex_registry_issue)
    report = OPIS._incomplete_report({"positions": [], "common_missing": missing_titles}, unavailable)
    if full and report:
        parts.append(report)
    w = PdfWriter()
    for b in parts:
        try:
            for pg in PdfReader(io.BytesIO(b)).pages:
                w.add_page(pg)
        except Exception as e:
            logger.error(f"atr merge: {e}")
    o = io.BytesIO(); w.write(o)
    incomplete = bool(miss or unavailable or request_type_missing or annex_issues or annex_registry_issue)
    name = f"{'DOSAR_ATR' if full else 'CERERE_ATR'}_{(client.get('name') or rec.get('client_name') or '').replace(' ', '_')}{'_INCOMPLET' if full and incomplete else ''}.pdf"
    return o.getvalue(), name

@api_router.get("/power/{item_id}/official-docx")
async def power_official_docx(item_id: str, authorization: str = Header(None), auth: str = Query(None)):
    """Generate the official DEER Annex 1 DOCX for a power-increase request."""
    user = await user_from_token(authorization, auth)
    rec = await check_access(user, "power", item_id)
    client = await get_client(user["id"], rec)
    settings = await db.settings.find_one({"owner": user["id"]}, {"_id": 0}) or {}
    pros = {}
    if rec.get("pros_id") and await db.prosumator.find_one(
        {**scope_q(user, "prosumator"), "id": rec["pros_id"]}, {"id": 1}
    ):
        pros, pclient, settings, _ = await dossier_ctx(user, rec["pros_id"])
        client = {**(pclient or {}), **(client or {})}
    else:
        from atr_equipment import from_request
        pros = from_request(rec, field="power_cef")

    guard_power_prosumer_scope(rec, pros)
    operator = ATR.op_key(rec.get("operator"), pros.get("operator"), client.get("operator"))
    if operator != "deer":
        raise HTTPException(status_code=422, detail="Formularul DOCX completabil este disponibil pentru DEER. Pentru alți operatori, folosiți formularele oficiale din registrul OD.")
    client_kind = str(client.get("kind") or rec.get("applicant_type") or "").strip().casefold()
    applicant_type = rec.get("applicant_type")
    if not applicant_type:
        if "jurid" in client_kind or client_kind in ("pj", "company", "firmă", "firma"):
            applicant_type = "Persoană juridică"
        elif "fizic" in client_kind or client_kind in ("pf", "individual"):
            applicant_type = "Persoană fizică"
        else:
            raise HTTPException(status_code=422, detail="Selectați tipul clientului (persoană fizică sau juridică) în fișa clientului înainte de generarea formularului oficial.")

    case = "loc nou" if rec.get("request_kind") == "nou" else "spor de putere"
    official_rec = {
        **rec,
        "operator": rec.get("operator") or pros.get("operator") or client.get("operator") or "DEER",
        "deer_case": case,
        "request_type": "nou" if rec.get("request_kind") == "nou" else "spor",
        "applicant_type": applicant_type,
    }
    if rec.get("requested_kva") not in (None, "") and official_rec.get("p_abs_kva") in (None, ""):
        official_rec["p_abs_kva"] = rec["requested_kva"]
    try:
        payload = ATR.render_deer_official_docx(official_rec, client or {}, settings, pros or {})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        logger.exception("DEER power-increase official DOCX generation failed")
        raise HTTPException(status_code=500, detail="Nu am putut genera formularul DEER. Verificați dacă șablonul oficial este disponibil.")
    safe_name = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in str((client or {}).get("name") or "client")).strip().replace(" ", "_")
    case_name = "loc_nou" if rec.get("request_kind") == "nou" else "spor_putere"
    filename = f"DEER_Anexa1_{case_name}_{safe_name}.docx"
    return Response(content=payload, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": disp("attachment", filename)})


@api_router.get("/power/{item_id}/official-annex")
async def power_official_annex(item_id: str, authorization: str = Header(None), auth: str = Query(None)):
    """Download the selected operator's official Annex 1, prefilled only where safe."""
    user = await user_from_token(authorization, auth)
    rec = await check_access(user, "power", item_id)
    client = await get_client(user["id"], rec)
    settings = await db.settings.find_one({"owner": user["id"]}, {"_id": 0}) or {}
    pros = {}
    if rec.get("pros_id") and await db.prosumator.find_one(
        {**scope_q(user, "prosumator"), "id": rec["pros_id"]}, {"id": 1}
    ):
        pros, pclient, settings, _ = await dossier_ctx(user, rec["pros_id"])
        client = {**(pclient or {}), **(client or {})}
    else:
        from atr_equipment import from_request
        pros = from_request(rec, field="power_cef")

    guard_power_prosumer_scope(rec, pros)
    operator_key = ATR.op_key(rec.get("operator"), pros.get("operator"), client.get("operator"))
    if not operator_key:
        raise HTTPException(status_code=422, detail="Selectați operatorul de distribuție în dosar.")
    is_new = rec.get("request_kind") == "nou"
    case = "loc nou" if is_new else "spor de putere"
    annex_rec = {
        **rec,
        "operator": rec.get("operator") or pros.get("operator") or client.get("operator"),
        "request_type": "nou" if is_new else "spor",
        "deer_case": case,
        "kind": rec.get("kind") or "loc de consum și de producere",
    }
    if rec.get("requested_kva") not in (None, "") and annex_rec.get("p_abs_kva") in (None, ""):
        annex_rec["p_abs_kva"] = rec["requested_kva"]

    if operator_key == "deer":
        client_kind = str(client.get("kind") or rec.get("applicant_type") or "").strip().casefold()
        applicant_type = rec.get("applicant_type")
        if not applicant_type:
            if "jurid" in client_kind or client_kind in ("pj", "company", "firmă", "firma"):
                applicant_type = "Persoană juridică"
            elif "fizic" in client_kind or client_kind in ("pf", "individual"):
                applicant_type = "Persoană fizică"
            else:
                raise HTTPException(status_code=422, detail="Selectați tipul clientului în fișa clientului înainte de generarea anexei oficiale.")
        annex_rec["applicant_type"] = applicant_type
        try:
            payload = ATR.render_deer_official_docx(annex_rec, client or {}, settings, pros or {})
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except Exception:
            logger.exception("DEER power official annex generation failed")
            raise HTTPException(status_code=500, detail="Nu am putut genera formularul oficial DEER.")
        safe_name = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in str((client or {}).get("name") or "client")).strip().replace(" ", "_")
        filename = f"DEER_Anexa1_{'loc_nou' if is_new else 'spor_putere'}_{safe_name}.docx"
        return Response(content=payload, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": disp("attachment", filename)})

    from atr_routes import _registry_forms_for_request, _fetch_registry_annex, _prefill_official_pdf
    annex_no, forms = await _registry_forms_for_request(operator_key, annex_rec, pros or {})
    if not annex_no or not forms:
        raise HTTPException(status_code=404, detail="Nu există un formular oficial verificat pentru tipul cererii și operatorul selectat. Verificați Registrul formularelor oficiale.")
    try:
        payload, filename = await _fetch_registry_annex(forms[0], operator_key)
    except Exception as exc:
        logger.warning("Official power annex fetch failed (%s): %s", operator_key, exc)
        raise HTTPException(status_code=502, detail="Formularul oficial al operatorului nu este disponibil momentan. Verificați Registrul formularelor oficiale.")
    if filename.lower().endswith(".pdf"):
        payload, _filled_fields = _prefill_official_pdf(payload, annex_rec, client or {}, pros or {})
        media_type = "application/pdf"
    elif filename.lower().endswith(".docx"):
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        raise HTTPException(status_code=502, detail="Formatul formularului oficial nu este acceptat.")
    return Response(content=payload, media_type=media_type,
                    headers={"Content-Disposition": disp("attachment", filename)})


@api_router.get("/power/{item_id}/pdf")
async def power_pdf(item_id: str, full: int = 0, authorization: str = Header(None), auth: str = Query(None)):
    user = await user_from_token(authorization, auth)
    rec = await check_access(user, "power", item_id)
    client = await get_client(user["id"], rec)
    base = await db.settings.find_one({"owner": user["id"]}, {"_id": 0}) or {}
    pros, auto, info = None, {}, None
    if rec.get("pros_id") and await db.prosumator.find_one({**scope_q(user, "prosumator"), "id": rec["pros_id"]}, {"id": 1}):
        pros, pclient, ps, info = await dossier_ctx(user, rec["pros_id"])
        client = client or pclient
        base = ps
        bykey = {p["key"]: p for p in info["positions"]}
        auto = {"h": [bykey.get("receptie")], "i": [bykey.get("priza")], "k": [bykey.get("schema")],
                "j": [p for p in info["positions"] if p.get("source") == "catalog" and p.get("files")]}
    else:
        from atr_equipment import from_request
        pros = from_request(rec, field="power_cef") or None
    guard_power_prosumer_scope(rec, pros or {})
    power_catalog_files = []
    direct_catalog_complete = False
    if pros and info is None:
        from atr_equipment import catalog_documents_complete as direct_catalog_documents_complete
        await auto_import_selected_catalog_documents(user, pros)
        power_catalog_files = await catalog_files(user["id"], pros)
        direct_catalog_complete = direct_catalog_documents_complete(pros.get("cef"), power_catalog_files)
    att = rec.get("attachments") or {}
    attached = {k for k, v in att.items() if v}
    if pros and info is None:
        if direct_catalog_complete:
            attached.add("j")
        else:
            attached.discard("j")
    # Only mark auto-linked source documents present after the prosumer opis has
    # cleared their missing-data and approval checks. Draft PDFs may still be
    # included in the full bundle, but they cannot make Anexa 1 appear complete.
    source_positions = {
        "h": (auto.get("h") or [None])[0],
        "i": (auto.get("i") or [None])[0],
        "k": (auto.get("k") or [None])[0],
    }
    for key, position in source_positions.items():
        if position and position.get("auto_status") in ("generat", "atașat"):
            attached.add(key)
    if pros and info is not None and not rec.get("is_test") and catalog_documents_complete(pros, info.get("positions", [])):
        attached.add("j")
    parts = [PWR.render_anexa1(rec, client, base, pros or {}, attached, ATR.op_key(rec.get("operator"), (pros or {}).get("operator"), client.get("operator")))]
    unavailable = []
    annex_registry_issue = ""
    if pros and info is not None and not rec.get("is_test"):
        # Use the same per-model catalog evidence as the prosumer and ATR dossiers;
        # a datasheet for one model cannot satisfy another model's requirement.
        if not catalog_documents_complete(pros, info.get("positions", [])):
            attached.discard("j")
            parts[0] = PWR.render_anexa1(rec, client, base, pros, attached,
                ATR.op_key(rec.get("operator"), pros.get("operator"), client.get("operator")))
    if full:
        operator_key = ATR.op_key(rec.get("operator"), (pros or {}).get("operator"), client.get("operator"))
        is_new = rec.get("request_kind") == "nou"
        annex_rec = {
            **rec,
            "operator": rec.get("operator") or (pros or {}).get("operator") or client.get("operator"),
            "request_type": "nou" if is_new else "spor",
            "deer_case": "loc nou" if is_new else "spor de putere",
            "kind": rec.get("kind") or "loc de consum și de producere",
        }
        if rec.get("requested_kva") not in (None, "") and annex_rec.get("p_abs_kva") in (None, ""):
            annex_rec["p_abs_kva"] = rec["requested_kva"]
        if operator_key:
            if operator_key == "deer":
                annex_title = "Anexa 1 oficială DEER (DOCX — descărcare separată)"
                annex_registry_issue = "Formularul oficial DEER este DOCX și se descarcă separat din butonul «Anexa 1 oficială DEER»; PDF-ul dosarului conține fișa de precompletare, nu formularul operatorului."
                annex_no, forms = 1, [{"title": annex_title}]
            else:
                from atr_routes import _registry_forms_for_request, _fetch_registry_annex, _prefill_official_pdf
                annex_no, forms = await _registry_forms_for_request(operator_key, annex_rec, pros or {})
                annex_title = (forms[0].get("title") if forms else "")
            if annex_no:
                parts.append(ATR.render_operator_annex_prep(
                    annex_rec, client or {}, pros or {}, operator_key, annex_no, annex_title))
            if not forms:
                annex_registry_issue = annex_registry_issue or f"Nu există un formular oficial verificat în registru pentru Anexa {annex_no or 1} a operatorului selectat."
            elif operator_key != "deer":
                try:
                    official_data, official_name = await _fetch_registry_annex(forms[0], operator_key)
                    if official_name.lower().endswith(".pdf"):
                        completed_data, filled_fields = _prefill_official_pdf(
                            official_data, annex_rec, client or {}, pros or {})
                        parts.append(completed_data if filled_fields else official_data)
                        if not filled_fields:
                            annex_registry_issue = "Formularul PDF oficial nu are câmpuri text semantice compatibile; originalul și fișa DNS de precompletare sunt incluse, iar formularul trebuie verificat/completat manual."
                    else:
                        annex_registry_issue = f"Formularul oficial {official_name} este DOCX și se descarcă separat din butonul «Anexa 1 oficială OD»; PDF-ul dosarului nu îl poate încorpora."
                except Exception as exc:
                    logger.warning("Official power annex could not be included: %s", exc)
                    annex_registry_issue = "Formularul oficial nu a putut fi preluat la generare; descărcați-l separat din Registrul formularelor oficiale."
        else:
            annex_registry_issue = "Selectați operatorul de distribuție pentru a stabili formularul oficial aplicabil."
        for k, title in PWR.DOCS:
            for f in att.get(k) or []:
                try:
                    data, ct = get_object(f["storage_path"])
                    parts.append(OPIS.file_pdf(data, ct))
                except Exception as e:
                    logger.error(f"power attach {k}: {e}")
                    unavailable.append(f"{title} — {f.get('original_filename') or 'fișier atașat'}")
            # Include model-linked catalog evidence alongside manual attachments.
            if not att.get(k) or k == "j":
                for p in auto.get(k) or []:
                    try:
                        if p:
                            parts += await OPIS.position_pdf(p, pros, client, base, info["titles"], get_object)
                    except Exception as e:
                        logger.error(f"power auto {k}: {e}")
                        unavailable.append(p.get("title") or title)
        if info is None and power_catalog_files:
            for catalog_file in power_catalog_files:
                try:
                    payload, content_type = get_object(catalog_file["storage_path"])
                    parts.append(OPIS.file_pdf(payload, content_type))
                except Exception as exc:
                    logger.warning("Power direct catalog PDF could not be included: %s", exc)
                    unavailable.append(catalog_file.get("original_filename") or catalog_file.get("model") or "fișă catalog")
    new_request = rec.get("request_kind") == "nou"
    juridical = "jurid" in str((client or {}).get("kind") or "").lower()
    required_keys = {"a"} | ({"b"} if juridical else set()) | ({"c", "d", "e", "f", "g"} if new_request else {"h", "i", "j", "k"})
    missing_keys = sorted(k for k in required_keys if k not in attached)
    pwr_titles = dict(PWR.DOCS)
    missing_titles = [f"Document obligatoriu lipsă: {pwr_titles.get(k, k)}" for k in missing_keys]
    if annex_registry_issue:
        missing_titles.append(annex_registry_issue)
    report = OPIS._incomplete_report({"positions": [], "common_missing": missing_titles}, unavailable)
    if full and report:
        parts.append(report)
    w = PdfWriter()
    for b in parts:
        try:
            for pg in PdfReader(io.BytesIO(b)).pages:
                w.add_page(pg)
        except Exception as e:
            logger.error(f"power merge: {e}")
    o = io.BytesIO(); w.write(o)
    incomplete = bool(missing_keys or unavailable or annex_registry_issue)
    name = f"{'DOSAR_SPOR_PUTERE' if full else 'ANEXA1_DEER'}_{(client.get('name') or rec.get('client_name') or '').replace(' ', '_')}{'_INCOMPLET' if full and incomplete else ''}.pdf"
    return Response(content=o.getvalue(), media_type="application/pdf", headers={"Content-Disposition": disp('inline', name)})

@api_router.get("/power/{item_id}/package.zip")
async def power_package(item_id: str, authorization: str = Header(None), auth: str = Query(None)):
    """Create a transfer-ready ZIP with the dossier, OD annex, source files and separate schema/PRAM."""
    import io
    import os
    import re
    import zipfile

    user = await user_from_token(authorization, auth)
    rec = await check_access(user, "power", item_id)
    package = io.BytesIO()
    notes = [
        "DNS Energy — pachet pentru depunerea cererii de spor / racordare.",
        "Verificați documentele, datele și versiunea formularelor în portalul oficial al operatorului înainte de depunere.",
        "Documentele generate sunt marcate ciornă când lipsesc date sau aprobarea tehnică; pachetul nu atestă conformitatea legală.",
    ]
    total_size = 0
    max_size = 100 * 1024 * 1024

    def add_file(archive, arcname, payload):
        nonlocal total_size
        payload = bytes(payload)
        if len(payload) > max_size or total_size + len(payload) > max_size:
            notes.append(f"Fișier omis, limita pachetului de 100 MB a fost depășită: {arcname}")
            return False
        safe_parts = [part for part in str(arcname).replace("\\", "/").split("/") if part not in ("", ".", "..")]
        safe_name = "/".join(safe_parts) or "document"
        archive.writestr(safe_name, payload)
        total_size += len(payload)
        return True

    client = await get_client(user["id"], rec) or {}
    client_name = str(client.get("name") or rec.get("client_name") or "client")
    safe_client = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in client_name).strip().replace(" ", "_") or "client"
    pdf_response = await power_pdf(item_id, full=1, authorization=authorization, auth=auth)

    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        add_file(archive, f"DOSAR_SPOR_PUTERE_{safe_client}.pdf", pdf_response.body)

        try:
            official_response = await power_official_annex(item_id, authorization=authorization, auth=auth)
            disposition = official_response.headers.get("content-disposition", "")
            match = re.search(r'filename="?([^";]+)"?', disposition, re.I)
            official_name = os.path.basename(match.group(1)) if match else "Anexa1_oficiala_OD"
            add_file(archive, f"Anexe oficiale/{official_name}", official_response.body)
            notes.append(f"Formular oficial inclus: {official_name}. Verificați și semnați varianta cerută de operator.")
        except HTTPException as exc:
            notes.append(f"Formularul oficial OD nu a putut fi inclus automat (HTTP {exc.status_code}): {exc.detail}")

        owner_prefix = f"{APP_NAME}/uploads/{user['id']}/"
        attachment_count = 0
        for slot, files in (rec.get("attachments") or {}).items():
            for entry in files or []:
                path = str((entry or {}).get("storage_path") or "")
                original = os.path.basename(str((entry or {}).get("original_filename") or f"{slot}.pdf"))
                if not path.startswith(owner_prefix):
                    notes.append(f"Fișier atașat ignorat deoarece nu aparține spațiului acestui cont: {original}")
                    continue
                try:
                    payload, _content_type = get_object(path)
                    if add_file(archive, f"Documente atașate/{slot}/{original}", payload):
                        attachment_count += 1
                except Exception:
                    logger.exception("Power package attachment could not be read (%s)", path)
                    notes.append(f"Fișier atașat indisponibil în stocare: {original}")
        notes.append(f"Fișiere atașate separat incluse: {attachment_count}.")

        pros_id = rec.get("pros_id")
        if pros_id and await db.prosumator.find_one({**scope_q(user, "prosumator"), "id": pros_id}, {"id": 1}):
            for key, label, filename in (
                ("schema", "Schema monofilară", f"Schema_monofilară_{safe_client}.pdf"),
                ("priza", "Buletin PRAM / priză de pământ", f"Buletin_PRAM_{safe_client}.pdf"),
            ):
                try:
                    response = await dossier_file(pros_id, key, download=1, authorization=authorization, auth=auth)
                    add_file(archive, f"Documente separate/{filename}", response.body)
                    notes.append(f"{label}: inclus separat; verificați marcajul ciornă/aprobat și completitudinea înainte de depunere.")
                except HTTPException as exc:
                    notes.append(f"{label}: nu a putut fi generat/atașat (HTTP {exc.status_code}): {exc.detail}")
        else:
            notes.append("Schema și PRAM separat nu au putut fi extrase: dosarul de spor nu are un dosar de prosumator asociat.")

        archive.writestr("CITESTE_INAINTE.txt", "\n".join(notes))

    return Response(
        content=package.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": disp("attachment", f"Pachet_depunere_spor_{safe_client}.zip")},
    )


# ---------------- Semnare la distanță (semnătură electronică simplă) ----------------
import hashlib
import re
import secrets
import base64
from html import escape as hesc
from mailer import send_email, EMAIL_FROM_NAME
from reportlab.pdfgen import canvas as rlc
from reportlab.lib.pagesizes import A4 as RA4
from reportlab.lib.utils import ImageReader

SIGN_ACTIVE = ("De trimis", "Link trimis", "Deschis")
sha = lambda b: hashlib.sha256(b).hexdigest()
now_iso = lambda: datetime.now(timezone.utc).isoformat()

def sign_status(r: dict) -> str:
    if r["status"] in SIGN_ACTIVE and r.get("expires_at") and r["expires_at"] < now_iso():
        return "Expirat"
    return r["status"]

def sign_public(r: dict) -> dict:
    out = {k: r.get(k) for k in ("id", "group_id", "dossier_id", "module", "client_name", "pos_key", "doc_title", "signer_name", "signer_email",
                                 "signer_phone", "role", "expires_at", "created_at", "signed_at", "refused_reason", "doc_sha256", "signed_sha256", "revoked")}
    out["status"] = sign_status(r)
    out["history"] = r.get("history", [])
    out["has_signed_file"] = bool(r.get("signed_file"))
    return out

def client_meta(request: Request) -> dict:
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "")).split(",")[0].strip()
    return {"ip": ip, "ua": request.headers.get("user-agent", "")[:300]}

def hist(action: str, meta: dict = None, detail: str = "") -> dict:
    return {"at": now_iso(), "action": action, "detail": detail, **(meta or {})}

def parse_days(v) -> int:
    try:
        d = int(v if v not in (None, "") else 7)
        if str(v).strip() not in ("", "None") and float(v) != d:
            raise ValueError
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Valabilitatea trebuie să fie un număr întreg de zile (1–90)")
    if not 1 <= d <= 90:
        raise HTTPException(status_code=400, detail="Valabilitatea trebuie să fie între 1 și 90 de zile")
    return d

def new_token(days: float):
    t = secrets.token_urlsafe(32)
    return t, sha(t.encode()), (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

@api_router.post("/sign/requests")
async def sign_create(request: Request, user: dict = Depends(get_current_user)):
    guard("prosumator", user, write=True); need(user, "sign_remote", True)
    b = await request.json()
    did, keys, signers = b.get("dossier_id"), b.get("pos_keys") or [], b.get("signers") or []
    days = parse_days(b.get("expires_days"))
    if not keys or not signers:
        raise HTTPException(status_code=400, detail="Alege documentele și semnatarii")
    if len(signers) != 1:
        raise HTTPException(status_code=400, detail="Documentele dosarului se trimit la semnare doar către client (un singur semnatar)")
    signers = [{**signers[0], "role": "Beneficiar"}]
    for s in signers:
        if not (s.get("name") or "").strip() or "@" not in (s.get("email") or ""):
            raise HTTPException(status_code=400, detail="Fiecare semnatar are nevoie de nume și e-mail valid (pentru codul de verificare)")
    return await create_sign_requests(user, did, keys, signers, days)

async def create_sign_requests(user, did, keys, signers, days):
    rec, client, settings, info = await dossier_ctx(user, did)
    pos = {p["key"]: p for p in info["positions"]}
    out = []
    st_sld = SZ.state(rec, client, settings)
    if any(k in ("schema", "fisa_tehnica") for k in keys) and st_sld["status"] != "approved":
        raise HTTPException(status_code=400, detail="Schema monofilară / fișa tehnică pot fi trimise la semnare doar după aprobarea tehnică")
    for k in keys:
        if k not in pos:
            raise HTTPException(status_code=404, detail=f"Poziție inexistentă: {k}")
        parts = await OPIS.position_pdf(pos[k], rec, client, settings, info["titles"], get_object, force_generated=True)
        if not parts:
            raise HTTPException(status_code=400, detail=f"Documentul „{pos[k]['title']}” nu poate fi generat")
        w = PdfWriter()
        for part in parts:
            for pg in PdfReader(io.BytesIO(part)).pages:
                w.add_page(pg)
        o = io.BytesIO(); w.write(o); pdf = o.getvalue()
        gid = str(uuid.uuid4())
        stored = put_object(f"{APP_NAME}/sign/{user['id']}/{gid}/original.pdf", pdf, "application/pdf")
        for s in signers:
            t, th, exp = new_token(days)
            r = _new(user, {"group_id": gid, "dossier_id": did, "client_name": client.get("name") or rec.get("client_name"), "pos_key": k,
                            "doc_title": pos[k]["title"], "doc_path": stored["path"], "doc_sha256": sha(pdf), "signer_name": s["name"].strip(),
                            "signer_email": s["email"].strip(), "signer_phone": (s.get("phone") or "").strip(), "role": (s.get("role") or "Beneficiar").strip(),
                            "status": "De trimis", "token_hash": th, "expires_at": exp, "otp_sends": 0, "otp_attempts": 0,
                            "sld_hash": st_sld["fingerprint"] if k in ("schema", "fisa_tehnica") else None,
                            "pif_hash": OPIS.PIFDOC.fingerprint(rec) if k == "pif_pv" else None, "is_test": bool(rec.get("is_test")),
                            "history": [hist("Cerere creată", None, f"de {user.get('email')}; link valabil până la {exp[:16]} UTC")]})
            await db.sign_requests.insert_one(dict(r))
            out.append({**sign_public(r), "token": t})
        await db.prosumator.update_one({"id": did, "owner": user["id"]}, {"$set": {f"opis.{k}.status": "necesită semnătură"}})
    await audit(user, "cerere semnare", "prosumator", did, keys)
    return out

@api_router.get("/sign/requests")
async def sign_list(dossier_id: Optional[str] = None, client_name: Optional[str] = None, module: str = "prosumator", user: dict = Depends(get_current_user)):
    need(user, "sign_remote")
    q = {"owner": user["id"]}
    if not is_admin(user):
        q["dossier_id"] = {"$in": [x["id"] for m in ("prosumator", "diu") for x in await db[m].find(scope_q(user, m), {"id": 1}).to_list(5000)]}
    if dossier_id:
        if module not in ("prosumator", "diu"):
            raise HTTPException(status_code=400, detail="Modul invalid")
        await check_access(user, module, dossier_id)
        q["dossier_id"] = dossier_id
    if client_name:
        q["client_name"] = client_name
    return [sign_public(r) for r in await db.sign_requests.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)]

async def sign_own(user, rid):
    r = await db.sign_requests.find_one({"id": rid, "owner": user["id"]}, {"_id": 0})
    if not r:
        raise HTTPException(status_code=404, detail="Cerere inexistentă")
    if not is_admin(user):
        if (r.get("module") or "prosumator") == "contracts":
            need(user, "oferte")
        else:
            await check_access(user, r.get("module") or "prosumator", r["dossier_id"])
    return r

@api_router.post("/sign/requests/{rid}/sent")
async def sign_mark_sent(rid: str, request: Request, user: dict = Depends(get_current_user)):
    guard("prosumator", user, write=True); need(user, "sign_remote", True)
    r = await sign_own(user, rid)
    ch = ((await request.json()).get("channel") or "copiat")[:30]
    upd = {"$push": {"history": hist("Link trimis", None, f"canal: {ch}; de {user.get('email')}")}}
    if sign_status(r) == "De trimis":
        upd["$set"] = {"status": "Link trimis"}
    await db.sign_requests.update_one({"id": rid}, upd)
    return {"ok": True}

@api_router.post("/sign/requests/{rid}/new-link")
async def sign_new_link(rid: str, request: Request, user: dict = Depends(get_current_user)):
    guard("prosumator", user, write=True); need(user, "sign_remote", True)
    r = await sign_own(user, rid)
    if r["status"] in ("Semnat", "Refuzat"):
        raise HTTPException(status_code=400, detail="Documentul a fost deja semnat sau refuzat — creează o cerere nouă")
    days = parse_days((await request.json()).get("expires_days"))
    t, th, exp = new_token(days)
    await db.sign_requests.update_one({"id": rid}, {"$set": {"token_hash": th, "expires_at": exp, "status": "De trimis", "revoked": False, "otp_hash": None,
                                                              "otp_attempts": 0, "otp_sends": 0, "otp_last": None}, "$push": {"history": hist("Link nou generat", None, f"linkul anterior invalidat; valabil până la {exp[:16]} UTC; de {user.get('email')}")}})
    return {**sign_public({**r, "status": "De trimis", "expires_at": exp}), "token": t}

@api_router.post("/sign/requests/{rid}/revoke")
async def sign_revoke(rid: str, user: dict = Depends(get_current_user)):
    guard("prosumator", user, write=True); need(user, "sign_remote", True)
    r = await sign_own(user, rid)
    if r["status"] in ("Semnat", "Refuzat"):
        raise HTTPException(status_code=400, detail="Cererea este deja închisă")
    await db.sign_requests.update_one({"id": rid}, {"$set": {"status": "Expirat", "revoked": True, "token_hash": None},
                                                    "$push": {"history": hist("Link revocat", None, f"de {user.get('email')}")}})
    return {"ok": True}

@api_router.get("/sign/requests/{rid}/file")
async def sign_file(rid: str, kind: str = "signed", authorization: str = Header(None), auth: str = Query(None)):
    user = await user_from_token(authorization, auth)
    r = await sign_own(user, rid)
    path = r.get("signed_file", {}).get("storage_path") if kind == "signed" else r["doc_path"]
    if not path:
        raise HTTPException(status_code=404, detail="Documentul semnat nu există încă")
    data, _ = get_object(path)
    return Response(content=data, media_type="application/pdf", headers={"Content-Disposition": disp('inline', f"{kind}_{r['pos_key']}.pdf")})

async def sign_by_token(token: str) -> dict:
    r = await db.sign_requests.find_one({"token_hash": sha(token.encode())}, {"_id": 0}) if token else None
    if not r:
        raise HTTPException(status_code=404, detail="Link invalid sau revocat")
    return r

def mask(e: str) -> str:
    u, _, d = e.partition("@")
    return (u[:2] + "***@" + d) if d else "***"

@api_router.get("/public/sign/{token}")
async def pub_sign_info(token: str, request: Request):
    r = await sign_by_token(token)
    st = sign_status(r)
    if st == "Expirat" and r["status"] != "Expirat":
        await db.sign_requests.update_one({"id": r["id"]}, {"$set": {"status": "Expirat"}, "$push": {"history": hist("Link expirat", client_meta(request))}})
    elif st in SIGN_ACTIVE:
        upd = {"$push": {"history": hist("Document deschis", client_meta(request))}}
        if st != "Deschis":
            upd["$set"] = {"status": "Deschis", "opened_at": now_iso()}
        await db.sign_requests.update_one({"id": r["id"]}, upd)
        st = "Deschis"
    s = await db.settings.find_one({"owner": r["owner"]}, {"_id": 0, "company": 1}) or {}
    pages = 0
    if st in SIGN_ACTIVE:
        import pymupdf
        data, _ = get_object(r["doc_path"])
        pages = pymupdf.open(stream=data, filetype="pdf").page_count
    return {"status": st, "pages": pages, "doc_title": r["doc_title"], "signer_name": r["signer_name"], "role": r["role"], "client_name": r["client_name"],
            "company": s.get("company") or "DNS HOSTESS SRL", "email_masked": mask(r["signer_email"]), "expires_at": r["expires_at"],
            "doc_sha256": r["doc_sha256"], "signed_at": r.get("signed_at")}

@api_router.get("/public/sign/{token}/document")
async def pub_sign_doc(token: str):
    r = await sign_by_token(token)
    if sign_status(r) not in SIGN_ACTIVE:
        raise HTTPException(status_code=410, detail="Linkul nu mai este activ")
    data, _ = get_object(r["doc_path"])
    return Response(content=data, media_type="application/pdf", headers={"Content-Disposition": 'inline; filename="document.pdf"'})

@api_router.get("/public/sign/{token}/page/{n}")
async def pub_sign_page(token: str, n: int):
    import pymupdf
    r = await sign_by_token(token)
    if sign_status(r) not in SIGN_ACTIVE:
        raise HTTPException(status_code=410, detail="Linkul nu mai este activ")
    data, _ = get_object(r["doc_path"])
    d = pymupdf.open(stream=data, filetype="pdf")
    if n < 0 or n >= d.page_count:
        raise HTTPException(status_code=404, detail="Pagină inexistentă")
    return Response(content=d[n].get_pixmap(dpi=150).tobytes("png"), media_type="image/png")

@api_router.post("/public/sign/{token}/otp")
async def pub_sign_otp(token: str, request: Request):
    r = await sign_by_token(token)
    if sign_status(r) not in SIGN_ACTIVE:
        raise HTTPException(status_code=410, detail="Linkul nu mai este activ")
    if r.get("otp_sends", 0) >= 5:
        raise HTTPException(status_code=429, detail="Ai cerut prea multe coduri. Contactează emitentul documentului.")
    if r.get("otp_last") and r["otp_last"] > (datetime.now(timezone.utc) - timedelta(seconds=45)).isoformat():
        raise HTTPException(status_code=429, detail="Așteaptă 45 de secunde înainte de un cod nou")
    code = f"{secrets.randbelow(1000000):06d}"
    html = (f'<table role="presentation" width="100%"><tr><td style="padding:24px;font-family:Arial,sans-serif;color:#0b1f3a">'
            f'<p>Bună ziua, {hesc(r["signer_name"])},</p><p>Codul pentru semnarea documentului <b>{hesc(r["doc_title"])}</b> este:</p>'
            f'<p style="font-size:28px;font-weight:bold;letter-spacing:6px">{code}</p>'
            f'<p>Codul este valabil 10 minute. Introdu-l doar pe pagina de semnare deschisă din linkul primit. Dacă nu ai cerut acest cod, ignoră mesajul.</p>'
            f'<p style="font-size:12px;color:#888">Trimis de {hesc(EMAIL_FROM_NAME)}. Nu îți vom cere niciodată parole sau date de card prin e-mail.</p></td></tr></table>')
    if not await deliver(r["owner"], bool(r.get("is_test")), r["signer_email"], f"Cod de semnare — {r['doc_title'][:60]}", html):
        raise HTTPException(status_code=400, detail="Dosar de TEST: nu este configurat un e-mail de test în Setări de bază — codul nu a fost trimis")
    await db.sign_requests.update_one({"id": r["id"]}, {"$set": {"otp_hash": sha(f"{r['id']}:{code}".encode()), "otp_exp": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
                                                                 "otp_last": now_iso(), "otp_attempts": 0}, "$inc": {"otp_sends": 1},
                                                        "$push": {"history": hist("Cod de verificare trimis", client_meta(request), f"către {mask(r['signer_email'])}")}})
    return {"ok": True, "email_masked": mask(r["signer_email"])}

def evidence_page(r: dict, sig_png: bytes, meta: dict, declared: str, signed_at: str, owner_company: str) -> bytes:
    buf = io.BytesIO()
    c = rlc.Canvas(buf, pagesize=RA4)
    W, H = RA4
    y = H - 60
    c.setFont("LSB", 14); c.drawString(50, y, "FIȘĂ DE EVIDENȚĂ A SEMNĂRII ELECTRONICE" + (" — TEST" if r.get("is_test") else ""))
    if r.get("is_test"):
        c.setFillColorRGB(0.7, 0.15, 0.15); c.setFont("LSB", 10); c.drawString(50, y - 32, "SEMNĂTURĂ DE TEST — date fictive. NU este o semnătură oficială și nu are efecte juridice."); c.setFillColorRGB(0, 0, 0); y -= 14
    y -= 18; c.setFont("LS", 9); c.drawString(50, y, "Tip semnătură: semnătură electronică SIMPLĂ (Reg. UE 910/2014 eIDAS, art. 3 pct. 10). Nu este semnătură avansată sau calificată.")
    rows = [("Document", r["doc_title"]), ("Emitent", owner_company), ("Beneficiar / dosar", r.get("client_name") or ""),
            ("Semnatar (identitate declarată)", declared), ("Rol", r["role"]), ("E-mail verificat prin cod unic", r["signer_email"]),
            ("Data și ora semnării (UTC, server)", signed_at), ("Adresă IP", meta["ip"]), ("Browser / dispozitiv", meta["ua"][:110]),
            ("SHA-256 document semnat (original)", r["doc_sha256"]), ("ID cerere", r["id"]),
            ("Declarație", "Am citit integral documentul și îmi exprim explicit intenția de a-l semna electronic.")]
    y -= 26
    for k, v in rows:
        c.setFont("LSB", 8.5); c.drawString(50, y, k)
        c.setFont("LS", 8.5)
        txt = str(v)
        while txt:
            part = txt[:85]; txt = txt[85:]
            c.drawString(230, y, part); y -= 12
        y -= 4
    y -= 10; c.setFont("LSB", 9); c.drawString(50, y, "Semnătura olografă trasată pe ecran:")
    img = ImageReader(io.BytesIO(sig_png))
    iw, ih = img.getSize(); s = min(260 / iw, 110 / ih)
    c.drawImage(img, 50, y - 10 - ih * s, iw * s, ih * s, mask="auto")
    c.rect(48, y - 12 - ih * s, iw * s + 4, ih * s + 4)
    c.setFont("LS", 7); c.drawString(50, 40, "Istoricul complet al acțiunilor (deschideri, coduri trimise, semnare) este păstrat în aplicația emitentului.")
    c.save()
    return buf.getvalue()

def stamp_pages(pdf: bytes, text: str) -> bytes:
    w = PdfWriter()
    for page in PdfReader(io.BytesIO(pdf)).pages:
        pw, ph = float(page.mediabox.width), float(page.mediabox.height)
        b = io.BytesIO(); c = rlc.Canvas(b, pagesize=(pw, ph)); c.setFont("LS", 6.5); c.setFillGray(0.35)
        c.drawString(20, 10, text[:180]); c.save()
        page.merge_page(PdfReader(io.BytesIO(b.getvalue())).pages[0]); w.add_page(page)
    o = io.BytesIO(); w.write(o); return o.getvalue()

async def rebuild_group(owner: str, gid: str):
    reqs = await db.sign_requests.find({"owner": owner, "group_id": gid}, {"_id": 0}).sort("created_at", 1).to_list(50)
    signed = [x for x in reqs if x["status"] == "Semnat" and x.get("evidence_path")]
    base, _ = get_object(reqs[0]["doc_path"])
    w = PdfWriter()
    for pg in PdfReader(io.BytesIO(stamp_pages(base, ("[TEST — NU ESTE SEMNĂTURĂ OFICIALĂ] " if reqs[0].get("is_test") else "") + "Semnat electronic (semnătură simplă) de: " + ", ".join(f"{x['signer_name']} {x['signed_at'][:16]} UTC" for x in signed) + f" · SHA-256 original {reqs[0]['doc_sha256'][:16]}…"))).pages:
        w.add_page(pg)
    for x in signed:
        ev, _ = get_object(x["evidence_path"])
        for pg in PdfReader(io.BytesIO(ev)).pages:
            w.add_page(pg)
    o = io.BytesIO(); w.write(o); final = o.getvalue()
    st = put_object(f"{APP_NAME}/sign/{owner}/{gid}/signed_{len(signed)}.pdf", final, "application/pdf")
    f = {"storage_path": st["path"], "original_filename": f"{reqs[0]['pos_key']}_semnat.pdf", "content_type": "application/pdf", "size": len(final)}
    if reqs[0].get("sld_hash"):
        f["sld_hash"] = reqs[0]["sld_hash"]
    if reqs[0].get("pif_hash"):
        f["pif_hash"] = reqs[0]["pif_hash"]
    await db.sign_requests.update_many({"owner": owner, "group_id": gid}, {"$set": {"signed_file": f, "signed_sha256": sha(final)}})
    if len(signed) == len(reqs):
        did, mod = reqs[0]["dossier_id"], reqs[0].get("module") or "prosumator"
        if mod == "diu":
            await db.diu.update_one({"id": did, "owner": owner}, {"$set": {f"signed.{reqs[0]['pos_key']}": {**f, "signed_at": signed[-1]["signed_at"]}}})
        elif mod == "contracts":
            await db.contracts.update_one({"id": did, "owner": owner}, {"$set": {"signed": {**f, "signed_at": signed[-1]["signed_at"]}, "status": "Semnat"},
                                                                        "$push": {"history": {"at": now_iso(), "by": "semnătură electronică client", "event": "contract semnat de beneficiar"}}})
        else:
            await db.prosumator.update_one({"id": did, "owner": owner},
                                           {"$set": {f"opis.{reqs[0]['pos_key']}.upload": f, f"opis.{reqs[0]['pos_key']}.status": "atașat"}})
        prec = await db[mod].find_one({"id": did, "owner": owner}, {"_id": 0}) or {}
        cl = await get_client(owner, prec)
        await db.documents.insert_one({"id": str(uuid.uuid4()), "owner": owner, "created_at": now_iso(), "updated_at": now_iso(), "client_id": cl.get("id"),
                                       "dossier_id": reqs[0]["dossier_id"], "client_name": reqs[0].get("client_name"), "kind": "Semnat electronic",
                                       "doc_type": f"{reqs[0]['doc_title']} — semnat", **f})
        if cl.get("id"):
            await db.clients.update_one({"id": cl["id"], "owner": owner}, {"$push": {"docs.semnate": {**f, "original_filename": f"{reqs[0]['doc_title']} — semnat.pdf",
                                                                                                    "signed_at": signed[-1]["signed_at"]}}})

@api_router.post("/public/sign/{token}/sign")
async def pub_sign(token: str, request: Request):
    r = await sign_by_token(token)
    if sign_status(r) not in SIGN_ACTIVE:
        raise HTTPException(status_code=410, detail="Linkul nu mai este activ")
    b = await request.json()
    declared = (b.get("declared_name") or "").strip()
    if not b.get("intent") or not declared:
        raise HTTPException(status_code=400, detail="Confirmă intenția de semnare și scrie numele complet")
    if not r.get("otp_hash") or (r.get("otp_exp") or "") < now_iso():
        raise HTTPException(status_code=400, detail="Cere un cod de verificare pe e-mail")
    if r.get("otp_attempts", 0) >= 5:
        raise HTTPException(status_code=429, detail="Prea multe încercări. Cere un cod nou.")
    if sha(f"{r['id']}:{str(b.get('otp') or '').strip()}".encode()) != r["otp_hash"]:
        await db.sign_requests.update_one({"id": r["id"]}, {"$inc": {"otp_attempts": 1}, "$push": {"history": hist("Cod greșit", client_meta(request))}})
        raise HTTPException(status_code=400, detail="Cod incorect")
    m = re.match(r"^data:image/png;base64,(.+)$", b.get("signature") or "")
    if not m:
        raise HTTPException(status_code=400, detail="Desenează semnătura")
    png = base64.b64decode(m.group(1))
    if len(png) < 800 or len(png) > 2_000_000:
        raise HTTPException(status_code=400, detail="Semnătura nu este validă")
    meta, at = client_meta(request), now_iso()
    claim = await db.sign_requests.update_one({"id": r["id"], "token_hash": r["token_hash"], "status": {"$in": list(SIGN_ACTIVE)}, "otp_hash": r["otp_hash"]},
                                              {"$set": {"status": "Semnat", "signed_at": at, "otp_hash": None}})
    if claim.modified_count == 0:
        raise HTTPException(status_code=409, detail="Documentul a fost deja semnat")
    s = await db.settings.find_one({"owner": r["owner"]}, {"_id": 0, "company": 1}) or {}
    ev = evidence_page(r, png, meta, declared, at, s.get("company") or "DNS HOSTESS SRL")
    evp = put_object(f"{APP_NAME}/sign/{r['owner']}/{r['group_id']}/evidence_{r['id']}.pdf", ev, "application/pdf")
    sigp = put_object(f"{APP_NAME}/sign/{r['owner']}/{r['group_id']}/signature_{r['id']}.png", png, "image/png")
    await db.sign_requests.update_one({"id": r["id"]}, {"$set": {"declared_name": declared,
        "evidence_path": evp["path"], "signature_path": sigp["path"], "sign_meta": meta, "otp_hash": None},
        "$push": {"history": hist("Semnat", meta, f"identitate declarată: {declared}; cod e-mail verificat; intenție confirmată")}})
    await rebuild_group(r["owner"], r["group_id"])
    return {"ok": True, "signed_at": at}

@api_router.post("/public/sign/{token}/refuse")
async def pub_refuse(token: str, request: Request):
    r = await sign_by_token(token)
    if sign_status(r) not in SIGN_ACTIVE:
        raise HTTPException(status_code=410, detail="Linkul nu mai este activ")
    reason = ((await request.json()).get("reason") or "").strip()[:500]
    await db.sign_requests.update_one({"id": r["id"]}, {"$set": {"status": "Refuzat", "refused_reason": reason},
                                                        "$push": {"history": hist("Refuzat", client_meta(request), reason)}})
    return {"ok": True}

# ---------------- Dosar de test ----------------
import test_data as TD

@api_router.post("/test-dossier")
async def test_dossier_create(user: dict = Depends(get_current_user)):
    require(user, "admin")
    existing = await db.prosumator.find_one(
        {"owner": user["id"], "is_test": True},
        {"_id": 0, "id": 1, "number": 1, "client_name": 1},
    )
    if existing:
        return {
            "prosumator_id": existing["id"],
            "number": existing.get("number"),
            "client": existing.get("client_name"),
            "already_exists": True,
        }
    st = await db.settings.find_one({"owner": user["id"]}, {"_id": 0, "test_email": 1}) or {}
    stamp = datetime.now(timezone.utc).strftime("%m%d%H%M%S")
    files = {}
    for k, title in [("auth", "Autorizație personal (TEST)"), ("cert", "Certificat etalonare aparat (TEST)"), ("datasheet", "Fișă tehnică echipament (TEST)"),
                     ("conformity", "Declarație de conformitate echipament (TEST)"), ("clientdoc", "Document client (TEST)")]:
        data = TD.placeholder_pdf(title)
        stored = put_object(f"{APP_NAME}/uploads/{user['id']}/test_{stamp}_{k}.pdf", data, "application/pdf")
        files[k] = {"storage_path": stored["path"], "original_filename": f"TEST_{k}.pdf", "content_type": "application/pdf", "size": len(data)}
    D = TD.build(stamp, (st.get("test_email") or "").strip() or None, files)
    mk = lambda d: _new(user, {**d, "is_test": True})
    staff = {}
    for p in D["staff"]:
        doc = mk({k: v for k, v in p.items() if k != "key"}); await db.staff.insert_one(dict(doc)); staff[p["key"]] = doc["id"]
    inst = mk(D["instrument"]); await db.instruments.insert_one(dict(inst))
    cat = {}
    for c in D["catalog"]:
        doc = mk(c); await db.catalog.insert_one(dict(doc)); cat[c["category"]] = doc["id"]
    client_doc = mk(D["client"]); await db.clients.insert_one(dict(client_doc))
    pros = D["prosumator"]
    inv = pros["cef"]["inverters"][0]
    inv["catalog_id"], inv["panel_catalog_id"] = cat["Invertor"], cat["Panou"]
    inv["battery"]["catalog_id"] = cat["Baterie"]
    pros["cef"]["grid"]["meter_catalog_id"] = cat["Smart meter"]
    pros.update({"client_id": client_doc["id"], "instrument_id": inst["id"], "signers": {"designer": staff["designer"], "verifier": staff["verifier"]}})
    pros = derive_cef(pros)
    pdoc = mk(pros); await db.prosumator.insert_one(dict(pdoc))
    diu = mk(D["diu"]); await db.diu.insert_one(dict(diu))
    await db.pram.insert_one(dict(mk({**D["pram"], "diu_ref": diu["number"]})))
    await audit(user, "creare dosar de test", "prosumator", pdoc["id"], [])
    return {"prosumator_id": pdoc["id"], "number": pdoc["number"], "client": client_doc["name"], "test_email": st.get("test_email") or None}

@api_router.delete("/test-dossier")
async def test_dossier_delete(user: dict = Depends(get_current_user)):
    require(user, "admin")
    q = {"owner": user["id"], "is_test": True}
    ids = [x["id"] for x in await db.prosumator.find(q, {"id": 1}).to_list(1000)]
    n = (await db.sign_requests.delete_many({"owner": user["id"], "$or": [{"is_test": True}, {"dossier_id": {"$in": ids}}]})).deleted_count
    for c in TD.TEST_COLLECTIONS:
        n += (await db[c].delete_many(q)).deleted_count
    n += (await db.documents.delete_many({"owner": user["id"], "client_name": {"$regex": "^TEST — "}})).deleted_count
    await audit(user, "ștergere date de test", "prosumator", "", [str(n)])
    return {"deleted": n}

# ---------------- Startup ----------------
@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    for m in MODULES:
        await db[m].create_index("owner")
        # Keep tenant-scoped list and quick-search sorts efficient as collections grow.
        await db[m].create_index([("owner", 1), ("created_at", -1)], name="owner_created_at")
        await db[m].create_index([("owner", 1), ("updated_at", -1)], name="owner_updated_at")
    for field in NUMERIC_CLIENT_SEARCH_FIELDS:
        await db.clients.create_index([("owner", 1), (field, 1)], name=f"owner_{field}")
    await db.prosumator.create_index([("owner", 1), ("client_id", 1), ("updated_at", -1)], name="owner_client_id_updated_at")
    admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    jwt_secret = os.environ.get("JWT_SECRET", "")
    if PRIVATE_MODE:
        # Never boot a private staging service with fallback/default credentials.
        if not admin_email or not admin_password:
            raise RuntimeError("Private mode requires ADMIN_EMAIL and ADMIN_PASSWORD environment secrets")
        if len(admin_password) < 16:
            raise RuntimeError("Private mode requires ADMIN_PASSWORD with at least 16 characters")
        if len(jwt_secret) < 32:
            raise RuntimeError("Private mode requires JWT_SECRET with at least 32 characters")
    else:
        # Local development still needs explicit credentials; do not silently create admin123.
        if not admin_email or not admin_password or not jwt_secret:
            raise RuntimeError("Set ADMIN_EMAIL, ADMIN_PASSWORD and JWT_SECRET in backend/.env before startup")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({"id": str(uuid.uuid4()), "email": admin_email,
            "password_hash": hash_password(admin_password), "name": "Administrator",
            "role": "admin", "created_at": datetime.now(timezone.utc).isoformat()})
        logger.info("Admin seeded")
    elif not existing.get("password_hash"):
        # Seed a missing credential once; do not overwrite an existing password on every deploy.
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})
    PLATFORM["id"] = (await db.users.find_one({"email": admin_email}))["id"]
    await db.users.update_one({"id": PLATFORM["id"]}, {"$set": {"role": "admin", "status": "active", "tenant": None}})
    for pl in DEFAULT_PLANS:
        await db.plans.update_one({"code": pl["code"]}, {"$setOnInsert": pl}, upsert=True)
    await db.billing_config.update_one({"id": "main"}, {"$setOnInsert": {"id": "main", "vat_rate": 21.0, "expired_policy": "read_only", "currency": "RON"}}, upsert=True)
    docgen.IMG_LOADER = lambda p: get_object(p)[0]
    await forms_routes.seed()
    # Fail fast: do not report a healthy API when private file storage is unavailable.
    init_storage()
    logger.info("MongoDB GridFS object storage initialized")

@app.on_event("shutdown")
async def shutdown():
    client.close()

import billing_routes  # noqa: E402
import forms_routes  # noqa: E402
import atr_routes  # noqa: E402
import sld_edit_routes  # noqa: E402
import modules_routes  # noqa: E402
import ai_routes  # noqa: E402
import diu_routes  # noqa: E402
import offers_routes  # noqa: E402
import operator_routes  # noqa: E402
import anre_routes  # noqa: E402
import anre_templates  # noqa: E402
app.include_router(api_router)
# Restrict browser access to explicitly configured frontend origins.
# Preserve deployment-specific origins and always allow the configured staging and DNS Energy web origins.
_cors_raw = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
_cors_origins = [origin.strip().rstrip("/") for origin in _cors_raw.split(",") if origin.strip()]
for _required_origin in (
    "https://dns-energy-web.onrender.com",
    "https://dns-energy.ro",
    "https://www.dns-energy.ro",
):
    if _required_origin not in _cors_origins:
        _cors_origins.append(_required_origin)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)


