import os as _dns_test_os
import pytest as _dns_test_pytest
if not (_dns_test_os.environ.get("DNS_ENERGY_TEST_EMAIL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_PASSWORD") and _dns_test_os.environ.get("REACT_APP_BACKEND_URL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_ALLOW_MUTATION") == "1"):
    _dns_test_pytest.skip("Set staging-only DNS_ENERGY_TEST_* credentials, REACT_APP_BACKEND_URL and DNS_ENERGY_TEST_ALLOW_MUTATION=1", allow_module_level=True)

# Iteration 15 — ATR submission by e-mail, public token link, deadline tracking, cron reminders, form alerts, operator contacts
import os, uuid, io, time
from datetime import date, timedelta, datetime, timezone
import pytest, requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = (_dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"], _dns_test_os.environ["DNS_ENERGY_TEST_PASSWORD"])
PWD = "TestPass123!"
TAG = f"test_i15_{uuid.uuid4().hex[:6]}"
ORIGIN = {"Origin": BASE_URL}


def _env(key):
    for line in open("/app/backend/.env"):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


mdb = MongoClient(_env("MONGO_URL"))[_env("DB_NAME")]
S = {}
PF = {"client_type": "pf", "full_name": "Maria Test", "address": "Str. PF 2", "locality": "Cluj", "county": "Cluj", "country": "România",
      "billing_email": "pf@example.com", "phone": "0711111111"}
FORM_ID = "615156a6-020c-4e2a-98c5-38f730ad32a2"  # DEER 'ATR consum'
POWER_FORM_ID = "cbdbae66-e1cc-4bae-838b-0e13bdb0f170"  # DEER 'prosumator / spor putere'


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


def login(email, pw=PWD):
    return requests.post(f"{API}/auth/login", json={"email": email, "password": pw})


def em(k):
    return f"{TAG}_{k}@example.com"


def mkpdf(text="TEST"):
    from reportlab.pdfgen import canvas
    b = io.BytesIO(); c = canvas.Canvas(b); c.drawString(100, 750, text); c.showPage(); c.save()
    return b.getvalue()


@pytest.fixture(scope="module", autouse=True)
def setup_and_cleanup():
    r = login(*ADMIN)
    assert r.status_code == 200, r.text
    S["admin"] = r.json()["access_token"]
    S["admin_id"] = r.json()["user"]["id"]
    for k, plan in (("s", "start"), ("p", "pro"), ("f", "full")):
        r = requests.post(f"{API}/auth/register", json={"email": em(k), "password": PWD, "name": f"TEST {k}", "billing": PF})
        assert r.status_code == 200, r.text
        u = mdb.users.find_one({"email": em(k)})
        S[f"{k}_id"] = u["id"]
        requests.put(f"{API}/admin/subscribers/{u['id']}", headers=h(S["admin"]), json={"status": "active"})
        rr = requests.post(f"{API}/admin/subscribers/{u['id']}/plan", headers=h(S["admin"]),
                           json={"plan": plan, "valid_until": (date.today() + timedelta(days=30)).isoformat(), "justification": "TEST"})
        assert rr.status_code == 200, rr.text
        S[k] = login(em(k)).json()["access_token"]
    orig = {f["id"]: f.get("status") for f in mdb.official_forms.find({"id": {"$in": [FORM_ID, POWER_FORM_ID]}})}
    yield
    for fid, st in orig.items():
        mdb.official_forms.update_one({"id": fid}, {"$set": {"status": st}})
    uids = [u["id"] for u in mdb.users.find({"email": {"$regex": f"^{TAG}"}}, {"id": 1})]
    ids = [x["id"] for x in mdb.atr.find({"client_name": {"$regex": TAG}}, {"id": 1})]
    mdb.reminders.delete_many({"id": {"$regex": "|".join(ids) or "^$"}})
    mdb.cron_runs.delete_many({"id": {"$regex": TAG}})
    for m in ("clients", "atr", "power", "documents"):
        mdb[m].delete_many({"$or": [{"owner": {"$in": uids}}, {"created_by": {"$in": uids}}]})
    mdb.atr.delete_many({"client_name": {"$regex": TAG}})
    mdb.power.delete_many({"client_name": {"$regex": TAG}})
    for m in ("invoices", "subscriptions", "billing_profiles", "billing_history", "payment_transactions"):
        mdb[m].delete_many({"tenant": {"$in": uids}})
    mdb.users.delete_many({"email": {"$regex": f"^{TAG}"}})
    requests.put(f"{API}/operator-contacts/deer", headers=h(S["admin"]), json={"email": ""})


def new_atr(tok, **kw):
    body = {"client_name": f"{TAG} {kw.pop('n', 'c')}", "kind": "Loc de consum", "request_type": "utilizator nou definitiv", "operator": "DEER",
            "object_name": "Casa TEST", "cf_nr": "1", "cadastral_nr": "2", "supply": "Trifazat", "p_abs_kw": 10, "receptors": [], "attachments": {},
            "is_test": True, **kw}
    r = requests.post(f"{API}/data/atr", headers=h(tok), json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def track(aid, tok=None, **b):
    return requests.post(f"{API}/atr/{aid}/track", headers=h(tok or S["admin"]), json=b)


class TestContacts:
    def test_01_contacts(self):
        r = requests.get(f"{API}/operator-contacts", headers=h(S["admin"]))
        assert r.status_code == 200 and {x["op"] for x in r.json()} == {"deer", "delgaz", "rer", "oltenia"}
        assert requests.put(f"{API}/operator-contacts/deer", headers=h(S["f"]), json={"email": "test@distributie-energie.ro"}).status_code == 403
        assert requests.put(f"{API}/operator-contacts/deer", headers=h(S["admin"]), json={"email": "x@gmail.com"}).status_code == 400
        assert requests.put(f"{API}/operator-contacts/deer", headers=h(S["admin"]), json={"email": "x@evil-distributie-energie.ro"}).status_code == 400
        assert requests.put(f"{API}/operator-contacts/xxx", headers=h(S["admin"]), json={"email": ""}).status_code == 400
        assert requests.put(f"{API}/operator-contacts/deer", headers=h(S["admin"]), json={"email": "test@distributie-energie.ro"}).status_code == 200
        g = {x["op"]: x for x in requests.get(f"{API}/operator-contacts", headers=h(S["admin"])).json()}
        assert g["deer"]["email"] == "test@distributie-energie.ro"
        assert requests.put(f"{API}/operator-contacts/deer", headers=h(S["admin"]), json={"email": ""}).status_code == 200
        assert requests.get(f"{API}/operator-contacts").status_code == 401


class TestSubmit:
    def test_02_incomplete_and_domain(self):
        S["a"] = new_atr(S["admin"])
        r = requests.post(f"{API}/atr/{S['a']}/submit", headers={**h(S["admin"]), **ORIGIN}, json={"to": "test@distributie-energie.ro"})
        assert r.status_code == 400 and "incomplet" in r.json()["detail"].lower(), r.text
        r = requests.post(f"{API}/atr/{S['a']}/submit", headers={**h(S["admin"]), **ORIGIN}, json={"to": "test@delgaz-grid.ro"})
        assert r.status_code == 400 and "Destinatar" in r.json()["detail"], r.text

    def test_03_complete_submit(self):
        att = {}
        for k in ("plan", "cf", "prop", "id", "cu"):
            r = requests.post(f"{API}/upload", headers=h(S["admin"]), files={"file": (f"{k}.pdf", mkpdf(k), "application/pdf")})
            assert r.status_code == 200, r.text
            att[k] = [r.json()]
        g = requests.get(f"{API}/data/atr/{S['a']}", headers=h(S["admin"])).json()
        assert requests.put(f"{API}/data/atr/{S['a']}", headers=h(S["admin"]), json={**g, "attachments": att}).status_code == 200
        # No origin -> 400
        r = requests.post(f"{API}/atr/{S['a']}/submit", headers=h(S["admin"]), json={"to": "test@distributie-energie.ro"})
        print("no-origin:", r.status_code, r.text[:200])
        assert r.status_code == 400
        r = requests.post(f"{API}/atr/{S['a']}/submit", headers={**h(S["admin"]), **ORIGIN}, json={"to": "Test@Distributie-Energie.ro"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["sent_to"] == "" and d["copy"] == "" and d["track"]["status"] == "trimis" and "token" not in d["track"]
        assert d["track"]["sent_to"] == "test@distributie-energie.ro" and d["track"]["real_sent"] is False
        g = requests.get(f"{API}/atr/{S['a']}/track", headers=h(S["admin"])).json()
        assert g["status"] == "trimis" and "token" not in g
        print("TOKEN LEAK via GET /data/atr:", "token" in (requests.get(f"{API}/data/atr/{S['a']}", headers=h(S["admin"])).json().get("atr_track") or {}))

    def test_04_public_link(self):
        tok = mdb.atr.find_one({"id": S["a"]})["atr_track"]["token"]
        r = requests.get(f"{API}/public/atr/{tok}")
        assert r.status_code == 200 and r.content[:4] == b"%PDF" and r.headers["content-type"].startswith("application/pdf")
        assert requests.get(f"{API}/public/atr/invalidtoken123").status_code == 404
        # expired
        mdb.atr.update_one({"id": S["a"]}, {"$set": {"atr_track.token_exp": "2020-01-01T00:00:00+00:00"}})
        assert requests.get(f"{API}/public/atr/{tok}").status_code == 404
        mdb.atr.update_one({"id": S["a"]}, {"$set": {"atr_track.token_exp": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()}})


class TestTrack:
    def test_05_register_complete_issued(self):
        r = track(S["a"], action="register", reg_no="", reg_date="2026-10-27")
        assert r.status_code == 400
        r = track(S["a"], action="register", reg_no="R-1", reg_date="bad")
        assert r.status_code == 400
        r = track(S["a"], action="register", reg_no="R-1", reg_date="2026-10-27")
        assert r.status_code == 200 and r.json()["check_due"] == "2026-11-10" and r.json()["status"] == "înregistrat", r.text
        r = track(S["a"], action="incomplete", note="lipsă CU")
        assert r.status_code == 200 and r.json()["status"] == "completări solicitate" and r.json()["check_due"] is None
        r = track(S["a"], action="complete", date="2026-10-28")
        assert r.status_code == 200 and r.json()["issue_due"] == "2026-11-27" and r.json()["status"] == "dosar complet"
        r = track(S["a"], action="dates", check_due="2026-12-01", issue_due="2026-12-20")
        assert r.status_code == 200 and r.json()["check_due"] == "2026-12-01" and r.json()["issue_due"] == "2026-12-20"
        r = track(S["a"], action="issued", atr_no="ATR-77", date="2026-11-20")
        assert r.status_code == 200 and r.json()["status"] == "aviz emis" and r.json()["issue_due"] is None
        assert requests.get(f"{API}/data/atr/{S['a']}", headers=h(S["admin"])).json().get("atr_ref") == "ATR-77 / 2026-11-20"
        assert track(S["a"], action="nope").status_code == 400
        assert len(r.json()["events"]) >= 6

    def test_06_custom_terms(self):
        b = new_atr(S["admin"], n="terms")
        S["b"] = b
        assert track(b, action="terms", check_days=0).status_code == 400
        assert track(b, action="terms", check_days=999).status_code == 400
        r = track(b, action="terms", check_days=5, issue_days=10, remind_days=2)
        assert r.status_code == 200 and r.json()["terms"] == {"check_days": 5, "issue_days": 10, "remind_days": 2}
        r = track(b, action="register", reg_no="R-2", reg_date="2026-10-27")  # Tue + 5 wd = Tue 2026-11-03
        assert r.json()["check_due"] == "2026-11-03", r.json()
        r = track(b, action="complete", date="2026-10-28")
        assert r.json()["issue_due"] == "2026-11-07"

    def test_07_put_keeps_track(self):
        g = requests.get(f"{API}/data/atr/{S['b']}", headers=h(S["admin"])).json()
        r = requests.put(f"{API}/data/atr/{S['b']}", headers=h(S["admin"]), json={**g, "object_name": "X", "atr_track": {"status": "hack"}})
        assert r.status_code == 200
        t = requests.get(f"{API}/atr/{S['b']}/track", headers=h(S["admin"])).json()
        assert t["status"] == "dosar complet" and t["reg_no"] == "R-2"

    def test_08_gating_and_tenant(self):
        for k in ("s", "p"):
            pid = str(uuid.uuid4())
            mdb.atr.insert_one({"id": pid, "owner": S[f"{k}_id"], "client_name": f"{TAG} own", "created_by": S[f"{k}_id"], "is_test": True})
            assert track(pid, S[k], action="terms").status_code == 402, k
            assert requests.post(f"{API}/atr/{pid}/submit", headers={**h(S[k]), **ORIGIN}, json={"to": "a@distributie-energie.ro"}).status_code == 402
            gt = requests.get(f"{API}/atr/{pid}/track", headers=h(S[k]))
            print(k, "GET track status:", gt.status_code)
        assert requests.get(f"{API}/atr/{S['a']}/track", headers=h(S["f"])).status_code == 404
        assert track(S["a"], S["f"], action="terms").status_code == 404
        assert requests.post(f"{API}/atr/{S['a']}/submit", headers={**h(S["f"]), **ORIGIN}, json={"to": "a@distributie-energie.ro"}).status_code == 404
        assert requests.get(f"{API}/atr/{S['a']}/track").status_code == 401


class TestCron:
    def test_09_cron(self):
        sec = _env("WEBHOOK_CRON_SECRET")
        assert requests.post(f"{API}/cron/atr-deadlines").status_code == 401
        assert requests.post(f"{API}/cron/atr-deadlines", headers={"Authorization": "Bearer wrong"}).status_code == 401
        c = new_atr(S["admin"], n="cron")
        S["c"] = c
        tomorrow = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
        track(c, action="register", reg_no="R-C", reg_date="2026-01-05")
        assert track(c, action="dates", check_due=tomorrow).status_code == 200
        n0 = len(requests.get(f"{API}/atr/{c}/track", headers=h(S["admin"])).json()["events"])
        r = requests.post(f"{API}/cron/atr-deadlines", headers={"Authorization": f"Bearer {sec}", "x-webhook-id": f"{TAG}-1"})
        assert r.status_code == 200 and r.json()["status"] == "accepted"
        assert requests.post(f"{API}/cron/atr-deadlines", headers={"Authorization": f"Bearer {sec}", "x-webhook-id": f"{TAG}-1"}).json()["status"] == "duplicate"
        time.sleep(6)
        ev = requests.get(f"{API}/atr/{c}/track", headers=h(S["admin"])).json()["events"]
        rem = [e for e in ev if e["by"] == "cron"]
        assert len(ev) == n0 + 1 and len(rem) == 1 and "Reamintire" in rem[0]["text"], ev[-3:]
        r = requests.post(f"{API}/cron/atr-deadlines", headers={"Authorization": f"Bearer {sec}", "x-webhook-id": f"{TAG}-2"})
        assert r.json()["status"] == "accepted"
        time.sleep(6)
        ev2 = requests.get(f"{API}/atr/{c}/track", headers=h(S["admin"])).json()["events"]
        assert len([e for e in ev2 if e["by"] == "cron"]) == 1, "duplicate reminder"


class TestAlerts:
    def test_10_alerts(self):
        r = requests.get(f"{API}/forms/alerts?operator=DEER&scope=atr", headers=h(S["admin"]))
        assert r.status_code == 200 and r.json() == [], r.text
        mdb.official_forms.update_one({"id": FORM_ID}, {"$set": {"status": "versiune nouă detectată"}})
        mdb.official_forms.update_one({"id": POWER_FORM_ID}, {"$set": {"status": "link invalid"}})
        r = requests.get(f"{API}/forms/alerts?operator=DEER&scope=atr", headers=h(S["f"])).json()
        assert [x["id"] for x in r] == [FORM_ID] and "_id" not in r[0]
        r = requests.get(f"{API}/forms/alerts?operator=Distribuție Energie Electrică România&scope=power", headers=h(S["admin"])).json()
        assert [x["id"] for x in r] == [POWER_FORM_ID]
        assert requests.get(f"{API}/forms/alerts?operator=Delgaz Grid&scope=atr", headers=h(S["admin"])).json() == []
        assert requests.get(f"{API}/forms/alerts?operator=DEER&scope=atr").status_code == 401
