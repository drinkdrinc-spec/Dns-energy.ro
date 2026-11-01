import os as _dns_test_os
if not (_dns_test_os.environ.get("DNS_ENERGY_TEST_EMAIL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_PASSWORD") and _dns_test_os.environ.get("REACT_APP_BACKEND_URL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_ALLOW_MUTATION") == "1"):
    raise SystemExit("Set staging-only DNS_ENERGY_TEST_* credentials, REACT_APP_BACKEND_URL and DNS_ENERGY_TEST_ALLOW_MUTATION=1 before running this helper.")

# Seed a TEST dossier with 2 approved revisions (rev0, rev1 after AC length change) for UI compare checks. No e-mails (test_email must be empty).
import os, requests
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
t = requests.post(f"{API}/auth/login", json={"email": _dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"], "password": _dns_test_os.environ["DNS_ENERGY_TEST_PASSWORD"]}).json()["access_token"]
h = {"Authorization": f"Bearer {t}"}
assert not (requests.get(f"{API}/settings", headers=h).json().get("test_email") or "")
pid = requests.post(f"{API}/test-dossier", headers=h).json()["prosumator_id"]
assert requests.post(f"{API}/sld/{pid}/approve", json={"role": "designer"}, headers=h).status_code == 200
rec = requests.get(f"{API}/data/prosumator/{pid}", headers=h).json()
rec["cef"]["inverters"][0]["ac"]["length_m"] = 40
requests.put(f"{API}/data/prosumator/{pid}", json=rec, headers=h)
assert requests.post(f"{API}/sld/{pid}/approve", json={"role": "designer"}, headers=h).status_code == 200
open("/tmp/uiid", "w").write(pid); open("/tmp/tok", "w").write(t)
print(pid)
