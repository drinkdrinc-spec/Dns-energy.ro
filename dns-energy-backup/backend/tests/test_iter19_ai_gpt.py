# Iteration 19 — ChatGPT AI (chat, dossier check, draft, extract), ai_gpt gating, iter18 regression fixes
import os, io, json, uuid, sys
from datetime import datetime, timezone, timedelta
import pytest, requests
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
import pif_doc  # noqa: E402

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = ("drinkdrinc@gmail.com", "DEnergy2026!")
PWD = "Test2026!x"
TAG = f"sub_i19_{uuid.uuid4().hex[:6]}"
PF = {"client_type": "pf", "full_name": "Maria Test", "address": "Str. PF 2", "locality": "Cluj", "county": "Cluj", "country": "România",
      "billing_email": "pf@example.com", "phone": "0711111111"}
TEST_COLLECTIONS = ["clients", "prosumator", "diu", "pram", "staff", "instruments", "catalog", "documents"]
env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
mdb = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
S = {}
LLM_T = 180


def h(tok=None):
    return {"Authorization": f"Bearer {tok or S['admin']}"}


def sse(r):
    """Parse SSE body -> (text, events)"""
    evs = [json.loads(line[6:]) for line in r.text.split("\n\n") if line.startswith("data: ")]
    return "".join(e.get("t", "") for e in evs), evs


def mk_user(suffix, team=None, plan=None):
    email = f"{TAG}_{suffix}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": PWD, "name": f"TEST {suffix}", "billing": PF})
    assert r.status_code == 200, r.text
    uid = mdb.users.find_one({"email": email})["id"]
    r = requests.put(f"{API}/admin/subscribers/{uid}", headers=h(), json={"status": "active", **({"to_team": team} if team else {})})
    assert r.status_code == 200, r.text
    if plan:
        r = requests.post(f"{API}/admin/subscribers/{uid}/plan", headers=h(),
                          json={"plan": plan, "valid_until": "2026-12-31", "status": "activ", "justification": "TEST"})
        assert r.status_code == 200, r.text
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": PWD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def make_pdf():
    import pymupdf
    doc = pymupdf.open()
    pg = doc.new_page()
    lines = ["CERERE DE RACORDARE PROSUMATOR", "Beneficiar: Ionescu Gheorghe TEST", "Adresa loc de consum: Str. Florilor nr. 12, Oradea, judet Bihor",
             "Cod loc de consum (POD): RO005E123456789", "Telefon: 0744123456", "Putere instalata: 6 kW, Monofazat", "Invertor: Huawei SUN2000-6KTL-L1 (1 buc)"]
    for i, t in enumerate(lines):
        pg.insert_text((60, 80 + i * 24), t, fontsize=12)
    return doc.tobytes()


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
    mdb.ai_sessions.delete_many({"title": {"$regex": "^TEST"}})
    for sid in S.get("sids", []):
        mdb.ai_sessions.delete_many({"id": sid}); mdb.ai_messages.delete_many({"session_id": sid})
    for c in TEST_COLLECTIONS:
        mdb[c].delete_many({"owner": S["owner"], "is_test": True, "created_at": {"$gte": start}})
    if S.get("cid"):
        mdb.clients.delete_many({"id": S["cid"]})
    for u in mdb.users.find({"email": {"$regex": f"^{TAG}"}}):
        mdb.subscriptions.delete_many({"tenant": u["id"]})
        mdb.ai_sessions.delete_many({"owner": u["id"]})
    mdb.users.delete_many({"email": {"$regex": f"^{TAG}"}})
    assert (mdb.platform_modules.find_one({"id": "main"}) or {}).get("disabled", []) == []


# ---------- Chat ----------
class TestChat:
    def test_session_crud_and_multiturn(self):
        r = requests.post(f"{API}/ai/sessions", headers=h())
        assert r.status_code == 200, r.text
        sid = r.json()["id"]; S.setdefault("sids", []).append(sid); S["sid"] = sid
        assert r.json()["title"] == "Conversație nouă"
        assert any(s["id"] == sid for s in requests.get(f"{API}/ai/sessions", headers=h()).json())
        # empty text -> 400
        assert requests.post(f"{API}/ai/sessions/{sid}/message", headers=h(), json={"text": "  "}).status_code == 400
        q1 = "TEST Care este valoarea maximă admisă a rezistenței prizei de pământ pentru o instalație fotovoltaică conform I7? Răspunde scurt."
        r = requests.post(f"{API}/ai/sessions/{sid}/message", headers=h(), json={"text": q1}, timeout=LLM_T)
        assert r.status_code == 200 and "text/event-stream" in r.headers.get("content-type", "")
        t1, evs = sse(r)
        print("A1:", t1[:300])
        assert not any("error" in e for e in evs), evs[-1]
        assert evs[-1] == {"done": True} and len(t1) > 20
        q2 = "Și dacă valoarea măsurată este dublă față de ce mi-ai spus mai sus, ce fac? Repetă întâi valoarea pe care ai menționat-o."
        r = requests.post(f"{API}/ai/sessions/{sid}/message", headers=h(), json={"text": q2}, timeout=LLM_T)
        t2, evs = sse(r)
        print("A2:", t2[:400])
        assert evs[-1] == {"done": True}
        assert "4" in t2 or "ohm" in t2.lower() or "Ω" in t2, "multi-turn context not used?"
        msgs = requests.get(f"{API}/ai/sessions/{sid}/messages", headers=h()).json()
        assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
        assert msgs[0]["content"] == q1 and msgs[1]["content"] == t1
        s = next(s for s in requests.get(f"{API}/ai/sessions", headers=h()).json() if s["id"] == sid)
        assert s["title"] == q1[:60]

    def test_other_user_cannot_access(self):
        tok = mk_user("full", plan="full")
        S["full_tok"] = tok
        sid = S["sid"]
        assert requests.get(f"{API}/ai/sessions/{sid}/messages", headers=h(tok)).status_code == 404
        assert requests.post(f"{API}/ai/sessions/{sid}/message", headers=h(tok), json={"text": "x"}).status_code == 404
        assert requests.delete(f"{API}/ai/sessions/{sid}", headers=h(tok)).status_code == 404
        assert all(s["id"] != sid for s in requests.get(f"{API}/ai/sessions", headers=h(tok)).json())

    def test_delete_session(self):
        sid = S["sid"]
        r = requests.delete(f"{API}/ai/sessions/{sid}", headers=h())
        assert r.status_code == 200 and r.json()["ok"]
        assert requests.get(f"{API}/ai/sessions/{sid}/messages", headers=h()).status_code == 404
        assert mdb.ai_messages.count_documents({"session_id": sid}) == 0


# ---------- Dossier check / Draft ----------
class TestCheckDraft:
    def test_dossier_check(self):
        r = requests.post(f"{API}/ai/dossier/{S['pid']}/check", headers=h(), timeout=LLM_T)
        assert r.status_code == 200, r.text
        t, evs = sse(r)
        print("CHECK:", t[:600])
        assert evs[-1] == {"done": True} and len(t) > 100
        assert "verdict" in t.lower() or "gata de trimis" in t.lower() or "necesită" in t.lower()

    def test_dossier_check_404(self):
        assert requests.post(f"{API}/ai/dossier/nonexistent-id/check", headers=h(), timeout=60).status_code == 404

    def test_draft_validation(self):
        assert requests.post(f"{API}/ai/draft", headers=h(), json={"module": "bogus", "label": "x"}).status_code == 400
        assert requests.post(f"{API}/ai/draft", headers=h(), json={"module": "prosumator", "label": ""}).status_code == 400

    def test_draft_stream(self):
        r = requests.post(f"{API}/ai/draft", headers=h(), timeout=LLM_T, json={
            "module": "prosumator", "field": "notes", "label": "Observații", "current": "",
            "instructions": "recepție fără obiecțiuni, 1 invertor", "form": {"client_name": "Ionescu TEST", "power": 6, "inverter": "Huawei SUN2000-6KTL"}})
        assert r.status_code == 200, r.text
        t, evs = sse(r)
        print("DRAFT:", t[:400])
        assert evs[-1] == {"done": True} and len(t) > 20


# ---------- Extract ----------
class TestExtract:
    def test_extract_pdf_gpt(self):
        r = requests.post(f"{API}/ai/extract", headers=h(), timeout=LLM_T,
                          files={"file": ("cerere_test.pdf", make_pdf(), "application/pdf")})
        assert r.status_code == 200, r.text
        d = r.json()
        print("EXTRACT:", d)
        assert d["engine"] == "ChatGPT (GPT 6 Sol)"
        assert "ionescu" in str(d["data"].get("client_name", "")).lower()
        assert "RO005E123456789" in str(d["data"].get("pod", ""))
        assert "oradea" in str(d["data"].get("address", "")).lower()


# ---------- Gating ----------
class TestGating:
    def test_start_and_pro_get_402(self):
        for plan in ("start", "pro"):
            tok = mk_user(plan, plan=plan)
            for m, p, kw in [("get", "/ai/sessions", {}), ("post", "/ai/sessions", {}), ("post", "/ai/draft", {"json": {"module": "prosumator", "label": "x"}}),
                             ("post", f"/ai/dossier/{S['pid']}/check", {})]:
                r = getattr(requests, m)(f"{API}{p}", headers=h(tok), **kw)
                assert r.status_code == 402 or (r.status_code == 404 and "dossier" in p), (plan, p, r.status_code, r.text)
            assert getattr(requests, "get")(f"{API}/ai/sessions", headers=h(tok)).status_code == 402

    def test_disabled_ai_gpt_403_and_restore(self):
        tok = S.get("full_tok") or mk_user("full2", plan="full")
        assert requests.get(f"{API}/ai/sessions", headers=h(tok)).status_code == 200
        r = requests.put(f"{API}/platform/modules", headers=h(), json={"disabled": ["ai_gpt"]})
        assert r.status_code == 200, r.text
        try:
            r = requests.get(f"{API}/ai/sessions", headers=h(tok))
            assert r.status_code == 403, r.text
            assert requests.post(f"{API}/ai/draft", headers=h(tok), json={"module": "prosumator", "label": "x"}).status_code == 403
            # platform admin unaffected
            assert requests.get(f"{API}/ai/sessions", headers=h()).status_code == 200
            me = requests.get(f"{API}/auth/me", headers=h(tok)).json()
            assert "ai_gpt" in me["plan"]["disabled"]
        finally:
            requests.put(f"{API}/platform/modules", headers=h(), json={"disabled": []})
        assert requests.get(f"{API}/ai/sessions", headers=h(tok)).status_code == 200


# ---------- Regression fixes from iteration 18 ----------
class TestRegressions:
    def test_team_member_affected_by_disabled(self):
        tok = mk_user("team", team="instalator")
        requests.put(f"{API}/platform/modules", headers=h(), json={"disabled": ["power", "ai_gpt"]})
        try:
            me = requests.get(f"{API}/auth/me", headers=h(tok)).json()
            assert set(me["plan"]["disabled"]) >= {"power", "ai_gpt"}, me["plan"]
            assert requests.get(f"{API}/ai/sessions", headers=h(tok)).status_code == 403
            assert requests.get(f"{API}/auth/me", headers=h()).json()["plan"]["disabled"] == []
        finally:
            requests.put(f"{API}/platform/modules", headers=h(), json={"disabled": []})

    def test_client_put_keeps_docs_semnate(self):
        r = requests.post(f"{API}/data/clients", headers=h(), json={"name": "TEST Client i19", "kind": "pf", "docs": {}})
        assert r.status_code in (200, 201), r.text
        cid = r.json()["id"]; S["cid"] = cid
        entry = {"title": "TEST semnat", "storage_path": "x/y.pdf"}
        mdb.clients.update_one({"id": cid}, {"$push": {"docs.semnate": entry}})
        r = requests.put(f"{API}/data/clients/{cid}", headers=h(), json={"name": "TEST Client i19 upd", "kind": "pf", "docs": {"ci": []}})
        assert r.status_code == 200, r.text
        c = mdb.clients.find_one({"id": cid})
        assert c["name"] == "TEST Client i19 upd"
        assert c["docs"].get("semnate") == [entry], c["docs"]

    def test_pif_signed_upload_invalidated(self):
        pid = S["pid"]
        r = requests.put(f"{API}/dossier/{pid}/pif", headers=h(), json={"date": "2026-01-15", "strings": {"0.0": {"voc": "487.3"}}, "checks": {"0": "Conform"}})
        assert r.status_code == 200, r.text
        rec = mdb.prosumator.find_one({"id": pid}, {"_id": 0})
        up = {"storage_path": "x/pif_semnat.pdf", "original_filename": "pif_pv_semnat.pdf", "content_type": "application/pdf", "size": 1, "pif_hash": pif_doc.fingerprint(rec)}
        mdb.prosumator.update_one({"id": pid}, {"$set": {"opis.pif_pv.upload": up, "opis.pif_pv.status": "atașat"}})
        p = next(p for p in requests.get(f"{API}/dossier/{pid}", headers=h()).json()["positions"] if p["key"] == "pif_pv")
        assert p["upload"] and p["upload"]["storage_path"] == "x/pif_semnat.pdf"
        r = requests.put(f"{API}/dossier/{pid}/pif", headers=h(), json={"date": "2026-01-15", "strings": {"0.0": {"voc": "499.9"}}, "checks": {"0": "Conform"}})
        assert r.status_code == 200
        p = next(p for p in requests.get(f"{API}/dossier/{pid}", headers=h()).json()["positions"] if p["key"] == "pif_pv")
        assert p["upload"] is None, p
        assert any("PIF s-au modificat" in m for m in p["missing"]), p["missing"]
