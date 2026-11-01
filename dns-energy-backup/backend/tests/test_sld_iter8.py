import os as _dns_test_os
import pytest as _dns_test_pytest
if not (_dns_test_os.environ.get("DNS_ENERGY_TEST_EMAIL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_PASSWORD") and _dns_test_os.environ.get("REACT_APP_BACKEND_URL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_ALLOW_MUTATION") == "1"):
    _dns_test_pytest.skip("Set staging-only DNS_ENERGY_TEST_* credentials, REACT_APP_BACKEND_URL and DNS_ENERGY_TEST_ALLOW_MUTATION=1", allow_module_level=True)

# Tests (iteration 8): sld preserved on generic PUT, dual approvals, NECONFORM -> errors/warnings, demo config, label, single-phase warning
import os
import sys
import copy
import zlib
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
EMAIL = _dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"]
PASSWORD = _dns_test_os.environ["DNS_ENERGY_TEST_PASSWORD"]
sys.path.insert(0, "/app/backend")
from sld_demo import DEMO_REC, DEMO_CLIENT  # noqa: E402
import sizing as SZ  # noqa: E402
import sld as SLD  # noqa: E402

CREATED = {"prosumator": [], "clients": [], "staff": []}


@pytest.fixture(scope="module")
def s():
    r = requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    if r.status_code != 200:
        pytest.skip("login failed")
    ss = requests.Session()
    ss.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    yield ss
    for m, ids in CREATED.items():
        for i in ids:
            ss.delete(f"{API}/data/{m}/{i}", timeout=30)


def mk(s, module, payload):
    r = s.post(f"{API}/data/{module}", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    CREATED[module].append(r.json()["id"])
    return r.json()


def staffer(s, name):
    return mk(s, "staff", {"name": name, "auths": [{"type": "ANRE", "number": "T8", "expires": "2030-12-31",
                                                    "file": {"storage_path": "x"}, "verified": True}]})


@pytest.fixture(scope="module")
def rec(s):
    d, v = staffer(s, "TEST_Designer8"), staffer(s, "TEST_Verifier8")
    cl = mk(s, "clients", {**DEMO_CLIENT, "name": "TEST_SLD8 Client"})
    r = copy.deepcopy(DEMO_REC)
    r.update({"client_name": cl["name"], "client_id": cl["id"], "name": cl["name"], "address": DEMO_CLIENT["address"],
              "locality": DEMO_CLIENT["locality"], "county": DEMO_CLIENT["county"], "operator": DEMO_CLIENT["operator"],
              "signers": {"designer": d["id"], "verifier": v["id"]}})
    return mk(s, "prosumator", r)


def st(s, rid):
    return s.get(f"{API}/sld/{rid}", timeout=30).json()


class TestPutPreservesSld:
    def test_full_form_put_keeps_approval(self, s, rec):
        rid = rec["id"]
        stale_form = s.get(f"{API}/data/prosumator/{rid}", timeout=30).json()  # form loaded BEFORE approve (no sld)
        assert s.post(f"{API}/sld/{rid}/approve", json={"role": "designer"}, timeout=30).status_code == 200
        stale_form["sld"] = {"source": "generated"}  # simulate stale sld in form
        r = s.put(f"{API}/data/prosumator/{rid}", json=stale_form, timeout=30)
        assert r.status_code == 200
        assert r.json()["sld"]["approvals"]["designer"]["name"] == "TEST_Designer8"
        assert st(s, rid)["approval"]["status"] == "approved"

    def test_put_keeps_upload(self, s, rec):
        rid = rec["id"]
        up = {"storage_path": "TEST/sld8.pdf", "original_filename": "sld8.pdf"}
        assert s.put(f"{API}/sld/{rid}/source", json={"source": "uploaded", "upload": up}, timeout=30).status_code == 200
        form = s.get(f"{API}/data/prosumator/{rid}", timeout=30).json()
        form["sld"] = {}
        s.put(f"{API}/data/prosumator/{rid}", json=form, timeout=30)
        d = st(s, rid)
        assert d["source"] == "uploaded" and d["upload"]["storage_path"] == "TEST/sld8.pdf"
        s.put(f"{API}/sld/{rid}/source", json={"clear_upload": True}, timeout=30)
        s.post(f"{API}/sld/{rid}/unapprove", timeout=30)
        assert st(s, rid)["source"] == "generated"


class TestDualApprovals:
    def test_both_valid_then_stale_then_reapprove(self, s, rec):
        rid = rec["id"]
        s.post(f"{API}/sld/{rid}/unapprove", timeout=30)
        rev0 = st(s, rid)["revision"]
        assert s.post(f"{API}/sld/{rid}/approve", json={"role": "designer"}, timeout=30).status_code == 200
        assert s.post(f"{API}/sld/{rid}/approve", json={"role": "verifier"}, timeout=30).status_code == 200
        d = st(s, rid)
        aps = d["approval"]["approvals"]
        assert set(aps) == {"designer", "verifier"}
        assert aps["designer"]["valid"] is True and aps["verifier"]["valid"] is True
        assert d["approval"]["status"] == "approved" and d["revision"] == rev0
        # change cef -> stale
        form = s.get(f"{API}/data/prosumator/{rid}", timeout=30).json()
        form["cef"]["inverters"][0]["ac"]["length_m"] = 22
        s.put(f"{API}/data/prosumator/{rid}", json={"cef": form["cef"]}, timeout=30)
        d = st(s, rid)
        assert d["approval"]["status"] == "stale"
        assert all(a["valid"] is False for a in d["approval"]["approvals"].values())
        # re-approve bumps revision, drops stale verifier
        assert s.post(f"{API}/sld/{rid}/approve", json={"role": "designer"}, timeout=30).status_code == 200
        d = st(s, rid)
        assert d["approval"]["status"] == "approved" and d["revision"] == rev0 + 1
        assert list(d["approval"]["approvals"]) == ["designer"]
        # verifier approves again -> no extra bump
        s.post(f"{API}/sld/{rid}/approve", json={"role": "verifier"}, timeout=30)
        d = st(s, rid)
        assert d["revision"] == rev0 + 1 and len(d["approval"]["approvals"]) == 2
        # unapprove clears both
        assert s.post(f"{API}/sld/{rid}/unapprove", timeout=30).status_code == 200
        d = st(s, rid)
        assert d["approval"]["status"] == "draft" and d["approval"]["approvals"] == {}


class TestNeconform:
    def test_demo_ready_no_errors(self):
        r = SZ.compute(DEMO_REC, DEMO_CLIENT)
        assert DEMO_REC["cef"]["grid"]["tg_breaker_a"] == 32 and DEMO_REC["cef"]["grid"]["bmp_a"] == 40
        assert r["errors"] == [] and r["missing"] == [] and r["ready"] is True, (r["errors"], r["missing"])
        assert not [i for i in r["items"] if i["ok"] is False]

    def test_selectivity_violation_is_error(self, s, rec):
        rid = rec["id"]
        form = s.get(f"{API}/data/prosumator/{rid}", timeout=30).json()
        cef = form["cef"]
        cef["grid"]["tg_breaker_a"] = 50  # TG 50 > BMP 40
        s.put(f"{API}/data/prosumator/{rid}", json={"cef": cef}, timeout=30)
        d = st(s, rid)
        assert d["ready"] is False
        assert any("Selectivitate" in e for e in d["errors"]), d["errors"]
        r = s.post(f"{API}/sld/{rid}/approve", json={"role": "designer"}, timeout=30)
        assert r.status_code == 400 and "erori" in r.json()["detail"]
        cef["grid"]["tg_breaker_a"] = 32
        s.put(f"{API}/data/prosumator/{rid}", json={"cef": cef}, timeout=30)
        assert st(s, rid)["ready"] is True

    def test_dc_drop_is_warning(self):
        r = copy.deepcopy(DEMO_REC)
        for inv in r["cef"]["inverters"]:
            if inv.get("dc"):
                inv["dc"]["length_m"] = 400
                inv["dc"]["section"] = 4
        res = SZ.compute(r, DEMO_CLIENT)
        assert any("DC — cădere" in w for w in res["warnings"]), res["warnings"]
        assert not any("DC — cădere" in e for e in res["errors"])


class TestLabelsAndWarnings:
    def test_no_zero_kwp_label(self):
        r = copy.deepcopy(DEMO_REC)
        for inv in r["cef"]["inverters"]:
            inv.pop("panel_w", None)
        res = SZ.compute(r, DEMO_CLIENT)
        pdf = SLD.render(r, DEMO_CLIENT, {}, res, {"status": "draft"}, "A3")
        import io
        from pypdf import PdfReader
        txt = " ".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf)).pages)
        assert "kWp lipsă" in txt, txt[:500]
        assert not re.search(r"= 0 kWp", txt), re.findall(r".{20}= 0 kWp", txt)

    def test_no_single_phase_warning_without_supply(self):
        c = {"inverters": [{"p_nom_kw": 5, "phases": "Monofazat", "panel_w": 450, "panel_voc": 41, "panel_vmp": 34.5,
                            "panel_isc": 13.9, "strings": [{"panels": 10, "mppt": 1}]}], "grid": {}}
        res = SZ.compute({"cef": c}, {})
        assert not any("monofazat pe racord trifazat" in w for w in res["warnings"]), res["warnings"]
        c["grid"]["supply"] = "Trifazat"
        res = SZ.compute({"cef": c}, {})
        assert any("monofazat pe racord trifazat" in w for w in res["warnings"])
