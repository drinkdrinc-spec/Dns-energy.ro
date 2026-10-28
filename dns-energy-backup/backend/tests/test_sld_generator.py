# Tests: new single-line diagram (SLD) generator — demo PDF, status, PDFs, apply, approve/stale/unapprove, source/upload
import os
import copy
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
EMAIL = "drinkdrinc@gmail.com"
PASSWORD = "DEnergy2026!"

import sys
sys.path.insert(0, "/app/backend")
from sld_demo import DEMO_REC, DEMO_CLIENT  # noqa: E402

CREATED = {"prosumator": [], "clients": [], "staff": []}


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    if r.status_code != 200:
        pytest.skip("login failed")
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def s(token):
    ss = requests.Session()
    ss.headers.update({"Authorization": f"Bearer {token}"})
    yield ss
    for m, ids in CREATED.items():
        for i in ids:
            ss.delete(f"{API}/data/{m}/{i}", timeout=30)


def pdf_pages(b: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page[^s]", b))


def mk(s, module, payload):
    r = s.post(f"{API}/data/{module}", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    CREATED[module].append(r.json()["id"])
    return r.json()


@pytest.fixture(scope="module")
def staff(s):
    return mk(s, "staff", {"name": "TEST_Proiectant SLD", "role": "Proiectant",
                           "auths": [{"type": "ANRE IIB", "number": "TEST123", "expires": "2030-12-31",
                                      "file": {"storage_path": "x"}, "verified": True}]})


@pytest.fixture(scope="module")
def staff_bad(s):
    return mk(s, "staff", {"name": "TEST_Neautorizat", "auths": [{"type": "ANRE", "number": "1", "expires": "2020-01-01",
                                                                   "file": {"storage_path": "x"}, "verified": True}]})


@pytest.fixture(scope="module")
def full_rec(s, staff):
    cl = mk(s, "clients", {**{k: v for k, v in DEMO_CLIENT.items()}, "name": "TEST_SLD Client"})
    rec = copy.deepcopy(DEMO_REC)
    rec.update({"client_name": cl["name"], "client_id": cl["id"], "name": cl["name"], "address": DEMO_CLIENT["address"],
                "locality": DEMO_CLIENT["locality"], "county": DEMO_CLIENT["county"], "operator": DEMO_CLIENT["operator"],
                "project_no": "TEST-SLD-1", "signers": {"designer": staff["id"]}})
    return mk(s, "prosumator", rec)


@pytest.fixture(scope="module")
def empty_rec(s):
    return mk(s, "prosumator", {"client_name": "TEST_SLD Empty", "cef": {"inverters": [{"p_nom_kw": 5, "phases": "Monofazat",
                                                                                         "panel_w": 450, "panel_voc": 41, "panel_vmp": 34.5, "panel_isc": 13.9,
                                                                                         "strings": [{"panels": 10, "mppt": 1}]}], "grid": {"supply": "Monofazat"}}})


class TestDemo:
    def test_demo_pdf(self, token):
        r = requests.get(f"{API}/sld/demo/pdf", params={"auth": token}, timeout=60)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
        assert pdf_pages(r.content) == 2, pdf_pages(r.content)

    def test_demo_no_auth(self):
        r = requests.get(f"{API}/sld/demo/pdf", timeout=30)
        assert r.status_code == 401


class TestStatus:
    def test_status_full(self, s, full_rec):
        r = s.get(f"{API}/sld/{full_rec['id']}", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("items", "missing", "errors", "warnings", "cables", "ready", "format", "approval", "source", "people"):
            assert k in d
        assert d["approval"]["status"] == "draft"
        assert d["format"] in ("A3", "A4")
        assert d["source"] == "generated"
        print("missing:", d["missing"], "errors:", d["errors"])
        assert d["ready"] is True, (d["missing"], d["errors"])
        assert d["people"]["designer"]["eligible"] is True

    def test_status_empty_missing(self, s, empty_rec):
        d = s.get(f"{API}/sld/{empty_rec['id']}", timeout=30).json()
        assert d["ready"] is False
        assert len(d["missing"]) > 0
        assert d["format"] == "A4"

    def test_status_404(self, s):
        assert s.get(f"{API}/sld/nonexistent-id", timeout=30).status_code == 404


class TestPdfs:
    @pytest.mark.parametrize("fmt", ["A3", "A4", "auto"])
    def test_pdf(self, token, full_rec, fmt):
        r = requests.get(f"{API}/sld/{full_rec['id']}/pdf", params={"auth": token, "fmt": fmt}, timeout=60)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"

    def test_pdf_incomplete(self, token, empty_rec):
        r = requests.get(f"{API}/sld/{empty_rec['id']}/pdf", params={"auth": token}, timeout=60)
        assert r.status_code == 200 and r.content[:4] == b"%PDF"

    def test_report(self, token, full_rec, empty_rec):
        for rid in (full_rec["id"], empty_rec["id"]):
            r = requests.get(f"{API}/sld/{rid}/report", params={"auth": token}, timeout=60)
            assert r.status_code == 200 and r.content[:4] == b"%PDF"


class TestApply:
    def test_apply_fills_empty_only(self, s, empty_rec):
        cef = copy.deepcopy(empty_rec["cef"])
        cef["inverters"][0]["ac"] = {"section": 6}
        r = s.post(f"{API}/sld/{empty_rec['id']}/apply", json={"cef": cef}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d["filled"], list) and len(d["filled"]) > 0
        assert "cef.inverters.0.ac.section" not in d["filled"]
        assert d["cef"]["inverters"][0]["ac"]["section"] == 6
        assert d["cef"]["inverters"][0]["ac"]["pe_section"] == 6
        assert set(d["filled"]).issubset(set(d["cef"]["auto_filled"]))
        got = s.get(f"{API}/data/prosumator/{empty_rec['id']}", timeout=30).json()
        assert got["cef"]["auto_filled"] == d["cef"]["auto_filled"]
        st = s.get(f"{API}/sld/{empty_rec['id']}", timeout=30).json()
        assert st["auto_filled"] == d["cef"]["auto_filled"]
        # second apply should fill nothing new
        r2 = s.post(f"{API}/sld/{empty_rec['id']}/apply", json={}, timeout=30).json()
        assert r2["filled"] == []


class TestApprove:
    def test_approve_missing_data(self, s, empty_rec, staff):
        s.put(f"{API}/data/prosumator/{empty_rec['id']}", json={"signers": {"designer": staff["id"]}}, timeout=30)
        r = s.post(f"{API}/sld/{empty_rec['id']}/approve", json={"role": "designer"}, timeout=30)
        assert r.status_code == 400
        assert "lipsă" in r.json()["detail"]

    def test_approve_invalid_role(self, s, full_rec):
        assert s.post(f"{API}/sld/{full_rec['id']}/approve", json={"role": "x"}, timeout=30).status_code == 400

    def test_approve_no_signer(self, s, full_rec):
        r = s.post(f"{API}/sld/{full_rec['id']}/approve", json={"role": "verifier"}, timeout=30)
        assert r.status_code == 400
        assert "Selectați" in r.json()["detail"]

    def test_approve_ineligible_signer(self, s, full_rec, staff, staff_bad):
        s.put(f"{API}/data/prosumator/{full_rec['id']}", json={"signers": {"designer": staff["id"], "verifier": staff_bad["id"]}}, timeout=30)
        r = s.post(f"{API}/sld/{full_rec['id']}/approve", json={"role": "verifier"}, timeout=30)
        assert r.status_code == 400
        assert "autorizație" in r.json()["detail"]

    def test_approve_flow_stale_unapprove(self, s, token, full_rec, staff):
        rid = full_rec["id"]
        r = s.post(f"{API}/sld/{rid}/approve", json={"role": "designer"}, timeout=30)
        assert r.status_code == 200, r.text
        ap = r.json()
        assert ap["name"] == staff["name"] and ap["role"] == "designer" and "hash" in ap
        st = s.get(f"{API}/sld/{rid}", timeout=30).json()
        assert st["approval"]["status"] == "approved"
        pdf = requests.get(f"{API}/sld/{rid}/pdf", params={"auth": token}, timeout=60)
        assert pdf.status_code == 200
        # modify cef -> stale
        rec = s.get(f"{API}/data/prosumator/{rid}", timeout=30).json()
        cef = rec["cef"]
        cef["inverters"][0]["ac"]["length_m"] = 18
        s.put(f"{API}/data/prosumator/{rid}", json={"cef": cef}, timeout=30)
        st = s.get(f"{API}/sld/{rid}", timeout=30).json()
        assert st["approval"]["status"] == "stale"
        # re-approve bumps revision
        r = s.post(f"{API}/sld/{rid}/approve", json={"role": "designer"}, timeout=30)
        assert r.status_code == 200
        st = s.get(f"{API}/sld/{rid}", timeout=30).json()
        assert st["approval"]["status"] == "approved" and st["revision"] == 1
        # unapprove
        assert s.post(f"{API}/sld/{rid}/unapprove", timeout=30).status_code == 200
        st = s.get(f"{API}/sld/{rid}", timeout=30).json()
        assert st["approval"]["status"] == "draft"


class TestSource:
    def test_uploaded_without_upload(self, s, full_rec):
        r = s.put(f"{API}/sld/{full_rec['id']}/source", json={"source": "uploaded"}, timeout=30)
        assert r.status_code == 400

    def test_upload_and_clear(self, s, full_rec):
        rid = full_rec["id"]
        up = {"storage_path": "TEST/sld.pdf", "name": "sld.pdf"}
        r = s.put(f"{API}/sld/{rid}/source", json={"source": "uploaded", "upload": up}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["source"] == "uploaded"
        st = s.get(f"{API}/sld/{rid}", timeout=30).json()
        assert st["source"] == "uploaded" and st["upload"]["storage_path"] == "TEST/sld.pdf"
        r = s.put(f"{API}/sld/{rid}/source", json={"clear_upload": True}, timeout=30)
        assert r.status_code == 200
        assert r.json()["source"] == "generated" and "upload" not in r.json()
        st = s.get(f"{API}/sld/{rid}", timeout=30).json()
        assert st["source"] == "generated" and st["upload"] is None

    def test_source_404(self, s):
        assert s.put(f"{API}/sld/nope/source", json={"source": "generated"}, timeout=30).status_code == 404
