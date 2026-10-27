from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, UploadFile, File, Form, Response, Header, Query
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

app = FastAPI()
api_router = APIRouter(prefix="/api")

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
        user.pop("password_hash", None)
        user.pop("_id", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesiune expirată")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalid")

# ---------------- Object storage ----------------
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "d-energy"
storage_key = None

def init_storage(force: bool = False):
    global storage_key
    if storage_key and not force:
        return storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    storage_key = resp.json()["storage_key"]
    return storage_key

def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = requests.put(f"{STORAGE_URL}/objects/{path}",
                        headers={"X-Storage-Key": key, "Content-Type": content_type},
                        data=data, timeout=120)
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.put(f"{STORAGE_URL}/objects/{path}",
                            headers={"X-Storage-Key": key, "Content-Type": content_type},
                            data=data, timeout=120)
    resp.raise_for_status()
    return resp.json()

def get_object(path: str):
    key = init_storage()
    resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")

MIME_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif",
              "webp": "image/webp", "pdf": "application/pdf", "doc": "application/msword",
              "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
              "xls": "application/vnd.ms-excel",
              "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}

# ---------------- Models ----------------
class RegisterReq(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None

class LoginReq(BaseModel):
    email: EmailStr
    password: str

# ---------------- Auth routes ----------------
@api_router.post("/auth/register")
async def register(body: RegisterReq, response: Response):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email deja înregistrat")
    uid = str(uuid.uuid4())
    doc = {"id": uid, "email": email, "password_hash": hash_password(body.password),
           "name": body.name or email.split("@")[0], "role": "admin",
           "created_at": datetime.now(timezone.utc).isoformat()}
    await db.users.insert_one(doc)
    token = create_access_token(uid, email)
    return {"access_token": token, "user": {"id": uid, "email": email, "name": doc["name"], "role": "admin"}}

@api_router.post("/auth/login")
async def login(body: LoginReq, response: Response):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email sau parolă incorectă")
    token = create_access_token(user["id"], email)
    return {"access_token": token, "user": {"id": user["id"], "email": email,
            "name": user.get("name"), "role": user.get("role", "admin")}}

@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return {"id": user["id"], "email": user["email"], "name": user.get("name"), "role": user.get("role", "admin")}

@api_router.post("/auth/logout")
async def logout(user: dict = Depends(get_current_user)):
    return {"ok": True}

# ---------------- Generic module CRUD ----------------
MODULES = ["clients", "prosumator", "diu", "mono", "panels", "anti", "pram", "equipment", "power", "works", "projects", "documents", "catalog", "staff", "instruments"]

def clean(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc

@api_router.get("/data/{module}")
async def list_items(module: str, q: Optional[str] = None, user: dict = Depends(get_current_user)):
    if module not in MODULES:
        raise HTTPException(status_code=404, detail="Modul inexistent")
    guard(module, user)
    query = {"owner": user["id"]}
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
    data.pop("_id", None)
    data["id"] = str(uuid.uuid4())
    data["owner"] = user["id"]
    data["created_at"] = datetime.now(timezone.utc).isoformat()
    data["updated_at"] = data["created_at"]
    guard(module, user)
    data["created_by"] = user.get("email")
    await db[module].insert_one(dict(data))
    await audit(user, "creare", module, data["id"], list(data.keys()))
    return clean(data)

@api_router.get("/data/{module}/{item_id}")
async def get_item(module: str, item_id: str, user: dict = Depends(get_current_user)):
    if module not in MODULES:
        raise HTTPException(status_code=404, detail="Modul inexistent")
    guard(module, user)
    doc = await db[module].find_one({"id": item_id, "owner": user["id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Înregistrare inexistentă")
    return clean(doc)

@api_router.put("/data/{module}/{item_id}")
async def update_item(module: str, item_id: str, request: Request, user: dict = Depends(get_current_user)):
    if module not in MODULES:
        raise HTTPException(status_code=404, detail="Modul inexistent")
    guard(module, user)
    data = await request.json()
    data.pop("_id", None); data.pop("id", None); data.pop("owner", None); data.pop("created_at", None)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    if module == "prosumator":
        data = derive_cef(data)
        data.pop("opis", None); data.pop("snapshot", None); data.pop("snapshot_history", None); data.pop("sld", None)
        if data.get("client_name"):
            c = await db.clients.find_one({"owner": user["id"], "name": data["client_name"]}, {"id": 1})
            if c:
                data["client_id"] = c["id"]
    res = await db[module].update_one({"id": item_id, "owner": user["id"]}, {"$set": data})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Înregistrare inexistentă")
    await audit(user, "modificare", module, item_id, list(data.keys()))
    doc = await db[module].find_one({"id": item_id, "owner": user["id"]})
    return clean(doc)

@api_router.delete("/data/{module}/{item_id}")
async def delete_item(module: str, item_id: str, user: dict = Depends(get_current_user)):
    if module not in MODULES:
        raise HTTPException(status_code=404, detail="Modul inexistent")
    guard(module, user)
    await db[module].delete_one({"id": item_id, "owner": user["id"]})
    await audit(user, "ștergere", module, item_id, [])
    if module == "prosumator":
        for m in ("works", "mono", "equipment"):
            await db[m].delete_many({"owner": user["id"], "pros_ref": item_id})
    return {"ok": True}

# ---------------- Dashboard ----------------
@api_router.get("/stats/dashboard")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    owner = {"owner": user["id"]}
    clients = await db.clients.count_documents(owner)
    diu = await db.diu.count_documents(owner)
    mono = await db.mono.count_documents(owner)
    pending = await db.diu.count_documents({**owner, "status": {"$in": ["În lucru", "Documente de completat", "În verificare"]}})
    recent = await db.diu.find(owner).sort("created_at", -1).to_list(5)
    return {"clients": clients, "diu": diu, "mono": mono, "pending": pending,
            "recent": [clean(r) for r in recent]}

# ---------------- Settings (singleton per owner) ----------------
PRIVATE = ("staff", "instruments")

def guard(module: str, user: dict):
    if module in PRIVATE and user.get("role", "admin") not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="Acces restricționat la documentele personalului")

async def audit(user: dict, action: str, module: str, item_id: str, fields: list):
    await db.audit.insert_one({"owner": user["id"], "user": user.get("email"), "action": action, "module": module, "item_id": item_id,
                               "fields": [f for f in fields if f not in ("updated_at", "owner", "id", "created_at")][:40],
                               "at": datetime.now(timezone.utc).isoformat()})

@api_router.get("/audit")
async def audit_log(module: Optional[str] = None, item_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {"owner": user["id"]}
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
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "bin"
    path = f"{APP_NAME}/uploads/{user['id']}/{uuid.uuid4()}.{ext}"
    data = await file.read()
    ct = file.content_type or MIME_TYPES.get(ext, "application/octet-stream")
    result = put_object(path, data, ct)
    return {"storage_path": result["path"], "original_filename": file.filename,
            "content_type": ct, "size": result.get("size", len(data))}

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
    try:
        jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalid")
    data, content_type = get_object(path)
    return Response(content=data, media_type=content_type)

# ---------------- AI extraction & document generation ----------------
import docgen
from ai_extract import extract_pdf

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
    return user

@api_router.post("/ai/extract")
async def ai_extract(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    data = await file.read()
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "pdf"
    ct = file.content_type or MIME_TYPES.get(ext, "application/pdf")
    if ct not in ("application/pdf", "image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Sunt acceptate doar PDF sau imagini")
    stored = put_object(f"{APP_NAME}/uploads/{user['id']}/{uuid.uuid4()}.{ext}", data, ct)
    try:
        fields = await extract_pdf(data, ct)
    except Exception as e:
        logger.error(f"AI extract failed: {e}")
        raise HTTPException(status_code=502, detail="Nu am putut citi documentul. Încearcă din nou.")
    return {"data": fields, "file": {"storage_path": stored["path"], "original_filename": file.filename,
                                      "content_type": ct, "size": len(data)}}

def _new(user, extra):
    now = datetime.now(timezone.utc).isoformat()
    return {"id": str(uuid.uuid4()), "owner": user["id"], "created_at": now, "updated_at": now, **extra}

@api_router.post("/import/prosumator")
async def import_prosumator(request: Request, user: dict = Depends(get_current_user)):
    d = await request.json()
    for k in ("_id", "id", "owner", "created_at", "updated_at"):
        d.pop(k, None)
    name = (d.get("client_name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Lipsește numele beneficiarului")
    client = await db.clients.find_one({"owner": user["id"], "name": name}, {"_id": 0})
    if d.get("pod") and await db.prosumator.find_one({"owner": user["id"], "client_name": name, "pod": d["pod"]}):
        raise HTTPException(status_code=409, detail="Există deja un dosar pentru acest client și acest POD")
    if not client:
        client = _new(user, {"name": name, "idcode": d.get("cnp", ""), "phone": d.get("phone", ""), "email": d.get("email", ""),
                             "address": d.get("address", ""), "hq_address": d.get("hq_address", ""), "county": d.get("county", ""),
                             "pod": d.get("pod", ""), "operator": d.get("operator", ""), "cadastral_nr": d.get("cadastral_nr", ""),
                             "cf_nr": d.get("cf_nr", ""), "supplier": d.get("supplier", ""), "rep_name": d.get("rep_name", ""),
                             "regcom": d.get("regcom", ""), "kind": d.get("kind", "")})
        await db.clients.insert_one(dict(client))
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
    sz = docgen.sizing(d)
    await db.works.insert_one(_new(user, {"title": f"Sistem fotovoltaic {docgen.fmt(sz['kwp'] or docgen.num(d.get('power')))} kWp — {name}",
        "client_name": name, "type": "Sistem fotovoltaic", "status": "Finalizat" if d.get("status") == "Prosumator activ" else "În execuție",
        "start_date": d.get("date", ""), "responsible": d.get("executant_rep", ""), "notes": f"Generat din dosar {pros['number']}", "pros_ref": pros["id"]}))
    await db.mono.insert_one(_new(user, {"code": f"SM-{pros['number']} / rev. 0", "type": "Sistem fotovoltaic", "voltage": "230/400 V AC",
        "dc_voltage": "conform MPPT invertor", "fuses": f"BMP {sz['main']} A {sz['poles']}P C · invertor {sz['invb']} A {sz['poles']}P C · gPV 15 A DC",
        "spd_ac": "Tip 1+2", "spd_dc": "Tip 2", "grounding": f"{d.get('grounding_ohm', '')} Ω",
        "battery_type": "Low Voltage (LV)" if d.get("battery") else "Fără baterie", "bess_kwh": d.get("battery_kwh", ""),
        "battery_ah": d.get("battery_ah", ""), "notes": f"Generată automat pentru {pros['number']} ({name})", "pros_ref": pros["id"]}))
    for nm, model, rating in [("Invertor", d.get("inverter"), f"{d.get('inverter_kw', '')} kW"),
                              ("Module fotovoltaice", d.get("panels"), f"{d.get('panel_count', '')} × {d.get('panel_w', '')} W"),
                              ("Sistem de stocare", d.get("battery"), f"{d.get('battery_kwh', '')} kWh")]:
        if model:
            await db.equipment.insert_one(_new(user, {"name": nm, "model": model, "rating": rating, "serial": "", "client_name": name, "pros_ref": pros["id"]}))
    for f in files:
        await db.documents.insert_one(_new(user, {"client_id": client["id"], "client_name": name, "kind": "Dosar prosumator",
                                                  "doc_type": "Dosar prosumator (import)", **f}))
    return clean(pros)

@api_router.get("/docs/types")
async def doc_types(user: dict = Depends(get_current_user)):
    return [{"key": k, "label": v[0]} for k, v in docgen.DOCS.items()]

@api_router.get("/docs/sizing/{item_id}")
async def doc_sizing(item_id: str, user: dict = Depends(get_current_user)):
    rec = await db.prosumator.find_one({"id": item_id, "owner": user["id"]}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
    return docgen.sizing(rec)

@api_router.get("/docs/{doc_type}/{item_id}")
async def generate_doc(doc_type: str, item_id: str, authorization: str = Header(None), auth: str = Query(None),
                       attach: int = Query(0)):
    user = await user_from_token(authorization, auth)
    rec = await db.prosumator.find_one({"id": item_id, "owner": user["id"]}, {"_id": 0})
    if doc_type == "all":
        has_cef = bool(((rec or {}).get("cef") or {}).get("inverters"))
        keys = [k for k in docgen.DOCS if k not in ("schema", "schema_cef")]
    else:
        keys = [doc_type]
    if any(k not in docgen.DOCS for k in keys):
        raise HTTPException(status_code=404, detail="Tip document inexistent")
    if not rec:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
    settings = await db.settings.find_one({"owner": user["id"]}, {"_id": 0}) or {}
    client = await get_client(user["id"], rec)
    pdf = docgen.render(keys, rec, settings, client)
    if attach:
        pdf = merge_pdfs(pdf, await catalog_files(user["id"], rec))
    fname = f"{doc_type}_{(rec.get('client_name') or 'dosar').replace(' ', '_')}.pdf"
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{fname}"'})

# ---------------- CEF checks & catalog ----------------
import cef as CEF
from catalog_seed import SEED as CATALOG_SEED, NOTE as CATALOG_NOTE
from pypdf import PdfReader, PdfWriter
import io

async def seed_catalog(owner: str):
    await db.settings.update_one({"owner": owner}, {"$setOnInsert": {"owner": owner}}, upsert=True)
    res = await db.settings.update_one({"owner": owner, "catalog_seeded": {"$ne": True}}, {"$set": {"catalog_seeded": True}})
    if res.modified_count and not await db.catalog.count_documents({"owner": owner}):
        await db.catalog.insert_many([_new({"id": owner}, {**x, "notes": CATALOG_NOTE}) for x in CATALOG_SEED])

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

def pdf_resp(data: bytes, name: str):
    return Response(content=data, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{name}"'})

async def sld_ctx(owner: str, item_id: str):
    rec = await db.prosumator.find_one({"id": item_id, "owner": owner}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
    client = await get_client(owner, rec)
    base = await db.settings.find_one({"owner": owner}, {"_id": 0}) or {}
    s, warns = await effective_settings(owner, rec, base)
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
    rec, client, s, res, state, warns = await sld_ctx(user["id"], item_id)
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
            "history": [{k: v for k, v in h.items() if k != "hash"} | {"current": h.get("hash") == state["fingerprint"]} for h in reversed(sld.get("history") or [])]}

@api_router.get("/sld/{item_id}/pdf")
async def sld_pdf(item_id: str, authorization: str = Header(None), auth: str = Query(None), fmt: str = Query("auto")):
    user = await user_from_token(authorization, auth)
    rec, client, s, res, state, _ = await sld_ctx(user["id"], item_id)
    return pdf_resp(SLD.render(rec, client, s, res, state, fmt), f"schema_monofilara_{rec.get('number') or item_id}.pdf")

@api_router.get("/sld/{item_id}/report")
async def sld_report(item_id: str, authorization: str = Header(None), auth: str = Query(None)):
    user = await user_from_token(authorization, auth)
    rec, client, s, res, state, _ = await sld_ctx(user["id"], item_id)
    return pdf_resp(SLD.report(rec, client, s, res, state), f"raport_calcul_{rec.get('number') or item_id}.pdf")

@api_router.post("/sld/{item_id}/apply")
async def sld_apply(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    rec = await db.prosumator.find_one({"id": item_id, "owner": user["id"]}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
    body = await request.json() if (await request.body()) else {}
    cef, filled = SZ.apply(body.get("cef") or rec.get("cef") or {})
    await db.prosumator.update_one({"id": item_id}, {"$set": {"cef": cef}})
    await audit(user, "dimensionare automată", "prosumator", item_id, filled)
    return {"filled": filled, "cef": cef}

@api_router.put("/sld/{item_id}/source")
async def sld_source(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    rec = await db.prosumator.find_one({"id": item_id, "owner": user["id"]}, {"_id": 0})
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
    role = (await request.json()).get("role")
    if role not in SLD_ROLES:
        raise HTTPException(status_code=400, detail="Rol invalid")
    rec, client, s, res, state, _ = await sld_ctx(user["id"], item_id)
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
    rec2, client2, s2, res2, st2, _ = await sld_ctx(user["id"], item_id)
    if src == "uploaded":
        f = sld["upload"]
    else:
        pdf = SLD.render(rec2, client2, s2, res2, st2)
        stored = put_object(f"{APP_NAME}/sld/{user['id']}/{item_id}/rev{rev}_{uuid.uuid4().hex[:8]}.pdf", pdf, "application/pdf")
        f = {"storage_path": stored["path"], "original_filename": f"schema_rev{rev}.pdf", "content_type": "application/pdf", "size": len(pdf)}
    entry = {"revision": rev, "at": sld["approval"]["at"], "role": role, "role_label": SLD_ROLES[role], "name": p.get("name"),
             "auth": sld["approval"]["auth"], "hash": sld["approval"]["hash"], "source": src, "file": f, "by": user.get("email")}
    await db.prosumator.update_one({"id": item_id}, {"$push": {"sld.history": entry}})
    await audit(user, "schemă aprobată", "prosumator", item_id, [role, p.get("name")])
    return sld["approval"]

@api_router.post("/sld/{item_id}/send-sign")
async def sld_send_sign(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    b = await request.json()
    role = b.get("role")
    if role not in SLD_ROLES:
        raise HTTPException(status_code=400, detail="Rol invalid")
    rec, client, s, res, state, _ = await sld_ctx(user["id"], item_id)
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
        await send_email(to=p["email"], subject=f"Semnare {r['doc_title'][:60]}", html=html)
        await db.sign_requests.update_one({"id": r["id"]}, {"$set": {"status": "Link trimis"}, "$push": {"history": hist("Link trimis", None, f"e-mail automat către {mask(p['email'])}; de {user.get('email')}")}})
    await audit(user, "schemă trimisă la semnare", "prosumator", item_id, [role, p.get("name")])
    return [{**sign_public({**{k: v for k, v in r.items() if k != "token"}, "history": [], "status": "Link trimis"}), "token": r["token"]} for r in reqs]

@api_router.post("/sld/{item_id}/unapprove")
async def sld_unapprove(item_id: str, user: dict = Depends(get_current_user)):
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

@api_router.get("/prosumator/{item_id}/catalog-files")
async def pros_catalog_files(item_id: str, user: dict = Depends(get_current_user)):
    rec = await db.prosumator.find_one({"id": item_id, "owner": user["id"]}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
    return await catalog_files(user["id"], rec)

@api_router.post("/prosumator/{item_id}/attach-catalog")
async def attach_catalog(item_id: str, user: dict = Depends(get_current_user)):
    rec = await db.prosumator.find_one({"id": item_id, "owner": user["id"]}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
    client = await db.clients.find_one({"owner": user["id"], "name": rec.get("client_name")}, {"_id": 0}) or {}
    added = 0
    for f in await catalog_files(user["id"], rec):
        if await db.documents.find_one({"owner": user["id"], "storage_path": f["storage_path"], "client_name": rec.get("client_name")}):
            continue
        await db.documents.insert_one(_new(user, {"client_id": client.get("id", ""), "client_name": rec.get("client_name", ""),
            "kind": "Catalog", "doc_type": f"{f['kind']} — {f['model']}", "storage_path": f["storage_path"],
            "original_filename": f.get("original_filename"), "content_type": f.get("content_type"), "size": f.get("size"), "pros_ref": item_id}))
        added += 1
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

async def get_client(owner: str, rec: dict) -> dict:
    c = None
    if rec.get("client_id"):
        c = await db.clients.find_one({"owner": owner, "id": rec["client_id"]}, {"_id": 0})
    if not c and rec.get("client_name"):
        c = await db.clients.find_one({"owner": owner, "name": rec["client_name"]}, {"_id": 0})
    return c or {}

async def dossier_ctx(owner: str, item_id: str):
    rec = await db.prosumator.find_one({"id": item_id, "owner": owner}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
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
    return s, warns

@api_router.post("/dossier/{item_id}/finalize")
async def dossier_finalize(item_id: str, user: dict = Depends(get_current_user)):
    rec = await db.prosumator.find_one({"id": item_id, "owner": user["id"]}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
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
    res = await db.prosumator.update_one({"id": item_id, "owner": user["id"]}, {"$unset": {"snapshot": ""}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
    await audit(user, "redeschidere", "prosumator", item_id, ["snapshot"])
    return {"ok": True}

@api_router.get("/dossier/{item_id}")
async def dossier_info(item_id: str, user: dict = Depends(get_current_user)):
    rec, client, _, info = await dossier_ctx(user["id"], item_id)
    return {**info, "client_id": client.get("id"), "client_kind": client.get("kind"), "statuses": OPIS.STATUSES}

@api_router.put("/dossier/{item_id}/item/{key}")
async def dossier_item(item_id: str, key: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    rec = await db.prosumator.find_one({"id": item_id, "owner": user["id"]}, {"_id": 0, "opis": 1})
    if rec is None:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
    _, _, _, info = await dossier_ctx(user["id"], item_id)
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
    rec, client, settings, info = await dossier_ctx(user["id"], item_id)
    p = next((x for x in info["positions"] if x["key"] == key), None)
    if key == "opis":
        p = {"source": "generat", "docs": ["declaratie_autenticitate"], "key": "opis"}
    if not p:
        raise HTTPException(status_code=404, detail="Poziție inexistentă")
    name = f"{key}_{(client.get('name') or rec.get('client_name') or 'dosar').replace(' ', '_')}"
    if fmt == "docx":
        if key in ("schema", "fisa_tehnica"):
            raise HTTPException(status_code=400, detail="Schema și fișa tehnică se exportă doar în PDF (vectorial)")
        if p["source"] != "generat":
            raise HTTPException(status_code=400, detail="Export Word doar pentru documentele generate")
        docx = docgen.render_docx(p["docs"], rec, settings, client, info["titles"])
        return Response(content=docx, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": f'attachment; filename="{name}.docx"'})
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
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{name}.pdf"'})

@api_router.get("/dossier/{item_id}/export")
async def dossier_export(item_id: str, authorization: str = Header(None), auth: str = Query(None)):
    user = await user_from_token(authorization, auth)
    rec, client, settings, info = await dossier_ctx(user["id"], item_id)
    pdf = await OPIS.export_bundle(info, rec, client, settings, get_object, logger)
    name = f"DOSAR_{(client.get('name') or rec.get('client_name') or 'prosumator').replace(' ', '_')}{'_CIORNA' if not info['complete'] else ''}.pdf"
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{name}"'})

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
    out = {k: r.get(k) for k in ("id", "group_id", "dossier_id", "client_name", "pos_key", "doc_title", "signer_name", "signer_email",
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
    b = await request.json()
    did, keys, signers = b.get("dossier_id"), b.get("pos_keys") or [], b.get("signers") or []
    days = parse_days(b.get("expires_days"))
    if not keys or not signers:
        raise HTTPException(status_code=400, detail="Alege documentele și semnatarii")
    for s in signers:
        if not (s.get("name") or "").strip() or "@" not in (s.get("email") or ""):
            raise HTTPException(status_code=400, detail="Fiecare semnatar are nevoie de nume și e-mail valid (pentru codul de verificare)")
    return await create_sign_requests(user, did, keys, signers, days)

async def create_sign_requests(user, did, keys, signers, days):
    rec, client, settings, info = await dossier_ctx(user["id"], did)
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
                            "history": [hist("Cerere creată", None, f"de {user.get('email')}; link valabil până la {exp[:16]} UTC")]})
            await db.sign_requests.insert_one(dict(r))
            out.append({**sign_public(r), "token": t})
        await db.prosumator.update_one({"id": did, "owner": user["id"]}, {"$set": {f"opis.{k}.status": "necesită semnătură"}})
    await audit(user, "cerere semnare", "prosumator", did, keys)
    return out

@api_router.get("/sign/requests")
async def sign_list(dossier_id: Optional[str] = None, client_name: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {"owner": user["id"]}
    if dossier_id:
        q["dossier_id"] = dossier_id
    if client_name:
        q["client_name"] = client_name
    return [sign_public(r) for r in await db.sign_requests.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)]

async def sign_own(user, rid):
    r = await db.sign_requests.find_one({"id": rid, "owner": user["id"]}, {"_id": 0})
    if not r:
        raise HTTPException(status_code=404, detail="Cerere inexistentă")
    return r

@api_router.post("/sign/requests/{rid}/sent")
async def sign_mark_sent(rid: str, request: Request, user: dict = Depends(get_current_user)):
    r = await sign_own(user, rid)
    ch = ((await request.json()).get("channel") or "copiat")[:30]
    upd = {"$push": {"history": hist("Link trimis", None, f"canal: {ch}; de {user.get('email')}")}}
    if sign_status(r) == "De trimis":
        upd["$set"] = {"status": "Link trimis"}
    await db.sign_requests.update_one({"id": rid}, upd)
    return {"ok": True}

@api_router.post("/sign/requests/{rid}/new-link")
async def sign_new_link(rid: str, request: Request, user: dict = Depends(get_current_user)):
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
    return Response(content=data, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{kind}_{r["pos_key"]}.pdf"'})

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
    await send_email(to=r["signer_email"], subject=f"Cod de semnare — {r['doc_title'][:60]}", html=html)
    await db.sign_requests.update_one({"id": r["id"]}, {"$set": {"otp_hash": sha(f"{r['id']}:{code}".encode()), "otp_exp": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
                                                                 "otp_last": now_iso(), "otp_attempts": 0}, "$inc": {"otp_sends": 1},
                                                        "$push": {"history": hist("Cod de verificare trimis", client_meta(request), f"către {mask(r['signer_email'])}")}})
    return {"ok": True, "email_masked": mask(r["signer_email"])}

def evidence_page(r: dict, sig_png: bytes, meta: dict, declared: str, signed_at: str, owner_company: str) -> bytes:
    buf = io.BytesIO()
    c = rlc.Canvas(buf, pagesize=RA4)
    W, H = RA4
    y = H - 60
    c.setFont("LSB", 14); c.drawString(50, y, "FIȘĂ DE EVIDENȚĂ A SEMNĂRII ELECTRONICE")
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
    for pg in PdfReader(io.BytesIO(stamp_pages(base, "Semnat electronic (semnătură simplă) de: " + ", ".join(f"{x['signer_name']} {x['signed_at'][:16]} UTC" for x in signed) + f" · SHA-256 original {reqs[0]['doc_sha256'][:16]}…"))).pages:
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
    await db.sign_requests.update_many({"owner": owner, "group_id": gid}, {"$set": {"signed_file": f, "signed_sha256": sha(final)}})
    if len(signed) == len(reqs):
        await db.prosumator.update_one({"id": reqs[0]["dossier_id"], "owner": owner},
                                       {"$set": {f"opis.{reqs[0]['pos_key']}.upload": f, f"opis.{reqs[0]['pos_key']}.status": "atașat"}})
        await db.documents.insert_one({"id": str(uuid.uuid4()), "owner": owner, "created_at": now_iso(), "updated_at": now_iso(),
                                       "client_name": reqs[0].get("client_name"), "kind": "Semnat electronic", "doc_type": f"{reqs[0]['doc_title']} — semnat", **f})

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

# ---------------- Startup ----------------
@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    for m in MODULES:
        await db[m].create_index("owner")
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({"id": str(uuid.uuid4()), "email": admin_email,
            "password_hash": hash_password(admin_password), "name": "Administrator",
            "role": "admin", "created_at": datetime.now(timezone.utc).isoformat()})
        logger.info("Admin seeded")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})
    try:
        init_storage()
        logger.info("Storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")

@app.on_event("shutdown")
async def shutdown():
    client.close()

app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
