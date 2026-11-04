import io
import uuid
import unicodedata
import zipfile
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


def inverter_circuit_name(index: int, inverter: dict) -> str:
    try:
        count = max(1, int(float(inverter.get("count") or 1)))
    except (TypeError, ValueError):
        count = 1
    model = inverter.get("brand_model") or "invertor"
    return f"INV{index + 1} — {model}" + (f" × {count} buc." if count > 1 else "")


async def diu_ctx(user: dict, item_id: str):
    S.guard("diu", user)
    rec = await S.check_access(user, "diu", item_id)
    prec = None
    if rec.get("pros_id"):
        prec = await db.prosumator.find_one({**S.scope_q(user, "prosumator"), "id": rec["pros_id"]}, {"_id": 0})
    prec = CEF.flatten(CEF.from_legacy(prec)) if prec else {}
    client = await S.get_client(user["id"], rec) or (await S.get_client(user["id"], prec) if prec else {})
    base = await db.settings.find_one({"owner": user["id"]}, {"_id": 0}) or {}
    # The DI-U uses the company representative configured in company settings.
    # Do not inherit legacy signer, verifier, or metrology-apparatus selections.
    s, _ = await S.effective_settings(user["id"], rec, base)
    prec = {k: v for k, v in prec.items() if not k.startswith(OWN)}
    merged = {**prec, **{k: v for k, v in rec.items() if v not in (None, "", [], {})}}
    pm = dict(merged.get("pram_m") or {})
    pm.pop("instrument", None)
    pm.pop("metrology_valid_until", None)
    pm.pop("verifier", None)
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
    if doc != "all" and doc not in {k for k, _ in DD.applicable_docs(r)}:
        raise HTTPException(status_code=404, detail="Document inexistent")
    base = f"DIU_{doc}_{(client.get('name') or r.get('client_name') or 'dosar').replace(' ', '_')}"
    if fmt == "docx":
        if doc in ("all", "schema_tg"):
            raise HTTPException(status_code=400, detail="Exportul Word este disponibil pe fiecare document, cu excepția schemei desenate")
        return Response(content=DD.render_docx(doc, r, s, client), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": S.disp("attachment", base + ".docx")})
    keys = [k for k, _ in DD.applicable_docs(r)] if doc == "all" else [doc]
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


@api.get("/diu/{item_id}/package")
async def diu_package(item_id: str, authorization: str = Header(None), auth: str = Query(None)):
    """Download the generated DI-U PDF together with selected client and equipment evidence."""
    user = await S.user_from_token(authorization, auth)
    rec, r, client, s = await diu_ctx(user, item_id)
    keys = [k for k, _ in DD.applicable_docs(r)]
    signed = r.get("signed") or {}
    pos = {p["key"]: p for p in DD.positions(r, s)}
    draft = any(pos[k]["missing"] for k in keys if not signed.get(k))
    writer = PdfWriter()
    for key in keys:
        is_signed = bool(signed.get(key))
        part = doc_pdf(key, r, s, client, True)
        part_writer = PdfWriter()
        for page in PdfReader(io.BytesIO(part)).pages:
            part_writer.add_page(page)
        if not is_signed and pos[key]["missing"]:
            OPIS.watermark(part_writer)
        if not is_signed and r.get("is_test"):
            OPIS.watermark(part_writer, "DOSAR DE TEST — NEOFICIAL", 38)
        for page in part_writer.pages:
            writer.add_page(page)
    pdf_out = io.BytesIO()
    writer.write(pdf_out)

    client_docs, client_issues = S.atr_client_documents(user, client)
    evidence = []
    if rec.get("pros_id"):
        pros = await db.prosumator.find_one(
            {**S.scope_q(user, "prosumator"), "id": rec["pros_id"]}, {"_id": 0}
        )
        if pros:
            evidence = await S.catalog_files(user["id"], CEF.flatten(CEF.from_legacy(pros)))
    used = 0
    max_total = 100 * 1024 * 1024
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("DI-U/00_Dosar_DI-U.pdf" if not draft else "DI-U/00_Dosar_DI-U_CIORNA.pdf", pdf_out.getvalue())
        manifest = ["Pachet DI-U — documente generate și documente justificative selectate."]
        if draft:
            manifest.append("ATENȚIE: dosarul PDF este ciornă; lipsesc date reale necesare completării/verificării.")
        for item in client_docs:
            data = item["data"]
            if used + len(data) > max_total:
                client_issues.append(f"{item['label']} — omisă, limita de 100 MB a pachetului a fost atinsă.")
                continue
            used += len(data)
            name = str(item["name"]).replace("\\", "_").replace("/", "_")
            bundle.writestr(f"Documente client/{item['label']} — {name}", data)
            manifest.append(f"Client: {item['label']} — {name}")
        for item in evidence:
            try:
                data, _ = S.get_object(item["storage_path"])
                if used + len(data) > max_total:
                    client_issues.append(f"{item.get('kind')} {item.get('model')} — omis, limita de 100 MB a fost atinsă.")
                    continue
                used += len(data)
                name = str(item.get("original_filename") or "document").replace("\\", "_").replace("/", "_")
                label = str(item.get("kind") or "Document echipament")
                model = str(item.get("model") or "echipament")
                bundle.writestr(f"Echipamente/{label} — {model} — {name}", data)
                manifest.append(f"Echipament: {label} — {model} — {name}")
            except Exception as exc:
                client_issues.append(f"{item.get('kind')} {item.get('model')} — fișierul nu a putut fi citit.")
                S.logger.warning("DI-U catalog evidence could not be read: %s", exc)
        if client_issues:
            manifest.append("")
            manifest.append("Fișiere omise:")
            manifest.extend(f"- {issue}" for issue in client_issues)
        bundle.writestr("00_CITESTE.txt", "\n".join(manifest))
    name = (client.get("name") or r.get("client_name") or "dosar").replace(" ", "_")
    return Response(content=out.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": S.disp("attachment", f"DIU_{name}.zip")})


@api.post("/diu/{item_id}/sign")
async def diu_sign(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    S.guard("diu", user, write=True)
    S.need(user, "sign_remote", True)
    rec, r, client, s = await diu_ctx(user, item_id)
    b = await request.json()
    keys, sg = b.get("pos_keys") or [], b.get("signer") or {}
    if not keys or any(k not in {key for key, _ in DD.applicable_docs(r)} for k in keys):
        raise HTTPException(status_code=400, detail="Alege documentele DI-U de semnat")
    positions = {position["key"]: position for position in DD.positions(r, s)}
    incomplete = [positions[key] for key in keys if positions.get(key, {}).get("missing")]
    if incomplete:
        details = "; ".join(
            f"{position['title']}: {', '.join(position['missing'])}"
            for position in incomplete
        )
        raise HTTPException(
            status_code=400,
            detail=("Nu pot trimite la semnare documente DI-U incomplete. Completează și verifică datele reale: " + details)[:2000],
        )
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
    return await import_prosumer_into_diu(user, item_id, rec, pid)


async def import_prosumer_into_diu(user: dict, item_id: str, rec: dict, pid: str):
    p = await db.prosumator.find_one({**S.scope_q(user, "prosumator"), "id": pid}, {"_id": 0}) if pid else None
    if not p:
        raise HTTPException(status_code=404, detail="Dosar de prosumator inexistent")

    def name_key(value):
        value = unicodedata.normalize("NFD", str(value or ""))
        value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
        return " ".join(value.casefold().split())

    rec_client_id, pros_client_id = rec.get("client_id"), p.get("client_id")
    if rec_client_id and pros_client_id:
        same_client = rec_client_id == pros_client_id
    else:
        diu_name = rec.get("client_name") or rec.get("name")
        pros_name = p.get("client_name") or p.get("name")
        same_client = bool(diu_name and pros_name and name_key(diu_name) == name_key(pros_name))
    if not same_client:
        raise HTTPException(status_code=409, detail="Dosarul prosumator selectat nu aparține aceluiași client ca dosarul DI-U.")

    p = CEF.from_legacy(p)
    cef = p.get("cef") or {}
    g = cef.get("grid") or {}
    inverters = cef.get("inverters") or []
    has_storage = CEF.has_storage(p)
    switching = rec.get("pros_id") != pid
    fill = {"client_name": p.get("client_name"), "client_id": p.get("client_id"), "address": p.get("address"),
            "operator": p.get("operator"), "power": p.get("power"), "atr": p.get("atr"),
            "supply": p.get("supply"), "earthing": g.get("earthing"), "tg_breaker_a": g.get("tg_breaker_a"),
            "bmp_a": g.get("bmp_a"), "meter_enabled": bool(g.get("meter_enabled") if g.get("meter_enabled") is not None else g.get("meter")),
            "meter": g.get("meter"), "meter_serial": g.get("meter_serial"), "meter_specs": g.get("meter_specs"),
            "type": "Sistem fotovoltaic hibrid" if has_storage else "Sistem fotovoltaic on-grid",
            **{k: p.get(k) for k in ("receptie_date", "receptie_decision", "receptie_findings", "pif_date", "warranty_months")}}
    upd = {"pros_id": pid}
    # Switching the linked installation is a source change: overwrite or clear
    # every imported field so no client data leaks from the previous dossier.
    # Re-importing the same source only fills empty fields to preserve DI-U edits.
    if switching:
        upd.update(fill)
    else:
        upd.update({k: v for k, v in fill.items() if v not in (None, "") and rec.get(k) in (None, "")})
    if switching or not rec.get("circuits"):
        upd["circuits"] = [{"name": inverter_circuit_name(i, inv), "breaker_a": (inv.get("ac") or {}).get("breaker_a"),
                            "curve": (inv.get("ac") or {}).get("curve") or "C", "section": (inv.get("ac") or {}).get("section"),
                            "cable": (inv.get("ac") or {}).get("cable_type"), "length": (inv.get("ac") or {}).get("length_m"),
                            "rcd_ma": inv.get("rcd_ma"), "rcd_type": rcd(inv.get("rcd_type"))} for i, inv in enumerate(inverters)]
    gr = g.get("grounding_ohm") or p.get("grounding_ohm")
    if switching:
        # Measurements belong to the selected installation; clear old values
        # and copy only actual measurements present in its source dossier.
        pm = {}
        if gr not in (None, ""):
            pm["earth_ohm"] = gr
        if p.get("grounding_limit") not in (None, ""):
            pm["earth_limit"] = p["grounding_limit"]
        upd["pram_m"] = pm
    else:
        pm = dict(rec.get("pram_m") or {})
        if gr not in (None, "") and not pm.get("earth_ohm"):
            pm["earth_ohm"] = gr
        if p.get("grounding_limit") not in (None, "") and not pm.get("earth_limit"):
            pm["earth_limit"] = p["grounding_limit"]
        upd["pram_m"] = pm
    upd["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.diu.update_one({"id": item_id, "owner": user["id"]}, {"$set": upd})
    await S.audit(user, "preluare din prosumator", "diu", item_id, list(upd.keys()))
    return await db.diu.find_one({"id": item_id}, {"_id": 0})


@api.post("/power/{item_id}/ensure-diu")
async def power_ensure_diu(item_id: str, user: dict = Depends(get_current_user)):
    """Create or refresh the linked DI-U when a power-increase dossier is saved."""
    S.guard("power", user)
    S.guard("diu", user, write=True)
    power = await S.check_access(user, "power", item_id)
    owner = user["id"]
    pros_id = str(power.get("pros_id") or "").strip()
    pros = None
    if pros_id:
        pros = await db.prosumator.find_one({**S.scope_q(user, "prosumator"), "id": pros_id}, {"_id": 0})
        if not pros:
            raise HTTPException(status_code=404, detail="Dosarul de prosumator asociat nu mai există")
        power_client_id = power.get("client_id")
        pros_client_id = pros.get("client_id")
        if power_client_id and pros_client_id:
            same_client = power_client_id == pros_client_id
        else:
            def name_key(value):
                value = unicodedata.normalize("NFD", str(value or ""))
                value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
                return " ".join(value.casefold().split())
            power_name = power.get("client_name") or ""
            pros_name = pros.get("client_name") or pros.get("name") or ""
            same_client = bool(power_name and pros_name and name_key(power_name) == name_key(pros_name))
        if not same_client:
            raise HTTPException(status_code=409, detail="Dosarul prosumator selectat aparține altui client decât cererea de spor.")
    rec = await db.diu.find_one({"owner": owner, "power_id": item_id}, {"_id": 0})
    created = rec is None
    if rec is None and power.get("diu_id"):
        rec = await db.diu.find_one({**S.scope_q(user, "diu"), "id": power["diu_id"]}, {"_id": 0})
        created = False

    if rec is None:
        client = await S.get_client(owner, power) or {}
        now = datetime.now(timezone.utc).isoformat()
        number = str(power.get("number") or "").strip()
        rec = {
            "id": str(uuid.uuid4()),
            "owner": owner,
            "created_at": now,
            "updated_at": now,
            "created_by": user.get("uid"),
            "created_by_email": user.get("email"),
            "client_id": power.get("client_id") or client.get("id"),
            "client_name": power.get("client_name") or client.get("name") or "",
            "address": power.get("address") or client.get("consumption_address") or client.get("address") or "",
            "locality": power.get("locality") or client.get("locality") or "",
            "county": power.get("county") or client.get("county") or "",
            "pod": power.get("pod") or client.get("pod") or "",
            "operator": power.get("operator") or client.get("operator") or "",
            "supply": power.get("new_supply") or power.get("current_supply") or power.get("supply") or "",
            "atr": power.get("atr") or "",
            "type": "Sistem fotovoltaic",
            "status": "Documente de completat",
            "workflow_status": "În pregătire",
            "power_id": item_id,
            "power_request_number": number,
            "requested_power_kw": power.get("requested") or power.get("requested_power") or "",
            "approved_power_kw": power.get("approved") or power.get("approved_power") or "",
            "request_type": "spor de putere",
            "is_test": bool(power.get("is_test")),
        }
        await db.diu.insert_one(dict(rec))
    else:
        # Existing user-entered DI-U values remain authoritative. Power-request
        # references are safe to refresh and let retries remain idempotent.
        await db.diu.update_one(
            {"id": rec["id"], "owner": owner},
            {"$set": {
                "power_id": item_id,
                "power_request_number": str(power.get("number") or "").strip(),
                "requested_power_kw": power.get("requested") or power.get("requested_power") or "",
                "approved_power_kw": power.get("approved") or power.get("approved_power") or "",
                "request_type": "spor de putere",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        rec = await db.diu.find_one({"id": rec["id"], "owner": owner}, {"_id": 0}) or rec

    if pros_id:
        # Reuse the same ownership and same-client validation as the manual DI-U
        # import action. It copies only values present in the source dossier.
        rec = await import_prosumer_into_diu(user, rec["id"], rec, pros_id)
    await db.power.update_one(
        {"id": item_id, "owner": owner},
        {"$set": {"diu_id": rec["id"]}},
    )
    if created:
        await S.audit(user, "creare automată DI-U din spor de putere", "diu", rec["id"], ["power_id", "pros_id", "client_id"])
    await S.audit(user, "legare DI-U la spor de putere", "power", item_id, ["diu_id"])
    return {"id": rec["id"], "diu_id": rec["id"], "created": created, "number": rec.get("number") or "", "status": rec.get("status") or "Documente de completat"}

