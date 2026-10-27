import io
import os
from html import escape

from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors

import docgen as D

AS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
S, M = D.S, D.M
GREY = colors.HexColor("#bfbfbf")
CATS = {"panouri": "Panouri fotovoltaice", "invertor": "Invertoare", "baterii": "Baterii", "structura": "Structură montaj",
        "pasive": "Echipamente pasive, de protecție și de comunicație", "contor": "Contoare inteligente și comunicație", "montaj": "Montaj",
        "ac": "Legături curent alternativ", "racordare": "Lucrări de racordare la rețea și punere în funcțiune", "probe": "Probe, măsurători și PIF",
        "proiectare": "Proiectare și asistență tehnică", "dosar": "Dosar de prosumator / racordare", "transport": "Transport", "mentenanta": "Mentenanță",
        "altele": "Alte servicii"}
EQUIP = {"panouri", "invertor", "baterii", "structura", "pasive", "contor"}


def e(v):
    return escape(str(v)) if v not in (None, "") else M


def num(v, d=0.0):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return d


def money(v, cur=""):
    s = f"{v:,.2f}".replace(",", " ").replace(".", ",")
    return f"{s} {'€' if cur == 'EUR' else 'lei' if cur == 'RON' else cur}".strip()


def calc(o: dict) -> dict:
    r = num(o.get("vat_rate"), 21) / 100
    gross_in = bool(o.get("prices_include_vat"))
    lines, eq, sv = [], 0.0, 0.0
    for it in o.get("items") or []:
        v = round(num(it.get("qty")) * num(it.get("unit_price")), 2)
        net = round(v / (1 + r), 2) if gross_in else v
        lines.append(net)
        if it.get("category") in EQUIP or it.get("kind") == "echipament":
            eq += net
        else:
            sv += net
    sub = round(eq + sv, 2)
    d = o.get("discount") or {}
    disc = round(sub * num(d.get("value")) / 100, 2) if d.get("type") == "percent" else round(min(num(d.get("value")), sub), 2)
    net = round(sub - disc, 2)
    vat = round(net * r, 2)
    out = {"equipment": round(eq, 2), "services": round(sv, 2), "subtotal": sub, "discount": disc, "net": net, "vat": vat, "gross": round(net + vat, 2),
           "vat_rate": round(r * 100, 2), "currency": o.get("currency") or "RON", "lines": lines}
    fx = num(o.get("exchange_rate"))
    if out["currency"] == "EUR" and fx > 0:
        out["ron"] = {k: round(out[k] * fx, 2) for k in ("net", "vat", "gross")}
    return out


def _page(c, doc):
    w, h = A4
    c.drawImage(os.path.join(AS, "offer_header.png"), 0, h - 74, width=w, height=74, mask="auto")
    c.drawImage(os.path.join(AS, "offer_footer.png"), 0, 0, width=w, height=58, mask="auto")
    c.setFont("LS", 7); c.drawRightString(w - 16 * mm, 60, f"Pagina {doc.page}")


def build(story, title):
    buf = io.BytesIO()
    pw, ph = A4
    pt = PageTemplate("p", [Frame(16 * mm, 64, pw - 32 * mm, ph - 64 - 82, id="f")], onPage=_page)
    BaseDocTemplate(buf, pageTemplates=[pt], title=title).build(story)
    return buf.getvalue()


def grid(rows, widths, head=True, fs=8.2):
    st = [("GRID", (0, 0), (-1, -1), 0.5, colors.black), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("FONTSIZE", (0, 0), (-1, -1), fs)]
    if head:
        st.append(("BACKGROUND", (0, 0), (-1, 0), GREY))
    t = Table([[Paragraph(str(c), S["cellb" if head and i == 0 else "cell"]) for c in r] for i, r in enumerate(rows)], colWidths=[w * mm for w in widths], repeatRows=1 if head else 0)
    t.setStyle(TableStyle(st))
    return t


def ben_lines(b):
    pj = b.get("kind") == "PJ"
    return [f"Beneficiar: <b>{e(b.get('name'))}</b>", f"CUI/CNP: {e(b.get('cui_cnp'))}",
            f"NR REG/SERIE CI: {e(b.get('reg_com') if pj else ' '.join(x for x in (b.get('ci_series'), b.get('ci_number')) if x))}",
            f"Locație: {e(b.get('install_address') or b.get('address'))}"]


def company_block(s):
    return "<br/>".join(x for x in [f"<b>{e(s.get('company'))}</b>", e(s.get("cui")), e(s.get("regcom")), e(s.get("address"))] if x)


def item_desc(it):
    bits = [x for x in (it.get("manufacturer"), it.get("model")) if x]
    spec = [x for x in (f"{it['power']}" if it.get("power") else "", f"{it['capacity']}" if it.get("capacity") else "") if x]
    head = " ".join(bits + spec)
    lines = [f"<b>{escape(head)}</b>"] if head else []
    lines += [f"• {escape(x.strip())}" for x in str(it.get("description") or "").split("\n") if x.strip()]
    if it.get("warranty"):
        lines.append(f"Garanție: {escape(str(it['warranty']))}")
    return "<br/>".join(lines) or escape(it.get("name") or "")


def offer_pdf(o: dict, s: dict) -> bytes:
    t = calc(o)
    cur = t["currency"]
    b = o.get("beneficiary") or {}
    left = Paragraph("<br/>".join(ben_lines(b)), S["p"])
    right = Paragraph(f"<b>NR REG: {e(o.get('number'))}</b><br/>Data: {e(D.ro_date(o.get('date')))}<br/><br/>{company_block(s)}", S["p"])
    hd = Table([[left, right]], colWidths=[100 * mm, 78 * mm]); hd.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story = [Paragraph(f"OFERTĂ DE PREȚ NR. {e(o.get('number'))}", S["h"]), hd, Spacer(1, 8),
             Paragraph(f"<b>{e(o.get('title') or (o.get('system') or {}).get('title'))}</b>", S["c"]), Spacer(1, 6)]
    rows = [["Nr.", "Nume", "Descriere", "Cant.", "UM", "Preț unitar", "Valoare"]]
    show_prices = o.get("show_line_prices", True)
    for i, it in enumerate(o.get("items") or []):
        r = [str(i + 1), f"<b>{escape(it.get('name') or CATS.get(it.get('category'), ''))}</b>", item_desc(it), e(it.get("qty")), e(it.get("unit"))]
        r += [money(num(it.get("unit_price")), cur), money(num(it.get("qty")) * num(it.get("unit_price")), cur)] if show_prices else ["", ""]
        rows.append(r)
    w = [9, 34, 72, 13, 11, 20, 21] if show_prices else [9, 40, 107, 13, 11, 0.1, 0.1]
    story += [Paragraph("<b>Descrierea sistemului fotovoltaic propus:</b>", S["c"]),
              Paragraph(escape((o.get("system") or {}).get("description") or ""), S["p"]), grid(rows, w), Spacer(1, 6)]
    vat_lbl = "TVA inclus în prețurile unitare" if o.get("prices_include_vat") else "prețuri unitare fără TVA"
    tot = [["Valoare echipamente", money(t["equipment"], cur)], ["Valoare manoperă și servicii", money(t["services"], cur)], ["Subtotal", money(t["subtotal"], cur)]]
    if t["discount"]:
        tot.append(["Reducere", "− " + money(t["discount"], cur)])
    tot += [[f"<b>Preț total {'euro' if cur == 'EUR' else 'lei'} fără TVA</b>", f"<b>{money(t['net'], cur)}</b>"], [f"TVA {t['vat_rate']:g}%", money(t["vat"], cur)],
            [f"<b>Total cu TVA</b>", f"<b>{money(t['gross'], cur)}</b>"]]
    if t.get("ron"):
        tot.append([f"Echivalent RON (curs {e(o.get('exchange_rate'))} lei/€) — total cu TVA", money(t["ron"]["gross"], "RON")])
    tt = grid(tot, [120, 58], head=False, fs=9); tt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#d9d9d9"))]))
    story += [KeepTogether([tt]), Paragraph(f"<i>Calcul: {vat_lbl}; TVA aplicat o singură dată pe totalul net.</i>", S["small"]), Spacer(1, 8)]
    for title, key in (("Prețul include:", "includes"), ("Garanții:", "warranties"), ("Observații comerciale:", "commercial_notes")):
        lines = [x.strip() for x in str(o.get(key) or "").split("\n") if x.strip()]
        if lines:
            story += [Paragraph(f"<b>{title}</b>", S["p"])] + [Paragraph(f"{i + 1}. {escape(x)}", S["li"]) for i, x in enumerate(lines)]
    if o.get("validity_days"):
        story.append(Paragraph(f"Prezenta ofertă este valabilă: <b>{e(o.get('validity_days'))} zile</b>", S["p"]))
    if (o.get("maintenance") or "").strip():
        story += [PageBreak(), Paragraph("<b>Mentenanță (opțional)</b>", S["h"])] + [Paragraph(escape(x), S["p"]) for x in o["maintenance"].split("\n") if x.strip()]
    story.append(D.pdf_sign(["Ofertant,", f"<b>{e(s.get('company'))}</b>", e(s.get("rep")), "semnătura și ștampila"],
                            ["Beneficiar (de acord cu oferta),", f"<b>{e(b.get('name'))}</b>", "semnătura"], {}))
    return build(story, f"Oferta de pret nr. {o.get('number')}")


def party_line(b):
    pj = b.get("kind") == "PJ"
    if pj:
        return (f"<b>{e(b.get('name'))}</b>, cu sediul în {e(b.get('address'))}, CUI {e(b.get('cui_cnp'))}, Reg. Comerțului {e(b.get('reg_com'))}, "
                f"numit în continuare <b>BENEFICIAR</b>, reprezentat prin {e(b.get('rep_role') or 'administrator')} <b>{e(b.get('rep_name'))}</b>")
    return (f"<b>{e(b.get('name'))}</b>, domiciliat în {e(b.get('address'))}, CNP {e(b.get('cui_cnp'))}, act de identitate seria {e(b.get('ci_series'))} "
            f"nr. {e(b.get('ci_number'))}, numit în continuare <b>BENEFICIAR</b>")


def contract_pdf(c: dict, s: dict) -> bytes:
    o, t, b = c["offer"], c["totals"], c["offer"].get("beneficiary") or {}
    cur = t["currency"]
    no, dt = c["number"], D.ro_date(c["date"])
    story = [Paragraph("CONTRACT DE PRESTĂRI SERVICII ȘI FURNIZARE DE PRODUSE", S["h"]), Paragraph(f"<b>NR. {no} / {dt}</b>", S["c"]), Spacer(1, 6)]
    for art in c["articles"]:
        story.append(Paragraph(f"<b>{escape(art['title'])}</b>", S["b"]))
        for para in art["text"].split("\n"):
            if para.strip():
                story.append(Paragraph(para.strip(), S["p"]))
    story.append(D.pdf_sign([f"BENEFICIAR,", f"<b>{e(b.get('name'))}</b>", "Semnătura/Ștampila"], ["PRESTATOR,", f"<b>{e(s.get('company'))}</b>", e(s.get("rep")), "Semnătura și ștampila"], {}))
    story += [PageBreak(), Paragraph("<b>Anexa 1 – Oferta Comercială</b>", S["p"]),
              Paragraph(f"<b>CONTRACT DE PRESTĂRI SERVICII ȘI FURNIZARE DE PRODUSE NR. {no} din {dt}</b>", S["c"]),
              Paragraph(f"C1 – <b>{e(b.get('name'))}</b> · Ofertă de preț nr. {e(o.get('number'))}", S["p"]),
              Paragraph(f"* Locul de implementare a instalațiilor este <b>{e(b.get('install_address') or b.get('address'))}</b>:", S["p"])]
    rows = [["Nr. crt", "PN / Producător", "Descriere", "Cant.", "UM", "Preț unitar", "Valoare"]]
    for i, it in enumerate(o.get("items") or []):
        rows.append([str(i + 1), escape(it.get("manufacturer") or it.get("name") or ""), escape(" ".join(x for x in (it.get("name"), it.get("model"), it.get("power"), it.get("capacity")) if x)),
                     e(it.get("qty")), e(it.get("unit")), money(num(it.get("unit_price")), cur), money(num(it.get("qty")) * num(it.get("unit_price")), cur)])
    rows += [["", "", f"<b>{escape(o.get('title') or '')}</b> — Subtotal fără TVA" + (f" (după reducere {money(t['discount'], cur)})" if t["discount"] else ""), "", "", "", f"<b>{money(t['net'], cur)}</b>"],
             ["", "", f"TVA {t['vat_rate']:g}%", "", "", "", money(t["vat"], cur)], ["", "", "<b>Total cu TVA</b>", "", "", "", f"<b>{money(t['gross'], cur)}</b>"]]
    story += [grid(rows, [12, 30, 62, 12, 10, 26, 26]), Spacer(1, 6),
              D.pdf_sign(["PRESTATOR,", f"<b>{e(s.get('company'))}</b>", "Semnătură și ștampilă"], ["BENEFICIAR,", f"<b>{e(b.get('name'))}</b>", "Semnătură/Ștampilă"], {})]
    story += [PageBreak(), Paragraph("<b>Anexa 2 – Garanții</b>", S["p"]),
              Paragraph(f"<b>CONTRACT DE PRESTĂRI SERVICII ȘI FURNIZARE DE PRODUSE NR. {no} din {dt}</b>", S["c"]), Paragraph(f"C1 – <b>{e(b.get('name'))}</b>", S["p"])]
    wr = [["Nr. crt", "Echipament / lucrare", "Producător / model", "Perioada de garanție"]]
    for i, it in enumerate([x for x in o.get("items") or [] if x.get("category") in EQUIP or x.get("kind") == "echipament"]):
        wr.append([str(i + 1), escape(it.get("name") or ""), escape(" ".join(x for x in (it.get("manufacturer"), it.get("model")) if x)), e(it.get("warranty"))])
    wr.append([str(len(wr)), "Manoperă și montaj", "—", f"{e(c.get('works_warranty_months'))} luni de la semnarea procesului-verbal de terminare a lucrărilor"])
    story += [grid(wr, [12, 55, 55, 56]), Spacer(1, 4),
              Paragraph("Garanția echipamentelor este cea prevăzută în certificatele de garanție emise de producători, care însoțesc echipamentele. "
                        "Perioada de garanție începe de la data recepției / punerii în funcțiune a sistemului (art. IX).", S["small"]),
              D.pdf_sign(["PRESTATOR,", f"<b>{e(s.get('company'))}</b>", "Semnătură și ștampilă"], ["BENEFICIAR,", f"<b>{e(b.get('name'))}</b>", "Semnătură/Ștampilă"], {})]
    return build(story, f"Contract nr. {no}")
