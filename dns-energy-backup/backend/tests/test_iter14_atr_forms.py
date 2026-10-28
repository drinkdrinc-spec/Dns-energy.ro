# Iteration 14 — Cerere ATR module (CRUD + PDF + gating), Anexa 1 operator header, official forms registry + cron
import os, uuid, io
from datetime import date, timedelta
import pytest, requests
from pymongo import MongoClient
from pypdf import PdfReader

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = ("drinkdrinc@gmail.com", "DEnergy2026!")
PWD = "TestPass123!"
TAG = f"test_i14_{uuid.uuid4().hex[:6]}"


def _env(key):
    for line in open("/app/backend/.env"):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


mdb = MongoClient(_env("MONGO_URL"))[_env("DB_NAME")]
S = {}
PF = {"client_type": "pf", "full_name": "Maria Test", "address": "Str. PF 2", "locality": "Cluj", "county": "Cluj", "country": "România",
      "billing_email": "pf@example.com", "phone": "0711111111"}
PROD = "Loc de consum și de producere (> 27 kW)"


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


def login(email, pw=PWD):
    return requests.post(f"{API}/auth/login", json={"email": email, "password": pw})


def em(k):
    return f"{TAG}_{k}@example.com"


def set_plan(uid, plan):
    r = requests.post(f"{API}/admin/subscribers/{uid}/plan", headers=h(S["admin"]),
                      json={"plan": plan, "valid_until": (date.today() + timedelta(days=30)).isoformat(), "justification": "TEST"})
    assert r.status_code == 200, r.text


def pdf_pages(content):
    return len(PdfReader(io.BytesIO(content)).pages)


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
        set_plan(u["id"], plan)
        S[k] = login(em(k)).json()["access_token"]
    yield
    uids = [u["id"] for u in mdb.users.find({"email": {"$regex": f"^{TAG}"}}, {"id": 1})]
    for m in ("clients", "prosumator", "atr", "power", "documents"):
        mdb[m].delete_many({"$or": [{"owner": {"$in": uids}}, {"created_by": {"$in": uids}}]})
    mdb.atr.delete_many({"owner": S["admin_id"], "client_name": {"$regex": TAG}})
    mdb.power.delete_many({"owner": S["admin_id"], "client_name": {"$regex": TAG}})
    mdb.official_forms.delete_many({"url": {"$regex": TAG}})
    for m in ("invoices", "subscriptions", "billing_profiles", "billing_history", "payment_transactions"):
        mdb[m].delete_many({"tenant": {"$in": uids}})
    mdb.users.delete_many({"email": {"$regex": f"^{TAG}"}})


class TestAtr:
    def test_01_test_pros(self):
        t = mdb.prosumator.find_one({"owner": S["admin_id"], "is_test": True}, sort=[("created_at", -1)])
        if not t:
            r = requests.post(f"{API}/test-dossier", headers=h(S["admin"]))
            assert r.status_code == 200
            t = {"id": r.json()["prosumator_id"]}
        S["pros"] = t["id"]

    def test_02_crud_consum(self):
        body = {"client_name": f"{TAG} consum", "kind": "Loc de consum", "request_type": "utilizator nou definitiv", "operator": "DEER",
                "object_name": "Casa TEST", "cf_nr": "123", "cadastral_nr": "456", "supply": "Trifazat", "p_abs_kw": 10,
                "receptors": [{"name": "Pompa", "kw": 3, "notes": "TEST"}], "attachments": {}}
        r = requests.post(f"{API}/data/atr", headers=h(S["admin"]), json=body)
        assert r.status_code == 200, r.text
        S["c"] = r.json()["id"]
        g = requests.get(f"{API}/data/atr/{S['c']}", headers=h(S["admin"])).json()
        assert g["kind"] == "Loc de consum" and g["receptors"][0]["name"] == "Pompa" and g["cf_nr"] == "123"
        r = requests.put(f"{API}/data/atr/{S['c']}", headers=h(S["admin"]), json={**g, "object_name": "Casa TEST 2"})
        assert r.status_code == 200, r.text
        assert requests.get(f"{API}/data/atr/{S['c']}", headers=h(S["admin"])).json()["object_name"] == "Casa TEST 2"
        lst = requests.get(f"{API}/data/atr", headers=h(S["admin"])).json()
        assert any(x["id"] == S["c"] for x in lst)

    def test_03_pdf_consum_incomplete(self):
        a = requests.get(f"{API}/atr/{S['c']}/pdf?full=0&auth={S['admin']}")
        f = requests.get(f"{API}/atr/{S['c']}/pdf?full=1&auth={S['admin']}")
        assert a.status_code == 200 and a.content[:4] == b"%PDF", a.text[:300]
        assert f.status_code == 200 and f.content[:4] == b"%PDF", f.text[:300]
        assert "CERERE_ATR" in a.headers["content-disposition"]
        assert "_INCOMPLET" in f.headers["content-disposition"], f.headers["content-disposition"]
        txt = "".join(p.extract_text() for p in PdfReader(io.BytesIO(a.content)).pages)
        assert "CERERE" in txt and "Pompa" in txt

    def test_04_consum_complete_after_upload(self):
        att = {}
        for k in ("plan", "cf", "prop", "id", "cu"):
            r = requests.post(f"{API}/upload", headers=h(S["admin"]), files={"file": (f"{k}.pdf", mkpdf(k), "application/pdf")})
            assert r.status_code == 200, r.text
            att[k] = [r.json()]
        g = requests.get(f"{API}/data/atr/{S['c']}", headers=h(S["admin"])).json()
        assert requests.put(f"{API}/data/atr/{S['c']}", headers=h(S["admin"]), json={**g, "attachments": att}).status_code == 200
        a = requests.get(f"{API}/atr/{S['c']}/pdf?full=0&auth={S['admin']}")
        f = requests.get(f"{API}/atr/{S['c']}/pdf?full=1&auth={S['admin']}")
        assert f.status_code == 200
        assert "_INCOMPLET" not in f.headers["content-disposition"], f.headers["content-disposition"]
        assert pdf_pages(f.content) >= pdf_pages(a.content) + 5, (pdf_pages(a.content), pdf_pages(f.content))

    def test_05_producer_with_pros(self):
        body = {"client_name": f"{TAG} prod", "kind": PROD, "request_type": "dezvoltarea unui utilizator existent (spor de putere)",
                "operator": "Delgaz Grid", "pros_id": S["pros"], "pv_kw": 50, "p_evac_kw": 45, "receptors": [], "attachments": {}}
        r = requests.post(f"{API}/data/atr", headers=h(S["admin"]), json=body)
        assert r.status_code == 200, r.text
        S["pr"] = r.json()["id"]
        a = requests.get(f"{API}/atr/{S['pr']}/pdf?full=0&auth={S['admin']}")
        f = requests.get(f"{API}/atr/{S['pr']}/pdf?full=1&auth={S['admin']}")
        assert a.status_code == 200 and f.status_code == 200, (a.text[:200], f.text[:200])
        txt = "".join(p.extract_text() for p in PdfReader(io.BytesIO(a.content)).pages)
        assert "Delgaz Grid" in txt and "producere" in txt
        assert pdf_pages(f.content) > pdf_pages(a.content) and len(f.content) > len(a.content)
        assert "_INCOMPLET" in f.headers["content-disposition"]  # plan/cf/prop/id/atr_prev missing

    def test_06_producer_no_pros(self):
        r = requests.post(f"{API}/data/atr", headers=h(S["admin"]), json={"client_name": f"{TAG} prod2", "kind": PROD})
        assert r.status_code == 200
        for full in (0, 1):
            x = requests.get(f"{API}/atr/{r.json()['id']}/pdf?full={full}&auth={S['admin']}")
            assert x.status_code == 200 and x.content[:4] == b"%PDF"

    def test_07_gating(self):
        for k in ("s", "p"):
            assert requests.post(f"{API}/data/atr", headers=h(S[k]), json={"client_name": f"{TAG} x"}).status_code == 402, k
            assert requests.get(f"{API}/data/atr", headers=h(S[k])).status_code == 402, k
            pid = str(uuid.uuid4())
            mdb.atr.insert_one({"id": pid, "owner": S[f"{k}_id"], "client_name": f"{TAG} own", "created_by": S[f"{k}_id"]})
            assert requests.get(f"{API}/atr/{pid}/pdf?auth={S[k]}").status_code == 402, k
        r = requests.post(f"{API}/data/atr", headers=h(S["f"]), json={"client_name": f"{TAG} full", "kind": "Loc de consum"})
        assert r.status_code == 200, r.text
        assert requests.get(f"{API}/atr/{r.json()['id']}/pdf?full=1&auth={S['f']}").status_code == 200
        assert requests.get(f"{API}/atr/{S['c']}/pdf?auth={S['f']}").status_code == 404
        assert requests.get(f"{API}/data/atr/{S['c']}", headers=h(S["f"])).status_code == 404
        assert requests.get(f"{API}/atr/{S['c']}/pdf").status_code == 401

    def test_08_power_delgaz(self):
        r = requests.post(f"{API}/data/power", headers=h(S["admin"]), json={"client_name": f"{TAG} pw", "operator": "Delgaz Grid", "requested": 10})
        assert r.status_code == 200
        a = requests.get(f"{API}/power/{r.json()['id']}/pdf?full=0&auth={S['admin']}")
        assert a.status_code == 200 and a.content[:4] == b"%PDF"
        txt = "".join(p.extract_text() for p in PdfReader(io.BytesIO(a.content)).pages)
        assert "Delgaz Grid" in txt
        r = requests.post(f"{API}/data/power", headers=h(S["admin"]), json={"client_name": f"{TAG} pw2", "operator": "Rețele Electrice România"})
        a = requests.get(f"{API}/power/{r.json()['id']}/pdf?full=0&auth={S['admin']}")
        assert a.status_code == 200 and "Rețele Electrice" in "".join(p.extract_text() for p in PdfReader(io.BytesIO(a.content)).pages)


class TestForms:
    def test_10_list(self):
        for k in ("admin", "s"):
            r = requests.get(f"{API}/forms", headers=h(S[k]))
            assert r.status_code == 200
            seeded = [f for f in r.json() if TAG not in f["url"]]
            assert len(seeded) == 16, len(seeded)
            assert "_id" not in r.json()[0]
        S["fid0"] = r.json()[0]["id"]
        assert requests.get(f"{API}/forms").status_code == 401

    def test_11_non_platform_403(self):
        for k in ("s", "f"):
            t = h(S[k])
            assert requests.post(f"{API}/forms", headers=t, json={"operator": "X", "title": "x", "url": "https://x.ro"}).status_code == 403
            assert requests.put(f"{API}/forms/{S['fid0']}", headers=t, json={"notes": "x"}).status_code == 403
            assert requests.delete(f"{API}/forms/{S['fid0']}", headers=t).status_code == 403
            assert requests.post(f"{API}/forms/check?fid={S['fid0']}", headers=t).status_code == 403
            assert requests.post(f"{API}/forms/{S['fid0']}/confirm", headers=t, json={"version": "x"}).status_code == 403

    def test_12_admin_crud(self):
        t = h(S["admin"])
        assert requests.post(f"{API}/forms", headers=t, json={"operator": "DEER", "title": "T", "url": "ftp://bad"}).status_code == 400
        dup = requests.get(f"{API}/forms", headers=t).json()[0]["url"]
        assert requests.post(f"{API}/forms", headers=t, json={"operator": "DEER", "title": "T", "url": dup}).status_code == 400
        url = f"https://www.google.com/?q={TAG}"
        r = requests.post(f"{API}/forms", headers=t, json={"operator": "DEER", "title": f"{TAG} form", "kind": "test", "url": url}, timeout=60)
        assert r.status_code == 200, r.text
        f = r.json()
        assert f["status"] in ("valid", "neverificabil automat", "link invalid") and f["last_check"]["at"], f
        S["fid"] = f["id"]
        u = requests.put(f"{API}/forms/{S['fid']}", headers=t, json={"notes": "TEST note"})
        assert u.status_code == 200 and u.json()["notes"] == "TEST note"
        assert requests.put(f"{API}/forms/{S['fid']}", headers=t, json={"url": "bad"}).status_code == 400
        c = requests.post(f"{API}/forms/{S['fid']}/confirm", headers=t, json={"version": "V-TEST-1"})
        assert c.status_code == 200 and c.json()["status"] == "valid" and c.json()["version"] == "V-TEST-1"
        ch = requests.post(f"{API}/forms/check?fid={S['fid']}", headers=t, timeout=60)
        assert ch.status_code == 200 and len(ch.json()) == 1 and ch.json()[0]["id"] == S["fid"]
        assert requests.post(f"{API}/forms/check?fid=nonexistent", headers=t).status_code == 404
        d = requests.delete(f"{API}/forms/{S['fid']}", headers=t)
        assert d.status_code == 200
        assert not any(x["id"] == S["fid"] for x in requests.get(f"{API}/forms", headers=t).json())

    def test_13_delgaz_blocked(self):
        t = h(S["admin"])
        dg = [f for f in requests.get(f"{API}/forms", headers=t).json() if f["operator"] == "Delgaz Grid"][0]
        r = requests.post(f"{API}/forms/check?fid={dg['id']}", headers=t, timeout=60)
        assert r.status_code == 200
        print("Delgaz status:", r.json()[0]["status"], r.json()[0]["last_check"].get("http"))
        assert r.json()[0]["status"] in ("neverificabil automat", "valid", "versiune nouă detectată")

    def test_14_cron(self):
        assert requests.post(f"{API}/cron/forms-check").status_code == 401
        assert requests.post(f"{API}/cron/forms-check", headers={"Authorization": "Bearer wrong"}).status_code == 401
        rid = f"{TAG}-run"
        r = requests.post(f"{API}/cron/forms-check", headers={"Authorization": f"Bearer {_env('WEBHOOK_CRON_SECRET')}", "x-webhook-id": rid})
        assert r.status_code == 200 and r.json()["status"] == "accepted", r.text
        r = requests.post(f"{API}/cron/forms-check", headers={"Authorization": f"Bearer {_env('WEBHOOK_CRON_SECRET')}", "x-webhook-id": rid})
        assert r.json()["status"] == "duplicate"
        mdb.cron_runs.delete_many({"id": rid})
