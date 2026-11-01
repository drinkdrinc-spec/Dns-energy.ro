import os as _dns_test_os
if not (_dns_test_os.environ.get("DNS_ENERGY_TEST_EMAIL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_PASSWORD") and _dns_test_os.environ.get("REACT_APP_BACKEND_URL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_ALLOW_MUTATION") == "1"):
    raise SystemExit("Set staging-only DNS_ENERGY_TEST_* credentials, REACT_APP_BACKEND_URL and DNS_ENERGY_TEST_ALLOW_MUTATION=1 before running this helper.")

# Iteration 19 UI setup/cleanup: admin test dossier + START subscriber (AI upgrade gate). Usage: python iter19_ui_setup.py setup|cleanup
import os, sys, json, requests
from pymongo import MongoClient

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
mdb = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
EMAIL, PWD = "sub_i19ui@example.com", "Test2026!x"
PF = {"client_type": "pf", "full_name": "Maria Test", "address": "Str. PF 2", "locality": "Cluj", "county": "Cluj", "country": "România", "billing_email": "pf@example.com", "phone": "0711111111"}
tok = requests.post(f"{API}/auth/login", json={"email": _dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"], "password": _dns_test_os.environ["DNS_ENERGY_TEST_PASSWORD"]}).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}
owner = mdb.users.find_one({"email": _dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"]})["id"]

if sys.argv[1] == "setup":
    pid = requests.post(f"{API}/test-dossier", headers=H).json()["prosumator_id"]
    requests.post(f"{API}/auth/register", json={"email": EMAIL, "password": PWD, "name": "TEST UI sub", "billing": PF})
    uid = mdb.users.find_one({"email": EMAIL})["id"]
    requests.put(f"{API}/admin/subscribers/{uid}", headers=H, json={"status": "active"})
    requests.post(f"{API}/admin/subscribers/{uid}/plan", headers=H, json={"plan": "start", "valid_until": "2026-12-31", "status": "activ", "justification": "TEST"})
    rec = mdb.prosumator.find_one({"id": pid})
    json.dump({"pid": pid, "stamp": rec.get("created_at")}, open("/tmp/i19ui.json", "w"))
    print(pid)
else:
    d = json.load(open("/tmp/i19ui.json"))
    requests.put(f"{API}/platform/modules", headers=H, json={"disabled": []})
    for c in ["clients", "prosumator", "diu", "pram", "staff", "instruments", "catalog", "documents"]:
        mdb[c].delete_many({"owner": owner, "is_test": True, "created_at": {"$gte": d["stamp"][:19]}})
    for s in mdb.ai_sessions.find({"owner": owner, "created_at": {"$gte": d["stamp"][:19]}}):
        mdb.ai_messages.delete_many({"session_id": s["id"]}); mdb.ai_sessions.delete_one({"id": s["id"]})
    u = mdb.users.find_one({"email": EMAIL})
    if u:
        mdb.subscriptions.delete_many({"tenant": u["id"]}); mdb.users.delete_many({"id": u["id"]})
    print("cleaned", mdb.platform_modules.find_one({"id": "main"}, {"_id": 0}))
