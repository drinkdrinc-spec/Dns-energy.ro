import os as _dns_test_os
if not (_dns_test_os.environ.get("DNS_ENERGY_TEST_EMAIL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_PASSWORD") and _dns_test_os.environ.get("REACT_APP_BACKEND_URL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_ALLOW_MUTATION") == "1"):
    raise SystemExit("Set staging-only DNS_ENERGY_TEST_* credentials, REACT_APP_BACKEND_URL and DNS_ENERGY_TEST_ALLOW_MUTATION=1 before running this helper.")

# Setup/cleanup helper for iteration 16 frontend tests (ATR tracking UI)
import sys, json, requests
API = "https://dns-energy.preview.emergentagent.com/api"
tok = requests.post(f"{API}/auth/login", json={"email": _dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"], "password": _dns_test_os.environ["DNS_ENERGY_TEST_PASSWORD"]}).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}
cmd = sys.argv[1]
if cmd == "setup":
    clients = requests.get(f"{API}/data/clients", headers=H).json()
    cname = clients[0]["name"] if clients else "TEST client"
    r = requests.post(f"{API}/data/atr", headers=H, json={"client_name": cname, "operator": "DEER — Transilvania Nord", "kind": "Loc de consum", "is_test": True, "number_note": "TEST_iter16"})
    print(r.status_code, json.dumps({k: r.json().get(k) for k in ("id", "number", "client_name", "atr_track", "is_test")}))
    email = "sub_iter16@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Test2026!x", "name": "TEST Sub16", "billing": {"client_type": "pf", "full_name": "TEST Sub16", "address": "Str 1", "locality": "Cluj", "county": "Cluj", "country": "Romania", "phone": "0700000000"}})
    print("register", r.status_code, r.text[:200])
    subs = requests.get(f"{API}/admin/subscribers", headers=H).json()
    uid = next((s.get("id") for s in subs if s.get("email") == email), None)
    print("uid", uid, requests.put(f"{API}/admin/subscribers/{uid}", headers=H, json={"status": "active"}).status_code)
elif cmd == "cleanup":
    for it in requests.get(f"{API}/data/atr", headers=H).json():
        if it.get("is_test") and it.get("number_note") == "TEST_iter16":
            print("del atr", it["id"], requests.delete(f"{API}/data/atr/{it['id']}", headers=H).status_code)
    subs = requests.get(f"{API}/admin/subscribers", headers=H).json()
    for s in subs:
        if s.get("email") == "sub_iter16@example.com":
            print("del sub", requests.delete(f"{API}/admin/subscribers/{s['id']}", headers=H).status_code)
