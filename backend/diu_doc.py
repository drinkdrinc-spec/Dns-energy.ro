import io
from html import escape

from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, PageBreak, Paragraph, NextPageTemplate
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors

import docgen as D
from docgen import B, M, ro_date, hdr, sign, ex_sig, ben_sig

DOCS = [("opis", "Opis documente — dosar instalație de utilizare"), ("memoriu", "Memoriu tehnic"), ("schema_tg", "Schemă monofilară tablou general (TG)"),
        ("pram_priza", "Buletin PRAM — rezistența de dispersie a prizei de pământ"), ("pram_cont", "Buletin PRAM — continuitatea conductoarelor de protecție"),
        ("pram_izol", "Buletin PRAM — rezistența de izolație"), ("pram_ddr", "Buletin PRAM — verificarea dispozitivelor diferențiale (DDR)"),
        ("receptie", "Proces-verbal de recepție la terminarea lucrărilor"), ("pif", "Proces-verbal de punere în funcțiune"),
        ("conformitate", "Declarație de conformitate a executantului"), ("garantie", "Certificat de garanție")]
TITLES = dict(DOCS)
RISO_MIN, DDR_MAX_MS = 1.0, 300.0


def num(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def e(v):
    return escape(str(v)) if v not in (None, "") else M


def circuits(r):
    return [c for c in r.get("circuits") or [] if isinstance(c, dict) and c.get("name")]


def missing(key, r, s):
    p = r.get("pram_m") or {}
    cs = circuits(r)
    need = lambda pairs: [lbl for val, lbl in pairs if val in (None, "")]
    m = []
    if key == "memoriu":
        m = need([(r.get("type"), "Tip instalație"), (r.get("power"), "Putere instalată"), (r.get("supply"), "Tip alimentare (mono/trifazat)")])
    elif key == "schema_tg":
        m = need([(r.get("tg_breaker_a"), "Întreruptor general TG (A)")]) + ([] if cs else ["Circuitele tabloului"])
        m += [f"Circuit „{c['name']}”: întreruptor / secțiune cablu" for c in cs if not c.get("breaker_a") or not c.get("section")]
    elif key.startswith("pram_"):
        m = need([(p.get("date"), "Data măsurătorilor"), (p.get("instrument"), "Aparat de măsură (tip, serie)"), (p.get("verifier"), "Verificator PRAM")])
        if key == "pram_priza":
            m += need([(p.get("earth_ohm"), "Rezistența de dispersie măsurată (Ω)"), (p.get("earth_limit"), "Valoarea admisă (Ω)")])
        if key == "pram_cont":
            m += ([] if cs else ["Circuitele tabloului"]) + [f"Continuitate PE — {c['name']}" for c in cs if c.get("r_pe") in (None, "")]
        if key == "pram_izol":
            m += need([(p.get("test_v"), "Tensiune de încercare (V)")]) + ([] if cs else ["Circuitele tabloului"]) + [f"Rezistență izolație — {c['name']}" for c in cs if c.get("riso") in (None, "")]
        if key == "pram_ddr":
            dd = [c for c in cs if c.get("rcd_ma")]
            m += ([] if dd else ["Niciun circuit cu DDR definit"]) + [f"Timp declanșare DDR — {c['name']}" for c in dd if c.get("rcd_t") in (None, "")]
    elif key == "receptie":
        m = need([(r.get("receptie_date"), "Data recepției"), (r.get("receptie_decision"), "Hotărâre recepție")])
    elif key == "pif":
        m = need([(r.get("pif_date"), "Data punerii în funcțiune"), (r.get("pif_decision"), "Hotărâre PIF")])
    elif key == "conformitate":
        m = need([(r.get("date") or r.get("doc_date"), "Data finalizării")])
    elif key == "garantie":
        m = need([(r.get("warranty_months") or s.get("warranty_months"), "Durata garanției (luni)"), (r.get("warranty_start") or r.get("receptie_date"), "Data începerii garanției")])
    if key != "opis":
        m = need([(r.get("client_name") or r.get("name"), "Beneficiar"), (r.get("address"), "Adresă obiectiv")]) + \
            need([(s.get("company"), "Denumire executant"), (s.get("anre_attest"), "Atestat ANRE executant"), (s.get("rep"), "Reprezentant executant")]) + m
    return list(dict.fromkeys(m))


def positions(r, s):
    out = []
    for i, (k, t) in enumerate(DOCS):
        m = missing(k, r, s)
        out.append({"nr": i + 1, "key": k, "title": t, "missing": m, "status": "de completat" if m else "generat"})
    return out


def pram_head(ctx, r, title, norm):
    p = r.get("pram_m") or {}
    return hdr() + [B("title", title), B("sub", norm),
                    B("p", f"Beneficiar: <b>{ctx.name}</b> · Obiectiv: {ctx.loc} · Dosar DI-U: {e(r.get('number'))}"),
                    B("p", f"Data măsurătorilor: {ro_date(p.get('date')) or M} · Aparat de măsură: {e(p.get('instrument'))} · Verificator: {e(p.get('verifier'))}")]


def pram_sign(ctx, r):
    return sign(["Verificator PRAM,", e((r.get("pram_m") or {}).get("verifier")), "numele și semnătura"], ex_sig(ctx))


def verdict(ok):
    return "—" if ok is None else ("Corespunde" if ok else "NU corespunde")


def doc_opis(ctx, r, pos):
    rows = [["Nr.", "Document", "Stare"]] + [[str(p["nr"]), p["title"], "inclus" if not p["missing"] else "de completat"] for p in pos if p["key"] != "opis"]
    return hdr() + [B("title", "OPIS"), B("sub", "Dosarul instalației de utilizare (DI-U)"),
                    B("p", f"Beneficiar: <b>{ctx.name}</b> · Obiectiv: {ctx.loc} · Nr. dosar: {e(r.get('number'))} · Data: {ctx.date}"),
                    B("table", rows, [8, 70, 22], True),
                    B("p", "Executantul declară că documentele de mai sus aparțin instalației de utilizare descrise și reflectă situația reală de la data întocmirii."),
                    sign(ex_sig(ctx), ben_sig(ctx))]


def doc_memoriu(ctx, r, pos):
    cs = circuits(r)
    out = hdr() + [B("title", "MEMORIU TEHNIC"), B("sub", "privind instalația electrică de utilizare"),
                   B("b", "1. Date generale"),
                   B("p", f"Beneficiar: <b>{ctx.name}</b>; amplasament: {ctx.loc}; operator de distribuție: {ctx.v('operator')}; ATR / soluție de racordare: {ctx.v('atr')}."),
                   B("p", f"Executant: <b>{ctx.company}</b>, atestat ANRE {ctx.e('anre_attest')}, reprezentat prin {ctx.rep}."),
                   B("b", "2. Obiectul lucrării"),
                   B("p", f"Tip instalație: {ctx.v('type')}; putere instalată: {ctx.v('power')} kW; alimentare: {ctx.v('supply')}; "
                          f"sistem de legare la pământ: {ctx.v('earthing')}; întreruptor BMP: {ctx.v('bmp_a')} A; întreruptor general TG: {ctx.v('tg_breaker_a')} A."),
                   B("b", "3. Descrierea instalației"),
                   B("bullets", [escape(x.strip()) for x in str(r.get("memoriu_desc") or "").split("\n") if x.strip()] or [M], False)]
    if (r.get("cef") or {}).get("inverters") or r.get("inverter"):
        out += [B("b", "4. Echipamente principale"), B("table", D.equipment_lines(ctx), [60, 24, 90], True)]
    out += [B("b", "5. Circuitele tabloului general"),
            B("table", [["Nr.", "Circuit", "Protecție", "Cablu"]] + [[str(i + 1), escape(c["name"]), f"{e(c.get('curve'))}{e(c.get('breaker_a'))} A" + (f" + DDR {e(c.get('rcd_ma'))} mA tip {e(str(c.get('rcd_type') or '').replace('Tip', '').strip())}" if c.get("rcd_ma") else ""),
                                                                    f"{e(c.get('cable'))} {e(c.get('section'))} mm², L={e(c.get('length'))} m"] for i, c in enumerate(cs)] or [["—", M, M, M]], [6, 40, 30, 30], True),
            B("b", "6. Măsuri de protecție"),
            B("bullets", ["Protecția la suprasarcină și scurtcircuit se realizează cu întreruptoarele automate indicate în schema monofilară a tabloului.",
                          "Protecția împotriva șocurilor electrice prin atingere indirectă: dispozitive diferențiale (DDR) pe circuitele indicate și legare la pământ "
                          f"(sistem {ctx.v('earthing')}), valorile măsurate fiind consemnate în buletinele PRAM anexate.",
                          "Verificările la punerea în funcțiune s-au efectuat conform HD 60364-6 și normativului I7/2011; rezultatele sunt cele din buletinele PRAM."]),
            B("b", "7. Normative aplicate"),
            B("bullets", ["Normativ I7/2011 — proiectarea, execuția și exploatarea instalațiilor electrice aferente clădirilor", "SR HD 60364 — instalații electrice de joasă tensiune",
                          "SR EN IEC 62446-1 — sisteme fotovoltaice (dacă este cazul)", "Regulamentul ANRE privind racordarea utilizatorilor la rețelele electrice de interes public"]),
            sign(ex_sig(ctx, "Întocmit — executant,"), ben_sig(ctx))]
    return out


def tg_drawing(r):
    cs = circuits(r)
    W, H = 273 * mm, 150 * mm
    d = Drawing(W, H)
    t = lambda x, y, s, fs=7, a="middle", b=False: d.add(String(x, y, s, fontName="LSB" if b else "LS", fontSize=fs, textAnchor=a))
    ln = lambda x1, y1, x2, y2, w=1: d.add(Line(x1, y1, x2, y2, strokeWidth=w))
    box = lambda x, y, w, h: d.add(Rect(x, y, w, h, fillColor=None, strokeWidth=0.9))
    x0 = 22 * mm
    t(x0, H - 8, "Rețea OD 0,4 kV", 7.5, b=True); ln(x0, H - 12, x0, H - 22)
    box(x0 - 14, H - 40, 28, 18); t(x0, H - 31, "BMP", 7, b=True); t(x0, H - 38, f"{r.get('bmp_a') or '…'} A", 6.5)
    ln(x0, H - 40, x0, H - 62)
    t(x0 + 4, H - 52, f"Coloană {r.get('column_cable') or ''}".strip(), 6, "start")
    box(x0 - 18, H - 80, 36, 18); t(x0, H - 71, "Q0 — TG", 7, b=True); t(x0, H - 78, f"{r.get('tg_breaker_a') or '…'} A", 6.5)
    ln(x0, H - 80, x0, H - 92)
    bus_y = H - 92
    n = max(len(cs), 1)
    sp = min(32 * mm, (W - x0 - 30 * mm) / n)
    xs = [x0 + 26 * mm + i * sp for i in range(n)]
    ln(x0, bus_y, xs[-1] + 4, bus_y, 2.2)
    t(x0 - 6, bus_y - 10, f"PE / {r.get('earthing') or 'sistem …'}", 6, "start")
    for i, c in enumerate(cs):
        x = xs[i]
        ln(x, bus_y, x, bus_y - 14)
        box(x - 13, bus_y - 32, 26, 18); t(x, bus_y - 22, f"Q{i + 1}", 6.5, b=True); t(x, bus_y - 29, f"{c.get('curve') or ''}{c.get('breaker_a') or '…'} A", 6)
        y = bus_y - 32
        if c.get("rcd_ma"):
            ln(x, y, x, y - 8); box(x - 15, y - 24, 30, 16); t(x, y - 15, "DDR", 6, b=True); t(x, y - 22, f"{c['rcd_ma']} mA {c.get('rcd_type') or ''}", 5.5)
            y -= 24
        ye = y - 60
        ln(x, y, x, ye)
        t(x + 2, y - 14, f"{c.get('cable') or ''} {c.get('section') or '…'} mm²", 5.5, "start")
        t(x + 2, y - 22, f"L = {c.get('length') or '…'} m", 5.5, "start")
        t(x, ye - 10, c["name"][:22], 6, b=True)
        t(x, ye - 18, c["name"][22:44], 6)
    if not cs:
        t(xs[0], bus_y - 30, "circuite nedefinite", 7)
    return d


def doc_schema(ctx, r, pos):
    return [("flow", Paragraph("SCHEMĂ MONOFILARĂ — TABLOU GENERAL (TG)", D.S["h"])),
            ("flow", Paragraph(f"Beneficiar: <b>{ctx.name}</b> · Obiectiv: {ctx.loc} · Alimentare: {ctx.v('supply')} · Executant: {ctx.company} (atestat ANRE {ctx.e('anre_attest')})", D.S["sub"])),
            ("flow", tg_drawing(r)),
            ("flow", Paragraph("Valorile din schemă sunt cele introduse în dosar; elementele marcate „…” sunt de completat. Schema se verifică și se semnează de electricianul autorizat.", D.S["small"]))]


def doc_priza(ctx, r, pos):
    p = r.get("pram_m") or {}
    v, lim = num(p.get("earth_ohm")), num(p.get("earth_limit"))
    ok = None if v is None or lim is None else v <= lim
    return pram_head(ctx, r, "BULETIN DE VERIFICARE A PRIZEI DE PĂMÂNT", "măsurarea rezistenței de dispersie (I7/2011, SR HD 60364-6)") + [
        B("table", [["Priza de pământ", "Starea solului", "Valoare măsurată (Ω)", "Valoare admisă (Ω)", "Rezultat"],
                    [f"Priză {ctx.v('earthing')}", e(p.get("soil")), e(p.get("earth_ohm")), e(p.get("earth_limit")), verdict(ok)]], [26, 18, 18, 18, 20], True),
        B("p", "Valoarea admisă este cea stabilită de proiectant/verificator pentru sistemul de legare la pământ al instalației."), pram_sign(ctx, r)]


def doc_cont(ctx, r, pos):
    rows = [["Nr.", "Circuit", "Conductor PE (mm²)", "Rezistență continuitate măsurată (Ω)", "Rezultat"]]
    rows += [[str(i + 1), escape(c["name"]), e(c.get("section")), e(c.get("r_pe")), "—" if c.get("r_pe") in (None, "") else "Continuitate asigurată"] for i, c in enumerate(circuits(r))] or [["—", M, M, M, "—"]]
    return pram_head(ctx, r, "BULETIN DE VERIFICARE A CONTINUITĂȚII CONDUCTOARELOR DE PROTECȚIE", "SR HD 60364-6, art. 6.4.3.2") + [B("table", rows, [6, 36, 16, 24, 18], True), pram_sign(ctx, r)]


def doc_izol(ctx, r, pos):
    p = r.get("pram_m") or {}
    rows = [["Nr.", "Circuit", "Tensiune încercare (V)", "Riso măsurată (MΩ)", "Valoare minimă (MΩ)", "Rezultat"]]
    for i, c in enumerate(circuits(r)):
        v = num(c.get("riso"))
        rows.append([str(i + 1), escape(c["name"]), e(p.get("test_v")), e(c.get("riso")), f"{RISO_MIN:g}", verdict(None if v is None else v >= RISO_MIN)])
    if len(rows) == 1:
        rows.append(["—", M, M, M, f"{RISO_MIN:g}", "—"])
    return pram_head(ctx, r, "BULETIN DE MĂSURARE A REZISTENȚEI DE IZOLAȚIE", "SR HD 60364-6, art. 6.4.3.3 (circuite ≤ 500 V: încercare 500 V c.c., minimum 1 MΩ)") + [
        B("table", rows, [6, 34, 14, 15, 13, 18], True), pram_sign(ctx, r)]


def doc_ddr(ctx, r, pos):
    rows = [["Nr.", "Circuit", "DDR (IΔn, tip)", "Curent declanșare măsurat (mA)", "Timp declanșare la IΔn (ms)", "Rezultat"]]
    for i, c in enumerate([c for c in circuits(r) if c.get("rcd_ma")]):
        tm = num(c.get("rcd_t"))
        rows.append([str(i + 1), escape(c["name"]), f"{e(c.get('rcd_ma'))} mA tip {e(str(c.get('rcd_type') or '').replace('Tip', '').strip())}", e(c.get("rcd_i")), e(c.get("rcd_t")), verdict(None if tm is None else tm <= DDR_MAX_MS)])
    if len(rows) == 1:
        rows.append(["—", "niciun circuit cu DDR", M, M, M, "—"])
    return pram_head(ctx, r, "BULETIN DE VERIFICARE A DISPOZITIVELOR DIFERENȚIALE (DDR)", f"SR HD 60364-6, art. 6.4.3.7 (timp maxim la IΔn: {DDR_MAX_MS:g} ms, DDR general)") + [
        B("table", rows, [6, 30, 18, 16, 16, 14], True), pram_sign(ctx, r)]


def doc_garantie(ctx, r, pos):
    months = r.get("warranty_months") or ctx.s.get("warranty_months")
    start = ro_date(r.get("warranty_start") or r.get("receptie_date"))
    return hdr() + [B("title", "CERTIFICAT DE GARANȚIE"), B("sub", f"pentru lucrările de execuție a instalației electrice de utilizare — dosar {e(r.get('number'))}"),
                    B("p", f"<b>{ctx.company}</b>, atestat ANRE {ctx.e('anre_attest')}, garantează beneficiarului <b>{ctx.name}</b> lucrările executate la adresa {ctx.loc} "
                           f"pe o perioadă de <b>{e(months)} luni</b>, începând cu data de <b>{start or M}</b> (data recepției la terminarea lucrărilor)."),
                    B("b", "Condiții de garanție"),
                    B("bullets", ["Garanția acoperă defectele de execuție și montaj constatate în perioada de garanție, remediate gratuit de executant.",
                                  "Echipamentele (invertoare, panouri, baterii, aparataj) beneficiază de garanția producătorului, conform documentelor acestora.",
                                  "Garanția nu acoperă intervenții ale terților, modificări ale instalației, utilizare necorespunzătoare, supratensiuni atmosferice sau forță majoră.",
                                  "Defectele se notifică executantului în scris, la datele de contact de mai sus."]),
                    sign(ex_sig(ctx), ben_sig(ctx))]


def generic(fn):
    return lambda ctx, r, pos: fn(ctx)


RENDER = {"opis": doc_opis, "memoriu": doc_memoriu, "schema_tg": doc_schema, "pram_priza": doc_priza, "pram_cont": doc_cont, "pram_izol": doc_izol,
          "pram_ddr": doc_ddr, "receptie": generic(D.doc_pv_receptie), "pif": generic(D.doc_pv_pif), "conformitate": generic(D.doc_decl_conformitate), "garantie": doc_garantie}


def render(keys, r, s, client):
    ctx = D.Ctx(r, s, client, [t for k, t in DOCS])
    pos = positions(r, s)
    buf = io.BytesIO()
    pw, ph = A4
    port = PageTemplate("port", [Frame(18 * mm, 14 * mm, pw - 36 * mm, ph - 28 * mm, id="fp")], pagesize=A4)
    land = PageTemplate("land", [Frame(12 * mm, 10 * mm, ph - 24 * mm, pw - 20 * mm, id="fl")], pagesize=landscape(A4))
    first_land = keys[0] == "schema_tg"
    pdf = BaseDocTemplate(buf, pageTemplates=[land, port] if first_land else [port, land], title=f"DI-U — {ctx.raw('name') or ''}")
    story = []
    for i, k in enumerate(keys):
        blocks = RENDER[k](ctx, r, pos)
        if k == "schema_tg":
            if i:
                story += [NextPageTemplate("land"), PageBreak()]
            story += [b[1] for b in blocks] + [NextPageTemplate("port")]
            continue
        if i:
            story.append(PageBreak())
        story += D.to_flow(blocks, ctx)
    pdf.build(story)
    return buf.getvalue()


_ = colors
