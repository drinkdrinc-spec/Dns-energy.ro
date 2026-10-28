# Iteration 24: premium 'Dosare ANRE' service — create/pay gating, uploads, check report, statuses, ZIP package, isolation, AI
import os
import io
import json
import uuid
import zipfile
from datetime import date, timedelta

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE:
    for ln in open("/app/frontend/.env"):
        if ln.startswith("REACT_APP_BACKEND_URL="):
            BASE = ln.split("=", 1)[1].strip()
API = BASE.rstrip("/") + "/api"
ADMIN = {"email": "drinkdrinc@gmail.com", "password": "DEnergy2026!"}
env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
mdb = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
RID = uuid.uuid4().hex[:6]
PW = "Test2026!x"
BILL = {"client_type": "pj", "company_name": "TEST Firma ANRE SRL", "cui": "RO12345678", "regcom": "J37/1/2020", "hq_address": "Str. Test 1", "county": "Vaslui",
        "locality": "Vaslui", "country": "România", "rep_name": "TEST Rep", "phone": "0700000000"}
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n" + b"0" * 1000
ST = {}
COMPANY = {"name": "TEST Firma ANRE SRL", "cui": "RO999", "regcom": "J37/1/2020", "address": "Str. Test 1", "rep_name": "TEST Rep", "rep_role": "Administrator",
           "email": "t@example.com", "phone": "0700000000", "attest_no": "1/2024", "attest_types": "A1, B", "attest_valid": "2029-01-01"}
FUT = (date.today() + timedelta(days=400)).isoformat()
STAFF = [{"name": "TEST El1", "grade": "IIIB", "license": "L1", "license_valid": FUT}, {"name": "TEST El2", "grade": "IVA", "license": "L2", "license_valid": FUT}]


def login(creds):
    r = requests.post(f"{API}/auth/login", json=creds)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def register(H, tag):
    email = f"sub_iter24{tag}_{RID}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": PW, "name": f"TEST {tag}", "billing": BILL})
    assert r.status_code == 200, r.text
    uid = mdb.users.find_one({"email": email})["id"]
    assert requests.put(f"{API}/admin/subscribers/{uid}", json={"status": "active"}, headers=H).status_code == 200
    return uid, login({"email": email, "password": PW})


@pytest.fixture(scope="module")
def H():
    return login(ADMIN)


@pytest.fixture(scope="module")
def U(H):
    uid, h = register(H, "a")
    ST["uid"] = uid
    return h


@pytest.fixture(scope="module")
def U2(H):
    uid, h = register(H, "b")
    ST["uid2"] = uid
    return h


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    uids = [u["id"] for u in mdb.users.find({"email": {"$regex": f"^sub_iter24.*_{RID}@example.com$"}})]
    mdb.anre_dossiers.delete_many({"$or": [{"owner": {"$in": uids}}, {"id": {"$in": ST.get("admin_ids", [])}}]})
    for c in ("subscriptions", "invoices", "operators", "billing_profiles", "billing_history", "payment_transactions"):
        mdb[c].delete_many({"tenant": {"$in": uids}})
    mdb.users.delete_many({"id": {"$in": uids}})


def keys(d):
    return [i["key"] for i in d["items"]]


# --- create per kind
def test_create_kinds(U):
    r = requests.post(f"{API}/anre/dossiers", json={"kind": "bad"}, headers=U)
    assert r.status_code == 400
    exp = {"nou": ["cerere", "cert_constatator", "organigrama", "dotari", "personal", "autorizari", "revisal", "decl_9", "decl_10", "tarif"],
           "vizare": ["cerere", "cert_constatator", "organigrama", "dotari", "personal", "autorizari", "revisal", "decl_9", "decl_10", "atestat_original"],
           "modificare": ["cerere", "cert_constatator", "acte_modificare", "atestat_original"],
           "b_c1a": None, "altele": ["cerere", "alte"]}
    for k, ks in exp.items():
        r = requests.post(f"{API}/anre/dossiers", json={"kind": k}, headers=U)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["payment_status"] == "neplătit" and d["status"] == "Ciornă"
        assert d["price"]["net"] == 3200 and d["price"]["vat"] > 0 and d["price"]["total"] == round(3200 + d["price"]["vat"], 2)
        assert "_id" not in d
        if ks:
            assert keys(d) == ks, (k, keys(d))
        ST[k] = d["id"]


# --- unpaid gating
def test_unpaid_402(U):
    did = ST["nou"]
    assert requests.get(f"{API}/anre/dossiers/{did}", headers=U).status_code == 200
    assert requests.put(f"{API}/anre/dossiers/{did}", json={"company": COMPANY}, headers=U).status_code == 402
    assert requests.post(f"{API}/anre/dossiers/{did}/docs/cert_constatator", files={"file": ("a.pdf", PDF, "application/pdf")}, headers=U).status_code == 402
    assert requests.post(f"{API}/anre/dossiers/{did}/check", headers=U).status_code == 402
    assert requests.get(f"{API}/anre/dossiers/{did}/file/opis", headers=U).status_code == 402
    assert requests.get(f"{API}/anre/dossiers/{did}/package", headers=U).status_code == 402
    assert requests.post(f"{API}/anre/dossiers/{did}/ai", json={"text": "x"}, headers=U).status_code == 402
    assert requests.post(f"{API}/anre/dossiers/{did}/docs/organigrama/review", json={"approved": True}, headers=U).status_code == 402


def test_payment_confirm(H, U):
    did = ST["nou"]
    assert requests.post(f"{API}/admin/anre/{did}/payment", json={"reference": "OP1"}, headers=U).status_code == 403
    assert requests.post(f"{API}/admin/anre/{did}/payment", json={"reference": " "}, headers=H).status_code == 400
    r = requests.post(f"{API}/admin/anre/{did}/payment", json={"reference": "TEST OP 123"}, headers=H)
    assert r.status_code == 200 and r.json()["payment_status"] == "plătit"
    d = requests.get(f"{API}/anre/dossiers/{did}", headers=U).json()
    assert d["payment_status"] == "plătit" and d["payment"]["reference"] == "TEST OP 123"
    requests.post(f"{API}/admin/anre/{ST['b_c1a']}/payment", json={"reference": "OP2"}, headers=H)


def test_payment_nonexistent(H):
    r = requests.post(f"{API}/admin/anre/{uuid.uuid4()}/payment", json={"reference": "X"}, headers=H)
    ST["pay_nonexist"] = r.status_code
    assert r.status_code == 404, f"payment on nonexistent dossier returns {r.status_code}"


# --- isolation
def test_isolation(H, U2):
    did = ST["nou"]
    assert requests.get(f"{API}/anre/dossiers/{did}", headers=U2).status_code == 404
    assert requests.put(f"{API}/anre/dossiers/{did}", json={}, headers=U2).status_code == 404
    assert requests.get(f"{API}/anre/dossiers/{did}/ai", headers=U2).status_code == 404
    assert all(x["owner"] == ST["uid2"] for x in requests.get(f"{API}/anre/dossiers", headers=U2).json())
    lst = requests.get(f"{API}/anre/dossiers", headers=H).json()
    row = next(x for x in lst if x["id"] == did)
    for k in ("attest_status", "payment_status", "progress", "missing", "final_check", "company", "cui", "kind", "status"):
        assert k in row
    assert row["payment_status"] == "plătit"


# --- check report incomplete
def test_check_incomplete(U):
    did = ST["nou"]
    rep = requests.post(f"{API}/anre/dossiers/{did}/check", headers=U).json()
    assert rep["ok"] is False
    txt = " ".join(rep["incomplete"])
    assert "minimum 2 electricieni" in txt and "dotărilor" in txt and "Tipul de atestat" in txt and "lipsește" in txt
    assert len(rep["missing"]) == 4 and len(rep["review"]) == 6  # 6 generated pending
    d = requests.get(f"{API}/anre/dossiers/{did}", headers=U).json()
    assert d["status"] == "Documente lipsă" and d["final_check"]["ok"] is False
    r = requests.put(f"{API}/anre/dossiers/{did}", json={"status": "Pregătit pentru semnare"}, headers=U)
    assert r.status_code == 400
    assert requests.get(f"{API}/anre/dossiers/{did}/package", headers=U).status_code == 400


def test_issues_extension_and_expired(U):
    did = ST["b_c1a"]
    past = (date.today() - timedelta(days=5)).isoformat()
    r = requests.put(f"{API}/anre/dossiers/{did}", json={"company": {**COMPANY, "attest_types": "A1"}, "staff": [{"name": "TEST X", "grade": "II", "license_valid": past}]}, headers=U)
    assert r.status_code == 200
    rep = requests.post(f"{API}/anre/dossiers/{did}/check", headers=U).json()
    iss = " ".join(rep["issues"])
    assert "extindere de la B" in iss and "expirată" in iss


# --- uploads
def test_upload_magic_and_expiry(U):
    did = ST["nou"]
    r = requests.post(f"{API}/anre/dossiers/{did}/docs/cert_constatator", files={"file": ("a.pdf", b"NOTPDF" * 100, "application/pdf")}, headers=U)
    assert r.status_code == 400
    r = requests.post(f"{API}/anre/dossiers/{did}/docs/cert_constatator", files={"file": ("a.png", b"\xff\xd8\xff" + b"0" * 100, "image/png")}, headers=U)
    assert r.status_code == 400
    r = requests.post(f"{API}/anre/dossiers/{did}/docs/unknown", files={"file": ("a.pdf", PDF, "application/pdf")}, headers=U)
    assert r.status_code == 400
    old = (date.today() - timedelta(days=45)).isoformat()
    r = requests.post(f"{API}/anre/dossiers/{did}/docs/cert_constatator", files={"file": ("c.pdf", PDF, "application/pdf")}, data={"issued": old}, headers=U)
    assert r.status_code == 200
    it = next(i for i in r.json()["items"] if i["key"] == "cert_constatator")
    assert it["status"] == "expirat / nevalid" and it["file"] == "c.pdf"
    # small image -> manual verification
    r = requests.post(f"{API}/anre/dossiers/{did}/docs/revisal", files={"file": ("r.png", b"\x89PNG\r\n\x1a\n" + b"0" * 500, "image/png")}, headers=U)
    it = next(i for i in r.json()["items"] if i["key"] == "revisal")
    assert it["status"] == "necesită verificare manuală"


def test_upload_invalid_issued_date_bricks(U):
    """issued in RO format (dd.mm.yyyy) should be rejected (400), not crash every later GET"""
    did = ST["vizare"]
    requests.post(f"{API}/admin/anre/{did}/payment", json={"reference": "OPV"}, headers=login(ADMIN))
    r = requests.post(f"{API}/anre/dossiers/{did}/docs/cert_constatator", files={"file": ("c.pdf", PDF, "application/pdf")}, data={"issued": "12.01.2026"}, headers=U)
    g = requests.get(f"{API}/anre/dossiers/{did}", headers=U)
    ST["bad_date"] = (r.status_code, g.status_code)
    lst = requests.get(f"{API}/anre/dossiers", headers=U)
    ST["bad_date_list"] = lst.status_code
    # cleanup so other tests aren't affected
    mdb.anre_dossiers.update_one({"id": did}, {"$unset": {"docs.cert_constatator": ""}})
    assert r.status_code == 400 or g.status_code == 200, f"upload={r.status_code} get={g.status_code} list={lst.status_code}"


def test_review_validation(U):
    did = ST["nou"]
    assert requests.post(f"{API}/anre/dossiers/{did}/docs/autorizari/review", json={"status": "verificat"}, headers=U).status_code == 400  # not uploaded
    assert requests.post(f"{API}/anre/dossiers/{did}/docs/revisal/review", json={"status": "bogus"}, headers=U).status_code == 400


# --- full happy path
def test_full_flow_package(U):
    did = ST["nou"]
    r = requests.put(f"{API}/anre/dossiers/{did}", json={"company": COMPANY, "staff": STAFF, "equipment": [{"name": "TEST Megohmmetru", "serial": "S1"}], "target_types": ["A1", "B"]}, headers=U)
    assert r.status_code == 200, r.text
    fresh = date.today().isoformat()
    requests.post(f"{API}/anre/dossiers/{did}/docs/cert_constatator", files={"file": ("c.pdf", PDF, "application/pdf")}, data={"issued": fresh}, headers=U)
    for k in ("autorizari", "tarif"):
        assert requests.post(f"{API}/anre/dossiers/{did}/docs/{k}", files={"file": (f"{k}.pdf", PDF, "application/pdf")}, headers=U).status_code == 200
    for k in ("cert_constatator", "autorizari", "revisal", "tarif"):
        r = requests.post(f"{API}/anre/dossiers/{did}/docs/{k}/review", json={"status": "verificat"}, headers=U)
        assert r.status_code == 200, r.text
    for k in ("cerere", "organigrama", "dotari", "personal", "decl_9", "decl_10"):
        f = requests.get(f"{API}/anre/dossiers/{did}/file/{k}", headers=U)
        assert f.status_code == 200 and f.content[:4] == b"%PDF"
        r = requests.post(f"{API}/anre/dossiers/{did}/docs/{k}/review", json={"approved": True}, headers=U)
        assert r.status_code == 200
    d = r.json()
    assert d["progress"] == 100 and all(i["status"] == "verificat" for i in d["items"])
    rep = requests.post(f"{API}/anre/dossiers/{did}/check", headers=U).json()
    assert rep["ok"] is True, rep
    tok = U["Authorization"].split()[1]
    z = requests.get(f"{API}/anre/dossiers/{did}/package?auth={tok}")
    assert z.status_code == 200 and z.headers["content-type"].startswith("application/zip")
    names = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    for fo in ("01_Opis/", "02_Cerere/", "03_Anexe_si_declaratii/", "04_Documente_generate/", "05_Documente_client/", "06_Raport_verificare/"):
        assert any(n.startswith(fo) for n in names), (fo, names)
    assert requests.get(f"{API}/anre/dossiers/{did}/file/raport?auth={tok}").content[:4] == b"%PDF"
    r = requests.put(f"{API}/anre/dossiers/{did}", json={"status": "Pregătit pentru semnare"}, headers=U)
    assert r.status_code == 200 and r.json()["status"] == "Pregătit pentru semnare"


def test_status_depus_solutionat(U):
    did = ST["nou"]
    assert requests.put(f"{API}/anre/dossiers/{did}", json={"status": "Depus"}, headers=U).status_code == 400
    assert requests.put(f"{API}/anre/dossiers/{did}", json={"status": "Depus", "filing_no": "123"}, headers=U).status_code == 400
    r = requests.put(f"{API}/anre/dossiers/{did}", json={"status": "Depus", "filing_no": "TEST-123", "filing_date": date.today().isoformat()}, headers=U)
    assert r.status_code == 200 and r.json()["filing_no"] == "TEST-123"
    assert requests.put(f"{API}/anre/dossiers/{did}", json={"status": "Soluționat", "result": "aprobat"}, headers=U).status_code == 400
    assert requests.post(f"{API}/anre/dossiers/{did}/docs/decizie", files={"file": ("dec.pdf", PDF, "application/pdf")}, headers=U).status_code == 200
    assert requests.put(f"{API}/anre/dossiers/{did}", json={"status": "Soluționat"}, headers=U).status_code == 400
    r = requests.put(f"{API}/anre/dossiers/{did}", json={"status": "Soluționat", "result": "aprobat"}, headers=U)
    assert r.status_code == 200 and r.json()["status"] == "Soluționat" and r.json()["result"] == "aprobat"


def test_admin_exempt_unpaid(H):
    r = requests.post(f"{API}/anre/dossiers", json={"kind": "nou"}, headers=H)
    assert r.status_code == 200
    did = r.json()["id"]
    ST["admin_ids"] = [did]
    assert requests.put(f"{API}/anre/dossiers/{did}", json={"target_types": ["A1"]}, headers=H).status_code == 200
    assert requests.post(f"{API}/anre/dossiers/{did}/check", headers=H).status_code == 200


# --- AI
def test_ai_stream_and_history(U):
    did = ST["nou"]
    assert requests.post(f"{API}/anre/dossiers/{did}/ai", json={"text": " "}, headers=U).status_code == 400
    r = requests.post(f"{API}/anre/dossiers/{did}/ai", json={"text": "Ce documente mai lipsesc? Răspunde scurt."}, headers=U, stream=True, timeout=120)
    assert r.status_code == 200 and "text/event-stream" in r.headers["content-type"]
    txt, done, err = "", False, None
    for ln in r.iter_lines(decode_unicode=True):
        if ln and ln.startswith("data: "):
            j = json.loads(ln[6:])
            txt += j.get("t", "")
            done = done or j.get("done", False)
            err = err or j.get("error")
    assert err is None and done and len(txt) > 10, (err, txt[:200])
    h = requests.get(f"{API}/anre/dossiers/{did}/ai", headers=U).json()
    assert [m["role"] for m in h[-2:]] == ["user", "assistant"] and h[-1]["content"] == txt
    assert "ai" not in requests.get(f"{API}/anre/dossiers/{did}", headers=U).json()
