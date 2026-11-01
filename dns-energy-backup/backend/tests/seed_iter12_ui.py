import os as _dns_test_os
if not (_dns_test_os.environ.get("DNS_ENERGY_TEST_EMAIL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_PASSWORD") and _dns_test_os.environ.get("REACT_APP_BACKEND_URL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_ALLOW_MUTATION") == "1"):
    raise SystemExit("Set staging-only DNS_ENERGY_TEST_* credentials, REACT_APP_BACKEND_URL and DNS_ENERGY_TEST_ALLOW_MUTATION=1 before running this helper.")

# Iteration 12 UI seed: subscriber with START plan (ui12_start) and one without plan (ui12_none). Cleanup: python seed_iter12_ui.py clean
import os, sys, requests
from datetime import date, timedelta
from pymongo import MongoClient
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
mdb = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
PJ = {"client_type": "pj", "company_name": "TEST UI SRL", "cui": "RO1234567", "regcom": "J12/3/2021", "hq_address": "Str. UI 1",
      "county": "Cluj", "locality": "Cluj-Napoca", "country": "România", "rep_name": "UI Tester", "billing_email": "ui12@example.com", "phone": "0700000001"}
EM = {"start": "test_ui12_start@example.com", "none": "test_ui12_none@example.com"}
if len(sys.argv) > 1 and sys.argv[1] == "clean":
    uids = [u["id"] for u in mdb.users.find({"email": {"$regex": "^test_ui12_"}}, {"id": 1})]
    for m in ("clients", "prosumator", "diu", "works", "mono", "equipment", "documents", "invoices", "subscriptions", "billing_profiles", "billing_history", "payment_transactions"):
        mdb[m].delete_many({"$or": [{"owner": {"$in": uids}}, {"tenant": {"$in": uids}}]})
    mdb.users.delete_many({"email": {"$regex": "^test_ui12_"}})
    print("cleaned", uids); sys.exit()
adm = {"Authorization": "Bearer " + requests.post(f"{API}/auth/login", json={"email": _dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"], "password": _dns_test_os.environ["DNS_ENERGY_TEST_PASSWORD"]}).json()["access_token"]}
for k, e in EM.items():
    r = requests.post(f"{API}/auth/register", json={"email": e, "password": "TestPass123!", "name": f"UI {k}", "billing": PJ})
    print(k, r.status_code, r.text[:80])
    uid = mdb.users.find_one({"email": e})["id"]
    requests.put(f"{API}/admin/subscribers/{uid}", headers=adm, json={"status": "active"})
    if k == "start":
        print(requests.post(f"{API}/admin/subscribers/{uid}/plan", headers=adm, json={"plan": "start", "valid_until": (date.today() + timedelta(days=30)).isoformat(), "justification": "UI test"}).text)
