import io
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib import colors
import docgen
import sizing as SZ
import sld as SLD
import pif_doc as PIFDOC

STATUSES = ["de completat", "generat", "necesită semnătură", "atașat"]
CLIENT_SLOTS = {"factura": "Factură furnizor de energie", "certificat": "Certificat de înregistrare", "constatator": "Certificat constatator",
                "ci": "Act de identitate", "cf": "Extras de carte funciară"}
L = {"name": "Nume / denumire client", "idcode": "CNP / CUI", "hq_address": "Domiciliu / sediu social", "phone": "Telefon client",
     "address": "Adresă loc de consum", "county": "Județ loc de consum", "pod": "POD (cod unic de identificare)", "operator": "Operator de distribuție",
     "regcom": "Nr. Registrul Comerțului client", "rep_name": "Reprezentant legal client", "rep_role": "Calitate reprezentant", "ci_series": "Serie/nr. act identitate",
     "apparent_kva": "Putere aparentă evacuată (kVA)", "power": "Putere maximă evacuată (kW)", "doc_date": "Data documentelor",
     "internal_pi": "Pi servicii interne", "internal_pmax": "Pmax absorbită servicii interne", "afm": "Accesare AFM (Da/Nu)", "doc_no": "Nr. declarație executant",
     "bulletin_no": "Nr. buletin priză", "measure_date": "Data măsurătorii", "measure_object": "Obiectivul verificării", "soil": "Starea solului",
     "soil_psi": "Coeficient Ѱ", "grounding_ohm": "Rezistență dispersie măsurată", "grounding_limit": "Valoare admisă (Ω)",
     "pif_date": "Data punerii în funcțiune", "pif_decision": "Hotărâre PIF", "bmp_desc": "Descriere BMP", "anti_relay_present": "Releu antiinsularizare (Da/Nu)",
     "reconnect_min": "Interval reconectare (min)", "receptie_date": "Data recepției", "receptie_decision": "Hotărâre recepție", "receptie_findings": "Constatări recepție"}
EL = {"company": "Denumire executant", "cui": "CUI executant", "regcom": "Reg. Com. executant", "address": "Adresă executant", "phone": "Telefon executant",
      "email": "E-mail executant", "anre_attest": "Atestat ANRE", "rep": "Reprezentant executant", "anre_valid": "Valabilitate atestat ANRE",
      "warranty_months": "Garanție lucrări (luni)", "meter_device": "Aparat de măsură", "meter_serial": "Serie aparat de măsură", "meter_valid": "Valabilitate metrologică"}

GEN = [("notificare", "Anexa 2 — Notificare (Ord. ANRE 19/2022)", ["notificare"], ["apparent_kva", "power", "doc_date", "internal_pi", "internal_pmax"], []),
       ("schema", "Schemă monofilară", ["sld"], [], []),
       ("fisa_tehnica", "Fișă tehnică instalație — echipamente, cabluri și protecții", ["fisa_tehnica"], [], []),
       ("afm", "Declarație accesare fonduri (AFM)", ["declaratie_afm"], ["afm", "doc_date"], []),
       ("reglaj", "Buletin reglaj", ["buletin_reglaj"], ["doc_date"], []),
       ("priza", "Buletin de verificare și măsurare priză de pământ", ["buletin_priza"],
        ["bulletin_no", "measure_date", "measure_object", "soil", "soil_psi", "grounding_ohm", "grounding_limit"], ["meter_device", "meter_serial", "meter_valid"]),
       ("pif", "Proces-verbal de punere în funcțiune", ["pv_pif", "pv_teste"], ["pif_date", "pif_decision", "bmp_desc", "anti_relay_present", "reconnect_min", "afm"], ["anre_valid"]),
       ("receptie", "Proces-verbal de recepție la terminarea lucrărilor", ["pv_receptie", "serii"], ["receptie_date", "receptie_decision", "receptie_findings"], []),
       ("executant", "Declarația executantului (Ord. ANRE 59/2013)", ["declaratie_executant"], ["doc_no", "doc_date"], []),
       ("conformitate", "Declarație de conformitate (HGR 1022/2002)", ["declaratie_conformitate"], ["doc_date"], ["warranty_months"]),
       ("imputernicire", "Împuternicire", ["imputernicire"], ["county"], [])]
COMMON = ["name", "idcode", "hq_address", "phone", "address", "county", "pod", "operator"]
EXEC = ["company", "cui", "regcom", "address", "phone", "email", "anre_attest", "rep"]


def catalog_refs(rec):
    c = rec.get("cef") or {}
    inv, pan, bat = [], [], []
    for i in c.get("inverters") or []:
        inv.append((i.get("catalog_id"), i.get("brand_model")))
        pan.append((i.get("panel_catalog_id"), i.get("panel_model")))
        if i.get("battery_mode") == "own":
            bat.append(((i.get("battery") or {}).get("catalog_id"), (i.get("battery") or {}).get("model")))
    bat += [(b.get("catalog_id"), b.get("model")) for b in c.get("shared_batteries") or []]
    g = c.get("grid") or {}
    met = [(g.get("meter_catalog_id"), g.get("meter"))] if g.get("meter") else []
    if not c.get("inverters"):
        inv = [(None, rec.get("inverter"))] if rec.get("inverter") else []
        pan = [(None, rec.get("panels"))] if rec.get("panels") else []
        bat = [(None, rec.get("battery"))] if rec.get("battery") else []
    dedup = lambda xs: list({(m or ""): (cid, m) for cid, m in xs if m}.values())
    return dedup(inv), dedup(pan), dedup(bat), dedup(met)


async def build_positions(db, owner, rec, client, settings):
    pj = "jurid" in str(client.get("kind") or "").lower()
    ctx = docgen.Ctx(docgen.CEF.flatten(rec), settings, client)
    opis = rec.get("opis") or {}
    req_common = COMMON + (["regcom", "rep_name", "rep_role"] if pj else [])
    pos = []

    common = [L.get(k, k) for k in req_common if ctx.raw(k) in (None, "")] + [EL.get(k, k) for k in EXEC if settings.get(k) in (None, "")]

    def missing(keys, ekeys):
        m = [L.get(k, k) for k in keys if ctx.raw(k) in (None, "")]
        m += [EL.get(k, k) for k in ekeys if settings.get(k) in (None, "")]
        return list(dict.fromkeys(m))

    res_sld = SZ.compute(rec, client)
    st_sld = SZ.state(rec, client, settings)
    for key, title, docs, keys, ekeys in GEN:
        m = missing(keys, ekeys)
        if key == "notificare" and not docgen.inverters(ctx):
            m.append("Invertoare / panouri (configurare CEF)")
        if key in ("schema", "fisa_tehnica"):
            if not (rec.get("cef") or {}).get("inverters"):
                m.append("Configurare CEF (invertoare, stringuri)")
            if res_sld["missing"] or res_sld["errors"]:
                m.append(f"Dimensionare tehnică incompletă: {len(res_sld['missing'])} date lipsă, {len(res_sld['errors'])} erori (secțiunea Schemă monofilară)")
            m.append({"stale": "Aprobarea schemei a fost anulată — configurația s-a modificat; necesită o nouă verificare",
                      "draft": "Schema monofilară nu este aprobată de proiectant / verificator"}.get(st_sld["status"], "")) if st_sld["status"] != "approved" else None
            m[:] = [x for x in m if x]
        if key == "reglaj":
            rg = rec.get("reglaj") or {}
            if any(not (rg.get(k) or {}).get("val") for k, _ in docgen.REGLAJ):
                m.append("Valori reglaje protecții")
        if key == "pif":
            t = rec.get("tests") or {}
            ids = [f"a{i}" for i in range(len(docgen.TESTS_A))] + [f"f{i}" for i in range(len(docgen.FREQ))] + [f"c{i}" for i in range(len(docgen.CHECKS))]
            if any(not (t.get(i) or {}).get("ok") for i in ids):
                m.append("Rezultate teste și verificări (DA/NU)")
        pos.append({"key": key, "title": title, "source": "generat", "docs": docs, "missing": m, "files": []})
        if key == "priza" and PIFDOC.filled(rec):
            pos.append({"key": "pif_pv", "title": PIFDOC.TITLE, "source": "generat", "docs": ["pif_pv"], "missing": [], "files": []})

    cdocs = client.get("docs") or {}
    for key, slots, title in [("factura", ["factura"], "Factură furnizor de energie"),
                              ("certificat", ["certificat", "constatator"] if pj else ["ci"], "Certificat de înregistrare" if pj else "Act de identitate"),
                              ("cf", ["cf"], "Extras de carte funciară")]:
        files = [f for s in slots for f in (cdocs.get(s) or [])]
        pos.append({"key": key, "title": title, "source": "client", "slots": slots, "files": files,
                    "missing": [] if files else [f"Încarcă în fișa clientului: {', '.join(CLIENT_SLOTS[s] for s in slots)}"]})

    inv, pan, bat, met = catalog_refs(rec)

    async def cat(cid, kind):
        it = await db.catalog.find_one({"owner": owner, "id": cid}, {"_id": 0}) if cid else None
        f = (it or {}).get(kind)
        return [f] if f and f.get("storage_path") else []

    groups = [("invertor", inv), ("panou", pan)]
    extra = [("baterie", bat), ("smart meter", met)]
    for label, items in groups + extra:
        for cid, model in items:
            for kind, prefix in (("datasheet", "Fișă tehnică"), ("conformity", "Declarație de conformitate")):
                files = await cat(cid, kind)
                k = f"cat_{kind}_{label.replace(' ', '_')}_{cid or model}"
                pos.append({"key": k, "title": f"{prefix} {label} — {model}", "source": "catalog", "files": files,
                            "missing": [] if files else [f"Încarcă {prefix.lower()} în Catalog echipamente ({model})" + ("" if cid else " și alege modelul din catalog în CEF")]})

    for i, p in enumerate(pos):
        p["nr"] = i + 1
        o = opis.get(p["key"]) or {}
        p["upload"] = o.get("upload")
        if p["key"] in ("schema", "fisa_tehnica") and p["upload"] and (p["upload"].get("sld_hash") != st_sld["fingerprint"] or st_sld["status"] != "approved"):
            p["upload"] = None
            if o.get("upload", {}).get("sld_hash"):
                p["missing"].append("Versiunea semnată anterior nu mai corespunde configurației — necesită verificare și semnare nouă")
            o = {k: v for k, v in o.items() if k not in ("status", "upload")}
        elif p["key"] == "pif_pv" and (p["upload"] or {}).get("pif_hash") and p["upload"]["pif_hash"] != PIFDOC.fingerprint(rec):
            p["upload"] = None
            p["missing"].append("Măsurătorile PIF s-au modificat după semnare — necesită semnare nouă")
            o = {k: v for k, v in o.items() if k not in ("status", "upload")}
        elif p["key"] in ("schema", "fisa_tehnica") and st_sld["status"] != "approved":
            o = {k: v for k, v in o.items() if k != "status"}
        gen_missing = p["missing"] or (p["source"] == "generat" and common)
        auto = "atașat" if (o.get("upload") or (p["source"] != "generat" and p["files"])) else ("de completat" if gen_missing else "generat")
        p["auto_status"] = auto
        p["status"] = o.get("status") or auto
        if o.get("upload"):
            p["missing"] = []
    total = sum(len(p["missing"]) for p in pos) + len(common)
    return {"positions": pos, "common_missing": common, "missing_total": total, "complete": total == 0, "titles": [p["title"] for p in pos]}


def file_pdf(data: bytes, ct: str) -> bytes:
    if "pdf" in (ct or ""):
        return data
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    img = ImageReader(io.BytesIO(data))
    iw, ih = img.getSize()
    w, h = A4
    s = min((w - 40) / iw, (h - 40) / ih)
    c.drawImage(img, (w - iw * s) / 2, (h - ih * s) / 2, iw * s, ih * s)
    c.save()
    return buf.getvalue()


def watermark(writer, text="CIORNĂ", size=70):
    for page in writer.pages:
        w, h = float(page.mediabox.width), float(page.mediabox.height)
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=(w, h))
        c.setFont("LSB", size); c.setFillColor(colors.Color(0.8, 0.1, 0.1, alpha=0.12))
        c.translate(w / 2, h / 2); c.rotate(40); c.drawCentredString(0, 0, text); c.save()
        page.merge_page(PdfReader(io.BytesIO(buf.getvalue())).pages[0])


async def position_pdf(p, rec, client, settings, titles, get_object, force_generated=False):
    if p.get("upload") and not force_generated:
        data, ct = get_object(p["upload"]["storage_path"])
        return [file_pdf(data, p["upload"].get("content_type") or ct)]
    if p.get("key") in ("schema", "fisa_tehnica"):
        res = SZ.compute(rec, client)
        st = SZ.state(rec, client, settings)
        if p["key"] == "fisa_tehnica":
            return [SLD.tech_sheet(rec, client, settings, res, st)]
        sld = rec.get("sld") or {}
        if st["status"] == "approved" and sld.get("source") == "uploaded" and sld.get("upload"):
            data, ct = get_object(sld["upload"]["storage_path"])
            return [file_pdf(data, sld["upload"].get("content_type") or ct)]
        f = SZ.approved_file(rec, st["fingerprint"]) if st["status"] == "approved" else None
        if f:
            return [get_object(f["storage_path"])[0]]
        return [SLD.render(rec, client, settings, res, st)]
    if p.get("key") == "pif_pv":
        return [PIFDOC.render(rec, client, settings)]
    if p["source"] == "generat":
        return [docgen.render(p["docs"], rec, settings, client, titles)]
    out = []
    for f in p["files"]:
        data, ct = get_object(f["storage_path"])
        out.append(file_pdf(data, f.get("content_type") or ct))
    return out


async def export_bundle(positions_info, rec, client, settings, get_object, logger):
    titles = positions_info["titles"]
    w = PdfWriter()
    parts = [docgen.render(["declaratie_autenticitate"], rec, settings, client, titles)]
    for p in positions_info["positions"]:
        try:
            parts += await position_pdf(p, rec, client, settings, titles, get_object)
        except Exception as e:
            logger.error(f"bundle skip {p['key']}: {e}")
    for b in parts:
        try:
            for pg in PdfReader(io.BytesIO(b)).pages:
                w.add_page(pg)
        except Exception as e:
            logger.error(f"bundle merge skip: {e}")
    if not positions_info["complete"]:
        watermark(w)
    if rec.get("is_test"):
        watermark(w, "DOSAR DE TEST — NEOFICIAL", 38)
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


def mark_test(pdf: bytes) -> bytes:
    w = PdfWriter()
    for pg in PdfReader(io.BytesIO(pdf)).pages:
        w.add_page(pg)
    watermark(w, "DOSAR DE TEST — NEOFICIAL", 38)
    o = io.BytesIO(); w.write(o)
    return o.getvalue()
