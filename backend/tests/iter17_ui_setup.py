# Setup/cleanup is_test prosumator with DEMO cef for iteration 17 UI tests
import os, sys, copy, requests
sys.path.insert(0, "/app/backend")
from sld_demo import DEMO_REC
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
H = {"Authorization": "Bearer " + requests.post(f"{API}/auth/login", json={"email": "drinkdrinc@gmail.com", "password": "DEnergy2026!"}).json()["access_token"]}
if sys.argv[1] == "setup":
    cl = requests.get(f"{API}/data/clients", headers=H).json()
    cname = next((c["name"] for c in cl if c["name"] == "Test Client SRL"), cl[0]["name"])
    print(requests.post(f"{API}/data/prosumator", headers=H, json={"client_name": cname, "is_test": True, "number_note": "TEST_iter17ui", "cef": copy.deepcopy(DEMO_REC["cef"])}).json()["id"])
else:
    for it in requests.get(f"{API}/data/prosumator", headers=H).json():
        if it.get("is_test") and it.get("number_note") == "TEST_iter17ui":
            print("del", it["id"], requests.delete(f"{API}/data/prosumator/{it['id']}", headers=H).status_code)
