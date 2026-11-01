import os as _dns_test_os
import pytest as _dns_test_pytest
if not (_dns_test_os.environ.get("DNS_ENERGY_TEST_EMAIL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_PASSWORD") and _dns_test_os.environ.get("REACT_APP_BACKEND_URL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_ALLOW_MUTATION") == "1"):
    _dns_test_pytest.skip("Set staging-only DNS_ENERGY_TEST_* credentials, REACT_APP_BACKEND_URL and DNS_ENERGY_TEST_ALLOW_MUTATION=1", allow_module_level=True)

# Iteration 13 — upgrade credit (quote/checkout), SmartBill 'neconfigurat', simple prosumator dossier PDF, Spor de putere (Anexa 1) PDFs + plan gating
import os, uuid, io, time
from datetime import date, timedelta
import pytest, requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = (_dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"], _dns_test_os.environ["DNS_ENERGY_TEST_PASSWORD"])
PWD = "TestPass123!"
TAG = f"test_i13_{uuid.uuid4().hex[:6]}"


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


def set_plan(uid, plan, until=None):
    return requests.post(f"{API}/admin/subscribers/{uid}/plan", headers=h(S["admin"]),
                         json={"plan": plan, "valid_until": until or (date.today() + timedelta(days=30)).isoformat(), "justification": "TEST"})


def pay_plan(uid, plan, months=1):
    r = requests.post(f"{API}/admin/invoices", headers=h(S["admin"]), json={"uid": uid, "plan": plan, "months": months})
    assert r.status_code == 200, r.text
    inv = r.json()
    r = requests.post(f"{API}/admin/invoices/{inv['id']}/payment", headers=h(S["admin"]),
                      json={"amount": inv["total"], "reference": "OP TEST", "justification": "TEST plata"})
    assert r.status_code == 200 and r.json()["activated"] is True, r.text
    return inv


@pytest.fixture(scope="module", autouse=True)
def setup_and_cleanup():
    r = login(*ADMIN)
    assert r.status_code == 200, r.text
    S["admin"] = r.json()["access_token"]
    S["admin_id"] = r.json()["user"]["id"]
    for k, b in (("a", PJ), ("b", PF), ("p", PF)):
        r = requests.post(f"{API}/auth/register", json={"email": em(k), "password": PWD, "name": f"TEST {k}", "billing": b})
        assert r.status_code == 200, r.text
        u = mdb.users.find_one({"email": em(k)})
        S[f"{k}_id"] = u["id"]
        requests.put(f"{API}/admin/subscribers/{u['id']}", headers=h(S["admin"]), json={"status": "active"})
        S[k] = login(em(k)).json()["access_token"]
    yield
    requests.put(f"{API}/admin/plans/pro", headers=h(S["admin"]), json={"price": 500})
    uids = [u["id"] for u in mdb.users.find({"email": {"$regex": f"^{TAG}"}}, {"id": 1})]
    for m in ("clients", "prosumator", "diu", "works", "mono", "equipment", "documents", "sign_requests", "pram", "power"):
        mdb[m].delete_many({"$or": [{"owner": {"$in": uids}}, {"created_by": {"$in": uids}}]})
    mdb.power.delete_many({"owner": S["admin_id"], "client_name": {"$regex": TAG}})
    for m in ("invoices", "subscriptions", "billing_profiles", "billing_history", "payment_transactions"):
        mdb[m].delete_many({"tenant": {"$in": uids}})
    mdb.users.delete_many({"email": {"$regex": f"^{TAG}"}})
    mdb.login_attempts.delete_many({"identifier": {"$regex": TAG}})


class TestIter13:
    # ---- credit la upgrade ----
    def test_01_start_paid_then_quotes(self):
        S["inv_start"] = pay_plan(S["a_id"], "start")
        q = requests.get(f"{API}/billing/quote?plan=pro&months=1", headers=h(S["a"]))
        assert q.status_code == 200, q.text
        q = q.json()
        assert (q["gross"], q["credit"], q["net"], q["vat"], q["total"]) == (500, 250, 250, 52.5, 302.5), q
        assert q["credit_note"] and q["smartbill"] is False
        f = requests.get(f"{API}/billing/quote?plan=full&months=1", headers=h(S["a"])).json()
        assert (f["credit"], f["net"], f["total"]) == (250, 750, 907.5), f
        r = requests.get(f"{API}/billing/quote?plan=start&months=1", headers=h(S["a"])).json()
        assert (r["credit"], r["net"], r["total"]) == (0, 250, 302.5), r  # renewal: no credit
        f3 = requests.get(f"{API}/billing/quote?plan=full&months=3", headers=h(S["a"])).json()
        assert (f3["gross"], f3["credit"], f3["net"]) == (3000, 250, 2750), f3

    def test_02_fiscal_neconfigurat(self):
        time.sleep(2)
        inv = mdb.invoices.find_one({"id": S["inv_start"]["id"]})
        assert inv["status"] == "plătită"
        assert (inv.get("fiscal") or {}).get("status") == "neconfigurat", inv.get("fiscal")
        r = requests.post(f"{API}/admin/invoices/{inv['id']}/smartbill", headers=h(S["admin"]))
        assert r.status_code == 200 and r.json()["status"] == "neconfigurat", r.text
        assert requests.get(f"{API}/billing/invoices/{inv['id']}/fiscal-pdf", headers=h(S["a"])).status_code == 404
        assert requests.get(f"{API}/billing/invoices/{inv['id']}/fiscal-pdf?auth={S['admin']}").status_code == 404
        assert requests.post(f"{API}/admin/invoices/{inv['id']}/smartbill", headers=h(S["a"])).status_code == 403

    def test_03_checkout_pro_with_credit(self):
        r = requests.post(f"{API}/billing/checkout", headers=h(S["a"]), json={"plan": "pro", "months": 1, "origin_url": BASE_URL})
        assert r.status_code == 200, r.text
        d = r.json()
        assert "checkout.stripe.com" in d["checkout_url"]
        i = d["invoice"]
        assert (i["credit"], i["net"], i["vat"], i["total"]) == (250, 250, 52.5, 302.5), i
        assert i["credit_note"]
        tx = mdb.payment_transactions.find_one({"session_id": d["session_id"]})
        assert tx["amount"] == 302.5
        import stripe
        stripe.api_key = _env("STRIPE_SECRET_KEY")
        s = stripe.checkout.Session.retrieve(d["session_id"])
        assert s.amount_total == 30250
        requests.post(f"{API}/admin/invoices/{i['id']}/cancel", headers=h(S["admin"]), json={"justification": "TEST"})

    def test_04_unpaid_pending_does_not_count_and_manual_plan_no_credit(self):
        # manual PRO -> downgrade quote must be 400 with Romanian message
        assert set_plan(S["a_id"], "pro").status_code == 200
        r = requests.get(f"{API}/billing/quote?plan=start", headers=h(S["a"]))
        assert r.status_code == 400 and "abonament inferior" in r.json()["detail"], r.text
        r = requests.post(f"{API}/billing/checkout", headers=h(S["a"]), json={"plan": "start", "months": 1, "origin_url": BASE_URL})
        assert r.status_code == 400
        f = requests.get(f"{API}/billing/quote?plan=full", headers=h(S["a"])).json()
        assert f["credit"] == 0 and "manual" in f["credit_note"], f

    def test_05_credit_covers_all_activates_directly(self):
        # sub P: pay START; temporarily price PRO 250.5 -> total < 2 lei -> activated from credit
        pay_plan(S["p_id"], "start")
        assert requests.put(f"{API}/admin/plans/pro", headers=h(S["admin"]), json={"price": 250.5}).status_code == 200
        try:
            r = requests.post(f"{API}/billing/checkout", headers=h(S["p"]), json={"plan": "pro", "months": 1, "origin_url": BASE_URL})
            assert r.status_code == 200, r.text
            d = r.json()
            assert d["session_id"] is None and "credit=1" in d["checkout_url"], d
            assert d["invoice"]["total"] < 2
            p = requests.get(f"{API}/auth/me", headers=h(S["p"])).json()["plan"]
            assert p["code"] == "pro" and p["active"] is True
            inv = mdb.invoices.find_one({"id": d["invoice"]["id"]})
            assert inv["status"] == "plătită"
        finally:
            requests.put(f"{API}/admin/plans/pro", headers=h(S["admin"]), json={"price": 500})

    # ---- dosar simplu ----
    def test_06_simple_dossier_admin(self):
        t = mdb.prosumator.find_one({"owner": S["admin_id"], "is_test": True}, sort=[("created_at", -1)])
        if not t:
            r = requests.post(f"{API}/test-dossier", headers=h(S["admin"]))
            assert r.status_code == 200
            t = {"id": r.json()["prosumator_id"]}
        S["test_pros"] = t["id"]
        r = requests.get(f"{API}/dossier/{t['id']}/simple?auth={S['admin']}")
        assert r.status_code == 200 and r.content[:4] == b"%PDF", r.text[:200]
        from pypdf import PdfReader
        S["simple_pages"] = len(PdfReader(io.BytesIO(r.content)).pages)
        full = requests.get(f"{API}/dossier/{t['id']}/export?auth={S['admin']}")
        assert full.status_code == 200
        S["full_pages"] = len(PdfReader(io.BytesIO(full.content)).pages)
        assert S["simple_pages"] >= 3 and S["simple_pages"] <= S["full_pages"], (S["simple_pages"], S["full_pages"])
        assert "SIMPLU" in r.headers.get("content-disposition", "")

    def test_07_simple_dossier_start_subscriber(self):
        set_plan(S["b_id"], "start")
        r = requests.post(f"{API}/import/prosumator", headers=h(S["b"]),
                          json={"client_name": f"{TAG} cl", "pod": uuid.uuid4().hex[:10], "cef": {"inverters": [{"model": "INV", "power_kw": 5, "brand": "TEST"}]}})
        assert r.status_code == 200, r.text
        S["b_pros"] = r.json()["id"]
        r = requests.get(f"{API}/dossier/{S['b_pros']}/simple", headers=h(S["b"]))
        assert r.status_code == 200 and r.content[:4] == b"%PDF", r.text[:300]
        assert requests.get(f"{API}/dossier/{S['b_pros']}/simple", headers=h(S["a"])).status_code == 404
        assert requests.get(f"{API}/dossier/{S['test_pros']}/simple", headers=h(S["b"])).status_code == 404
        assert requests.get(f"{API}/dossier/{S['b_pros']}/simple").status_code == 401

    # ---- spor de putere ----
    def test_08_power_admin_pdfs(self):
        body = {"client_name": f"{TAG} power", "request_kind": "existent", "pros_id": S["test_pros"], "current_supply": "monofazat",
                "approved": 6, "requested": 12, "new_supply": "trifazat", "changes": "TEST spor", "receptors": [{"name": "Pompa", "kw": 3, "qty": 1}]}
        r = requests.post(f"{API}/data/power", headers=h(S["admin"]), json=body)
        assert r.status_code == 200, r.text
        S["power"] = r.json()["id"]
        g = requests.get(f"{API}/data/power/{S['power']}", headers=h(S["admin"])).json()
        assert g["pros_id"] == S["test_pros"] and g["requested"] == 12
        a = requests.get(f"{API}/power/{S['power']}/pdf?full=0&auth={S['admin']}")
        f = requests.get(f"{API}/power/{S['power']}/pdf?full=1&auth={S['admin']}")
        assert a.status_code == 200 and a.content[:4] == b"%PDF", a.text[:300]
        assert f.status_code == 200 and f.content[:4] == b"%PDF", f.text[:300]
        from pypdf import PdfReader
        pa, pf = len(PdfReader(io.BytesIO(a.content)).pages), len(PdfReader(io.BytesIO(f.content)).pages)
        assert pf > pa and len(f.content) > len(a.content), (pa, pf)
        txt = "".join(p.extract_text() for p in PdfReader(io.BytesIO(a.content)).pages)
        assert "Anexa 1" in txt and "69/2020" in txt
        S["anexa_txt"] = txt

    def test_09_power_stale_pros_link(self):
        r = requests.post(f"{API}/data/power", headers=h(S["admin"]), json={"client_name": f"{TAG} stale", "pros_id": "nonexistent-id"})
        assert r.status_code == 200
        a = requests.get(f"{API}/power/{r.json()['id']}/pdf?full=0&auth={S['admin']}")
        assert a.status_code == 200, f"stale pros_id breaks Anexa 1: {a.status_code} {a.text[:200]}"

    def test_10_power_plan_gating(self):
        # b = START, a = PRO (manual)
        for k in ("b", "a"):
            r = requests.post(f"{API}/data/power", headers=h(S[k]), json={"client_name": f"{TAG} x"})
            assert r.status_code == 402, (k, r.text)
            pid = str(uuid.uuid4())
            mdb.power.insert_one({"id": pid, "owner": S[f"{k}_id"], "client_name": f"{TAG} own", "created_by": S[f"{k}_id"]})
            assert requests.get(f"{API}/power/{pid}/pdf?auth={S[k]}").status_code == 402
            assert requests.get(f"{API}/data/power", headers=h(S[k])).status_code == 402
        set_plan(S["a_id"], "full")
        r = requests.post(f"{API}/data/power", headers=h(S["a"]), json={"client_name": f"{TAG} full"})
        assert r.status_code == 200
        assert requests.get(f"{API}/power/{r.json()['id']}/pdf?auth={S['a']}").status_code == 200
        assert requests.get(f"{API}/power/{S['power']}/pdf?auth={S['a']}").status_code == 404
