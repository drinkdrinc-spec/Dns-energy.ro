# Iteration 23: Etapa 2 tariffs + OP transfer checkout, ANRE operator attest gating (new/legacy), contract online signing, offer from dossier
import os
import io
import uuid
import base64
import random
import hashlib
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient
from PIL import Image

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
BILL = {"client_type": "pj", "company_name": "TEST Firma SRL", "cui": "RO12345678", "regcom": "J37/1/2020", "hq_address": "Str. Test 1", "county": "Vaslui",
        "locality": "Vaslui", "country": "România", "rep_name": "TEST Rep", "phone": "0700000000"}
OPDATA = {"company": "TEST Firma SRL", "cui": f"RO{RID}", "regcom": "J37/1/2020", "contact_name": "TEST Contact", "contact_phone": "0700000000",
          "contact_email": "c@example.com", "attest_no": "1234/2025", "attest_types": ["A1", "B", "ZZ"], "holder_name": "TEST Firma SRL"}
ST = {}
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def login(creds):
    r = requests.post(f"{API}/auth/login", json=creds)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def me(h):
    r = requests.get(f"{API}/auth/me", headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    return j.get("plan") or j.get("user", {}).get("plan")


def register(H, tag):
    email = f"sub_iter23{tag}_{RID}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": PW, "name": f"TEST {tag}", "billing": BILL})
    assert r.status_code == 200 and r.json().get("pending"), r.text
    uid = mdb.users.find_one({"email": email})["id"]
    a = requests.put(f"{API}/admin/subscribers/{uid}", json={"status": "active"}, headers=H)
    assert a.status_code == 200, a.text
    return uid, login({"email": email, "password": PW})


@pytest.fixture(scope="module")
def H():
    return login(ADMIN)


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    uids = [u["id"] for u in mdb.users.find({"email": {"$regex": f"^sub_iter23.*_{RID}@example.com$"}})]
    for c in ("subscriptions", "invoices", "operators", "billing_profiles", "billing_history", "payment_transactions"):
        mdb[c].delete_many({"tenant": {"$in": uids}})
    mdb.users.delete_many({"id": {"$in": uids}})
    mdb.billing_config.update_one({"id": "main"}, {"$set": {"attest_block_existing": False}})


# --- plans + config
def test_plans_prices_transfer(H):
    j = requests.get(f"{API}/billing/plans", headers=H).json()
    prices = {p["code"]: p["price"] for p in j["plans"]}
    assert prices == {"start": 500, "pro": 900, "full": 1250}
    assert j["payment_mode"] == "transfer" and j["default_months"] == 1 and j["online_payment"] is False


def test_billing_config_validation(H):
    assert requests.put(f"{API}/admin/billing-config", json={"payment_mode": "cash"}, headers=H).status_code == 400
    assert requests.put(f"{API}/admin/billing-config", json={"default_months": 5}, headers=H).status_code == 400
    r = requests.put(f"{API}/admin/billing-config", json={"payment_mode": "transfer", "default_months": 1}, headers=H)
    assert r.status_code == 200, r.text


def test_platform_admin_exempt(H):
    p = me(H)
    assert p["active"] and p["exempt"] and "*" in p["features"]


# --- new subscriber flow
def test_checkout_transfer(H):
    uid, A = register(H, "a")
    ST.update(a=uid, A=A)
    r = requests.post(f"{API}/billing/checkout", json={"plan": "pro"}, headers=A)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["checkout_url"] is None
    assert j["transfer"]["amount"] == j["invoice"]["total"] == pytest.approx(1089.0)
    assert j["transfer"]["reference"] == j["invoice"]["number"]
    assert j["invoice"]["months"] == 1 if "months" in j["invoice"] else True
    ST["inv"] = j["invoice"]["id"]
    ST["transfer"] = j["transfer"]
    assert me(A)["active"] is False


def test_payment_activates_sub_but_attest_blocks(H):
    r = requests.post(f"{API}/admin/invoices/{ST['inv']}/payment", json={"amount": 1089, "reference": "OP TEST 1", "justification": "TEST încasare"}, headers=H)
    assert r.status_code == 200 and r.json()["activated"], r.text
    sub = requests.get(f"{API}/billing/me", headers=ST["A"]).json()["subscription"]
    assert sub["status"] == "activ" and sub["plan"] == "pro"
    p = me(ST["A"])
    assert p["active"] is False and p["features"] == [] and "atestat" in p["status"] and p["attest"] == "lipsă" and p["attest_legacy"] is False
    # write blocked
    assert requests.post(f"{API}/offers", json={"beneficiary": {"name": "TEST x"}, "items": []}, headers=ST["A"]).status_code in (402, 403)


def test_operator_save_validation_and_pending():
    A = ST["A"]
    r = requests.put(f"{API}/operator", json={"company": "X"}, headers=A)
    assert r.status_code == 400 and "CUI" in r.json()["detail"]
    r = requests.put(f"{API}/operator", json={**OPDATA, "attest_types": []}, headers=A)
    assert r.status_code == 400 and "Tipul" in r.json()["detail"]
    r = requests.put(f"{API}/operator", json=OPDATA, headers=A)
    assert r.status_code == 200, r.text
    o = r.json()["operator"]
    assert o["status"] == "în așteptare" and o["attest_types"] == ["A1", "B"] and o["has_document"] is False and "doc_path" not in o
    assert requests.get(f"{API}/operator", headers=A).json()["operator"]["cui"] == OPDATA["cui"]
    assert me(A)["active"] is False


def test_approve_without_doc_400(H):
    r = requests.post(f"{API}/admin/operators/{ST['a']}/decision", json={"status": "aprobat"}, headers=H)
    assert r.status_code == 400


def test_upload_doc():
    A = ST["A"]
    bad = requests.post(f"{API}/operator/document", files={"file": ("a.txt", b"hello", "text/plain")}, headers=A)
    assert bad.status_code == 400
    r = requests.post(f"{API}/operator/document", files={"file": ("atestat.pdf", PDF, "application/pdf")}, headers=A)
    assert r.status_code == 200, r.text
    o = r.json()["operator"]
    assert o["has_document"] and o["status"] == "în așteptare" and o["doc_name"] == "atestat.pdf"
    d = requests.get(f"{API}/operator/document", headers=A)
    assert d.status_code == 200 and d.content.startswith(b"%PDF")


def test_reject_requires_notes(H):
    assert requests.post(f"{API}/admin/operators/{ST['a']}/decision", json={"status": "respins"}, headers=H).status_code == 400
    assert requests.post(f"{API}/admin/operators/{ST['a']}/decision", json={"status": "expirat", "notes": " "}, headers=H).status_code == 400
    assert requests.post(f"{API}/admin/operators/{ST['a']}/decision", json={"status": "bogus"}, headers=H).status_code == 400
    r = requests.post(f"{API}/admin/operators/{ST['a']}/decision", json={"status": "respins", "notes": "TEST document neclar"}, headers=H)
    assert r.status_code == 200 and r.json()["status"] == "respins"
    p = me(ST["A"])
    assert p["active"] is False and p["attest"] == "respins"


def test_admin_list_and_doc(H):
    lst = requests.get(f"{API}/admin/operators", headers=H).json()
    o = next(x for x in lst if x["tenant"] == ST["a"])
    assert o["status"] == "respins" and o["admin_notes"] == "TEST document neclar" and "doc_path" not in o and o["has_document"]
    d = requests.get(f"{API}/admin/operators/{ST['a']}/document", headers=H)
    assert d.status_code == 200 and d.content.startswith(b"%PDF")
    tok = H["Authorization"].split(" ")[1]
    assert requests.get(f"{API}/admin/operators/{ST['a']}/document?auth={tok}").status_code == 200


def test_approve_grants_access(H):
    r = requests.post(f"{API}/admin/operators/{ST['a']}/decision", json={"status": "aprobat", "notes": "ok"}, headers=H)
    assert r.status_code == 200
    p = me(ST["A"])
    assert p["active"] is True and p["attest"] == "aprobat" and len(p["features"]) > 0 and p["code"] == "pro"


def test_attest_valid_past_expires(H):
    A = ST["A"]
    past = (datetime.now(timezone.utc) - timedelta(days=3)).date().isoformat()
    r = requests.put(f"{API}/operator", json={**OPDATA, "attest_valid": past}, headers=A)
    assert r.json()["operator"]["status"] == "în așteptare"  # changed => reverify
    assert me(A)["active"] is False
    requests.post(f"{API}/admin/operators/{ST['a']}/decision", json={"status": "aprobat"}, headers=H)
    p = me(A)
    assert p["active"] is False and p["attest"] == "expirat"
    fut = (datetime.now(timezone.utc) + timedelta(days=300)).date().isoformat()
    requests.put(f"{API}/operator", json={**OPDATA, "attest_valid": fut}, headers=A)
    requests.post(f"{API}/admin/operators/{ST['a']}/decision", json={"status": "aprobat"}, headers=H)
    assert me(A)["active"] is True


# --- isolation
def test_operator_isolation(H):
    uid, B = register(H, "b")
    ST.update(b=uid, B=B)
    assert requests.get(f"{API}/operator", headers=B).json()["operator"] is None
    assert requests.get(f"{API}/operator/document", headers=B).status_code == 404
    assert requests.get(f"{API}/admin/operators", headers=B).status_code == 403
    assert requests.get(f"{API}/admin/operators/{ST['a']}/document", headers=B).status_code == 403
    assert requests.post(f"{API}/admin/operators/{ST['a']}/decision", json={"status": "respins", "notes": "x"}, headers=B).status_code == 403
    assert requests.get(f"{API}/admin/attest-config", headers=B).status_code == 403
    assert requests.put(f"{API}/admin/attest-config", json={"attest_block_existing": True}, headers=B).status_code == 403
    assert requests.put(f"{API}/admin/billing-config", json={"default_months": 3}, headers=B).status_code == 403


# --- legacy rule
def test_legacy_rule(H):
    vu = (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat()
    r = requests.post(f"{API}/admin/subscribers/{ST['b']}/plan", json={"plan": "start", "valid_until": vu, "status": "activ", "justification": "TEST"}, headers=H)
    assert r.status_code == 200, r.text
    assert me(ST["B"])["active"] is False  # new account
    cfg = requests.get(f"{API}/admin/attest-config", headers=H).json()
    assert cfg["attest_block_existing"] is False and cfg["attest_cutoff"]
    mdb.users.update_one({"id": ST["b"]}, {"$set": {"created_at": "2025-01-01T00:00:00+00:00"}})
    p = me(ST["B"])
    assert p["active"] is True and p["attest_legacy"] is True and p["attest"] == "lipsă"
    try:
        assert requests.put(f"{API}/admin/attest-config", json={"attest_block_existing": True}, headers=H).json()["attest_block_existing"] is True
        p = me(ST["B"])
        assert p["active"] is False and p["features"] == []
    finally:
        assert requests.put(f"{API}/admin/attest-config", json={"attest_block_existing": False}, headers=H).json()["attest_block_existing"] is False
    assert me(ST["B"])["active"] is True


def test_legacy_rejected_blocked(H):
    requests.put(f"{API}/operator", json={**OPDATA, "cui": "RO99"}, headers=ST["B"])
    assert me(ST["B"])["active"] is True  # în așteptare still legacy
    requests.post(f"{API}/operator/document", files={"file": ("a.png", b"\x89PNG" + b"0" * 100, "image/png")}, headers=ST["B"])
    requests.post(f"{API}/admin/operators/{ST['b']}/decision", json={"status": "respins", "notes": "TEST"}, headers=H)
    p = me(ST["B"])
    assert p["active"] is False and p["attest_legacy"] is False


# --- contract signing
def _png():
    img = Image.new("RGB", (300, 120), "white"); px = img.load()
    for _ in range(4000):
        px[random.randrange(300), random.randrange(120)] = (0, 0, random.randrange(255))
    b = io.BytesIO(); img.save(b, "PNG")
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


def test_contract_sign_e2e(H):
    o = requests.post(f"{API}/offers", json={"title": "TEST semnare", "beneficiary": {"kind": "PF", "name": "TEST Semnatar", "email": "t@example.com"},
                                              "items": [{"category": "montaj", "kind": "serviciu", "name": "Montaj", "qty": 1, "unit": "lot", "unit_price": 1000}]}, headers=H).json()
    assert requests.post(f"{API}/offers/{o['id']}/status", json={"status": "Acceptată"}, headers=H).status_code == 200
    c = requests.post(f"{API}/offers/{o['id']}/contract", json={"payment": {"mode": "integral", "due_days": 5}}, headers=H)
    assert c.status_code == 200, c.text
    cid = c.json()["id"]
    ST["cid"] = cid
    assert requests.post(f"{API}/contracts/{cid}/sign", json={"signer": {"name": "TEST", "email": "bad"}}, headers=H).status_code == 400
    r = requests.post(f"{API}/contracts/{cid}/sign", json={"signer": {"name": "TEST Semnatar", "email": "t@example.com", "phone": "0700"}}, headers=H)
    assert r.status_code == 200, r.text
    j = r.json()
    tok = j["token"]
    assert j["module"] == "contracts" and j["status"] == "De trimis"
    assert requests.get(f"{API}/contracts/{cid}", headers=H).json()["status"] == "Trimis la semnare"
    lst = requests.get(f"{API}/contracts/{cid}/sign-requests", headers=H).json()
    assert len(lst) == 1 and lst[0]["signer_email"] == "t@example.com"
    assert requests.get(f"{API}/contracts/{cid}/signed-pdf", headers=H).status_code == 404
    assert requests.get(f"{API}/public/sign/{tok}", ).status_code == 200
    rq = mdb.sign_requests.find_one({"token_hash": hashlib.sha256(tok.encode()).hexdigest()})
    mdb.sign_requests.update_one({"id": rq["id"]}, {"$set": {"otp_hash": hashlib.sha256(f"{rq['id']}:123456".encode()).hexdigest(),
                                                             "otp_exp": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(), "otp_attempts": 0}})
    s = requests.post(f"{API}/public/sign/{tok}/sign", json={"otp": "123456", "intent": True, "declared_name": "TEST Semnatar", "signature": _png()})
    assert s.status_code == 200, s.text
    cc = requests.get(f"{API}/contracts/{cid}", headers=H).json()
    assert cc["status"] == "Semnat" and cc.get("signed", {}).get("storage_path")
    pdf = requests.get(f"{API}/contracts/{cid}/signed-pdf", headers=H)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert mdb.documents.find_one({"dossier_id": cid, "kind": "Semnat electronic"})
    assert requests.post(f"{API}/public/sign/{tok}/sign", json={"otp": "123456", "intent": True, "declared_name": "x", "signature": _png()}).status_code in (400, 409, 410)


# --- offer from dossier
def test_offer_from_dossier(H):
    assert requests.post(f"{API}/offers/from-dossier", json={"pros_id": "nope"}, headers=H).status_code == 404
    pid = "e98aaf0f-aa11-4d92-902c-abeafd3f80b1"
    nxt = requests.get(f"{API}/offers/numbering", headers=H).json()["offer_next"]
    r = requests.post(f"{API}/offers/from-dossier", json={"pros_id": pid}, headers=H)
    assert r.status_code == 200, r.text
    o = r.json()
    ST["fd"] = o["id"]
    assert o["number"] == nxt and o["status"] == "Ciornă" and o["pros_id"] == pid
    cats = [i["category"] for i in o["items"]]
    pan = [i for i in o["items"] if i["category"] == "panouri"]
    assert len(pan) == 1 and pan[0]["qty"] == 24 and pan[0]["manufacturer"] == "Aiko" and pan[0]["power"] == "475 W"
    inv = [i for i in o["items"] if i["category"] == "invertor"]
    print("INVERTERS", inv)
    assert inv[0]["manufacturer"] == "Solis" and inv[0]["model"].startswith("S6-")
    bat = [i for i in o["items"] if i["category"] == "baterii"]
    print("BATTERIES", bat)
    assert len(bat) == 1 and bat[0]["manufacturer"] == "Deye"
    assert cats[-3:] == ["montaj", "probe", "dosar"]
    assert o["beneficiary"].get("name")
    print("BEN", o["beneficiary"], "TITLE", o["title"])
    n2 = requests.get(f"{API}/offers/numbering", headers=H).json()["offer_next"]
    assert n2 == nxt + 1
