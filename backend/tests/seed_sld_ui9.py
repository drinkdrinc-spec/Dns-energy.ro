# Helper (iter9): seed/clean an APPROVED TEST_ SLD record (designer with email) for UI tests. Usage: python seed_sld_ui9.py seed|clean
import os, sys, copy, json, requests
sys.path.insert(0, "/app/backend")
from sld_demo import DEMO_REC, DEMO_CLIENT
from pymongo import MongoClient
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
tok = requests.post(f"{API}/auth/login", json={"email": "drinkdrinc@gmail.com", "password": "DEnergy2026!"}).json()["access_token"]
s = requests.Session(); s.headers["Authorization"] = f"Bearer {tok}"
F = "/tmp/sld_ui9_ids.json"
AUTH = [{"type": "ANRE", "number": "UI9", "expires": "2030-12-31", "file": {"storage_path": "x"}, "verified": True}]
if sys.argv[1] == "seed":
    ids = {"designer": s.post(f"{API}/data/staff", json={"name": "TEST_UI9 designer", "email": "drinkdrinc@gmail.com", "phone": "0700000009", "auths": AUTH}).json()["id"],
           "verifier": s.post(f"{API}/data/staff", json={"name": "TEST_UI9 verifier", "auths": AUTH}).json()["id"]}
    cl = s.post(f"{API}/data/clients", json={**DEMO_CLIENT, "name": "TEST_UI9 SLD Client"}).json()
    ids["client"] = cl["id"]
    rec = copy.deepcopy(DEMO_REC)
    rec.update({"client_name": cl["name"], "client_id": cl["id"], "name": cl["name"], "address": DEMO_CLIENT["address"], "locality": DEMO_CLIENT["locality"],
                "county": DEMO_CLIENT["county"], "operator": DEMO_CLIENT["operator"], "signers": {"designer": ids["designer"], "verifier": ids["verifier"]}})
    ids["rec"] = s.post(f"{API}/data/prosumator", json=rec).json()["id"]
    print("approve", s.post(f"{API}/sld/{ids['rec']}/approve", json={"role": "designer"}).status_code)
    json.dump(ids, open(F, "w")); print(json.dumps(ids))
else:
    ids = json.load(open(F))
    MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")].sign_requests.delete_many({"dossier_id": ids["rec"]})
    s.delete(f"{API}/data/prosumator/{ids['rec']}"); s.delete(f"{API}/data/clients/{ids['client']}")
    for r in ("designer", "verifier"):
        s.delete(f"{API}/data/staff/{ids[r]}")
    print("cleaned")
