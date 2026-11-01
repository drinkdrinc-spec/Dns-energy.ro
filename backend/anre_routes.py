import io
import re
import unicodedata
import uuid
import zipfile
from datetime import datetime, timezone, date

from fastapi import HTTPException, Request, Depends, UploadFile, File, Form, Header, Query, Response

import server as S
import anre_doc as AD

db, api, get_current_user = S.db, S.api_router, S.get_current_user
PRICE = 3200.0
STATUSES = ["Ciornă", "În completare", "Documente lipsă", "În verificare", "Pregătit pentru semnare", "Pregătit pentru depunere", "Depus", "Soluționat"]
DOC_ST = ["lipsă", "încărcat — necesită verificare", "verificat", "expirat / nevalid", "necesită verificare manuală"]
SRC = {"client": "de încărcat de client", "generat_verificare": "generat automat — necesită verificare", "generat": "generat de aplicație"}
GEN = {"cerere", "organigrama", "dotari", "personal", "decl_9", "decl_10"}
MAGIC = {"application/pdf": b"%PDF", "image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG\r\n\x1a\n"}
now = lambda: datetime.now(timezone.utc).isoformat()


def is_pf(user):
    return user["uid"] == S.PLATFORM["id"]


async def get_d(user, did):
    q = {"id": did} if is_pf(user) else {"id": did, "owner": user["id"]}
    d = await db.anre_dossiers.find_one(q, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
    return d


def paid_or_403(d, user):
    if d.get("payment_status") not in ("plătit", "intern") and not is_pf(user):
        raise HTTPException(status_code=402, detail="Serviciul ANRE comandat (3.200 lei + TVA) se activează după confirmarea plății prin OP de către administrator")


def items(d):
    out = []
    for it in AD.opis_items(d.get("kind")):
        st = (d.get("docs") or {}).get(it["key"]) or {}
        status = st.get("status") or ("generat — de verificat" if it["key"] in GEN else "lipsă")
        if it["key"] in GEN and st.get("approved"):
            status = "verificat"
        if it["key"] == "cert_constatator" and st.get("issued"):
            try:
                if (date.today() - date.fromisoformat(st["issued"])).days > 30:
                    status = "expirat / nevalid"
            except ValueError:
                status = "necesită verificare manuală"
        out.append({**it, "source_label": SRC[it["source"]], "status": status, "file": st.get("name"), "issued": st.get("issued"), "notes": st.get("notes")})
    return out


# Minimum electrician qualifications by attestation type, transcribed from
# Annex 8 of ANRE Order 134/2021. Each entry is the required count per grade.
ANRE_MIN_STAFF = {
    "A1": {"IIB": 2}, "A2": {"IIB": 1, "IIIB": 1}, "A3": {"IIB": 1, "IIIB": 1},
    "B": {"IIA": 1, "IIB": 1}, "Bi": {"IIB": 2}, "Bp": {"IIA": 2},
    "C1A": {"IIIA": 2}, "C1B": {"IVA": 2}, "C2A": {"IIIB": 2}, "C2B": {"IVB": 2},
    "D1": {"IVA": 2}, "D2": {"IVB": 2}, "E1": {"IVA": 2}, "E2": {"IVB": 2},
}


def staff_grades(value):
    normalized = unicodedata.normalize("NFD", str(value or "")).encode("ascii", "ignore").decode("ascii").upper()
    normalized = re.sub(r"[^A-Z0-9]", "", normalized)
    return set(re.findall(r"IV[AB]|III[AB]|II[AB]", normalized))


def staff_name_key(value):
    normalized = unicodedata.normalize("NFD", str(value or ""))
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return " ".join(normalized.casefold().split())


def check(d):
    its = items(d)
    c = d.get("company") or {}
    rep = {"at": now(), "present": [], "missing": [], "review": [], "incomplete": [], "issues": [], "actions": []}
    for i in its:
        (rep["present"] if i["status"] == "verificat" else rep["missing"] if i["status"] == "lipsă" else rep["review"]).append(f"{i['nr']}. {i['title']} — {i['status']}")
    for k, l in (("name", "denumire"), ("cui", "CUI"), ("regcom", "Nr. Reg. Comerțului"), ("address", "sediu social"), ("rep_name", "reprezentant legal"), ("email", "e-mail"), ("phone", "telefon")):
        if not c.get(k):
            rep["incomplete"].append(f"Date firmă: lipsește {l}")
    if d.get("kind") in ("nou", "b_c1a", "b_c2a", "vizare"):
        if not [x for x in d.get("equipment") or [] if x.get("name")]:
            rep["incomplete"].append("Lista dotărilor tehnico-materiale este goală (minimul din Anexa nr. 6)")
        target_types = list(dict.fromkeys(str(x).strip() for x in (d.get("target_types") or []) if str(x).strip()))
        if not target_types:
            rep["incomplete"].append("Tipul de atestat solicitat nu este ales")
        named_staff = {}
        for person in d.get("staff") or []:
            key = staff_name_key(person.get("name"))
            if key:
                named_staff.setdefault(key, person)
        for target in target_types:
            requirements = ANRE_MIN_STAFF.get(target)
            if not requirements:
                rep["issues"].append(f"Tipul de atestat {target} nu are o regulă de personal mapată; verificați Anexa nr. 8 înainte de finalizare")
                continue
            for grade, required_count in requirements.items():
                found = sum(1 for person in named_staff.values() if grade in staff_grades(person.get("grade")))
                if found < required_count:
                    rep["incomplete"].append(
                        f"Personal insuficient pentru {target}: lipsesc {required_count - found} electrician(i) cu autorizare {grade} conform Anexei nr. 8"
                    )
        for person in named_staff.values():
            if person.get("grade") and not person.get("license"):
                rep["incomplete"].append(f"Fișa de personal: lipsește numărul legitimației ANRE pentru {person.get('name')}")
    if d.get("kind") in ("b_c1a", "b_c2a") and "B" not in str(c.get("attest_types") or ""):
        rep["issues"].append("Solicitare de extindere de la B, dar atestatul existent declarat nu conține tipul B — verificați eligibilitatea")
    for s in d.get("staff") or []:
        if s.get("license_valid") and s["license_valid"] < date.today().isoformat():
            rep["issues"].append(f"Autorizarea ANRE a lui {s.get('name')} este expirată ({s['license_valid']})")
        elif s.get("name") and s.get("grade") and not s.get("license_valid"):
            rep["issues"].append(f"Valabilitatea autorizației ANRE a lui {s.get('name')} nu este precizată — verificați legitimația")
    rep["actions"] = [f"Încărcați / verificați: {x}" for x in rep["missing"] + rep["review"]] + [f"Completați: {x}" for x in rep["incomplete"]] + [f"Clarificați: {x}" for x in rep["issues"]]
    rep["ok"] = not (rep["missing"] or rep["review"] or rep["incomplete"] or rep["issues"])
    return rep


def pub(d):
    its = items(d)
    done = sum(1 for i in its if i["status"] == "verificat")
    return {**{k: v for k, v in d.items() if k not in ("ai",)}, "items": its, "progress": round(100 * done / max(len(its), 1)), "statuses": STATUSES, "types": AD.TYPES, "doc_statuses": DOC_ST}


@api.get("/anre/dossiers")
async def anre_list(user: dict = Depends(get_current_user)):
    q = {} if is_pf(user) else {"owner": user["id"]}
    out = []
    for d in await db.anre_dossiers.find(q, {"_id": 0, "ai": 0}).sort("created_at", -1).to_list(1000):
        p = pub(d)
        op = await db.operators.find_one({"tenant": d["owner"]}, {"status": 1}) or {}
        out.append({k: p.get(k) for k in ("id", "owner", "kind", "status", "creation_mode", "payment_status", "progress", "created_at", "final_check")} | {
            "company": (d.get("company") or {}).get("name"), "cui": (d.get("company") or {}).get("cui"), "owner_email": d.get("created_by"), "attest_status": op.get("status") or "netrimis",
            "missing": sum(1 for i in p["items"] if i["status"] != "verificat")})
    return out


@api.post("/anre/dossiers")
async def anre_create(request: Request, user: dict = Depends(get_current_user)):
    b = await request.json()
    if b.get("kind") not in AD.TYPES:
        raise HTTPException(status_code=400, detail="Alegeți tipul solicitării")
    op = await db.operators.find_one({"tenant": user["id"]}, {"_id": 0}) or {}
    internal = b.get("mode") == "intern"
    cfg = await S.billing_cfg() if not internal else {}
    vat = round(PRICE * float(cfg.get("vat_rate", 21)) / 100, 2) if not internal else 0
    d = {"id": str(uuid.uuid4()), "owner": user["id"], "kind": b["kind"], "target_types": b.get("target_types") or [], "status": "Ciornă", "created_at": now(), "updated_at": now(),
         "created_by": user.get("email"), "creation_mode": "intern" if internal else "serviciu", "payment_status": "intern" if internal else "neplătit", "price": {"net": 0 if internal else PRICE, "vat": vat, "total": 0 if internal else round(PRICE + vat, 2), "note": "Dosar intern — fără comandă de servicii" if internal else "Serviciu D-ENERGY; tarifele ANRE se plătesc separat"},
         "company": {"name": op.get("company"), "cui": op.get("cui"), "regcom": op.get("regcom"), "email": op.get("contact_email"), "phone": op.get("contact_phone"),
                     "rep_name": op.get("contact_name"), "rep_role": op.get("holder_role"), "attest_no": op.get("attest_no"), "attest_types": ", ".join(op.get("attest_types") or []), "attest_valid": op.get("attest_valid")},
         "docs": {}, "staff": [], "equipment": [], "org": [], "history": [{"at": now(), "by": user.get("email"), "event": "dosar intern creat" if internal else "comandă creată"}]}
    if not internal:
        import billing_routes as BR
        inv = await BR.service_invoice(user["id"], user.get("email"), f"Serviciu D-ENERGY — pregătire Dosar ANRE ({AD.TYPES[b['kind']]}), ref. {d['id'][:8]}", PRICE, user.get("email"),
                                       {"client_type": "pj", "company_name": op.get("company"), "cui": op.get("cui"), "regcom": op.get("regcom"), "billing_email": op.get("contact_email") or user.get("email"),
                                    "phone": op.get("contact_phone"), "rep_name": op.get("contact_name"), "country": "România"})
        d.update({"invoice_id": inv["id"], "invoice_number": inv["number"], "transfer": inv["transfer"]})
        d["history"].append({"at": now(), "by": "sistem", "event": f"proformă emisă: {inv['number']}"})
    await db.anre_dossiers.insert_one(dict(d))
    await S.audit(user, "dosar ANRE intern creat" if internal else "comandă dosar ANRE", "anre", d["id"], [d["kind"], d.get("invoice_number") or "intern"])
    return pub(d)


@api.get("/anre/dossiers/{did}")
async def anre_get(did: str, user: dict = Depends(get_current_user)):
    return pub(await get_d(user, did))


@api.put("/anre/dossiers/{did}")
async def anre_update(did: str, request: Request, user: dict = Depends(get_current_user)):
    d = await get_d(user, did)
    paid_or_403(d, user)
    b = await request.json()
    upd = {k: b[k] for k in ("company", "staff", "equipment", "org", "target_types") if k in b}
    if any(d.get(k) != v for k, v in upd.items()):
        for g in GEN:
            if (d.get("docs") or {}).get(g, {}).get("approved"):
                upd[f"docs.{g}.approved"] = False
                upd[f"docs.{g}.status"] = "generat — de verificat"
    if b.get("status"):
        st = b["status"]
        if st not in STATUSES:
            raise HTTPException(status_code=400, detail="Status invalid")
        if st in ("Pregătit pentru semnare", "Pregătit pentru depunere") and not check({**d, **upd})["ok"]:
            raise HTTPException(status_code=400, detail="Dosarul are documente lipsă sau neclarități nerezolvate — rulați verificarea finală")
        if st == "Depus" and not (b.get("filing_no") and b.get("filing_date")):
            raise HTTPException(status_code=400, detail="„Depus” se marchează doar cu numărul și data înregistrării la ANRE")
        if st == "Soluționat" and not (b.get("result") and d.get("docs", {}).get("decizie")):
            raise HTTPException(status_code=400, detail="„Soluționat” necesită rezultatul și documentul ANRE încărcat (decizie/atestat)")
        upd.update({"status": st, **{k: b[k] for k in ("filing_no", "filing_date", "result") if b.get(k)}})
    elif d["status"] == "Ciornă":
        upd["status"] = "În completare"
    await db.anre_dossiers.update_one({"id": did}, {"$set": {**upd, "updated_at": now()}, "$push": {"history": {"at": now(), "by": user.get("email"), "event": "actualizare: " + ", ".join(upd.keys())}}})
    return pub(await get_d(user, did))


@api.post("/anre/dossiers/{did}/docs/{key}")
async def anre_upload(did: str, key: str, file: UploadFile = File(...), issued: str = Form(""), user: dict = Depends(get_current_user)):
    d = await get_d(user, did)
    paid_or_403(d, user)
    if key not in {i["key"] for i in AD.opis_items(d["kind"])} | {"decizie"}:
        raise HTTPException(status_code=400, detail="Document necunoscut pentru acest tip de dosar")
    if issued:
        try:
            issued = (datetime.strptime(issued.strip(), "%d.%m.%Y").date() if "." in issued else date.fromisoformat(issued.strip())).isoformat()
        except ValueError:
            raise HTTPException(status_code=400, detail="Data emiterii invalidă — folosiți ZZ.LL.AAAA sau AAAA-LL-ZZ")
    data, ct = await file.read(), file.content_type or ""
    if ct not in MAGIC or not data.startswith(MAGIC[ct]) or len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Încărcați PDF, JPG sau PNG (max. 15 MB)")
    lowres = ct != "application/pdf" and len(data) < 40_000
    st = S.put_object(f"{S.APP_NAME}/anre/{d['owner']}/{did}/{key}_{uuid.uuid4().hex[:6]}_{(file.filename or 'doc')[-50:]}", data, ct)
    meta = {"path": st["path"], "name": file.filename, "type": ct, "size": len(data), "at": now(), "by": user.get("email"), "issued": issued or None,
            "status": "necesită verificare manuală" if lowres else "încărcat — necesită verificare", "notes": "imagine mică — verificați lizibilitatea" if lowres else ""}
    await db.anre_dossiers.update_one({"id": did}, {"$set": {f"docs.{key}": meta, "updated_at": now()}, "$push": {"history": {"at": now(), "by": user.get("email"), "event": f"document încărcat: {key}"}}})
    await S.audit(user, "document dosar ANRE", "anre", did, [key])
    return pub(await get_d(user, did))


@api.post("/anre/dossiers/{did}/docs/{key}/review")
async def anre_review(did: str, key: str, request: Request, user: dict = Depends(get_current_user)):
    d = await get_d(user, did)
    paid_or_403(d, user)
    b = await request.json()
    if key in GEN:
        await db.anre_dossiers.update_one({"id": did}, {"$set": {f"docs.{key}.approved": bool(b.get("approved")), f"docs.{key}.approved_by": user.get("email"), f"docs.{key}.status": "verificat" if b.get("approved") else "generat — de verificat"}})
    else:
        if b.get("status") not in DOC_ST or not (d.get("docs") or {}).get(key):
            raise HTTPException(status_code=400, detail="Status invalid sau document neîncărcat")
        await db.anre_dossiers.update_one({"id": did}, {"$set": {f"docs.{key}.status": b["status"], f"docs.{key}.notes": str(b.get("notes") or "")[:500], f"docs.{key}.reviewed_by": user.get("email")}})
    await db.anre_dossiers.update_one({"id": did}, {"$push": {"history": {"at": now(), "by": user.get("email"), "event": f"verificare {key}: {b.get('status') or b.get('approved')}"}}})
    return pub(await get_d(user, did))


async def doc_bytes(d, key):
    if key == "opis":
        return AD.opis_pdf(d, items(d)), "application/pdf", "00_Opis.pdf"
    if key == "raport":
        return AD.report_pdf(d, check(d)), "application/pdf", "Raport_verificare.pdf"
    if key in GEN:
        import anre_templates as AT
        return await AT.filled(key, d) or (AD.render(key, d), "application/pdf", f"{key}.pdf")
    f = (d.get("docs") or {}).get(key)
    if not f or not f.get("path"):
        raise HTTPException(status_code=404, detail="Document neîncărcat")
    return S.get_object(f["path"])[0], f["type"], f["name"]


@api.get("/anre/dossiers/{did}/file/{key}")
async def anre_file(did: str, key: str, authorization: str = Header(None), auth: str = Query(None)):
    user = await S.user_from_token(authorization, auth)
    d = await get_d(user, did)
    paid_or_403(d, user)
    data, ct, name = await doc_bytes(d, key)
    return Response(content=data, media_type=ct, headers={"Content-Disposition": S.disp("inline", name), "Cache-Control": "no-store"})


@api.post("/anre/dossiers/{did}/check")
async def anre_check(did: str, user: dict = Depends(get_current_user)):
    d = await get_d(user, did)
    paid_or_403(d, user)
    rep = check(d)
    await db.anre_dossiers.update_one({"id": did}, {"$set": {"final_check": {"at": rep["at"], "ok": rep["ok"]}, **({"status": "Documente lipsă"} if not rep["ok"] and d["status"] in ("Ciornă", "În completare") else {"status": "În verificare"} if rep["ok"] and d["status"] in ("Ciornă", "În completare", "Documente lipsă") else {})}})
    return rep


@api.get("/anre/dossiers/{did}/package")
async def anre_package(did: str, authorization: str = Header(None), auth: str = Query(None)):
    user = await S.user_from_token(authorization, auth)
    d = await get_d(user, did)
    paid_or_403(d, user)
    rep = check(d)
    if not rep["ok"]:
        raise HTTPException(status_code=400, detail="Pachetul final se generează după rezolvarea tuturor lipsurilor (vezi raportul de verificare)")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("01_Opis/Opis.pdf", AD.opis_pdf(d, items(d)))
        for i in items(d):
            folder = "02_Cerere" if i["key"] == "cerere" else "03_Anexe_si_declaratii" if i["key"] in ("decl_9", "decl_10") else "04_Documente_generate" if i["key"] in GEN else "05_Documente_client"
            data, _, name = await doc_bytes(d, i["key"])
            z.writestr(f"{folder}/{i['nr']:02d}_{name}", data)
        z.writestr("06_Raport_verificare/Raport_final.pdf", AD.report_pdf(d, rep))
    await S.audit(user, "descărcare pachet ANRE", "anre", did, [])
    return Response(content=buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": S.disp("attachment", f"Dosar_ANRE_{(d['company'] or {}).get('cui') or did[:6]}.zip")})


@api.post("/anre/dossiers/{did}/ai")
async def anre_ai(did: str, request: Request, user: dict = Depends(get_current_user)):
    import json
    import ai_routes as AI
    d = await get_d(user, did)
    paid_or_403(d, user)
    q = str((await request.json()).get("text") or "").strip()[:4000]
    if not q:
        raise HTTPException(status_code=400, detail="Scrieți întrebarea")
    ctx = {"tip": AD.TYPES.get(d["kind"]), "tipuri_solicitate": d.get("target_types"), "firma": d.get("company"), "opis": [{k: i[k] for k in ("nr", "title", "basis", "source_label", "status", "notes")} for i in items(d)],
           "personal": d.get("staff"), "dotari": d.get("equipment"), "verificare": check(d)}
    hist = [{"role": m["role"], "content": m["content"]} for m in (d.get("ai") or [])[-20:]]
    system = (f"Ești asistentul D-ENERGY pentru pregătirea dosarelor de atestare ANRE conform {AD.REG}. Explici cerințele, ce document trebuie încărcat și de unde se obține, "
              "câmpurile necompletate, neconcordanțele și pașii următori. Nu inventezi date, nu modifici documente justificative și nu garantezi aprobarea ANRE; când nu ești sigur, "
              "recomanzi verificarea textului oficial pe anre.ro. " + AI.RULES + "\nDOSAR (JSON):\n" + json.dumps(ctx, ensure_ascii=False, default=str)[:12000])
    await db.anre_dossiers.update_one({"id": did}, {"$push": {"ai": {"role": "user", "content": q, "at": now()}}})

    async def done(out):
        await db.anre_dossiers.update_one({"id": did}, {"$push": {"ai": {"role": "assistant", "content": out, "at": now()}}})
    return AI.sse(AI.new_chat(system, hist), q, done)


@api.get("/anre/dossiers/{did}/ai")
async def anre_ai_hist(did: str, user: dict = Depends(get_current_user)):
    d = await get_d(user, did)
    paid_or_403(d, user)
    return d.get("ai") or []


@api.post("/admin/anre/{did}/payment")
async def anre_pay(did: str, request: Request, user: dict = Depends(get_current_user)):
    if not is_pf(user):
        raise HTTPException(status_code=403, detail="Doar administratorul platformei confirmă plata")
    b = await request.json()
    if not (b.get("reference") or "").strip():
        raise HTTPException(status_code=400, detail="Introduceți referința OP / extrasului de cont")
    d = await db.anre_dossiers.find_one({"id": did}, {"_id": 0, "invoice_id": 1})
    if d is None:
        raise HTTPException(status_code=404, detail="Dosar inexistent")
    if d.get("invoice_id"):
        import billing_routes as BR
        inv = await db.invoices.find_one({"id": d["invoice_id"]}, {"_id": 0, "total": 1, "status": 1})
        if inv and inv["status"] != BR.PAID:
            await db.invoices.update_one({"id": d["invoice_id"]}, {"$push": {"payments": {"at": now(), "amount": inv["total"], "method": "transfer bancar (OP)", "reference": b["reference"].strip()[:80], "by": user.get("email")}}})
            await BR.activate(d["invoice_id"], user.get("email"), "plată OP confirmată de administrator")
    await db.anre_dossiers.update_one({"id": did}, {"$set": {"payment_status": "plătit", "payment": {"reference": b["reference"].strip()[:80], "at": now(), "by": user.get("email")}},
                                                   "$push": {"history": {"at": now(), "by": user.get("email"), "event": f"plată confirmată: {b['reference']}"}}})
    await S.audit(user, "plată dosar ANRE confirmată", "anre", did, [b["reference"]])
    return {"payment_status": "plătit"}
