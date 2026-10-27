# Tests: Remote signing module (sign requests CRUD, links, revoke/new-link/expire, public page, OTP, sign, refuse, attach to opis)
import base64
import hashlib
import io
import os
import time
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient
from pypdf import PdfReader
from PIL import Image, ImageDraw

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
EMAIL = "drinkdrinc@gmail.com"
PASSWORD = "DEnergy2026!"
DID = "3f6fd4d4-f603-4880-9a11-304820c2d3e3"
KEYS = ["afm", "pif", "reglaj"]
db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
S = {}


def sig_png():
    im = Image.new("RGBA", (600, 200), (255, 255, 255, 0))
    d = ImageDraw.Draw(im)
    import random
    random.seed(1)
    pts = [(random.randint(10, 590), random.randint(10, 190)) for _ in range(40)]
    d.line(pts, fill=(11, 31, 58, 255), width=4)
    b = io.BytesIO(); im.save(b, "PNG"); data = b.getvalue()
    assert len(data) > 800
    return "data:image/png;base64," + base64.b64encode(data).decode()


def set_otp(rid, code="123456"):
    db.sign_requests.update_one({"id": rid}, {"$set": {"otp_hash": hashlib.sha256(f"{rid}:{code}".encode()).hexdigest(),
                                                       "otp_exp": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()}})


@pytest.fixture(scope="module")
def h():
    r = requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    if r.status_code != 200:
        pytest.skip("login failed")
    t = r.json()["access_token"]
    S["auth"] = t
    yield {"Authorization": f"Bearer {t}"}
    # cleanup
    db.sign_requests.delete_many({"signer_name": {"$regex": "^TEST"}})
    db.documents.delete_many({"kind": "Semnat electronic", "client_name": "ZOLTAN ANTAL"})
    db.prosumator.update_one({"id": DID}, {"$unset": {f"opis.{k}": "" for k in KEYS + ["imputernicire"]}})


class TestRemoteSigning:
    def test_validation(self, h):
        base = {"dossier_id": DID, "pos_keys": ["afm"], "expires_days": 7}
        r = requests.post(f"{API}/sign/requests", headers=h, json={**base, "signers": [{"name": "", "email": "a@b.ro"}]})
        assert r.status_code == 400
        r = requests.post(f"{API}/sign/requests", headers=h, json={**base, "signers": [{"name": "TEST X", "email": "nope"}]})
        assert r.status_code == 400
        for d in (91, -1):
            r = requests.post(f"{API}/sign/requests", headers=h, json={**base, "expires_days": d, "signers": [{"name": "TEST X", "email": "a@b.ro"}]})
            assert r.status_code == 400, d
        r = requests.post(f"{API}/sign/requests", headers=h, json={**base, "pos_keys": ["nuexista"], "signers": [{"name": "TEST X", "email": "a@b.ro"}]})
        assert r.status_code == 404

    def test_create(self, h):
        r = requests.post(f"{API}/sign/requests", headers=h, json={"dossier_id": DID, "pos_keys": ["afm", "pif"], "expires_days": 7,
                          "signers": [{"name": "TEST Sig1", "email": "delivered@resend.dev", "phone": "0722000000", "role": "Beneficiar"},
                                      {"name": "TEST Sig2", "email": "delivered@resend.dev", "role": "Soț"}]})
        assert r.status_code == 200, r.text
        d = r.json()
        assert len(d) == 4
        for x in d:
            assert x["status"] == "De trimis" and len(x["token"]) >= 40 and x["doc_sha256"]
        S["afm"] = [x for x in d if x["pos_key"] == "afm"]
        S["pif"] = [x for x in d if x["pos_key"] == "pif"]
        doc = db.sign_requests.find_one({"id": d[0]["id"]})
        assert doc["token_hash"] == hashlib.sha256(d[0]["token"].encode()).hexdigest()
        assert "token" not in doc
        info = requests.get(f"{API}/dossier/{DID}", headers=h).json()
        st = {p["key"]: p.get("status") for p in info["positions"]}
        assert st["afm"] == "necesită semnătură" and st["pif"] == "necesită semnătură"

    def test_list(self, h):
        r = requests.get(f"{API}/sign/requests", headers=h, params={"dossier_id": DID})
        ids = {x["id"] for x in r.json()}
        assert {x["id"] for x in S["afm"] + S["pif"]} <= ids
        r2 = requests.get(f"{API}/sign/requests", headers=h, params={"client_name": "ZOLTAN ANTAL"})
        assert {x["id"] for x in S["afm"]} <= {x["id"] for x in r2.json()}
        assert all("token" not in x and "token_hash" not in x for x in r.json())

    def test_sent_and_public_open(self, h):
        a = S["afm"][0]
        r = requests.post(f"{API}/sign/requests/{a['id']}/sent", headers=h, json={"channel": "WhatsApp"})
        assert r.status_code == 200
        x = next(i for i in requests.get(f"{API}/sign/requests", headers=h, params={"dossier_id": DID}).json() if i["id"] == a["id"])
        assert x["status"] == "Link trimis"
        p = requests.get(f"{API}/public/sign/{a['token']}")
        assert p.status_code == 200, p.text
        pj = p.json()
        assert pj["status"] == "Deschis" and pj["pages"] >= 1 and "***@" in pj["email_masked"]
        S["pages"] = pj["pages"]
        doc = requests.get(f"{API}/public/sign/{a['token']}/document")
        assert doc.status_code == 200 and doc.content[:4] == b"%PDF"
        assert hashlib.sha256(doc.content).hexdigest() == a["doc_sha256"]
        pg = requests.get(f"{API}/public/sign/{a['token']}/page/0")
        assert pg.status_code == 200 and pg.content[:4] == b"\x89PNG"
        assert requests.get(f"{API}/public/sign/{a['token']}/page/{pj['pages']}").status_code == 404
        assert requests.get(f"{API}/public/sign/invalidtoken123").status_code == 404

    def test_otp_real_and_cooldown(self, h):
        a = S["afm"][0]
        r = requests.post(f"{API}/public/sign/{a['token']}/otp", json={})
        assert r.status_code == 200, r.text
        r2 = requests.post(f"{API}/public/sign/{a['token']}/otp", json={})
        assert r2.status_code == 429

    def test_wrong_otp(self, h):
        a = S["afm"][0]
        r = requests.post(f"{API}/public/sign/{a['token']}/sign", json={"declared_name": "TEST Sig1", "intent": True, "otp": "000000", "signature": sig_png()})
        assert r.status_code == 400 and r.json()["detail"] == "Cod incorect"
        doc = db.sign_requests.find_one({"id": a["id"]})
        assert any(x["action"] == "Cod greșit" for x in doc["history"])
        # missing intent
        r = requests.post(f"{API}/public/sign/{a['token']}/sign", json={"declared_name": "TEST Sig1", "intent": False, "otp": "000000", "signature": sig_png()})
        assert r.status_code == 400

    def test_sign_single_group(self, h):
        a = S["afm"][0]
        set_otp(a["id"])
        r = requests.post(f"{API}/public/sign/{a['token']}/sign", json={"declared_name": "TEST Sig1 Declarat", "intent": True, "otp": "123456", "signature": sig_png()})
        assert r.status_code == 200, r.text
        pj2 = requests.get(f"{API}/public/sign/{a['token']}").json()
        assert pj2["status"] == "Semnat" and pj2["pages"] == 0
        assert requests.post(f"{API}/public/sign/{a['token']}/sign", json={"declared_name": "x", "intent": True, "otp": "123456", "signature": sig_png()}).status_code == 410
        x = next(i for i in requests.get(f"{API}/sign/requests", headers=h, params={"dossier_id": DID}).json() if i["id"] == a["id"])
        assert x["status"] == "Semnat" and x["has_signed_file"]
        f = requests.get(f"{API}/sign/requests/{a['id']}/file", params={"auth": S["auth"]})
        assert f.status_code == 200 and f.content[:4] == b"%PDF"
        rd = PdfReader(io.BytesIO(f.content))
        assert len(rd.pages) == S["pages"] + 1  # only first signer's evidence page so far
        assert "FIȘĂ DE EVIDENȚĂ" in rd.pages[-1].extract_text()

    def test_attach_only_after_all(self, h):
        # afm group has 2 signers -> after 1 signed, not attached yet
        rec = db.prosumator.find_one({"id": DID}, {"_id": 0, "opis": 1})
        assert (rec["opis"].get("afm") or {}).get("status") == "necesită semnătură"
        assert "upload" not in (rec["opis"].get("afm") or {})
        b = S["afm"][1]
        set_otp(b["id"])
        r = requests.post(f"{API}/public/sign/{b['token']}/sign", json={"declared_name": "TEST Sig2", "intent": True, "otp": "123456", "signature": sig_png()})
        assert r.status_code == 200, r.text
        rec = db.prosumator.find_one({"id": DID}, {"_id": 0, "opis": 1})
        assert rec["opis"]["afm"]["status"] == "atașat" and rec["opis"]["afm"]["upload"]["storage_path"]
        f = requests.get(f"{API}/sign/requests/{b['id']}/file", params={"auth": S["auth"]})
        rd = PdfReader(io.BytesIO(f.content))
        assert len(rd.pages) == S["pages"] + 2
        last = rd.pages[-1].extract_text()
        assert "FIȘĂ DE EVIDENȚĂ A SEMNĂRII ELECTRONICE" in last
        assert "TEST Sig2" in last
        assert db.documents.count_documents({"kind": "Semnat electronic", "client_name": "ZOLTAN ANTAL"}) == 1
        # dossier export still works with attached signed file
        ex = requests.get(f"{API}/dossier/{DID}/export", headers=h)
        assert ex.status_code == 200 and ex.content[:4] == b"%PDF"

    def test_refuse(self, h):
        p = S["pif"][0]
        r = requests.post(f"{API}/public/sign/{p['token']}/refuse", json={"reason": "TEST motiv"})
        assert r.status_code == 200
        pr = requests.get(f"{API}/public/sign/{p['token']}").json()
        assert pr["status"] == "Refuzat" and pr["pages"] == 0
        x = next(i for i in requests.get(f"{API}/sign/requests", headers=h, params={"dossier_id": DID}).json() if i["id"] == p["id"])
        assert x["refused_reason"] == "TEST motiv"
        assert requests.post(f"{API}/sign/requests/{p['id']}/new-link", headers=h, json={}).status_code == 400

    def test_newlink_revoke_expire(self, h):
        p = S["pif"][1]
        r = requests.post(f"{API}/sign/requests/{p['id']}/new-link", headers=h, json={"expires_days": 3})
        assert r.status_code == 200
        nt = r.json()["token"]
        assert nt != p["token"]
        assert requests.get(f"{API}/public/sign/{p['token']}").status_code == 404
        assert requests.get(f"{API}/public/sign/{nt}").status_code == 200
        hist = db.sign_requests.find_one({"id": p["id"]})["history"]
        assert any(x["action"] == "Link nou generat" for x in hist) and any(x["action"] == "Cerere creată" for x in hist)
        # expire
        db.sign_requests.update_one({"id": p["id"]}, {"$set": {"expires_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()}})
        x = next(i for i in requests.get(f"{API}/sign/requests", headers=h, params={"dossier_id": DID}).json() if i["id"] == p["id"])
        assert x["status"] == "Expirat"
        pj = requests.get(f"{API}/public/sign/{nt}").json()
        assert pj["status"] == "Expirat" and pj["pages"] == 0
        assert requests.post(f"{API}/public/sign/{nt}/otp", json={}).status_code == 410
        # new link again then revoke
        nt2 = requests.post(f"{API}/sign/requests/{p['id']}/new-link", headers=h, json={}).json()["token"]
        assert requests.post(f"{API}/sign/requests/{p['id']}/revoke", headers=h).status_code == 200
        assert requests.get(f"{API}/public/sign/{nt2}").status_code == 404
        x = next(i for i in requests.get(f"{API}/sign/requests", headers=h, params={"dossier_id": DID}).json() if i["id"] == p["id"])
        assert x["status"] == "Expirat" and x["revoked"] is True

    def test_auth_required(self, h):
        assert requests.get(f"{API}/sign/requests").status_code in (401, 403)
        assert requests.get(f"{API}/sign/requests/{S['afm'][0]['id']}/file").status_code in (401, 403)
