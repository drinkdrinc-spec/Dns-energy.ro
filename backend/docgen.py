import io
import math
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, NextPageTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable
from reportlab.lib.pagesizes import landscape
import cef as CEF
import schema_cef
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FD = "/usr/share/fonts/truetype/liberation/"
pdfmetrics.registerFont(TTFont("LS", FD + "LiberationSans-Regular.ttf"))
pdfmetrics.registerFont(TTFont("LSB", FD + "LiberationSans-Bold.ttf"))

NAVY = colors.HexColor("#0b1f3a")
BLUE = colors.HexColor("#2878f0")
S = {
    "h": ParagraphStyle("h", fontName="LSB", fontSize=13, leading=17, alignment=TA_CENTER, spaceAfter=4, textColor=NAVY),
    "sub": ParagraphStyle("sub", fontName="LS", fontSize=9, leading=12, alignment=TA_CENTER, textColor=colors.HexColor("#5a6b85")),
    "p": ParagraphStyle("p", fontName="LS", fontSize=10, leading=14.5, alignment=TA_JUSTIFY, spaceAfter=6),
    "b": ParagraphStyle("b", fontName="LSB", fontSize=10, leading=14, spaceBefore=6, spaceAfter=4, textColor=NAVY),
    "small": ParagraphStyle("small", fontName="LS", fontSize=8, leading=10, textColor=colors.HexColor("#5a6b85")),
    "cell": ParagraphStyle("cell", fontName="LS", fontSize=8.5, leading=11),
    "cellb": ParagraphStyle("cellb", fontName="LSB", fontSize=8.5, leading=11),
}

BREAKERS = [6, 10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160]
SECTION = {6: 1.5, 10: 1.5, 16: 2.5, 20: 4, 25: 4, 32: 6, 40: 10, 50: 10, 63: 16, 80: 25, 100: 35, 125: 50, 160: 70}


def num(v, default=0.0):
    try:
        return float(str(v).replace(",", ".").split()[0])
    except Exception:
        return default


def fmt(v, d=2):
    s = f"{v:.{d}f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def pick(i):
    return next((b for b in BREAKERS if b >= i), BREAKERS[-1])


def ro_date(v):
    if not v:
        return datetime.now().strftime("%d.%m.%Y")
    try:
        return datetime.fromisoformat(str(v)[:10]).strftime("%d.%m.%Y")
    except Exception:
        return str(v)


def sizing(r):
    tri = "mono" not in str(r.get("supply") or "Trifazat").lower()
    cur = (lambda kw: kw * 1000 / (math.sqrt(3) * 400 * 0.95)) if tri else (lambda kw: kw * 1000 / (230 * 0.95))
    inv_kw = num(r.get("inverter_kw")) or num(r.get("power"))
    br_kw = num(r.get("bransament_kw")) or num(r.get("power")) or inv_kw
    n = int(num(r.get("panel_count")))
    w = num(r.get("panel_w"))
    kwp = num(r.get("_kwp")) or n * w / 1000
    mppt = 2 if n > 12 else 1
    i_br = cur(br_kw) if br_kw else 0
    i_inv = cur(inv_kw) if inv_kw else 0
    main = pick(i_br * 1.25) if br_kw else 0
    invb = pick(i_inv * 1.25) if inv_kw else 0
    warnings = []
    if inv_kw and br_kw and inv_kw > br_kw:
        warnings.append(f"Puterea invertorului ({fmt(inv_kw)} kW) depășește puterea branșamentului ({fmt(br_kw)} kW) — este necesar spor de putere.")
    if not tri and inv_kw > 3.68:
        warnings.append("Branșament monofazat cu invertor > 3,68 kW — verificați cerințele OD (recomandat trifazat).")
    if main and invb > main:
        warnings.append("Protecția invertorului depășește protecția generală a branșamentului — verificați selectivitatea.")
    return {
        "tri": tri, "phases": "3P+N+PE" if tri else "1P+N+PE", "un": "3x400/230 V" if tri else "230 V",
        "br_kw": br_kw, "inv_kw": inv_kw, "i_br": i_br, "i_inv": i_inv, "main": main, "invb": invb,
        "main_sec": SECTION.get(main, 0), "inv_sec": SECTION.get(invb, 0),
        "poles": 4 if tri else 2, "kwp": kwp, "n": n, "w": w, "mppt": mppt,
        "per_string": math.ceil(n / mppt) if n else 0, "warnings": warnings,
        "bat_kwh": num(r.get("battery_kwh")),
    }


class Ctx:
    def __init__(self, rec, settings, client):
        self.r = rec
        self.s = settings or {}
        self.c = client or {}

    def g(self, k, alt=None, default="................"):
        v = self.r.get(k) or (self.c.get(alt) if alt else None)
        return str(v) if v not in (None, "") else default

    @property
    def name(self): return self.g("client_name", "name")
    @property
    def cnp(self): return self.g("cnp", "idcode")
    @property
    def addr(self): return self.g("address", "address")
    @property
    def company(self): return self.s.get("company") or "DNS HOSTESS S.R.L."
    @property
    def rep(self): return self.r.get("executant_rep") or self.s.get("rep") or "................"
    @property
    def attest(self): return self.s.get("anre_attest") or "................"
    @property
    def date(self): return ro_date(self.r.get("date"))


def P(t, st="p"):
    return Paragraph(t, S[st])


def header(ctx, title, subtitle=None):
    s = ctx.s
    line = f"<b>{ctx.company}</b> · Atestat ANRE nr. {ctx.attest}"
    extra = " · ".join(x for x in [s.get("cui") and f"CUI {s.get('cui')}", s.get("regcom"), s.get("address"), s.get("phone")] if x)
    out = [P(line + (f"<br/>{extra}" if extra else ""), "small"), Spacer(1, 10), P(title, "h")]
    if subtitle:
        out.append(P(subtitle, "sub"))
    out.append(Spacer(1, 12))
    return out


def table(rows, widths, head=True):
    data = [[Paragraph(str(c), S["cellb" if (head and i == 0) else "cell"]) for c in row] for i, row in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if head else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#b8c4d6")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if head:
        st.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef4ff")))
    t.setStyle(TableStyle(st))
    return t


def kv(rows):
    return table(rows, [62 * mm, 112 * mm], head=False)


def signatures(left_label, left_name, right_label, right_name):
    t = Table([[P(f"<b>{left_label}</b><br/>{left_name}<br/><br/>Semnătura: ____________"),
                P(f"<b>{right_label}</b><br/>{right_name}<br/><br/>Semnătura: ____________")]], colWidths=[87 * mm, 87 * mm])
    return [Spacer(1, 22), t]


def equipment_rows(ctx):
    r = ctx.r
    return [
        ["Echipament", "Producător / model", "Buc.", "Putere / caracteristici"],
        ["Invertor", ctx.g("inverter"), ctx.g("inverter_count", default="1"), f"{ctx.g('inverter_kw')} kW c.a."],
        ["Module fotovoltaice", ctx.g("panels"), ctx.g("panel_count"), f"{ctx.g('panel_w')} W / modul"],
        ["Sistem de stocare", ctx.g("battery", default="—"), "1" if r.get("battery") else "—",
         f"{ctx.g('battery_kwh', default='—')} kWh" + (f" · {r.get('battery_v')} V / {r.get('battery_ah')} Ah" if r.get("battery_ah") else "")],
    ]


# ---------------- Documents ----------------
def doc_notificare(ctx):
    sz = sizing(ctx.r)
    op = ctx.g("operator", default="Operatorul de distribuție")
    out = header(ctx, "NOTIFICARE", "Anexa nr. 2 — privind racordarea la un loc de consum existent a unei instalații de producere a energiei electrice")
    out += [
        P(f"Către: <b>{op}</b>"),
        P(f"Subsemnatul(a) <b>{ctx.name}</b>, CNP/CUI <b>{ctx.cnp}</b>, cu domiciliul/sediul în <b>{ctx.addr}</b>, "
          f"titular al locului de consum cu codul unic de identificare (POD) <b>{ctx.g('pod')}</b>, notific racordarea la locul de consum "
          f"existent a unei instalații de producere a energiei electrice din surse regenerabile (fotovoltaică), conform datelor de mai jos."),
        P("1. Date tehnice și energetice ale instalației de producere", "b"),
        kv([["Putere instalată (simultan evacuată în rețea)", f"{ctx.g('power')} kW"],
            ["Putere aparentă maximă evacuată", f"{ctx.g('apparent_kva')} kVA"],
            ["Putere totală module PV (c.c.)", f"{fmt(sz['kwp'])} kWp" if sz["kwp"] else "................"],
            ["Tip racord", f"{'Trifazat' if sz['tri'] else 'Monofazat'} — {sz['un']}"],
            ["Putere aprobată loc de consum / branșament", f"{fmt(sz['br_kw'])} kW" if sz["br_kw"] else "................"],
            ["Tip sistem", ctx.g("system_type")]]),
        Spacer(1, 8), P("2. Generatoare, invertoare și module", "b"),
        table(equipment_rows(ctx), [38 * mm, 70 * mm, 14 * mm, 52 * mm]),
        P("3. Sisteme de stocare", "b"),
        P(f"Sistem de stocare: <b>{ctx.g('battery', default='nu există')}</b>, energie utilă {ctx.g('battery_kwh', default='—')} kWh. "
          "Sistemul de stocare nu evacuează și nu absoarbe energie din rețea în afara regimului de funcționare declarat."),
        P("4. Anexe", "b"),
        P("Act de identitate; împuternicire; atestat ANRE al executantului; proces-verbal de recepție la terminarea lucrărilor; "
          "buletin de verificare a prizei de pământ; buletin de reglaj protecții invertor; certificate de conformitate și fișe tehnice "
          "(invertor, module, baterie); schema monofilară a instalației."),
        P("Declar pe propria răspundere că datele de mai sus sunt reale și că documentele anexate sunt conforme cu originalul."),
        P(f"Data: {ctx.date}"),
    ]
    return out + signatures("Titular loc de consum", ctx.name, "Împuternicit / executant", f"{ctx.company}<br/>{ctx.rep}")


def doc_imputernicire(ctx):
    out = header(ctx, "ÎMPUTERNICIRE")
    out += [
        P(f"Subsemnatul(a) <b>{ctx.name}</b>, CNP <b>{ctx.cnp}</b>, domiciliat(ă) în <b>{ctx.addr}</b>, titular al locului de consum "
          f"POD <b>{ctx.g('pod')}</b>, împuternicesc prin prezenta societatea <b>{ctx.company}</b>, atestată ANRE nr. {ctx.attest}, "
          f"reprezentată prin <b>{ctx.rep}</b>, să mă reprezinte în relația cu <b>{ctx.g('operator', default='operatorul de distribuție')}</b> "
          "și cu furnizorul de energie electrică pentru: depunerea și semnarea notificării de racordare a instalației de producere, "
          "a documentelor anexe, solicitarea înlocuirii contorului cu unul bidirecțional, precum și ridicarea documentelor emise."),
        P("Prezenta împuternicire este valabilă până la finalizarea procedurii de racordare și obținerea statutului de prosumator."),
        P(f"Data: {ctx.date}"),
    ]
    return out + signatures("Mandant (titular)", ctx.name, "Mandatar", f"{ctx.company}<br/>{ctx.rep}")


def doc_decl_beneficiar(ctx):
    afm = str(ctx.r.get("afm") or "Nu").lower().startswith("d")
    out = header(ctx, "DECLARAȚIE PE PROPRIA RĂSPUNDERE", "a titularului locului de consum")
    out += [
        P(f"Subsemnatul(a) <b>{ctx.name}</b>, CNP <b>{ctx.cnp}</b>, domiciliat(ă) în <b>{ctx.addr}</b>, cunoscând prevederile Codului penal "
          "privind falsul în declarații, declar pe propria răspundere următoarele:"),
        P(f"1. Instalația fotovoltaică de {ctx.g('power')} kW de la locul de consum POD {ctx.g('pod')} a fost executată de "
          f"<b>{ctx.company}</b>, operator economic atestat ANRE nr. {ctx.attest}."),
        P(f"2. {'Beneficiez' if afm else 'NU beneficiez'} de finanțare prin Programul AFM pentru această instalație."),
        P("3. Mă oblig să respect instrucțiunile de exploatare ale echipamentelor și să nu modific setările de protecție ale invertorului "
          "fără acordul operatorului de distribuție."),
        P("4. Datele și documentele depuse în dosar sunt reale și conforme cu originalul."),
        P(f"Data: {ctx.date}"),
    ]
    return out + signatures("Declarant", ctx.name, "", "")


def doc_decl_executant(ctx):
    out = header(ctx, "DECLARAȚIE EXECUTANT")
    out += [
        P(f"Subscrisa <b>{ctx.company}</b>, atestată ANRE nr. {ctx.attest}, reprezentată prin <b>{ctx.rep}</b>, declar pe propria "
          f"răspundere că instalația de producere a energiei electrice de {ctx.g('power')} kW, amplasată la adresa <b>{ctx.addr}</b>, "
          f"beneficiar <b>{ctx.name}</b>, a fost executată cu respectarea normativului I7/2011, a NTE 007/08/00, a reglementărilor ANRE "
          "în vigoare și a documentației tehnice a producătorilor de echipamente."),
        P("Echipamentele montate sunt noi, certificate și compatibile cu cerințele tehnice de racordare la rețeaua electrică de distribuție. "
          "Protecțiile de interfață (antiinsularizare) ale invertorului au fost reglate conform cerințelor operatorului de distribuție."),
        table(equipment_rows(ctx), [38 * mm, 70 * mm, 14 * mm, 52 * mm]),
        P(f"Data: {ctx.date}"),
    ]
    return out + signatures("Executant", f"{ctx.company}<br/>{ctx.rep}", "", "")


def doc_decl_conformitate(ctx):
    out = header(ctx, "DECLARAȚIE DE CONFORMITATE", "privind calitatea lucrărilor executate")
    out += [
        P(f"<b>{ctx.company}</b>, atestat ANRE nr. {ctx.attest}, declară că lucrarea „Instalație fotovoltaică de "
          f"{ctx.g('power')} kW” executată pentru <b>{ctx.name}</b> la adresa <b>{ctx.addr}</b> este conformă cu: Legea nr. 10/1995 privind "
          "calitatea în construcții, normativul I7/2011, PE 116/1994, SR HD 60364-7-712 și cu fișele tehnice ale echipamentelor utilizate."),
        P("Lucrarea a fost verificată, s-au efectuat măsurătorile prevăzute (continuitate, rezistență de izolație, priză de pământ, "
          "funcționarea protecțiilor) și poate fi pusă în funcțiune în condiții de siguranță."),
        P(f"Data: {ctx.date}"),
    ]
    return out + signatures("Executant", f"{ctx.company}<br/>{ctx.rep}", "", "")


def doc_pv_receptie(ctx):
    sz = sizing(ctx.r)
    out = header(ctx, "PROCES-VERBAL DE RECEPȚIE LA TERMINAREA LUCRĂRILOR")
    out += [
        P(f"Încheiat astăzi, {ctx.date}, la obiectivul situat în <b>{ctx.addr}</b>, beneficiar <b>{ctx.name}</b>."),
        P(f"Comisia formată din reprezentantul beneficiarului ({ctx.name}) și reprezentantul executantului ({ctx.rep}, {ctx.company}) "
          "a procedat la recepția lucrării de montaj a instalației fotovoltaice, constatând următoarele:"),
        table(equipment_rows(ctx), [38 * mm, 70 * mm, 14 * mm, 52 * mm]),
        Spacer(1, 6),
        kv([["Putere totală module", f"{fmt(sz['kwp'])} kWp" if sz["kwp"] else "................"],
            ["Putere evacuată", f"{ctx.g('power')} kW / {ctx.g('apparent_kva')} kVA"],
            ["Protecție generală AC invertor", f"{sz['invb']} A, {sz['poles']}P, curba C" if sz["invb"] else "................"],
            ["Rezistența prizei de pământ", f"{ctx.g('grounding_ohm')} Ω"]]),
        P("Constatări: lucrările au fost executate conform documentației tehnice și normativelor în vigoare; nu s-au constatat "
          "deficiențe care să împiedice punerea în funcțiune. Se admite recepția lucrării."),
    ]
    return out + signatures("Beneficiar", ctx.name, "Executant", f"{ctx.company}<br/>{ctx.rep}")


def doc_pv_pif(ctx):
    out = header(ctx, "PROCES-VERBAL DE PUNERE ÎN FUNCȚIUNE FINALĂ", "a centralei electrice fotovoltaice")
    out += [
        P(f"Încheiat astăzi, {ctx.date}, pentru instalația de producere de <b>{ctx.g('power')} kW</b> de la locul de consum POD "
          f"<b>{ctx.g('pod')}</b>, adresa <b>{ctx.addr}</b>, titular <b>{ctx.name}</b>."),
        P("S-au efectuat: verificarea vizuală a montajului, verificarea conexiunilor c.c. și c.a., verificarea polarității stringurilor, "
          "verificarea setărilor de protecție ale invertorului, proba de deconectare la lipsa tensiunii rețelei (antiinsularizare) și "
          "punerea sub tensiune a instalației."),
        P("Concluzii: instalația funcționează normal, protecțiile acționează corect, iar centrala fotovoltaică a fost pusă în funcțiune. "
          "Beneficiarul a fost instruit privind exploatarea și a primit manualele echipamentelor."),
        P("Se recomandă respectarea instrucțiunilor de exploatare și efectuarea verificărilor periodice prevăzute de producători."),
    ]
    return out + signatures("Beneficiar", ctx.name, "Executant", f"{ctx.company}<br/>{ctx.rep}")


def doc_buletin_priza(ctx):
    ohm = num(ctx.r.get("grounding_ohm"), None)
    limit = 4.0
    verdict = "................" if ohm is None else ("ADMIS" if ohm <= limit else "RESPINS")
    out = header(ctx, "BULETIN DE VERIFICARE ȘI MĂSURARE", "a instalației de legare la pământ")
    out += [
        P(f"Beneficiar: <b>{ctx.name}</b> · Adresa: <b>{ctx.addr}</b> · Data măsurării: {ctx.date}"),
        kv([["Aparat de măsură", ctx.g("meter_device", default="Telurometru / analizor instalații — serie ................")],
            ["Metoda de măsurare", "Metoda celor două sonde auxiliare (62%)"],
            ["Tip priză", ctx.g("grounding_type", default="Priză artificială — electrozi verticali OL-Zn")],
            ["Starea solului", ctx.g("soil", default="Normală")]]),
        Spacer(1, 8),
        table([["Nr.", "Punct de măsurare", "Valoare măsurată (Ω)", "Valoare admisă (Ω)", "Rezultat"],
               ["1", "Priză de pământ instalație PV / TG", fmt(ohm) if ohm is not None else "......", f"≤ {fmt(limit)}", verdict]],
              [12 * mm, 62 * mm, 36 * mm, 34 * mm, 30 * mm]),
        P("Valoarea admisă conform I7/2011 și SR HD 60364-7-712 pentru instalația fotovoltaică comună cu instalația de paratrăsnet / "
          "protecție: ≤ 4 Ω (≤ 1 Ω în cazul prizei comune cu IPT, dacă este cazul)."),
        P(f"Concluzie: instalația de legare la pământ este <b>{verdict}</b>."),
    ]
    return out + signatures("Verificator", f"{ctx.company}<br/>{ctx.rep}", "Beneficiar", ctx.name)


def doc_buletin_reglaj(ctx):
    tri = sizing(ctx.r)["tri"]
    out = header(ctx, "BULETIN DE REGLAJ", "protecții de interfață invertor (antiinsularizare)")
    out += [
        P(f"Invertor: <b>{ctx.g('inverter')}</b>, {ctx.g('inverter_kw')} kW · Beneficiar: <b>{ctx.name}</b> · Data: {ctx.date}"),
        table([["Funcție", "Prag", "Temporizare", "Stare"],
               ["Maximal de tensiune U>", "1,10 Un (253 V)", "3 s", "Setat / verificat"],
               ["Maximal de tensiune U>>", "1,15 Un (264,5 V)", "0,2 s", "Setat / verificat"],
               ["Minimal de tensiune U<", "0,85 Un (195,5 V)", "1,5 s", "Setat / verificat"],
               ["Maximal de frecvență f>", "51,5 Hz", "0,5 s", "Setat / verificat"],
               ["Minimal de frecvență f<", "47,5 Hz", "0,5 s", "Setat / verificat"],
               ["ROCOF df/dt", "1 Hz/s", "0,5 s", "Setat / verificat"],
               ["Reconectare automată", "U, f în limite", "≥ 60 s", "Setat / verificat"]],
              [55 * mm, 45 * mm, 34 * mm, 40 * mm]),
        P(f"Cod rețea selectat în invertor: România / conform cerințelor OD · Rețea: {'trifazată 3x400/230 V' if tri else 'monofazată 230 V'}."),
        P("Valorile au fost setate conform cerințelor tehnice ale operatorului de distribuție (Ordin ANRE 51/2019 / ATR). "
          "Se verifică și se adaptează conform avizului tehnic de racordare emis, dacă acesta prevede alte valori."),
    ]
    return out + signatures("Executant", f"{ctx.company}<br/>{ctx.rep}", "Beneficiar", ctx.name)


def doc_autenticitate(ctx):
    items = ["Notificare Anexa nr. 2", "Act de identitate titular", "Împuternicire", "Atestat ANRE executant",
             "Declarație executant", "Declarație de conformitate", "Proces-verbal de recepție la terminarea lucrărilor",
             "Proces-verbal de punere în funcțiune finală", "Buletin de verificare priză de pământ", "Buletin de reglaj protecții invertor",
             "Schema monofilară", "Fișă tehnică și certificat de conformitate invertor", "Fișă tehnică module fotovoltaice",
             "Fișă tehnică și certificat sistem de stocare"]
    out = header(ctx, "DECLARAȚIE", "privind autenticitatea datelor și conformitatea documentelor cu originalul")
    out += [P(f"Subsemnatul(a) <b>{ctx.name}</b>, CNP <b>{ctx.cnp}</b>, declar pe propria răspundere că datele prezentate sunt reale "
              "și că documentele anexate notificării sunt conforme cu originalul:"),
            table([["Nr.", "Document"]] + [[str(i + 1), d] for i, d in enumerate(items)], [12 * mm, 162 * mm]),
            P(f"Data: {ctx.date}")]
    return out + signatures("Titular", ctx.name, "Împuternicit", f"{ctx.company}<br/>{ctx.rep}")


class SchemaDrawing(Flowable):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.sz = sizing(ctx.r)
        self.width, self.height = 174 * mm, 205 * mm

    def box(self, x, y, w, h, title, lines, fill="#f3f7ff"):
        c = self.canv
        c.setFillColor(colors.HexColor(fill)); c.setStrokeColor(NAVY); c.setLineWidth(0.9)
        c.roundRect(x, y, w, h, 4, stroke=1, fill=1)
        c.setFillColor(NAVY); c.setFont("LSB", 8.5); c.drawString(x + 5, y + h - 11, title)
        c.setFont("LS", 7.3); c.setFillColor(colors.black)
        for i, ln in enumerate(lines):
            c.drawString(x + 5, y + h - 22 - i * 9, ln)

    def wire(self, x1, y1, x2, y2, label=None, dc=False):
        c = self.canv
        c.setStrokeColor(colors.HexColor("#c0392b") if dc else NAVY); c.setLineWidth(1.4)
        if dc:
            c.setDash(4, 2)
        c.line(x1, y1, x2, y2); c.setDash()
        if label:
            c.setFont("LS", 6.8); c.setFillColor(colors.HexColor("#334"))
            c.drawString(max(x1, x2) + 4, (y1 + y2) / 2 - 2, label)

    def draw(self):
        sz, ctx, c = self.sz, self.ctx, self.canv
        W = self.width
        cx = 55 * mm
        bw = 92 * mm
        x0 = cx - bw / 2
        ph = "3x400/230 V, 50 Hz" if sz["tri"] else "230 V, 50 Hz"
        self.box(x0, 186 * mm, bw, 17 * mm, "REȚEA OD — " + ctx.g("operator", default="Operator distribuție"),
                 [f"Branșament {'trifazat' if sz['tri'] else 'monofazat'} {ph}", f"Putere aprobată: {fmt(sz['br_kw'])} kW"], "#e8eef8")
        self.wire(cx, 186 * mm, cx, 176 * mm, f"Cablu branșament {sz['phases']}")
        self.box(x0, 150 * mm, bw, 26 * mm, "BMP — Bloc de măsură și protecție",
                 [f"Contor bidirecțional {'trifazat' if sz['tri'] else 'monofazat'}",
                  f"Întreruptor general: {sz['main']} A, {sz['poles']}P, curba C (Ib={fmt(sz['i_br'], 1)} A)",
                  f"POD: {ctx.g('pod')}"])
        self.wire(cx, 150 * mm, cx, 140 * mm, f"CYY-F {'5' if sz['tri'] else '3'}x{fmt(sz['main_sec'])} mm²")
        self.box(x0, 106 * mm, bw, 34 * mm, "TG — Tablou general / Tablou AC PV",
                 [f"Disjunctor invertor: {sz['invb']} A, {sz['poles']}P, curba C (Ib={fmt(sz['i_inv'], 1)} A)",
                  f"Protecție diferențială: {ctx.g('rcd', default='RCD tip A/B 300 mA')}",
                  f"SPD AC tip 1+2, {'4P' if sz['tri'] else '2P'}, Uc 275 V",
                  "Bară PE + legătură la priza de pământ",
                  f"Consumatori casă — circuite existente"])
        self.wire(cx, 106 * mm, cx, 96 * mm, f"CYY-F {'5' if sz['tri'] else '3'}x{fmt(sz['inv_sec'])} mm²")
        self.box(x0, 68 * mm, bw, 28 * mm, "INVERTOR " + ("HIBRID" if ctx.r.get("battery") else "ON-GRID"),
                 [ctx.g("inverter")[:52], f"P = {fmt(sz['inv_kw'])} kW c.a. · {sz['un']}",
                  f"MPPT utilizate: {sz['mppt']} · protecție antiinsularizare integrată",
                  f"Putere evacuată: {ctx.g('power')} kW / {ctx.g('apparent_kva')} kVA"])
        # DC side
        self.wire(cx, 68 * mm, cx, 58 * mm, "Cablu solar 2x6 mm² (DC)", dc=True)
        self.box(x0, 36 * mm, bw, 22 * mm, "TABLOU DC (string box)",
                 [f"Siguranțe gPV 15 A / 1000 V DC × {sz['mppt'] * 2}", "Separator DC 1000 V · SPD DC tip 2, 1000 V",
                  "Legare la PE a ramelor modulelor"], "#fff4f2")
        self.wire(cx, 36 * mm, cx, 28 * mm, None, dc=True)
        self.box(x0, 4 * mm, bw, 24 * mm, "CÂMP FOTOVOLTAIC",
                 [f"{sz['n']} × {fmt(sz['w'], 0)} W — {ctx.g('panels')[:40]}", f"Total: {fmt(sz['kwp'])} kWp",
                  f"{sz['mppt']} string(uri) × {sz['per_string']} module"], "#fffbe8")
        # battery
        if ctx.r.get("battery"):
            bx = 112 * mm
            self.box(bx, 70 * mm, 60 * mm, 24 * mm, "SISTEM STOCARE",
                     [ctx.g("battery")[:34], f"{ctx.g('battery_kwh')} kWh · {ctx.g('battery_v', default='—')} V",
                      "Siguranță DC baterie / BMS"], "#effaf2")
            self.wire(x0 + bw, 82 * mm, bx, 82 * mm, None, dc=True)
        # ground
        gx = 112 * mm
        c.setStrokeColor(colors.HexColor("#1e8449")); c.setLineWidth(1.2)
        c.line(x0 + bw, 112 * mm, gx + 10 * mm, 112 * mm); c.line(gx + 10 * mm, 112 * mm, gx + 10 * mm, 104 * mm)
        for i, w in enumerate([10, 7, 4]):
            c.line(gx + 10 * mm - w * mm / 2, (104 - i * 2) * mm, gx + 10 * mm + w * mm / 2, (104 - i * 2) * mm)
        c.setFont("LS", 7); c.setFillColor(colors.HexColor("#1e8449"))
        c.drawString(gx + 16 * mm, 102 * mm, f"Priză de pământ R = {ctx.g('grounding_ohm', default='≤4')} Ω")
        # legend + warnings
        c.setFillColor(colors.black); c.setFont("LSB", 7.5)
        c.drawString(112 * mm, 60 * mm, "Legendă")
        c.setFont("LS", 7)
        c.setStrokeColor(NAVY); c.line(112 * mm, 56 * mm, 122 * mm, 56 * mm); c.drawString(124 * mm, 55 * mm, "Circuit c.a.")
        c.setStrokeColor(colors.HexColor("#c0392b")); c.setDash(4, 2); c.line(112 * mm, 51 * mm, 122 * mm, 51 * mm); c.setDash()
        c.drawString(124 * mm, 50 * mm, "Circuit c.c.")
        c.setStrokeColor(colors.HexColor("#1e8449")); c.line(112 * mm, 46 * mm, 122 * mm, 46 * mm); c.drawString(124 * mm, 45 * mm, "Conductor PE")
        y = 38 * mm
        for wtxt in sz["warnings"]:
            c.setFillColor(colors.HexColor("#b03a2e")); c.setFont("LSB", 6.8)
            words, line = wtxt.split(), ""
            for wd in ["ATENȚIE:"] + words:
                if c.stringWidth(line + " " + wd, "LSB", 6.8) > 58 * mm:
                    c.drawString(112 * mm, y, line.strip()); y -= 8; line = ""
                line += " " + wd
            c.drawString(112 * mm, y, line.strip()); y -= 12


def doc_schema(ctx):
    out = header(ctx, "SCHEMA MONOFILARĂ", f"Instalație fotovoltaică {ctx.g('power')} kW — {ctx.name}, {ctx.addr}")
    out.append(SchemaDrawing(ctx))
    out.append(Spacer(1, 6))
    out.append(table([["Întocmit", "Beneficiar", "Data", "Planșa"],
                      [f"{ctx.company} / {ctx.rep}", ctx.name, ctx.date, "E-01 · rev. 0"]], [55 * mm, 55 * mm, 30 * mm, 34 * mm]))
    return out


DOCS = {
    "notificare": ("Notificare Anexa 2 (OD)", doc_notificare),
    "imputernicire": ("Împuternicire", doc_imputernicire),
    "declaratie_beneficiar": ("Declarație beneficiar", doc_decl_beneficiar),
    "declaratie_executant": ("Declarație executant", doc_decl_executant),
    "declaratie_conformitate": ("Declarație de conformitate", doc_decl_conformitate),
    "pv_receptie": ("PV recepție la terminarea lucrărilor", doc_pv_receptie),
    "pv_pif": ("PV punere în funcțiune finală", doc_pv_pif),
    "buletin_priza": ("Buletin priză de pământ", doc_buletin_priza),
    "buletin_reglaj": ("Buletin reglaj protecții invertor", doc_buletin_reglaj),
    "declaratie_autenticitate": ("Declarație autenticitate documente", doc_autenticitate),
    "schema": ("Schema monofilară (simplificată)", doc_schema),
    "schema_cef": ("Schema monofilară CEF (multi-invertor)", None),
}


def render(doc_keys, rec, settings, client):
    ctx = Ctx(CEF.flatten(rec), settings, client)
    buf = io.BytesIO()
    m = 14 * mm
    pw, ph = A4
    port = PageTemplate("port", [Frame(18 * mm, m, pw - 36 * mm, ph - 2 * m, id="fp")], pagesize=A4)
    land = PageTemplate("land", [Frame(12 * mm, 10 * mm, ph - 24 * mm, pw - 20 * mm, id="fl")], pagesize=landscape(A4))
    first_land = doc_keys and doc_keys[0] == "schema_cef"
    pdf = BaseDocTemplate(buf, pageTemplates=[land, port] if first_land else [port, land], title=f"D-ENERGY — {ctx.name}")
    story = []
    for i, k in enumerate(doc_keys):
        if k == "schema_cef":
            draw, tbl = schema_cef.story(ctx, P, table, S)
            if i:
                story += [NextPageTemplate("land"), PageBreak()]
            story += draw + [PageBreak()] + tbl + [NextPageTemplate("port")]
            continue
        if i:
            story.append(PageBreak())
        story += DOCS[k][1](ctx)
    pdf.build(story)
    return buf.getvalue()
