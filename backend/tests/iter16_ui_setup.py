import os as _dns_test_os
if not (_dns_test_os.environ.get("DNS_ENERGY_TEST_EMAIL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_PASSWORD") and _dns_test_os.environ.get("REACT_APP_BACKEND_URL") and _dns_test_os.environ.get("DNS_ENERGY_TEST_ALLOW_MUTATION") == "1"):
    raise SystemExit("Set staging-only DNS_ENERGY_TEST_* credentials, REACT_APP_BACKEND_URL and DNS_ENERGY_TEST_ALLOW_MUTATION=1 before running this helper.")

# Setup/cleanup helper for iteration 16 UI tests: legacy is_test prosumator + is_test ATR (registered) ; 'cleanup' deletes them
import sys, json, copy, requests
sys.path.insert(0, "/app/backend")
API = "https://dns-energy.preview.emergentagent.com/api"
tok = requests.post(f"{API}/auth/login", json={"email": _dns_test_os.environ["DNS_ENERGY_TEST_EMAIL"], "password": _dns_test_os.environ["DNS_ENERGY_TEST_PASSWORD"]}).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}
TAG = "TEST_iter16_ui"
cmd = sys.argv[1]
if cmd == "setup":
    out = {}
    r = requests.post(f"{API}/data/prosumator", headers=H, json={"client_name": "Test Client SRL", "is_test": True, "number_note": TAG, "supply": "Trifazat",
                      "inverter": "Solis S6-EH3P12K02-NV-YD-L", "inverter_kw": 12, "inverter_count": 1, "panels": "Aiko 475W", "panel_count": 26, "panel_w": 475,
                      "battery": "Ecobat 16 kWh", "battery_kwh": 16})
    out["pros"] = r.json()["id"]; out["pros_number"] = r.json().get("number")
    from sld_demo import DEMO_REC
    invs = []
    for k, name in enumerate(("TESTBRAND Alpha 10K", "TESTBRAND Beta 8K", "TESTBRAND Gamma 6K")):
        x = copy.deepcopy(DEMO_REC["cef"]["inverters"][0]); x["brand_model"] = name
        x["strings"] = [{"panels": 10, "mppt": 1}, {"panels": 10, "mppt": 2}]
        if k: x["battery_mode"] = "none"; x["battery"] = None
        invs.append(x)
    r = requests.post(f"{API}/data/prosumator", headers=H, json={"client_name": "Test Client SRL", "is_test": True, "number_note": TAG, "supply": "Trifazat",
                      "cef": {"tmin": -10, "grid": DEMO_REC["cef"]["grid"], "inverters": invs, "shared_batteries": []}})
    out["multi"] = r.json()["id"]
    r = requests.post(f"{API}/data/atr", headers=H, json={"client_name": "Test Client SRL", "operator": "DEER — Transilvania Nord", "kind": "Loc de consum", "is_test": True, "number_note": TAG})
    out["atr"] = r.json()["id"]
    requests.post(f"{API}/atr/{out['atr']}/track", headers=H, json={"action": "register", "reg_no": "TEST-UI-1", "reg_date": "2026-10-20"})
    r = requests.post(f"{API}/data/atr", headers=H, json={"client_name": "Test Client SRL", "operator": "DEER — Transilvania Nord", "kind": "Loc de consum", "is_test": True, "number_note": TAG})
    out["atr2"] = r.json()["id"]
    requests.post(f"{API}/atr/{out['atr2']}/track", headers=H, json={"action": "register", "reg_no": "TEST-UI-2", "reg_date": "2026-10-20"})
    print(json.dumps(out))
elif cmd == "cleanup":
    for m in ("prosumator", "atr"):
        for it in requests.get(f"{API}/data/{m}", headers=H).json():
            if it.get("is_test") and it.get("number_note") == TAG:
                print("del", m, it["id"], requests.delete(f"{API}/data/{m}/{it['id']}", headers=H).status_code)
