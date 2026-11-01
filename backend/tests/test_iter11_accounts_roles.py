import os as _dns_test_os
import pytest as _dns_test_pytest
if not (_dns_test_os.environ.get("DNS_ENERGY_TEST_EMAIL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_PASSWORD") and _dns_test_os.environ.get("REACT_APP_BACKEND_URL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_ALLOW_MUTATION") == "1"):
    _dns_test_pytest.skip("Set staging-only DNS_ENERGY_TEST_* credentials, REACT_APP_BACKEND_URL and DNS_ENERGY_TEST_ALLOW_MUTATION=1", allow_module_level=True)

# Iteration 11 — Phase A: accounts (register/approve/suspend/disable), roles, data separation, audit trail
import os, time, uuid
import pytest, requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = (_dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"], _dns_test_os.environ["DNS_ENERGY_TEST_PASSWORD"])
PWD = "TestPass123!"
TAG = f"test_phasea_{uuid.uuid4().hex[:6]}"


def _env(key):
    for line in open("/app/backend/.env"):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


mdb = MongoClient(_env("MONGO_URL"))[_env("DB_NAME")]
S = {}  # shared state


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


def login(email, pw):
    return requests.post(f"{API}/auth/login", json={"email": email, "password": pw})


@pytest.fixture(scope="module", autouse=True)
def setup_and_cleanup():
    r = login(*ADMIN)
    assert r.status_code == 200, r.text
    S["admin"] = r.json()["access_token"]
    S["admin_id"] = r.json()["user"]["id"]
    yield
    uids = [u["id"] for u in mdb.users.find({"email": {"$regex": f"^{TAG}"}}, {"id": 1})]
    for m in ("clients", "prosumator", "diu", "works", "mono", "equipment", "documents", "sign_requests"):
        mdb[m].delete_many({"created_by": {"$in": uids}})
    if S.get("admin_client"):
        mdb.clients.delete_one({"id": S["admin_client"]})
    mdb.users.delete_many({"email": {"$regex": f"^{TAG}"}})
    mdb.login_attempts.delete_many({"identifier": {"$regex": TAG}})
    mdb.audit.delete_many({"user": {"$regex": f"^{TAG}"}})


def register(kind):
    email = f"{TAG}_{kind}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": PWD, "name": f"TEST {kind}"})
    return email, r


# ---------- registration / approval ----------
class TestAccounts:
    def test_01_register_pending(self):
        for kind in ("inst", "lim", "eng", "brute", "susp"):
            email, r = register(kind)
            assert r.status_code == 200, r.text
            assert r.json().get("pending") is True
            assert "access_token" not in r.json()
            S[kind + "_email"] = email
        u = mdb.users.find_one({"email": S["inst_email"]})
        assert u["status"] == "pending" and u["role"] == "limitat" and u["tenant"] == S["admin_id"]
        assert u["password_hash"].startswith("$2b$")

    def test_02_duplicate_register(self):
        r = requests.post(f"{API}/auth/register", json={"email": S["inst_email"], "password": PWD})
        assert r.status_code == 400

    def test_03_login_pending_403(self):
        r = login(S["inst_email"], PWD)
        assert r.status_code == 403
        assert "Contul așteaptă aprobarea administratorului" in r.json()["detail"]

    def test_04_admin_lists_users(self):
        r = requests.get(f"{API}/admin/users", headers=h(S["admin"]))
        assert r.status_code == 200
        d = r.json()
        emails = {u["email"]: u for u in d["users"]}
        assert S["inst_email"] in emails and emails[S["inst_email"]]["status"] == "pending"
        assert set(d["roles"]) == {"admin", "inginer", "electrician", "instalator", "limitat"}
        assert all("password_hash" not in u for u in d["users"])
        for kind in ("inst", "lim", "eng", "brute", "susp"):
            S[kind + "_id"] = emails[S[kind + "_email"]]["id"]

    def test_05_approve(self):
        roles = {"inst": "instalator", "lim": "limitat", "eng": "inginer", "brute": "limitat", "susp": "electrician"}
        for kind, role in roles.items():
            r = requests.put(f"{API}/admin/users/{S[kind + '_id']}", headers=h(S["admin"]), json={"status": "active", "role": role})
            assert r.status_code == 200, r.text
        bad = requests.put(f"{API}/admin/users/{S['inst_id']}", headers=h(S["admin"]), json={"role": "superuser"})
        assert bad.status_code == 400
        main = requests.put(f"{API}/admin/users/{S['admin_id']}", headers=h(S["admin"]), json={"status": "disabled"})
        assert main.status_code == 404

    def test_06_login_and_me(self):
        for kind, role in (("inst", "instalator"), ("lim", "limitat"), ("eng", "inginer"), ("susp", "electrician")):
            r = login(S[kind + "_email"], PWD)
            assert r.status_code == 200, r.text
            S[kind] = r.json()["access_token"]
            me = requests.get(f"{API}/auth/me", headers=h(S[kind])).json()
            assert me["role"] == role and me["status"] == "active" and me["id"] == S[kind + "_id"]

    def test_07_brute_force(self):
        codes = [login(S["brute_email"], "wrong-pass").status_code for _ in range(5)]
        assert codes == [401] * 5
        r = login(S["brute_email"], "wrong-pass")
        assert r.status_code == 429
        r2 = login(S["brute_email"], PWD)  # still locked even with correct password
        assert r2.status_code == 429

    def test_08_admin_routes_forbidden(self):
        for kind in ("inst", "lim", "eng"):
            assert requests.get(f"{API}/admin/users", headers=h(S[kind])).status_code == 403
            assert requests.put(f"{API}/admin/users/{S['brute_id']}", headers=h(S[kind]), json={"status": "active"}).status_code == 403


# ---------- data separation ----------
class TestSeparation:
    def test_10_admin_dossier(self):
        items = requests.get(f"{API}/data/prosumator", headers=h(S["admin"])).json()
        assert len(items) > 0
        S["adm_pros"] = next((i["id"] for i in items if i.get("is_test")), items[0]["id"])
        S["adm_ids"] = {i["id"] for i in items}

    def test_11_installer_list_excludes_admin(self):
        items = requests.get(f"{API}/data/prosumator", headers=h(S["inst"])).json()
        assert not ({i["id"] for i in items} & S["adm_ids"])
        cl = requests.get(f"{API}/data/clients", headers=h(S["inst"])).json()
        assert all(c.get("created_by") == S["inst_id"] for c in cl)

    def test_12_installer_creates(self):
        r = requests.post(f"{API}/import/prosumator", headers=h(S["inst"]),
                          json={"client_name": f"TEST_PhaseA {TAG}", "power": "5", "assigned_to": ["x"]})
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["created_by"] == S["inst_id"] and p["created_by_email"] == S["inst_email"]
        S["inst_pros"] = p["id"]
        r = requests.post(f"{API}/data/clients", headers=h(S["inst"]), json={"name": f"TEST_cli {TAG}", "assigned_to": [S["inst_id"]]})
        assert r.status_code == 200
        c = r.json()
        assert c["created_by"] == S["inst_id"] and "assigned_to" not in c
        S["inst_client"] = c["id"]
        mine = {i["id"] for i in requests.get(f"{API}/data/prosumator", headers=h(S["inst"])).json()}
        adm = {i["id"] for i in requests.get(f"{API}/data/prosumator", headers=h(S["admin"])).json()}
        assert S["inst_pros"] in mine and S["inst_pros"] in adm
        assert requests.get(f"{API}/data/clients/{S['inst_client']}", headers=h(S["admin"])).status_code == 200

    def test_13_installer_404_on_admin_dossier(self):
        a = S["adm_pros"]
        tq = {"auth": S["inst"]}
        assert requests.get(f"{API}/data/prosumator/{a}", headers=h(S["inst"])).status_code == 404
        assert requests.put(f"{API}/data/prosumator/{a}", headers=h(S["inst"]), json={"notes": "x"}).status_code == 404
        assert requests.get(f"{API}/dossier/{a}", headers=h(S["inst"])).status_code == 404
        assert requests.get(f"{API}/sld/{a}", headers=h(S["inst"])).status_code == 404
        assert requests.get(f"{API}/sld/{a}/pdf", params=tq).status_code == 404
        assert requests.get(f"{API}/sld/{a}/report", params=tq).status_code == 404
        assert requests.get(f"{API}/dossier/{a}/export", params=tq).status_code == 404
        assert requests.get(f"{API}/dossier/{a}/file/opis", params=tq).status_code == 404
        assert requests.get(f"{API}/docs/fisa_tehnica/{a}", params=tq).status_code == 404
        assert requests.get(f"{API}/docs/sizing/{a}", headers=h(S["inst"])).status_code == 404
        assert requests.get(f"{API}/sign/requests", params={"dossier_id": a}, headers=h(S["inst"])).status_code == 404

    def test_14_installer_reopen_admin_dossier_blocked(self):
        r = requests.post(f"{API}/dossier/{S['adm_pros']}/reopen", headers=h(S["inst"]))
        # Expected 404/403 — reopen has no check_access
        assert r.status_code in (403, 404), f"reopen admin dossier by installer returned {r.status_code}"

    def test_15_non_admin_cannot_assign_or_delete(self):
        r = requests.put(f"{API}/data/prosumator/{S['inst_pros']}", headers=h(S["inst"]), json={"assigned_to": [S["lim_id"]], "notes": "upd"})
        assert r.status_code == 200
        d = r.json()
        assert "assigned_to" not in d or S["lim_id"] not in d["assigned_to"]
        assert d["updated_by"] == S["inst_email"]
        assert requests.delete(f"{API}/data/prosumator/{S['inst_pros']}", headers=h(S["inst"])).status_code == 403
        assert requests.delete(f"{API}/data/clients/{S['inst_client']}", headers=h(S["inst"])).status_code == 403

    def test_16_admin_assigns(self):
        r = requests.put(f"{API}/data/prosumator/{S['adm_pros']}", headers=h(S["admin"]), json={"assigned_to": [S["inst_id"]]})
        assert r.status_code == 200 and r.json()["assigned_to"] == [S["inst_id"]]
        assert r.json()["updated_by"] == ADMIN[0]
        assert requests.get(f"{API}/data/prosumator/{S['adm_pros']}", headers=h(S["inst"])).status_code == 200
        assert requests.get(f"{API}/dossier/{S['adm_pros']}", headers=h(S["inst"])).status_code == 200
        assert requests.get(f"{API}/sld/{S['adm_pros']}", headers=h(S["inst"])).status_code == 200
        ids = {i["id"] for i in requests.get(f"{API}/data/prosumator", headers=h(S["inst"])).json()}
        assert S["adm_pros"] in ids
        # revoke assignment
        r = requests.put(f"{API}/data/prosumator/{S['adm_pros']}", headers=h(S["admin"]), json={"assigned_to": []})
        assert r.status_code == 200
        assert requests.get(f"{API}/data/prosumator/{S['adm_pros']}", headers=h(S["inst"])).status_code == 404

    def test_17_dashboard_stats_scoped(self):
        adm = requests.get(f"{API}/stats/dashboard", headers=h(S["admin"])).json()
        ins = requests.get(f"{API}/stats/dashboard", headers=h(S["inst"])).json()
        assert ins["clients"] < adm["clients"] or adm["clients"] == 0, f"installer dashboard shows tenant-wide counts: {ins['clients']} clients, recent={len(ins['recent'])}"

    def test_18_audit_scoped(self):
        r = requests.get(f"{API}/audit", headers=h(S["inst"]))
        users = {a.get("user") for a in r.json()} if r.status_code == 200 else set()
        assert r.status_code == 403 or users <= {S["inst_email"]}, f"installer sees audit of {len(users)} users"

    def test_19_import_same_name_links_admin_client(self):
        adm_client = requests.post(f"{API}/data/clients", headers=h(S["admin"]), json={"name": f"TEST_admcli {TAG}", "idcode": "1900101000000", "phone": "0700000000"}).json()
        S["admin_client"] = adm_client["id"]
        r = requests.post(f"{API}/import/prosumator", headers=h(S["inst"]), json={"client_name": f"TEST_admcli {TAG}"})
        assert r.status_code == 200
        assert r.json()["client_id"] != adm_client["id"], "installer import linked to an ADMIN client by name (client data exposed via dossier)"

    def test_19b_file_download_unscoped(self):
        doc = mdb.documents.find_one({"owner": S["admin_id"], "created_by": {"$ne": S["inst_id"]}, "storage_path": {"$exists": True}})
        if not doc:
            pytest.skip("no admin document")
        r = requests.get(f"{API}/files/{doc['storage_path']}", params={"auth": S["inst"]})
        assert r.status_code in (403, 404), f"installer downloaded admin file: {r.status_code}"


# ---------- permissions ----------
class TestPermissions:
    def test_20_limitat_read_only(self):
        assert requests.post(f"{API}/data/clients", headers=h(S["lim"]), json={"name": "TEST_x"}).status_code == 403
        assert requests.post(f"{API}/import/prosumator", headers=h(S["lim"]), json={"client_name": "TEST_x"}).status_code == 403
        assert requests.put(f"{API}/data/clients/{S['inst_client']}", headers=h(S["lim"]), json={"name": "y"}).status_code == 403
        assert requests.get(f"{API}/data/prosumator", headers=h(S["lim"])).status_code == 200
        assert requests.get(f"{API}/data/staff", headers=h(S["lim"])).status_code == 403

    def test_21_non_admin_settings_staff_testdossier(self):
        for kind in ("inst", "eng"):
            t = h(S[kind])
            assert requests.put(f"{API}/settings", headers=t, json={"company": "HACK"}).status_code == 403
            assert requests.post(f"{API}/data/staff", headers=t, json={"name": "TEST_s"}).status_code == 403
            assert requests.post(f"{API}/data/instruments", headers=t, json={"name": "TEST_i"}).status_code == 403
            assert requests.post(f"{API}/test-dossier", headers=t).status_code == 403
            assert requests.delete(f"{API}/test-dossier", headers=t).status_code == 403
        assert requests.get(f"{API}/settings", headers=h(S["admin"])).json().get("company") != "HACK"

    def test_22_sld_approve_roles(self):
        r = requests.post(f"{API}/sld/{S['inst_pros']}/approve", headers=h(S["inst"]), json={"role": "designer"})
        assert r.status_code == 403
        # inginer passes role check (may 404 since not assigned / 400 data missing — not 403)
        mdb.prosumator.update_one({"id": S["inst_pros"]}, {"$set": {"assigned_to": [S["eng_id"]]}})
        r = requests.post(f"{API}/sld/{S['inst_pros']}/approve", headers=h(S["eng"]), json={"role": "designer"})
        assert r.status_code != 403, r.text

    def test_23_limitat_cannot_write_via_sld_dossier(self):
        mdb.prosumator.update_one({"id": S["inst_pros"]}, {"$set": {"assigned_to": [S["eng_id"], S["lim_id"]]}})
        t = h(S["lim"])
        res = {
            "sld_source": requests.put(f"{API}/sld/{S['inst_pros']}/source", headers=t, json={"source": "generated"}).status_code,
            "dossier_item": requests.put(f"{API}/dossier/{S['inst_pros']}/item/opis", headers=t, json={"status": None}).status_code,
            "reopen": requests.post(f"{API}/dossier/{S['inst_pros']}/reopen", headers=t).status_code,
        }
        assert all(c == 403 for c in res.values()), f"limitat write endpoints: {res}"


# ---------- suspend / disable ----------
class TestStatus:
    def test_30_suspend_then_disable(self):
        tok = S["susp"]
        assert requests.get(f"{API}/auth/me", headers=h(tok)).status_code == 200
        requests.put(f"{API}/admin/users/{S['susp_id']}", headers=h(S["admin"]), json={"status": "suspended"})
        r = requests.get(f"{API}/auth/me", headers=h(tok))
        assert r.status_code == 403 and "suspendat" in r.json()["detail"]
        assert login(S["susp_email"], PWD).status_code == 403
        requests.put(f"{API}/admin/users/{S['susp_id']}", headers=h(S["admin"]), json={"status": "disabled"})
        r = requests.get(f"{API}/auth/me", headers=h(tok))
        assert r.status_code == 403 and "dezactivat" in r.json()["detail"]
        assert requests.get(f"{API}/sld/{S['inst_pros']}/pdf", params={"auth": tok}).status_code == 403
        doc = mdb.documents.find_one({"owner": S["admin_id"], "storage_path": {"$exists": True}})
        if doc:
            fr = requests.get(f"{API}/files/{doc['storage_path']}", params={"auth": tok})
            assert fr.status_code in (401, 403), f"disabled user downloaded file: {fr.status_code}"

    def test_31_audit_records(self):
        acts = list(mdb.audit.find({"owner": S["admin_id"], "$or": [{"item_id": {"$in": [S["inst_pros"], S["susp_id"], S["inst_client"]]}}]}))
        kinds = {(a["user"], a["action"]) for a in acts}
        assert (S["inst_email"], "modificare") in kinds
        assert (S["inst_email"], "creare") in kinds  # clients create
        assert (ADMIN[0], "cont utilizator") in kinds
        assert any(a["action"].startswith("înregistrare") for a in mdb.audit.find({"item_id": S["inst_id"]}))
