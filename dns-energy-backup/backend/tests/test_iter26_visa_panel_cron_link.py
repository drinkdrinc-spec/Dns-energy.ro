import os as _dns_test_os
import pytest as _dns_test_pytest
if not (_dns_test_os.environ.get("DNS_ENERGY_TEST_EMAIL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_PASSWORD") and _dns_test_os.environ.get("REACT_APP_BACKEND_URL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_ALLOW_MUTATION") == "1"):
    _dns_test_pytest.skip("Set staging-only DNS_ENERGY_TEST_* credentials, REACT_APP_BACKEND_URL and DNS_ENERGY_TEST_ALLOW_MUTATION=1", allow_module_level=True)

# Iteration 26: admin visa panel API (GET /api/admin/operators/visas) + cron visa reminder with 'Comandă dosarul de vizare' link
import time
import uuid
from datetime import date, timedelta

import pytest
import requests
from pymongo import MongoClient

BASE = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0]
API = BASE.rstrip("/") + "/api"
env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
mdb = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
SECRET = env["WEBHOOK_CRON_SECRET"].strip('"')
RID = uuid.uuid4().hex[:6]
T = date.today()
CASES = {"past": -10, "soon": 30, "edge": 90, "far": 91}
TEN = {k: f"TEST_iter26_{k}_{RID}" for k in CASES}


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def H():
    return login(_dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"], _dns_test_os.environ["DNS_ENERGY_TEST_PASSWORD"])


@pytest.fixture(scope="module", autouse=True)
def seed():
    for k, d in CASES.items():
        mdb.operators.insert_one({"tenant": TEN[k], "company": f"TEST {k} SRL", "cui": f"RO26{k}{RID}", "attest_no": f"26/{k}", "contact_name": "TEST C",
                                  "contact_email": "delivered@resend.dev", "contact_phone": "0700", "status": "aprobat",
                                  "visa_date": (T + timedelta(days=d)).isoformat(), "visa_confirmed": k == "soon", "updated_at": T.isoformat()})
    yield
    mdb.operators.delete_many({"tenant": {"$in": list(TEN.values())}})
    mdb.reminders.delete_many({"id": {"$regex": f"^visa:TEST_iter26_.*_{RID}:"}})


# ---- visas list
def test_visas_list_filter_sort_days(H):
    r = requests.get(f"{API}/admin/operators/visas", headers=H)
    assert r.status_code == 200, r.text
    data = r.json()
    mine = {v["tenant"]: v for v in data if v["tenant"] in TEN.values()}
    assert TEN["past"] in mine and TEN["soon"] in mine and TEN["edge"] in mine
    assert TEN["far"] not in mine
    assert mine[TEN["past"]]["days_left"] == -10
    assert mine[TEN["soon"]]["days_left"] == 30
    assert mine[TEN["edge"]]["days_left"] == 90
    dates = [v["visa_date"] for v in data]
    assert dates == sorted(dates)
    assert all("_id" not in v and "history" not in v and "doc_path" not in v for v in data)


def test_visas_forbidden_for_subscriber(H):
    email = f"sub_iter26_{RID}@example.com"
    bill = {"client_type": "pj", "company_name": "TEST I26 SRL", "cui": "RO12345678", "regcom": "J37/1/2020", "hq_address": "Str. Test 1", "county": "Vaslui",
            "locality": "Vaslui", "country": "România", "rep_name": "TEST Rep", "phone": "0700000000"}
    assert requests.post(f"{API}/auth/register", json={"email": email, "password": "Test2026!x", "name": "TEST", "billing": bill}).status_code == 200
    uid = mdb.users.find_one({"email": email})["id"]
    try:
        requests.put(f"{API}/admin/subscribers/{uid}", json={"status": "active"}, headers=H)
        U = login(email, "Test2026!x")
        assert requests.get(f"{API}/admin/operators/visas", headers=U).status_code == 403
        assert requests.get(f"{API}/admin/operators/visas").status_code in (401, 403)
    finally:
        for c in ("subscriptions", "billing_profiles", "billing_history"):
            mdb[c].delete_many({"tenant": uid})
        mdb.users.delete_many({"id": uid})


# ---- cron visa reminder (only the confirmed 30-day operator gets reminded, once)
def test_cron_reminds_soon_once():
    hdr = {"Authorization": f"Bearer {SECRET}"}
    assert requests.post(f"{API}/cron/anre-visa", headers=hdr).json()["status"] == "accepted"
    time.sleep(8)
    o = mdb.operators.find_one({"tenant": TEN["soon"]})
    assert o.get("visa_reminded_at"), "confirmed 30-day visa was not reminded"
    key = f"visa:{TEN['soon']}:{o['visa_date']}"
    assert mdb.reminders.count_documents({"id": key}) == 1
    assert not mdb.operators.find_one({"tenant": TEN["past"]}).get("visa_reminded_at")
    assert requests.post(f"{API}/cron/anre-visa", headers=hdr).json()["status"] == "accepted"
    time.sleep(5)
    assert mdb.reminders.count_documents({"id": key}) == 1
    assert mdb.operators.find_one({"tenant": TEN["soon"]})["visa_reminded_at"] == o["visa_reminded_at"]


def test_visas_list_shows_reminded(H):
    data = requests.get(f"{API}/admin/operators/visas", headers=H).json()
    v = [x for x in data if x["tenant"] == TEN["soon"]][0]
    assert v["visa_reminded_at"]
    assert v["visa_confirmed"] is True
