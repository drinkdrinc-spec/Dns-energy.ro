# Tests: CEF technical checks, schema_cef PDF, catalog seed/CRUD/files, attach-catalog, import fixes
import os
import io
import json
import copy
import uuid
import pytest
import requests
from pypdf import PdfReader
from reportlab.pdfgen import canvas

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
EMAIL = "drinkdrinc@gmail.com"
PASSWORD = "DEnergy2026!"
SAMPLE = json.load(open(os.path.join(os.path.dirname(__file__), "cef_sample.json")))
CREATED = {"prosumator": [], "catalog": [], "clients": [], "documents": []}


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
def cleanup(s):
    yield
    for pid in CREATED["prosumator"]:
        s.delete(f"{API}/data/prosumator/{pid}")
    for m in ("catalog", "documents"):
        for i in CREATED[m]:
            s.delete(f"{API}/data/{m}/{i}")
    for it in s.get(f"{API}/data/clients").json():
        if str(it.get("name", "")).startswith("TEST_CEF"):
            s.delete(f"{API}/data/clients/{it['id']}")
    for it in s.get(f"{API}/data/documents").json():
        if str(it.get("client_name", "")).startswith("TEST_CEF"):
            s.delete(f"{API}/data/documents/{it['id']}")


def chk(s, cef):
    r = s.post(f"{API}/cef/check", json=cef)
    assert r.status_code == 200, r.text
    return r.json()


def small_pdf(pages=2):
    b = io.BytesIO()
    c = canvas.Canvas(b)
    for i in range(pages):
        c.drawString(100, 700, f"TEST datasheet page {i+1}")
        c.showPage()
    c.save()
    return b.getvalue()


# ---- CEF check ----
class TestCefCheck:
    def test_sample_totals_and_errors(self, s):
        r = chk(s, SAMPLE)
        t = r["totals"]
        assert abs(t["kwp"] - 17.63) < 0.01
        assert t["inverters_kw"] == 18
        assert abs(t["storage_kwh"] - 30.48) < 0.01
        assert t["panels"] == 38
        errs = " | ".join(r["errors"])
        print("ERRORS:", errs)
        print("WARNINGS:", " | ".join(r["warnings"]))
        assert "524 V" in errs and "500 V" in errs
        assert "14.0 A" in errs and "(13 A)" in errs
        assert "40 A > Iz" in errs and "2.5 mm²" in errs
        assert any("cădere de tensiune AC" in w for w in r["warnings"])

    def test_mono_grid_tri_inverter(self, s):
        c = copy.deepcopy(SAMPLE); c["grid"]["supply"] = "Monofazat"
        r = chk(s, c)
        assert any("trifazat pe branșament monofazat" in e for e in r["errors"])

    def test_export_over_bransament(self, s):
        c = copy.deepcopy(SAMPLE); c["grid"]["bransament_kw"] = 10
        r = chk(s, c)
        assert any("depășește puterea aprobată" in e for e in r["errors"])
        c["grid"]["bransament_kw"] = 50
        assert not any("depășește puterea aprobată" in e for e in chk(s, c)["errors"])

    def test_shared_battery_parallel(self, s):
        c = copy.deepcopy(SAMPLE)
        c["inverters"][0]["battery_mode"] = "shared"; c["inverters"][0]["shared_battery_id"] = "b1"
        r = chk(s, c)
        assert any("Baterie comună" in e for e in r["errors"])
        c["shared_batteries"][0]["parallel_supported"] = True
        r2 = chk(s, c)
        assert not any("Baterie comună" in e for e in r2["errors"])

    def test_anti_auto_over_27(self, s):
        c = copy.deepcopy(SAMPLE)
        assert chk(s, c)["grid"]["anti"] is False
        c["inverters"][0]["strings"] = [{"panels": 20, "mppt": 1}, {"panels": 20, "mppt": 2}, {"panels": 20, "mppt": 2}]
        r = chk(s, c)
        assert r["totals"]["kwp"] > 27
        assert r["grid"]["anti"] is True and r["grid"]["anti_auto"] is True
        c2 = copy.deepcopy(SAMPLE); c2["grid"]["anti_required"] = True
        r2 = chk(s, c2)
        assert r2["grid"]["anti"] is True and r2["grid"]["anti_auto"] is False

    def test_parallel_strings_diff_panels(self, s):
        c = copy.deepcopy(SAMPLE)
        c["inverters"][0]["strings"] = [{"panels": 13, "mppt": 1}, {"panels": 12, "mppt": 1}]
        r = chk(s, c)
        assert any("număr diferit de panouri" in e for e in r["errors"])

    def test_ac_proposals(self, s):
        r = chk(s, SAMPLE)
        import math
        for inv in r["inverters"]:
            p = inv["proposals"]["ac"]
            assert p["breaker_a"] >= p["ib"]
            assert p["section"] is not None
            print("AC proposal", inv["index"], p)
        # verify proposals satisfy check when applied
        c = copy.deepcopy(SAMPLE)
        for i, inv in enumerate(r["inverters"]):
            c["inverters"][i]["ac"]["breaker_a"] = inv["proposals"]["ac"]["breaker_a"]
            c["inverters"][i]["ac"]["section"] = inv["proposals"]["ac"]["section"]
        r2 = chk(s, c)
        assert not any("Iz" in e or "sub curentul de calcul" in e for e in r2["errors"]), r2["errors"]
        assert not any("cădere de tensiune AC" in w for w in r2["warnings"]), r2["warnings"]

    def test_empty_body(self, s):
        r = chk(s, {})
        assert r["totals"]["inverters"] == 0

    def test_unauth(self):
        assert requests.post(f"{API}/cef/check", json=SAMPLE).status_code == 401


# ---- Catalog ----
class TestCatalog:
    def test_seeded(self, s):
        items = s.get(f"{API}/data/catalog").json()
        cats = {}
        for i in items:
            cats[i["category"]] = cats.get(i["category"], 0) + 1
        print(cats)
        assert cats.get("Invertor", 0) >= 6 and cats.get("Panou", 0) >= 3 and cats.get("Baterie", 0) >= 4 and cats.get("Smart meter", 0) >= 1

    def test_seed_once_fresh_user(self):
        em = f"test_cef_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/auth/register", json={"email": em, "password": "Passw0rd!x"})
        assert r.status_code == 200
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        a = requests.get(f"{API}/data/catalog", headers=h).json()
        assert len(a) == 14
        b = requests.get(f"{API}/data/catalog", headers=h).json()
        assert len(b) == 14
        for it in b:
            requests.delete(f"{API}/data/catalog/{it['id']}", headers=h)
        assert requests.get(f"{API}/data/catalog", headers=h).json() == []
        print("FRESH_USER", em)

    def test_crud_and_upload(self, s):
        r = s.post(f"{API}/data/catalog", json={"category": "Invertor", "brand_model": "TEST_CEF Inv X", "p_nom_kw": 5})
        assert r.status_code == 200
        cid = r.json()["id"]; CREATED["catalog"].append(cid)
        up = s.post(f"{API}/upload", files={"file": ("ds.pdf", small_pdf(2), "application/pdf")})
        assert up.status_code == 200
        f = up.json()
        r = s.put(f"{API}/data/catalog/{cid}", json={"datasheet": f, "p_nom_kw": 6})
        assert r.status_code == 200 and r.json()["p_nom_kw"] == 6
        g = s.get(f"{API}/data/catalog/{cid}").json()
        assert g["datasheet"]["storage_path"] == f["storage_path"]
        dl = s.get(f"{API}/files/{f['storage_path']}")
        assert dl.status_code == 200 and dl.content[:4] == b"%PDF"


# ---- Prosumator w/ CEF: docs, catalog-files, attach ----
class TestProsCef:
    def test_flow(self, s, token):
        up = s.post(f"{API}/upload", files={"file": ("ds.pdf", small_pdf(3), "application/pdf")}).json()
        cat = s.post(f"{API}/data/catalog", json={"category": "Panou", "brand_model": "TEST_CEF Panel", "datasheet": up}).json()
        CREATED["catalog"].append(cat["id"])
        cef = copy.deepcopy(SAMPLE)
        cef["inverters"][0]["panel_catalog_id"] = cat["id"]
        cef["shared_batteries"][0]["catalog_id"] = cat["id"]  # dedupe check
        name = f"TEST_CEF_{uuid.uuid4().hex[:6]}"
        p = s.post(f"{API}/import/prosumator", json={"client_name": name, "pod": "TESTPOD1", "power": 18, "cef": cef}).json()
        pid = p["id"]; CREATED["prosumator"].append(pid)
        # schema_cef
        r = s.get(f"{API}/docs/schema_cef/{pid}?auth={token}")
        assert r.status_code == 200
        rd = PdfReader(io.BytesIO(r.content))
        print("schema_cef pages", len(rd.pages), [(float(pg.mediabox.width), float(pg.mediabox.height)) for pg in rd.pages])
        assert len(rd.pages) == 2
        assert all(float(pg.mediabox.width) > float(pg.mediabox.height) for pg in rd.pages)
        # all
        a = PdfReader(io.BytesIO(s.get(f"{API}/docs/all/{pid}?auth={token}").content))
        land = sum(1 for pg in a.pages if float(pg.mediabox.width) > float(pg.mediabox.height))
        print("all pages", len(a.pages), "landscape", land)
        assert land == 0  # iter9: old schema removed from legacy docs/all
        a2 = PdfReader(io.BytesIO(s.get(f"{API}/docs/all/{pid}?auth={token}&attach=1").content))
        print("attach pages", len(a2.pages))
        assert len(a2.pages) == len(a.pages) + 3
        # catalog-files
        cf = s.get(f"{API}/prosumator/{pid}/catalog-files").json()
        assert len(cf) == 1 and cf[0]["catalog_id"] == cat["id"]
        r1 = s.post(f"{API}/prosumator/{pid}/attach-catalog").json()
        r2 = s.post(f"{API}/prosumator/{pid}/attach-catalog").json()
        assert r1["added"] == 1 and r2["added"] == 0
        docs = [d for d in s.get(f"{API}/data/documents").json() if d.get("pros_ref") == pid and d.get("kind") == "Catalog"]
        assert len(docs) == 1
        CREATED["documents"] += [d["id"] for d in docs]
        # old schema when no cef
        p2 = s.post(f"{API}/import/prosumator", json={"client_name": name, "pod": "TESTPOD2", "power": 5, "inverter": "X", "inverter_kw": 5}).json()
        CREATED["prosumator"].append(p2["id"])
        b = PdfReader(io.BytesIO(s.get(f"{API}/docs/all/{p2['id']}?auth={token}").content))
        land2 = sum(1 for pg in b.pages if float(pg.mediabox.width) > float(pg.mediabox.height))
        print("no-cef all pages", len(b.pages), "landscape", land2)
        r = s.get(f"{API}/docs/schema/{p2['id']}?auth={token}")
        assert r.status_code == 200 and r.content[:4] == b"%PDF"
        # catalog-files 404
        assert s.get(f"{API}/prosumator/nonexistent/catalog-files").status_code == 404


# ---- Import fixes ----
class TestImport:
    def test_numbering_dup_cascade(self, s):
        name = f"TEST_CEF_IMP_{uuid.uuid4().hex[:6]}"
        nums = [int(p["number"].split("-")[-1]) for p in s.get(f"{API}/data/prosumator").json()
                if str(p.get("number") or "").startswith("PROS-2026-") and p["number"].split("-")[-1].isdigit()]
        r = s.post(f"{API}/import/prosumator", json={"client_name": name, "pod": "P1", "number": "", "inverter": "Inv", "panels": "Pan", "battery": "Bat"})
        assert r.status_code == 200
        p = r.json(); CREATED["prosumator"].append(p["id"])
        assert p["number"] == f"PROS-2026-{(max(nums) if nums else 0) + 1:03d}", p["number"]
        d = s.post(f"{API}/import/prosumator", json={"client_name": name, "pod": "P1"})
        assert d.status_code == 409
        eq = [e for e in s.get(f"{API}/data/equipment").json() if e.get("pros_ref") == p["id"]]
        assert len(eq) == 3 and all(e["client_name"] == name for e in eq)
        s.delete(f"{API}/data/prosumator/{p['id']}")
        for m in ("works", "mono", "equipment"):
            assert not [x for x in s.get(f"{API}/data/{m}").json() if x.get("pros_ref") == p["id"]], m
