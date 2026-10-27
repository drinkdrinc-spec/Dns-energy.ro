# Iteration 23 UI setup: register + approve a subscriber for UI tests (cleanup: python iter23_ui_setup.py clean)
import sys, uuid, requests
from pymongo import MongoClient

env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
mdb = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
BASE = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/") + "/api"
EMAIL = "sub_iter23ui@example.com"
if len(sys.argv) > 1 and sys.argv[1] == "clean":
    uids = [u["id"] for u in mdb.users.find({"email": {"$regex": "^sub_iter23"}})]
    for c in ("subscriptions", "invoices", "operators", "billing_profiles", "billing_history", "payment_transactions"):
        print(c, mdb[c].delete_many({"tenant": {"$in": uids}}).deleted_count)
    print("users", mdb.users.delete_many({"id": {"$in": uids}}).deleted_count)
    sys.exit()
H = {"Authorization": "Bearer " + requests.post(f"{BASE}/auth/login", json={"email": "drinkdrinc@gmail.com", "password": "DEnergy2026!"}).json()["access_token"]}
BILL = {"client_type": "pj", "company_name": "TEST UI SRL", "cui": "RO87654321", "regcom": "J37/2/2020", "hq_address": "Str. Test 2", "county": "Vaslui",
        "locality": "Vaslui", "country": "România", "rep_name": "TEST Rep", "phone": "0700000000"}
print(requests.post(f"{BASE}/auth/register", json={"email": EMAIL, "password": "Test2026!x", "name": "TEST UI", "billing": BILL}).text)
uid = mdb.users.find_one({"email": EMAIL})["id"]
print(requests.put(f"{BASE}/admin/subscribers/{uid}", json={"status": "active"}, headers=H).text[:100])
print("uid", uid)
