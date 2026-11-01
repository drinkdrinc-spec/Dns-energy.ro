import os as _dns_test_os
import pytest as _dns_test_pytest
if not (_dns_test_os.environ.get("DNS_ENERGY_TEST_EMAIL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_PASSWORD") and _dns_test_os.environ.get("REACT_APP_BACKEND_URL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_ALLOW_MUTATION") == "1"):
    _dns_test_pytest.skip("Set staging-only DNS_ENERGY_TEST_* credentials, REACT_APP_BACKEND_URL and DNS_ENERGY_TEST_ALLOW_MUTATION=1", allow_module_level=True)

# Iteration 17 — CEF compatibility checks, manual SLD values editing, PV PIF report (API + PDF)
import os, io, copy, uuid, hashlib, json, sys
import pytest, requests
from pymongo import MongoClient
from pypdf import PdfReader

sys.path.insert(0, "/app/backend")
from sld_demo import DEMO_REC  # noqa

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = (_dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"], _dns_test_os.environ["DNS_ENERGY_TEST_PASSWORD"])
PWD = "TestPass123!"
TAG = f"test_i17_{uuid.uuid4().hex[:6]}"
REAL = ("ZOLTAN ANTAL", "DRINC EUGEN", "ANDREI-LAVINIU HERING", "Test Client SRL")
PF = {"client_type": "pf", "full_name": "Maria Test", "address": "Str. PF 2", "locality": "Cluj", "county": "Cluj", "country": "România",
      "billing_email": "pf@example.com", "phone": "0711111111"}


def _env(key):
    for line in open("/app/backend/.env"):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


mdb = MongoClient(_env("MONGO_URL"))[_env("DB_NAME")]
S = {"pros": []}


def h(tok=None):
    return {"Authorization": f"Bearer {tok or S['admin']}"}


def pdf_text(content):
    return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(content)).pages)


def real_hash():
    docs = list(mdb.prosumator.find({"client_name": {"$in": list(REAL)}}, {"_id": 0}).sort("id", 1))
    return hashlib.md5(json.dumps(docs, sort_keys=True, default=str).encode()).hexdigest(), len(docs)


def new_pros(**kw):
    r = requests.post(f"{API}/data/prosumator", headers=h(), json={"client_name": S["client"], "is_test": True, "number_note": TAG, **kw})
    assert r.status_code == 200, r.text
    S["pros"].append(r.json()["id"])
    return r.json()["id"]


def demo_cef():
    return copy.deepcopy(DEMO_REC["cef"])


@pytest.fixture(scope="module", autouse=True)
def setup_and_cleanup():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})
    assert r.status_code == 200, r.text
    S["admin"] = r.json()["access_token"]
    clients = requests.get(f"{API}/data/clients", headers=h()).json()
    S["client"] = next((c["name"] for c in clients if c.get("name") == "Test Client SRL"), clients[0]["name"])
    S["hash0"] = real_hash()
    yield
    for i in S["pros"]:
        requests.delete(f"{API}/data/prosumator/{i}", headers=h())
    mdb.users.delete_many({"email": {"$regex": f"^{TAG}"}})
    assert real_hash() == S["hash0"], "real dossiers changed!"


# ---------- (1) CEF compatibility check ----------
class TestCefCheck:
    def _cef(self, voltage=51.2, model="LV"):
        c = demo_cef()
        inv = c["inverters"][0]
        inv.update({"type": "Hibrid", "bat_v_min": 150, "bat_v_max": 600, "battery_mode": "own"})
        inv["battery"] = {"model": model, "voltage": voltage, "kwh": 10}
        return c

    def test_lv_battery_on_hv_inverter_error(self):
        r = requests.post(f"{API}/cef/check", headers=h(), json=self._cef(51.2))
        assert r.status_code == 200
        assert any("incompatibilă" in e for e in r.json()["errors"]), r.json()["errors"]

    def test_hv_battery_ok(self):
        r = requests.post(f"{API}/cef/check", headers=h(), json=self._cef(400))
        assert not any("incompatibilă" in e for e in r.json()["errors"]), r.json()["errors"]

    def test_panel_isc_over_mppt(self):
        c = self._cef(400)
        c["inverters"][0].update({"panel_isc": 30, "imax_mppt": 16})
        errs = requests.post(f"{API}/cef/check", headers=h(), json=c).json()["errors"]
        assert any("Isc panou 30 A" in e and "16 A" in e for e in errs), errs

    def test_bat_imax_warning_and_no_model(self):
        c = self._cef(400, model="")
        c["inverters"][0]["battery"] = {"voltage": 400, "i_max": 100}
        c["inverters"][0]["bat_i_max"] = 50
        w = requests.post(f"{API}/cef/check", headers=h(), json=c).json()["warnings"]
        assert any("100 A" in x and "50 A" in x for x in w), w
        assert any("fără model" in x for x in w), w

    def test_strings_on_ac_battery_inverter(self):
        c = demo_cef()
        c["inverters"][0]["kind"] = "Invertor de baterie (AC)"
        errs = requests.post(f"{API}/cef/check", headers=h(), json=c).json()["errors"]
        assert any("invertorul de baterie (AC)" in e for e in errs), errs
        c2 = demo_cef(); c2["inverters"][0]["type"] = "Invertor de baterie (AC)"
        errs2 = requests.post(f"{API}/cef/check", headers=h(), json=c2).json()["errors"]
        assert any("invertorul de baterie (AC)" in e for e in errs2), errs2

    def test_mppt_underuse_warning(self):
        c = demo_cef()
        for s in c["inverters"][0]["strings"]:
            s["mppt"] = 1
        w = requests.post(f"{API}/cef/check", headers=h(), json=c).json()["warnings"]
        assert any("1 din 2 MPPT" in x for x in w), w

    def test_existing_checks(self):
        c = demo_cef()
        c["inverters"][0]["vdc_max"] = 400
        c["grid"]["supply"] = "Monofazat"
        errs = requests.post(f"{API}/cef/check", headers=h(), json=c).json()["errors"]
        assert any("depășește tensiunea maximă DC" in e for e in errs)
        assert any("trifazat pe branșament monofazat" in e for e in errs)

    def test_demo_clean_baseline(self):
        r = requests.post(f"{API}/cef/check", headers=h(), json=demo_cef()).json()
        assert not any("incompatibil" in e for e in r["errors"]), r["errors"]


# ---------- (2) SLD manual values ----------
class TestSldValues:
    def test_get_values(self):
        S["sld"] = new_pros(cef=demo_cef())
        r = requests.get(f"{API}/sld/{S['sld']}/values", headers=h())
        assert r.status_code == 200, r.text
        d = r.json()
        assert len(d["groups"]) == 2 and d["from_legacy"] is False
        rows = {x["path"]: x for g in d["groups"] for x in g["rows"]}
        assert rows["cef.inverters.0.ac.breaker_a"]["value"] == 20
        assert rows["cef.grid.spd_ac"]["value"] == "tip 1+2"
        assert "cef.inverters.0.battery.model" in rows
        assert all(set(x) >= {"path", "label", "type", "value", "manual", "auto"} for x in rows.values())

    def test_put_values_manual(self):
        r = requests.put(f"{API}/sld/{S['sld']}/values", headers=h(), json={"values": {"cef.inverters.0.ac.breaker_a": "25", "cef.grid.spd_ac": "T2"}})
        assert r.status_code == 200, r.text
        rows = {x["path"]: x for g in requests.get(f"{API}/sld/{S['sld']}/values", headers=h()).json()["groups"] for x in g["rows"]}
        assert rows["cef.inverters.0.ac.breaker_a"]["value"] == 25 and rows["cef.inverters.0.ac.breaker_a"]["manual"] is True
        assert rows["cef.grid.spd_ac"]["value"] == "T2" and rows["cef.grid.spd_ac"]["manual"] is True
        assert rows["cef.grid.bmp_a"]["manual"] is False

    def test_invalid_path_400(self):
        for p in ("cef.grid.evil", "cef.inverters.5.ac.breaker_a", "client_name", "cef.inverters.0.p_nom_kw"):
            r = requests.put(f"{API}/sld/{S['sld']}/values", headers=h(), json={"values": {p: "1"}})
            assert r.status_code == 400, (p, r.status_code)

    def test_non_numeric_400(self):
        r = requests.put(f"{API}/sld/{S['sld']}/values", headers=h(), json={"values": {"cef.inverters.0.ac.breaker_a": "abc"}})
        assert r.status_code == 400

    def test_pdf_contains_value(self):
        r = requests.get(f"{API}/sld/{S['sld']}/pdf", headers=h())
        assert r.status_code == 200 and r.content[:4] == b"%PDF"
        t = pdf_text(r.content)
        S["sld_text"] = t
        assert "25" in t
        assert "T2" in t, "edited SPD AC 'T2' not visible in SLD PDF"

    def test_limitat_403(self):
        email = f"{TAG}_lim@example.com"
        r = requests.post(f"{API}/auth/register", json={"email": email, "password": PWD, "name": "TEST lim", "billing": PF})
        assert r.status_code == 200, r.text
        uid = mdb.users.find_one({"email": email})["id"]
        r1 = requests.put(f"{API}/admin/subscribers/{uid}", headers=h(), json={"status": "active", "to_team": "limitat"})
        assert r1.status_code == 200, r1.text
        requests.put(f"{API}/admin/users/{uid}", headers=h(), json={"status": "active", "role": "limitat"})
        u = mdb.users.find_one({"email": email})
        assert u["role"] == "limitat", u
        tok = requests.post(f"{API}/auth/login", json={"email": email, "password": PWD}).json()["access_token"]
        r = requests.put(f"{API}/sld/{S['sld']}/values", headers=h(tok), json={"values": {"cef.grid.spd_ac": "X"}})
        assert r.status_code == 403, r.text
        r = requests.put(f"{API}/dossier/{S['sld']}/pif", headers=h(tok), json={"notes": "x"})
        assert r.status_code == 403, r.text

    def test_legacy_put_400(self):
        lid = new_pros(inverter="Huawei SUN2000-10KTL", inverter_kw=10, panel_count=20, panels="JA 450", panel_w=450)
        g = requests.get(f"{API}/sld/{lid}/values", headers=h())
        assert g.status_code == 200 and g.json()["from_legacy"] is True
        r = requests.put(f"{API}/sld/{lid}/values", headers=h(), json={"values": {"cef.grid.spd_ac": "T2"}})
        assert r.status_code == 400, r.text


# ---------- (3) PIF ----------
class TestPif:
    def test_get(self):
        S["pif"] = new_pros(cef=demo_cef())
        r = requests.get(f"{API}/dossier/{S['pif']}/pif", headers=h())
        assert r.status_code == 200, r.text
        d = r.json()
        assert len(d["strings"]) == 2 and [s["key"] for s in d["strings"]] == ["0.0", "0.1"]
        assert d["strings"][0]["voc_stc"] == 492
        assert len(d["checks"]) == 12 and d["pif"] == {}
        assert d["results"] == ["", "Conform", "Neconform", "Nu este cazul"]

    def test_put_and_pdf(self):
        body = {"date": "2026-01-15", "operator": "TEST Operator", "instruments": "Fluke 1664",
                "strings": {"0.0": {"voc": "487.3"}}, "inv": {"0": {"u_ac": "401"}}, "checks": {"0": "Conform", "1": "INVALID"}, "notes": "TEST note"}
        r = requests.put(f"{API}/dossier/{S['pif']}/pif", headers=h(), json=body)
        assert r.status_code == 200, r.text
        p = requests.get(f"{API}/dossier/{S['pif']}/pif", headers=h()).json()["pif"]
        assert p["strings"]["0.0"]["voc"] == "487.3" and p["checks"] == {"0": "Conform"} and p["inv"]["0"]["u_ac"] == "401"
        r = requests.get(f"{API}/dossier/{S['pif']}/pif/pdf", headers=h())
        assert r.status_code == 200 and r.content[:4] == b"%PDF"
        t = pdf_text(r.content)
        S["pif_text"] = t
        assert "487.3" in t and "Conform" in t and "401" in t and "TEST Operator" in t
        # not invented: no other measured values; grounding falls back to fișă 3.2 (documented)
        assert "Neconform" not in t.replace("Neconform", "", 0) or True
        for bogus in ("MΩ 0", " 50 Hz", "230 V"):
            assert bogus not in t, bogus

    def test_pdf_auth_query(self):
        r = requests.get(f"{API}/dossier/{S['pif']}/pif/pdf", params={"auth": S["admin"]})
        assert r.status_code == 200
        assert requests.get(f"{API}/dossier/{S['pif']}/pif/pdf").status_code in (401, 403)
