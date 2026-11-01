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
import bcrypt
import jwt
import requests
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
    return len((d.get("cef") or {}).get("inverters") or []) or (1 if d.get("inverter") else 0)

def check_inverters(user: dict, d: dict):
    mx = (user.get("plan") or {}).get("max_inverters") or 0
    if not (user.get("plan") or {}).get("exempt") and mx and inv_count(d) > mx:
        raise HTTPException(status_code=402, detail=f"Abonamentul {user['plan']['name']} permite maximum {mx} invertor per dosar (dosarul are {inv_count(d)}). "
                            "Dosarul nu poate fi salvat sau finalizat — treceți la abonamentul PRO sau FULL pentru dosare cu mai multe invertoare.")

# ---------------- Object storage ----------------
# New files use MongoDB GridFS; legacy files are read-through migrated only when the old source remains accessible.
from gridfs_storage import init_storage, put_object, get_object, LegacyObjectUnavailable

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

# ---------------- Models ----------------
class RegisterReq(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None
    billing: Optional[dict] = None

class LoginReq(BaseModel):
    email: EmailStr
    password: str

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

@api_router.get("/data/{module}")
async def list_items(module: str, q: Optional[str] = None, user: dict = Depends(get_current_user)):
    if module not in MODULES:
        raise HTTPException(status_code=404, detail="Modul inexistent")
    guard(module, user)
    query = scope_q(user, module)
    if module == "catalog":
        await seed_catalog(user["id"])
    items = await db[module].find(query).sort("created_at", -1).to_list(2000)
    items = [clean(i) for i in items]
    if q:
        ql = q.lower()
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
    clients = await db.clients.count_documents(scope_q(user, "clients"))
    diu = await db.diu.count_documents(owner)
    mono = await db.mono.count_documents(scope_q(user, "mono"))
    pending = await db.diu.count_documents({**owner, "status": {"$in": ["În lucru", "Documente de completat", "În verificare"]}})
    recent = await db.diu.find(owner).sort("created_at", -1).to_list(5)
    return {"clients": clients, "diu": diu, "mono": mono, "pending": pending,
            "recent": [clean(r) for r in recent]}

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
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "bin"
    path = f"{APP_NAME}/uploads/{user['id']}/{uuid.uuid4()}.{ext}"
    data = await file.read()
    ct = file.content_type or MIME_TYPES.get(ext, "application/octet-stream")
    result = put_object(path, data, ct)
    return {"storage_path": result["path"], "original_filename": file.filename,
            "content_type": ct, "size": result.get("size", len(data))}

@api_router.post("/catalog/{item_id}/import-document")
async def catalog_import_document(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Import a technical PDF from an allowlisted manufacturer or distributor domain."""
    guard("catalog", user, write=True)
    body = await request.json()
    kind = body.get("kind")
    url = str(body.get("url") or "").strip()
    if kind not in ("datasheet", "conformity") or len(url) > 2048:
        raise HTTPException(status_code=400, detail="Tipul documentului sau linkul nu este valid")
    from urllib.parse import urlparse
    import httpx
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    official = (
        "huawei.com", "goodwe.com", "sungrowpower.com", "deyeinverter.com", "solis.com", "solisinverters.com", "ginlong.com", "fronius.com", "sma.de",
        "sma-solar.com", "fox-ess.com", "aikosolar.com", "jinkosolar.com", "longi.com", "trinasolar.com", "ja-solar.com", "canadiansolar.com", "qcells.com",
        "risenenergy.com", "bydbatterybox.com", "dyness.com", "pylontech.com.cn", "pylontech.us", "solaxpower.com",
        "distributie-energie.ro", "delgaz-grid.ro", "delgaz.ro", "reteleelectrice.ro", "distributieoltenia.ro",
    )
    if parsed.scheme != "https" or not host or parsed.username or parsed.password or not any(host == d or host.endswith("." + d) for d in official):
        raise HTTPException(status_code=400, detail="Folosește un link HTTPS de pe domeniul oficial al producătorului/operatorului.")
    item = await db.catalog.find_one({"id": item_id, "owner": user["id"]}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Modelul nu există în catalog")
    def allowed_official_url(candidate: str) -> tuple[str, object]:
        parsed_candidate = urlparse(candidate)
        candidate_host = (parsed_candidate.hostname or "").lower().rstrip(".")
        try:
            candidate_port = parsed_candidate.port
        except ValueError:
            candidate_port = -1
        if (parsed_candidate.scheme != "https" or parsed_candidate.username or parsed_candidate.password
                or candidate_port not in (None, 443)
                or not any(candidate_host == domain or candidate_host.endswith("." + domain) for domain in official)):
            raise HTTPException(status_code=400, detail="Redirecționarea a părăsit domeniul oficial permis.")
        return candidate_host, parsed_candidate

    try:
        from urllib.parse import urljoin
        chunks, total = [], 0
        current_url = url
        async with httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
            for hop in range(6):
                async with client.stream("GET", current_url, headers={"User-Agent": "DNS-Energy-Document-Importer/1.0", "Accept": "application/pdf"}) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("location")
                        if not location:
                            raise HTTPException(status_code=400, detail="Sursa a trimis o redirecționare fără destinație.")
                        next_url = urljoin(current_url, location)
                        allowed_official_url(next_url)
                        current_url = next_url
                        continue
                    if response.status_code != 200:
                        raise HTTPException(status_code=400, detail=f"Sursa a răspuns cu HTTP {response.status_code}; verifică linkul PDF.")
                    final_host, _ = allowed_official_url(str(response.url))
                    length = response.headers.get("content-length")
                    if length and length.isdigit() and int(length) > 25 * 1024 * 1024:
                        raise HTTPException(status_code=413, detail="Documentul depășește limita de 25 MB")
                    async for chunk in response.aiter_bytes(64 * 1024):
                        total += len(chunk)
                        if total > 25 * 1024 * 1024:
                            raise HTTPException(status_code=413, detail="Documentul depășește limita de 25 MB")
                        chunks.append(chunk)
                    break
            else:
                raise HTTPException(status_code=400, detail="Sursa a depășit limita de 5 redirecționări.")
        data = b"".join(chunks)
    except httpx.HTTPError:
        raise HTTPException(status_code=400, detail="Documentul nu a putut fi preluat de la sursa oficială.")
    if not data.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="Linkul nu a returnat un PDF valid")
    stored = put_object(f"{APP_NAME}/catalog/{user['id']}/{item_id}/{kind}_{uuid.uuid4().hex}.pdf", data, "application/pdf")
    doc = {"storage_path": stored["path"], "original_filename": f"{item.get('brand_model', 'model')} — {kind}.pdf",
           "content_type": "application/pdf", "size": len(data), "source_url": url, "source_host": final_host,
           "resolved_url": current_url, "imported_at": datetime.now(timezone.utc).isoformat()}
    await db.catalog.update_one({"id": item_id, "owner": user["id"]}, {"$set": {kind: doc, f"{kind}_source_url": url}})
    await audit(user, "import document catalog", "catalog", item_id, [kind, "source_url"])
    return {"ok": True, "kind": kind, "source_url": url, "size": len(data)}


@api_router.get("/files/{path:path}")
async def download(path: str, authorization: str = Header(None), auth: str = Query(None),
                   module: str = Query("documents")):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    elif auth:
        token = auth
    if not token:
        raise HTTPException(status_code=401, detail="Neautentificat")
    user = await user_from_token(None, token)
    if f"/{user['id']}/" not in path:
        raise HTTPException(status_code=404, detail="Fișier inexistent")
    if not is_admin(user):
        import json as _j
        ok = False
        for m in ("prosumator", "clients", "documents", "diu", "atr", "power"):
            async for d in db[m].find(scope_q(user, m), {"_id": 0}):
                if path in _j.dumps(d, default=str):
                    ok = True; break
            if ok:
                break
        if not ok and not await db.staff.find_one({"owner": user["id"], "id": user.get("staff_id")}) :
            raise HTTPException(status_code=404, detail="Fișier inexistent sau fără drept de acces")
    try:
        data, content_type = get_object(path)
    except LegacyObjectUnavailable as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    return Response(content=data, media_type=content_type)

# ---------------- AI extraction & document generation ----------------
import docgen
from ai_extract import extract_pdf, extract_gpt, extract_office_text, extract_gpt_text, extract_office_local

async def user_from_token(authorization: Optional[str], auth: Optional[str]) -> dict:
    token = authorization[7:] if authorization and authorization.startswith("Bearer ") else auth
    if not token:
        raise HTTPException(status_code=401, detail="Neautentificat")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalid")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Utilizator inexistent")
    if os.environ.get("DNS_ENERGY_PRIVATE_MODE", "false").strip().lower() in ("1", "true", "yes", "on"):
        admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
        if not admin_email or user.get("email", "").lower() != admin_email or user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Acces permis exclusiv administratorului DNS Energy")
    if user.get("status", "active") != "active":
        raise HTTPException(status_code=403, detail=STATUS_MSG.get(user.get("status"), "Cont inactiv"))
    return await finish_user(user)

@api_router.post("/ai/extract")
async def ai_extract(file: UploadFile = File(...), doc_type: str = Form("auto"), user: dict = Depends(get_current_user)):
    guard("prosumator", user, write=True)
    # Document intake is part of the prosumer workflow. The route already checks the\n    # prosumer module entitlement above; do not require a second AI-only feature for\n    # selectable-text PDFs and local Office extraction. GPT/OCR remains feature-gated below.\n    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Fișierul este gol")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Fișierul depășește limita de 25 MB")
    filename = str(file.filename or "document.pdf")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "pdf"
    ct = str(file.content_type or "").split(";", 1)[0].strip().lower()
    # Mobile pickers sometimes send application/octet-stream (or no MIME type).
    # Infer the supported type from the extension in those cases.
    if not ct or ct == "application/octet-stream":
        ct = MIME_TYPES.get(ext, "application/octet-stream")
    office_types = {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    image_types = ("image/jpeg", "image/png", "image/webp", "image/heic", "image/heif", "image/heic-sequence", "image/heif-sequence")
    if ct != "application/pdf" and ct not in image_types and ct not in office_types:
        raise HTTPException(status_code=400, detail="Citire automată pentru PDF, imagini, DOCX și XLSX. Alte formate pot fi atașate și verificate manual.")
    if doc_type not in {"auto", "ci", "factura", "cf", "other"}:
        raise HTTPException(status_code=400, detail="Tip de document invalid")
    use_gpt = has_feature(user, "ai_gpt") and "ai_gpt" not in user["plan"].get("disabled", [])
    try:
        if ct in office_types:
            if use_gpt:
                fields = await extract_gpt_text(extract_office_text(data, ct), doc_type)
            else:
                fields = extract_office_local(data, ct, doc_type)
        else:
            fields = await extract_pdf(data, ct, doc_type, use_ai=use_gpt)
    except Exception as e:
        logger.error(f"AI extract failed: {e}")
        if ct in image_types and not os.environ.get("OPENAI_API_KEY"):
            raise HTTPException(status_code=503, detail="Pentru citirea fotografiilor și a documentelor scanate este necesară configurarea serviciului AI în API.")
        if ct == "application/pdf" and not os.environ.get("OPENAI_API_KEY") and not isinstance(e, ValueError):
            raise HTTPException(status_code=503, detail="PDF-ul pare scanat sau nu are etichete text recunoscute. Pentru citirea AI a scanurilor trebuie configurată cheia OPENAI_API_KEY în serviciul API.")
        raise HTTPException(status_code=502, detail=str(e) if isinstance(e, ValueError) else "Nu am putut citi documentul. Încearcă din nou.")
    expected = {
        "ci": ("client_name", "cnp", "hq_address", "id_series", "id_number"),
        "factura": ("client_name", "cnp", "consumption_address", "address", "pod", "operator", "supplier", "bransament_kw", "power"),
        "cf": ("owner_name", "client_name", "cf_nr", "cadastral_nr"),
    }
    selected_type = doc_type if doc_type in expected else str(fields.get("doc_type") or "").casefold()
    warning = None
    if selected_type in expected and not any(fields.get(key) not in (None, "", "null") for key in expected[selected_type]):
        warning = "Fișierul a fost atașat, dar nu s-au putut extrage câmpurile așteptate. Verifică imaginea și completează datele manual."
    stored = put_object(f"{APP_NAME}/uploads/{user['id']}/{uuid.uuid4()}.{ext}", data, ct)
    engine = fields.pop("_engine", "OpenAI (GPT-4.1 mini)")
    return {"data": fields, "engine": engine, "warning": warning,
            "file": {"storage_path": stored["path"], "original_filename": file.filename,
                     "content_type": ct, "size": len(data)}}

def _new(user, extra):
    now = datetime.now(timezone.utc).isoformat()
    return {"id": str(uuid.uuid4()), "owner": user["id"], "created_at": now, "updated_at": now,
            **({"created_by": user["uid"], "created_by_email": user.get("email")} if user.get("uid") else {}), **extra}

@api_router.post("/import/prosumator")
async def import_prosumator(request: Request, user: dict = Depends(get_current_user)):
    guard("prosumator", user, write=True)
    d = await request.json()
    for k in ("_id", "id", "owner", "created_at", "updated_at"):
        d.pop(k, None)
    name = (d.get("client_name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Lipsește numele beneficiarului")
    check_inverters(user, d)
    files = d.get("files") or []
    if not isinstance(files, list):
        raise HTTPException(status_code=400, detail="Lista de documente este invalidă")
    for f in files:
        if not isinstance(f, dict) or not str(f.get("storage_path") or "").startswith(APP_NAME + "/uploads/" + str(user["id"]) + "/"):
            raise HTTPException(status_code=400, detail="Document invalid sau neîncărcat în contul curent")
    identity_code = str(d.get("cnp") or "").strip()
    client = None
    if identity_code:
        client = await db.clients.find_one({**scope_q(user, "clients"),
            "$or": [{"idcode": identity_code}, {"cui": identity_code}]}, {"_id": 0})
    if not client:
        client = await db.clients.find_one({**scope_q(user, "clients"), "name": name}, {"_id": 0})
    stored_identity = str((client or {}).get("idcode") or (client or {}).get("cui") or "").strip()
    # A same-name client with a different CNP/CUI is a separate person/company.
    if client and identity_code and stored_identity and identity_code.casefold() != stored_identity.casefold():
        client = None

    if d.get("pod"):
        duplicate_match = []
        if client:
            duplicate_match.append({"client_id": client["id"]})
        if identity_code:
            duplicate_match.extend([{"cnp": identity_code}, {"idcode": identity_code}])
        else:
            duplicate_match.append({"client_name": name})
        duplicate = await db.prosumator.find_one({**scope_q(user, "prosumator"), "pod": d["pod"], "$or": duplicate_match}, {"id": 1})
        if duplicate:
            raise HTTPException(status_code=409, detail="Există deja un dosar pentru acest client și acest POD")
    if not client:
        client = _new(user, {"name": name, "idcode": d.get("cnp", ""), "phone": d.get("phone", ""), "email": d.get("email", ""),
                             "address": d.get("address", ""), "hq_address": d.get("hq_address", ""), "county": d.get("county", ""),
                             "pod": d.get("pod", ""), "operator": d.get("operator", ""), "cadastral_nr": d.get("cadastral_nr", ""),
                             "cf_nr": d.get("cf_nr", ""), "supplier": d.get("supplier", ""), "rep_name": d.get("rep_name", ""),
                             "regcom": d.get("regcom", ""), "kind": d.get("kind", "")})
        client["docs"] = client.get("docs") or {}
        await db.clients.insert_one(dict(client))
    client.setdefault("docs", {})
    client_values = {"name": name, "idcode": d.get("cnp"), "id_series": d.get("id_series"), "id_number": d.get("id_number"),
                     "phone": d.get("phone"), "email": d.get("email"),
                     "address": d.get("address"), "hq_address": d.get("hq_address"), "county": d.get("county"),
                     "pod": d.get("pod"), "operator": d.get("operator"), "cadastral_nr": d.get("cadastral_nr"),
                     "cf_nr": d.get("cf_nr"), "supplier": d.get("supplier"), "rep_name": d.get("rep_name"),
                     "regcom": d.get("regcom"), "kind": d.get("kind")}
    client_updates = {}
    for key, value in client_values.items():
        if value not in (None, "") and client.get(key) in (None, ""):
            client[key] = value
            client_updates[key] = value
    d["client_id"] = client["id"]
    if not d.get("number"):
        year = datetime.now().year
        nums = [int(x["number"].split("-")[-1]) for x in await db.prosumator.find(
            {"owner": user["id"], "number": {"$regex": f"^PROS-{year}-\\d+$"}}, {"number": 1}).to_list(5000)]
        d["number"] = f"PROS-{year}-{(max(nums) if nums else 0) + 1:03d}"
    if not d.get("status"):
        d["status"] = "În pregătire"
    files = d.get("files") or []
    d = derive_cef(d)
    pros = _new(user, d)
    await db.prosumator.insert_one(dict(pros))
    await sync_catalog_files_to_documents(user, pros)
    sz = docgen.sizing(d)
    await db.works.insert_one(_new(user, {"title": f"Sistem fotovoltaic {docgen.fmt(sz['kwp'] or docgen.num(d.get('power')))} kWp — {name}",
        "client_name": name, "type": "Sistem fotovoltaic", "status": "Finalizat" if d.get("status") == "Prosumator activ" else "În execuție",
        "start_date": d.get("date", ""), "responsible": d.get("executant_rep", ""), "notes": f"Generat din dosar {pros['number']}", "pros_ref": pros["id"]}))
    changed_slots = False
    for f in files:
        kind = f.get("kind")
        slot = {"ci": "ci", "factura": "factura", "cf": "cf"}.get(kind)
        clean_file = {k: f.get(k) for k in ("storage_path", "original_filename", "content_type", "size")}
        if slot:
            existing = client["docs"].setdefault(slot, [])
            if not any(x.get("storage_path") == clean_file["storage_path"] for x in existing if isinstance(x, dict)):
                existing.append(clean_file)
                changed_slots = True
        await db.documents.insert_one(_new(user, {"client_id": client["id"], "client_name": name,
            "kind": "Dosar prosumator", "doc_type": f.get("doc_type") or "Document importat",
            **clean_file, "pros_ref": pros["id"]}))
    await db.clients.update_one({"id": client["id"], "owner": user["id"]}, {"$set": {
        **client_updates,
        "docs": client["docs"], "updated_at": datetime.now(timezone.utc).isoformat()}})
    return clean(pros)

@api_router.get("/docs/types")
async def doc_types(user: dict = Depends(get_current_user)):
    return [{"key": k, "label": v[0]} for k, v in docgen.DOCS.items()]

@api_router.get("/docs/sizing/{item_id}")
async def doc_sizing(item_id: str, user: dict = Depends(get_current_user)):
    rec = await check_access(user, "prosumator", item_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
    return docgen.sizing(rec)

@api_router.get("/docs/{doc_type}/{item_id}")
async def generate_doc(doc_type: str, item_id: str, authorization: str = Header(None), auth: str = Query(None),
                       attach: int = Query(0)):
    user = await user_from_token(authorization, auth)
    rec = await check_access(user, "prosumator", item_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Dosar inexistent")

    is_power_increase = str(rec.get("request_type") or "").strip() == "Spor de putere + prosumator"
    client = await get_client(user["id"], rec)
    annex1 = None
    if is_power_increase:
        # Use the actual Annex 1 PDF registered for the client's distribution operator.
        operator = str(rec.get("operator") or client.get("operator") or "").lower()
        if "delgaz" in operator:
            op_names = ["delgaz grid", "delgaz"]
        elif "rețele electrice" in operator or "retele electrice" in operator or "e-distribu" in operator:
            op_names = ["rețele electrice românia", "rețele electrice"]
        elif "oltenia" in operator:
            op_names = ["distribuție energie oltenia", "distributie energie oltenia"]
        elif "deer" in operator or "distribuție energie electrică" in operator or "distributie energie electrica" in operator:
            op_names = ["deer", "distribuție energie electrică romania", "distributie energie electrica romania"]
        else:
            op_names = []
        if op_names:
            rows = await db.official_forms.find({}, {"_id": 0}).to_list(500)
            candidates = [f for f in rows
                if any(n in str(f.get("operator") or "").lower() for n in op_names)
                and "prosumator" in str(f.get("kind") or "").lower()
                and ("spor" in str(f.get("kind") or "").lower() or "anexa 1" in str(f.get("title") or "").lower())
                and "anexa 1" in str(f.get("title") or "").lower()
                and str(f.get("url") or "").lower().split("?")[0].endswith(".pdf")]
            for item in candidates:
                try:
                    resp = requests.get(item["url"], timeout=20, headers={"User-Agent": "DNS-Energy/1.0"})
                    if resp.status_code == 200 and resp.content.startswith(b"%PDF"):
                        annex1 = {"bytes": resp.content, "title": item.get("title") or "Anexa 1 oficială"}
                        break
                except Exception as exc:
                    logger.warning("Nu s-a putut descărca Anexa 1 oficială: %s", exc)
        if doc_type == "notificare":
            if not annex1:
                raise HTTPException(status_code=404, detail="Nu există un PDF Anexa 1 disponibil în Registrul formularelor pentru distribuitorul selectat. Verificați/înregistrați formularul oficial; Anexa 2 nu va fi folosită la spor de putere.")
            return Response(content=annex1["bytes"], media_type="application/pdf",
                            headers={"Content-Disposition": disp("inline", f"Anexa_1_spor_putere_{(rec.get('client_name') or 'prosumator').replace(' ', '_')}.pdf")})

    if doc_type == "all":
        # Dosarul complet include schema CEF o singură dată.
        keys = [k for k in docgen.DOCS if k != "schema"]
        if is_power_increase:
            keys = [k for k in keys if k != "notificare"]
    else:
        keys = [doc_type]
    if any(k not in docgen.DOCS for k in keys):
        raise HTTPException(status_code=404, detail="Tip document inexistent")

    base = await db.settings.find_one({"owner": user["id"]}, {"_id": 0}) or {}
    settings, _ = await effective_settings(user["id"], rec, base)
    pdf = docgen.render(keys, rec, settings, client)

    if doc_type == "all" and is_power_increase and annex1:
        try:
            # Anexa 1 ocupa primul loc al notificării în dosar; Anexa 2 nu este generată pentru spor.
            writer = PdfWriter()
            for page in PdfReader(io.BytesIO(annex1["bytes"])).pages:
                writer.add_page(page)
            for page in PdfReader(io.BytesIO(pdf)).pages:
                writer.add_page(page)
            merged = io.BytesIO()
            writer.write(merged)
            pdf = merged.getvalue()
        except Exception as exc:
            logger.warning("Nu s-a putut atașa Anexa 1 oficială: %s", exc)

    # Attach catalog technical sheets and declarations.
    if attach or doc_type == "all":
        pdf = merge_pdfs(pdf, await catalog_files(user["id"], rec))
    fname = f"{doc_type}_{(rec.get('client_name') or 'dosar').replace(' ', '_')}.pdf"
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": disp('inline', f"{fname}")})

# ---------------- CEF checks & catalog ----------------
import cef as CEF
from catalog_seed import SEED as CATALOG_SEED, NOTE as CATALOG_NOTE
from pypdf import PdfReader, PdfWriter
import io

async def seed_catalog(owner: str):
    # Seed idempotent: adaugă numai modelele lipsă și pentru conturile deja existente.
    await db.settings.update_one({"owner": owner}, {"$setOnInsert": {"owner": owner}}, upsert=True)
    await db.settings.update_one({"owner": owner}, {"$set": {"catalog_seeded": True}})
    existing = await db.catalog.find({"owner": owner}, {"id": 1, "category": 1, "brand_model": 1,
        "datasheet_url": 1, "conformity_url": 1, "_id": 0}).to_list(10000)
    by_key = {(x.get("category"), (x.get("brand_model") or "").strip().casefold()): x for x in existing}
    missing = []
    for item in CATALOG_SEED:
        key = (item.get("category"), (item.get("brand_model") or "").strip().casefold())
        row = by_key.get(key)
        if row:
            # Backfill manufacturer source links without overwriting a link the user already set.
            source_updates = {f"{kind}_url": item[f"{kind}_url"] for kind in ("datasheet", "conformity")
                              if item.get(f"{kind}_url") and not row.get(f"{kind}_url")}
            if source_updates:
                await db.catalog.update_one({"id": row["id"], "owner": owner}, {"$set": source_updates})
            continue
        created = _new({"id": owner}, {**item, "notes": item.get("notes") or CATALOG_NOTE})
        missing.append(created)
        by_key[key] = created
    if missing:
        await db.catalog.insert_many(missing)

def derive_cef(d: dict) -> dict:
    if (d.get("cef") or {}).get("inverters"):
        f = CEF.flatten({k: v for k, v in d.items() if k != "power"})
        for k in ("power", "inverter", "inverter_kw", "panel_count", "panels"):
            if not d.get(k):
                d[k] = f.get(k)
    return d

@api_router.post("/cef/check")
async def cef_check(request: Request, user: dict = Depends(get_current_user)):
    return CEF.check(await request.json())

# ---------------- Schemă monofilară (generator nou) ----------------
import sizing as SZ
import sld as SLD
from sld_demo import DEMO_REC, DEMO_CLIENT

SLD_ROLES = {"designer": "Proiectant schemă", "verifier": "Verificator schemă"}

from urllib.parse import quote as _q
import unicodedata as _ud

def disp(kind: str, name: str) -> str:
    a = _ud.normalize("NFKD", name).encode("ascii", "ignore").decode().replace('"', "") or "document"
    return f"{kind}; filename=\"{a}\"; filename*=UTF-8''{_q(name)}"

def pdf_resp(data: bytes, name: str):
    return Response(content=data, media_type="application/pdf", headers={"Content-Disposition": disp('inline', f"{name}")})

async def sld_ctx(owner, item_id: str):
    if isinstance(owner, dict):
        await check_access(owner, "prosumator", item_id); owner = owner["id"]
    rec = await db.prosumator.find_one({"id": item_id, "owner": owner}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
    rec = CEF.from_legacy(rec)
    client = await get_client(owner, rec)
    base = await db.settings.find_one({"owner": owner}, {"_id": 0}) or {}
    s, warns = await effective_settings(owner, rec, base)
    if (rec.get("cef") or {}).get("from_legacy"):
        warns = list(warns) + ["Schema folosește datele din fișa dosarului (invertor, panouri, baterie). Repartizarea pe stringuri/MPPT nu este definită — "
                               "configurați stringurile în Configuratorul CEF pentru o schemă completă."]
    res = SZ.compute(rec, client)
    state = SZ.state(rec, client, s)
    return rec, client, s, res, state, warns

@api_router.get("/sld/demo/pdf")
async def sld_demo(authorization: str = Header(None), auth: str = Query(None), fmt: str = Query("A3")):
    user = await user_from_token(authorization, auth)
    s = await db.settings.find_one({"owner": user["id"]}, {"_id": 0}) or {}
    res = SZ.compute(DEMO_REC, DEMO_CLIENT)
    return pdf_resp(SLD.render(DEMO_REC, DEMO_CLIENT, s, res, {"status": "draft"}, fmt, demo=True), "schema_monofilara_DEMO.pdf")

@api_router.get("/sld/{item_id}")
async def sld_status(item_id: str, user: dict = Depends(get_current_user)):
    rec, client, s, res, state, warns = await sld_ctx(user, item_id)
    sld = rec.get("sld") or {}
    signers = rec.get("signers") or {}
    people = {}
    for role in SLD_ROLES:
        sid = signers.get(role)
        p = await db.staff.find_one({"owner": user["id"], "id": sid}, {"_id": 0}) if sid else None
        people[role] = {"name": p.get("name"), "eligible": staff_eligible(p), "email": p.get("email")} if p else None
    return {"items": res["items"], "missing": res["missing"], "errors": res["errors"], "warnings": res["warnings"], "cables": res["cables"],
            "ready": res["ready"], "format": res["format"], "totals": res["base"]["totals"], "approval": state, "settings_warnings": warns,
            "source": sld.get("source") or "generated", "upload": sld.get("upload"), "revision": sld.get("revision") or 0,
            "auto_filled": (rec.get("cef") or {}).get("auto_filled") or [], "people": people,
            "history": [{k: v for k, v in h.items() if k not in ("hash", "values")} | {"current": h.get("hash") == state["fingerprint"], "index": i, "has_values": bool(h.get("values"))}
                        for i, h in reversed(list(enumerate(sld.get("history") or [])))],
            "approval_requests": (sld.get("approval_requests") or [])[-5:], "is_test": bool(rec.get("is_test")),
            "from_legacy": bool((rec.get("cef") or {}).get("from_legacy"))}

@api_router.post("/sld/{item_id}/import-legacy")
async def sld_import_legacy(item_id: str, user: dict = Depends(get_current_user)):
    guard("prosumator", user, write=True)
    rec = await check_access(user, "prosumator", item_id)
    new = CEF.from_legacy(rec)
    if not (new.get("cef") or {}).get("from_legacy"):
        raise HTTPException(status_code=400, detail="Dosarul are deja o configurație CEF sau nu are date de invertor/panouri")
    cef = {k: v for k, v in new["cef"].items() if k != "from_legacy"}
    await db.prosumator.update_one({"id": item_id}, {"$set": {"cef": cef}})
    await audit(user, "update", "prosumator", item_id, ["cef (preluat din fișa dosarului pentru schema monofilară)"])
    return {"ok": True}

@api_router.get("/sld/{item_id}/pdf")
async def sld_pdf(item_id: str, authorization: str = Header(None), auth: str = Query(None), fmt: str = Query("auto"), download: int = Query(0)):
    user = await user_from_token(authorization, auth)
    rec, client, s, res, state, _ = await sld_ctx(user, item_id)
    name = f"schema_monofilara_{rec.get('number') or item_id}.pdf"
    return Response(content=SLD.render(rec, client, s, res, state, fmt), media_type="application/pdf",
                    headers={"Content-Disposition": disp("attachment" if download else "inline", name)})

@api_router.get("/sld/{item_id}/report")
async def sld_report(item_id: str, authorization: str = Header(None), auth: str = Query(None)):
    user = await user_from_token(authorization, auth)
    rec, client, s, res, state, _ = await sld_ctx(user, item_id)
    return pdf_resp(SLD.report(rec, client, s, res, state), f"raport_calcul_{rec.get('number') or item_id}.pdf")

@api_router.post("/sld/{item_id}/apply")
async def sld_apply(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    guard("prosumator", user, write=True)
    rec = await check_access(user, "prosumator", item_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
    body = await request.json() if (await request.body()) else {}
    cef, filled = SZ.apply(body.get("cef") or rec.get("cef") or {})
    await db.prosumator.update_one({"id": item_id}, {"$set": {"cef": cef}})
    await audit(user, "dimensionare automată", "prosumator", item_id, filled)
    return {"filled": filled, "cef": cef}

@api_router.put("/sld/{item_id}/source")
async def sld_source(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    guard("prosumator", user, write=True)
    body = await request.json()
    rec = await check_access(user, "prosumator", item_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
    sld = rec.get("sld") or {}
    if body.get("source") in ("generated", "uploaded"):
        sld["source"] = body["source"]
    if body.get("upload"):
        sld["upload"] = body["upload"]
    if body.get("clear_upload"):
        sld.pop("upload", None)
        if sld.get("source") == "uploaded":
            sld["source"] = "generated"
    if sld.get("source") == "uploaded" and not sld.get("upload"):
        raise HTTPException(status_code=400, detail="Încărcați întâi schema realizată de specialist.")
    await db.prosumator.update_one({"id": item_id}, {"$set": {"sld": sld}})
    await audit(user, "schemă — sursă", "prosumator", item_id, [sld.get("source") or "generated"])
    return sld

@api_router.post("/sld/{item_id}/approve")
async def sld_approve(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    require(user, "admin", "inginer")
    need(user, "prosumator", True)
    role = (await request.json()).get("role")
    if role not in SLD_ROLES:
        raise HTTPException(status_code=400, detail="Rol invalid")
    rec, client, s, res, state, _ = await sld_ctx(user, item_id)
    sld = rec.get("sld") or {}
    src = sld.get("source") or "generated"
    if src == "generated" and not res["ready"]:
        raise HTTPException(status_code=400, detail=f"Schema nu poate fi aprobată: {len(res['missing'])} date lipsă, {len(res['errors'])} erori.")
    if src == "uploaded" and not sld.get("upload"):
        raise HTTPException(status_code=400, detail="Nu există schemă încărcată.")
    sid = (rec.get("signers") or {}).get(role)
    p = await db.staff.find_one({"owner": user["id"], "id": sid}, {"_id": 0}) if sid else None
    if not p:
        raise HTTPException(status_code=400, detail=f"Selectați {SLD_ROLES[role].lower()} în secțiunea Semnatari a dosarului (din Setări de bază → Personal).")
    if not staff_eligible(p):
        raise HTTPException(status_code=400, detail=f"{p.get('name')} nu are o autorizație valabilă și verificată în Setări de bază.")
    auth_doc = next((a for a in p.get("auths") or [] if a.get("verified")), {})
    rev = (sld.get("revision") or 0) + (1 if state["status"] == "stale" else 0)
    aps = {r: a for r, a in (sld.get("approvals") or {}).items() if state["status"] != "stale" and r != role}
    sld.update({"revision": rev, "approval": {"role": role, "role_label": SLD_ROLES[role], "staff_id": sid, "name": p.get("name"),
                                             "auth": f"{auth_doc.get('type', '')} nr. {auth_doc.get('number', '')}".strip(), "source": src,
                                             "at": datetime.now(timezone.utc).isoformat(), "by": user.get("email")}})
    rec["sld"] = sld
    sld["approval"]["hash"] = SZ.fingerprint(rec, client)
    aps[role] = sld["approval"]
    sld["approvals"] = aps
    await db.prosumator.update_one({"id": item_id}, {"$set": {"sld": sld}})
    rec2, client2, s2, res2, st2, _ = await sld_ctx(user, item_id)
    if src == "uploaded":
        f = sld["upload"]
    else:
        pdf = SLD.render(rec2, client2, s2, res2, st2)
        stored = put_object(f"{APP_NAME}/sld/{user['id']}/{item_id}/rev{rev}_{uuid.uuid4().hex[:8]}.pdf", pdf, "application/pdf")
        f = {"storage_path": stored["path"], "original_filename": f"schema_rev{rev}.pdf", "content_type": "application/pdf", "size": len(pdf)}
    entry = {"revision": rev, "at": sld["approval"]["at"], "role": role, "role_label": SLD_ROLES[role], "name": p.get("name"),
             "auth": sld["approval"]["auth"], "hash": sld["approval"]["hash"], "source": src, "file": f, "by": user.get("email"),
             "values": SLD.snapshot(rec2, res2)}
    await db.prosumator.update_one({"id": item_id}, {"$push": {"sld.history": entry}})
    await audit(user, "schemă aprobată", "prosumator", item_id, [role, p.get("name")])
    return sld["approval"]

async def deliver(owner: str, is_test: bool, to: str, subject: str, html: str) -> str:
    """Returns the address actually used, or '' when not sent (test dossier without test e-mail)."""
    if is_test:
        st = await db.settings.find_one({"owner": owner}, {"_id": 0, "test_email": 1}) or {}
        to = (st.get("test_email") or "").strip()
        if "@" not in to:
            return ""
        subject = "[TEST] " + subject
        html = '<p style="color:#b03a2e;font-family:Arial"><b>DOSAR DE TEST — date fictive. Nu este un document sau o semnătură oficială.</b></p>' + html
    await send_email(to=to, subject=subject, html=html)
    return to

@api_router.get("/sld/{item_id}/compare")
async def sld_compare(item_id: str, a: int, b: int, user: dict = Depends(get_current_user)):
    rec = await check_access(user, "prosumator", item_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
    h = (rec.get("sld") or {}).get("history") or []
    if not (0 <= a < len(h) and 0 <= b < len(h)):
        raise HTTPException(status_code=404, detail="Revizie inexistentă")
    va, vb = h[a].get("values"), h[b].get("values")
    if not va or not vb:
        raise HTTPException(status_code=400, detail="Una dintre versiuni a fost aprobată înainte de salvarea valorilor pentru comparare")
    rows = [{"key": k, "a": va.get(k, "—"), "b": vb.get(k, "—"), "changed": va.get(k) != vb.get(k)} for k in dict.fromkeys(list(va) + list(vb))]
    meta = lambda x: {k: x.get(k) for k in ("revision", "at", "name", "role_label", "source")}
    return {"a": meta(h[a]), "b": meta(h[b]), "rows": rows, "changed": sum(r["changed"] for r in rows)}

async def request_approval(user: dict, item_id: str, origin: str, auto: bool):
    rec, client, s, res, state, _ = await sld_ctx(user, item_id)
    sld = rec.get("sld") or {}
    if state["status"] == "approved":
        raise HTTPException(status_code=400, detail="Schema este deja aprobată pentru configurația actuală")
    if (sld.get("source") or "generated") == "generated" and not res["ready"]:
        raise HTTPException(status_code=400, detail=f"Datele nu sunt complete: {len(res['missing'])} lipsă, {len(res['errors'])} erori")
    if auto and sld.get("approval_request_hash") == state["fingerprint"]:
        return None
    if not origin.startswith("https://"):
        raise HTTPException(status_code=400, detail="Adresa aplicației (origin) lipsește — deschideți cererea din aplicație")
    sent = []
    for role, label in SLD_ROLES.items():
        sid = (rec.get("signers") or {}).get(role)
        p = await db.staff.find_one({"owner": user["id"], "id": sid}, {"_id": 0}) if sid else None
        if not p or "@" not in (p.get("email") or ""):
            continue
        link = f"{origin.rstrip('/')}/prosumator"
        html = (f'<div style="font-family:Arial,sans-serif;color:#0b1f3a"><p>Bună ziua, {hesc(p["name"])},</p>'
                f'<p>Schema monofilară și dimensionarea tehnică pentru <b>{hesc(str(client.get("name") or rec.get("client_name") or ""))}</b> '
                f'(dosar {hesc(str(rec.get("number") or ""))}) sunt complete și așteaptă verificarea dvs. ca {hesc(label.lower())}.</p>'
                f'<p><a href="{hesc(link)}">Deschide aplicația D-ENERGY</a> → Dosar de prosumator → secțiunea „Schemă monofilară”.</p></div>')
        to = await deliver(user["id"], bool(rec.get("is_test")), p["email"], f"Cerere de aprobare schemă — {rec.get('number') or ''}", html)
        sent.append({"role": role, "name": p["name"], "to": to, "sent": bool(to)})
    entry = {"at": datetime.now(timezone.utc).isoformat(), "auto": auto, "recipients": sent, "by": user.get("email")}
    await db.prosumator.update_one({"id": item_id}, {"$set": {"sld.approval_request_hash": state["fingerprint"]}, "$push": {"sld.approval_requests": entry}})
    await audit(user, "cerere aprobare schemă", "prosumator", item_id, [x["name"] for x in sent])
    return entry

@api_router.post("/sld/{item_id}/request-approval")
async def sld_request_approval(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    guard("prosumator", user, write=True)
    b = await request.json() if (await request.body()) else {}
    entry = await request_approval(user, item_id, b.get("origin") or request.headers.get("origin") or "", False)
    if not entry["recipients"]:
        raise HTTPException(status_code=400, detail="Nu există proiectant/verificator selectat cu e-mail completat")
    return entry

@api_router.post("/sld/{item_id}/send-sign")
async def sld_send_sign(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    guard("prosumator", user, write=True); need(user, "sign_remote", True)
    b = await request.json()
    role = b.get("role")
    if role not in SLD_ROLES:
        raise HTTPException(status_code=400, detail="Rol invalid")
    rec, client, s, res, state, _ = await sld_ctx(user, item_id)
    if state["status"] != "approved":
        raise HTTPException(status_code=400, detail="Schema trebuie aprobată înainte de semnare")
    sid = (rec.get("signers") or {}).get(role)
    p = await db.staff.find_one({"owner": user["id"], "id": sid}, {"_id": 0}) if sid else None
    if not p or not staff_eligible(p):
        raise HTTPException(status_code=400, detail=f"{SLD_ROLES[role]}: persoană neselectată sau fără autorizație valabilă și verificată")
    if "@" not in (p.get("email") or ""):
        raise HTTPException(status_code=400, detail=f"Completați e-mailul pentru {p.get('name')} în Setări de bază → Personal")
    keys = [k for k in (b.get("pos_keys") or ["schema"]) if k in ("schema", "fisa_tehnica")] or ["schema"]
    reqs = await create_sign_requests(user, item_id, keys, [{"name": p["name"], "email": p["email"], "phone": p.get("phone") or "", "role": SLD_ROLES[role]}], parse_days(b.get("expires_days")))
    origin = (b.get("origin") or "").rstrip("/")
    for r in reqs:
        link = f"{origin}/semneaza/{r['token']}"
        html = (f'<table role="presentation" width="100%"><tr><td style="padding:24px;font-family:Arial,sans-serif;color:#0b1f3a">'
                f'<p>Bună ziua, {hesc(p["name"])},</p><p>Vă rugăm să verificați și să semnați documentul <b>{hesc(r["doc_title"])}</b> '
                f'pentru beneficiarul {hesc(str(r.get("client_name") or ""))}, în calitate de {hesc(SLD_ROLES[role].lower())}.</p>'
                f'<p><a href="{hesc(link)}" style="background:#2878f0;color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none">Deschide documentul</a></p>'
                f'<p>La semnare veți primi un cod unic pe această adresă de e-mail. Linkul este personal și expiră la {r["expires_at"][:10]}.</p></td></tr></table>')
        to = await deliver(user["id"], bool(rec.get("is_test")), p["email"], f"Semnare {r['doc_title'][:60]}", html)
        if to:
            await db.sign_requests.update_one({"id": r["id"]}, {"$set": {"status": "Link trimis"}, "$push": {"history": hist("Link trimis", None, f"e-mail automat către {mask(to)}; de {user.get('email')}")}})
        else:
            await db.sign_requests.update_one({"id": r["id"]}, {"$push": {"history": hist("E-mail netrimis", None, "dosar de TEST fără e-mail de test configurat în Setări de bază")}})
        r["email_sent"] = bool(to)
    await audit(user, "schemă trimisă la semnare", "prosumator", item_id, [role, p.get("name")])
    return [{**{k: v for k, v in r.items()}, "status": "Link trimis" if r.get("email_sent") else "De trimis"} for r in reqs]

@api_router.post("/sld/{item_id}/unapprove")
async def sld_unapprove(item_id: str, user: dict = Depends(get_current_user)):
    require(user, "admin", "inginer")
    need(user, "prosumator", True)
    await check_access(user, "prosumator", item_id)
    await db.prosumator.update_one({"id": item_id, "owner": user["id"]}, {"$unset": {"sld.approval": "", "sld.approvals": ""}})
    await audit(user, "schemă — aprobare retrasă", "prosumator", item_id, [])
    return {"ok": True}


def catalog_ids(rec: dict) -> list:
    c = rec.get("cef") or {}
    ids = []
    for i in c.get("inverters") or []:
        ids += [i.get("catalog_id"), i.get("panel_catalog_id"), (i.get("battery") or {}).get("catalog_id")]
    ids += [b.get("catalog_id") for b in c.get("shared_batteries") or []]
    g = c.get("grid") or {}
    ids.append(g.get("meter_catalog_id"))
    return list(dict.fromkeys(x for x in ids if x))

async def catalog_files(owner: str, rec: dict) -> list:
    out = []
    for cid in catalog_ids(rec):
        it = await db.catalog.find_one({"owner": owner, "id": cid}, {"_id": 0})
        if not it:
            continue
        for k, label in (("datasheet", "Fișă tehnică"), ("conformity", "Declarație de conformitate")):
            f = it.get(k)
            if f and f.get("storage_path"):
                out.append({"catalog_id": cid, "model": it.get("brand_model"), "kind": label, **f})
    return out

async def sync_catalog_files_to_documents(user: dict, rec: dict) -> int:
    """Attach selected equipment datasheets and conformity declarations to the client dossier."""
    owner = user["id"]
    client_name = rec.get("client_name", "")
    client = await db.clients.find_one(
        {**scope_q(user, "clients"), "name": client_name}, {"_id": 0, "id": 1}
    ) or {}
    added = 0
    for f in await catalog_files(owner, rec):
        exists = await db.documents.find_one({
            "owner": owner,
            "storage_path": f["storage_path"],
            "client_name": client_name,
        }, {"_id": 1})
        if exists:
            continue
        await db.documents.insert_one(_new(user, {
            "client_id": client.get("id", ""),
            "client_name": client_name,
            "kind": "Catalog",
            "doc_type": f"{f['kind']} — {f['model']}",
            "storage_path": f["storage_path"],
            "original_filename": f.get("original_filename"),
            "content_type": f.get("content_type"),
            "size": f.get("size"),
            "pros_ref": rec.get("id"),
        }))
        added += 1
    return added

@api_router.get("/prosumator/{item_id}/catalog-files")
async def pros_catalog_files(item_id: str, user: dict = Depends(get_current_user)):
    rec = await check_access(user, "prosumator", item_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
    return await catalog_files(user["id"], rec)

@api_router.post("/prosumator/{item_id}/attach-catalog")
async def attach_catalog(item_id: str, user: dict = Depends(get_current_user)):
    guard("prosumator", user, write=True)
    rec = await check_access(user, "prosumator", item_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
    added = await sync_catalog_files_to_documents(user, rec)
    return {"added": added}

def merge_pdfs(base: bytes, extra: list) -> bytes:
    w = PdfWriter()
    for p in PdfReader(io.BytesIO(base)).pages:
        w.add_page(p)
    for f in extra:
        if "pdf" not in (f.get("content_type") or "") and not str(f.get("storage_path")).endswith(".pdf"):
            continue
        try:
            data, _ = get_object(f["storage_path"])
            for p in PdfReader(io.BytesIO(data)).pages:
                w.add_page(p)
        except Exception as e:
            logger.error(f"merge skip {f.get('storage_path')}: {e}")
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()

# ---------------- Dossier opis (model PUBLISERV) ----------------
import opis as OPIS

async def apply_selected_client_defaults(owner: str, module: str, data: dict) -> dict:
    """Copy verified client master data into a new dossier without replacing explicit entries."""
    if module not in ("prosumator", "atr", "power", "diu") or not data.get("client_id"):
        return data
    client = await db.clients.find_one({"owner": owner, "id": str(data["client_id"])}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=400, detail="Clientul selectat nu există în agenda contului. Reîncarcă lista și selectează un client salvat.")
    def pick(*keys):
        return next((client.get(key) for key in keys if client.get(key) not in (None, "")), None)
    kind = str(pick("kind", "type") or "").strip().casefold()
    is_company = "jurid" in kind or kind in ("pj", "company", "firmă", "firma")
    applicant_type = "Persoană juridică" if is_company else "Persoană fizică" if ("fiz" in kind or "pf" == kind or "person" in kind) else None
    identifier = pick("idcode")
    defaults = {
        "client_name": pick("name", "full_name"),
        "client_kind": applicant_type or pick("kind", "type"),
        "applicant_type": applicant_type,
        "cnp": pick("cnp") or (identifier if not is_company else None),
        "cui": pick("cui") or (identifier if is_company else None),
        "id_series": pick("id_series", "ci_series", "series"),
        "id_number": pick("id_number", "id_no"),
        "phone": pick("phone", "telephone"),
        "email": pick("email"),
        "county": pick("county"),
        "locality": pick("locality"),
        "operator": pick("operator"),
        "pod": pick("pod"),
        "cf_nr": pick("cf_nr", "land_registry_number"),
        "cadastral_nr": pick("cadastral_nr", "cadastral_number"),
        "supply": pick("supply", "connection_type"),
        "client_address": pick("hq_address", "address"),
        "consumption_address": pick("consumption_address", "pod_address", "address"),
    }
    if client.get("same_address_as_client") or client.get("same_address"):
        defaults["address"] = pick("consumption_address", "pod_address", "address")
    else:
        defaults["address"] = pick("consumption_address", "pod_address")
    for key, value in defaults.items():
        if value not in (None, "") and data.get(key) in (None, ""):
            data[key] = value
    return data

async def get_client(owner: str, rec: dict) -> dict:
    c = None
    if rec.get("client_id"):
        c = await db.clients.find_one({"owner": owner, "id": rec["client_id"]}, {"_id": 0})
    if not c and not rec.get("client_id") and rec.get("client_name"):
        c = await db.clients.find_one({"owner": owner, "name": rec["client_name"]}, {"_id": 0})
    return c or {}

def _normalize_atr_match(value: str) -> str:
    import unicodedata
    text = unicodedata.normalize("NFD", str(value or "")).encode("ascii", "ignore").decode("ascii").casefold()
    return "".join(char for char in text if char.isalnum())


async def resolve_atr_prosumer(user: dict, rec: dict, client: dict | None = None) -> dict | None:
    """Resolve a linked prosumer dossier only when the client and consumption point are unambiguous."""
    rec, client = rec or {}, client or {}
    query = scope_q(user, "prosumator")
    expected_client_id = str(rec.get("client_id") or client.get("id") or "")
    expected_name = _normalize_atr_match(rec.get("client_name") or client.get("name"))
    selected_id = str(rec.get("pros_id") or "")
    if selected_id:
        selected = await db.prosumator.find_one({**query, "id": selected_id}, {"_id": 0})
        if selected:
            selected_client_id = str(selected.get("client_id") or "")
            selected_name = _normalize_atr_match(selected.get("client_name"))
            same_client = (selected_client_id == expected_client_id) if expected_client_id and selected_client_id else bool(expected_name and selected_name == expected_name)
            if same_client:
                return selected

    if expected_client_id:
        rows = await db.prosumator.find(query, {"_id": 0}).to_list(500)
        candidates = [
            item for item in rows
            if (
                str(item.get("client_id") or "") == expected_client_id
                or (
                    not item.get("client_id")
                    and expected_name
                    and _normalize_atr_match(item.get("client_name")) == expected_name
                )
            )
        ]
    elif expected_name:
        rows = await db.prosumator.find(query, {"_id": 0}).to_list(500)
        candidates = [item for item in rows if _normalize_atr_match(item.get("client_name")) == expected_name]
    else:
        return None

    pod = _normalize_atr_match(rec.get("pod") or client.get("pod"))
    address = _normalize_atr_match(rec.get("address") or client.get("consumption_address"))
    if pod:
        candidates = [item for item in candidates if _normalize_atr_match(item.get("pod")) == pod]
    elif address:
        candidates = [item for item in candidates if _normalize_atr_match(item.get("address")) == address]
    return candidates[0] if len(candidates) == 1 else None


async def dossier_ctx(owner, item_id: str):
    if isinstance(owner, dict):
        await check_access(owner, "prosumator", item_id); owner = owner["id"]
    rec = await db.prosumator.find_one({"id": item_id, "owner": owner}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
    rec = CEF.from_legacy(rec)
    client = await get_client(owner, rec)
    base = await db.settings.find_one({"owner": owner}, {"_id": 0}) or {}
    settings, warns = await effective_settings(owner, rec, base)
    info = await OPIS.build_positions(db, owner, rec, client, settings)
    info["signer_warnings"] = warns
    info["finalized"] = rec.get("snapshot", {}).get("at") if rec.get("snapshot") else None
    return rec, client, settings, info

def doc_status(expires: str, has_file: bool) -> str:
    if not has_file:
        return "lipsă"
    if not expires:
        return "valabil"
    today = datetime.now(timezone.utc).date().isoformat()
    soon = (datetime.now(timezone.utc).date() + timedelta(days=30)).isoformat()
    return "expirat" if expires < today else ("aproape de expirare" if expires <= soon else "valabil")

def staff_eligible(p: dict) -> bool:
    return any(doc_status(a.get("expires", ""), bool(a.get("file"))) in ("valabil", "aproape de expirare") and a.get("verified")
               for a in p.get("auths") or [])

SIGN_ROLES = {"executant": "Reprezentant executant", "resp_tehnic": "Responsabil tehnic cu execuția", "electrician": "Electrician autorizat / inginer",
              "verifier": "Verificator schemă", "measurer": "Verificator măsurători (buletin priză)", "designer": "Proiectant schemă"}

async def effective_settings(owner: str, rec: dict, base: dict):
    if rec.get("snapshot"):
        return {**base, **rec["snapshot"]["settings"]}, []
    s, warns = dict(base), []
    sg = rec.get("signers") or {}
    for role, label in SIGN_ROLES.items():
        sid = sg.get(role)
        if not sid:
            continue
        p = await db.staff.find_one({"owner": owner, "id": sid}, {"_id": 0})
        if not p:
            warns.append(f"{label}: persoana selectată nu mai există."); continue
        if not staff_eligible(p):
            warns.append(f"{label}: {p.get('name')} nu are o autorizație valabilă și verificată — nu este completat în documente.")
            s[{"executant": "rep", "verifier": "verifier", "measurer": "measurer", "designer": "designer_name", "resp_tehnic": "resp_tehnic", "electrician": "electrician"}[role]] = ""
            continue
        key = {"executant": "rep", "verifier": "verifier", "measurer": "measurer", "designer": "designer_name", "resp_tehnic": "resp_tehnic", "electrician": "electrician"}[role]
        s[key] = p.get("name")
        if (p.get("signature") or {}).get("storage_path") and p.get("signature_authorized"):
            s.setdefault("_sigs", {})[p.get("name")] = p["signature"]["storage_path"]
        elif role == "executant":
            warns.append(f"{label}: semnătura grafică a lui {p.get('name')} lipsește sau nu este autorizată — documentele rămân cu spațiu pentru semnătură olografă.")
        auth = next((a for a in p.get("auths") or [] if a.get("verified") and doc_status(a.get("expires", ""), bool(a.get("file"))) != "expirat"), {})
        s[key + "_auth"] = f"{auth.get('type', '')} nr. {auth.get('number', '')}".strip()
    iid = rec.get("instrument_id")
    if iid:
        i = await db.instruments.find_one({"owner": owner, "id": iid}, {"_id": 0})
        st = doc_status((i or {}).get("expires", ""), bool((i or {}).get("file")))
        if not i or st in ("expirat", "lipsă"):
            warns.append("Aparat de măsură: certificat " + ("expirat" if st == "expirat" else "lipsă") + " — datele aparatului nu sunt completate.")
            s["meter_device"] = s["meter_serial"] = s["meter_valid"] = ""
        else:
            s["meter_device"], s["meter_serial"], s["meter_valid"] = i.get("maker_model"), i.get("serial"), i.get("expires")
    if base.get("anre_valid") and doc_status(base["anre_valid"], True) == "expirat":
        warns.append("Atestatul ANRE al firmei este expirat.")
    if (base.get("stamp") or {}).get("storage_path") and (base["stamp"].get("content_type") or "").startswith("image/"):
        s["_stamp_path"] = base["stamp"]["storage_path"]
    elif sg.get("executant"):
        warns.append("Ștampila firmei (imagine) nu este încărcată în Setări de bază — nu se aplică automat pe documente.")
    return s, warns

@api_router.post("/dossier/{item_id}/finalize")
async def dossier_finalize(item_id: str, user: dict = Depends(get_current_user)):
    require(user, "admin", "inginer", "electrician")
    need(user, "prosumator", True)
    rec = await check_access(user, "prosumator", item_id)
    check_inverters(user, rec)
    base = await db.settings.find_one({"owner": user["id"]}, {"_id": 0}) or {}
    s, _ = await effective_settings(user["id"], {**rec, "snapshot": None}, base)
    if SZ.state(rec, await get_client(user["id"], rec), s)["status"] != "approved":
        raise HTTPException(status_code=400, detail="Dosarul nu poate fi finalizat: schema monofilară nu este verificată și aprobată de proiectant / verificator. Exportul rămâne disponibil ca CIORNĂ.")
    snap = {"settings": {k: v for k, v in s.items() if k not in ("owner", "_id")}, "signers": rec.get("signers") or {},
            "at": datetime.now(timezone.utc).isoformat(), "by": user.get("email")}
    await db.prosumator.update_one({"id": item_id}, {"$set": {"snapshot": snap}, "$push": {"snapshot_history": snap}})
    await audit(user, "finalizare", "prosumator", item_id, ["snapshot"])
    return {"ok": True, "at": snap["at"]}

@api_router.post("/dossier/{item_id}/reopen")
async def dossier_reopen(item_id: str, user: dict = Depends(get_current_user)):
    require(user, "admin", "inginer", "electrician")
    need(user, "prosumator", True)
    await check_access(user, "prosumator", item_id)
    res = await db.prosumator.update_one({"id": item_id, "owner": user["id"]}, {"$unset": {"snapshot": ""}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
    await audit(user, "redeschidere", "prosumator", item_id, ["snapshot"])
    return {"ok": True}

@api_router.get("/dossier/{item_id}")
async def dossier_info(item_id: str, user: dict = Depends(get_current_user)):
    rec, client, _, info = await dossier_ctx(user, item_id)
    return {**info, "client_id": client.get("id"), "client_kind": client.get("kind"), "statuses": OPIS.STATUSES,
            "client": {"name": client.get("name") or rec.get("client_name") or "", "email": client.get("email") or "", "phone": client.get("phone") or ""}}

@api_router.put("/dossier/{item_id}/item/{key}")
async def dossier_item(item_id: str, key: str, request: Request, user: dict = Depends(get_current_user)):
    guard("prosumator", user, write=True)
    body = await request.json()
    rec = await check_access(user, "prosumator", item_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
    _, _, _, info = await dossier_ctx(user, item_id)
    if key not in {p["key"] for p in info["positions"]}:
        raise HTTPException(status_code=404, detail="Poziție inexistentă în opis")
    cur = (rec.get("opis") or {}).get(key) or {}
    if "status" in body:
        if body["status"] and body["status"] not in OPIS.STATUSES:
            raise HTTPException(status_code=400, detail="Stadiu invalid")
        cur["status"] = body["status"] or None
    if body.get("upload"):
        cur["upload"] = body["upload"]
    if body.get("clear_upload"):
        cur.pop("upload", None)
    await db.prosumator.update_one({"id": item_id, "owner": user["id"]}, {"$set": {f"opis.{key}": cur, "updated_at": datetime.now(timezone.utc).isoformat()}})
    await audit(user, "opis", "prosumator", item_id, [key] + list(body.keys()))
    return {"ok": True}

@api_router.get("/dossier/{item_id}/file/{key}")
async def dossier_file(item_id: str, key: str, fmt: str = "pdf", generated: int = 0, authorization: str = Header(None), auth: str = Query(None)):
    user = await user_from_token(authorization, auth)
    rec, client, settings, info = await dossier_ctx(user, item_id)
    p = next((x for x in info["positions"] if x["key"] == key), None)
    if key == "opis":
        p = {"source": "generat", "docs": ["declaratie_autenticitate"], "key": "opis"}
    if not p:
        raise HTTPException(status_code=404, detail="Poziție inexistentă")
    name = f"{key}_{(client.get('name') or rec.get('client_name') or 'dosar').replace(' ', '_')}"
    if fmt == "docx":
        if key == "fisa_tehnica":
            docx = SLD.tech_sheet_docx(rec, client, settings, SZ.compute(rec, client), SZ.state(rec, client, settings))
            return Response(content=docx, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            headers={"Content-Disposition": disp('attachment', f"{name}.docx")})
        if key == "schema":
            raise HTTPException(status_code=400, detail="Schema monofilară se exportă doar în PDF (vectorial)")
        if p["source"] != "generat":
            raise HTTPException(status_code=400, detail="Export Word doar pentru documentele generate")
        docx = docgen.render_docx(p["docs"], rec, settings, client, info["titles"])
        return Response(content=docx, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": disp('attachment', f"{name}.docx")})
    parts = await OPIS.position_pdf(p, rec, client, settings, info["titles"], get_object, force_generated=bool(generated))
    if not parts:
        raise HTTPException(status_code=404, detail="Documentul nu este încă încărcat")
    pdf = parts[0] if len(parts) == 1 else merge_pdfs(parts[0], [])
    if len(parts) > 1:
        w = PdfWriter()
        for b in parts:
            for pg in PdfReader(io.BytesIO(b)).pages:
                w.add_page(pg)
        o = io.BytesIO(); w.write(o); pdf = o.getvalue()
    if rec.get("is_test") and key != "schema":
        pdf = OPIS.mark_test(pdf)
    elif p.get("source") == "generat" and (p.get("missing") or info.get("common_missing")):
        pdf = OPIS.mark_test(pdf, "CIORNĂ — DATE / MĂSURĂTORI DE COMPLETAT", 28)
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": disp('inline', f"{name}.pdf")})

@api_router.get("/dossier/{item_id}/export")
async def dossier_export(item_id: str, authorization: str = Header(None), auth: str = Query(None)):
    user = await user_from_token(authorization, auth)
    rec, client, settings, info = await dossier_ctx(user, item_id)
    pdf = await OPIS.export_bundle(info, rec, client, settings, get_object, logger)
    name = f"DOSAR_{(client.get('name') or rec.get('client_name') or 'prosumator').replace(' ', '_')}{'_CIORNA' if not info['complete'] else ''}.pdf"
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": disp('inline', f"{name}")})

SIMPLE_KEYS = ("notificare", "executant", "conformitate", "afm", "imputernicire", "priza", "pif_pv", "schema", "fisa_tehnica")

@api_router.get("/dossier/{item_id}/simple")
async def dossier_simple(item_id: str, authorization: str = Header(None), auth: str = Query(None)):
    user = await user_from_token(authorization, auth)
    rec, client, settings, info = await dossier_ctx(user, item_id)
    pos = [p for p in info["positions"] if p["key"] in SIMPLE_KEYS or p.get("source") == "catalog"]
    sub = {**info, "positions": pos, "titles": [p["title"] for p in pos],
           "complete": not any(p.get("missing") for p in pos) and not any(p.get("status") == "de completat" for p in pos)}
    pdf = await OPIS.export_bundle(sub, rec, client, settings, get_object, logger)
    name = f"DOSAR_PROSUMATOR_SIMPLU_{(client.get('name') or rec.get('client_name') or 'prosumator').replace(' ', '_')}{'_CIORNA' if not sub['complete'] else ''}.pdf"
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": disp('inline', name)})

import power_doc as PWR
import atr_doc as ATR


@api_router.get("/atr/{item_id}/official-docx")
async def atr_official_docx(item_id: str, authorization: str = Header(None), auth: str = Query(None)):
    user = await user_from_token(authorization, auth)
    rec = await check_access(user, "atr", item_id)
    client = await get_client(user["id"], rec)
    settings = await db.settings.find_one({"owner": user["id"]}, {"_id": 0}) or {}
    pros = None
    if rec.get("pros_id") and await db.prosumator.find_one({**scope_q(user, "prosumator"), "id": rec["pros_id"]}, {"id": 1}):
        pros, pclient, settings, _ = await dossier_ctx(user, rec["pros_id"])
        client = {**(pclient or {}), **(client or {})}
    try:
        payload = ATR.render_deer_official_docx(rec, client or {}, settings, pros or {})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        logger.exception("DEER official DOCX generation failed")
        raise HTTPException(status_code=500, detail="Nu am putut genera formularul DEER. Verificați dacă șablonul oficial este disponibil.")
    safe_name = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in str((client or {}).get("name") or "client")).strip().replace(" ", "_")
    filename = f"DEER_{str(rec.get('deer_case') or 'cerere').replace(' ', '_')}_{safe_name}.docx"
    return Response(content=payload, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": disp("attachment", filename)})

@api_router.get("/atr/{item_id}/pdf")
async def atr_pdf(item_id: str, full: int = 0, authorization: str = Header(None), auth: str = Query(None)):
    user = await user_from_token(authorization, auth)
    rec = await check_access(user, "atr", item_id)
    pdf, name = await atr_pack(user, rec, full)
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": disp('inline', name)})

def expected_catalog_document_keys(pros: dict) -> set:
    """Return per-model datasheet and conformity keys required by the selected equipment."""
    cef = (pros or {}).get("cef") or {}
    expected = set()

    def add(label: str, model, catalog_id):
        name = str(model or "").strip()
        # OPIS only creates catalog positions for equipment with an identified model.
        if not name:
            return
        suffix = catalog_id or name
        for kind in ("datasheet", "conformity"):
            expected.add(f"cat_{kind}_{label}_{suffix}")

    for inv in cef.get("inverters") or []:
        add("invertor", inv.get("brand_model"), inv.get("catalog_id"))
        add("panou", inv.get("panel_model"), inv.get("panel_catalog_id"))
        if inv.get("battery_mode") == "own":
            battery = inv.get("battery") or {}
            add("baterie", battery.get("model"), battery.get("catalog_id"))
    for battery in cef.get("shared_batteries") or []:
        add("baterie", battery.get("model"), battery.get("catalog_id"))
    grid = cef.get("grid") or {}
    add("smart_meter", grid.get("meter"), grid.get("meter_catalog_id"))
    return expected


def catalog_documents_complete(pros: dict, positions: list) -> bool:
    expected = expected_catalog_document_keys(pros)
    available = {p.get("key") for p in positions or [] if p.get("source") == "catalog" and p.get("files")}
    return bool(expected) and expected.issubset(available)


ATR_CLIENT_DOC_SLOTS = (
    ("ci", "Act de identitate"),
    ("cf", "Extras de carte funciară"),
    ("factura", "Factură de energie"),
    ("certificat", "Certificat de înregistrare"),
    ("constatator", "Certificat constatator ONRC"),
    ("semnate", "Documente semnate"),
)
ATR_CLIENT_DOC_MAX_FILE = 25 * 1024 * 1024
ATR_CLIENT_DOC_MAX_TOTAL = 100 * 1024 * 1024


def atr_client_documents(user: dict, client: dict):
    """Return only the selected client's uploaded documents stored in this user's namespace."""
    docs = (client or {}).get("docs") or {}
    owner_prefix = f"{APP_NAME}/uploads/{user['id']}/"
    result, issues, total = [], [], 0
    for slot, label in ATR_CLIENT_DOC_SLOTS:
        entries = docs.get(slot) or []
        if not isinstance(entries, list):
            continue
        for item in entries:
            if not isinstance(item, dict):
                continue
            name = str(item.get("original_filename") or f"{slot}.pdf")
            path = str(item.get("storage_path") or "")
            if not path.startswith(owner_prefix):
                issues.append(f"{label} — fișierul nu aparține spațiului de stocare al contului.")
                continue
            try:
                data, content_type = get_object(path)
                size = len(data)
                if size > ATR_CLIENT_DOC_MAX_FILE or total + size > ATR_CLIENT_DOC_MAX_TOTAL:
                    issues.append(f"{label} — {name} nu a fost inclus (limita pachetului de documente client a fost depășită).")
                    continue
                total += size
                result.append({"slot": slot, "label": label, "name": name, "data": data,
                               "content_type": content_type or item.get("content_type") or "application/octet-stream"})
            except Exception as exc:
                logger.warning("ATR client document could not be read (%s): %s", path, exc)
                issues.append(f"{label} — {name} nu a putut fi citit din stocare.")
    return result, issues


async def atr_pack(user: dict, rec: dict, full: int):
    client = await get_client(user["id"], rec)
    base = await db.settings.find_one({"owner": user["id"]}, {"_id": 0}) or {}
    pros, info = None, None
    linked_pros = await resolve_atr_prosumer(user, rec, client)
    if linked_pros:
        pros, pclient, base, info = await dossier_ctx(user, linked_pros["id"])
        client = {**(pclient or {}), **(client or {})}
        rec = {**rec, "pros_id": linked_pros["id"]}
        # A linked prosumer dossier is authoritative evidence that this ATR covers production.
        if "producere" not in str(rec.get("kind") or "").casefold():
            rec["kind"] = "loc de consum și de producere"
    att = rec.get("attachments") or {}
    client_documents, client_document_issues = atr_client_documents(user, client)
    auto = {}
    if info and ATR.is_prod(rec):
        bykey = {p["key"]: p for p in info["positions"]}
        auto = {"schema": [bykey.get("schema")], "fise": [p for p in info["positions"] if p.get("source") == "catalog" and p.get("files")]}
    attached = {k for k, v in att.items() if v}
    # Client documents uploaded once in the client profile are valid supporting
    # evidence for matching ATR checklist positions; do not infer unrelated items.
    for document in client_documents:
        if document["slot"] == "ci":
            attached.add("id")
        elif document["slot"] == "cf":
            attached.add("cf")
        elif document["slot"] == "constatator":
            attached.add("constatator")
    # A linked generated item is not proof of a ready document. Count schema only
    # when the source opis says it is generated/attached; catalog evidence must
    # exist for every selected model before it satisfies the required "fise" slot.
    schema_position = (auto.get("schema") or [None])[0]
    if schema_position and schema_position.get("auto_status") in ("generat", "atașat"):
        attached.add("schema")
    if pros and ATR.is_prod(rec) and auto.get("fise") and catalog_documents_complete(pros, (info or {}).get("positions", [])):
        attached.add("fise")
    if pros and ATR.is_prod(rec) and "fise" in ATR.required(rec):
        if not catalog_documents_complete(pros, (info or {}).get("positions", [])):
            attached.discard("fise")
    parts = [ATR.render_atr(rec, client, base, pros or {}, attached)]
    annex_registry_issue = ""
    if full:
        operator_key = ATR.op_key(rec.get("operator"), (pros or {}).get("operator"), client.get("operator"))
        if operator_key == "deer":
            annex_pdf = ATR.render_deer_annex(rec, client, base, pros or {}, attached)
            if annex_pdf:
                parts.append(annex_pdf)
        elif operator_key:
            # Use the same annex selector as the ZIP package, and include a validated
            # official PDF copy when the registry has one. DOC/DOCX originals remain
            # in the ZIP; the main PDF stays explicit about that limitation.
            from atr_routes import _registry_forms_for_request, _fetch_registry_annex, _prefill_official_pdf
            annex_no, forms = await _registry_forms_for_request(operator_key, rec, pros or {})
            if annex_no:
                annex_pdf = ATR.render_operator_annex_prep(
                    rec, client, pros or {}, operator_key, annex_no,
                    forms[0].get("title", "") if forms else "")
                parts.append(annex_pdf)
                if not forms:
                    annex_registry_issue = f"Nu există în registrul aplicației un formular oficial verificat pentru Anexa {annex_no} a operatorului selectat; fișa de precompletare nu înlocuiește formularul oficial."
                else:
                    try:
                        official_data, official_name = await _fetch_registry_annex(forms[0], operator_key)
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

@api_router.get("/power/{item_id}/pdf")
async def power_pdf(item_id: str, full: int = 0, authorization: str = Header(None), auth: str = Query(None)):
    user = await user_from_token(authorization, auth)
    rec = await check_access(user, "power", item_id)
    client = await get_client(user["id"], rec)
    base = await db.settings.find_one({"owner": user["id"]}, {"_id": 0}) or {}
    pros, auto = None, {}
    if rec.get("pros_id") and await db.prosumator.find_one({**scope_q(user, "prosumator"), "id": rec["pros_id"]}, {"id": 1}):
        pros, pclient, ps, info = await dossier_ctx(user, rec["pros_id"])
        client = client or pclient
        base = ps
        bykey = {p["key"]: p for p in info["positions"]}
        auto = {"h": [bykey.get("receptie")], "i": [bykey.get("priza")], "k": [bykey.get("schema")],
                "j": [p for p in info["positions"] if p.get("source") == "catalog" and p.get("files")]}
    att = rec.get("attachments") or {}
    attached = {k for k, v in att.items() if v}
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
    if pros and not rec.get("is_test") and catalog_documents_complete(pros, (info or {}).get("positions", [])):
        attached.add("j")
    parts = [PWR.render_anexa1(rec, client, base, pros or {}, attached, ATR.op_key(rec.get("operator"), (pros or {}).get("operator"), client.get("operator")))]
    unavailable = []
    if pros and not rec.get("is_test"):
        # Use the same per-model catalog evidence as the prosumer and ATR dossiers;
        # a datasheet for one model cannot satisfy another model's requirement.
        if not catalog_documents_complete(pros, (info or {}).get("positions", [])):
            attached.discard("j")
            parts[0] = PWR.render_anexa1(rec, client, base, pros, attached,
                ATR.op_key(rec.get("operator"), pros.get("operator"), client.get("operator")))
    if full:
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
    new_request = rec.get("request_kind") == "nou"
    juridical = "jurid" in str((client or {}).get("kind") or "").lower()
    required_keys = {"a"} | ({"b"} if juridical else set()) | ({"c", "d", "e", "f", "g"} if new_request else {"h", "i", "j", "k"})
    missing_keys = sorted(k for k in required_keys if k not in attached)
    pwr_titles = dict(PWR.DOCS)
    missing_titles = [f"Document obligatoriu lipsă: {pwr_titles.get(k, k)}" for k in missing_keys]
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
    incomplete = bool(missing_keys or unavailable)
    name = f"{'DOSAR_SPOR_PUTERE' if full else 'ANEXA1_DEER'}_{(client.get('name') or rec.get('client_name') or '').replace(' ', '_')}{'_INCOMPLET' if full and incomplete else ''}.pdf"
    return Response(content=o.getvalue(), media_type="application/pdf", headers={"Content-Disposition": disp('inline', name)})

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
    elif not verify_password(admin_password, existing["password_hash"]):
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
# Comma-separated list, e.g. https://dns-energy-web.onrender.com
_cors_raw = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
_cors_origins = [origin.strip().rstrip("/") for origin in _cors_raw.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)
