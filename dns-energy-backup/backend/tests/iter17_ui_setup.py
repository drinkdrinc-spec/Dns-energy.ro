import os as _dns_test_os
if not (_dns_test_os.environ.get("DNS_ENERGY_TEST_EMAIL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_PASSWORD") and _dns_test_os.environ.get("REACT_APP_BACKEND_URL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_ALLOW_MUTATION") == "1"):
    raise SystemExit("Set staging-only DNS_ENERGY_TEST_* credentials, REACT_APP_BACKEND_URL and DNS_ENERGY_TEST_ALLOW_MUTATION=1 before running this helper.")

# Setup/cleanup is_test prosumator with DEMO cef for iteration 17 UI tests
import os, sys, copy, requests
sys.path.insert(0, "/app/backend")
from sld_demo import DEMO_REC
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
H = {"Authorization": "Bearer " + requests.post(f"{API}/auth/login", json={"email": _dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"], "password": _dns_test_os.environ["DNS_ENERGY_TEST_PASSWORD"]}).json()["access_token"]}
if sys.argv[1] == "setup":
    cl = requests.get(f"{API}/data/clients", headers=H).json()
    cname = next((c["name"] for c in cl if c["name"] == "Test Client SRL"), cl[0]["name"])
    print(requests.post(f"{API}/data/prosumator", headers=H, json={"client_name": cname, "is_test": True, "number_note": "TEST_iter17ui", "cef": copy.deepcopy(DEMO_REC["cef"])}).json()["id"])
else:
    for it in requests.get(f"{API}/data/prosumator", headers=H).json():
        if it.get("is_test") and it.get("number_note") == "TEST_iter17ui":
            print("del", it["id"], requests.delete(f"{API}/data/prosumator/{it['id']}", headers=H).status_code)
