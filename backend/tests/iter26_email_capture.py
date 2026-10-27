# Captures the visa reminder html built by run_visa (send_email patched) and validates it with mailer._assert_safe_email
import asyncio
import sys
import uuid
from datetime import date, timedelta
sys.path.insert(0, "/app/backend")
import operator_routes as OR
import mailer

cap = []


async def fake(**kw):
    mailer._assert_safe_email(kw["subject"], kw["html"])
    cap.append(kw)


async def main():
    OR.send_email = fake
    ten = "TEST_iter26_cap_" + uuid.uuid4().hex[:6]
    vd = (date.today() + timedelta(days=20)).isoformat()
    await OR.db.operators.insert_one({"tenant": ten, "company": "TEST Cap <b>SRL</b>", "attest_no": "9/X", "contact_email": "delivered@resend.dev", "visa_date": vd, "visa_confirmed": True})
    try:
        await OR.run_visa("TEST-cap", "https://dns-energy.preview.emergentagent.com")
    finally:
        await OR.db.operators.delete_many({"tenant": ten})
        await OR.db.reminders.delete_many({"id": {"$regex": f"^visa:{ten}"}})
    mine = [c for c in cap if "TEST Cap" in c["html"]]
    print("captured", len(cap), "mine", len(mine))
    h = mine[0]["html"]
    print("link ok:", 'href="https://dns-energy.preview.emergentagent.com/dosare-anre?tip=vizare"' in h, "| button:", "Comandă dosarul de vizare" in h, "| escaped:", "&lt;b&gt;SRL" in h)
    print(mine[0]["subject"])

asyncio.run(main())
