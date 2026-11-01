import os as _dns_test_os
if not (_dns_test_os.environ.get("DNS_ENERGY_TEST_EMAIL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_PASSWORD") and _dns_test_os.environ.get("REACT_APP_BACKEND_URL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_ALLOW_MUTATION") == "1"):
    raise SystemExit("Set staging-only DNS_ENERGY_TEST_* credentials, REACT_APP_BACKEND_URL and DNS_ENERGY_TEST_ALLOW_MUTATION=1 before running this helper.")

# Helper: seed / cleanup a TEST_ SLD record for UI testing. Usage: python seed_sld_ui.py [seed|clean]
import os, sys, copy, json, requests
sys.path.insert(0, "/app/backend")
from sld_demo import DEMO_REC, DEMO_CLIENT
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
tok = requests.post(f"{API}/auth/login", json={"email": _dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"], "password": _dns_test_os.environ["DNS_ENERGY_TEST_PASSWORD"]}).json()["access_token"]
s = requests.Session(); s.headers["Authorization"] = f"Bearer {tok}"
F = "/tmp/sld_ui_ids.json"
if sys.argv[1] == "seed":
    ids = {}
    for r in ("designer", "verifier"):
        ids[r] = s.post(f"{API}/data/staff", json={"name": f"TEST_UI {r}", "auths": [{"type": "ANRE", "number": "UI1", "expires": "2030-12-31", "file": {"storage_path": "x"}, "verified": True}]}).json()["id"]
    cl = s.post(f"{API}/data/clients", json={**DEMO_CLIENT, "name": "TEST_UI SLD Client"}).json()
    ids["client"] = cl["id"]
    rec = copy.deepcopy(DEMO_REC)
    rec.update({"client_name": cl["name"], "client_id": cl["id"], "name": cl["name"], "address": DEMO_CLIENT["address"], "locality": DEMO_CLIENT["locality"],
                "county": DEMO_CLIENT["county"], "operator": DEMO_CLIENT["operator"], "signers": {"designer": ids["designer"], "verifier": ids["verifier"]}})
    ids["rec"] = s.post(f"{API}/data/prosumator", json=rec).json()["id"]
    json.dump(ids, open(F, "w")); print(json.dumps(ids)); print("status", s.get(f"{API}/sld/{ids['rec']}").json()["ready"])
elif sys.argv[1] == "show":
    ids = json.load(open(F)); d = s.get(f"{API}/sld/{ids['rec']}").json()
    print(json.dumps({k: d[k] for k in ("source", "upload", "revision", "ready")}), json.dumps(d["approval"])[:800])
else:
    ids = json.load(open(F))
    s.delete(f"{API}/data/prosumator/{ids['rec']}"); s.delete(f"{API}/data/clients/{ids['client']}")
    for r in ("designer", "verifier"):
        s.delete(f"{API}/data/staff/{ids[r]}")
    print("cleaned")
