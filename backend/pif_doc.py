import hashlib
import io
import json
from html import escape

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm

import docgen as D
import cef as CEF

TITLE = "Proces-verbal PIF — teste și verificări (măsurători)"
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


def fingerprint(rec: dict) -> str:
    p = {k: v for k, v in (rec.get("pif") or {}).items() if k not in ("updated_at", "updated_by")}
    return hashlib.sha256(json.dumps(p, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def filled(rec: dict) -> bool:
    p = rec.get("pif") or {}
    vals = [v for grp in ("strings", "inv") for row in (p.get(grp) or {}).values() for v in row.values()]
    return bool(p.get("date")) and (any(vals) or any((p.get("checks") or {}).values()) or bool(p.get("grounding_measured")))


def render(rec: dict, client: dict, s: dict) -> bytes:
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
              Spacer(1, 4), P("3. Serii echipamente identificate la punerea în funcțiune", "b")]
    serials = p.get("serials") or {}
    serial_rows = [["Echipament", "Model", "Serie"]]
    cef = rec.get("cef") or {}
    for i, inv in enumerate(cef.get("inverters") or []):
        count = max(1, min(100, int(CEF.n(inv.get("count") or inv.get("quantity"), 1) or 1)))
        for unit in range(count):
            key = f"{i}.{unit}"
            label = f"Invertor {i + 1}" + (f" — unitatea {unit + 1}" if count > 1 else "")
            serial_rows.append([label, e(inv.get("brand_model")) or M, e((serials.get("inverters") or {}).get(key)) or "Neînregistrată"])
    battery_items = []
    for i, inv in enumerate(cef.get("inverters") or []):
        battery = inv.get("battery") or {}
        if inv.get("battery_mode") == "own" and battery.get("model"):
            count = max(1, min(100, int(CEF.n(battery.get("modules") or battery.get("count"), 1) or 1)))
            battery_items.extend((f"inv-{i}-{unit}", f"Baterie invertor {i + 1}" + (f" — modulul {unit + 1}" if count > 1 else ""), battery.get("model")) for unit in range(count))
    for i, battery in enumerate(cef.get("shared_batteries") or []):
        count = max(1, min(100, int(CEF.n(battery.get("modules") or battery.get("count"), 1) or 1)))
        battery_items.extend((f"shared-{i}-{unit}", f"Baterie {i + 1}" + (f" — modulul {unit + 1}" if count > 1 else ""), battery.get("model")) for unit in range(count))
    for key, label, model in battery_items:
        serial_rows.append([label, e(model) or M, e((serials.get("batteries") or {}).get(key)) or "Neînregistrată"])
    panel_serials = serials.get("panels") or []
    if isinstance(panel_serials, str):
        panel_serials = panel_serials.splitlines()
    panel_serials = [str(value).strip() for value in panel_serials if str(value).strip()]
    panel_count = CEF.check(cef).get("totals", {}).get("panels") or rec.get("panel_count") or 0
    panel_models = sorted({str(inv.get("panel_model")) for inv in cef.get("inverters") or [] if inv.get("panel_model")})
    panel_model = ", ".join(panel_models) or M
    if panel_serials:
        serial_rows.extend([[f"Panou {index + 1}", panel_model, e(value)] for index, value in enumerate(panel_serials)])
    elif panel_count:
        serial_rows.append([f"Panouri ({panel_count} configurate)", panel_model, "Neînregistrate"])
    if len(serial_rows) == 1:
        serial_rows.append(["—", "Nu sunt echipamente declarate", ""])
    story += [T(serial_rows, [30, 48, 34]), Spacer(1, 4), P("Seriile se completează după citirea etichetelor echipamentelor. Lipsa unei serii nu reprezintă o măsurătoare și nu confirmă conformitatea.", "small"),
              Spacer(1, 4), P("4. Verificări vizuale și funcționale", "b"),
              T([["Nr.", "Verificare", "Rezultat"]] + [[str(k + 1), c, e((p.get("checks") or {}).get(str(k)))] for k, c in enumerate(CHECKS)], [6, 74, 20])]
    if p.get("notes"):
        story.append(P(f"Observații: {e(p['notes'])}"))
    story += [Spacer(1, 4), P("Rezultatele de mai sus sunt cele măsurate efectiv la data testelor; câmpurile necompletate nu au fost măsurate și nu constituie confirmare de conformitate.", "small"),
              D.pdf_sign(["Reprezentantul firmei executante (electrician autorizat ANRE),", f"<b>{e(s.get('company'))}</b>", e(p.get("operator") or s.get("rep")) or M, "(numele, prenumele și semnătura)", "(ștampilă)"], [], s)]
    doc.build(story)
    return buf.getvalue()
