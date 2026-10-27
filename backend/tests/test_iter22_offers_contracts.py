# Iteration 22: Oferte de preț + Contracte (numbering, totals, PDF, status, contract gen, versions, template, isolation, feature gate)
import os
import io
import uuid
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE:
    for ln in open("/app/frontend/.env"):
        if ln.startswith("REACT_APP_BACKEND_URL="):
            BASE = ln.split("=", 1)[1].strip()
BASE = BASE.rstrip("/")
API = f"{BASE}/api"
ADMIN = {"email": "drinkdrinc@gmail.com", "password": "DEnergy2026!"}

ITEMS = [
    {"category": "panouri", "kind": "echipament", "name": "Panouri", "manufacturer": "Jinko", "model": "Tiger", "power": "450W", "qty": 10, "unit": "buc", "unit_price": 500, "warranty": "25 ani"},
    {"category": "invertor", "kind": "echipament", "name": "Invertor", "manufacturer": "Huawei", "model": "SUN2000", "qty": 1, "unit": "buc", "unit_price": 5000, "warranty": "10 ani"},
    {"category": "montaj", "kind": "serviciu", "name": "Montaj", "qty": 1, "unit": "lot", "unit_price": 3000},
]
BEN = {"kind": "PF", "name": "TEST Ion Popescu", "cui_cnp": "1800101123456", "ci_series": "XV", "ci_number": "123456", "address": "Str. Test 1, Vaslui",
       "install_address": "Str. Test 1, Vaslui", "phone": "0700000000", "email": "test@example.com"}
ST = {}


def login(creds):
    r = requests.post(f"{API}/auth/login", json=creds)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def H():
    return login(ADMIN)


def mk(H, **kw):
    r = requests.post(f"{API}/offers", json={"beneficiary": BEN, "items": ITEMS, "title": "TEST Sistem 4.5 kWp", **kw}, headers=H)
    assert r.status_code == 200, r.text
    return r.json()


# --- numbering
def test_numbering_start(H):
    r = requests.get(f"{API}/offers/numbering", headers=H)
    assert r.status_code == 200
    assert r.json() == {"offer_next": 249, "contract_next": 93}


def test_create_first_249_then_250_and_dup(H):
    a = mk(H)
    assert a["number"] == 249 and a["status"] == "Ciornă" and a["version"] == 1
    b = mk(H)
    assert b["number"] == 250
    d = requests.post(f"{API}/offers/{a['id']}/duplicate", headers=H).json()
    assert d["number"] == 251 and d["duplicated_from"] == 249 and d["beneficiary"]["name"] == BEN["name"]
    ST.update(a=a["id"], b=b["id"], d=d["id"])


def test_list_fields(H):
    r = requests.get(f"{API}/offers", headers=H).json()
    o = next(x for x in r if x["id"] == ST["a"])
    for k in ("number", "beneficiary", "date", "net", "gross", "status", "contract_id"):
        assert k in o
    assert o["beneficiary"] == BEN["name"] and o["net"] == 13000 and o["gross"] == 15730
    nums = [x["number"] for x in r]
    assert len(nums) == len(set(nums))


def test_delete_rules(H):
    r = requests.delete(f"{API}/offers/{ST['b']}", headers=H)
    assert r.status_code == 200
    assert requests.get(f"{API}/offers/{ST['b']}", headers=H).status_code == 404
    # number not reused
    c = mk(H)
    assert c["number"] == 252
    ST["c"] = c["id"]
    requests.post(f"{API}/offers/{c['id']}/status", json={"status": "Trimisă"}, headers=H)
    assert requests.delete(f"{API}/offers/{c['id']}", headers=H).status_code == 400


def test_numbering_set_rules(H):
    assert requests.put(f"{API}/offers/numbering", json={"offer_next": 250}, headers=H).status_code == 400
    assert requests.put(f"{API}/offers/numbering", json={"offer_next": 252}, headers=H).status_code == 400
    r = requests.put(f"{API}/offers/numbering", json={"offer_next": 260}, headers=H)
    assert r.status_code == 200 and r.json()["offer_next"] == 260
    e = mk(H)
    assert e["number"] == 260
    ST["e"] = e["id"]


# --- totals
def test_totals_split_discount_vat(H):
    t = requests.get(f"{API}/offers/{ST['a']}", headers=H).json()["totals"]
    assert t["equipment"] == 10000 and t["services"] == 3000 and t["net"] == 13000 and t["vat"] == 2730 and t["gross"] == 15730
    r = requests.put(f"{API}/offers/{ST['d']}", json={"discount": {"type": "percent", "value": 10}}, headers=H).json()
    assert r["totals"]["discount"] == 1300 and r["totals"]["net"] == 11700 and r["totals"]["vat"] == 2457
    r = requests.put(f"{API}/offers/{ST['d']}", json={"discount": {"type": "amount", "value": 500}}, headers=H).json()
    assert r["totals"]["discount"] == 500 and r["totals"]["net"] == 12500


def test_totals_prices_include_vat_and_eur(H):
    r = requests.put(f"{API}/offers/{ST['e']}", json={"prices_include_vat": True, "discount": None, "items": [{"category": "panouri", "qty": 1, "unit_price": 1210}]}, headers=H).json()
    t = r["totals"]
    assert t["net"] == 1000 and t["vat"] == 210 and t["gross"] == 1210
    r = requests.put(f"{API}/offers/{ST['e']}", json={"prices_include_vat": False, "currency": "EUR", "exchange_rate": "5", "items": [{"category": "montaj", "qty": 2, "unit_price": 100}]}, headers=H).json()
    t = r["totals"]
    assert t["currency"] == "EUR" and t["net"] == 200 and t["ron"]["net"] == 1000 and t["ron"]["gross"] == 1210
    assert requests.put(f"{API}/offers/{ST['e']}", json={"currency": "USD"}, headers=H).status_code == 400


# --- PDF
def test_offer_pdf(H):
    tok = H["Authorization"].split()[1]
    r = requests.get(f"{API}/offers/{ST['a']}/pdf?auth={tok}")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    assert "Oferta_de_pret_249.pdf" in r.headers.get("content-disposition", "")
    from pypdf import PdfReader
    txt = "".join(p.extract_text() for p in PdfReader(io.BytesIO(r.content)).pages)
    assert "OFERTĂ DE PREȚ NR. 249" in txt and "NR REG" in txt and "TEST Ion Popescu" in txt
    assert requests.get(f"{API}/offers/{ST['a']}/pdf").status_code == 401


# --- status + contract
def test_contract_requires_accepted(H):
    r = requests.post(f"{API}/offers/{ST['a']}/contract", json={"payment": {"mode": "integral", "due_days": 5}}, headers=H)
    assert r.status_code == 400
    assert requests.post(f"{API}/offers/{ST['a']}/status", json={"status": "Bogus"}, headers=H).status_code == 400
    assert requests.post(f"{API}/offers/{ST['a']}/status", json={"status": "Acceptată"}, headers=H).status_code == 200


def test_contract_preview_and_invalid_advance(H):
    r = requests.post(f"{API}/offers/{ST['a']}/contract/preview", json={"payment": {"mode": "avans", "advance_type": "percent", "advance_value": 30, "advance_days": 5, "balance_rule": "la finalizare"}}, headers=H)
    assert r.status_code == 200
    j = r.json()
    assert j["advance_net"] == 3900 and j["rest_net"] == 9100 and "3 900,00 lei" in j["text"] and "4 719,00 lei" in j["text"]
    r = requests.post(f"{API}/offers/{ST['a']}/contract", json={"payment": {"mode": "avans", "advance_type": "amount", "advance_value": 20000}}, headers=H)
    assert r.status_code == 400
    r = requests.post(f"{API}/offers/{ST['a']}/contract/preview", json={"payment": {"mode": "avans", "tranches": [{"type": "percent", "value": 80}, {"type": "amount", "value": 5000}]}}, headers=H)
    assert r.status_code == 400


def test_contract_integral_93(H):
    r = requests.post(f"{API}/offers/{ST['a']}/contract", json={"payment": {"mode": "integral", "due_days": 10}, "execution_term": "30 zile", "works_warranty_months": 24, "place": "Vaslui"}, headers=H)
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["number"] == 93 and c["status"] == "Generat" and c["offer_number"] == 249
    joined = " ".join(a["text"] for a in c["articles"])
    assert len(c["articles"]) == 12
    assert "TEST Ion Popescu" in joined and "13 000,00 lei" in joined and "15 730,00 lei" in joined and "10 zile" in joined and "{" not in joined
    ST["c93"] = c["id"]
    assert requests.post(f"{API}/offers/{ST['a']}/contract", json={"payment": {"mode": "integral", "due_days": 10}}, headers=H).status_code == 409
    r = requests.post(f"{API}/offers/{ST['a']}/contract", json={"payment": {"mode": "integral", "due_days": 15}, "regenerate": True}, headers=H)
    assert r.status_code == 200 and r.json()["number"] == 93 and len(r.json()["revisions"]) == 1
    # offer with contract cannot leave Acceptată
    assert requests.post(f"{API}/offers/{ST['a']}/status", json={"status": "Respinsă"}, headers=H).status_code == 400
    assert requests.delete(f"{API}/offers/{ST['a']}", headers=H).status_code == 400


def test_contract_avans_tranches_94(H):
    requests.post(f"{API}/offers/{ST['d']}/status", json={"status": "Acceptată"}, headers=H)
    r = requests.post(f"{API}/offers/{ST['d']}/contract", json={"payment": {"mode": "avans", "tranches": [{"label": "Avans", "type": "percent", "value": 50, "due": "la semnare"}, {"type": "amount", "value": 1000}], "balance_rule": "la PIF"}}, headers=H)
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["number"] == 94 and c["payment_calc"]["mode"] == "avans" and len(c["payment_calc"]["tranches"]) == 3
    assert c["payment_calc"]["tranches"][2]["net"] == 12500 - 6250 - 1000
    ST["c94"] = c["id"]


def test_offer_edit_after_contract(H):
    r = requests.put(f"{API}/offers/{ST['a']}", json={"title": "TEST changed"}, headers=H)
    assert r.status_code == 409
    r = requests.put(f"{API}/offers/{ST['a']}", json={"title": "TEST changed", "confirm_contract_change": True}, headers=H)
    assert r.status_code == 200 and r.json()["version"] == 2 and r.json()["contract_outdated"] is True
    c = requests.get(f"{API}/contracts/{ST['c93']}", headers=H).json()
    assert c["offer"]["title"] == "TEST Sistem 4.5 kWp" and c["offer_version"] == 1
    lst = requests.get(f"{API}/contracts", headers=H).json()
    row = next(x for x in lst if x["id"] == ST["c93"])
    assert row["offer_changed"] is True and row["beneficiary"] == BEN["name"]
    v = requests.get(f"{API}/offers/{ST['a']}/versions", headers=H).json()
    assert v[0]["version"] == 1


def test_contract_pdf_and_status(H):
    tok = H["Authorization"].split()[1]
    r = requests.get(f"{API}/contracts/{ST['c93']}/pdf?auth={tok}")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    from pypdf import PdfReader
    rd = PdfReader(io.BytesIO(r.content))
    txt = "".join(p.extract_text() for p in rd.pages)
    print("contract pages", len(rd.pages))
    assert len(rd.pages) >= 5
    assert "Anexa 1 – Oferta Comercială" in txt and "Anexa 2 – Garanții" in txt and "NR. 93" in txt
    assert requests.post(f"{API}/contracts/{ST['c93']}/status", json={"status": "Semnat"}, headers=H).json()["status"] == "Semnat"
    assert requests.post(f"{API}/contracts/{ST['c93']}/status", json={"status": "x"}, headers=H).status_code == 400


def test_template_flow(H):
    t = requests.get(f"{API}/contract-template", headers=H).json()
    assert t["active"]["version"] == 0 and len(t["active"]["articles"]) == 12 and t["pending"] is None
    arts = t["active"]["articles"]
    arts[7] = {"title": arts[7]["title"], "text": "TEST_CLAUZA litigii {firma}"}
    r = requests.put(f"{API}/contract-template", json={"articles": arts}, headers=H)
    assert r.status_code == 200 and r.json()["status"] == "în așteptare"
    t = requests.get(f"{API}/contract-template", headers=H).json()
    assert t["active"]["version"] == 0 and t["pending"]["version"] == 1
    # reject
    assert requests.post(f"{API}/contract-template/approve", json={"approve": False}, headers=H).json()["status"] == "respins"
    assert requests.get(f"{API}/contract-template", headers=H).json()["active"]["version"] == 0
    requests.put(f"{API}/contract-template", json={"articles": arts}, headers=H)
    r = requests.post(f"{API}/contract-template/approve", json={"approve": True}, headers=H).json()
    assert r["status"] == "aprobat" and r["version"] == 2
    # new contract uses approved template
    requests.post(f"{API}/offers/{ST['c']}/status", json={"status": "Acceptată"}, headers=H)
    c = requests.post(f"{API}/offers/{ST['c']}/contract", json={"payment": {"mode": "integral", "due_rule": "la semnare"}}, headers=H).json()
    assert c["number"] == 95 and c["template_version"] == 2
    assert any("TEST_CLAUZA" in a["text"] for a in c["articles"])
    assert requests.put(f"{API}/contract-template", json={"articles": []}, headers=H).status_code == 400


# --- isolation + feature gate
def test_isolation_and_gate(H):
    em = f"sub_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": em, "password": "Test2026!x", "name": "TEST Sub",
                                                    "billing": {"client_type": "pf", "full_name": "TEST Sub", "address": "x", "locality": "x", "county": "x", "country": "RO", "phone": "0700"}})
    assert r.status_code in (200, 201), r.text
    users = requests.get(f"{API}/admin/subscribers", headers=H).json()
    users = users.get("items", users) if isinstance(users, dict) else users
    uid = next(u["id"] for u in users if u.get("email") == em)
    ST["sub_uid"], ST["sub_email"] = uid, em
    assert requests.put(f"{API}/admin/subscribers/{uid}", json={"status": "active"}, headers=H).status_code == 200
    requests.post(f"{API}/admin/subscribers/{uid}/plan", json={"plan": "pro", "valid_until": "2027-01-01", "status": "activ", "justification": "TEST"}, headers=H)
    S = login({"email": em, "password": "Test2026!x"})
    assert requests.get(f"{API}/offers", headers=S).status_code in (402, 403)
    assert requests.post(f"{API}/offers", json={}, headers=S).status_code in (402, 403)
    requests.post(f"{API}/admin/subscribers/{uid}/plan", json={"plan": "full", "valid_until": "2027-01-01", "status": "activ", "justification": "TEST"}, headers=H)
    S = login({"email": em, "password": "Test2026!x"})
    assert requests.get(f"{API}/offers", headers=S).json() == []
    assert requests.get(f"{API}/offers/{ST['a']}", headers=S).status_code == 404
    assert requests.put(f"{API}/offers/{ST['a']}", json={"title": "hack"}, headers=S).status_code == 404
    assert requests.get(f"{API}/contracts/{ST['c93']}", headers=S).status_code == 404
    tok = S["Authorization"].split()[1]
    assert requests.get(f"{API}/contracts/{ST['c93']}/pdf?auth={tok}").status_code == 404
    # sub's own numbering starts at 249 independently
    o = requests.post(f"{API}/offers", json={"beneficiary": {"name": "TEST sub ben"}}, headers=S).json()
    assert o["number"] == 249
