# Iteration 20 — DI-U automatic documents (import from prosumer, 11 positions, PDFs, verdicts), AI precheck + ack, AI sign message, plan gating
import os, io, json, uuid, re
import pytest, requests
from pymongo import MongoClient
from pypdf import PdfReader

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = ("drinkdrinc@gmail.com", "DEnergy2026!")
PWD = "Test2026!x"
TAG = f"sub_i20_{uuid.uuid4().hex[:6]}"
PF = {"client_type": "pf", "full_name": "Maria Test", "address": "Str. PF 2", "locality": "Cluj", "county": "Cluj", "country": "România",
      "billing_email": "pf@example.com", "phone": "0711111111"}
env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
mdb = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
S = {}
LLM_T = 180
KEYS = ["opis", "memoriu", "schema_tg", "pram_priza", "pram_cont", "pram_izol", "pram_ddr", "receptie", "pif", "conformitate", "garantie"]
DOTS = "…………………"


def h(tok=None):
    return {"Authorization": f"Bearer {tok or S['admin']}"}


def sse(r):
    evs = [json.loads(line[6:]) for line in r.text.split("\n\n") if line.startswith("data: ")]
    return "".join(e.get("t", "") for e in evs), evs


def pdf_text(content):
    return re.sub(r"\s+", " ", " ".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(content)).pages))


def mk_user(suffix, plan):
    email = f"{TAG}_{suffix}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": PWD, "name": f"TEST {suffix}", "billing": PF})
    assert r.status_code == 200, r.text
    uid = mdb.users.find_one({"email": email})["id"]
    S.setdefault("uids", []).append(uid)
    requests.put(f"{API}/admin/subscribers/{uid}", headers=h(), json={"status": "active"})
    r = requests.post(f"{API}/admin/subscribers/{uid}/plan", headers=h(), json={"plan": plan, "valid_until": "2026-12-31", "status": "activ", "justification": "TEST"})
    assert r.status_code == 200, r.text
    return requests.post(f"{API}/auth/login", json={"email": email, "password": PWD}).json()["access_token"]


@pytest.fixture(scope="module", autouse=True)
def setup():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})
    assert r.status_code == 200
    S["admin"] = r.json()["access_token"]
    r = requests.post(f"{API}/test-dossier", headers=h())
    assert r.status_code == 200, r.text
    S["pid"] = r.json()["prosumator_id"]
    S["pros"] = mdb.prosumator.find_one({"id": S["pid"]}, {"_id": 0})
    S["stamp"] = S["pros"]["created_at"][:19]
    r = requests.post(f"{API}/data/diu", headers=h(), json={"number": f"TEST_DIU_{TAG}"})
    assert r.status_code in (200, 201), r.text
    S["diu"] = r.json()["id"]
    yield
    mdb.diu.delete_many({"id": S["diu"]})
    owner = mdb.users.find_one({"email": ADMIN[0]})["id"]
    for c in ["clients", "prosumator", "diu", "pram", "staff", "instruments", "catalog", "documents"]:
        mdb[c].delete_many({"owner": owner, "is_test": True, "created_at": {"$gte": S["stamp"]}})
    mdb.sign_requests.delete_many({"dossier_id": S["pid"]})
    for uid in S.get("uids", []):
        mdb.subscriptions.delete_many({"tenant": uid}); mdb.users.delete_many({"id": uid}); mdb.diu.delete_many({"owner": uid})


# ---- DI-U positions + import ----
class TestDiu:
    def test_docs_empty_positions(self):
        r = requests.get(f"{API}/diu/{S['diu']}/docs", headers=h())
        assert r.status_code == 200, r.text
        d = r.json()
        assert [p["key"] for p in d["positions"]] == KEYS
        assert d["complete"] is False
        mem = next(p for p in d["positions"] if p["key"] == "memoriu")
        assert "Beneficiar" in mem["missing"] and "Tip instalație" in mem["missing"]
        assert next(p for p in d["positions"] if p["key"] == "opis")["missing"] == []

    def test_import_pros(self):
        r = requests.post(f"{API}/diu/{S['diu']}/import-pros", headers=h(), json={"pros_id": S["pid"]})
        assert r.status_code == 200, r.text
        d = r.json()
        p = S["pros"]
        S["import"] = d
        print("IMPORTED:", {k: d.get(k) for k in ("client_name", "address", "operator", "power", "atr", "type", "supply", "earthing", "tg_breaker_a", "bmp_a", "pram_m")})
        print("CIRCUITS:", d.get("circuits"))
        assert d["pros_id"] == S["pid"]
        assert d["client_name"] == p["client_name"]
        for k in ("address", "operator", "power"):
            if p.get(k):
                assert d.get(k) == p[k], k
        assert d["type"].startswith("Sistem fotovoltaic")
        assert len(d.get("circuits") or []) == len(p["cef"]["inverters"]) >= 1
        assert d["circuits"][0]["name"].startswith("INV1")
        g = p["cef"].get("grid") or {}
        if g.get("grounding_ohm") or p.get("grounding_ohm"):
            assert d["pram_m"].get("earth_ohm") == (g.get("grounding_ohm") or p.get("grounding_ohm"))
        if p.get("grounding_limit"):
            assert d["pram_m"].get("earth_limit") == p["grounding_limit"]

    def test_import_keeps_existing_circuits(self):
        cur = mdb.diu.find_one({"id": S["diu"]}, {"_id": 0})
        circ = [{"name": "TEST priza bucatarie", "breaker_a": 16, "curve": "C", "section": "2.5", "rcd_ma": 30, "rcd_type": "A"}] + cur["circuits"]
        r = requests.put(f"{API}/data/diu/{S['diu']}", headers=h(), json={**{k: v for k, v in cur.items() if k not in ("id", "owner")}, "circuits": circ, "supply": "Monofazat"})
        assert r.status_code == 200, r.text
        r = requests.post(f"{API}/diu/{S['diu']}/import-pros", headers=h(), json={"pros_id": S["pid"]})
        assert r.status_code == 200
        assert r.json()["circuits"][0]["name"] == "TEST priza bucatarie"
        assert r.json()["supply"] == "Monofazat"  # not overwritten

    def test_import_invalid(self):
        r = requests.post(f"{API}/diu/{S['diu']}/import-pros", headers=h(), json={"pros_id": "nope"})
        assert r.status_code == 404

    def test_missing_lists_clear(self):
        cur = mdb.diu.find_one({"id": S["diu"]}, {"_id": 0})
        circ = []
        for i, c in enumerate(cur["circuits"]):
            c = {**c, "breaker_a": c.get("breaker_a") or 25, "section": c.get("section") or "6", "r_pe": "0.2", "riso": "0.5" if i == 0 else "250",
                 "rcd_ma": c.get("rcd_ma") or 30, "rcd_t": "400" if i == 0 else "25", "rcd_i": "22"}
            circ.append(c)
        S["circ"] = circ
        body = {**{k: v for k, v in cur.items() if k not in ("id", "owner")}, "circuits": circ, "type": "Sistem fotovoltaic on-grid", "power": cur.get("power") or "6",
                "supply": "Monofazat", "tg_breaker_a": "40", "bmp_a": "32", "earthing": "TN-C-S",
                "pram_m": {**(cur.get("pram_m") or {}), "date": "2026-01-10", "instrument": "TEST Metrel MI3152 SN123", "verifier": "TEST Ion Verificator", "test_v": "500",
                           "earth_ohm": "12", "earth_limit": "4"},
                "receptie_date": "2026-01-12", "receptie_decision": "Se recepționează", "pif_date": "2026-01-13", "pif_decision": "Se pune în funcțiune",
                "warranty_months": "24", "warranty_start": "2026-01-12", "date": "2026-01-12", "address": cur.get("address") or "Str. TEST 1"}
        r = requests.put(f"{API}/data/diu/{S['diu']}", headers=h(), json=body)
        assert r.status_code == 200, r.text
        d = requests.get(f"{API}/diu/{S['diu']}/docs", headers=h()).json()
        miss = {p["key"]: p["missing"] for p in d["positions"]}
        print("MISSING AFTER FILL:", miss)
        assert all(not v for v in miss.values()), miss
        assert d["complete"] is True
        assert all(p["status"] == "generat" for p in d["positions"])

    def test_pdf_all_and_keys(self):
        tok = S["admin"]
        r = requests.get(f"{API}/diu/{S['diu']}/pdf?doc=all&auth={tok}")
        assert r.status_code == 200 and r.content[:4] == b"%PDF"
        assert "CIORNA" not in r.headers.get("content-disposition", "")
        n = len(PdfReader(io.BytesIO(r.content)).pages)
        assert n >= 11, n
        for k in KEYS:
            r = requests.get(f"{API}/diu/{S['diu']}/pdf?doc={k}&auth={tok}")
            assert r.status_code == 200 and r.content[:4] == b"%PDF", (k, r.status_code, r.text[:200])
        r = requests.get(f"{API}/diu/{S['diu']}/pdf?doc=bogus&auth={tok}")
        assert r.status_code == 404

    def test_pdf_requires_auth(self):
        r = requests.get(f"{API}/diu/{S['diu']}/pdf?doc=all")
        assert r.status_code in (401, 403)

    def test_verdicts(self):
        tok = S["admin"]
        izol = pdf_text(requests.get(f"{API}/diu/{S['diu']}/pdf?doc=pram_izol&auth={tok}").content)
        assert "NU corespunde" in izol
        if len(S["circ"]) > 1:
            assert re.search(r"(?<!NU )Corespunde", izol)
        ddr = pdf_text(requests.get(f"{API}/diu/{S['diu']}/pdf?doc=pram_ddr&auth={tok}").content)
        assert "NU corespunde" in ddr  # 400 ms > 300
        priza = pdf_text(requests.get(f"{API}/diu/{S['diu']}/pdf?doc=pram_priza&auth={tok}").content)
        assert "NU corespunde" in priza  # 12 > 4
        cur = mdb.diu.find_one({"id": S["diu"]}, {"_id": 0})
        mdb.diu.update_one({"id": S["diu"]}, {"$set": {"pram_m.earth_ohm": "3", "circuits.0.rcd_t": "300", "circuits.0.riso": "1"}})
        priza = pdf_text(requests.get(f"{API}/diu/{S['diu']}/pdf?doc=pram_priza&auth={tok}").content)
        assert "Corespunde" in priza and "NU corespunde" not in priza
        ddr = pdf_text(requests.get(f"{API}/diu/{S['diu']}/pdf?doc=pram_ddr&auth={tok}").content)
        assert "NU corespunde" not in ddr
        izol = pdf_text(requests.get(f"{API}/diu/{S['diu']}/pdf?doc=pram_izol&auth={tok}").content)
        assert "NU corespunde" not in izol

    def test_blank_dotted_and_draft(self):
        mdb.diu.update_one({"id": S["diu"]}, {"$set": {"circuits.0.riso": "", "pram_m.verifier": ""}})
        d = requests.get(f"{API}/diu/{S['diu']}/docs", headers=h()).json()
        miss = {p["key"]: p["missing"] for p in d["positions"]}
        assert "Verificator PRAM" in miss["pram_izol"] and any("Rezistență izolație" in m for m in miss["pram_izol"])
        r = requests.get(f"{API}/diu/{S['diu']}/pdf?doc=pram_izol&auth={S['admin']}")
        assert "CIORNA" in r.headers.get("content-disposition", "")
        txt = pdf_text(r.content)
        assert "……" in txt or DOTS in txt


# ---- Plan gating ----
class TestGating:
    def test_start_402_diu(self):
        S["start"] = mk_user("start", "start")
        r = requests.get(f"{API}/diu/{S['diu']}/docs", headers=h(S["start"]))
        assert r.status_code == 402, (r.status_code, r.text)
        r = requests.post(f"{API}/data/diu", headers=h(S["start"]), json={"number": "TEST_X"})
        assert r.status_code in (402, 403), r.status_code

    def test_pro_diu_ok_ai_402(self):
        S["pro"] = mk_user("pro", "pro")
        r = requests.post(f"{API}/data/diu", headers=h(S["pro"]), json={"number": "TEST_PRO_DIU"})
        assert r.status_code in (200, 201), r.text
        did = r.json()["id"]
        r = requests.get(f"{API}/diu/{did}/docs", headers=h(S["pro"]))
        assert r.status_code == 200 and len(r.json()["positions"]) == 11
        r = requests.post(f"{API}/ai/dossier/{S['pid']}/precheck", headers=h(S["pro"]))
        assert r.status_code == 402, (r.status_code, r.text)
        r = requests.post(f"{API}/ai/sign-message", headers=h(S["pro"]), json={"dossier_id": S["pid"], "channel": "sms", "links": [{"title": "x", "url": "https://a.b/c"}]})
        assert r.status_code == 402


# ---- AI precheck + sign message (3 LLM calls) ----
class TestAi:
    def test_precheck(self):
        r = requests.post(f"{API}/ai/dossier/{S['pid']}/precheck", headers=h(), timeout=LLM_T)
        assert r.status_code == 200, r.text
        d = r.json()
        print("PRECHECK:", json.dumps(d, ensure_ascii=False)[:1500])
        assert isinstance(d["items"], list) and d["at"]
        for it in d["items"]:
            assert it["text"] and it["severity"] in ("critic", "important", "minor")
        saved = mdb.prosumator.find_one({"id": S["pid"]})["ai_precheck"]
        assert len(saved["items"]) == len(d["items"])
        S["n"] = len(d["items"])

    def test_ack(self):
        n = S.get("n", 0)
        chk = [0] if n else []
        r = requests.post(f"{API}/ai/dossier/{S['pid']}/precheck/ack", headers=h(), json={"checked": chk + [99, "x"]})
        assert r.status_code == 200, r.text
        assert r.json() == {"checked": chk, "unchecked": n - len(chk)}
        assert mdb.prosumator.find_one({"id": S["pid"]})["ai_precheck"]["checked"] == chk

    def test_sign_message_no_links(self):
        r = requests.post(f"{API}/ai/sign-message", headers=h(), json={"dossier_id": S["pid"], "channel": "whatsapp", "links": []})
        assert r.status_code == 400

    @pytest.mark.parametrize("ch", ["whatsapp", "email"])
    def test_sign_message(self, ch):
        links = [{"title": "Cerere de racordare", "url": f"{BASE_URL}/semneaza/TESTtokA1b2C3d4E5f6G7h8"},
                 {"title": "Împuternicire", "url": f"{BASE_URL}/semneaza/TESTtokZ9y8X7w6V5u4T3s2"}]
        r = requests.post(f"{API}/ai/sign-message", headers=h(), json={"dossier_id": S["pid"], "channel": ch, "links": links}, timeout=LLM_T)
        assert r.status_code == 200
        txt, evs = sse(r)
        print(f"MSG[{ch}]:", txt)
        assert any(e.get("done") for e in evs), evs[-1:]
        for l in links:
            assert l["url"] in txt, l["url"]
        if ch == "email":
            assert re.search(r"^Subiect:", txt.strip(), re.M)
