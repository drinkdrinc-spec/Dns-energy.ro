# Iteration 12 — manual check: stamp/signature images auto-applied on generated PDFs + signer_warnings
import os, io, requests
from pypdf import PdfReader
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
tok = requests.post(f"{API}/auth/login", json={"email": "drinkdrinc@gmail.com", "password": "DEnergy2026!"}).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}
pid = "3f6fd4d4-f603-4880-9a11-304820c2d3e3"
info = requests.get(f"{API}/dossier/{pid}", headers=H).json()
print("signer_warnings:", info.get("signer_warnings"))
types = requests.get(f"{API}/docs/types", headers=H).json()
print("types:", str(types)[:300])
keys = [t.get("key") or t.get("id") or t for t in (types if isinstance(types, list) else types.get("types", []))]
for k in keys[:25]:
    r = requests.get(f"{API}/docs/{k}/{pid}?format=pdf", headers=H)
    if r.status_code != 200 or r.content[:4] != b"%PDF":
        print(k, r.status_code, r.headers.get("content-type")); continue
    n = r.content.count(b"/Subtype /Image")
    print(k, "images:", n)
