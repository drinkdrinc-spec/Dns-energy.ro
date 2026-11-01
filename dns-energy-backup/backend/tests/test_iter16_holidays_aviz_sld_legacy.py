import os as _dns_test_os
import pytest as _dns_test_pytest
if not (_dns_test_os.environ.get("DNS_ENERGY_TEST_EMAIL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_PASSWORD") and _dns_test_os.environ.get("REACT_APP_BACKEND_URL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_ALLOW_MUTATION") == "1"):
    _dns_test_pytest.skip("Set staging-only DNS_ENERGY_TEST_* credentials, REACT_APP_BACKEND_URL and DNS_ENERGY_TEST_ALLOW_MUTATION=1", allow_module_level=True)

# Iteration 16 — RO holidays/working days, ATR deadlines panel API, aviz upload, SLD legacy (from_legacy) + multi-inverter SLD
import os, io, copy, uuid
from datetime import date, timedelta
import pytest, requests
from pymongo import MongoClient
from pypdf import PdfReader

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = (_dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"], _dns_test_os.environ["DNS_ENERGY_TEST_PASSWORD"])
PWD = "TestPass123!"
TAG = f"test_i16_{uuid.uuid4().hex[:6]}"
REAL = ("ZOLTAN ANTAL", "DRINC EUGEN", "ANDREI-LAVINIU HERING", "Test Client SRL")


def _env(key):
    for line in open("/app/backend/.env"):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


mdb = MongoClient(_env("MONGO_URL"))[_env("DB_NAME")]
S = {"atr": [], "pros": []}
PF = {"client_type": "pf", "full_name": "Maria Test", "address": "Str. PF 2", "locality": "Cluj", "county": "Cluj", "country": "România",
      "billing_email": "pf@example.com", "phone": "0711111111"}


def h(tok=None):
    return {"Authorization": f"Bearer {tok or S['admin']}"}


def login(email, pw=PWD):
    return requests.post(f"{API}/auth/login", json={"email": email, "password": pw})


def mkpdf(text="TEST"):
    from reportlab.pdfgen import canvas
    b = io.BytesIO(); c = canvas.Canvas(b); c.drawString(100, 750, text); c.showPage(); c.save()
    return b.getvalue()


def pdf_text(content, pages=None):
    r = PdfReader(io.BytesIO(content))
    ps = r.pages if pages is None else r.pages[:pages]
    return "\n".join(p.extract_text() or "" for p in ps)


def new_atr():
    r = requests.post(f"{API}/data/atr", headers=h(), json={"client_name": S["client"], "operator": "DEER — Transilvania Nord",
                                                            "kind": "Loc de consum", "is_test": True, "number_note": TAG})
    assert r.status_code == 200, r.text
    S["atr"].append(r.json()["id"])
    return r.json()["id"]


def new_pros(**kw):
    r = requests.post(f"{API}/data/prosumator", headers=h(), json={"client_name": S["client"], "is_test": True, "number_note": TAG, **kw})
    assert r.status_code == 200, r.text
    S["pros"].append(r.json()["id"])
    return r.json()["id"]


@pytest.fixture(scope="module", autouse=True)
def setup_and_cleanup():
    r = login(*ADMIN)
    assert r.status_code == 200, r.text
    S["admin"] = r.json()["access_token"]
    clients = requests.get(f"{API}/data/clients", headers=h()).json()
    S["client"] = next((c["name"] for c in clients if c.get("name") == "Test Client SRL"), clients[0]["name"])
    S["extra_orig"] = (mdb.calendar_config.find_one({"id": "main"}) or {}).get("extra") or []
    r = requests.post(f"{API}/auth/register", json={"email": f"{TAG}_s@example.com", "password": PWD, "name": "TEST s", "billing": PF})
    assert r.status_code == 200, r.text
    u = mdb.users.find_one({"email": f"{TAG}_s@example.com"})
    S["s_id"] = u["id"]
    requests.put(f"{API}/admin/subscribers/{u['id']}", headers=h(), json={"status": "active"})
    rr = requests.post(f"{API}/admin/subscribers/{u['id']}/plan", headers=h(),
                       json={"plan": "start", "valid_until": (date.today() + timedelta(days=30)).isoformat(), "justification": "TEST"})
    assert rr.status_code == 200, rr.text
    S["s"] = login(f"{TAG}_s@example.com").json()["access_token"]
    yield
    requests.put(f"{API}/calendar/extra", headers=h(), json={"extra": S["extra_orig"]})
    for i in S["atr"]:
        requests.delete(f"{API}/data/atr/{i}", headers=h())
    for i in S["pros"]:
        requests.delete(f"{API}/data/prosumator/{i}", headers=h())
    mdb.reminders.delete_many({"id": {"$regex": "|".join(S["atr"]) or "^$"}})
    uid = S["s_id"]
    for m in ("clients", "atr", "power", "documents", "prosumator", "invoices", "subscriptions", "billing_profiles", "billing_history", "payment_transactions"):
        mdb[m].delete_many({"$or": [{"owner": uid}, {"tenant": uid}]})
    mdb.users.delete_many({"email": {"$regex": f"^{TAG}"}})


# ---------- (A) holidays ----------
class TestHolidays:
    def test_2026_list(self):
        r = requests.get(f"{API}/calendar/holidays", params={"year": 2026}, headers=h())
        assert r.status_code == 200
        ds = {x["date"] for x in r.json()["legal"]}
        for d in ("2026-04-10", "2026-04-12", "2026-04-13", "2026-05-31", "2026-06-01", "2026-01-01", "2026-01-02", "2026-01-06",
                  "2026-01-07", "2026-01-24", "2026-05-01", "2026-08-15", "2026-11-30", "2026-12-01", "2026-12-25", "2026-12-26"):
            assert d in ds, d
        # 2026: A doua zi de Rusalii (Easter+50) coincides with 1 iunie -> 16 unique dates
        assert len(ds) == 16

    def _reg(self, d):
        i = new_atr()
        r = requests.post(f"{API}/atr/{i}/track", headers=h(), json={"action": "register", "reg_no": "TEST-1", "reg_date": d})
        assert r.status_code == 200, r.text
        return r.json()["check_due"]

    def test_register_workdays(self):
        requests.put(f"{API}/calendar/extra", headers=h(), json={"extra": []})
        assert self._reg("2026-11-20") == "2026-12-08"
        assert self._reg("2026-12-18") == "2027-01-05"

    def test_extra_day(self):
        r = requests.put(f"{API}/calendar/extra", headers=h(), json={"extra": [{"date": "2026-12-07", "label": "TEST punte"}]})
        assert r.status_code == 200 and r.json()["extra"][0]["date"] == "2026-12-07"
        g = requests.get(f"{API}/calendar/holidays", params={"year": 2026}, headers=h()).json()
        assert {"date": "2026-12-07", "label": "TEST punte"} in g["extra"]
        assert self._reg("2026-11-20") == "2026-12-09"
        r = requests.put(f"{API}/calendar/extra", headers=h(), json={"extra": S["extra_orig"]})
        assert r.status_code == 200
        assert self._reg("2026-11-20") == "2026-12-08"

    def test_extra_invalid_date(self):
        r = requests.put(f"{API}/calendar/extra", headers=h(), json={"extra": [{"date": "xx", "label": "a"}]})
        assert r.status_code == 400

    def test_non_platform_403(self):
        r = requests.put(f"{API}/calendar/extra", headers=h(S["s"]), json={"extra": []})
        assert r.status_code == 403
        assert requests.get(f"{API}/calendar/holidays", params={"year": 2026}, headers=h(S["s"])).status_code == 200


# ---------- (B) deadlines ----------
class TestDeadlines:
    def test_registered_in_deadlines(self):
        i = new_atr()
        reg = (date.today() - timedelta(days=1)).isoformat()
        requests.post(f"{API}/atr/{i}/track", headers=h(), json={"action": "register", "reg_no": "TEST-DL", "reg_date": reg})
        draft = new_atr()
        r = requests.get(f"{API}/atr/deadlines", headers=h())
        assert r.status_code == 200
        rows = {x["id"]: x for x in r.json()}
        assert i in rows and draft not in rows
        row = rows[i]
        assert row["status"] == "înregistrat" and row["reg_no"] == "TEST-DL" and isinstance(row["days_left"], int)
        assert row["due_kind"] == "verificare documentație"
        assert row["days_left"] == (date.fromisoformat(row["due"]) - date.today()).days

    def test_start_gets_empty(self):
        r = requests.get(f"{API}/atr/deadlines", headers=h(S["s"]))
        assert r.status_code == 200 and r.json() == []


# ---------- (C) aviz ----------
class TestAviz:
    def test_aviz_flow(self):
        i = new_atr()
        up = requests.post(f"{API}/upload", headers=h(), files={"file": ("aviz_test.pdf", mkpdf("AVIZ"), "application/pdf")})
        assert up.status_code == 200, up.text
        f = up.json()
        r = requests.post(f"{API}/atr/{i}/aviz", headers=h(), json={"file": f, "date": "2026-02-01"})
        assert r.status_code == 400
        bad = {**f, "storage_path": f["storage_path"].replace("/uploads/", "/uploads/someoneelse/")}
        r = requests.post(f"{API}/atr/{i}/aviz", headers=h(), json={"file": bad, "atr_no": "A1", "date": "2026-02-01"})
        assert r.status_code == 400
        r = requests.post(f"{API}/atr/{i}/aviz", headers=h(), json={"file": {}, "atr_no": "A1", "date": "2026-02-01"})
        assert r.status_code == 400
        r = requests.post(f"{API}/atr/{i}/aviz", headers=h(), json={"file": f, "atr_no": "TEST-ATR-77", "date": "2026-02-01"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "aviz emis"
        t = requests.get(f"{API}/atr/{i}/track", headers=h()).json()
        assert t["status"] == "aviz emis" and t["atr_no"] == "TEST-ATR-77" and t["atr_date"] == "2026-02-01"
        assert t["aviz_file"]["storage_path"] == f["storage_path"]
        dl = requests.get(f"{API}/files/{f['storage_path']}", headers=h(), params={"module": "atr"})
        assert dl.status_code == 200 and dl.content[:4] == b"%PDF"
        assert i not in {x["id"] for x in requests.get(f"{API}/atr/deadlines", headers=h()).json()}


LEG = dict(supply="Trifazat", inverter="Solis S6-EH3P12K02-NV-YD-L", inverter_kw=12, inverter_count=1, panels="Aiko 475W",
           panel_count=26, panel_w=475, battery="Ecobat 16 kWh", battery_kwh=16)


# ---------- (D) SLD legacy ----------
class TestSldLegacy:
    def test_legacy_flow(self):
        i = new_pros(**LEG)
        st = requests.get(f"{API}/sld/{i}", headers=h())
        assert st.status_code == 200, st.text
        assert st.json()["from_legacy"] is True
        p = requests.get(f"{API}/sld/{i}/pdf", headers=h())
        assert p.status_code == 200 and p.content[:4] == b"%PDF"
        txt = pdf_text(p.content, 1)
        S["legacy_txt"] = txt
        assert "Câmp PV total" in txt, txt[:1500]
        assert "Solis S6-EH3P12K02-NV-YD-L" in txt
        assert "Ecobat" in txt
        r = requests.post(f"{API}/sld/{i}/import-legacy", headers=h())
        assert r.status_code == 200, r.text
        rec = mdb.prosumator.find_one({"id": i})
        assert len(rec["cef"]["inverters"]) == 1 and rec["cef"]["inverters"][0]["strings"][0]["panels"] == 26
        assert "from_legacy" not in rec["cef"]
        assert requests.get(f"{API}/sld/{i}", headers=h()).json()["from_legacy"] is False
        assert requests.post(f"{API}/sld/{i}/import-legacy", headers=h()).status_code == 400

    def test_legacy_two_inverters(self):
        i = new_pros(**{**LEG, "inverter_count": 2, "panel_count": 27})
        assert requests.get(f"{API}/sld/{i}", headers=h()).json()["from_legacy"] is True
        p = requests.get(f"{API}/sld/{i}/pdf", headers=h())
        assert p.status_code == 200
        txt = pdf_text(p.content, 1)
        assert "-PV1.1" in txt and "-PV2.1" in txt and "TDC2" in txt, txt[:1500]
        assert txt.count("Câmp PV total (stringuri nedefinite)") >= 2 and "14×" in txt and "13×" in txt
        S["two_txt"] = txt
        requests.post(f"{API}/sld/{i}/import-legacy", headers=h())
        invs = mdb.prosumator.find_one({"id": i})["cef"]["inverters"]
        assert [x["strings"][0]["panels"] for x in invs] == [14, 13]
        assert invs[0]["battery_mode"] == "own" and invs[1]["battery_mode"] == "none"

    def test_aggregate_label_not_truncated(self):
        # aggregated PV label must show panel W and kWp (e.g. '26×475 W = 12.35 kWp'), not be cut by width-fit
        txt = S.get("legacy_txt", "")
        assert "26×475 W" in txt and "12.35 kWp" in txt, [l for l in txt.splitlines() if "Câmp" in l]

    def test_no_legacy_data_400(self):
        i = new_pros()
        assert requests.post(f"{API}/sld/{i}/import-legacy", headers=h()).status_code == 400


class TestSldMulti:
    def test_three_inverters(self):
        from sld_demo import DEMO_REC
        base = DEMO_REC["cef"]["inverters"][0]
        invs = []
        for k, name in enumerate(("TESTBRAND Alpha 10K", "TESTBRAND Beta 8K", "TESTBRAND Gamma 6K")):
            x = copy.deepcopy(base)
            x["brand_model"] = name
            x["strings"] = [{"panels": 10, "mppt": 1}, {"panels": 10, "mppt": 2}]
            if k:
                x["battery_mode"] = "none"; x["battery"] = None
            invs.append(x)
        cef = {"tmin": -10, "grid": copy.deepcopy(DEMO_REC["cef"]["grid"]), "inverters": invs, "shared_batteries": []}
        i = new_pros(cef=cef, supply="Trifazat")
        st = requests.get(f"{API}/sld/{i}", headers=h())
        assert st.status_code == 200 and st.json()["from_legacy"] is False
        p = requests.get(f"{API}/sld/{i}/pdf", headers=h())
        assert p.status_code == 200 and p.content[:4] == b"%PDF"
        txt = pdf_text(p.content)
        S["multi_txt"] = txt
        for t in ("-PV1.1", "-PV1.2", "-PV2.1", "-PV2.2", "-PV3.1", "-PV3.2", "TDC1", "TDC2", "TDC3",
                  "TESTBRAND Alpha 10K", "TESTBRAND Beta 8K", "TESTBRAND Gamma 6K"):
            assert t in txt, t


class TestRealUntouched:
    def test_real_dossiers_exist(self):
        rows = requests.get(f"{API}/data/prosumator", headers=h()).json()
        for r in rows:
            if r.get("client_name") in REAL and not r.get("is_test"):
                assert "from_legacy" not in (r.get("cef") or {})
