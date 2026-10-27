from datetime import datetime, timezone

from fastapi import HTTPException, Request, Depends, Header, Query, Response

import server as S
import cef as CEF
import diu_doc as DD
import opis as OPIS

db, api, get_current_user = S.db, S.api_router, S.get_current_user


async def diu_ctx(user: dict, item_id: str):
    S.guard("diu", user)
    rec = await S.check_access(user, "diu", item_id)
    prec = None
    if rec.get("pros_id"):
        prec = await db.prosumator.find_one({**S.scope_q(user, "prosumator"), "id": rec["pros_id"]}, {"_id": 0})
    prec = CEF.flatten(CEF.from_legacy(prec)) if prec else {}
    client = await S.get_client(user["id"], rec) or (await S.get_client(user["id"], prec) if prec else {})
    base = await db.settings.find_one({"owner": user["id"]}, {"_id": 0}) or {}
    s, _ = await S.effective_settings(user["id"], prec, base)
    merged = {**prec, **{k: v for k, v in rec.items() if v not in (None, "", [], {})}}
    for k in ("address", "county"):
        if not merged.get(k) and client.get(k):
            merged[k] = client[k]
    return rec, merged, client, s


@api.get("/diu/{item_id}/docs")
async def diu_docs(item_id: str, user: dict = Depends(get_current_user)):
    rec, r, client, s = await diu_ctx(user, item_id)
    pos = DD.positions(r, s)
    return {"positions": pos, "complete": not any(p["missing"] for p in pos), "pros_id": rec.get("pros_id"),
            "pros_name": r.get("client_name") if rec.get("pros_id") else None}


@api.get("/diu/{item_id}/pdf")
async def diu_pdf(item_id: str, doc: str = "all", authorization: str = Header(None), auth: str = Query(None)):
    user = await S.user_from_token(authorization, auth)
    rec, r, client, s = await diu_ctx(user, item_id)
    if doc != "all" and doc not in DD.TITLES:
        raise HTTPException(status_code=404, detail="Document inexistent")
    keys = [k for k, _ in DD.DOCS] if doc == "all" else [doc]
    pdf = DD.render(keys, r, s, client)
    pos = DD.positions(r, s)
    draft = any(p["missing"] for p in pos if p["key"] in keys)
    if draft or r.get("is_test"):
        from pypdf import PdfReader, PdfWriter
        import io
        w = PdfWriter()
        for pg in PdfReader(io.BytesIO(pdf)).pages:
            w.add_page(pg)
        if draft:
            OPIS.watermark(w)
        if r.get("is_test"):
            OPIS.watermark(w, "DOSAR DE TEST — NEOFICIAL", 38)
        o = io.BytesIO(); w.write(o); pdf = o.getvalue()
    name = f"DIU_{doc}_{(client.get('name') or r.get('client_name') or 'dosar').replace(' ', '_')}{'_CIORNA' if draft else ''}.pdf"
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": S.disp("inline", name)})


@api.post("/diu/{item_id}/import-pros")
async def diu_import(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    S.guard("diu", user, write=True)
    rec = await S.check_access(user, "diu", item_id)
    pid = (await request.json()).get("pros_id")
    p = await db.prosumator.find_one({**S.scope_q(user, "prosumator"), "id": pid}, {"_id": 0}) if pid else None
    if not p:
        raise HTTPException(status_code=404, detail="Dosar de prosumator inexistent")
    p = CEF.from_legacy(p)
    cef = p.get("cef") or {}
    g = cef.get("grid") or {}
    upd = {"pros_id": pid, "client_name": p.get("client_name"), "address": p.get("address"), "operator": p.get("operator"), "power": p.get("power"),
           "atr": p.get("atr"), "type": "Sistem fotovoltaic hibrid" if p.get("battery") or "hibrid" in str(p.get("system_type") or "").lower() else "Sistem fotovoltaic on-grid"}
    if p.get("client_id"):
        upd["client_id"] = p["client_id"]
    fill = {"supply": p.get("supply"), "earthing": g.get("earthing"), "tg_breaker_a": g.get("tg_breaker_a"), "bmp_a": g.get("bmp_a")}
    upd.update({k: v for k, v in fill.items() if v not in (None, "") and rec.get(k) in (None, "")})
    upd = {k: v for k, v in upd.items() if v not in (None, "")}
    if not rec.get("circuits"):
        upd["circuits"] = [{"name": f"INV{i + 1} — {inv.get('brand_model') or 'invertor'}", "breaker_a": (inv.get("ac") or {}).get("breaker_a"),
                            "curve": (inv.get("ac") or {}).get("curve") or "C", "section": (inv.get("ac") or {}).get("section"),
                            "cable": (inv.get("ac") or {}).get("cable_type"), "length": (inv.get("ac") or {}).get("length_m"),
                            "rcd_ma": inv.get("rcd_ma"), "rcd_type": inv.get("rcd_type")} for i, inv in enumerate(cef.get("inverters") or [])]
    gr = g.get("grounding_ohm") or p.get("grounding_ohm")
    pm = dict(rec.get("pram_m") or {})
    if gr and not pm.get("earth_ohm"):
        pm["earth_ohm"] = gr
    if p.get("grounding_limit") and not pm.get("earth_limit"):
        pm["earth_limit"] = p["grounding_limit"]
    upd["pram_m"] = pm
    upd["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.diu.update_one({"id": item_id, "owner": user["id"]}, {"$set": upd})
    await S.audit(user, "preluare din prosumator", "diu", item_id, list(upd.keys()))
    return await db.diu.find_one({"id": item_id}, {"_id": 0})
