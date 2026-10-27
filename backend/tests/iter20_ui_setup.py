# Iteration 20 UI setup/cleanup: admin TEST prosumer dossier + empty TEST DI-U. Usage: python iter20_ui_setup.py setup|cleanup
import os, sys, json, requests
from pymongo import MongoClient

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
mdb = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
tok = requests.post(f"{API}/auth/login", json={"email": "drinkdrinc@gmail.com", "password": "DEnergy2026!"}).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}
owner = mdb.users.find_one({"email": "drinkdrinc@gmail.com"})["id"]

if sys.argv[1] == "setup":
    pid = requests.post(f"{API}/test-dossier", headers=H).json()["prosumator_id"]
    did = requests.post(f"{API}/data/diu", headers=H, json={"number": "TEST_DIU_UI20"}).json()["id"]
    rec = mdb.prosumator.find_one({"id": pid})
    json.dump({"pid": pid, "did": did, "stamp": rec.get("created_at")}, open("/tmp/i20ui.json", "w"))
    print(json.dumps({"pid": pid, "did": did, "client": rec.get("client_name")}))
else:
    d = json.load(open("/tmp/i20ui.json"))
    mdb.diu.delete_many({"id": d["did"]})
    mdb.sign_requests.delete_many({"dossier_id": d["pid"]})
    for c in ["clients", "prosumator", "diu", "pram", "staff", "instruments", "catalog", "documents"]:
        mdb[c].delete_many({"owner": owner, "is_test": True, "created_at": {"$gte": d["stamp"][:19]}})
    print("cleaned", mdb.platform_modules.find_one({"id": "main"}, {"_id": 0}))
