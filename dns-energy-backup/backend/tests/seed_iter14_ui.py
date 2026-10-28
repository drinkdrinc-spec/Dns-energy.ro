# Seed START + FULL subscribers for iter14 UI tests (delete with: python seed_iter14_ui.py clean)
import sys, requests, os
from datetime import date, timedelta
from pymongo import MongoClient

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
env = {l.split("=", 1)[0]: l.split("=", 1)[1].strip().strip('"') for l in open("/app/backend/.env") if "=" in l}
mdb = MongoClient(env["MONGO_URL"])[env["DB_NAME"]]
PF = {"client_type": "pf", "full_name": "UI Test", "address": "Str 1", "locality": "Cluj", "county": "Cluj", "country": "România", "phone": "0711111111"}
if len(sys.argv) > 1 and sys.argv[1] == "clean":
    uids = [u["id"] for u in mdb.users.find({"email": {"$regex": "^ui14_"}})]
    for m in ("clients", "prosumator", "atr", "power", "invoices", "subscriptions", "billing_profiles"):
        mdb[m].delete_many({"$or": [{"owner": {"$in": uids}}, {"tenant": {"$in": uids}}]})
    mdb.users.delete_many({"email": {"$regex": "^ui14_"}})
    mdb.atr.delete_many({"client_name": {"$regex": "UI14"}})
    print("cleaned", len(uids)); sys.exit()
adm = requests.post(f"{API}/auth/login", json={"email": "drinkdrinc@gmail.com", "password": "DEnergy2026!"}).json()["access_token"]
for k, plan in (("start", "start"), ("full", "full")):
    e = f"ui14_{k}@example.com"
    requests.post(f"{API}/auth/register", json={"email": e, "password": "Test2026!x", "name": f"UI {k}", "billing": PF})
    u = mdb.users.find_one({"email": e})
    H = {"Authorization": f"Bearer {adm}"}
    requests.put(f"{API}/admin/subscribers/{u['id']}", headers=H, json={"status": "active"})
    print(requests.post(f"{API}/admin/subscribers/{u['id']}/plan", headers=H, json={"plan": plan, "valid_until": (date.today() + timedelta(days=30)).isoformat(), "justification": "TEST"}).status_code, e)
