# Iteration 12 — staff signature image + company stamp auto-applied on dossier PDFs; expired attestation => warning, generation allowed
import os, io, uuid, requests
from PIL import Image
from pymongo import MongoClient
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
mdb = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
tok = requests.post(f"{API}/auth/login", json={"email": "drinkdrinc@gmail.com", "password": "DEnergy2026!"}).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}
TAG = "TEST_SIG_" + uuid.uuid4().hex[:5]
b = io.BytesIO(); Image.new("RGB", (200, 80), (10, 10, 120)).save(b, "PNG")
up = requests.post(f"{API}/upload", headers=H, files={"file": ("sig.png", b.getvalue(), "image/png")}).json()
print("upload", up.get("storage_path"))
ids = []
try:
    st = requests.post(f"{API}/data/staff", headers=H, json={"name": f"{TAG} Executant", "signature": up, "signature_authorized": True,
          "auths": [{"type": "ANRE", "number": "1", "expires": "2030-01-01", "verified": True, "file": up}]}).json()
    ids.append(("staff", st["id"]))
    st2 = requests.post(f"{API}/data/staff", headers=H, json={"name": f"{TAG} Expired", "signature": up, "signature_authorized": True,
          "auths": [{"type": "ANRE", "number": "2", "expires": "2020-01-01", "verified": True, "file": up}]}).json()
    ids.append(("staff", st2["id"]))
    p = requests.post(f"{API}/import/prosumator", headers=H, json={"client_name": f"{TAG} client", "pod": uuid.uuid4().hex[:8],
          "signers": {"executant": st["id"], "verifier": st2["id"]}, "cef": {"inverters": [{"model": "X", "power_kw": 5}]}}).json()
    pid = p["id"]
    info = requests.get(f"{API}/dossier/{pid}", headers=H).json()
    print("signer_warnings:", info.get("signer_warnings"))
    for k in ("receptie", "pif", "executant"):
        r = requests.get(f"{API}/dossier/{pid}/file/{k}", headers=H)
        print(k, r.status_code, "images:", r.content.count(b"/Subtype /Image"))
    r = requests.get(f"{API}/docs/pv_receptie/{pid}", headers=H)
    print("legacy /docs/pv_receptie", r.status_code, "images:", r.content.count(b"/Subtype /Image"))
    # without executant signature -> warning
    mdb.staff.update_one({"id": st["id"]}, {"$set": {"signature_authorized": False}})
    print("warnings w/o authorized sig:", requests.get(f"{API}/dossier/{pid}", headers=H).json().get("signer_warnings"))
finally:
    for m, i in ids:
        mdb[m].delete_one({"id": i})
    for m in ("prosumator", "clients", "works", "mono", "equipment"):
        mdb[m].delete_many({"$or": [{"client_name": {"$regex": TAG}}, {"name": {"$regex": TAG}}]})
    print("cleaned")
