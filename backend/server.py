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
    doc = await db[module].find_one({"id": item_id, "owner": user["id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Înregistrare inexistentă")
    return clean(doc)

@api_router.put("/data/{module}/{item_id}")
async def update_item(module: str, item_id: str, request: Request, user: dict = Depends(get_current_user)):
    if module not in MODULES:
        raise HTTPException(status_code=404, detail="Modul inexistent")
    data = await request.json()
    data.pop("_id", None); data.pop("id", None); data.pop("owner", None); data.pop("created_at", None)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    if module == "prosumator":
        data = derive_cef(data)
        data.pop("opis", None); data.pop("snapshot", None); data.pop("snapshot_history", None)
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
        keys = [k for k in docgen.DOCS if k != ("schema" if has_cef else "schema_cef")]
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
            if role == "executant":
                s["rep"] = ""
            continue
        key = {"executant": "rep", "verifier": "verifier", "measurer": "measurer", "designer": "designer_name", "resp_tehnic": "resp_tehnic", "electrician": "electrician"}[role]
        s[key] = p.get("name")
        auth = next((a for a in p.get("auths") or [] if a.get("verified")), {})
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
    snap = {"settings": {k: v for k, v in s.items() if k not in ("owner", "_id")}, "signers": rec.get("signers") or {},
            "at": datetime.now(timezone.utc).isoformat(), "by": user.get("email")}
    await db.prosumator.update_one({"id": item_id}, {"$set": {"snapshot": snap}, "$push": {"snapshot_history": snap}})
    await audit(user, "finalizare", "prosumator", item_id, ["snapshot"])
    return {"ok": True, "at": snap["at"]}

@api_router.post("/dossier/{item_id}/reopen")
async def dossier_reopen(item_id: str, user: dict = Depends(get_current_user)):
    await db.prosumator.update_one({"id": item_id, "owner": user["id"]}, {"$unset": {"snapshot": ""}})
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
        if p["source"] != "generat":
            raise HTTPException(status_code=400, detail="Export Word doar pentru documentele generate")
        docs = [docgen.render_docx(k, rec, settings, client, info["titles"]) for k in p["docs"]]
        return Response(content=docs[0], media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
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
