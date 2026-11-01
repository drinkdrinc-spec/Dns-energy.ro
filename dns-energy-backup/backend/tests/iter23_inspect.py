import os as _dns_test_os
if not (_dns_test_os.environ.get("DNS_ENERGY_TEST_EMAIL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_PASSWORD") and _dns_test_os.environ.get("REACT_APP_BACKEND_URL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_ALLOW_MUTATION") == "1"):
    raise SystemExit("Set staging-only DNS_ENERGY_TEST_* credentials, REACT_APP_BACKEND_URL and DNS_ENERGY_TEST_ALLOW_MUTATION=1 before running this helper.")

# Iteration 23 helper: inspect DB state for billing/attest/from-dossier tests
from pymongo import MongoClient

env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
mdb = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
print("cfg", mdb.billing_config.find_one({"id": "main"}, {"_id": 0}))
print("plans", [(p["code"], p.get("price")) for p in mdb.plans.find({}, {"_id": 0})])
print("counters", list(mdb.counters.find({"id": {"$regex": "^(offer|contract):"}}, {"_id": 0})))
print("operators", list(mdb.operators.find({}, {"_id": 0, "tenant": 1, "status": 1, "cui": 1})))
print("offers", mdb.offers.count_documents({}), "contracts", mdb.contracts.count_documents({}))
for u in mdb.users.find({}, {"_id": 0, "id": 1, "email": 1, "created_at": 1, "tenant": 1, "status": 1, "account_type": 1}).limit(40):
    print("user", u)
plat = mdb.users.find_one({"email": _dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"]}, {"_id": 0, "id": 1})
for p in mdb.prosumator.find({"owner": plat["id"], "cef.inverters.0": {"$exists": True}}, {"_id": 0, "id": 1, "client_name": 1, "cef.inverters": 1}).limit(5):
    print("pros", p["id"], p.get("client_name"), [(i.get("brand_model"), i.get("panel_model"), i.get("panel_w"), [s.get("panels") for s in i.get("strings") or []], i.get("battery")) for i in p["cef"]["inverters"]])
print("settings plat", mdb.settings.find_one({"owner": plat["id"]}, {"_id": 0, "company": 1, "iban": 1, "bank": 1, "cui": 1}))
