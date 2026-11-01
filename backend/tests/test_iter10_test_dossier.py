import os as _dns_test_os
import pytest as _dns_test_pytest
if not (_dns_test_os.environ.get("DNS_ENERGY_TEST_EMAIL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_PASSWORD") and _dns_test_os.environ.get("REACT_APP_BACKEND_URL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_ALLOW_MUTATION") == "1"):
    _dns_test_pytest.skip("Set staging-only DNS_ENERGY_TEST_* credentials, REACT_APP_BACKEND_URL and DNS_ENERGY_TEST_ALLOW_MUTATION=1", allow_module_level=True)

# Iteration 10: TEST dossier (create/delete/separation), exports, docx fisa_tehnica, revisions compare,
# approval requests (auto+manual), test_email routing of e-mails, remote signing on TEST dossiers.
# Sends at most 3 real e-mails (only to the configured test address).
import io, os, sys, time, uuid
import pytest, requests
from pypdf import PdfReader

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = {"email": _dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"], "password": _dns_test_os.environ["DNS_ENERGY_TEST_PASSWORD"]}
TEST_EMAIL = _dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"]
pytestmark = pytest.mark.xdist_group("iter10")  # run sequentially in one worker
S = {}


def h():
    return {"Authorization": f"Bearer {S['tok']}"}


def setting(test_email):
    r = requests.put(f"{API}/settings", json={"test_email": test_email}, headers=h())
    assert r.status_code == 200 and (r.json().get("test_email") or "") == test_email


def db_sign(rid):
    from pymongo import MongoClient
    from dotenv import dotenv_values
    env = dotenv_values("/app/backend/.env")
    return MongoClient(env["MONGO_URL"])[env["DB_NAME"]].sign_requests.find_one({"id": rid}) or {}


def pdf_text(b):
    rd = PdfReader(io.BytesIO(b))
    return rd, "\n".join((p.extract_text() or "") for p in rd.pages)


@pytest.fixture(scope="module", autouse=True)
def session():
    r = requests.post(f"{API}/auth/login", json=ADMIN)
    assert r.status_code == 200
    S["tok"] = r.json()["access_token"]
    orig = requests.get(f"{API}/settings", headers=h()).json()
    S["orig_test_email"] = orig.get("test_email") or ""
    # snapshot of real (non-test) records to prove deletion never touches them
    S["real_counts"] = {m: len([x for x in requests.get(f"{API}/data/{m}", headers=h()).json() if not x.get("is_test")])
                        for m in ("clients", "prosumator", "diu", "pram")}
    setting("")
    yield
    setting(S["orig_test_email"] or "")


class TestA_NoTestEmail:
    def test_01_create_test_dossier(self):
        r = requests.post(f"{API}/test-dossier", headers=h())
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["test_email"] is None and d["number"].startswith("TEST-PROS-")
        S["d1"] = d["prosumator_id"]
        rec = requests.get(f"{API}/data/prosumator/{S['d1']}", headers=h()).json()
        assert rec["is_test"] is True and rec["owner"]
        for m in ("clients", "diu", "pram", "staff", "instruments", "catalog"):
            r = requests.get(f"{API}/data/{m}", headers=h())
            if r.status_code == 200:
                assert any(x.get("is_test") for x in r.json()), m

    def test_02_positions_only_schema_fisa_missing(self):
        d = requests.get(f"{API}/dossier/{S['d1']}", headers=h()).json()
        assert len(d["positions"]) == 22
        bad = {p["key"]: p["missing"] for p in d["positions"] if p["missing"]}
        assert set(bad) <= {"schema", "fisa_tehnica"}, bad
        assert "schema" in bad and "fisa_tehnica" in bad
        assert d["complete"] is False

    def test_03_finalize_blocked_before_approval(self):
        r = requests.post(f"{API}/dossier/{S['d1']}/finalize", headers=h())
        assert r.status_code == 400 and "CIORNĂ" in r.json()["detail"]

    def test_04_request_approval_no_staff_email(self):
        r = requests.post(f"{API}/sld/{S['d1']}/request-approval", json={"origin": BASE_URL}, headers=h())
        assert r.status_code == 400, r.text

    def test_05_approve_finalize_reopen(self):
        r = requests.post(f"{API}/sld/{S['d1']}/approve", json={"role": "designer"}, headers=h())
        assert r.status_code == 200, r.text
        d = requests.get(f"{API}/dossier/{S['d1']}", headers=h()).json()
        assert d["complete"] is True and d["missing_total"] == 0
        assert requests.post(f"{API}/dossier/{S['d1']}/finalize", headers=h()).status_code == 200
        assert requests.post(f"{API}/dossier/{S['d1']}/reopen", headers=h()).status_code == 200

    def test_06_export_bundle_watermark(self):
        r = requests.get(f"{API}/dossier/{S['d1']}/export?auth={S['tok']}")
        assert r.status_code == 200 and r.content[:4] == b"%PDF"
        cd = r.headers["content-disposition"]
        assert "filename*=UTF-8''" in cd and "_CIORNA" not in cd
        rd, txt = pdf_text(r.content)
        S["pages"] = len(rd.pages)
        print("export pages", len(rd.pages), cd)
        assert 25 <= len(rd.pages) <= 40
        assert "DOSAR DE TEST" in txt

    @pytest.mark.parametrize("key", ["notificare", "schema", "fisa_tehnica", "afm", "reglaj", "priza", "pif", "receptie",
                                     "executant", "conformitate", "imputernicire", "opis"])
    def test_07_position_pdf(self, key):
        r = requests.get(f"{API}/dossier/{S['d1']}/file/{key}?auth={S['tok']}")
        assert r.status_code == 200, f"{key}: {r.status_code} {r.text[:200]}"
        assert r.content[:4] == b"%PDF"
        _, txt = pdf_text(r.content)
        if key != "schema":
            assert "DOSAR DE TEST" in txt, key

    @pytest.mark.parametrize("key", ["notificare", "fisa_tehnica", "afm", "reglaj", "priza", "pif", "receptie", "executant", "conformitate", "imputernicire"])
    def test_08_docx(self, key):
        r = requests.get(f"{API}/dossier/{S['d1']}/file/{key}?fmt=docx&auth={S['tok']}")
        assert r.status_code == 200, f"{key}: {r.text[:200]}"
        assert r.content[:2] == b"PK" and "wordprocessingml" in r.headers["content-type"]
        assert "filename*=UTF-8''" in r.headers["content-disposition"]

    def test_09_docx_schema_400(self):
        r = requests.get(f"{API}/dossier/{S['d1']}/file/schema?fmt=docx&auth={S['tok']}")
        assert r.status_code == 400

    def test_10_revision_compare(self):
        rec = requests.get(f"{API}/data/prosumator/{S['d1']}", headers=h()).json()
        old = rec["cef"]["inverters"][0]["ac"]["length_m"]
        rec["cef"]["inverters"][0]["ac"]["length_m"] = float(old) + 20
        r = requests.put(f"{API}/data/prosumator/{S['d1']}", json=rec, headers=h())
        assert r.status_code == 200
        st = requests.get(f"{API}/sld/{S['d1']}", headers=h()).json()
        assert st["approval"]["status"] == "stale", st["approval"]["status"]
        # auto request on save recorded with sent=false (no test e-mail and empty staff e-mails -> no recipients)
        r = requests.post(f"{API}/sld/{S['d1']}/approve", json={"role": "designer"}, headers=h())
        assert r.status_code == 200, r.text
        st = requests.get(f"{API}/sld/{S['d1']}", headers=h()).json()
        assert st["revision"] == 1
        c = requests.get(f"{API}/sld/{S['d1']}/compare?a=0&b=1", headers=h())
        assert c.status_code == 200, c.text
        cj = c.json()
        assert cj["changed"] > 0
        ch = [x["key"] for x in cj["rows"] if x["changed"]]
        print("changed rows:", ch)
        assert any("AC" in k or "Cablu" in k for k in ch)
        assert any("ΔU" in k or "cădere" in k.lower() or "Cablu" in k for k in ch)
        assert requests.get(f"{API}/sld/{S['d1']}/compare?a=0&b=9", headers=h()).status_code == 404

    def test_11_otp_without_test_email_400(self):
        r = requests.post(f"{API}/sign/requests", json={"dossier_id": S["d1"], "pos_keys": ["notificare"],
                          "signers": [{"name": "TEST Semnatar", "email": "nobody@example.com", "role": "Beneficiar"}]}, headers=h())
        assert r.status_code == 200, r.text
        req = r.json()[0]
        assert db_sign(req["id"]).get("is_test") is True
        o = requests.post(f"{API}/public/sign/{req['token']}/otp")
        assert o.status_code == 400 and "TEST" in o.json()["detail"]

    def test_12_separation_other_user(self):
        em = f"test_iter10_{uuid.uuid4().hex[:6]}@example.com"
        r = requests.post(f"{API}/auth/register", json={"email": em, "password": "Passw0rd!x", "name": "TEST Other"})
        assert r.status_code in (200, 201), r.text
        t2 = r.json().get("access_token") or requests.post(f"{API}/auth/login", json={"email": em, "password": "Passw0rd!x"}).json()["access_token"]
        h2 = {"Authorization": f"Bearer {t2}"}
        lst = requests.get(f"{API}/data/prosumator", headers=h2)
        assert lst.status_code == 200 and not any(x["id"] == S["d1"] for x in lst.json())
        assert requests.get(f"{API}/sld/{S['d1']}", headers=h2).status_code == 404
        assert requests.get(f"{API}/dossier/{S['d1']}", headers=h2).status_code == 404
        assert requests.delete(f"{API}/test-dossier", headers=h2).json()["deleted"] == 0
        assert requests.get(f"{API}/data/prosumator/{S['d1']}", headers=h()).status_code == 200


class TestB_WithTestEmail:
    def test_20_create_with_test_email_and_auto_request(self):
        setting(TEST_EMAIL)
        r = requests.post(f"{API}/test-dossier", headers=h())
        assert r.status_code == 200 and r.json()["test_email"] == TEST_EMAIL
        S["d2"] = r.json()["prosumator_id"]
        rec = requests.get(f"{API}/data/prosumator/{S['d2']}", headers=h()).json()
        S["verifier"] = rec["signers"]["verifier"]
        # keep only designer as signer to limit real e-mails (auto request -> e-mail #1)
        rec["signers"] = {"designer": rec["signers"]["designer"]}
        # NOTE: auto request builds the link from the Origin header (browser sends it); without it the e-mail API rejects a relative link
        hh = {**h(), "Origin": BASE_URL}
        assert requests.put(f"{API}/data/prosumator/{S['d2']}", json=rec, headers=hh).status_code == 200
        st = requests.get(f"{API}/sld/{S['d2']}", headers=h()).json()
        ar = st["approval_requests"]
        assert len(ar) == 1 and ar[0]["auto"] is True
        assert ar[0]["recipients"][0]["sent"] is True and ar[0]["recipients"][0]["to"] == TEST_EMAIL
        # once per fingerprint: same save -> no new entry
        assert requests.put(f"{API}/data/prosumator/{S['d2']}", json=rec, headers=hh).status_code == 200
        st = requests.get(f"{API}/sld/{S['d2']}", headers=h()).json()
        assert len(st["approval_requests"]) == 1

    def test_21_manual_request_with_test_email_cleared_sent_false(self):
        setting("")
        r = requests.post(f"{API}/sld/{S['d2']}/request-approval", json={"origin": BASE_URL}, headers=h())
        assert r.status_code == 200, r.text
        e = r.json()
        assert e["auto"] is False and e["recipients"] and all(x["sent"] is False for x in e["recipients"])
        setting(TEST_EMAIL)

    def test_22_send_sign_and_otp(self):
        r = requests.post(f"{API}/sld/{S['d2']}/send-sign", json={"role": "designer", "origin": BASE_URL}, headers=h())
        assert r.status_code == 400  # not approved yet
        assert requests.post(f"{API}/sld/{S['d2']}/approve", json={"role": "designer"}, headers=h()).status_code == 200
        r = requests.post(f"{API}/sld/{S['d2']}/send-sign", json={"role": "designer", "origin": BASE_URL}, headers=h())  # e-mail #2
        assert r.status_code == 200, r.text
        req = r.json()[0]
        assert req["status"] == "Link trimis" and db_sign(req["id"]).get("is_test") is True
        pub = requests.get(f"{API}/public/sign/{req['token']}")
        assert pub.status_code == 200
        o = requests.post(f"{API}/public/sign/{req['token']}/otp")  # e-mail #3
        assert o.status_code == 200, o.text
        print("otp", o.json())
        setting("")

    def test_23_evidence_page_test_title(self):
        sys.path.insert(0, "/app/backend")
        import server
        from PIL import Image
        bb = io.BytesIO(); Image.new("RGB", (40, 20), "white").save(bb, "PNG")
        b = server.evidence_page({"is_test": True, "doc_title": "TEST doc", "client_name": "TEST", "role": "Proiectant", "signer_email": "a@b.c",
                                  "doc_sha256": "0" * 64, "id": "x"}, bb.getvalue(), {"ip": "1.1.1.1", "ua": "pytest"}, "TEST", "2026-01-01", "DNS")
        _, txt = pdf_text(b)
        assert "— TEST" in txt and "NU este o semnătură oficială" in txt


class TestC_Cleanup:
    def test_30_delete_only_test(self):
        r = requests.delete(f"{API}/test-dossier", headers=h())
        assert r.status_code == 200 and r.json()["deleted"] > 0
        for m, n in S["real_counts"].items():
            lst = requests.get(f"{API}/data/{m}", headers=h()).json()
            assert not any(x.get("is_test") for x in lst), m
            assert len(lst) == n, f"{m}: real count changed {n} -> {len(lst)}"
        for k in ("d1", "d2"):
            if S.get(k):
                assert requests.get(f"{API}/sld/{S[k]}", headers=h()).status_code == 404
        sr = requests.get(f"{API}/sign/requests", headers=h()).json()
        assert not any(x.get("dossier_id") in (S["d1"], S.get("d2")) for x in sr)

    def test_31_leave_fresh_dossier(self):
        setting("")
        r = requests.post(f"{API}/test-dossier", headers=h())
        assert r.status_code == 200 and r.json()["test_email"] is None
        with open("/tmp/testid", "w") as f:
            f.write(r.json()["prosumator_id"])
