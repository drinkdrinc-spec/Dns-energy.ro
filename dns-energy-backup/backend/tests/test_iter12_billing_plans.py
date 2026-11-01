import os as _dns_test_os
import pytest as _dns_test_pytest
if not (_dns_test_os.environ.get("DNS_ENERGY_TEST_EMAIL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_PASSWORD") and _dns_test_os.environ.get("REACT_APP_BACKEND_URL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_ALLOW_MUTATION") == "1"):
    _dns_test_pytest.skip("Set staging-only DNS_ENERGY_TEST_* credentials, REACT_APP_BACKEND_URL and DNS_ENERGY_TEST_ALLOW_MUTATION=1", allow_module_level=True)

# Iteration 12 — subscriptions (START/PRO/FULL), billing profile, Stripe checkout, admin billing, plan enforcement (402), isolation, RBAC regression
import os, uuid, io
from datetime import date, timedelta
import pytest, requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = (_dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"], _dns_test_os.environ["DNS_ENERGY_TEST_PASSWORD"])
PWD = "TestPass123!"
TAG = f"test_bill_{uuid.uuid4().hex[:6]}"


def _env(key):
    for line in open("/app/backend/.env"):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


mdb = MongoClient(_env("MONGO_URL"))[_env("DB_NAME")]
S = {}

PJ = {"client_type": "pj", "company_name": "TEST SRL", "cui": "RO12345678", "regcom": "J40/1/2020", "hq_address": "Str. Test 1",
      "county": "Ilfov", "locality": "Voluntari", "country": "România", "rep_name": "Ion Test", "billing_email": "b@example.com", "phone": "0700000000"}
PF = {"client_type": "pf", "full_name": "Maria Test", "address": "Str. PF 2", "locality": "Cluj", "county": "Cluj", "country": "România",
      "billing_email": "pf@example.com", "phone": "0711111111"}


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


def login(email, pw=PWD):
    return requests.post(f"{API}/auth/login", json={"email": email, "password": pw})


def em(k):
    return f"{TAG}_{k}@example.com"


def inv(n):
    return [{"model": f"INV-{i}", "power_kw": 5, "brand": "TEST"} for i in range(n)]


def imp(tok, name, n, pod=None):
    return requests.post(f"{API}/import/prosumator", headers=h(tok),
                         json={"client_name": name, "pod": pod or uuid.uuid4().hex[:10], "cef": {"inverters": inv(n)}})


def set_plan(uid, plan, until=None, just="TEST justificare"):
    return requests.post(f"{API}/admin/subscribers/{uid}/plan", headers=h(S["admin"]),
                         json={"plan": plan, "valid_until": until or (date.today() + timedelta(days=30)).isoformat(), "justification": just})


@pytest.fixture(scope="module", autouse=True)
def setup_and_cleanup():
    r = login(*ADMIN)
    assert r.status_code == 200, r.text
    S["admin"] = r.json()["access_token"]
    S["admin_id"] = r.json()["user"]["id"]
    yield
    requests.put(f"{API}/admin/plans/start", headers=h(S["admin"]), json={"price": 250})
    uids = [u["id"] for u in mdb.users.find({"email": {"$regex": f"^{TAG}"}}, {"id": 1})]
    for m in ("clients", "prosumator", "diu", "works", "mono", "equipment", "documents", "sign_requests", "pram"):
        mdb[m].delete_many({"$or": [{"owner": {"$in": uids}}, {"created_by": {"$in": uids}}]})
        mdb[m].delete_many({"owner": S["admin_id"], "$or": [{"client_name": {"$regex": TAG}}, {"name": {"$regex": TAG}}]})
    for m in ("invoices", "subscriptions", "billing_profiles", "billing_history", "payment_transactions"):
        mdb[m].delete_many({"tenant": {"$in": uids}})
    mdb.users.delete_many({"email": {"$regex": f"^{TAG}"}})
    mdb.login_attempts.delete_many({"identifier": {"$regex": TAG}})
    mdb.audit.delete_many({"user": {"$regex": f"^{TAG}"}})


class TestIter12Billing:
  # single class so xdist loadscope keeps shared state on one worker
    def test_01_missing_billing_fields(self):
        r = requests.post(f"{API}/auth/register", json={"email": em("x"), "password": PWD, "billing": {"client_type": "pj", "company_name": "X"}})
        assert r.status_code == 400
        d = r.json()["detail"]
        assert "incomplete" in d and "CUI/CIF" in d and "Telefon" in d, d

    def test_02_invalid_cui(self):
        r = requests.post(f"{API}/auth/register", json={"email": em("x"), "password": PWD, "billing": {**PJ, "cui": "ABCD"}})
        assert r.status_code == 400 and "CUI" in r.json()["detail"]

    def test_03_register_pending(self):
        for k, b in (("a", PJ), ("b", PF), ("c", PF)):
            r = requests.post(f"{API}/auth/register", json={"email": em(k), "password": PWD, "name": f"TEST {k}", "billing": b})
            assert r.status_code == 200, r.text
            assert r.json().get("pending") is True
        assert login(em("a")).status_code == 403

    def test_04_admin_lists_and_approves(self):
        r = requests.get(f"{API}/admin/subscribers", headers=h(S["admin"]))
        assert r.status_code == 200
        subs = {u["email"]: u for u in r.json()}
        a = subs[em("a")]
        assert a["status"] == "pending" and a["profile"]["company_name"] == "TEST SRL" and a["profile"]["cui"] == "RO12345678"
        for k in "abc":
            S[f"{k}_id"] = subs[em(k)]["id"]
            assert requests.put(f"{API}/admin/subscribers/{S[k + '_id']}", headers=h(S["admin"]), json={"status": "active"}).status_code == 200
        r = login(em("a"))
        assert r.status_code == 200
        p = r.json()["user"]["plan"]
        assert p["active"] is False and p["status"] == "fără abonament"
        S["a"] = r.json()["access_token"]
        S["b"] = login(em("b")).json()["access_token"]
        # convert c to team member limitat
        assert requests.put(f"{API}/admin/subscribers/{S['c_id']}", headers=h(S["admin"]), json={"to_team": "limitat"}).status_code == 200
        r = login(em("c"))
        assert r.status_code == 200
        S["c"] = r.json()["access_token"]
        assert r.json()["user"]["role"] == "limitat"

    def test_05_no_plan_read_only(self):
        r = requests.post(f"{API}/data/clients", headers=h(S["a"]), json={"name": f"{TAG} c"})
        assert r.status_code == 402, r.text
        assert "Abonamentul nu este activ" in r.json()["detail"]
        assert requests.get(f"{API}/data/clients", headers=h(S["a"])).status_code == 200

    # ---- TestBillingUser ----
    def test_06_plans(self):
        r = requests.get(f"{API}/billing/plans", headers=h(S["a"]))
        assert r.status_code == 200
        P = {p["code"]: p for p in r.json()["plans"]}
        assert (P["start"]["net"], P["start"]["vat"], P["start"]["total"]) == (250, 52.5, 302.5)
        assert (P["pro"]["net"], P["pro"]["vat"], P["pro"]["total"]) == (500, 105, 605)
        assert (P["full"]["net"], P["full"]["vat"], P["full"]["total"]) == (1000, 210, 1210)

    def test_07_profile_update_history(self):
        r = requests.put(f"{API}/billing/profile", headers=h(S["a"]), json={**PJ, "phone": "0799999999"})
        assert r.status_code == 200 and r.json()["phone"] == "0799999999"
        me = requests.get(f"{API}/billing/me", headers=h(S["a"])).json()
        assert me["profile"]["phone"] == "0799999999"
        assert any(x["kind"] == "date facturare" and "phone" in x["detail"] for x in me["history"])
        mb = requests.get(f"{API}/billing/me", headers=h(S["b"])).json()
        assert mb["profile"].get("full_name") == "Maria Test" and "company_name" not in mb["profile"]
        assert all("phone" not in x.get("detail", "") or x["tenant"] == S["b_id"] for x in mb["history"])

    def test_08_team_member_forbidden(self):
        assert requests.get(f"{API}/billing/me", headers=h(S["c"])).status_code == 403
        assert requests.put(f"{API}/billing/profile", headers=h(S["c"]), json=PF).status_code == 403

    def test_09_checkout(self):
        r = requests.post(f"{API}/billing/checkout", headers=h(S["a"]), json={"plan": "start", "months": 1, "origin_url": BASE_URL})
        assert r.status_code == 200, r.text
        d = r.json()
        assert "checkout.stripe.com" in d["checkout_url"]
        assert d["invoice"]["status"] == "în așteptarea plății" and d["invoice"]["total"] == 302.5
        S["sid"], S["inv_online"], S["checkout_url"] = d["session_id"], d["invoice"]["id"], d["checkout_url"]
        r = requests.get(f"{API}/billing/payment-status/{S['sid']}", headers=h(S["a"]))
        assert r.status_code == 200 and r.json()["payment_status"] != "paid"
        assert requests.get(f"{API}/auth/me", headers=h(S["a"])).json()["plan"]["active"] is False
        assert requests.get(f"{API}/billing/payment-status/{S['sid']}", headers=h(S["b"])).status_code == 404

    def test_10_checkout_validation(self):
        assert requests.post(f"{API}/billing/checkout", headers=h(S["a"]), json={"plan": "start", "months": 2, "origin_url": BASE_URL}).status_code == 400
        assert requests.post(f"{API}/billing/checkout", headers=h(S["a"]), json={"plan": "start", "months": 1, "origin_url": "http://x"}).status_code == 400
        assert requests.post(f"{API}/billing/checkout", headers=h(S["admin"]), json={"plan": "start", "months": 1, "origin_url": BASE_URL}).status_code == 400

    # ---- TestAdminPayment ----
    def test_11_manual_payment(self):
        r = requests.post(f"{API}/admin/invoices", headers=h(S["admin"]), json={"uid": S["a_id"], "plan": "start", "months": 1})
        assert r.status_code == 200, r.text
        iid = r.json()["id"]
        S["inv_manual"] = iid
        assert r.json()["total"] == 302.5
        r = requests.post(f"{API}/admin/invoices/{iid}/payment", headers=h(S["admin"]), json={"amount": 302.5, "reference": "OP 1"})
        assert r.status_code == 400
        r = requests.post(f"{API}/admin/invoices/{iid}/payment", headers=h(S["admin"]), json={"amount": 302.5, "reference": "OP 1", "justification": "TEST plata"})
        assert r.status_code == 200 and r.json()["activated"] is True, r.text
        r = requests.post(f"{API}/admin/invoices/{iid}/payment", headers=h(S["admin"]), json={"amount": 302.5, "reference": "OP 2", "justification": "TEST"})
        assert r.status_code == 400
        p = requests.get(f"{API}/auth/me", headers=h(S["a"])).json()["plan"]
        assert p["active"] is True and p["code"] == "start"

    def test_12_invoice_pdf(self):
        r = requests.get(f"{API}/billing/invoices/{S['inv_manual']}/pdf", headers=h(S["a"]))
        assert r.status_code == 200 and r.content[:4] == b"%PDF"
        from pypdf import PdfReader
        txt = "".join(p.extract_text() for p in PdfReader(io.BytesIO(r.content)).pages)
        assert "250,00" in txt and "52,50" in txt and "302,50" in txt, txt[:500]
        assert requests.get(f"{API}/billing/invoices/{S['inv_manual']}/pdf", headers=h(S["b"])).status_code == 404

    # ---- TestPlanEnforcement ----
    def test_13_start_limits(self):
        r = imp(S["a"], f"{TAG} clientA", 2)
        assert r.status_code == 402 and "invertor" in r.json()["detail"], r.text
        r = imp(S["a"], f"{TAG} clientA", 1)
        assert r.status_code == 200, r.text
        S["a_pros"] = r.json()["id"]
        S["a_client"] = r.json()["client_id"]
        r = requests.put(f"{API}/data/prosumator/{S['a_pros']}", headers=h(S["a"]), json={"cef": {"inverters": inv(2)}})
        assert r.status_code == 402, r.text
        assert requests.post(f"{API}/data/diu", headers=h(S["a"]), json={"name": "x"}).status_code == 402
        r = requests.post(f"{API}/sign/requests", headers=h(S["a"]), json={"dossier_id": S["a_pros"], "pos_keys": ["x"], "signers": [{"name": "a", "email": "a@example.com"}]})
        assert r.status_code == 402

    def test_14_pro(self):
        assert requests.post(f"{API}/admin/subscribers/{S['a_id']}/plan", headers=h(S["admin"]), json={"plan": "pro", "valid_until": "2030-01-01"}).status_code == 400
        assert set_plan(S["a_id"], "pro").status_code == 200
        assert requests.post(f"{API}/data/diu", headers=h(S["a"]), json={"name": f"{TAG} diu"}).status_code == 200
        assert imp(S["a"], f"{TAG} clientA", 2).status_code == 200
        assert requests.post(f"{API}/data/pram", headers=h(S["a"]), json={"name": "x"}).status_code == 402
        assert requests.post(f"{API}/data/mono", headers=h(S["a"]), json={"name": "x"}).status_code == 402
        r = requests.post(f"{API}/sign/requests", headers=h(S["a"]), json={"dossier_id": S["a_pros"], "pos_keys": ["x"], "signers": [{"name": "a", "email": "a@example.com"}]})
        assert r.status_code == 402

    def test_15_full(self):
        assert set_plan(S["a_id"], "full").status_code == 200
        assert requests.post(f"{API}/data/pram", headers=h(S["a"]), json={"name": f"{TAG} pram"}).status_code == 200
        assert requests.post(f"{API}/data/mono", headers=h(S["a"]), json={"name": f"{TAG} mono"}).status_code == 200
        r = requests.post(f"{API}/sign/requests", headers=h(S["a"]), json={"dossier_id": S["a_pros"], "pos_keys": [], "signers": []})
        assert r.status_code == 400  # passes plan check, fails validation

    def test_16_expiry_keeps_data(self):
        n = mdb.prosumator.count_documents({"owner": S["a_id"]})
        assert n >= 2
        assert set_plan(S["a_id"], "full", (date.today() - timedelta(days=2)).isoformat()).status_code == 200
        p = requests.get(f"{API}/auth/me", headers=h(S["a"])).json()["plan"]
        assert p["status"] == "expirat" and p["active"] is False
        assert requests.post(f"{API}/data/clients", headers=h(S["a"]), json={"name": "x"}).status_code == 402
        r = requests.get(f"{API}/data/prosumator/{S['a_pros']}", headers=h(S["a"]))
        assert r.status_code == 200
        assert mdb.prosumator.count_documents({"owner": S["a_id"]}) == n

    # ---- TestIsolationAndAdmin ----
    def test_17_isolation(self):
        assert requests.get(f"{API}/data/prosumator/{S['a_pros']}", headers=h(S["b"])).status_code == 404
        assert requests.get(f"{API}/billing/invoices/{S['inv_online']}/pdf", headers=h(S["b"])).status_code == 404
        for path in ("/admin/subscribers", "/admin/plans", "/admin/transactions", "/admin/invoices"):
            assert requests.get(f"{API}{path}", headers=h(S["b"])).status_code == 403, path
        assert requests.get(f"{API}/admin/billing/export?auth={S['b']}").status_code == 403

    def test_18_plan_editor(self):
        r = requests.put(f"{API}/admin/plans/start", headers=h(S["admin"]), json={"price": 300})
        assert r.status_code == 200 and r.json()["price"] == 300
        P = {p["code"]: p for p in requests.get(f"{API}/billing/plans", headers=h(S["a"])).json()["plans"]}
        assert P["start"]["total"] == 363.0
        requests.put(f"{API}/admin/plans/start", headers=h(S["admin"]), json={"price": 250})
        P = {p["code"]: p for p in requests.get(f"{API}/billing/plans", headers=h(S["a"])).json()["plans"]}
        assert P["start"]["total"] == 302.5
        r = requests.put(f"{API}/admin/billing-config", headers=h(S["admin"]), json={"vat_rate": 21, "expired_policy": "read_only"})
        assert r.status_code == 200 and r.json()["vat_rate"] == 21
        assert requests.put(f"{API}/admin/billing-config", headers=h(S["admin"]), json={"vat_rate": 99}).status_code == 400

    def test_19_export_csv(self):
        r = requests.get(f"{API}/admin/billing/export?auth={S['admin']}")
        assert r.status_code == 200 and "text/csv" in r.headers["content-type"]
        assert "Număr proformă" in r.text and "302.50" in r.text

    def test_20_webhook_and_cron(self):
        assert requests.post(f"{API}/stripe/webhook", data=b"{}", headers={"stripe-signature": "t=1,v1=bad"}).status_code == 400
        assert requests.post(f"{API}/cron/billing-reminders").status_code == 401
        assert requests.post(f"{API}/cron/billing-reminders", headers={"Authorization": "Bearer wrong"}).status_code == 401
        r = requests.post(f"{API}/cron/billing-reminders", headers={"Authorization": f"Bearer {_env('WEBHOOK_CRON_SECRET')}"})
        assert r.status_code == 200 and r.json()["status"] == "accepted"

    def test_21_suspend(self):
        assert requests.put(f"{API}/admin/subscribers/{S['a_id']}", headers=h(S["admin"]), json={"status": "suspended"}).status_code == 200
        assert login(em("a")).status_code == 403
        assert requests.get(f"{API}/auth/me", headers=h(S["a"])).status_code == 403
        requests.put(f"{API}/admin/subscribers/{S['a_id']}", headers=h(S["admin"]), json={"status": "active"})
        assert mdb.prosumator.count_documents({"owner": S["a_id"]}) >= 2

    # ---- TestRBACRegression ----
    def test_22_limitat_writes_forbidden(self):
        r = imp(S["admin"], f"{TAG} clientA", 1)  # same client name as subscriber A
        assert r.status_code == 200, r.text
        pid = r.json()["id"]
        assert r.json()["client_id"] != S["a_client"], "import linked another tenant's client"
        c = mdb.clients.find_one({"id": r.json()["client_id"]})
        assert c["owner"] == S["admin_id"]
        mdb.prosumator.update_one({"id": pid}, {"$set": {"assigned_to": [S["c_id"]]}})
        hc = h(S["c"])
        assert requests.get(f"{API}/data/prosumator/{pid}", headers=hc).status_code == 200
        assert requests.put(f"{API}/sld/{pid}/source", headers=hc, json={"source": "generated"}).status_code == 403
        assert requests.put(f"{API}/dossier/{pid}/item/x", headers=hc, json={"status": None}).status_code == 403
        assert requests.post(f"{API}/sign/requests", headers=hc, json={"dossier_id": pid, "pos_keys": ["x"], "signers": [{"name": "a", "email": "a@example.com"}]}).status_code == 403
        assert requests.post(f"{API}/dossier/{pid}/reopen", headers=hc).status_code == 403
        assert requests.get(f"{API}/billing/plans", headers=hc).status_code == 200
