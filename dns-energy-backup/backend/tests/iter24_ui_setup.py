# Iteration 24 UI helper: create/approve a TEST subscriber for ANRE dossier UI tests; `python iter24_ui_setup.py clean` removes it
import sys
import requests
from pymongo import MongoClient

BASE = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0] + "/api"
env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
mdb = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
EMAIL = "sub_iter24ui@example.com"
if len(sys.argv) > 1 and sys.argv[1] == "clean":
    uids = [u["id"] for u in mdb.users.find({"email": {"$regex": "^sub_iter24"}})]
    print(mdb.anre_dossiers.delete_many({"$or": [{"owner": {"$in": uids}}, {"company.name": {"$regex": "^TEST"}}, {"created_by": "drinkdrinc@gmail.com"}]}).deleted_count)
    for c in ("subscriptions", "invoices", "operators", "billing_profiles", "billing_history", "payment_transactions"):
        mdb[c].delete_many({"tenant": {"$in": uids}})
    mdb.users.delete_many({"id": {"$in": uids}})
    sys.exit()
H = {"Authorization": "Bearer " + requests.post(f"{BASE}/auth/login", json={"email": "drinkdrinc@gmail.com", "password": "DEnergy2026!"}).json()["access_token"]}
if not mdb.users.find_one({"email": EMAIL}):
    r = requests.post(f"{BASE}/auth/register", json={"email": EMAIL, "password": "Test2026!x", "name": "TEST UI", "billing": {"client_type": "pj", "company_name": "TEST UI SRL", "cui": "RO12345678", "regcom": "J37/1/2020", "hq_address": "Str. Test 1", "county": "Vaslui", "locality": "Vaslui", "country": "România", "rep_name": "TEST Rep", "phone": "0700000000"}})
    print(r.status_code, r.text[:100])
uid = mdb.users.find_one({"email": EMAIL})["id"]
print(requests.put(f"{BASE}/admin/subscribers/{uid}", json={"status": "active"}, headers=H).status_code, uid)
