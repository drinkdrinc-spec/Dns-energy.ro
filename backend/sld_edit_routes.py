import io
import re
from datetime import datetime, timezone
from html import escape

from fastapi import HTTPException, Request, Depends, Header, Query, Response
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm

import server as S
import docgen as D
import cef as CEF

db, api, get_current_user = S.db, S.api_router, S.get_current_user

INV_FIELDS = [("brand_model", "Invertor — marcă/model", "text"), ("ac.breaker_a", "Întreruptor AC (A)", "num"), ("ac.curve", "Curbă întreruptor AC", "text"),
              ("ac.section", "Cablu AC — secțiune (mm²)", "num"), ("ac.length_m", "Cablu AC — lungime (m)", "num"), ("ac.cable_type", "Cablu AC — tip", "text"),
              ("rcd_type", "DDR — tip (A/B/F)", "text"), ("rcd_ma", "DDR — IΔn (mA)", "num"), ("dc.section", "Cablu DC — secțiune (mm²)", "num"),
              ("dc.length_m", "Cablu DC — lungime (m)", "num"), ("dc.switch", "Separator DC", "text"), ("dc.spd_ucpv", "SPD DC Ucpv (V)", "num"),
              ("dc.fuse_a", "Siguranțe gPV (A)", "num"), ("battery.model", "Baterie — model", "text"), ("battery.fuse_a", "Baterie — protecție DC (A)", "num")]
GRID_FIELDS = [("bmp_a", "BMP — întreruptor (A)", "num"), ("tg_breaker_a", "TG — întreruptor general (A)", "num"), ("spd_ac", "SPD AC (tip)", "text"),
               ("earthing", "Sistem legare la pământ", "text"), ("column_section", "Coloană BMP→TG — secțiune (mm²)", "num"),
               ("column_length", "Coloană BMP→TG — lungime (m)", "num"), ("anti_relay", "Releu protecție interfață", "text")]
PATH_RE = re.compile(r"^cef\.(grid\.[a-z_]+|inverters\.\d+\.[a-z_]+(\.[a-z_]+)?)$")


def get_path(d, parts):
    for p in parts:
        d = (d[int(p)] if p.isdigit() and isinstance(d, list) and int(p) < len(d) else None) if isinstance(d, list) else (d or {}).get(p)
    return d


@api.get("/sld/{item_id}/values")
async def sld_values(item_id: str, user: dict = Depends(get_current_user)):
    rec = CEF.from_legacy(await S.check_access(user, "prosumator", item_id))
    cef = rec.get("cef") or {}
    man = set(cef.get("manual") or [])
    auto = set(cef.get("auto_filled") or [])
    row = lambda path, lbl, t: {"path": path, "label": lbl, "type": t, "value": get_path(rec, path.split(".")), "manual": path in man, "auto": path in auto}
    groups = [{"title": "Racord / BMP / TG", "rows": [row(f"cef.grid.{k}", l, t) for k, l, t in GRID_FIELDS]}]
    for i, inv in enumerate(cef.get("inverters") or []):
        rows = [row(f"cef.inverters.{i}.{k}", l, t) for k, l, t in INV_FIELDS if not (k.startswith("battery") and inv.get("battery_mode") != "own")]
        groups.append({"title": f"INV {i + 1} — {inv.get('brand_model') or 'invertor'}", "rows": rows})
    return {"groups": groups, "from_legacy": bool(cef.get("from_legacy"))}


@api.put("/sld/{item_id}/values")
async def sld_values_save(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    S.guard("prosumator", user, write=True)
    rec = await S.check_access(user, "prosumator", item_id)
    cef = rec.get("cef") or {}
    if not cef.get("inverters"):
        raise HTTPException(status_code=400, detail="Preluați întâi datele în configuratorul CEF (butonul din schemă)")
    vals = (await request.json()).get("values") or {}
    allowed = {f"cef.grid.{k}": t for k, _, t in GRID_FIELDS} | {f"cef.inverters.{i}.{k}": t for i in range(len(cef["inverters"])) for k, _, t in INV_FIELDS}
    man = set(cef.get("manual") or [])
    for path, v in list(vals.items())[:200]:
        if path not in allowed or not PATH_RE.match(path):
            raise HTTPException(status_code=400, detail=f"Câmp nepermis: {path}")
        if allowed[path] == "num" and v not in (None, ""):
            try:
                v = float(str(v).replace(",", "."))
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Valoare numerică invalidă: {path}")
        parts = path.split(".")[1:]
        d = cef
        for p in parts[:-1]:
            d = d[int(p)] if p.isdigit() else d.setdefault(p, {})
        d[parts[-1]] = v if v not in ("",) else None
        man.add(path)
    cef["manual"] = sorted(man)
    cef["auto_filled"] = [p for p in cef.get("auto_filled") or [] if p not in vals]
    await db.prosumator.update_one({"id": item_id}, {"$set": {"cef": cef, "updated_at": datetime.now(timezone.utc).isoformat()}})
    await S.audit(user, "update", "prosumator", item_id, [f"schemă: {p}" for p in vals])
    return {"ok": True, "changed": len(vals)}


# ---------------- Proces-verbal PIF (teste și verificări la punerea în funcțiune) ----------------
CHECKS = ["Inspecție vizuală: montaj panouri, structură, cleme, etanșări", "Cabluri DC/AC: traseu, protecție UV/mecanică, etichetare", "Conectori DC compatibili (același producător/tip)",
          "Polaritate stringuri verificată înainte de conectare", "Continuitate conductoare de protecție și echipotențializare rame/structură",
          "Separator DC și protecții AC montate și etichetate conform schemei", "SPD DC/AC montate și conectate la PE", "Etichete de avertizare (dublă alimentare, DC) aplicate",
          "Funcționare invertor: pornire, sincronizare cu rețeaua, fără erori", "Protecție interfață / antiinsularizare: deconectare la lipsa tensiunii rețelei",
          "Limitare / zero-export configurată conform ATR (dacă e cazul)", "Baterie: comunicație BMS, încărcare/descărcare (dacă e cazul)"]
RES = ("", "Conform", "Neconform", "Nu este cazul")


def pif_rows(rec: dict) -> list:
    out = []
    base = CEF.check(rec.get("cef") or {})
    for i, inv in enumerate((rec.get("cef") or {}).get("inverters") or []):
        for k, s in enumerate(base["inverters"][i]["strings"] if i < len(base["inverters"]) else []):
            out.append({"key": f"{i}.{k}", "inv": i + 1, "label": f"INV{i + 1} / S{k + 1} (MPPT {s['mppt']}) — {s['panels']} panouri", "voc_stc": round(s["voc_stc"]) if s.get("voc_stc") else None,
                        "isc": s.get("isc") or None, "aggregate": bool(((inv.get("strings") or [{}])[k] if k < len(inv.get("strings") or []) else {}).get("aggregate"))})
    return out


@api.get("/dossier/{item_id}/pif")
async def pif_get(item_id: str, user: dict = Depends(get_current_user)):
    rec = CEF.from_legacy(await S.check_access(user, "prosumator", item_id))
    return {"pif": rec.get("pif") or {}, "strings": pif_rows(rec), "checks": CHECKS, "results": RES,
            "inverters": [{"n": i + 1, "model": v.get("brand_model")} for i, v in enumerate((rec.get("cef") or {}).get("inverters") or [])],
            "grounding_ohm": (rec.get("cef") or {}).get("grid", {}).get("grounding_ohm") or rec.get("grounding_ohm")}


@api.put("/dossier/{item_id}/pif")
async def pif_save(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    S.guard("prosumator", user, write=True)
    await S.check_access(user, "prosumator", item_id)
    b = await request.json()
    clean = lambda v: str(v)[:120] if v not in (None,) else ""
    pif = {"date": clean(b.get("date")), "operator": clean(b.get("operator")), "instruments": clean(b.get("instruments")), "notes": str(b.get("notes") or "")[:1000],
           "strings": {k: {f: clean(v.get(f)) for f in ("voc", "isc", "riso_p", "riso_n", "polarity")} for k, v in (b.get("strings") or {}).items() if isinstance(v, dict)},
           "inv": {k: {f: clean(v.get(f)) for f in ("u_ac", "f_hz", "p_kw", "anti_s", "rcd_ms", "rcd_ma")} for k, v in (b.get("inv") or {}).items() if isinstance(v, dict)},
           "checks": {str(k): v for k, v in (b.get("checks") or {}).items() if v in RES}, "grounding_measured": clean(b.get("grounding_measured")),
           "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": user.get("email")}
    await db.prosumator.update_one({"id": item_id}, {"$set": {"pif": pif}})
    await S.audit(user, "update", "prosumator", item_id, ["proces-verbal PIF"])
    return {"pif": pif}


@api.get("/dossier/{item_id}/pif/pdf")
async def pif_pdf(item_id: str, authorization: str = Header(None), auth: str = Query(None)):
    user = await S.user_from_token(authorization, auth)
    rec, client, s, _ = await S.dossier_ctx(user, item_id)
    p = rec.get("pif") or {}
    st, M = D.S, D.M
    e = lambda v: escape(str(v)) if v not in (None, "") else ""
    P = lambda t, k="p": Paragraph(t, st[k])
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm, title="PV PIF")
    T = lambda rows, w: D.pdf_table(rows, w, True, 7.4, 273)
    story = [P("PROCES-VERBAL DE EFECTUARE A TESTELOR ȘI VERIFICĂRILOR LA PUNEREA ÎN FUNCȚIUNE", "h"),
             P("a instalației fotovoltaice de producere a energiei electrice (SR EN IEC 62446-1, I7/2011, HD 60364-6)", "sub"),
             P(f"Beneficiar: <b>{e(client.get('name') or rec.get('client_name'))}</b> · Adresa: {e(client.get('address') or rec.get('address'))} · POD: {e(rec.get('pod')) or M} · "
               f"Executant: <b>{e(s.get('company'))}</b> (atestat ANRE {e(s.get('anre_attest')) or M}) · Data testelor: {e(D.ro_date(p.get('date'))) or M}"),
             P(f"Aparate de măsură utilizate (tip, serie, certificat metrologic): {e(p.get('instruments')) or M}"),
             Spacer(1, 4), P("1. Măsurători pe partea de curent continuu (stringuri)", "b")]
    rows = [["String", "Voc STC calculat (V)", "Voc măsurat (V)", "Isc STC panou (A)", "Isc măsurat (A)", "Riso + (MΩ)", "Riso − (MΩ)", "Polaritate"]]
    for r in pif_rows(rec):
        m = (p.get("strings") or {}).get(r["key"]) or {}
        rows.append([e(r["label"]) + (" (stringuri nedefinite)" if r["aggregate"] else ""), e(r["voc_stc"]) or M, e(m.get("voc")), e(r["isc"]) or M, e(m.get("isc")),
                     e(m.get("riso_p")), e(m.get("riso_n")), e(m.get("polarity"))])
    if len(rows) == 1:
        rows.append(["configurația stringurilor nu este definită", M, "", M, "", "", "", ""])
    story += [T(rows, [30, 10, 10, 10, 10, 10, 10, 10]), Spacer(1, 4), P("2. Verificări pe partea de curent alternativ / invertoare", "b")]
    rows = [["Invertor", "U AC (V)", "f (Hz)", "P la test (kW)", "Deconectare la lipsa rețelei (s)", "DDR timp declanșare (ms)", "DDR curent declanșare (mA)"]]
    for i, inv in enumerate((rec.get("cef") or {}).get("inverters") or []):
        m = (p.get("inv") or {}).get(str(i)) or {}
        rows.append([f"INV{i + 1} — {e(inv.get('brand_model')) or M}", e(m.get("u_ac")), e(m.get("f_hz")), e(m.get("p_kw")), e(m.get("anti_s")), e(m.get("rcd_ms")), e(m.get("rcd_ma"))])
    gm = p.get("grounding_measured") or (rec.get("cef") or {}).get("grid", {}).get("grounding_ohm") or rec.get("grounding_ohm")
    story += [T(rows, [30, 10, 10, 12, 14, 12, 12]), Spacer(1, 3),
              P(f"Rezistența prizei de pământ (valoare măsurată, conform buletinului PRAM): {e(gm) + ' Ω' if gm else M}"),
              Spacer(1, 4), P("3. Verificări vizuale și funcționale", "b"),
              T([["Nr.", "Verificare", "Rezultat"]] + [[str(k + 1), c, e((p.get("checks") or {}).get(str(k)))] for k, c in enumerate(CHECKS)], [6, 74, 20])]
    if p.get("notes"):
        story.append(P(f"Observații: {e(p['notes'])}"))
    story += [Spacer(1, 4), P("Rezultatele de mai sus sunt cele măsurate efectiv la data testelor; câmpurile necompletate nu au fost măsurate și nu constituie confirmare de conformitate.", "small"),
              D.pdf_sign(["Executant (electrician autorizat ANRE),", f"<b>{e(s.get('company'))}</b>", e(p.get("operator") or s.get("rep")) or M, "(numele, prenumele și semnătura)", "(ștampilă)"],
                         ["Beneficiar,", f"<b>{e(client.get('name') or rec.get('client_name'))}</b>", "(numele, prenumele și semnătura)"], s)]
    doc.build(story)
    pdf = buf.getvalue()
    if rec.get("is_test"):
        import opis as OPIS
        pdf = OPIS.mark_test(pdf)
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": S.disp("inline", f"PV_PIF_{(client.get('name') or 'dosar').replace(' ', '_')}.pdf")})
