import os
import io
import csv
import re
import uuid
import hmac
import asyncio
import calendar
import logging
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal, ROUND_HALF_UP
from html import escape as hesc
from typing import Optional

import stripe
from fastapi import HTTPException, Request, Depends, Header, Query, Response, BackgroundTasks

import server as S
from mailer import send_email

db, api, get_current_user = S.db, S.api_router, S.get_current_user
logger = logging.getLogger("d-energy.billing")
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
PENDING, PAID, FAILED, CANCELLED, REFUNDED, EXPIRED = "în așteptarea plății", "plătită", "eșuată", "anulată", "rambursată", "expirată"

# ---------------- helpers ----------------
def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def today() -> date:
    return datetime.now(timezone.utc).date()

def money(x) -> float:
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))

def quote(plan: dict, months: int, vat_rate: float, credit: float = 0.0) -> dict:
    gross = money(Decimal(str(plan["price"])) * months)
    credit = min(money(credit), gross)
    net = money(Decimal(str(gross)) - Decimal(str(credit)))
    vat = money(Decimal(str(net)) * Decimal(str(vat_rate)) / 100)
    return {"unit": money(plan["price"]), "months": months, "gross": gross, "credit": credit, "net": net, "vat_rate": vat_rate, "vat": vat,
            "total": money(Decimal(str(net)) + Decimal(str(vat)))}

async def upgrade_credit(tenant: str, new_plan: dict) -> dict:
    """Unused value of the current paid plan (net, from its last paid proforma) when moving to a more expensive plan."""
    sub = await db.subscriptions.find_one({"tenant": tenant}, {"_id": 0}) or {}
    t = today()
    if sub.get("status") != "activ" or (sub.get("valid_until") or "") < t.isoformat() or sub.get("plan") == new_plan["code"]:
        return {"credit": 0.0}
    cur = await db.plans.find_one({"code": sub.get("plan")}, {"_id": 0}) or {}
    if float(cur.get("price") or 0) > float(new_plan["price"]):
        raise HTTPException(status_code=400, detail=f"Trecerea la un abonament inferior este posibilă după expirarea abonamentului actual ({sub['valid_until']}).")
    inv = await db.invoices.find_one({"tenant": tenant, "status": PAID, "plan": sub.get("plan"), "period_to": sub.get("valid_until")}, {"_id": 0})
    if not inv or not inv.get("period_from"):
        return {"credit": 0.0, "note": "Abonamentul actual a fost atribuit manual — fără credit automat."}
    total_days = (date.fromisoformat(inv["period_to"]) - date.fromisoformat(inv["period_from"])).days + 1
    left = (date.fromisoformat(sub["valid_until"]) - max(t, date.fromisoformat(inv["period_from"]))).days + 1
    left = max(0, min(left, total_days))
    credit = money(Decimal(str(inv["net"])) * left / total_days) if total_days else 0.0
    return {"credit": credit, "days": left, "from_plan": cur.get("name"), "from_invoice": inv["number"],
            "note": f"Credit pentru {left} zile neconsumate din {cur.get('name')} ({inv['number']})"}

def is_platform(user: dict) -> bool:
    return user["uid"] == S.PLATFORM["id"]

def platform_only(user: dict):
    if not is_platform(user):
        raise HTTPException(status_code=403, detail="Doar administratorul platformei are acces la această secțiune")

def owner_only(user: dict):
    if user["uid"] != user["id"] or user.get("account_type") == "team":
        raise HTTPException(status_code=403, detail="Doar titularul contului poate gestiona abonamentul și datele de facturare")

# ---------------- billing profile ----------------
PF_REQ = {"full_name": "Nume și prenume", "address": "Adresă de facturare", "locality": "Localitate", "county": "Județ", "country": "Țară"}
PJ_REQ = {"company_name": "Denumire firmă", "cui": "CUI/CIF", "regcom": "Nr. Registrul Comerțului", "hq_address": "Sediu social",
          "county": "Județ", "locality": "Localitate", "country": "Țară", "rep_name": "Nume și prenume reprezentant"}
COMMON_REQ = {"billing_email": "E-mail facturare", "phone": "Telefon"}
FIELDS = ("client_type", "full_name", "cnp", "address", "company_name", "cui", "regcom", "hq_address", "county", "locality", "country",
          "postal_code", "rep_name", "billing_email", "phone", "contact_person", "contact_phone", "vat_payer", "bank", "iban", "notes")
SENSITIVE = ("cnp", "iban")

def validate_profile(b: dict, email: str = "") -> dict:
    p = {k: (b.get(k).strip() if isinstance(b.get(k), str) else b.get(k)) for k in FIELDS if b.get(k) not in (None, "")}
    p.setdefault("billing_email", email)
    p.setdefault("country", "România")
    if p.get("client_type") not in ("pf", "pj"):
        raise HTTPException(status_code=400, detail="Alegeți tipul de client: persoană fizică sau persoană juridică")
    req = {**(PF_REQ if p["client_type"] == "pf" else PJ_REQ), **COMMON_REQ}
    miss = [lbl for k, lbl in req.items() if not p.get(k)]
    if miss:
        raise HTTPException(status_code=400, detail="Date de facturare incomplete: " + ", ".join(miss))
    if p.get("cui") and not re.fullmatch(r"(RO)?\s?\d{2,10}", p["cui"].upper()):
        raise HTTPException(status_code=400, detail="CUI/CIF invalid (ex. RO12345678 sau 12345678)")
    if p.get("cnp") and not re.fullmatch(r"\d{13}", p["cnp"]):
        raise HTTPException(status_code=400, detail="CNP invalid (13 cifre) — câmpul este opțional")
    if "@" not in (p.get("billing_email") or ""):
        raise HTTPException(status_code=400, detail="E-mail de facturare invalid")
    if p["client_type"] == "pf":
        for k in ("company_name", "cui", "regcom", "hq_address", "vat_payer"):
            p.pop(k, None)
    else:
        p.pop("cnp", None)
    return p

async def save_profile(tenant: str, prof: dict, by: str, old: dict):
    changes = {k: ["***" if k in SENSITIVE else old.get(k), "***" if k in SENSITIVE else prof.get(k)]
               for k in set(prof) | set(k for k in old if k in FIELDS) if prof.get(k) != old.get(k)}
    await db.billing_profiles.update_one({"tenant": tenant}, {"$set": {**prof, "tenant": tenant, "updated_at": now(), "updated_by": by}}, upsert=True)
    if changes:
        await db.billing_history.insert_one({"id": str(uuid.uuid4()), "tenant": tenant, "kind": "date facturare", "at": now(), "by": by,
                                            "detail": ", ".join(sorted(changes)), "changes": changes})

async def get_profile(tenant: str) -> dict:
    return await db.billing_profiles.find_one({"tenant": tenant}, {"_id": 0}) or {}

async def plans() -> list:
    return await db.plans.find({}, {"_id": 0}).sort("order", 1).to_list(20)

async def get_plan(code: str) -> dict:
    p = await db.plans.find_one({"code": code, "active": {"$ne": False}}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=400, detail="Abonament inexistent")
    return p

def fiscal_note(prof: dict) -> str:
    c = (prof.get("country") or "România").strip().lower()
    if c not in ("românia", "romania", "ro"):
        return "Client din afara României — regimul TVA (taxare inversă / neimpozabil) se verifică de administrator înainte de emiterea facturii fiscale."
    return ""

async def log(tenant: str, kind: str, by: str, detail: str, extra: dict = None):
    await db.billing_history.insert_one({"id": str(uuid.uuid4()), "tenant": tenant, "kind": kind, "at": now(), "by": by, "detail": detail, **(extra or {})})

async def next_number() -> str:
    y = today().year
    c = await db.counters.find_one_and_update({"id": f"proforma-{y}"}, {"$inc": {"seq": 1}}, upsert=True, return_document=True)
    return f"DEN-PF-{y}-{c['seq']:04d}"

async def new_invoice(tenant: str, email: str, plan: dict, months: int, by: str, vat_rate: Optional[float] = None, source: str = "online") -> dict:
    prof = await get_profile(tenant)
    if not prof:
        raise HTTPException(status_code=400, detail="Completați întâi datele de facturare")
    cfg = await S.billing_cfg()
    cr = await upgrade_credit(tenant, plan)
    q = quote(plan, months, float(cfg.get("vat_rate", 21)) if vat_rate is None else float(vat_rate), cr.get("credit", 0))
    q["credit_note"] = cr.get("note", "") if q["credit"] else ""
    issuer = await db.settings.find_one({"owner": S.PLATFORM["id"]}, {"_id": 0, "company": 1, "cui": 1, "regcom": 1, "address": 1, "phone": 1, "email": 1, "iban": 1, "bank": 1}) or {}
    inv = {"id": str(uuid.uuid4()), "number": await next_number(), "tenant": tenant, "user_email": email, "plan": plan["code"], "plan_name": plan["name"],
           **q, "currency": "RON", "status": PENDING, "client": {k: v for k, v in prof.items() if k not in ("_id", "tenant")},
           "issuer": issuer, "note": fiscal_note(prof), "source": source, "created_at": now(), "created_by": by, "payments": []}
    await db.invoices.insert_one(dict(inv))
    await log(tenant, "proformă emisă", by, f"{inv['number']} — {plan['name']} × {months} lună(i), total {q['total']:.2f} RON")
    inv.pop("_id", None)
    return inv

async def activate(inv_id: str, by: str, how: str) -> bool:
    """Marks the proforma paid exactly once and extends the subscription. Returns False when already processed."""
    inv = await db.invoices.find_one_and_update({"id": inv_id, "status": {"$in": [PENDING, FAILED, EXPIRED]}},
                                                {"$set": {"status": PAID, "paid_at": now(), "paid_via": how}}, return_document=True)
    if not inv:
        return False
    sub = await db.subscriptions.find_one({"tenant": inv["tenant"]}, {"_id": 0}) or {}
    start = today()
    if sub.get("plan") == inv["plan"] and sub.get("status") == "activ" and (sub.get("valid_until") or "") >= start.isoformat():
        start = date.fromisoformat(sub["valid_until"]) + timedelta(days=1)
    until = add_months(start, int(inv["months"])) - timedelta(days=1)
    await db.subscriptions.update_one({"tenant": inv["tenant"]}, {"$set": {"tenant": inv["tenant"], "plan": inv["plan"], "status": "activ",
                                       "valid_from": start.isoformat(), "valid_until": until.isoformat(), "updated_at": now(), "last_invoice": inv["number"]}}, upsert=True)
    await db.invoices.update_one({"id": inv_id}, {"$set": {"period_from": start.isoformat(), "period_to": until.isoformat()}})
    await log(inv["tenant"], "abonament activat", by, f"{inv['plan_name']} {start.isoformat()} → {until.isoformat()} ({how}; {inv['number']})")
    asyncio.create_task(mail(inv["user_email"], f"Plată confirmată — abonament {inv['plan_name']}",
        f"<p>Bună ziua,</p><p>Plata pentru proforma <b>{hesc(inv['number'])}</b> ({inv['total']:.2f} RON, din care TVA {inv['vat']:.2f} RON) a fost confirmată.</p>"
        f"<p>Abonamentul <b>{hesc(inv['plan_name'])}</b> este activ până la <b>{until.strftime('%d.%m.%Y')}</b>.</p><p>Echipa D-ENERGY</p>"))
    if inv["total"] >= 2:
        asyncio.create_task(issue_fiscal(inv_id))
    return True

# ---------------- SmartBill (factură fiscală + RO e-Factura prin SmartBill Cloud) ----------------
SB_BASE = "https://ws.smartbill.ro/SBORO/api"

def sb_cfg():
    c = {k: (os.environ.get(f"SMARTBILL_{k}") or "").strip() for k in ("USERNAME", "TOKEN", "CIF", "SERIES")}
    return c if all(c.values()) else None

def sb_payload(inv: dict, c: dict) -> dict:
    cl = inv.get("client") or {}
    pj = cl.get("client_type") == "pj"
    unit = money(Decimal(str(inv["net"])) / int(inv["months"]))
    name = f"Abonament D-ENERGY {inv['plan_name']} ({inv.get('period_from')} - {inv.get('period_to')})"
    if inv.get("credit"):
        name += f"; credit {inv['credit']:.2f} lei din abonamentul anterior"
    pay = inv.get("payments") or [{}]
    return {"companyVatCode": c["CIF"], "seriesName": c["SERIES"], "isDraft": False, "issueDate": today().isoformat(), "dueDate": today().isoformat(),
            "currency": "RON", "language": "RO", "mentions": f"Proformă {inv['number']}",
            "client": {"name": cl.get("company_name") if pj else cl.get("full_name"), "vatCode": (cl.get("cui") if pj else cl.get("cnp")) or "",
                       "regCom": cl.get("regcom", "") if pj else "", "address": cl.get("hq_address") if pj else cl.get("address"), "city": cl.get("locality"),
                       "county": cl.get("county"), "country": cl.get("country") or "Romania", "email": cl.get("billing_email"),
                       "isTaxPayer": bool(cl.get("vat_payer")), "saveToDb": False},
            "products": [{"name": name[:250], "code": f"DEN-{inv['plan'].upper()}", "isDiscount": False, "measuringUnitName": "luna", "currency": "RON",
                          "quantity": int(inv["months"]), "price": unit, "isTaxIncluded": False, "taxName": "Normala", "taxPercentage": float(inv["vat_rate"]),
                          "isService": True, "saveToDb": False}],
            "payment": {"value": inv["total"], "type": "Card" if "Stripe" in str(pay[-1].get("method")) else "Ordin plata", "isCash": False}}

async def issue_fiscal(inv_id: str) -> dict:
    c = sb_cfg()
    if not c:
        await db.invoices.update_one({"id": inv_id, "fiscal.status": {"$ne": "emisă"}}, {"$set": {"fiscal": {"status": "neconfigurat", "at": now(),
                                     "error": "Contul SmartBill nu este conectat — factura fiscală se emite manual."}}})
        return {"status": "neconfigurat"}
    inv = await db.invoices.find_one_and_update({"id": inv_id, "status": PAID, "fiscal.status": {"$nin": ["emisă", "în curs"]}},
                                                {"$set": {"fiscal.status": "în curs", "fiscal.at": now()}}, return_document=True)
    if not inv:
        return (await db.invoices.find_one({"id": inv_id}, {"_id": 0, "fiscal": 1}) or {}).get("fiscal") or {}
    import httpx
    try:
        async with httpx.AsyncClient(auth=(c["USERNAME"], c["TOKEN"]), timeout=40) as h:
            r = await h.post(f"{SB_BASE}/invoice", json=sb_payload(inv, c), headers={"Accept": "application/json"})
        d = r.json() if r.content else {}
        if r.status_code >= 400 or d.get("errorText"):
            raise ValueError(d.get("errorText") or f"HTTP {r.status_code}")
        fis = {"status": "emisă", "series": d.get("series"), "number": d.get("number"), "at": now(), "provider": "SmartBill",
               "efactura": "Transmisă automat în SPV de SmartBill (dacă trimiterea automată e-Factura este activă în SmartBill) — statusul ANAF se verifică în SmartBill Cloud."}
        await db.invoices.update_one({"id": inv_id}, {"$set": {"fiscal": fis, "fiscal_ref": f"{d.get('series')} {d.get('number')}"}})
        await log(inv["tenant"], "factură fiscală emisă", "SmartBill", f"{inv['number']} → {d.get('series')} {d.get('number')}")
        return fis
    except Exception as e:
        logger.error(f"smartbill invoice {inv['number']}: {e}")
        fis = {"status": "eroare", "at": now(), "error": str(e)[:300]}
        await db.invoices.update_one({"id": inv_id}, {"$set": {"fiscal": fis}})
        return fis

@api.post("/admin/invoices/{inv_id}/smartbill")
async def admin_smartbill(inv_id: str, user: dict = Depends(get_current_user)):
    platform_only(user)
    if not await db.invoices.find_one({"id": inv_id, "status": PAID}):
        raise HTTPException(status_code=400, detail="Factura fiscală se emite doar pentru proforme plătite")
    return await issue_fiscal(inv_id)

@api.get("/billing/invoices/{inv_id}/fiscal-pdf")
async def fiscal_pdf(inv_id: str, authorization: str = Header(None), auth: str = Query(None)):
    user = await S.user_from_token(authorization, auth)
    if not is_platform(user):
        owner_only(user)
    inv = await db.invoices.find_one({"id": inv_id} if is_platform(user) else {"id": inv_id, "tenant": user["id"]}, {"_id": 0})
    c = sb_cfg()
    f = (inv or {}).get("fiscal") or {}
    if not inv or f.get("status") != "emisă" or not c:
        raise HTTPException(status_code=404, detail="Factura fiscală nu este disponibilă")
    import httpx
    async with httpx.AsyncClient(auth=(c["USERNAME"], c["TOKEN"]), timeout=40) as h:
        r = await h.get(f"{SB_BASE}/invoice/pdf", params={"cif": c["CIF"], "seriesname": f["series"], "number": f["number"]}, headers={"Accept": "application/octet-stream"})
    if r.status_code >= 400 or not r.content.startswith(b"%PDF"):
        raise HTTPException(status_code=502, detail="SmartBill nu a returnat PDF-ul facturii")
    return Response(content=r.content, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="factura_{f["series"]}{f["number"]}.pdf"'})

@api.get("/billing/quote")
async def billing_quote(plan: str, months: int = 1, user: dict = Depends(get_current_user)):
    owner_only(user)
    p = await get_plan(plan)
    cr = await upgrade_credit(user["id"], p)
    q = quote(p, max(1, min(months, 12)), float((await S.billing_cfg()).get("vat_rate", 21)), cr.get("credit", 0))
    return {**q, "credit_note": cr.get("note", ""), "smartbill": bool(sb_cfg())}

async def mail(to: str, subject: str, html: str):
    try:
        if to and "@" in to:
            await send_email(to=to, subject=subject, html=f'<div style="font-family:Arial,sans-serif;color:#0b1f3a">{html}</div>')
    except Exception as e:
        logger.warning(f"billing mail failed: {e}")

def pub_inv(i: dict) -> dict:
    return {k: v for k, v in i.items() if k not in ("_id", "issuer")}

# ---------------- user routes ----------------
@api.get("/billing/plans")
async def billing_plans(user: dict = Depends(get_current_user)):
    cfg = await S.billing_cfg()
    return {"plans": [{**p, **quote(p, 1, float(cfg.get("vat_rate", 21)))} for p in await plans() if p.get("active") is not False],
            "features": S.ALL_FEATURES, "vat_rate": cfg.get("vat_rate", 21), "currency": "RON", "online_payment": bool(stripe.api_key)}

@api.get("/billing/me")
async def billing_me(user: dict = Depends(get_current_user)):
    owner_only(user)
    sub = await db.subscriptions.find_one({"tenant": user["id"]}, {"_id": 0}) or {}
    invs = await db.invoices.find({"tenant": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    hist = await db.billing_history.find({"tenant": user["id"]}, {"_id": 0, "changes": 0}).sort("at", -1).to_list(100)
    return {"profile": await get_profile(user["id"]), "subscription": sub, "plan": user["plan"], "invoices": [pub_inv(i) for i in invs], "history": hist}

@api.put("/billing/profile")
async def billing_profile(request: Request, user: dict = Depends(get_current_user)):
    owner_only(user)
    prof = validate_profile(await request.json(), user.get("email"))
    await save_profile(user["id"], prof, user.get("email"), await get_profile(user["id"]))
    return await get_profile(user["id"])

@api.post("/billing/checkout")
async def billing_checkout(request: Request, user: dict = Depends(get_current_user)):
    owner_only(user)
    if user["plan"].get("exempt"):
        raise HTTPException(status_code=400, detail="Contul platformei nu necesită abonament")
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Plata online nu este configurată — contactați administratorul")
    b = await request.json()
    months = int(b.get("months") or 1)
    if months not in (1, 3, 6, 12):
        raise HTTPException(status_code=400, detail="Perioadă invalidă (1, 3, 6 sau 12 luni)")
    origin = (b.get("origin_url") or "").rstrip("/")
    if not origin.startswith("https://"):
        raise HTTPException(status_code=400, detail="Adresa aplicației lipsește")
    plan = await get_plan(b.get("plan"))
    inv = await new_invoice(user["id"], user.get("email"), plan, months, user.get("email"))
    if inv["total"] < 2:
        await db.invoices.update_one({"id": inv["id"]}, {"$push": {"payments": {"at": now(), "amount": inv["total"], "method": "credit abonament anterior", "reference": inv["number"], "by": "sistem"}}})
        await activate(inv["id"], "sistem", "acoperit integral din creditul abonamentului anterior")
        return {"checkout_url": f"{origin}/abonament?credit=1", "session_id": None, "invoice": pub_inv(inv)}
    try:
        sess = stripe.checkout.Session.create(
            mode="payment", currency="ron", customer_email=inv["client"].get("billing_email") or user.get("email"),
            line_items=[{"quantity": 1, "price_data": {"currency": "ron", "unit_amount": int(round(inv["total"] * 100)),
                         "product_data": {"name": f"Abonament D-ENERGY {plan['name']} — {months} lună(i)",
                                          "description": f"Proformă {inv['number']}: {inv['net']:.2f} RON + TVA {inv['vat_rate']:g}% {inv['vat']:.2f} RON"}}}],
            success_url=f"{origin}/abonament?session_id={{CHECKOUT_SESSION_ID}}", cancel_url=f"{origin}/abonament?anulat=1",
            metadata={"invoice_id": inv["id"], "invoice_number": inv["number"], "tenant": user["id"], "plan": plan["code"], "months": str(months)},
            client_reference_id=inv["id"], adaptive_pricing={"enabled": False}, expires_at=int((datetime.now(timezone.utc) + timedelta(hours=23)).timestamp()))
    except stripe.error.StripeError as e:
        await db.invoices.update_one({"id": inv["id"]}, {"$set": {"status": CANCELLED, "cancel_reason": "eroare furnizor plăți"}})
        logger.error(f"stripe checkout: {e}")
        raise HTTPException(status_code=502, detail="Furnizorul de plăți nu a putut genera linkul. Încercați din nou.")
    await db.payment_transactions.insert_one({"id": str(uuid.uuid4()), "session_id": sess.id, "invoice_id": inv["id"], "invoice_number": inv["number"],
        "tenant": user["id"], "user_email": user.get("email"), "plan": plan["code"], "months": months, "net": inv["net"], "vat": inv["vat"],
        "amount": inv["total"], "currency": "RON", "provider": "stripe", "mode": os.environ.get("STRIPE_MODE", "test"),
        "status": PENDING, "payment_status": "pending", "created_at": now(), "updated_at": now()})
    await db.invoices.update_one({"id": inv["id"]}, {"$set": {"session_id": sess.id, "pay_url": sess.url}})
    return {"checkout_url": sess.url, "session_id": sess.id, "invoice": pub_inv(inv)}

async def sync_session(session_id: str, by: str) -> dict:
    tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not tx:
        raise HTTPException(status_code=404, detail="Tranzacție inexistentă")
    if tx["payment_status"] not in ("paid", "refunded"):
        try:
            s = stripe.checkout.Session.retrieve(session_id)
        except stripe.error.StripeError:
            return tx
        if s.payment_status == "paid" and int(s.amount_total or 0) == int(round(tx["amount"] * 100)) and (s.currency or "").lower() == "ron":
            await mark_paid(session_id, s.payment_intent, by)
        elif s.status == "expired":
            await mark(session_id, EXPIRED, "expired")
        tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    return tx

async def mark_paid(session_id: str, pi: Optional[str], by: str):
    r = await db.payment_transactions.update_one({"session_id": session_id, "payment_status": {"$ne": "paid"}},
        {"$set": {"status": PAID, "payment_status": "paid", "payment_intent": pi, "updated_at": now(), "paid_at": now()}})
    tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if r.modified_count and tx:
        await db.invoices.update_one({"id": tx["invoice_id"]}, {"$push": {"payments": {"at": now(), "amount": tx["amount"], "method": "card online (Stripe)",
                                                                                         "reference": pi or session_id, "by": by}}})
        await activate(tx["invoice_id"], by, "plată online confirmată de Stripe")

async def mark(session_id: str, st: str, ps: str):
    tx = await db.payment_transactions.find_one_and_update({"session_id": session_id, "payment_status": {"$nin": ["paid", "refunded"]}},
                                                           {"$set": {"status": st, "payment_status": ps, "updated_at": now()}})
    if tx:
        await db.invoices.update_one({"id": tx["invoice_id"], "status": PENDING}, {"$set": {"status": st}})
        if st == FAILED:
            asyncio.create_task(mail(tx.get("user_email"), "Plata abonamentului nu a reușit",
                f"<p>Plata pentru proforma <b>{hesc(tx['invoice_number'])}</b> nu a reușit. Puteți genera un link nou din aplicație → Abonament.</p>"))

@api.get("/billing/payment-status/{session_id}")
async def billing_payment_status(session_id: str, user: dict = Depends(get_current_user)):
    tx = await db.payment_transactions.find_one({"session_id": session_id, "tenant": user["id"]}, {"_id": 0})
    if not tx:
        raise HTTPException(status_code=404, detail="Tranzacție inexistentă")
    tx = await sync_session(session_id, "verificare stare plată")
    return {"session_id": session_id, "status": tx["status"], "payment_status": tx["payment_status"], "invoice_number": tx["invoice_number"]}

@api.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload, sig = await request.body(), request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Semnătură invalidă")
    if await db.webhook_events.find_one({"id": event["id"]}):
        return {"status": "duplicate"}
    await db.webhook_events.insert_one({"id": event["id"], "type": event["type"], "at": now()})
    obj, t = event["data"]["object"], event["type"]
    if t in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        await sync_session(obj["id"], "webhook Stripe")
    elif t == "checkout.session.async_payment_failed":
        await mark(obj["id"], FAILED, "failed")
    elif t == "checkout.session.expired":
        await mark(obj["id"], EXPIRED, "expired")
    elif t == "charge.refunded":
        tx = await db.payment_transactions.find_one_and_update({"payment_intent": obj.get("payment_intent")},
                                                               {"$set": {"status": REFUNDED, "payment_status": "refunded", "updated_at": now()}})
        if tx:
            await db.invoices.update_one({"id": tx["invoice_id"]}, {"$set": {"status": REFUNDED}})
            await log(tx["tenant"], "plată rambursată", "webhook Stripe", f"{tx['invoice_number']} — verificați manual abonamentul")
    return {"status": "ok"}

@api.get("/billing/invoices/{inv_id}/pdf")
async def invoice_pdf(inv_id: str, authorization: str = Header(None), auth: str = Query(None)):
    user = await S.user_from_token(authorization, auth)
    q = {"id": inv_id} if is_platform(user) else {"id": inv_id, "tenant": user["id"]}
    if not is_platform(user):
        owner_only(user)
    inv = await db.invoices.find_one(q, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Document inexistent")
    return Response(content=render_invoice(inv), media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{inv["number"]}.pdf"'})

def render_invoice(inv: dict) -> bytes:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    import docgen as D
    st, c, iss = D.S, inv.get("client") or {}, inv.get("issuer") or {}
    e = lambda x: hesc(str(x or "—"))
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm, title=inv["number"])
    who = (f"<b>{e(c.get('company_name'))}</b><br/>CUI/CIF: {e(c.get('cui'))} · Reg. Com.: {e(c.get('regcom'))}<br/>Sediu: {e(c.get('hq_address'))}, {e(c.get('locality'))}, jud. {e(c.get('county'))}, {e(c.get('country'))}<br/>Reprezentant: {e(c.get('rep_name'))}"
           if c.get("client_type") == "pj" else f"<b>{e(c.get('full_name'))}</b><br/>Adresă: {e(c.get('address'))}, {e(c.get('locality'))}, jud. {e(c.get('county'))}, {e(c.get('country'))}")
    who += f"<br/>E-mail: {e(c.get('billing_email'))} · Tel.: {e(c.get('phone'))}"
    sel = f"<b>{e(iss.get('company') or 'DNS HOSTESS S.R.L.')}</b><br/>CUI: {e(iss.get('cui'))} · Reg. Com.: {e(iss.get('regcom'))}<br/>{e(iss.get('address'))}<br/>{e(iss.get('email'))} · {e(iss.get('phone'))}"
    if iss.get("iban"):
        sel += f"<br/>IBAN: {e(iss.get('iban'))} {e(iss.get('bank'))}"
    head = Table([[Paragraph("<b>Furnizor</b><br/>" + sel, st["hdrl"]), Paragraph("<b>Client</b><br/>" + who, st["hdrl"])]], colWidths=[87 * mm, 87 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.5, D.GRID), ("INNERGRID", (0, 0), (-1, -1), 0.5, D.GRID)]))
    f = lambda v: f"{v:,.2f}".replace(",", " ").replace(".", ",")
    per = f"{inv.get('period_from')} → {inv.get('period_to')}" if inv.get("period_from") else f"{inv['months']} lună(i) de la data plății"
    rows = [["Descriere", "Cant.", "Preț unitar fără TVA", "Valoare fără TVA", "Cota TVA", "Valoare TVA"],
            [f"Abonament D-ENERGY {inv['plan_name']} — perioada: {per}", f"{inv['months']} luni", f(inv["unit"]), f(inv["net"]), f"{inv['vat_rate']:g}%", f(inv["vat"])]]
    tot = [["Total fără TVA (bază de impozitare)", f(inv["net"]) + " RON"], [f"TVA {inv['vat_rate']:g}%", f(inv["vat"]) + " RON"], ["TOTAL DE PLATĂ", f(inv["total"]) + " RON"]]
    t2 = Table([[Paragraph(a, st["cellb"]), Paragraph(b, st["cellb"])] for a, b in tot], colWidths=[60 * mm, 40 * mm], hAlign="RIGHT")
    t2.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, D.GRID), ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#eef4ff"))]))
    story = [Paragraph(f"FACTURĂ PROFORMĂ nr. {e(inv['number'])}", st["h"]),
             Paragraph(f"Data: {inv['created_at'][:10]} · Moneda: RON · Stare: <b>{e(inv['status'])}</b>", st["sub"]), Spacer(1, 8), head, Spacer(1, 10),
             D.pdf_table(rows, [70, 14, 24, 24, 14, 22], True), Spacer(1, 8), t2, Spacer(1, 10)]
    for p in inv.get("payments") or []:
        story.append(Paragraph(f"Plată înregistrată {p['at'][:10]}: {f(p['amount'])} RON — {e(p.get('method'))}, ref. {e(p.get('reference'))}", st["small"]))
    if inv.get("fiscal_ref"):
        story.append(Paragraph(f"Factură fiscală asociată: <b>{e(inv['fiscal_ref'])}</b>", st["p"]))
    if inv.get("note"):
        story.append(Paragraph(e(inv["note"]), st["small"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Document proformă — nu ține loc de factură fiscală. Factura fiscală se emite după confirmarea plății și se transmite în sistemul RO e-Factura. "
                           "Plata online se procesează securizat de furnizorul de plăți; D-ENERGY nu stochează datele cardului.", st["small"]))
    doc.build(story)
    return buf.getvalue()

# ---------------- platform admin ----------------
@api.get("/admin/subscribers")
async def admin_subscribers(user: dict = Depends(get_current_user)):
    platform_only(user)
    us = await db.users.find({"tenant": {"$in": [None, ""]}, "id": {"$ne": S.PLATFORM["id"]}}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(2000)
    out = []
    for u in us:
        u["plan"] = await S.plan_info({**u, "uid": u["id"]})
        sub = await db.subscriptions.find_one({"tenant": u["id"]}, {"_id": 0}) or {}
        prof = await get_profile(u["id"])
        last = await db.invoices.find_one({"tenant": u["id"]}, {"_id": 0, "number": 1, "status": 1, "total": 1, "created_at": 1}, sort=[("created_at", -1)])
        out.append({**S.pub_user(u), "created_at": u.get("created_at"), "subscription": sub, "profile": prof, "last_invoice": last,
                    "dossiers": await db.prosumator.count_documents({"owner": u["id"]}), "diu": await db.diu.count_documents({"owner": u["id"]})})
    return out

@api.put("/admin/subscribers/{uid}")
async def admin_subscriber_update(uid: str, request: Request, user: dict = Depends(get_current_user)):
    platform_only(user)
    b = await request.json()
    u = await db.users.find_one({"id": uid})
    if not u or uid == S.PLATFORM["id"]:
        raise HTTPException(status_code=404, detail="Utilizator inexistent")
    upd = {}
    if b.get("status"):
        if b["status"] not in ("pending", "active", "suspended", "disabled"):
            raise HTTPException(status_code=400, detail="Stare invalidă")
        upd["status"] = b["status"]
    if b.get("to_team"):
        if b["to_team"] not in S.ROLES:
            raise HTTPException(status_code=400, detail="Rol invalid")
        upd.update({"tenant": S.PLATFORM["id"], "role": b["to_team"], "account_type": "team"})
    await db.users.update_one({"id": uid}, {"$set": upd})
    await log(uid, "cont", user.get("email"), ", ".join(f"{k}={v}" for k, v in upd.items() if k != "tenant") + (f" — {b.get('justification')}" if b.get("justification") else ""))
    return {"ok": True}

@api.post("/admin/subscribers/{uid}/plan")
async def admin_set_plan(uid: str, request: Request, user: dict = Depends(get_current_user)):
    platform_only(user)
    b = await request.json()
    if not (b.get("justification") or "").strip():
        raise HTTPException(status_code=400, detail="Justificarea este obligatorie pentru modificarea manuală a abonamentului")
    if not await db.users.find_one({"id": uid}):
        raise HTTPException(status_code=404, detail="Utilizator inexistent")
    st = b.get("status") or "activ"
    if st not in ("activ", "suspendat", "anulat"):
        raise HTTPException(status_code=400, detail="Stare abonament invalidă")
    plan = await get_plan(b.get("plan"))
    vu = b.get("valid_until") or ""
    try:
        date.fromisoformat(vu)
    except ValueError:
        raise HTTPException(status_code=400, detail="Data de valabilitate invalidă")
    old = await db.subscriptions.find_one({"tenant": uid}, {"_id": 0}) or {}
    await db.subscriptions.update_one({"tenant": uid}, {"$set": {"tenant": uid, "plan": plan["code"], "status": st, "valid_until": vu,
                                       "valid_from": old.get("valid_from") or today().isoformat(), "updated_at": now(), "manual": True}}, upsert=True)
    await log(uid, "abonament modificat manual", user.get("email"), f"{old.get('plan') or '—'}/{old.get('status') or '—'}/{old.get('valid_until') or '—'} → {plan['code']}/{st}/{vu}: {b['justification'].strip()}")
    return {"ok": True}

@api.post("/admin/invoices")
async def admin_invoice_create(request: Request, user: dict = Depends(get_current_user)):
    platform_only(user)
    b = await request.json()
    u = await db.users.find_one({"id": b.get("uid")}, {"_id": 0})
    if not u:
        raise HTTPException(status_code=404, detail="Utilizator inexistent")
    return pub_inv(await new_invoice(u["id"], u["email"], await get_plan(b.get("plan")), int(b.get("months") or 1), user.get("email"),
                                     b.get("vat_rate") if b.get("vat_rate") not in (None, "") else None, "manual"))

@api.post("/admin/invoices/{inv_id}/payment")
async def admin_invoice_payment(inv_id: str, request: Request, user: dict = Depends(get_current_user)):
    platform_only(user)
    b = await request.json()
    inv = await db.invoices.find_one({"id": inv_id}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Proformă inexistentă")
    if inv["status"] in (PAID, CANCELLED, REFUNDED):
        raise HTTPException(status_code=400, detail=f"Proforma este deja {inv['status']}")
    amount = money(b.get("amount") or 0)
    if amount <= 0 or not (b.get("reference") or "").strip() or not (b.get("justification") or "").strip():
        raise HTTPException(status_code=400, detail="Completați suma, referința documentului de plată (OP / chitanță) și justificarea")
    pay = {"at": now(), "amount": amount, "method": (b.get("method") or "transfer bancar")[:40], "reference": b["reference"].strip()[:80],
           "justification": b["justification"].strip()[:300], "by": user.get("email")}
    await db.invoices.update_one({"id": inv_id}, {"$push": {"payments": pay}})
    await log(inv["tenant"], "plată manuală înregistrată", user.get("email"), f"{inv['number']}: {amount:.2f} RON, {pay['method']}, ref. {pay['reference']} — {pay['justification']}")
    paid = money(sum(p["amount"] for p in inv.get("payments") or []) + amount)
    activated = paid >= inv["total"] and await activate(inv_id, user.get("email"), "plată înregistrată de administrator")
    return {"ok": True, "paid": paid, "total": inv["total"], "activated": bool(activated)}

@api.post("/admin/invoices/{inv_id}/cancel")
async def admin_invoice_cancel(inv_id: str, request: Request, user: dict = Depends(get_current_user)):
    platform_only(user)
    j = ((await request.json()).get("justification") or "").strip()
    if not j:
        raise HTTPException(status_code=400, detail="Justificarea este obligatorie")
    inv = await db.invoices.find_one_and_update({"id": inv_id, "status": {"$in": [PENDING, FAILED, EXPIRED]}}, {"$set": {"status": CANCELLED, "cancel_reason": j}})
    if not inv:
        raise HTTPException(status_code=400, detail="Doar proformele neplătite pot fi anulate")
    if inv.get("session_id"):
        try:
            stripe.checkout.Session.expire(inv["session_id"])
        except stripe.error.StripeError:
            pass
        await db.payment_transactions.update_one({"session_id": inv["session_id"], "payment_status": {"$ne": "paid"}}, {"$set": {"status": CANCELLED, "payment_status": "cancelled"}})
    await log(inv["tenant"], "proformă anulată", user.get("email"), f"{inv['number']}: {j}")
    return {"ok": True}

@api.put("/admin/invoices/{inv_id}/fiscal")
async def admin_invoice_fiscal(inv_id: str, request: Request, user: dict = Depends(get_current_user)):
    platform_only(user)
    ref = ((await request.json()).get("fiscal_ref") or "").strip()[:80]
    inv = await db.invoices.find_one_and_update({"id": inv_id}, {"$set": {"fiscal_ref": ref}})
    if not inv:
        raise HTTPException(status_code=404, detail="Proformă inexistentă")
    await log(inv["tenant"], "factură fiscală asociată", user.get("email"), f"{inv['number']} → {ref}")
    return {"ok": True}

@api.get("/admin/invoices")
async def admin_invoices(uid: Optional[str] = None, user: dict = Depends(get_current_user)):
    platform_only(user)
    return [pub_inv(i) for i in await db.invoices.find({"tenant": uid} if uid else {}, {"_id": 0}).sort("created_at", -1).to_list(1000)]

@api.get("/admin/transactions")
async def admin_transactions(user: dict = Depends(get_current_user)):
    platform_only(user)
    return await db.payment_transactions.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)

@api.post("/admin/transactions/{session_id}/sync")
async def admin_tx_sync(session_id: str, user: dict = Depends(get_current_user)):
    platform_only(user)
    return await sync_session(session_id, f"verificare manuală {user.get('email')}")

@api.get("/admin/billing/history/{uid}")
async def admin_history(uid: str, user: dict = Depends(get_current_user)):
    platform_only(user)
    return await db.billing_history.find({"tenant": uid}, {"_id": 0}).sort("at", -1).to_list(500)

@api.get("/admin/plans")
async def admin_plans(user: dict = Depends(get_current_user)):
    platform_only(user)
    return {"plans": await plans(), "config": await S.billing_cfg(), "features": S.ALL_FEATURES}

@api.put("/admin/plans/{code}")
async def admin_plan_update(code: str, request: Request, user: dict = Depends(get_current_user)):
    platform_only(user)
    b = await request.json()
    upd = {}
    if "price" in b:
        if money(b["price"]) < 0:
            raise HTTPException(status_code=400, detail="Preț invalid")
        upd["price"] = money(b["price"])
    if "features" in b:
        bad = [f for f in b["features"] if f != "*" and f not in S.ALL_FEATURES]
        if bad:
            raise HTTPException(status_code=400, detail=f"Funcții necunoscute: {bad}")
        upd["features"] = list(dict.fromkeys(b["features"]))
    for k in ("name", "description"):
        if b.get(k):
            upd[k] = str(b[k])[:200]
    if "max_inverters" in b:
        upd["max_inverters"] = max(0, int(b["max_inverters"] or 0))
    if "active" in b:
        upd["active"] = bool(b["active"])
    r = await db.plans.update_one({"code": code}, {"$set": upd})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Abonament inexistent")
    await log("platform", "configurare abonament", user.get("email"), f"{code}: {upd}")
    return await db.plans.find_one({"code": code}, {"_id": 0})

@api.put("/admin/billing-config")
async def admin_billing_cfg(request: Request, user: dict = Depends(get_current_user)):
    platform_only(user)
    b = await request.json()
    upd = {}
    if "vat_rate" in b:
        v = float(b["vat_rate"])
        if not 0 <= v <= 30:
            raise HTTPException(status_code=400, detail="Cota TVA invalidă")
        upd["vat_rate"] = v
    if "expired_policy" in b:
        if b["expired_policy"] not in ("read_only", "blocked"):
            raise HTTPException(status_code=400, detail="Politică invalidă")
        upd["expired_policy"] = b["expired_policy"]
    await db.billing_config.update_one({"id": "main"}, {"$set": upd}, upsert=True)
    await log("platform", "configurare facturare", user.get("email"), str(upd))
    return await S.billing_cfg()

@api.get("/admin/billing/export")
async def admin_export(authorization: str = Header(None), auth: str = Query(None)):
    user = await S.user_from_token(authorization, auth)
    platform_only(user)
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow(["Număr proformă", "Data", "Stare", "Abonament", "Luni", "Perioada de la", "Perioada până la", "Bază (RON)", "Cota TVA", "TVA (RON)", "Total (RON)",
                "Tip client", "Denumire / nume", "CUI/CIF", "Reg. Com.", "Adresă", "Localitate", "Județ", "Țară", "E-mail facturare", "Telefon", "Plăți (ref.)", "Factură fiscală"])
    for i in await db.invoices.find({}, {"_id": 0}).sort("created_at", 1).to_list(10000):
        c = i.get("client") or {}
        w.writerow([i["number"], i["created_at"][:10], i["status"], i["plan_name"], i["months"], i.get("period_from", ""), i.get("period_to", ""),
                    f"{i['net']:.2f}", f"{i['vat_rate']:g}", f"{i['vat']:.2f}", f"{i['total']:.2f}", "PJ" if c.get("client_type") == "pj" else "PF",
                    c.get("company_name") or c.get("full_name", ""), c.get("cui", ""), c.get("regcom", ""), c.get("hq_address") or c.get("address", ""),
                    c.get("locality", ""), c.get("county", ""), c.get("country", ""), c.get("billing_email", ""), c.get("phone", ""),
                    " | ".join(f"{p['amount']:.2f} {p.get('method')} {p.get('reference')}" for p in i.get("payments") or []), i.get("fiscal_ref", "")])
    await log("platform", "export contabilitate", user.get("email"), "CSV proforme")
    return Response(content="\ufeff" + out.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="d-energy-facturare.csv"'})

# ---------------- cron: expiry reminders ----------------
async def run_reminders(run_id: str):
    t = today()
    for days in (7, 1):
        day = (t + timedelta(days=days)).isoformat()
        async for sub in db.subscriptions.find({"status": "activ", "valid_until": day}, {"_id": 0}):
            key = f"{sub['tenant']}:{day}:{days}"
            if await db.reminders.find_one({"id": key}):
                continue
            await db.reminders.insert_one({"id": key, "at": now(), "run_id": run_id})
            u = await db.users.find_one({"id": sub["tenant"]}, {"_id": 0, "email": 1})
            prof = await get_profile(sub["tenant"])
            to = prof.get("billing_email") or (u or {}).get("email")
            await mail(to, f"Abonamentul D-ENERGY expiră în {days} {'zi' if days == 1 else 'zile'}",
                       f"<p>Bună ziua,</p><p>Abonamentul dvs. <b>{hesc(str(sub.get('plan', '')).upper())}</b> este valabil până la <b>{date.fromisoformat(day).strftime('%d.%m.%Y')}</b>.</p>"
                       "<p>Pentru reînnoire, deschideți aplicația D-ENERGY → Abonament → „Plătește abonamentul”. Cardul nu este debitat automat.</p>"
                       "<p>După expirare, dosarele și documentele rămân salvate.</p>")
            await log(sub["tenant"], "reamintire expirare", "cron", f"{days} zile — {to}")

@api.post("/cron/billing-reminders")
async def cron_reminders(request: Request, background: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    h = request.headers.get("authorization", "")
    if not h.startswith("Bearer ") or not hmac.compare_digest(h[7:], os.environ.get("WEBHOOK_CRON_SECRET", "")):
        raise HTTPException(status_code=401, detail="Unauthorized")
    run_id = request.headers.get("x-webhook-id") or str(uuid.uuid4())
    if await db.cron_runs.find_one({"id": run_id}):
        return {"status": "duplicate"}
    await db.cron_runs.insert_one({"id": run_id, "at": now(), "name": "billing-reminders"})
    background.add_task(run_reminders, run_id)
    return {"status": "accepted"}
