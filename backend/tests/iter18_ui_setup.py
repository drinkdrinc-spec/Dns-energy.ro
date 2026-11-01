import os as _dns_test_os
if not (_dns_test_os.environ.get("DNS_ENERGY_TEST_EMAIL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_PASSWORD") and _dns_test_os.environ.get("REACT_APP_BACKEND_URL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_ALLOW_MUTATION") == "1"):
    raise SystemExit("Set staging-only DNS_ENERGY_TEST_* credentials, REACT_APP_BACKEND_URL and DNS_ENERGY_TEST_ALLOW_MUTATION=1 before running this helper.")

# Iteration 18 UI setup/cleanup: test dossier with completed PIF + subscriber account. Usage: python iter18_ui_setup.py setup|cleanup
import os, sys, json, requests
from pymongo import MongoClient

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
mdb = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
EMAIL, PWD = "sub_i18ui@example.com", "Test2026!x"
PF = {"client_type": "pf", "full_name": "Maria Test", "address": "Str. PF 2", "locality": "Cluj", "county": "Cluj", "country": "România", "billing_email": "pf@example.com", "phone": "0711111111"}
tok = requests.post(f"{API}/auth/login", json={"email": _dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"], "password": _dns_test_os.environ["DNS_ENERGY_TEST_PASSWORD"]}).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}
owner = mdb.users.find_one({"email": _dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"]})["id"]

if sys.argv[1] == "setup":
    pid = requests.post(f"{API}/test-dossier", headers=H).json()["prosumator_id"]
    requests.put(f"{API}/dossier/{pid}/pif", headers=H, json={"date": "2026-01-15", "strings": {"0.0": {"voc": "487.3"}}, "checks": {"0": "Conform"}})
    requests.post(f"{API}/auth/register", json={"email": EMAIL, "password": PWD, "name": "TEST UI sub", "billing": PF})
    uid = mdb.users.find_one({"email": EMAIL})["id"]
    requests.put(f"{API}/admin/subscribers/{uid}", headers=H, json={"status": "active"})
    requests.post(f"{API}/admin/subscribers/{uid}/plan", headers=H, json={"plan": "full", "valid_until": "2026-12-31", "status": "activ", "justification": "TEST"})
    rec = mdb.prosumator.find_one({"id": pid})
    json.dump({"pid": pid, "client_id": rec.get("client_id"), "stamp": rec.get("created_at")}, open("/tmp/i18ui.json", "w"))
    print(pid, rec.get("client_id"))
else:
    d = json.load(open("/tmp/i18ui.json"))
    requests.put(f"{API}/platform/modules", headers=H, json={"disabled": []})
    mdb.sign_requests.delete_many({"dossier_id": d["pid"]})
    mdb.documents.delete_many({"dossier_id": d["pid"]})
    for c in ["clients", "prosumator", "diu", "pram", "staff", "instruments", "catalog", "documents"]:
        mdb[c].delete_many({"owner": owner, "is_test": True, "created_at": {"$gte": d["stamp"][:19]}})
    u = mdb.users.find_one({"email": EMAIL})
    if u:
        for c in ("users", "subscriptions"):
            mdb[c].delete_many({"$or": [{"id": u["id"]}, {"uid": u["id"]}, {"owner": u["id"]}, {"user_id": u["id"]}]})
    print("cleaned", mdb.platform_modules.find_one({"id": "main"}, {"_id": 0}))
