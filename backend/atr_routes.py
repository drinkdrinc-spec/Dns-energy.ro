import os
import re
import hmac
import uuid
import secrets
import logging
from datetime import datetime, timezone, timedelta, date
from html import escape as hesc
from typing import Optional

from fastapi import HTTPException, Request, Depends, BackgroundTasks, Response

import server as S
import atr_doc as ATR
from mailer import send_email

db, api, get_current_user = S.db, S.api_router, S.get_current_user
logger = logging.getLogger("d-energy.atr")
OP_DOMAINS = {"deer": ("distributie-energie.ro",), "delgaz": ("delgaz-grid.ro", "delgaz.ro"), "rer": ("reteleelectrice.ro",),
              "oltenia": ("distributieoltenia.ro", "evryo.ro")}
DEFAULT_TERMS = {"check_days": 10, "issue_days": 30, "remind_days": 3}
LINK_DAYS = 30


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_workdays(d: date, n: int) -> date:
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def pdate(v: str, label: str) -> date:
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{label}: dată invalidă")


def valid_operator_email(op: str, email: str) -> bool:
    email = (email or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", email):
        return False
    dom = email.split("@")[1]
    return any(dom == d or dom.endswith("." + d) for d in OP_DOMAINS.get(op, ()))


async def get_rec(user: dict, item_id: str, write: bool = True) -> dict:
    if write:
        S.guard("atr", user, write=True)
    return await S.check_access(user, "atr", item_id)


def track(rec: dict) -> dict:
    t = rec.get("atr_track") or {}
    t.setdefault("status", "ciornă")
    t.setdefault("events", [])
    t.setdefault("terms", dict(DEFAULT_TERMS))
    return t


async def save_track(item_id: str, t: dict, ev: str, by: str):
    t["events"] = (t.get("events") or [])[-40:] + [{"at": now(), "by": by, "text": ev}]
    await db.atr.update_one({"id": item_id}, {"$set": {"atr_track": t}})
    return t


# ---------------- operator contacts (platform) ----------------
@api.get("/operator-contacts")
async def contacts(user: dict = Depends(get_current_user)):
    rows = {c["op"]: c for c in await db.operator_contacts.find({}, {"_id": 0}).to_list(20)}
    return [{"op": k, "name": ATR.OP_NAMES[k], "domains": list(v), "email": (rows.get(k) or {}).get("email", "")} for k, v in OP_DOMAINS.items()]


@api.put("/operator-contacts/{op}")
async def contacts_set(op: str, request: Request, user: dict = Depends(get_current_user)):
    if user["uid"] != S.PLATFORM["id"]:
        raise HTTPException(status_code=403, detail="Doar administratorul platformei setează adresele operatorilor")
    email = ((await request.json()).get("email") or "").strip().lower()
    if op not in OP_DOMAINS or (email and not valid_operator_email(op, email)):
        raise HTTPException(status_code=400, detail=f"Adresa trebuie să fie pe domeniul oficial al operatorului ({', '.join(OP_DOMAINS.get(op, ()))})")
    await db.operator_contacts.update_one({"op": op}, {"$set": {"op": op, "email": email, "updated_at": now()}}, upsert=True)
    return {"ok": True}


# ---------------- form alerts ----------------
@api.get("/forms/alerts")
async def form_alerts(operator: str = "", scope: str = "atr", user: dict = Depends(get_current_user)):
    op = ATR.op_key(operator)
    want = ("atr",) if scope == "atr" else ("spor", "prosumator")
    out = []
    for f in await db.official_forms.find({"status": {"$in": ["versiune nouă detectată", "link invalid"]}}, {"_id": 0, "history": 0}).to_list(200):
        if ATR.op_key(f.get("operator")) == op and any(w in (f.get("kind") or "").lower() for w in want):
            out.append({k: f.get(k) for k in ("id", "operator", "title", "url", "status", "version")} | {"checked": (f.get("last_check") or {}).get("at")})
    return out


# ---------------- submission ----------------
@api.post("/atr/{item_id}/submit")
async def atr_submit(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    rec = await get_rec(user, item_id)
    b = await request.json()
    op = ATR.op_key(rec.get("operator"))
    to = (b.get("to") or "").strip().lower()
    if not valid_operator_email(op, to):
        raise HTTPException(status_code=400, detail=f"Destinatarul trebuie să fie o adresă oficială {ATR.OP_NAMES[op]} ({', '.join(OP_DOMAINS[op])})")
    att = rec.get("attachments") or {}
    pdf, name = await S.atr_pack(user, rec, 1)
    if "_INCOMPLET" in name:
        miss = [t for k, t, _ in ATR.DOCS if k in ATR.required(rec) and not att.get(k)]
        raise HTTPException(status_code=400, detail="Dosarul este incomplet — atașați înainte de trimitere: " + "; ".join(miss[:6]))
    origin = (request.headers.get("origin") or "").rstrip("/")
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip()
    if not origin.startswith("https://") or (host and origin[8:] != host):
        raise HTTPException(status_code=400, detail="Deschideți trimiterea din aplicație")
    token = secrets.token_urlsafe(24)
    exp = (datetime.now(timezone.utc) + timedelta(days=LINK_DAYS)).isoformat()
    client = await S.get_client(user["id"], rec)
    st = await db.settings.find_one({"owner": user["id"]}, {"_id": 0, "company": 1, "phone": 1, "email": 1}) or {}
    link = f"{origin}/api/public/atr/{token}"
    cname, comp = hesc(str(client.get("name") or rec.get("client_name") or "")), hesc(str(st.get("company") or ""))
    html = (f"<p>Bună ziua,</p><p>Vă transmitem cererea de racordare (aviz tehnic de racordare) pentru <b>{cname}</b>, "
            f"obiectiv: {hesc(str(rec.get('object_name') or rec.get('address') or client.get('address') or ''))}, "
            f"tip: {hesc(str(rec.get('kind') or 'Loc de consum'))}.</p>"
            f"<p>Dosarul complet (cerere, chestionar și documentele anexate, PDF {round(len(pdf) / 1048576, 1)} MB) poate fi descărcat aici, timp de {LINK_DAYS} de zile:<br/>"
            f'<a href="{link}">Descarcă dosarul ATR (PDF)</a></p>'
            f"<p>Vă rugăm să ne comunicați numărul și data de înregistrare a cererii.</p>"
            f"<p>Cu stimă,<br/>{comp}<br/>{hesc(str(st.get('phone') or ''))} · {hesc(str(st.get('email') or user.get('email') or ''))}</p>"
            f"<p style='font-size:11px;color:#777'>Transmis prin D-ENERGY în numele {comp}.</p>")
    subj = f"Cerere de racordare (ATR) — {client.get('name') or rec.get('client_name') or ''}"
    sent_to = await S.deliver(user["id"], bool(rec.get("is_test")), to, subj, html)
    copy = await S.deliver(user["id"], bool(rec.get("is_test")), user.get("email"), "Copie: " + subj, "<p><b>Copie a e-mailului trimis la " + hesc(to) + "</b></p>" + html) if user.get("email") else ""
    t = track(rec)
    t.update({"status": "trimis", "sent_at": now(), "sent_to": to, "token": token, "token_exp": exp, "real_sent": bool(sent_to)})
    await save_track(item_id, t, f"Dosar trimis la {to}" + ("" if sent_to else " (dosar TEST — e-mail real neexpediat)") + (f"; copie la {copy}" if copy else ""), user.get("email"))
    return {"ok": True, "sent_to": sent_to, "copy": copy, "track": pub(t)}


@api.get("/public/atr/{token}")
async def atr_public(token: str):
    rec = await db.atr.find_one({"atr_track.token": token}, {"_id": 0})
    if not rec or (rec["atr_track"].get("token_exp") or "") < now():
        raise HTTPException(status_code=404, detail="Link expirat sau invalid")
    owner = rec["owner"]
    u = {"id": owner, "uid": owner, "role": "admin", "plan": {"exempt": True}}
    pdf, name = await S.atr_pack(u, rec, 1)
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": S.disp("inline", name)})


def pub(t: dict) -> dict:
    return {k: v for k, v in t.items() if k != "token"}


@api.get("/atr/{item_id}/track")
async def atr_track(item_id: str, user: dict = Depends(get_current_user)):
    rec = await get_rec(user, item_id, write=False)
    return pub(track(rec))


@api.post("/atr/{item_id}/track")
async def atr_track_update(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    rec = await get_rec(user, item_id)
    b = await request.json()
    t = track(rec)
    act = b.get("action")
    terms = {**DEFAULT_TERMS, **(t.get("terms") or {})}
    for k in ("check_days", "issue_days", "remind_days"):
        if b.get(k) not in (None, ""):
            v = int(b[k])
            if not 0 < v <= 365:
                raise HTTPException(status_code=400, detail="Termen invalid")
            terms[k] = v
    t["terms"] = terms
    if act == "register":
        reg_no = (b.get("reg_no") or "").strip()[:60]
        if not reg_no:
            raise HTTPException(status_code=400, detail="Introduceți numărul de înregistrare primit de la distribuitor")
        d = pdate(b.get("reg_date"), "Data înregistrării")
        t.update({"status": "înregistrat", "reg_no": reg_no, "reg_date": d.isoformat(), "check_due": add_workdays(d, terms["check_days"]).isoformat()})
        ev = f"Înregistrat la distribuitor: nr. {reg_no} / {d.isoformat()}; verificare documente până la {t['check_due']}"
    elif act == "incomplete":
        t.update({"status": "completări solicitate", "incomplete_note": (b.get("note") or "")[:300], "check_due": None})
        ev = f"Distribuitorul a solicitat completări: {t['incomplete_note']}"
    elif act == "complete":
        d = pdate(b.get("date"), "Data dosarului complet")
        t.update({"status": "dosar complet", "complete_date": d.isoformat(), "issue_due": (d + timedelta(days=terms["issue_days"])).isoformat(), "check_due": None})
        ev = f"Dosar declarat complet la {d.isoformat()}; termen emitere aviz {t['issue_due']}"
    elif act == "issued":
        d = pdate(b.get("date"), "Data avizului")
        t.update({"status": "aviz emis", "atr_no": (b.get("atr_no") or "").strip()[:60], "atr_date": d.isoformat(), "issue_due": None, "check_due": None})
        await db.atr.update_one({"id": item_id}, {"$set": {"atr_ref": f"{t['atr_no']} / {d.isoformat()}"}})
        ev = f"Aviz tehnic de racordare emis: {t['atr_no']} / {d.isoformat()}"
    elif act == "dates":
        for k, lbl in (("check_due", "Termen verificare"), ("issue_due", "Termen aviz")):
            if b.get(k):
                t[k] = pdate(b[k], lbl).isoformat()
        ev = f"Termene modificate manual: verificare {t.get('check_due') or '—'}, aviz {t.get('issue_due') or '—'}"
    elif act == "terms":
        ev = f"Termene standard: verificare {terms['check_days']} zile lucrătoare, aviz {terms['issue_days']} zile, reamintire cu {terms['remind_days']} zile înainte"
    else:
        raise HTTPException(status_code=400, detail="Acțiune necunoscută")
    return pub(await save_track(item_id, t, ev, user.get("email")))


# ---------------- deadline reminders (cron) ----------------
async def run_deadlines(run_id: str):
    today = datetime.now(timezone.utc).date()
    async for rec in db.atr.find({"atr_track.status": {"$in": ["înregistrat", "dosar complet"]}}, {"_id": 0}):
        t = rec["atr_track"]
        rd = int((t.get("terms") or {}).get("remind_days") or 3)
        for key, label in (("check_due", "verificarea documentației de către distribuitor"), ("issue_due", "emiterea avizului tehnic de racordare")):
            if not t.get(key):
                continue
            due = date.fromisoformat(t[key])
            phase = "depășit" if today > due else "aproape" if (due - today).days <= rd else None
            if not phase:
                continue
            rid = f"atr:{rec['id']}:{key}:{t[key]}:{phase}"
            if await db.reminders.find_one({"id": rid}):
                continue
            await db.reminders.insert_one({"id": rid, "at": now(), "run_id": run_id})
            u = await db.users.find_one({"id": rec.get("created_by") or rec["owner"]}, {"_id": 0, "email": 1}) or \
                await db.users.find_one({"id": rec["owner"]}, {"_id": 0, "email": 1}) or {}
            msg = (f"Termenul pentru {label} a fost depășit ({due.strftime('%d.%m.%Y')})." if phase == "depășit"
                   else f"Termenul pentru {label} expiră pe {due.strftime('%d.%m.%Y')}.")
            html = (f"<p>Bună ziua,</p><p>Cererea ATR pentru <b>{hesc(str(rec.get('client_name') or ''))}</b> "
                    f"(nr. înregistrare {hesc(str(t.get('reg_no') or '—'))}): {msg}</p>"
                    "<p>Verificați stadiul la distribuitor și actualizați cererea în D-ENERGY → Cerere ATR.</p>")
            try:
                await S.deliver(rec["owner"], bool(rec.get("is_test")), u.get("email") or "", f"Termen ATR {phase}: {rec.get('client_name') or ''}", html)
            except Exception as e:
                logger.warning(f"atr reminder: {e}")
            t["events"] = (t.get("events") or [])[-40:] + [{"at": now(), "by": "cron", "text": f"Reamintire trimisă: {msg}"}]
            await db.atr.update_one({"id": rec["id"]}, {"$set": {"atr_track.events": t["events"]}})


@api.post("/cron/atr-deadlines")
async def cron_atr(request: Request, background: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    h = request.headers.get("authorization", "")
    if not h.startswith("Bearer ") or not hmac.compare_digest(h[7:], os.environ.get("WEBHOOK_CRON_SECRET", "")):
        raise HTTPException(status_code=401, detail="Unauthorized")
    run_id = request.headers.get("x-webhook-id") or str(uuid.uuid4())
    if await db.cron_runs.find_one({"id": run_id}):
        return {"status": "duplicate"}
    await db.cron_runs.insert_one({"id": run_id, "at": now(), "name": "atr-deadlines"})
    background.add_task(run_deadlines, run_id)
    return {"status": "accepted"}
