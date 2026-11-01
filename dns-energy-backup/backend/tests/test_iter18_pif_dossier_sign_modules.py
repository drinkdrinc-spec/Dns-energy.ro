import os as _dns_test_os
import pytest as _dns_test_pytest
if not (_dns_test_os.environ.get("DNS_ENERGY_TEST_EMAIL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_PASSWORD") and _dns_test_os.environ.get("REACT_APP_BACKEND_URL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_ALLOW_MUTATION") == "1"):
    _dns_test_pytest.skip("Set staging-only DNS_ENERGY_TEST_* credentials, REACT_APP_BACKEND_URL and DNS_ENERGY_TEST_ALLOW_MUTATION=1", allow_module_level=True)

# Iteration 18 — PIF in dossier/opis, per-document signing links (client only), platform modules on/off
import os, io, uuid, base64, hashlib, random
from datetime import datetime, timezone, timedelta
import pytest, requests
from pymongo import MongoClient
from pypdf import PdfReader
from PIL import Image

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = (_dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"], _dns_test_os.environ["DNS_ENERGY_TEST_PASSWORD"])
PWD = "Test2026!x"
TAG = f"sub_i18_{uuid.uuid4().hex[:6]}"
PIF_TITLE = "Proces-verbal PIF — teste și verificări (măsurători)"
PF = {"client_type": "pf", "full_name": "Maria Test", "address": "Str. PF 2", "locality": "Cluj", "county": "Cluj", "country": "România",
      "billing_email": "pf@example.com", "phone": "0711111111"}
TEST_COLLECTIONS = ["clients", "prosumator", "diu", "pram", "staff", "instruments", "catalog", "documents"]


def _env(key):
    for line in open("/app/backend/.env"):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


mdb = MongoClient(_env("MONGO_URL"))[_env("DB_NAME")]
S = {}


def h(tok=None):
    return {"Authorization": f"Bearer {tok or S['admin']}"}


def pages(content):
    return len(PdfReader(io.BytesIO(content)).pages)


def pdf_text(content, n=None):
    pg = PdfReader(io.BytesIO(content)).pages
    return "\n".join((p.extract_text() or "") for p in (pg[:n] if n else pg))


def keys():
    return [p["key"] for p in requests.get(f"{API}/dossier/{S['pid']}", headers=h()).json()["positions"]]


def sig_png():
    img = Image.new("RGB", (300, 120), "white")
    px = img.load()
    for _ in range(4000):
        px[random.randrange(300), random.randrange(120)] = (0, 0, random.randrange(255))
    b = io.BytesIO(); img.save(b, "PNG")
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


def mk_user(suffix, team=None):
    email = f"{TAG}_{suffix}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": PWD, "name": f"TEST {suffix}", "billing": PF})
    assert r.status_code == 200, r.text
    uid = mdb.users.find_one({"email": email})["id"]
    body = {"status": "active", **({"to_team": team} if team else {})}
    r = requests.put(f"{API}/admin/subscribers/{uid}", headers=h(), json=body)
    assert r.status_code == 200, r.text
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": PWD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module", autouse=True)
def setup_and_cleanup():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})
    assert r.status_code == 200, r.text
    S["admin"] = r.json()["access_token"]
    S["owner"] = mdb.users.find_one({"email": ADMIN[0]})["id"]
    start = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    r = requests.post(f"{API}/test-dossier", headers=h())
    assert r.status_code == 200, r.text
    S["pid"] = r.json()["prosumator_id"]
    yield
    requests.put(f"{API}/platform/modules", headers=h(), json={"disabled": []})
    mdb.sign_requests.delete_many({"dossier_id": S["pid"]})
    mdb.documents.delete_many({"dossier_id": S["pid"]})
    for c in TEST_COLLECTIONS:
        mdb[c].delete_many({"owner": S["owner"], "is_test": True, "created_at": {"$gte": start}})
    mdb.users.delete_many({"email": {"$regex": f"^{TAG}"}})
    assert (mdb.platform_modules.find_one({"id": "main"}) or {}).get("disabled", []) == []


# ---------- (1) PIF in dossier ----------
class TestPifInDossier:
    def test_client_info_and_no_pif_initially(self):
        d = requests.get(f"{API}/dossier/{S['pid']}", headers=h()).json()
        assert set(d["client"]) >= {"name", "email", "phone"} and d["client"]["name"]
        assert "pif_pv" not in [p["key"] for p in d["positions"]]
        S["simple0"] = pages(requests.get(f"{API}/dossier/{S['pid']}/simple", params={"auth": S["admin"]}).content)
        S["export0"] = pages(requests.get(f"{API}/dossier/{S['pid']}/export", params={"auth": S["admin"]}).content)

    def test_date_without_values_not_present(self):
        r = requests.put(f"{API}/dossier/{S['pid']}/pif", headers=h(), json={"date": "2026-01-15", "operator": "TEST Op", "instruments": "Fluke"})
        assert r.status_code == 200, r.text
        assert "pif_pv" not in keys()

    def test_values_without_date_not_present(self):
        r = requests.put(f"{API}/dossier/{S['pid']}/pif", headers=h(), json={"date": "", "strings": {"0.0": {"voc": "487.3"}}})
        assert r.status_code == 200, r.text
        assert "pif_pv" not in keys()

    def test_completed_present_after_priza(self):
        r = requests.put(f"{API}/dossier/{S['pid']}/pif", headers=h(), json={"date": "2026-01-15", "strings": {"0.0": {"voc": "487.3"}}, "checks": {"0": "Conform"}})
        assert r.status_code == 200, r.text
        d = requests.get(f"{API}/dossier/{S['pid']}", headers=h()).json()
        k = [p["key"] for p in d["positions"]]
        assert "pif_pv" in k and k.index("pif_pv") == k.index("priza") + 1, k
        p = d["positions"][k.index("pif_pv")]
        assert p["title"] == PIF_TITLE and p["nr"] == d["positions"][k.index("priza")]["nr"] + 1

    def test_only_check_counts(self):
        r = requests.put(f"{API}/dossier/{S['pid']}/pif", headers=h(), json={"date": "2026-01-15", "checks": {"2": "Conform"}})
        assert r.status_code == 200
        assert "pif_pv" in keys()
        requests.put(f"{API}/dossier/{S['pid']}/pif", headers=h(), json={"date": "2026-01-15", "strings": {"0.0": {"voc": "487.3"}}, "checks": {"0": "Conform"}})

    def test_simple_and_export_include_pif(self):
        rs = requests.get(f"{API}/dossier/{S['pid']}/simple", params={"auth": S["admin"]})
        assert rs.status_code == 200 and rs.content[:4] == b"%PDF"
        assert pages(rs.content) > S["simple0"], (pages(rs.content), S["simple0"])
        t = pdf_text(rs.content)
        assert "487.3" in t
        assert "Proces-verbal PIF" in pdf_text(rs.content, 2), "opis declaration does not list PIF title"
        re_ = requests.get(f"{API}/dossier/{S['pid']}/export", params={"auth": S["admin"]})
        assert re_.status_code == 200 and pages(re_.content) > S["export0"]
        assert "487.3" in pdf_text(re_.content)

    def test_file_endpoint(self):
        r = requests.get(f"{API}/dossier/{S['pid']}/file/pif_pv", params={"auth": S["admin"]})
        assert r.status_code == 200 and r.content[:4] == b"%PDF"


# ---------- (2) Signing links per document ----------
class TestSigning:
    def signer(self):
        c = requests.get(f"{API}/dossier/{S['pid']}", headers=h()).json()["client"]
        return {"name": c["name"] or "TEST Client", "email": c["email"] if "@" in (c["email"] or "") else "client_i18@example.com", "phone": c["phone"]}

    def test_two_signers_400(self):
        s = self.signer()
        r = requests.post(f"{API}/sign/requests", headers=h(), json={"dossier_id": S["pid"], "pos_keys": ["priza"], "signers": [s, {**s, "email": "x2@example.com"}]})
        assert r.status_code == 400, r.text

    def test_multi_docs_one_signer(self):
        r = requests.post(f"{API}/sign/requests", headers=h(), json={"dossier_id": S["pid"], "pos_keys": ["priza", "pif_pv", "executant"], "signers": [self.signer()]})
        assert r.status_code == 200, r.text
        out = r.json()
        assert len(out) == 3
        assert len({x["token"] for x in out}) == 3 and len({x["group_id"] for x in out}) == 3
        assert {x["pos_key"] for x in out} == {"priza", "pif_pv", "executant"}
        assert all(x["role"] == "Beneficiar" for x in out)
        for x in out:
            exp = datetime.fromisoformat(x["expires_at"])
            assert abs((exp - datetime.now(timezone.utc)).total_seconds() - 7 * 86400) < 600
        S["req"] = next(x for x in out if x["pos_key"] == "pif_pv")

    def test_public_info_and_otp(self):
        t = S["req"]["token"]
        r = requests.get(f"{API}/public/sign/{t}")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["doc_title"] == PIF_TITLE and d["pages"] >= 1 and d["status"] == "Deschis"
        assert requests.get(f"{API}/public/sign/{t}/page/0").headers["content-type"] == "image/png"
        r = requests.post(f"{API}/public/sign/{t}/otp")
        S["otp_status"] = r.status_code
        print("OTP response:", r.status_code, r.text[:200])
        assert r.status_code in (200, 400)  # 400 expected when test_email not configured for TEST dossiers

    def test_sign_flow_and_dossier_save(self):
        t, rid = S["req"]["token"], S["req"]["id"]
        code = "123456"
        mdb.sign_requests.update_one({"id": rid}, {"$set": {"otp_hash": hashlib.sha256(f"{rid}:{code}".encode()).hexdigest(),
                                                            "otp_exp": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(), "otp_attempts": 0}})
        bad = requests.post(f"{API}/public/sign/{t}/sign", json={"otp": "000000", "signature": sig_png(), "intent": True, "declared_name": "TEST Client"})
        assert bad.status_code == 400
        r = requests.post(f"{API}/public/sign/{t}/sign", json={"otp": code, "signature": sig_png(), "intent": True, "declared_name": "TEST Client"})
        assert r.status_code == 200, r.text
        rec = mdb.prosumator.find_one({"id": S["pid"]})
        up = (rec.get("opis") or {}).get("pif_pv", {}).get("upload")
        assert up and up.get("storage_path"), rec.get("opis")
        assert rec["opis"]["pif_pv"]["status"] == "atașat"
        doc = mdb.documents.find_one({"dossier_id": S["pid"]})
        assert doc and doc.get("client_id") == rec.get("client_id") and doc["kind"] == "Semnat electronic"
        cl = mdb.clients.find_one({"id": rec["client_id"]})
        sem = (cl.get("docs") or {}).get("semnate") or []
        assert len(sem) == 1 and "semnat" in sem[0]["original_filename"]
        # other docs' requests unaffected
        others = list(mdb.sign_requests.find({"dossier_id": S["pid"], "pos_key": {"$ne": "pif_pv"}}))
        assert all(o["status"] != "Semnat" for o in others)
        again = requests.post(f"{API}/public/sign/{t}/sign", json={"otp": code, "signature": sig_png(), "intent": True, "declared_name": "X"})
        assert again.status_code in (409, 410)
        f = requests.get(f"{API}/sign/requests/{rid}/file", params={"auth": S["admin"]})
        assert f.status_code == 200 and pages(f.content) >= 2

    def test_dossier_position_attached(self):
        d = requests.get(f"{API}/dossier/{S['pid']}", headers=h()).json()
        p = next(x for x in d["positions"] if x["key"] == "pif_pv")
        assert p["upload"] and p["status"] == "atașat"


# ---------- (3) Platform modules ----------
class TestPlatformModules:
    def test_admin_get(self):
        r = requests.get(f"{API}/platform/modules", headers=h())
        assert r.status_code == 200, r.text
        m = {x["key"]: x for x in r.json()["modules"]}
        assert "power" in m and all(x["enabled"] for x in m.values())

    def test_non_platform_403(self):
        S["sub"] = mk_user("sub")
        assert requests.get(f"{API}/platform/modules", headers=h(S["sub"])).status_code == 403
        assert requests.put(f"{API}/platform/modules", headers=h(S["sub"]), json={"disabled": ["power"]}).status_code == 403

    def test_invalid_key_400(self):
        assert requests.put(f"{API}/platform/modules", headers=h(), json={"disabled": ["nope"]}).status_code == 400
        assert requests.put(f"{API}/platform/modules", headers=h(), json={"disabled": "power"}).status_code == 400

    def test_disable_power(self):
        r = requests.put(f"{API}/platform/modules", headers=h(), json={"disabled": ["power"]})
        assert r.status_code == 200 and r.json()["disabled"] == ["power"]
        me = requests.get(f"{API}/auth/me", headers=h(S["sub"])).json()
        assert "power" in me["plan"]["disabled"], me["plan"]
        r = requests.get(f"{API}/data/power", headers=h(S["sub"]))
        assert r.status_code == 403 and "indisponibil momentan" in r.text, r.text
        assert requests.get(f"{API}/auth/me", headers=h()).json()["plan"]["disabled"] == []
        assert requests.get(f"{API}/data/power", headers=h()).status_code == 200
        st = {x["key"]: x["enabled"] for x in requests.get(f"{API}/platform/modules", headers=h()).json()["modules"]}
        assert st["power"] is False

    def test_team_member_also_blocked(self):
        tok = mk_user("team", team="instalator")
        me = requests.get(f"{API}/auth/me", headers=h(tok)).json()
        assert "power" in me["plan"]["disabled"], f"team member of platform tenant NOT blocked: {me['plan']}"

    def test_restore(self):
        r = requests.put(f"{API}/platform/modules", headers=h(), json={"disabled": []})
        assert r.status_code == 200 and r.json()["disabled"] == []
        assert requests.get(f"{API}/data/power", headers=h(S["sub"])).status_code != 403 or "indisponibil" not in requests.get(f"{API}/data/power", headers=h(S["sub"])).text
