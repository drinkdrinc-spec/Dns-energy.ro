# Seed/cleanup for iteration 13 UI: START subscriber with a PAID proforma (credit on upgrade). Usage: python seed_iter13_ui.py [clean]
import os, sys, requests
from pymongo import MongoClient

API = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
env = {l.split("=", 1)[0]: l.split("=", 1)[1].strip().strip('"') for l in open("/app/backend/.env") if "=" in l}
mdb = MongoClient(env["MONGO_URL"])[env["DB_NAME"]]
EMAIL, PWD = "test_ui13_start@example.com", "TestPass123!"
PF = {"client_type": "pf", "full_name": "UI Test", "address": "Str. UI 1", "locality": "Cluj", "county": "Cluj", "country": "România", "phone": "0700000000"}


def clean():
    uids = [u["id"] for u in mdb.users.find({"email": EMAIL}, {"id": 1})]
    for m in ("clients", "prosumator", "power", "invoices", "subscriptions", "billing_profiles", "billing_history", "payment_transactions"):
        mdb[m].delete_many({"$or": [{"owner": {"$in": uids}}, {"tenant": {"$in": uids}}]})
    mdb.users.delete_many({"email": EMAIL})


if len(sys.argv) > 1 and sys.argv[1] == "clean":
    clean(); print("cleaned"); sys.exit()
clean()
adm = requests.post(f"{API}/auth/login", json={"email": "drinkdrinc@gmail.com", "password": "DEnergy2026!"}).json()["access_token"]
H = {"Authorization": f"Bearer {adm}"}
print(requests.post(f"{API}/auth/register", json={"email": EMAIL, "password": PWD, "name": "UI13", "billing": PF}).status_code)
uid = mdb.users.find_one({"email": EMAIL})["id"]
requests.put(f"{API}/admin/subscribers/{uid}", headers=H, json={"status": "active"})
inv = requests.post(f"{API}/admin/invoices", headers=H, json={"uid": uid, "plan": "start", "months": 1}).json()
print(requests.post(f"{API}/admin/invoices/{inv['id']}/payment", headers=H, json={"amount": inv["total"], "reference": "OP UI", "justification": "TEST"}).json())
print("seeded", EMAIL, inv["number"])
