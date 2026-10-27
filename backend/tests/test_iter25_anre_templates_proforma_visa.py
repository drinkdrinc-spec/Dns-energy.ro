# Iteration 25: ANRE official templates (docx/pdf), auto proforma at Dosar ANRE order, dossier<->invoice payment sync, visa reminders cron
import io
import time
import uuid
import zipfile
from datetime import date, timedelta

import pytest
import requests
from docx import Document
from pymongo import MongoClient
from pypdf import PdfReader

BASE = None
for ln in open("/app/frontend/.env"):
    if ln.startswith("REACT_APP_BACKEND_URL="):
        BASE = ln.split("=", 1)[1].strip()
API = BASE.rstrip("/") + "/api"
ADMIN = {"email": "drinkdrinc@gmail.com", "password": "DEnergy2026!"}
env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
mdb = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
SECRET = env["WEBHOOK_CRON_SECRET"].strip('"')
RID = uuid.uuid4().hex[:6]
PW = "Test2026!x"
BILL = {"client_type": "pj", "company_name": "TEST Firma25 SRL", "cui": "RO12345678", "regcom": "J37/1/2020", "hq_address": "Str. Test 1", "county": "Vaslui",
        "locality": "Vaslui", "country": "România", "rep_name": "TEST Rep", "phone": "0700000000"}
FUT = (date.today() + timedelta(days=400)).isoformat()
COMPANY = {"name": "TEST Firma25 SRL", "cui": "RO25025", "regcom": "J37/1/2020", "address": "Str. Test 1", "rep_name": "TEST Rep", "rep_role": "Administrator",
           "email": "t@example.com", "phone": "0700000000", "attest_no": "1/2024", "attest_types": "A1, B", "attest_valid": "2029-01-01"}
STAFF = [{"name": "TEST Electrician Unu", "grade": "IIIB", "license": "L1", "license_valid": FUT}, {"name": "TEST Electrician Doi", "grade": "IVA", "license": "L2", "license_valid": FUT},
         {"name": "TEST Electrician Trei", "grade": "IIA", "license": "L3", "license_valid": FUT}]
ST = {}


def login(creds):
    r = requests.post(f"{API}/auth/login", json=creds)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def register(H, tag):
    email = f"sub_iter25{tag}_{RID}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": PW, "name": f"TEST {tag}", "billing": BILL})
    assert r.status_code == 200, r.text
    uid = mdb.users.find_one({"email": email})["id"]
    assert requests.put(f"{API}/admin/subscribers/{uid}", json={"status": "active"}, headers=H).status_code == 200
    return uid, login({"email": email, "password": PW})


def make_docx():
    doc = Document()
    doc.add_paragraph("Firma: {{firma}} CUI: {{cui}}")
    doc.add_paragraph("Data: {{data}} Necunoscut: {{xyz_unknown}}")
    t = doc.add_table(rows=2, cols=3)
    t.rows[0].cells[0].text, t.rows[0].cells[1].text, t.rows[0].cells[2].text = "Nr", "Nume", "Grad"
    t.rows[1].cells[0].text, t.rows[1].cells[1].text, t.rows[1].cells[2].text = "{{p.nr}}", "{{p.name}}", "{{p.grade}}"
    b = io.BytesIO()
    doc.save(b)
    return b.getvalue()


@pytest.fixture(scope="module")
def H():
    return login(ADMIN)


@pytest.fixture(scope="module")
def U(H):
    uid, h = register(H, "a")
    ST["uid"] = uid
    return h


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    saved = list(mdb.anre_templates.find({"key": "personal"}))
    yield
    uids = [u["id"] for u in mdb.users.find({"email": {"$regex": f"^sub_iter25.*_{RID}@example.com$"}})]
    mdb.anre_dossiers.delete_many({"owner": {"$in": uids}})
    for c in ("subscriptions", "invoices", "operators", "billing_profiles", "billing_history", "payment_transactions"):
        mdb[c].delete_many({"tenant": {"$in": uids}})
    mdb.reminders.delete_many({"id": {"$regex": "^visa:(" + "|".join(uids or ["none"]) + "):"}})
    mdb.users.delete_many({"id": {"$in": uids}})
    mdb.anre_templates.delete_many({"key": "personal"})
    for s in saved:
        mdb.anre_templates.insert_one(s)


# ---- Auto proforma at order
def test_create_dossier_issues_proforma(U):
    r = requests.post(f"{API}/anre/dossiers", json={"kind": "nou", "target_types": ["A1"]}, headers=U)
    assert r.status_code == 200, r.text
    d = r.json()
    ST["did"] = d["id"]
    assert d["invoice_id"] and d["invoice_number"].startswith(f"DEN-PF-{date.today().year}-")
    assert d["transfer"]["amount"] == d["price"]["total"] and d["transfer"]["reference"] == d["invoice_number"]
    inv = mdb.invoices.find_one({"id": d["invoice_id"]})
    assert inv["service"] is True and inv["net"] == 3200 and inv["status"] == "în așteptarea plății"
    assert inv["vat"] == round(3200 * inv["vat_rate"] / 100, 2) and inv["total"] == round(3200 + inv["vat"], 2)
    ST["inv"] = d["invoice_id"]


def test_proforma_pdf(U):
    r = requests.get(f"{API}/billing/invoices/{ST['inv']}/pdf", headers=U)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    txt = "".join(p.extract_text() for p in PdfReader(io.BytesIO(r.content)).pages)
    assert "Dosar ANRE" in txt and "3 200,00" in txt and "3 872,00" in txt, txt[:300]


def test_unpaid_dossier_gated(U):
    r = requests.get(f"{API}/anre/dossiers/{ST['did']}/file/personal", headers=U)
    assert r.status_code == 402


# ---- dossier payment -> invoice paid
def test_dossier_payment_marks_invoice_paid(U, H):
    sub_before = mdb.subscriptions.find_one({"tenant": ST["uid"]}, {"_id": 0})
    r = requests.post(f"{API}/admin/anre/{ST['did']}/payment", json={"reference": "TEST OP 25"}, headers=H)
    assert r.status_code == 200
    time.sleep(1)
    inv = mdb.invoices.find_one({"id": ST["inv"]})
    assert inv["status"] == "plătită", inv["status"]
    assert inv["payments"][-1]["reference"] == "TEST OP 25"
    d = requests.get(f"{API}/anre/dossiers/{ST['did']}", headers=U).json()
    assert d["payment_status"] == "plătit"
    assert mdb.subscriptions.find_one({"tenant": ST["uid"]}, {"_id": 0}) == sub_before
    # idempotent second confirmation
    assert requests.post(f"{API}/admin/anre/{ST['did']}/payment", json={"reference": "TEST OP 25b"}, headers=H).status_code == 200
    assert len(mdb.invoices.find_one({"id": ST["inv"]})["payments"]) == 1


# ---- invoice payment -> dossier paid, no subscription change
def test_invoice_payment_marks_dossier_paid(U, H):
    d = requests.post(f"{API}/anre/dossiers", json={"kind": "vizare", "target_types": ["A1"]}, headers=U).json()
    sub_before = mdb.subscriptions.find_one({"tenant": ST["uid"]}, {"_id": 0})
    inv = mdb.invoices.find_one({"id": d["invoice_id"]})
    r = requests.post(f"{API}/admin/invoices/{d['invoice_id']}/payment", json={"amount": inv["total"], "reference": "OP-INV-25", "justification": "test", "method": "transfer bancar"}, headers=H)
    assert r.status_code == 200 and r.json()["activated"] is True, r.text
    d2 = requests.get(f"{API}/anre/dossiers/{d['id']}", headers=U).json()
    assert d2["payment_status"] == "plătit"
    assert mdb.invoices.find_one({"id": d["invoice_id"]})["status"] == "plătită"
    assert mdb.subscriptions.find_one({"tenant": ST["uid"]}, {"_id": 0}) == sub_before


# ---- templates admin
def test_templates_forbidden_for_subscriber(U):
    assert requests.get(f"{API}/admin/anre/templates", headers=U).status_code == 403
    assert requests.post(f"{API}/admin/anre/templates/personal", files={"file": ("x.docx", make_docx(), "application/octet-stream")}, headers=U).status_code == 403
    assert requests.delete(f"{API}/admin/anre/templates/personal", headers=U).status_code == 403
    assert requests.get(f"{API}/admin/anre/templates/personal/file", headers=U).status_code == 403


def test_template_invalid_rejected(H):
    assert requests.post(f"{API}/admin/anre/templates/personal", files={"file": ("x.txt", b"hello", "text/plain")}, headers=H).status_code == 400
    assert requests.post(f"{API}/admin/anre/templates/personal", files={"file": ("x.docx", b"PKnotadocx", "application/octet-stream")}, headers=H).status_code == 400
    assert requests.post(f"{API}/admin/anre/templates/unknown", files={"file": ("x.docx", make_docx(), "application/octet-stream")}, headers=H).status_code == 400


def test_template_upload_list_file(H):
    r = requests.post(f"{API}/admin/anre/templates/personal", files={"file": ("Anexa7.docx", make_docx(), "application/octet-stream")}, headers=H)
    assert r.status_code == 200, r.text
    it = {i["key"]: i for i in r.json()["items"]}
    assert set(it) == {"cerere", "organigrama", "dotari", "personal", "decl_9", "decl_10"}
    t = it["personal"]["template"]
    assert t["name"] == "Anexa7.docx" and "firma" in t["fields"] and "p.name" in t["fields"]
    assert "xyz_unknown" not in t["matched"] and "firma" in t["matched"]
    f = requests.get(f"{API}/admin/anre/templates/personal/file", headers=H)
    assert f.status_code == 200 and f.content.startswith(b"PK")


def test_dossier_personal_uses_template(U):
    r = requests.put(f"{API}/anre/dossiers/{ST['did']}", json={"company": COMPANY, "staff": STAFF, "equipment": [{"name": "Multimetru", "serial": "S1"}]}, headers=U)
    assert r.status_code == 200, r.text
    f = requests.get(f"{API}/anre/dossiers/{ST['did']}/file/personal", headers=U)
    assert f.status_code == 200 and f.content.startswith(b"PK"), f.headers
    doc = Document(io.BytesIO(f.content))
    body = "\n".join(p.text for p in doc.paragraphs)
    assert "TEST Firma25 SRL" in body and "RO25025" in body and "{{" not in body.replace("{{xyz_unknown}}", "")
    rows = doc.tables[0].rows
    assert len(rows) == 1 + len(STAFF)
    assert [r.cells[1].text for r in rows[1:]] == [s["name"] for s in STAFF]
    assert [r.cells[0].text for r in rows[1:]] == ["1", "2", "3"]
    # non-templated still PDF
    g = requests.get(f"{API}/anre/dossiers/{ST['did']}/file/dotari", headers=U)
    assert g.status_code == 200 and g.content.startswith(b"%PDF")


def test_package_contains_docx(U, H):
    # force check ok so package can be generated
    d = mdb.anre_dossiers.find_one({"id": ST["did"]})
    from_items = requests.get(f"{API}/anre/dossiers/{ST['did']}", headers=U).json()["items"]
    docs = {}
    for i in from_items:
        docs[i["key"]] = {"approved": True, "status": "verificat"} if i["source"] != "client" else {"status": "verificat", "path": None}
    # upload minimal client files via API is heavy; instead check doc_bytes via package only if ok
    pdf = b"%PDF-1.4\n%%EOF\n" + b"0" * 1000
    for i in from_items:
        if i["source"] == "client":
            requests.post(f"{API}/anre/dossiers/{ST['did']}/docs/{i['key']}", files={"file": ("a.pdf", pdf, "application/pdf")}, headers=U)
            requests.post(f"{API}/anre/dossiers/{ST['did']}/docs/{i['key']}/review", json={"status": "verificat"}, headers=H)
        else:
            requests.post(f"{API}/anre/dossiers/{ST['did']}/docs/{i['key']}/review", json={"approved": True}, headers=U)
    r = requests.get(f"{API}/anre/dossiers/{ST['did']}/package", headers=U)
    assert r.status_code == 200, r.text
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert any(n.endswith("personal.docx") for n in names), names


def test_template_delete_falls_back(H, U):
    r = requests.delete(f"{API}/admin/anre/templates/personal", headers=H)
    assert r.status_code == 200
    assert {i["key"]: i for i in r.json()["items"]}["personal"]["template"] is None
    f = requests.get(f"{API}/anre/dossiers/{ST['did']}/file/personal", headers=U)
    assert f.status_code == 200 and f.content.startswith(b"%PDF")
    assert requests.get(f"{API}/admin/anre/templates/personal/file", headers=H).status_code == 404


# ---- Visa
OP = {"company": "TEST Firma25 SRL", "cui": "RO25025", "regcom": "J1", "contact_name": "TEST C", "contact_email": None, "contact_phone": "0700",
      "attest_no": "25/2025", "attest_types": ["A1"], "holder_name": "TEST Firma25 SRL", "attest_valid": FUT}


def test_operator_visa_save_and_reset(U, H):
    OP["contact_email"] = "delivered@resend.dev"
    vd = (date.today() + timedelta(days=30)).isoformat()
    r = requests.put(f"{API}/operator", json={**OP, "visa_date": vd}, headers=U)
    assert r.status_code == 200, r.text
    o = r.json()["operator"]
    assert o["visa_date"] == vd and o["visa_confirmed"] is False
    assert requests.put(f"{API}/operator", json={**OP, "visa_date": "31-31-2020"}, headers=U).status_code == 400
    r = requests.post(f"{API}/admin/operators/{ST['uid']}/visa", json={"visa_date": vd, "confirmed": True}, headers=H)
    assert r.status_code == 200 and r.json()["visa_confirmed"] is True
    assert requests.post(f"{API}/admin/operators/{ST['uid']}/visa", json={"confirmed": True}, headers=U).status_code == 403
    assert requests.post(f"{API}/admin/operators/nonexist/visa", json={"visa_date": vd}, headers=H).status_code == 404
    # same date save keeps confirmation
    o = requests.put(f"{API}/operator", json={**OP, "visa_date": vd}, headers=U).json()["operator"]
    assert o["visa_confirmed"] is True
    # changed date resets
    vd2 = (date.today() + timedelta(days=31)).isoformat()
    o = requests.put(f"{API}/operator", json={**OP, "visa_date": vd2}, headers=U).json()["operator"]
    assert o["visa_confirmed"] is False
    ST["vd"] = vd


def test_cron_requires_secret():
    assert requests.post(f"{API}/cron/anre-visa").status_code == 401
    assert requests.post(f"{API}/cron/anre-visa", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_cron_visa_reminds_once(U, H):
    # unconfirmed -> no reminder
    hdr = {"Authorization": f"Bearer {SECRET}"}
    assert requests.post(f"{API}/cron/anre-visa", headers=hdr).json()["status"] == "accepted"
    time.sleep(4)
    assert not mdb.operators.find_one({"tenant": ST["uid"]}).get("visa_reminded_at")
    requests.post(f"{API}/admin/operators/{ST['uid']}/visa", json={"visa_date": ST["vd"], "confirmed": True}, headers=H)
    assert requests.post(f"{API}/cron/anre-visa", headers=hdr).json()["status"] == "accepted"
    time.sleep(6)
    o = mdb.operators.find_one({"tenant": ST["uid"]})
    assert o.get("visa_reminded_at"), "not reminded"
    key = f"visa:{ST['uid']}:{ST['vd']}"
    assert mdb.reminders.count_documents({"id": key}) == 1
    first = o["visa_reminded_at"]
    requests.post(f"{API}/cron/anre-visa", headers=hdr)
    time.sleep(5)
    assert mdb.reminders.count_documents({"id": key}) == 1
    assert mdb.operators.find_one({"tenant": ST["uid"]})["visa_reminded_at"] == first
    # duplicate run id
    rid = "TEST-run-" + RID
    assert requests.post(f"{API}/cron/anre-visa", headers={**hdr, "x-webhook-id": rid}).json()["status"] == "accepted"
    assert requests.post(f"{API}/cron/anre-visa", headers={**hdr, "x-webhook-id": rid}).json()["status"] == "duplicate"
    mdb.cron_runs.delete_many({"id": rid})


def test_cron_visa_far_not_reminded(U, H):
    far = (date.today() + timedelta(days=90)).isoformat()
    requests.post(f"{API}/admin/operators/{ST['uid']}/visa", json={"visa_date": far, "confirmed": True}, headers=H)
    requests.post(f"{API}/cron/anre-visa", headers={"Authorization": f"Bearer {SECRET}"})
    time.sleep(5)
    assert mdb.reminders.count_documents({"id": f"visa:{ST['uid']}:{far}"}) == 0
