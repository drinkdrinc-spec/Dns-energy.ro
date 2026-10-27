from datetime import datetime, timezone, date, timedelta
import hmac
import os
import uuid
from html import escape as hesc

from fastapi import HTTPException, Request, Depends, UploadFile, File, Header, Query, Response, BackgroundTasks

import server as S
from mailer import send_email

db, api, get_current_user = S.db, S.api_router, S.get_current_user
TYPES = ["A1", "A2", "A3", "B", "Bi", "Bp", "C1A", "C1B", "C2A", "C2B", "D1", "D2", "E1", "E2"]
STATUSES = ["în așteptare", "aprobat", "respins", "expirat"]
FIELDS = ("company", "cui", "regcom", "contact_name", "contact_email", "contact_phone", "attest_no", "attest_types", "attest_other", "attest_valid", "holder_name", "holder_role", "visa_date")
REQ = {"company": "Denumirea firmei", "cui": "CUI", "contact_name": "Persoană de contact", "contact_phone": "Telefon", "contact_email": "E-mail",
       "attest_no": "Numărul atestatului ANRE", "holder_name": "Titularul atestatului (firma)"}
now = lambda: datetime.now(timezone.utc).isoformat()


def owner_only(user):
    if user.get("role") != "admin" or user["uid"] != user["id"]:
        raise HTTPException(status_code=403, detail="Doar titularul contului firmei poate gestiona atestatul")


def platform_only(user):
    if user["uid"] != S.PLATFORM["id"]:
        raise HTTPException(status_code=403, detail="Doar administratorul platformei are acces la această secțiune")


def pub(o):
    return {k: v for k, v in (o or {}).items() if k not in ("_id", "doc_path")} | {"has_document": bool((o or {}).get("doc_path"))}


@api.get("/operator")
async def op_get(user: dict = Depends(get_current_user)):
    o = await db.operators.find_one({"tenant": user["id"]}, {"_id": 0})
    return {"operator": pub(o) if o else None, "types": TYPES, "attest": user["plan"].get("attest")}


@api.put("/operator")
async def op_save(request: Request, user: dict = Depends(get_current_user)):
    owner_only(user)
    b = await request.json()
    d = {k: b.get(k) for k in FIELDS}
    d["attest_types"] = [t for t in (d.get("attest_types") or []) if t in TYPES]
    miss = [l for k, l in REQ.items() if not str(d.get(k) or "").strip()]
    if not d["attest_types"] and not (d.get("attest_other") or "").strip():
        miss.append("Tipul atestatului")
    if miss:
        raise HTTPException(status_code=400, detail="Completați: " + ", ".join(miss))
    cur = await db.operators.find_one({"tenant": user["id"]}, {"_id": 0}) or {}
    changed = any(cur.get(k) != d.get(k) for k in ("cui", "attest_no", "attest_types", "attest_other", "attest_valid", "holder_name"))
    st = "în așteptare" if changed or not cur.get("status") else cur["status"]
    if d.get("visa_date"):
        try:
            d["visa_date"] = date.fromisoformat(str(d["visa_date"]).strip()).isoformat()
        except ValueError:
            raise HTTPException(status_code=400, detail="Data vizării periodice invalidă (AAAA-LL-ZZ)")
    if cur.get("visa_date") != d.get("visa_date"):
        d["visa_confirmed"] = False
    await db.operators.update_one({"tenant": user["id"]}, {"$set": {**d, "tenant": user["id"], "email": user.get("email"), "status": st, "updated_at": now()},
                                                          "$push": {"history": {"at": now(), "by": user.get("email"), "event": "date atestat trimise" + (" — reverificare necesară" if changed and cur else "")}}}, upsert=True)
    await S.audit(user, "atestat ANRE trimis", "operators", user["id"], [st])
    return await op_get(user)


@api.post("/operator/document")
async def op_doc(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    owner_only(user)
    data = await file.read()
    ct = file.content_type or ""
    magic = {"application/pdf": b"%PDF", "image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG\r\n\x1a\n"}
    if ct not in magic or not data.startswith(magic[ct]) or len(data) > 10 * 1024 * 1024 or (ct != "application/pdf" and len(data) < 2000):
        raise HTTPException(status_code=400, detail="Încărcați atestatul ca PDF, JPG sau PNG, maxim 10 MB")
    st = S.put_object(f"{S.APP_NAME}/operators/{user['id']}/{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{(file.filename or 'atestat')[-60:]}", data, ct)
    await db.operators.update_one({"tenant": user["id"]}, {"$set": {"tenant": user["id"], "doc_path": st["path"], "doc_name": file.filename, "doc_type": ct, "doc_size": len(data),
                                                                    "doc_uploaded_at": now(), "status": "în așteptare", "updated_at": now()},
                                                          "$push": {"history": {"at": now(), "by": user.get("email"), "event": f"document încărcat: {file.filename}"}}}, upsert=True)
    await S.audit(user, "document atestat încărcat", "operators", user["id"], [file.filename or ""])
    return await op_get(user)


async def send_doc(tenant: str):
    o = await db.operators.find_one({"tenant": tenant}, {"_id": 0})
    if not o or not o.get("doc_path"):
        raise HTTPException(status_code=404, detail="Document inexistent")
    data, _ = S.get_object(o["doc_path"])
    return Response(content=data, media_type=o.get("doc_type") or "application/pdf", headers={"Content-Disposition": S.disp("inline", o.get("doc_name") or "atestat.pdf"), "Cache-Control": "no-store"})


@api.get("/operator/document")
async def op_doc_get(authorization: str = Header(None), auth: str = Query(None)):
    user = await S.user_from_token(authorization, auth)
    return await send_doc(user["id"])


@api.get("/admin/operators")
async def adm_list(user: dict = Depends(get_current_user)):
    platform_only(user)
    return [pub(o) for o in await db.operators.find({}, {"_id": 0}).sort("updated_at", -1).to_list(2000)]


@api.get("/admin/operators/{tenant}/document")
async def adm_doc(tenant: str, authorization: str = Header(None), auth: str = Query(None)):
    user = await S.user_from_token(authorization, auth)
    platform_only(user)
    await S.audit(user, "vizualizare atestat", "operators", tenant, [])
    return await send_doc(tenant)


@api.post("/admin/operators/{tenant}/decision")
async def adm_decide(tenant: str, request: Request, user: dict = Depends(get_current_user)):
    platform_only(user)
    b = await request.json()
    st, notes = b.get("status"), str(b.get("notes") or "").strip()[:1000]
    if st not in STATUSES:
        raise HTTPException(status_code=400, detail="Status invalid")
    o = await db.operators.find_one({"tenant": tenant})
    if not o:
        raise HTTPException(status_code=404, detail="Operator inexistent")
    if st == "aprobat" and not o.get("doc_path"):
        raise HTTPException(status_code=400, detail="Nu se poate aproba fără documentul atestatului încărcat și verificat")
    if st in ("respins", "expirat") and not notes:
        raise HTTPException(status_code=400, detail="Scrieți motivul în observații")
    await db.operators.update_one({"tenant": tenant}, {"$set": {"status": st, "admin_notes": notes, "verified_at": now(), "verified_by": user.get("email"), "updated_at": now()},
                                                       "$push": {"history": {"at": now(), "by": user.get("email"), "event": f"decizie: {st}" + (f" — {notes}" if notes else "")}}})
    await S.audit(user, f"atestat {st}", "operators", tenant, [notes])
    return {"status": st}


@api.post("/admin/operators/{tenant}/visa")
async def adm_visa(tenant: str, request: Request, user: dict = Depends(get_current_user)):
    platform_only(user)
    b = await request.json()
    o = await db.operators.find_one({"tenant": tenant}, {"_id": 0})
    if not o:
        raise HTTPException(status_code=404, detail="Operator inexistent")
    vd = str(b.get("visa_date") or o.get("visa_date") or "").strip()
    try:
        vd = date.fromisoformat(vd).isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail="Completați data vizării periodice (AAAA-LL-ZZ)")
    ok = bool(b.get("confirmed", True))
    await db.operators.update_one({"tenant": tenant}, {"$set": {"visa_date": vd, "visa_confirmed": ok, "visa_confirmed_by": user.get("email"), "visa_confirmed_at": now()},
                                                       "$push": {"history": {"at": now(), "by": user.get("email"), "event": f"dată vizare {'confirmată' if ok else 'neconfirmată'}: {vd}"}}})
    await S.audit(user, "dată vizare ANRE", "operators", tenant, [vd, str(ok)])
    return pub(await db.operators.find_one({"tenant": tenant}, {"_id": 0}))


@api.get("/admin/operators/visas")
async def adm_visas(user: dict = Depends(get_current_user)):
    platform_only(user)
    t = date.today()
    out = []
    async for o in db.operators.find({"visa_date": {"$nin": [None, ""], "$lte": (t + timedelta(days=90)).isoformat()}}, {"_id": 0, "doc_path": 0, "history": 0}).sort("visa_date", 1):
        out.append({k: o.get(k) for k in ("tenant", "company", "cui", "attest_no", "contact_name", "contact_email", "contact_phone", "visa_date", "visa_confirmed", "visa_reminded_at", "status")}
                   | {"days_left": (date.fromisoformat(o["visa_date"]) - t).days})
    return out


async def run_visa(run_id: str, base: str):
    t = date.today()
    lim = (t + timedelta(days=60)).isoformat()
    async for o in db.operators.find({"visa_confirmed": True, "visa_date": {"$gte": t.isoformat(), "$lte": lim}}, {"_id": 0}):
        key = f"visa:{o['tenant']}:{o['visa_date']}"
        if await db.reminders.find_one({"id": key}):
            continue
        to = o.get("contact_email") or o.get("email")
        if not to:
            continue
        vd = date.fromisoformat(o["visa_date"])
        try:
            await send_email(to=to, subject=f"Memento: vizarea periodică a atestatului ANRE — {vd.strftime('%d.%m.%Y')}",
                             html=f'<div style="font-family:Arial,sans-serif;color:#0b1f3a"><p>Bună ziua,</p><p>Atestatul ANRE nr. <b>{hesc(str(o.get("attest_no") or "—"))}</b> al firmei '
                                  f'<b>{hesc(str(o.get("company") or ""))}</b> are termenul de vizare periodică la <b>{vd.strftime("%d.%m.%Y")}</b> (peste {(vd - t).days} zile).</p>'
                                  "<p>Vă recomandăm să pregătiți din timp dosarul de vizare (certificat constatator recent, personal autorizat, dotări). "
                                  "Puteți comanda serviciul D-ENERGY de pregătire a dosarului de vizare (3.200 lei + TVA):</p>"
                                  f'<p><a href="{base}/dosare-anre?tip=vizare" style="display:inline-block;background:#0b1f3a;color:#ffffff;padding:12px 22px;border-radius:6px;text-decoration:none;font-weight:bold">Comandă dosarul de vizare</a></p>'
                                  "<p style=\"font-size:12px;color:#5b6b80\">Butonul deschide aplicația cu „Vizare periodică” deja aleasă; comanda se plasează doar după confirmarea dvs.</p><p>Echipa D-ENERGY</p></div>")
        except HTTPException:
            continue
        await db.reminders.insert_one({"id": key, "at": now(), "run_id": run_id})
        await db.operators.update_one({"tenant": o["tenant"]}, {"$set": {"visa_reminded_at": now()}, "$push": {"history": {"at": now(), "by": "cron", "event": f"memento vizare trimis la {to}"}}})


@api.post("/cron/anre-visa")
async def cron_visa(request: Request, background: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    h = request.headers.get("authorization", "")
    if not h.startswith("Bearer ") or not hmac.compare_digest(h[7:], os.environ.get("WEBHOOK_CRON_SECRET", "")):
        raise HTTPException(status_code=401, detail="Unauthorized")
    run_id = request.headers.get("x-webhook-id") or str(uuid.uuid4())
    if await db.cron_runs.find_one({"id": run_id}):
        return {"status": "duplicate"}
    await db.cron_runs.insert_one({"id": run_id, "at": now(), "name": "anre-visa"})
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    background.add_task(run_visa, run_id, f"https://{host.split(',')[0].strip()}")
    return {"status": "accepted"}


@api.get("/admin/attest-config")
async def adm_cfg(user: dict = Depends(get_current_user)):
    platform_only(user)
    c = await S.billing_cfg()
    return {"attest_block_existing": bool(c.get("attest_block_existing")), "attest_cutoff": c.get("attest_cutoff")}


@api.put("/admin/attest-config")
async def adm_cfg_set(request: Request, user: dict = Depends(get_current_user)):
    platform_only(user)
    v = bool((await request.json()).get("attest_block_existing"))
    await db.billing_config.update_one({"id": "main"}, {"$set": {"attest_block_existing": v}}, upsert=True)
    await S.audit(user, "regulă atestate conturi existente", "operators", "config", ["blocare imediată" if v else "păstrare acces până la verificare"])
    return await adm_cfg(user)


@S.app.on_event("startup")
async def _cutoff():
    await db.billing_config.update_one({"id": "main", "attest_cutoff": {"$exists": False}}, {"$set": {"attest_cutoff": now()}})
    await db.operators.create_index("tenant", unique=True)
    if not await db.billing_config.find_one({"id": "main", "tariffs_2026_06": True}):
        for code, price in (("start", 500), ("pro", 900), ("full", 1250)):
            await db.plans.update_one({"code": code}, {"$set": {"price": price}})
        await db.billing_config.update_one({"id": "main"}, {"$set": {"tariffs_2026_06": True, "payment_mode": "transfer", "default_months": 1}}, upsert=True)
