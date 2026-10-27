# Tests (iteration 9): approved SLD in dossier opis (schema + fisa_tehnica positions), finalize gating, CIORNĂ export,
# approval history, designer-defined earthing limit, remote signing of approved schema (send-sign + sld_hash invalidation)
import os
import io
import sys
import copy
import uuid
import hashlib
import base64
import random
from datetime import datetime, timezone, timedelta
import pytest
import requests
from pypdf import PdfReader
from pymongo import MongoClient
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
EMAIL = "drinkdrinc@gmail.com"
PASSWORD = "DEnergy2026!"
sys.path.insert(0, "/app/backend")
from sld_demo import DEMO_REC  # noqa: E402

db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:6]
CREATED = {"prosumator": [], "clients": [], "staff": []}
ST = {}
AUTH = [{"type": "ANRE", "number": "T9", "expires": "2030-12-31", "file": {"storage_path": "x"}, "verified": True}]


def pdf(b):
    return PdfReader(io.BytesIO(b))


def text(b):
    return "\n".join(p.extract_text() or "" for p in pdf(b).pages)


def mkpdf(t):
    b = io.BytesIO(); c = canvas.Canvas(b); c.drawString(100, 700, t); c.save(); return b.getvalue()


def sig_png():
    im = Image.new("RGBA", (600, 200), (255, 255, 255, 0)); d = ImageDraw.Draw(im); random.seed(2)
    d.line([(random.randint(10, 590), random.randint(10, 190)) for _ in range(40)], fill=(11, 31, 58, 255), width=4)
    b = io.BytesIO(); im.save(b, "PNG"); return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


@pytest.fixture(scope="module")
def s():
    r = requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    if r.status_code != 200:
        pytest.skip("login failed")
    ss = requests.Session(); ss.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"}); ss.token = r.json()["access_token"]
    yield ss
    for pid in CREATED["prosumator"]:
        ss.post(f"{API}/dossier/{pid}/reopen", timeout=30)
        db.sign_requests.delete_many({"dossier_id": pid})
    for m, ids in CREATED.items():
        for i in ids:
            ss.delete(f"{API}/data/{m}/{i}", timeout=30)


def mk(s, module, payload):
    r = s.post(f"{API}/data/{module}", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    CREATED[module].append(r.json()["id"])
    return r.json()


@pytest.fixture(scope="module")
def rid(s):
    d = mk(s, "staff", {"name": f"TEST_Designer9_{TAG}", "email": EMAIL, "phone": "0700000009", "auths": AUTH})
    v = mk(s, "staff", {"name": f"TEST_Verifier9_{TAG}", "auths": AUTH})  # no email
    cl = mk(s, "clients", {"name": f"TEST_SLD9 Client {TAG}", "kind": "Persoană fizică", "idcode": "1800101123456", "hq_address": "Str. Dom 1",
                           "phone": "0722000999", "address": "Str. Exemplului nr. 1", "locality": "Loc Demo", "county": "Cluj",
                           "pod": f"POD9{TAG}", "operator": "Distribuție Energie Electrică România (DEER)"})
    r = copy.deepcopy(DEMO_REC)
    r.update({"client_name": cl["name"], "client_id": cl["id"], "name": cl["name"], "address": cl["address"], "locality": cl["locality"],
              "county": cl["county"], "operator": cl["operator"], "pod": cl["pod"], "signers": {"designer": d["id"], "verifier": v["id"]}})
    ST["cef"] = copy.deepcopy(r["cef"])
    return mk(s, "prosumator", r)["id"]


def dossier(s, rid):
    return s.get(f"{API}/dossier/{rid}", timeout=60).json()


def sld(s, rid):
    return s.get(f"{API}/sld/{rid}", timeout=60).json()


def put_cef(s, rid, cef):
    r = s.put(f"{API}/data/prosumator/{rid}", json={"cef": cef}, timeout=30)
    assert r.status_code == 200, r.text


class TestDossierSld:
    def test_01_positions_draft(self, s, rid):
        d = dossier(s, rid)
        p2, p3 = d["positions"][1], d["positions"][2]
        assert (p2["key"], p2["nr"]) == ("schema", 2) and (p3["key"], p3["nr"]) == ("fisa_tehnica", 3)
        for p in (p2, p3):
            assert any("Schema monofilară nu este aprobată" in m for m in p["missing"]), p["missing"]
            assert p["status"] == "de completat"
        assert sld(s, rid)["ready"] is True

    def test_02_files_pdf_and_docx_guard(self, s, rid):
        r = s.get(f"{API}/dossier/{rid}/file/schema", params={"auth": s.token}, timeout=90)
        assert r.status_code == 200 and r.headers["content-type"].startswith("application/pdf")
        rd = pdf(r.content)
        assert len(rd.pages) == 2
        assert all(float(p.mediabox.width) > float(p.mediabox.height) for p in rd.pages)
        r = s.get(f"{API}/dossier/{rid}/file/fisa_tehnica", params={"auth": s.token}, timeout=90)
        assert r.status_code == 200 and r.content[:4] == b"%PDF"
        t = text(r.content).lower()
        assert "cablu" in t or "cabluri" in t
        for k in ("schema", "fisa_tehnica"):
            r = s.get(f"{API}/dossier/{rid}/file/{k}", params={"auth": s.token, "fmt": "docx"}, timeout=30)
            assert r.status_code == 400, (k, r.status_code)

    def test_03_finalize_blocked_and_export_ciorna(self, s, rid):
        r = s.post(f"{API}/dossier/{rid}/finalize", timeout=30)
        assert r.status_code == 400 and "CIORNĂ" in r.json()["detail"]
        r = s.get(f"{API}/dossier/{rid}/export", params={"auth": s.token}, timeout=180)
        assert r.status_code == 200 and "_CIORNA" in r.headers.get("content-disposition", "")
        assert "CIORN" in text(r.content)

    def test_04_sign_blocked_before_approval(self, s, rid):
        r = s.post(f"{API}/sld/{rid}/send-sign", json={"role": "designer", "origin": "https://x"}, timeout=30)
        assert r.status_code == 400 and "aprobat" in r.json()["detail"]
        r = s.post(f"{API}/sign/requests", json={"dossier_id": rid, "pos_keys": ["schema"], "signers": [{"name": "TEST X", "email": EMAIL}]}, timeout=30)
        assert r.status_code == 400

    def test_05_earthing_limit_rules(self, s, rid):
        cef = copy.deepcopy(ST["cef"]); cef["grid"].pop("grounding_limit")
        put_cef(s, rid, cef)
        d = sld(s, rid)
        assert any("Valoare admisă priză de pământ" in m["label"] for m in d["missing"]) and d["ready"] is False
        cef["grid"].update({"grounding_limit": 10, "grounding_ohm": 5})
        put_cef(s, rid, cef)
        d = sld(s, rid)
        it = next(i for i in d["items"] if i["label"] == "Priză de pământ — valoare măsurată vs. admisă")
        assert it["ok"] is True and d["ready"] is True and not any("Priză de pământ" in e for e in d["errors"])
        cef["grid"]["grounding_ohm"] = 12
        put_cef(s, rid, cef)
        d = sld(s, rid)
        assert any("Priză de pământ — valoare măsurată vs. admisă" in e for e in d["errors"]) and d["ready"] is False
        assert s.post(f"{API}/sld/{rid}/approve", json={"role": "designer"}, timeout=30).status_code == 400
        # 4.5 Ω with limit 10 -> conform (no universal 4 Ω threshold)
        cef["grid"]["grounding_ohm"] = 4.5
        put_cef(s, rid, cef)
        d = sld(s, rid)
        assert d["ready"] is True and not any("Priză" in w for w in d["warnings"] + d["errors"])
        put_cef(s, rid, ST["cef"])
        assert sld(s, rid)["ready"] is True

    def test_06_approve_creates_history(self, s, rid):
        r = s.post(f"{API}/sld/{rid}/approve", json={"role": "designer"}, timeout=60)
        assert r.status_code == 200, r.text
        d = sld(s, rid)
        assert d["approval"]["status"] == "approved"
        assert len(d["history"]) == 1
        h = d["history"][0]
        assert h["revision"] == 0 and h["source"] == "generated" and h["current"] is True and h["file"]["storage_path"]
        assert "hash" not in h
        ST["h0"] = h["file"]["storage_path"]
        dd = dossier(s, rid)
        for p in dd["positions"][1:3]:
            assert p["missing"] == [], p["missing"]
            assert p["status"] == ("generat" if not dd["common_missing"] else "de completat"), (p["status"], dd["common_missing"])

    def test_07_schema_served_from_approved_file(self, s, rid):
        up = s.post(f"{API}/upload", files={"file": ("m.pdf", mkpdf("TEST_APPROVED_MARKER_9"), "application/pdf")}, timeout=60).json()
        db.prosumator.update_one({"id": rid}, {"$set": {"sld.history.0.file.storage_path": up["storage_path"]}})
        try:
            r = s.get(f"{API}/dossier/{rid}/file/schema", params={"auth": s.token}, timeout=60)
            assert "TEST_APPROVED_MARKER_9" in text(r.content)
            r = s.get(f"{API}/dossier/{rid}/export", params={"auth": s.token}, timeout=180)
            assert r.status_code == 200 and "TEST_APPROVED_MARKER_9" in text(r.content)
        finally:
            db.prosumator.update_one({"id": rid}, {"$set": {"sld.history.0.file.storage_path": ST["h0"]}})
        r = s.get(f"{API}/files/{ST['h0']}", params={"auth": s.token}, timeout=60)
        assert r.status_code == 200 and len(pdf(r.content).pages) == 2

    def test_08_finalize_after_approval(self, s, rid):
        r = s.post(f"{API}/dossier/{rid}/finalize", timeout=30)
        assert r.status_code == 200 and r.json()["ok"]
        assert s.post(f"{API}/dossier/{rid}/reopen", timeout=30).status_code == 200

    def test_09_send_sign(self, s, rid):
        r = s.post(f"{API}/sld/{rid}/send-sign", json={"role": "verifier", "origin": "https://x"}, timeout=30)
        assert r.status_code == 400 and "e-mail" in r.json()["detail"].lower()
        r = s.post(f"{API}/sld/{rid}/send-sign", json={"role": "designer", "origin": "https://x"}, timeout=90)
        assert r.status_code == 200, r.text
        out = r.json()
        assert len(out) == 1 and out[0]["pos_key"] == "schema" and out[0]["status"] == "Link trimis" and out[0]["token"]
        assert out[0]["signer_email"] == EMAIL and out[0]["role"] == "Proiectant schemă"
        rq = db.sign_requests.find_one({"id": out[0]["id"]})
        assert rq["sld_hash"] == sld(s, rid)["approval"]["fingerprint"]
        assert any(h["action"] == "Link trimis" for h in rq["history"])
        ST["sign"] = out[0]

    def test_10_sign_attaches_with_hash(self, s, rid):
        r0 = ST["sign"]
        db.sign_requests.update_one({"id": r0["id"]}, {"$set": {"otp_hash": hashlib.sha256(f"{r0['id']}:123456".encode()).hexdigest(),
                                                                "otp_exp": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()}})
        r = requests.post(f"{API}/public/sign/{r0['token']}/sign", json={"declared_name": "TEST Designer", "intent": True, "otp": "123456", "signature": sig_png()}, timeout=90)
        assert r.status_code == 200, r.text
        p = dossier(s, rid)["positions"][1]
        assert p["status"] == "atașat" and p["upload"] and p["upload"]["sld_hash"] == sld(s, rid)["approval"]["fingerprint"]

    def test_11_cef_change_invalidates(self, s, rid):
        cef = copy.deepcopy(ST["cef"]); cef["inverters"][0]["ac"]["length_m"] = 16
        put_cef(s, rid, cef)
        d = sld(s, rid)
        assert d["approval"]["status"] == "stale" and d["history"][0]["current"] is False
        p = dossier(s, rid)["positions"][1]
        print("POS_AFTER_CEF_CHANGE", {k: p[k] for k in ("status", "auto_status", "upload", "missing")})
        assert p["upload"] is None
        assert any("Versiunea semnată anterior" in m for m in p["missing"]), p["missing"]
        assert p["status"] != "atașat" and p["auto_status"] != "atașat", "BUG: stale signed schema still counted as atașat"
        assert any("Versiunea semnată anterior" in m for m in p["missing"]) and any("anulată" in m for m in p["missing"])
        assert s.post(f"{API}/dossier/{rid}/finalize", timeout=30).status_code == 400
        assert s.post(f"{API}/sld/{rid}/send-sign", json={"role": "designer", "origin": "https://x"}, timeout=30).status_code == 400

    def test_12_reapprove_new_revision(self, s, rid):
        r = s.post(f"{API}/sld/{rid}/approve", json={"role": "designer"}, timeout=60)
        assert r.status_code == 200, r.text
        d = sld(s, rid)
        assert d["revision"] == 1 and len(d["history"]) == 2
        assert d["history"][0]["revision"] == 1 and d["history"][0]["current"] is True
        assert d["history"][1]["revision"] == 0 and d["history"][1]["current"] is False
        assert d["history"][0]["file"]["storage_path"] != d["history"][1]["file"]["storage_path"]
        p = dossier(s, rid)["positions"][1]
        assert p["upload"] is None  # old signed version still ignored after re-approval (hash differs)
