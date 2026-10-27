# Iteration 18 helper: inject a known OTP for a signing token (OTP is hashed; test dossiers w/o test_email don't send). Usage: python iter18_sign_helper.py TOKEN [sign]
import sys, hashlib, os, io, base64, random, requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
from PIL import Image

env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
mdb = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
tok = sys.argv[1]
r = mdb.sign_requests.find_one({"token_hash": hashlib.sha256(tok.encode()).hexdigest()})
mdb.sign_requests.update_one({"id": r["id"]}, {"$set": {"otp_hash": hashlib.sha256(f"{r['id']}:123456".encode()).hexdigest(),
                                                        "otp_exp": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(), "otp_attempts": 0}})
print("otp set for", r["id"], r["pos_key"])
if len(sys.argv) > 2:
    img = Image.new("RGB", (300, 120), "white"); px = img.load()
    for _ in range(4000):
        px[random.randrange(300), random.randrange(120)] = (0, 0, random.randrange(255))
    b = io.BytesIO(); img.save(b, "PNG")
    API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
    x = requests.post(f"{API}/public/sign/{tok}/sign", json={"otp": "123456", "intent": True, "declared_name": "TEST Client",
                                                             "signature": "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()})
    print(x.status_code, x.text[:200])
