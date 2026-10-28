# Seed/cleanup helper for iteration 27 UI test: python seed_iter27_ui.py seed|clean
import sys
from datetime import date, timedelta
from pymongo import MongoClient

env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
db = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
T = date.today()
if sys.argv[1] == "seed":
    for k, d in (("past", -8), ("soon", 20), ("mid", 60)):
        db.operators.insert_one({"tenant": f"TEST_ui27_{k}", "company": f"TEST UI {k} SRL", "cui": f"RO27UI{k}", "attest_no": f"UI/{k}", "contact_name": "TEST Maria",
                                 "contact_email": "delivered@resend.dev", "contact_phone": "0700", "status": "aprobat", "attest_types": ["A1"],
                                 "visa_date": (T + timedelta(days=d)).isoformat(), "visa_confirmed": k != "mid", "updated_at": T.isoformat()})
else:
    db.operators.delete_many({"tenant": {"$regex": "^TEST_ui27_"}})
print("ok")
