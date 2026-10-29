import io
import uuid
from datetime import datetime, timezone

from pypdf import PdfReader, PdfWriter

from fastapi import HTTPException, Request, Depends, Header, Query, Response

import server as S
import cef as CEF
import diu_doc as DD
import opis as OPIS

db, api, get_current_user = S.db, S.api_router, S.get_current_user
OWN = ("receptie_", "pif_date", "pif_decision", "warranty_", "doc_date", "date")
rcd = lambda v: str(v).replace("Tip", "").replace("tip", "").strip() if v else v


async def diu_ctx(user: dict, item_id: str):
    S.guard("diu", user)
    rec = await S.check_access(user, "diu", item_id)
    prec = None
    if rec.get("pros_id"):
        prec = await db.prosumator.find_one({**S.scope_q(user, "prosumator"), "id": rec["pros_id"]}, {"_id": 0})
    prec = CEF.flatten(CEF.from_legacy(prec)) if prec else {}
    client = await S.get_client(user["id"], rec) or (await S.get_client(user["id"], prec) if prec else {})
    base = await db.settings.find_one({"owner": user["id"]}, {"_id": 0}) or {}
    # DI-U may override the signers and measuring instrument selected for the
    # linked prosumer dossier. If the DI-U has no selection, inherit the prosumer
    # dossier selection so both workflows use the same validated company data.
    effective_rec = {**prec, **rec, "snapshot": None}
    effective_rec["signers"] = rec.get("signers") or prec.get("signers") or {}
    effective_rec["instrument_id"] = rec.get("instrument_id") or prec.get("instrument_id")
    s, _ = await S.effective_settings(user["id"], effective_rec, base)
    prec = {k: v for k, v in prec.items() if not k.startswith(OWN)}
    merged = {**prec, **{k: v for k, v in rec.items() if v not in (None, "", [], {})}}
    # Feed the selected, currently valid metrology instrument and authorized
    # PRAM verifier into the DI-U PRAM templates (which read pram_m fields).
    pm = dict(merged.get("pram_m") or {})
    if s.get("meter_device"):
        pm["instrument"] = " ".join(str(v) for v in (s.get("meter_device"), ("seria " + str(s.get("meter_serial"))) if s.get("meter_serial") else None) if v)
    if s.get("meter_valid"):
        pm["metrology_valid_until"] = s.get("meter_valid")
    if s.get("measurer"):
        pm["verifier"] = s.get("measurer")
    merged["pram_m"] = pm
    for k in ("address", "county"):
        if not merged.get(k) and client.get(k):
            merged[k] = client[k]
    return rec, merged, client, s


@api.get("/diu/{item_id}/docs")
async def diu_docs(item_id: str, user: dict = Depends(get_current_user)):
    rec, r, client, s = await diu_ctx(user, item_id)
    pos = DD.positions(r, s)
    return {"positions": pos, "complete": not any(p["missing"] for p in pos), "pros_id": rec.get("pros_id"),
            "client": {"name": client.get("name") or r.get("client_name") or "", "email": client.get("email") or "", "phone": client.get("phone") or ""},
            "pros_name": r.get("client_name") if rec.get("pros_id") else None}


def doc_pdf(k, r, s, client, signed_ok=True):
    f = (r.get("signed") or {}).get(k) if signed_ok else None
    return S.get_object(f["storage_path"])[0] if f else DD.render([k], r, s, client)


@api.get("/diu/{item_id}/pdf")
async def diu_pdf(item_id: str, doc: str = "all", fmt: str = "pdf", orig: int = 0, authorization: str = Header(None), auth: str = Query(None)):
    user = await S.user_from_token(authorization, auth)
    rec, r, client, s = await diu_ctx(user, item_id)
    if doc != "all" and doc not in DD.TITLES:
        raise HTTPException(status_code=404, detail="Document inexistent")
    base = f"DIU_{doc}_{(client.get('name') or r.get('client_name') or 'dosar').replace(' ', '_')}"
    if fmt == "docx":
        if doc in ("all", "schema_tg"):
            raise HTTPException(status_code=400, detail="Exportul Word este disponibil pe fiecare document, cu excepția schemei desenate")
        return Response(content=DD.render_docx(doc, r, s, client), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": S.disp("attachment", base + ".docx")})
    keys = [k for k, _ in DD.DOCS] if doc == "all" else [doc]
    signed = r.get("signed") or {}
    pos = {p["key"]: p for p in DD.positions(r, s)}
    draft = any(pos[k]["missing"] for k in keys if not signed.get(k))
    w = PdfWriter()
    for k in keys:
        is_signed = bool(signed.get(k)) and not orig
        part = doc_pdf(k, r, s, client, not orig)
        pw = PdfWriter()
        for pg in PdfReader(io.BytesIO(part)).pages:
            pw.add_page(pg)
        if not is_signed and pos[k]["missing"]:
            OPIS.watermark(pw)
        if not is_signed and r.get("is_test"):
            OPIS.watermark(pw, "DOSAR DE TEST — NEOFICIAL", 38)
        for pg in pw.pages:
            w.add_page(pg)
    o = io.BytesIO(); w.write(o)
    return Response(content=o.getvalue(), media_type="application/pdf", headers={"Content-Disposition": S.disp("inline", base + ("_CIORNA" if draft else "") + ".pdf")})


@api.post("/diu/{item_id}/sign")
async def diu_sign(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    S.guard("diu", user, write=True)
    S.need(user, "sign_remote", True)
    rec, r, client, s = await diu_ctx(user, item_id)
    b = await request.json()
    keys, sg = b.get("pos_keys") or [], b.get("signer") or {}
    if not keys or any(k not in DD.TITLES for k in keys):
        raise HTTPException(status_code=400, detail="Alege documentele DI-U de semnat")
    if not (sg.get("name") or "").strip() or "@" not in (sg.get("email") or ""):
        raise HTTPException(status_code=400, detail="Clientul are nevoie de nume și e-mail valid (pentru codul de verificare)")
    days = S.parse_days(b.get("expires_days"))
    out = []
    for k in keys:
        pdf = DD.render([k], r, s, client)
        if r.get("is_test"):
            pdf = OPIS.mark_test(pdf)
        gid = str(uuid.uuid4())
        stored = S.put_object(f"{S.APP_NAME}/sign/{user['id']}/{gid}/original.pdf", pdf, "application/pdf")
        t, th, exp = S.new_token(days)
        req = S._new(user, {"module": "diu", "group_id": gid, "dossier_id": item_id, "client_name": client.get("name") or r.get("client_name"), "pos_key": k,
                            "doc_title": f"DI-U — {DD.TITLES[k]}", "doc_path": stored["path"], "doc_sha256": S.sha(pdf), "signer_name": sg["name"].strip(),
                            "signer_email": sg["email"].strip(), "signer_phone": (sg.get("phone") or "").strip(), "role": "Beneficiar", "status": "De trimis",
                            "token_hash": th, "expires_at": exp, "otp_sends": 0, "otp_attempts": 0, "is_test": bool(r.get("is_test")),
                            "history": [S.hist("Cerere creată", None, f"de {user.get('email')}; link valabil până la {exp[:16]} UTC")]})
        await db.sign_requests.insert_one(dict(req))
        out.append({**S.sign_public(req), "token": t})
    await S.audit(user, "cerere semnare", "diu", item_id, keys)
    return out


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
    upd = {"pros_id": pid, "client_name": p.get("client_name"), "address": p.get("address"), "operator": p.get("operator"), "power": p.get("power"), "atr": p.get("atr")}
    if p.get("client_id"):
        upd["client_id"] = p["client_id"]
    fill = {"supply": p.get("supply"), "earthing": g.get("earthing"), "tg_breaker_a": g.get("tg_breaker_a"), "bmp_a": g.get("bmp_a"),
            "type": "Sistem fotovoltaic hibrid" if p.get("battery") or "hibrid" in str(p.get("system_type") or "").lower() else "Sistem fotovoltaic on-grid",
            **{k: p.get(k) for k in ("receptie_date", "receptie_decision", "receptie_findings", "pif_date", "warranty_months")}}
    upd.update({k: v for k, v in fill.items() if v not in (None, "") and rec.get(k) in (None, "")})
    upd = {k: v for k, v in upd.items() if v not in (None, "")}
    if not rec.get("circuits"):
        upd["circuits"] = [{"name": f"INV{i + 1} — {inv.get('brand_model') or 'invertor'}", "breaker_a": (inv.get("ac") or {}).get("breaker_a"),
                            "curve": (inv.get("ac") or {}).get("curve") or "C", "section": (inv.get("ac") or {}).get("section"),
                            "cable": (inv.get("ac") or {}).get("cable_type"), "length": (inv.get("ac") or {}).get("length_m"),
                            "rcd_ma": inv.get("rcd_ma"), "rcd_type": rcd(inv.get("rcd_type"))} for i, inv in enumerate(cef.get("inverters") or [])]
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
