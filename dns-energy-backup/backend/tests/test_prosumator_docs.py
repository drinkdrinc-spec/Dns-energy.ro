# Tests: prosumator import, document generation (PDF), sizing, settings, AI extract, regression CRUD
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
EMAIL = "drinkdrinc@gmail.com"
PASSWORD = "DEnergy2026!"
CREATED = {"prosumator": [], "clients": [], "works": [], "mono": [], "equipment": [], "documents": []}


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    if r.status_code != 200:
        pytest.skip("login failed")
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def s(token):
    ss = requests.Session()
    ss.headers.update({"Authorization": f"Bearer {token}"})
    return ss


@pytest.fixture(scope="session", autouse=True)
def cleanup(request):
    yield
    if not CREATED["prosumator"]:
        return  # this xdist worker created nothing; don't touch other workers' data
    r = requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    # delete all records referencing TEST_ prefixed names
    for m in ["prosumator", "works", "mono", "equipment", "documents", "clients"]:
        items = requests.get(f"{API}/data/{m}", headers=h, timeout=30).json()
        for it in items:
            blob = str(it)
            if "TEST_PROS" in blob or it.get("pros_ref") in CREATED["prosumator"]:
                requests.delete(f"{API}/data/{m}/{it['id']}", headers=h, timeout=30)


def _import(s, **kw):
    payload = {"client_name": "TEST_PROS Ion Popescu", "cnp": "1800101123456", "pod": "RO005E123",
               "address": "Str. Test 1, Oradea", "power": 10, "inverter": "Huawei SUN2000-10KTL",
               "inverter_kw": 10, "panels": "Jinko 450W", "panel_count": 22, "panel_w": 450,
               "battery": "Huawei LUNA 10kWh", "battery_kwh": 10, "supply": "Trifazat", "bransament_kw": 15,
               "files": [{"storage_path": "d-energy/uploads/x/test.pdf", "original_filename": "TEST_PROS.pdf",
                          "content_type": "application/pdf", "size": 10}]}
    payload.update(kw)
    r = s.post(f"{API}/import/prosumator", json=payload, timeout=60)
    if r.status_code == 200:
        CREATED["prosumator"].append(r.json()["id"])
    return r


# --- Import prosumator + sizing + doc generation ---
# NOTE: kept in ONE class: pytest.ini uses xdist --dist loadscope (one class per worker), and these tests share CREATED state.
class TestImport:
    def test_import_creates_all(self, s):
        r = _import(s)
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["number"].startswith(f"PROS-{time.localtime().tm_year}-")
        assert p["client_name"] == "TEST_PROS Ion Popescu"
        assert "_id" not in p
        g = s.get(f"{API}/data/prosumator/{p['id']}").json()
        assert g["pod"] == "RO005E123"
        clients = [c for c in s.get(f"{API}/data/clients").json() if c["name"] == "TEST_PROS Ion Popescu"]
        assert len(clients) == 1 and clients[0]["idcode"] == "1800101123456"
        works = [w for w in s.get(f"{API}/data/works").json() if w.get("client_name") == "TEST_PROS Ion Popescu"]
        assert len(works) >= 1
        mono = [m for m in s.get(f"{API}/data/mono").json() if m.get("pros_ref") == p["id"]]
        assert len(mono) == 1 and "4P" in mono[0]["fuses"]
        eq = [e for e in s.get(f"{API}/data/equipment").json() if e.get("pros_ref") == p["id"]]
        assert len(eq) == 3
        docs = [d for d in s.get(f"{API}/data/documents").json() if d.get("original_filename") == "TEST_PROS.pdf"]
        assert len(docs) >= 1

    def test_import_existing_client_not_duplicated(self, s):
        # different POD (same client+pod now returns 409)
        r = _import(s, supply="Monofazat", inverter_kw=5, bransament_kw=3, power=5, pod="RO005E999")
        assert r.status_code == 200
        clients = [c for c in s.get(f"{API}/data/clients").json() if c["name"] == "TEST_PROS Ion Popescu"]
        assert len(clients) == 1

    def test_import_missing_name(self, s):
        r = s.post(f"{API}/import/prosumator", json={"power": 5}, timeout=30)
        assert r.status_code == 400

    def test_import_unauth(self):
        r = requests.post(f"{API}/import/prosumator", json={"client_name": "x"}, timeout=30)
        assert r.status_code == 401


# --- Sizing ---
    def test_sizing_tri_vs_mono(self, s):
        tri_id, mono_id = CREATED["prosumator"][0], CREATED["prosumator"][1]
        t = s.get(f"{API}/docs/sizing/{tri_id}").json()
        m = s.get(f"{API}/docs/sizing/{mono_id}").json()
        print("TRI", t); print("MONO", m)
        assert t["tri"] is True and t["poles"] == 4 and t["phases"] == "3P+N+PE"
        assert m["tri"] is False and m["poles"] == 2 and m["phases"] == "1P+N+PE"
        assert t["warnings"] == []
        assert any("depășește puterea branșamentului" in w for w in m["warnings"])
        assert m["i_inv"] > t["i_inv"] / 2  # mono current larger per kW
        assert t["kwp"] == pytest.approx(9.9)

    def test_sizing_404(self, s):
        assert s.get(f"{API}/docs/sizing/nonexistent").status_code == 404


# --- Doc generation ---
    def test_types_and_each_pdf(self, s, token):
        types = s.get(f"{API}/docs/types").json()
        keys = [t["key"] for t in types]
        assert len(keys) >= 11
        pid = CREATED["prosumator"][0]
        for k in keys + ["all"]:
            r = requests.get(f"{API}/docs/{k}/{pid}", params={"auth": token}, timeout=60)
            assert r.status_code == 200, f"{k}: {r.status_code} {r.text[:200]}"
            assert r.headers["content-type"].startswith("application/pdf")
            assert r.content[:4] == b"%PDF"

    def test_all_bundle_pages(self, token):
        pid = CREATED["prosumator"][0]
        r = requests.get(f"{API}/docs/all/{pid}", params={"auth": token}, timeout=60)
        pages = r.content.count(b"/Type /Page") - r.content.count(b"/Type /Pages")
        print("pages:", pages)
        assert pages >= 11

    def test_mono_record_docs(self, token):
        pid = CREATED["prosumator"][1]
        r = requests.get(f"{API}/docs/schema/{pid}", params={"auth": token}, timeout=60)
        assert r.status_code == 200 and r.content[:4] == b"%PDF"

    def test_doc_errors(self, token):
        pid = CREATED["prosumator"][0]
        assert requests.get(f"{API}/docs/unknown/{pid}", params={"auth": token}).status_code == 404
        assert requests.get(f"{API}/docs/notificare/{pid}").status_code == 401
        assert requests.get(f"{API}/docs/notificare/bad-id", params={"auth": token}).status_code == 404
        assert requests.get(f"{API}/docs/notificare/{pid}", params={"auth": "garbage"}).status_code == 401

    def test_other_user_cannot_access(self, token):
        email = f"test_pros_{int(time.time())}@example.com"
        r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Test1234!"})
        assert r.status_code == 200
        t2 = r.json()["access_token"]
        pid = CREATED["prosumator"][0]
        assert requests.get(f"{API}/docs/notificare/{pid}", params={"auth": t2}).status_code == 404
        assert requests.get(f"{API}/docs/sizing/{pid}", headers={"Authorization": f"Bearer {t2}"}).status_code == 404

    def test_special_chars_in_name(self, s, token):
        # Reportlab Paragraph markup: '&' and '<' in names should not 500
        r = _import(s, client_name="TEST_PROS A & B <SRL>", inverter="Fronius <Symo> & Co")
        assert r.status_code == 200
        pid = r.json()["id"]
        res = requests.get(f"{API}/docs/notificare/{pid}", params={"auth": token}, timeout=60)
        assert res.status_code == 200, f"status {res.status_code}"

    def test_antal_record_docs(self, s, token):
        items = [p for p in s.get(f"{API}/data/prosumator").json() if "ANTAL" in (p.get("client_name") or "").upper()]
        assert items, "ZOLTAN ANTAL record missing"
        pid = items[0]["id"]
        r = requests.get(f"{API}/docs/all/{pid}", params={"auth": token}, timeout=60)
        assert r.status_code == 200 and r.content[:4] == b"%PDF"
        print("antal sizing:", s.get(f"{API}/docs/sizing/{pid}").json())


# --- Settings new fields ---
class TestSettings:
    def test_settings_fields_persist(self, s):
        orig = s.get(f"{API}/settings").json()
        new = {**orig, "cui": orig.get("cui") or "RO12345678", "regcom": orig.get("regcom") or "J05/123/2020",
               "anre_attest": orig.get("anre_attest") or "12345"}
        r = s.put(f"{API}/settings", json=new)
        assert r.status_code == 200
        g = s.get(f"{API}/settings").json()
        assert g["cui"] == new["cui"] and g["anre_attest"] == new["anre_attest"]
        if not (orig.get("cui") and orig.get("regcom") and orig.get("anre_attest")):
            # restore original
            restore = {k: orig.get(k, "") for k in ["cui", "regcom", "anre_attest"]}
            s.put(f"{API}/settings", json={**g, **restore})


# --- AI extract (no LLM call for validation) ---
class TestAiExtract:
    def test_reject_non_pdf(self, s):
        r = s.post(f"{API}/ai/extract", files={"file": ("a.txt", b"hello", "text/plain")}, timeout=60)
        assert r.status_code == 400

    @pytest.mark.skipif(not os.path.exists("/tmp/antal.pdf") or os.environ.get("SKIP_AI") == "1", reason="no sample / SKIP_AI")
    def test_extract_antal(self, s):
        with open("/tmp/antal.pdf", "rb") as f:
            r = s.post(f"{API}/ai/extract", files={"file": ("antal.pdf", f, "application/pdf")}, timeout=280)
        print(r.status_code, r.text[:1500])
        assert r.status_code == 200
        d = r.json()
        assert "ANTAL" in d["data"].get("client_name", "").upper()
        assert d["file"]["storage_path"]
        for k in ["cnp", "pod", "power", "inverter"]:
            assert k in d["data"], k


# --- Regression CRUD ---
class TestRegression:
    @pytest.mark.parametrize("mod", ["diu", "panels", "anti", "pram", "power", "projects"])
    def test_crud(self, s, mod):
        r = s.post(f"{API}/data/{mod}", json={"name": "TEST_PROS reg", "title": "TEST_PROS reg"})
        assert r.status_code == 200
        i = r.json()["id"]
        u = s.put(f"{API}/data/{mod}/{i}", json={"notes": "upd"})
        assert u.json()["notes"] == "upd"
        s.delete(f"{API}/data/{mod}/{i}")
        assert s.get(f"{API}/data/{mod}/{i}").status_code == 404
