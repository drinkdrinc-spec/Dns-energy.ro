import os as _dns_test_os
if not (_dns_test_os.environ.get("DNS_ENERGY_TEST_EMAIL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_PASSWORD") and _dns_test_os.environ.get("REACT_APP_BACKEND_URL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_ALLOW_MUTATION") == "1"):
    raise SystemExit("Set staging-only DNS_ENERGY_TEST_* credentials, REACT_APP_BACKEND_URL and DNS_ENERGY_TEST_ALLOW_MUTATION=1 before running this helper.")

# Setup for iteration 26 UI: active subscriber + seeded operators (past -5d, 20d, 120d) ; run with 'cleanup' arg to remove
import json
import sys
import uuid
from datetime import date, timedelta
import requests
from pymongo import MongoClient

BASE = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0]
API = BASE.rstrip("/") + "/api"
env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
mdb = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
    uids = [u["id"] for u in mdb.users.find({"email": {"$regex": "^sub_iter26ui_.*@example.com$"}})]
    mdb.anre_dossiers.delete_many({"owner": {"$in": uids}})
    for c in ("subscriptions", "invoices", "operators", "billing_profiles", "billing_history", "payment_transactions"):
        mdb[c].delete_many({"tenant": {"$in": uids}})
    mdb.operators.delete_many({"tenant": {"$regex": "^TEST_iter26ui_"}})
    mdb.users.delete_many({"id": {"$in": uids}})
    print("cleaned", len(uids))
    sys.exit()
RID = uuid.uuid4().hex[:6]
H = {"Authorization": "Bearer " + requests.post(f"{API}/auth/login", json={"email": _dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"], "password": _dns_test_os.environ["DNS_ENERGY_TEST_PASSWORD"]}).json()["access_token"]}
email = f"sub_iter26ui_{RID}@example.com"
BILL = {"client_type": "pj", "company_name": "TEST UI26 SRL", "cui": "RO12345678", "regcom": "J37/1/2020", "hq_address": "Str. Test 1", "county": "Vaslui",
        "locality": "Vaslui", "country": "România", "rep_name": "TEST Rep", "phone": "0700000000"}
assert requests.post(f"{API}/auth/register", json={"email": email, "password": "Test2026!x", "name": "TEST UI26", "billing": BILL}).status_code == 200
uid = mdb.users.find_one({"email": email})["id"]
requests.put(f"{API}/admin/subscribers/{uid}", json={"status": "active"}, headers=H)
cuis = {}
for k, d in (("past", -5), ("soon", 20), ("mid", 60), ("far", 120)):
    cui = f"RO26{k}{RID}"
    cuis[k] = cui
    mdb.operators.insert_one({"tenant": f"TEST_iter26ui_{k}_{RID}", "company": f"TEST UI26 {k} SRL", "cui": cui, "attest_no": f"26/{k}", "contact_name": "TEST C",
                              "contact_email": "delivered@resend.dev", "contact_phone": "0700", "status": "aprobat", "email": "x@example.com",
                              "visa_date": (date.today() + timedelta(days=d)).isoformat(), "visa_confirmed": k != "mid", "updated_at": "2020-01-01"})
print(json.dumps({"email": email, "uid": uid, "cuis": cuis}))
