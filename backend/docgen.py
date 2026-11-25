import base64
import io
import os
import re
import math
from html import escape, unescape
import unicodedata
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, NextPageTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak, KeepTogether, Image)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import cef as CEF
import schema_cef

FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts") + os.sep
pdfmetrics.registerFont(TTFont("LS", FD + "LiberationSans-Regular.ttf"))
pdfmetrics.registerFont(TTFont("LSB", FD + "LiberationSans-Bold.ttf"))
pdfmetrics.registerFontFamily("LS", normal="LS", bold="LSB", italic="LS", boldItalic="LSB")

NAVY = colors.HexColor("#0b1f3a")
GRID = colors.HexColor("#9aa7b8")
S = {
    "h": ParagraphStyle("h", fontName="LSB", fontSize=13, leading=17, alignment=TA_CENTER, spaceAfter=2),
    "sub": ParagraphStyle("sub", fontName="LS", fontSize=9.5, leading=12.5, alignment=TA_CENTER, spaceAfter=4),
    "c": ParagraphStyle("c", fontName="LSB", fontSize=10, leading=13, alignment=TA_CENTER, spaceBefore=4, spaceAfter=4),
    "p": ParagraphStyle("p", fontName="LS", fontSize=9.6, leading=13.6, alignment=TA_JUSTIFY, spaceAfter=5),
    "r": ParagraphStyle("r", fontName="LS", fontSize=9.6, leading=13, alignment=TA_RIGHT, spaceAfter=4),
    "b": ParagraphStyle("b", fontName="LSB", fontSize=9.8, leading=13.5, spaceBefore=5, spaceAfter=3),
    "li": ParagraphStyle("li", fontName="LS", fontSize=9.6, leading=13.4, leftIndent=12, bulletIndent=2, spaceAfter=2, alignment=TA_JUSTIFY),
    "small": ParagraphStyle("small", fontName="LS", fontSize=7.8, leading=10),
    "hdrl": ParagraphStyle("hdrl", fontName="LS", fontSize=8, leading=10.5),
    "hdrr": ParagraphStyle("hdrr", fontName="LS", fontSize=8, leading=10.5, alignment=TA_RIGHT),
    "cell": ParagraphStyle("cell", fontName="LS", fontSize=8.3, leading=10.5),
    "cellb": ParagraphStyle("cellb", fontName="LSB", fontSize=8.3, leading=10.5),
    "sig": ParagraphStyle("sig", fontName="LS", fontSize=9.2, leading=12.5, alignment=TA_CENTER),
}
M = "…………………"
_PDF_MISSING_MARKERS = (M, "de confirmat", "de completat", "de verificat", "necompletat", "neconfirmat",
                        "[lipsă]", "[lipsa]", "lipsă —", "lipsa —", "date lipsă", "date lipsa",
                        "valoare lipsă", "valoare lipsa", "model lipsă", "model lipsa", "neprecizat",
                        "neconfigurat", "neselectat", "nemăsurat", "nestabilit", "neidentificat")


def _has_pdf_placeholder(value):
    text = str(value or "").strip().casefold()
    return any(marker.casefold() in text for marker in _PDF_MISSING_MARKERS)


def _clean_pdf_table(rows):
    """Omit rows whose source data is incomplete; never print placeholder fields."""
    if not rows:
        return rows
    header, *data = rows
    def empty(cell):
        text = str(cell or "").strip()
        return not text or text == "—" or text == "-"
    kept = [row for row in data
            if not any(_has_pdf_placeholder(cell) for cell in row)
            and (len(row) < 2 or any(not empty(cell) for cell in row[1:]))]
    return [header, *kept] if kept else []

GDPR_FILL = "……………………………………………………………………………………………………"
GDPR_TITLE = ("NOTĂ DE INFORMARE CU PRIVIRE LA PRELUCRAREA DATELOR DUMNEAVOASTRĂ CU CARACTER PERSONAL "
              "DE CĂTRE DISTRIBUȚIA ENERGIE ELECTRICĂ ROMÂNIA S.A.")
GDPR_SECTIONS = [
    "Introducere",
    "Categoriile de date prelucrate",
    "Scopurile și temeiurile legale ale prelucrării",
    "Sursa datelor",
    "Divulgarea datelor",
    "Perioada de păstrare",
    "Transferul datelor",
    "Drepturile persoanei vizate",
    "Consecințele nefurnizării datelor",
    "DATELE NOASTRE DE CONTACT",
]
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
        return None
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
    return {"tri": tri, "phases": "3P+N+PE" if tri else "1P+N+PE", "un": "3x400/230 V" if tri else "230 V",
            "br_kw": br_kw, "inv_kw": inv_kw, "i_br": i_br, "i_inv": i_inv, "main": main, "invb": invb,
            "main_sec": SECTION.get(main, 0), "inv_sec": SECTION.get(invb, 0), "poles": 4 if tri else 2, "kwp": kwp,
            "n": n, "w": w, "mppt": mppt, "per_string": math.ceil(n / mppt) if n else 0, "warnings": warnings,
            "bat_kwh": num(r.get("battery_kwh"))}


ALIASES = {"idcode": ["cnp", "cui"], "ci_series": ["id_series"], "name": ["client_name"]}


CLIENT_KEYS = {"name", "idcode", "kind", "regcom", "ci_series", "rep_name", "rep_role", "hq_address", "phone", "email", "iban", "bank",
               "address", "locality", "county", "pod", "nlc", "cadastral_nr", "cf_nr", "supplier", "operator"}


class Ctx:
    """Resolve the saved dossier snapshot first, with the client sheet as fallback; settings hold executant data."""

    def __init__(self, rec, settings, client, opis_titles=None):
        self.r, self.s, self.c = rec, settings or {}, client or {}
        self.opis_titles = opis_titles or []
        self.used = set()

    def raw(self, k):
        self.used.add(k)
        # The dossier form is editable after client selection. Generated documents must
        # reflect the values the operator reviewed and saved on this dossier, while the
        # master client record remains a fallback for fields not copied into the dossier.
        order = (self.r, self.c)
        for src in order:
            if src.get(k) not in (None, ""):
                return src.get(k)
            for a in ALIASES.get(k, []):
                if src.get(a) not in (None, ""):
                    return src.get(a)
        return None

    def v(self, k, d=M):
        x = self.raw(k)
        return escape(str(x)) if x is not None else d

    def e(self, k, d=M):
        x = self.s.get(k)
        return escape(str(x)) if x not in (None, "") else d

    @property
    def name(self): return self.v("name")
    @property
    def company(self): return self.e("company", "DNS HOSTESS SRL")
    @property
    def rep(self): return self.e("rep")
    @property
    def date(self): return ro_date(self.raw("doc_date") or self.raw("date")) or M
    @property
    def loc(self):
        parts = [self.raw("address"), self.raw("locality")]
        county = self.raw("county")
        s = ", ".join(str(p) for p in parts if p)
        if county:
            s += f", jud. {county}"
        return escape(s) if s else M
    @property
    def pj(self): return "jurid" in str(self.raw("kind") or "").lower()
    @property
    def op_short(self):
        o = str(self.raw("operator") or "")
        return escape(o.split("—")[0].split(" Sucursala")[0].strip()) if o else M
    @property
    def tot(self):
        return CEF.check(self.r.get("cef") or {}) if (self.r.get("cef") or {}).get("inverters") else None
    @property
    def cef_kw(self):
        p = self.raw("power")
        return f"{fmt(num(p))} kW" if p else M
    @property
    def power_increase(self):
        return str(self.raw("request_type") or "").strip() == "Spor de putere + prosumator"

    @property
    def request_scope(self):
        return "spor de putere și racordare a centralei electrice fotovoltaice în regim de prosumator" if self.power_increase else "racordare a centralei electrice fotovoltaice în regim de prosumator"


# ---------- blocks ----------
def B(kind, *a):
    return (kind, *a)


# Compatibility helpers used by the DI-U document renderer.
def hdr():
    return [B("hdr")]


def sign(left, right):
    return B("sign", left, right)


def ex_sig(ctx, label="Instalator/Executant"):
    return [label, ctx.company, f"Reprezentant: {ctx.rep}", "semnătura și ștampila"]


def ben_sig(ctx):
    return ["Beneficiar", ctx.name, "semnătura"]


# ---------- PDF renderer ----------
def inverters(ctx):
    cef = ctx.r.get("cef") or {}
    if cef.get("inverters"):
        return cef["inverters"]
    if ctx.raw("inverter"):
        return [{"brand_model": ctx.raw("inverter"), "p_nom_kw": ctx.raw("inverter_kw"), "p_max_kw": ctx.raw("inverter_kw"),
                 "phases": ctx.raw("supply") or "Trifazat", "panel_model": ctx.raw("panels"), "panel_w": ctx.raw("panel_w"),
                 "strings": [{"panels": ctx.raw("panel_count")}] if ctx.raw("panel_count") else []}]
    return []


def panel_rows(ctx):
    rows = []
    for inv in inverters(ctx):
        if inv.get("battery_only") or inv.get("no_panels"):
            continue
        count = max(1, int(num(inv.get("count") or inv.get("quantity"), 1)))
        groups = {}
        for string in inv.get("strings") or []:
            panels = int(num(string.get("panels")))
            if panels <= 0:
                continue
            model = string.get("panel_model") or inv.get("panel_model") or ""
            watts = num(string.get("panel_w") if string.get("panel_w") not in (None, "") else inv.get("panel_w"))
            key = (model, watts)
            groups[key] = groups.get(key, 0) + panels
        for (model, watts), panel_count in groups.items():
            rows.append({"n": panel_count, "count": count, "model": model, "w": watts, "kw": panel_count * watts / 1000})
    return rows


def storage(ctx):
    cef = ctx.r.get("cef") or {}
    bats = [i.get("battery") for i in cef.get("inverters") or [] if i.get("battery_mode") == "own"] + list(cef.get("shared_batteries") or [])
    if not cef.get("inverters") and ctx.raw("battery"):
        bats = [{"model": ctx.raw("battery"), "kwh": ctx.raw("battery_kwh")}]
    return [b for b in bats if b and b.get("model")]


def doc_notificare(ctx):
    sl = ctx.raw("smart_meter_type")
    st = storage(ctx)
    invs = inverters(ctx)
    pr = panel_rows(ctx)
    tri = "mono" not in str(ctx.raw("supply") or ((ctx.r.get("cef") or {}).get("grid") or {}).get("supply") or "Trifazat").lower()
    out = [B("r", "Anexa nr. 2"), B("title", "NOTIFICARE"), B("sub", "privind racordarea la un loc de consum existent a unei instalaţii<br/>de producere a energiei electrice"),
           B("p", f"Utilizatorul <b>{ctx.name}</b>, cu domiciliul/sediul în {ctx.v('hq_address')}, telefon/telefon mobil/fax {ctx.v('phone')}, "
                  f"e-mail {ctx.v('email', '—')}, cod de înregistrare fiscală/CNP {ctx.v('idcode')}, contul {ctx.v('iban', '................')}, deschis la banca "
                  f"{ctx.v('bank', '................')}, reprezentat prin împuternicit/reprezentant al operatorului economic atestat <b>{ctx.company}</b>, CUI "
                  f"{ctx.e('cui')}, {ctx.e('regcom')}, {ctx.rep}, cu domiciliul/sediul în {ctx.e('address')}, telefon {ctx.e('phone')}, e-mail {ctx.e('email')}, "
                  f"nr./dată act autorizare {ctx.e('anre_attest')}, emis de ANRE,"),
           B("p", f"notific prin prezenta racordarea la locul de consum existent situat în <b>{ctx.loc}</b>, nr. CF {ctx.v('cf_nr', '—')}, nr. cadastral "
                  f"{ctx.v('cadastral_nr', '—')}, având codul unic de identificare <b>{ctx.v('pod')}</b> (înscris pe factura de energie electrică), a unei instalaţii "
                  f"de producere a energiei electrice cu putere maximă simultană ce poate fi evacuată în reţeaua de distribuţie de <b>{ctx.cef_kw} "
                  f"{ctx.v('apparent_kva')} kVA</b>."),
           B("p", "Prin prezenta notificare solicit:"),
           B("bullets", ["înlocuirea contorului existent la locul de consum cu un contor de măsurare a energiei electrice în ambele sensuri;",
                         "punerea sub tensiune pentru perioada de probe a instalaţiei de producere a energiei electrice."]),
           B("b", "Date tehnice şi energetice aferente instalaţiei de producere a energiei electrice:"), B("b", "Generatoare asincrone şi sincrone:"),
           B("table", [["Nr. crt.", "Nr. UG", "Tip UG (As, S)", "Tip UG (T, H, E)", "U (V)", "Un UG (V)", "Pn UG (kW)", "Sn UG (kVA)", "Pi total (kW)",
                        "Pmax produsă de UG (kW)", "Pmin produsă de UG (kW)", "Qmax (kVAr)", "Qmin (kVAr)", "Sevac (kVA)", "Observaţii"],
                       [""] * 15, ["TOTAL:"] + [""] * 14], [9, 9, 11, 11, 10, 11, 11, 11, 11, 13, 13, 11, 11, 11, 13], True, 6.3),
           B("b", "Mijloace de compensare a energiei reactive:"), B("p", "[ X ] NU     [  ] DA" if not ctx.raw("compensation") else "[  ] NU     [ X ] DA"),
           B("table", [["Nr. crt.", "Tip echipament de compensare", "Qn (kVAr)", "Qmin (kVAr)", "Qmax (kVAr)", "Nr. trepte***", "Observaţii"], [""] * 7],
             [12, 48, 20, 20, 20, 22, 32], True),
           B("small", "***) Se completează dacă tipul de echipament de compensare utilizat are reglaj în trepte."),
           B("b", "Module generatoare de tip fotovoltaic:")]
    rows = [["Nr. crt.", "Nr. panouri", "Tip panou", "Pi panou (c.c.) (kW)", "Pi total panouri (c.c.) (kW)", "Pmax debitat de panouri (c.c.) (kW)",
             "Pi total panouri pe 1 invertor (c.c.) (kW)", "Observaţii"]]
    for i, p in enumerate(pr):
        total_panels = p["n"] * p["count"]
        total_kw = p["kw"] * p["count"]
        rows.append([str(i + 1), str(total_panels or ""), escape(p["model"]), f"{p['w'] / 1000:.3f}" if p["w"] else "",
                     f"{total_kw:.2f}" if total_kw else "", f"{total_kw:.2f}" if total_kw else "",
                     f"{p['kw']:.2f}" if p["kw"] else "", ""])
    tk = sum(p["kw"] * p["count"] for p in pr)
    total_panels = sum(p["n"] * p["count"] for p in pr)
    rows.append(["TOTAL:", str(total_panels) if total_panels else "", "", "", f"{tk:.2f}" if tk else "", f"{tk:.2f}" if tk else "", "", ""])
    out.append(B("table", rows, [12, 16, 30, 20, 24, 26, 28, 18], True))
    out.append(B("b", "Invertoare:"))
    rows = [["Nr. crt.", "Nr. invertoare", "Tipul invertoarelor", "Un invertor (c.a.) (V)", "Pi invertor (c.a.) (kW)", "Pmax invertor evacuată în reţea (c.a.) (kW)",
             "Pmax centrală formată din module generatoare (c.a.) (kW)", "Observaţii"]]
    tpi = tpm = 0
    total_inverters = 0
    for i, inv in enumerate(invs):
        count = max(1, int(num(inv.get("count") or inv.get("quantity"), 1)))
        pi = num(inv.get("p_nom_kw"))
        pm = 0 if inv.get("battery_only") or inv.get("no_panels") else (num(inv.get("p_limit_kw")) or num(inv.get("p_max_kw")) or pi)
        tpi += pi * count
        tpm += pm * count
        total_inverters += count
        un = "400" if "mono" not in str(inv.get("phases") or ("Trifazat" if tri else "Monofazat")).lower() else "230"
        observation = "Invertor hibrid doar cu baterie; putere evacuată 0 kW" if inv.get("battery_only") or inv.get("no_panels") else ""
        rows.append([str(i + 1), str(count), escape(inv.get("brand_model") or ""), un, f"{pi:.2f}" if pi else "",
                     f"{pm:.2f}" if pm is not None else "", f"{pm * count:.2f}" if pm is not None else "", observation])
    rows.append(["TOTAL:", str(total_inverters) if total_inverters else "", "", "", f"{tpi:.2f}" if tpi else "", f"{tpm:.2f}" if tpm else "", f"{tpm:.2f}" if tpm else "", ""])
    out += [B("table", rows, [12, 16, 34, 20, 20, 26, 30, 16], True),
            B("small", "NOTĂ:<br/>U.G. = unitate generatoare; panou = panou fotovoltaic; As - asincron; S - sincron; T - termo; H - hidro; E - eolian; "
                       "Qn - putere reactivă nominală; Qmax = putere reactivă maximă; Qmin = putere reactivă minimă; c.c. = curent continuu; c.a. = curent alternativ; "
                       "Pn = putere activă nominală; Pi = putere activă instalată; Pmax = putere activă maximă; Pmin = putere activă minimă; Sn = putere aparentă nominală; "
                       "Un = tensiune nominală la borne; U = tensiunea în punctul de racordare; Sevac = puterea aparentă aprobată pentru evacuare în reţea."),
            B("b", "Serviciile interne ale instalaţiei de producere:"),
            B("table", [["Pi servicii interne", f"{ctx.v('internal_pi')} kW"], ["Puterea maximă simultan absorbită servicii interne", f"{ctx.v('internal_pmax')} kW"]], [110, 64], False),
            B("p", "Anexez prezentei următoarele documente:"),
            B("bullets", ["a) copia actului de identitate, a certificatului de înregistrare la registrul comerţului sau a altor autorizaţii legale de funcţionare emise de autorităţile competente, după caz;",
                          "b) certificatul constatator (doar în cazul prosumatorului persoană juridică), în copie, emis de oficiul registrului comerţului, cu informaţii complete care să reflecte situaţia la zi a solicitantului, prin care se dovedeşte că persoana juridică nu desfăşoară ca activitate principală producerea de energie electrică;",
                          "c) procesul-verbal care confirmă recepţia la terminarea lucrărilor aferente instalaţiei de producere a energiei electrice şi instalaţiei de stocare, după caz, întocmit de executantul lucrării;",
                          "d) buletinul de încercare a prizei la pământ;",
                          "e) certificatele de conformitate şi fişele tehnice ale invertoarelor şi unităţilor generatoare cu datele şi funcţiile corespunzătoare, emise de fabricant, în copie, şi, după caz, fişele tehnice emise de fabricant, în copie, ale instalaţiei de stocare;",
                          "f) schema electrică monofilară a instalaţiei de producere a energiei electrice şi modul de racordare a acesteia în instalaţia de utilizare existentă, cu precizarea protecţiilor prevăzute şi reglajelor acestora."], False),
            B("p", "În sprijinul solicitării mele, transmit următoarele informaţii privind:"),
            B("p", "a) deţinerea de sisteme de stocare a energiei electrice produse din surse regenerabile:"),
            B("p", "[  ] NU DEŢIN.     [ X ] DEŢIN" if st else "[ X ] NU DEŢIN.     [  ] DEŢIN"),
            B("b", "Detalii sistem de stocare (datele se preiau din modelul selectat / fișa tehnică):"),
            B("table",
              [["Producător / model", "Nr. unități", "Capacitate kWh/unitate", "Tensiune V", "Capacitate Ah/unitate", "Imax A", "Schema / cuplare"]]
              + [[escape(str(b.get("model") or M)), escape(str(b.get("modules") if b.get("modules") is not None else M)),
                  escape(str(b.get("kwh") if b.get("kwh") is not None else M)),
                  escape(str(b.get("voltage") if b.get("voltage") is not None else M)),
                  escape(str(b.get("ah") if b.get("ah") is not None else M)),
                  escape(str(b.get("i_max") if b.get("i_max") is not None else M)),
                  escape(str(b.get("coupling") or M))]
                 for b in st]
              if st else [["Nu este selectat", M, M, M, M, M, M]],
              [30, 12, 23, 15, 20, 14, 25], True),
            B("p", "b) echipamentele de măsurare a energiei electrice montate în instalaţiile de utilizare, altele decât cele aparţinând operatorilor de distribuţie, "
                   "şi caracteristicile acestora, respectiv: serie contor, tip contor, date tehnice:"),
            B("p", "[  ] NU     [ X ] DA" if sl else "[ X ] NU     [  ] DA")]
    if sl:
        out.append(B("table", [["Nr. crt.", "Serie contor", "Tip contor", "Date tehnice"],
                               ["1", ctx.v("smart_meter_serial"), ctx.v("smart_meter_type"), ctx.v("smart_meter_data")]], [14, 40, 70, 50], True))
    out += [B("p", "Declar pe propria răspundere că datele şi informaţiile cuprinse în prezenta notificare sunt autentice şi că documentele anexate, în copie, sunt conforme cu originalul."),
            sign(["Data", f"<b>{ctx.date}</b>"], ["Reprezentantul firmei instalatoare,", f"<b>{ctx.rep}</b>", f"<b>{ctx.company}</b>", "semnătura și ștampila"])]
    return out


def doc_imputernicire(ctx):
    scope = ctx.raw("imputernicire_scope") or (f"accesul meu/nostru la rețeaua de distribuție a energiei electrice la nivelul Județului {ctx.raw('county')};\nobținerea avizului de amplasament."
                                                if ctx.raw("county") else None)
    items = [escape(x.strip()) for x in str(scope).split("\n") if x.strip()] if scope else [M]
    reg = "înregistrată la Registrul Comerțului sub numărul" if ctx.pj else "act de identitate cu seria și numărul"
    return hdr() + [
        B("r", "Număr înregistrare evidențe împuternicit: ............. / ....................."), B("title", "ÎMPUTERNICIRE"),
        B("p", f"Subsemnatul/-a/subscrisa <b>{ctx.name}</b>, domiciliat/-ă/sediul social în {ctx.v('hq_address')}, număr telefon mobil/fix* <b>{ctx.v('phone')}</b>, "
               f"număr fax ........................., adresă de poștă electronică (e-mail)* {ctx.v('email', '—')}, act de identitate cu seria și numărul/{reg}: "
               f"{ctx.v('regcom') if ctx.pj else ctx.v('ci_series')}, având CNP/CUI: <b>{ctx.v('idcode')}</b>"
               + (f", reprezentată prin domnul/-a <b>{ctx.v('rep_name')}</b>, în calitate de {ctx.v('rep_role')}" if ctx.pj else "") + ", prin prezenta"),
        B("c", "ÎMPUTERNICEȘTE"),
        B("p", f"pe subscrisa <b>{ctx.company}</b>, reprezentată legal prin domnul/-a <b>{ctx.rep}</b>, în calitate de reprezentant, cu sediul social în "
               f"{ctx.e('address')}, număr telefon mobil: <b>{ctx.e('phone')}</b>, număr fax ........................., adresă de poștă electronică "
               f"<b>{ctx.e('email')}</b>, înregistrată la Registrul Comerțului sub numărul: <b>{ctx.e('regcom')}</b>, având CUI: <b>{ctx.e('cui')}</b>, "
               f"pentru a mă reprezenta în relația cu Societatea: <b>{ctx.v('operator')}</b>."),
        B("p", "În exercitarea prezentei, împuternicitul <b>poate depune și ridica orice documente, poate efectua plăți, putând semna în numele și pe seama "
               "mea/noastră</b>, semnătura sa fiindu-mi pe deplin opozabilă, pentru formalități privind:"),
        B("bullets", [f"<b>{x}</b>" for x in items]),
        sign(["Semnătură reprezentat,", f"<b>{ctx.name}</b>", "semnătura", "(ștampilă societate)"],
             ["Semnătură reprezentant (împuternicit),", f"<b>{ctx.company}</b>", ctx.rep, "semnătura", "(ștampilă societate)"]),
        B("small", "(*) câmp obligatoriu de completat; în cazul necompletării fără documente justificative atașate, cererea va fi considerată neconformă.")]


def doc_storage(ctx):
    """Fișă separată pentru instalația de stocare, după structura dosarului ReEnergy."""
    bats = storage(ctx)
    rows = [["Nr.", "Producător / model", "Capacitate totală (kWh)", "kWh / modul", "Tensiune (V)",
             "Capacitate (Ah)", "Clasă (LV/HV)", "Cuplare", "Nr. module", "Serie"]]
    for i, b in enumerate(bats, 1):
        kwh_per_module = num(b.get("kwh"), None)
        modules = num(b.get("modules"), None)
        total_kwh = kwh_per_module * modules if kwh_per_module is not None and modules is not None else None
        rows.append([
            str(i), escape(str(b.get("model") or M)),
            fmt(total_kwh) if total_kwh is not None else M,
            fmt(kwh_per_module) if kwh_per_module is not None else M,
            escape(str(b.get("voltage") if b.get("voltage") is not None else M)),
            escape(str(b.get("ah") if b.get("ah") is not None else M)),
            escape(str(b.get("tech") or M)),
            escape(str(b.get("coupling") or M)),
            escape(str(b.get("modules") if b.get("modules") is not None else M)),
            escape(str(b.get("serial") or M)),
        ])
    if not bats:
        rows.append(["—", "Nu este declarat un sistem de stocare în datele dosarului", M, M, M, M, M, M, M, M])
    return hdr() + [
        B("title", "DATE DESPRE INSTALAȚIA DE STOCARE"),
        B("p", f"<b>Beneficiar:</b> {ctx.name}<br/><b>Loc de consum:</b> {ctx.loc}<br/><b>POD:</b> {ctx.v('pod')}"),
        B("table", rows, [5, 26, 15, 11, 12, 10, 10, 9, 9, 14], True),
        B("small", "Capacitatea totală este calculată din kWh pe modul și numărul de module. Datele provin din configurația dosarului; valorile lipsă trebuie verificate pe eticheta și fișa tehnică a echipamentului. Seria se completează la punerea în funcțiune."),
        sign(ex_sig(ctx), ben_sig(ctx)),
    ]


def doc_afm(ctx):
    afm = ctx.raw("afm")
    txt = M if not afm else ("ACCESEZ" if str(afm).lower().startswith("d") else "NU accesez")
    return hdr() + [
        B("title", "DECLARAȚIE"), B("c", f"Către {ctx.op_short}"),
        B("p", f"Subsemnatul, <b>{ctx.name}</b>, cu domiciliul/sediul în {ctx.v('hq_address')}, identificat cu CNP/CUI {ctx.v('idcode')}, declar pe proprie răspundere următoarele:"),
        B("p", f"Pentru instalarea unui sistem fotovoltaic la {ctx.loc}, <b>{txt}</b> programul privind instalarea sistemelor fotovoltaice pentru producerea "
               "energiei electrice în vederea acoperirii necesarului de consum și livrării surplusului în rețeaua națională, derulat prin Administrația Fondului pentru Mediu."),
        sign(["Data", f"<b>{ctx.date}</b>"], ["Nume și prenume,", f"<b>{ctx.name}</b>", "semnătura"])]


def doc_decl_executant(ctx):
    atr = ctx.raw("atr")
    return hdr() + [
        B("title", "DECLARAȚIA EXECUTANTULUI"), B("sub", f"conform art. 54 alin. (1) din Ordinul ANRE nr. 59/2013 · Nr. {ctx.v('doc_no')} din {ctx.date}"),
        B("p", f"<b>{ctx.company}</b>, cu sediul în {ctx.e('address')}, înregistrată la Oficiul Național al Registrului Comerțului sub nr. {ctx.e('regcom')}, cod unic de "
               f"înregistrare {ctx.e('cui')}, telefon {ctx.e('phone')}, e-mail {ctx.e('email')}, deținătoare a atestatului ANRE {ctx.e('anre_attest')}, reprezentată prin "
               f"{ctx.rep}, confirmăm prin prezenta declarație, pentru obiectivul cu cod loc de consum / POD {ctx.v('nlc', '—')} / {ctx.v('pod')}, situat în {ctx.loc}, "
               f"având ca beneficiar <b>{ctx.name}</b>, cu domiciliul/sediul în {ctx.v('hq_address')}, următoarele:"),
        B("bullets", [f"respectarea cerințelor din Avizul Tehnic de Racordare nr. {escape(str(atr)) if atr else '______________ / ____________'} emis de "
                      f"{ctx.v('operator')} pentru obiectivul mai sus menționat (dacă este cazul);",
                      "realizarea instalaţiei de utilizare în baza proiectului tehnic verificat în condițiile legii, cu respectarea normelor tehnice în vigoare la data "
                      "executării acesteia, inclusiv a prevederilor Normativului pentru proiectarea, execuţia şi exploatarea instalaţiilor electrice aferente clădirilor, "
                      "indicativ I7-2011, aprobat prin Ordinul ministrului dezvoltării regionale şi turismului nr. 2.741/2011, şi cu îndeplinirea condiţiilor care permit punerea ei sub tensiune."]),
        B("small", "Prezenta declarație a fost întocmită pe propria răspundere, cunoscând prevederile art. 326 din Codul Penal privind falsul în declarații."),
        sign(ex_sig(ctx), [])]


def doc_decl_conformitate(ctx):
    return hdr() + [
        B("title", "DECLARAȚIA DE CONFORMITATE privind calitatea lucrărilor"), B("sub", f"în conformitate cu art. 5 din HGR 1022/2002 · {ctx.date}"),
        B("p", f"<b>{ctx.company}</b>, cu sediul în {ctx.e('address')}, telefon {ctx.e('phone')}, email {ctx.e('email')}, înregistrată la Oficiul Național al Registrului "
               f"Comerțului sub nr. {ctx.e('regcom')}, cod unic de înregistrare {ctx.e('cui')}, atestat ANRE {ctx.e('anre_attest')}, asigurăm, garantăm și declarăm pe propria "
               "răspundere, conform prevederilor art. 5 din Hotărârea Guvernului nr. 1022/2002 privind regimul produselor și serviciilor care pot pune în pericol viața, "
               f"sănătatea, securitatea muncii și protecția mediului, că produsul/serviciul: <b>„INSTALAȚIE DE UTILIZARE CENTRALĂ FOTOVOLTAICĂ”</b>, montat la imobilul "
               f"aparținând <b>{ctx.name}</b>, din {ctx.loc}, cod loc consum / POD: {ctx.v('nlc', '—')} / {ctx.v('pod')}, la care se referă această declarație, nu pune în "
               "pericol viața, sănătatea, securitatea muncii, nu produce un impact negativ asupra mediului și este în conformitate cu:"),
        B("bullets", ["LEGEA nr. 319 din 14 iulie 2006 a securității și sănătății în muncă;", "FT 34/1983 „Executarea și repararea instalațiilor interioare din locuințe”;",
                      "Normativul I7/2011 și Ghidul GP 052/2000;", "Ordinul 163/2007, pentru aprobarea „Normelor generale de prevenire și stingere a incendiilor”;",
                      "HGR nr. 537/2007, privind stabilirea și sancționarea contravențiilor la normele de prevenire și stingere a incendiilor;",
                      "Legea 307/12 iulie 2006 privind apărarea împotriva incendiilor;", "Legea calității în construcții „Legea 10/1995”, publicată în Monitorul Oficial nr. 12/1995;",
                      "HGR 1022/2002 privind certificarea de conformitate."]),
        B("b", "AGENTUL ECONOMIC DECLARĂ ȘI GARANTEAZĂ că:"),
        B("bullets", ["Instalațiile au fost executate în baza proiectului tehnic verificat în condiţiile legii, cu respectarea normelor tehnice în vigoare la data executării, "
                      "inclusiv a prevederilor Normativului I7-2011, aprobat prin Ordinul ministrului dezvoltării regionale şi turismului nr. 2.741/2011, şi cu îndeplinirea condiţiilor care permit punerea ei sub tensiune;",
                      "Lucrările au fost verificate de responsabilul tehnic cu execuția, atestat în condițiile legii;",
                      "Sunt respectate condițiile de amplasare, distanțele și gabaritele prescrise față de alte instalații, construcții și sol;",
                      "Sunt respectate condițiile de protecție împotriva electrocutării conform reglementărilor legale, precum și cele indicate de producătorul aparatajului instalat;",
                      "Echipamentele, aparatajul și materialele utilizate sunt noi, de bună calitate și procurate pe cale legală, actele și documentația tehnică însoțitoare emisă de furnizor fiind depuse la dosarul instalației;",
                      "Societatea își asumă răspunderea pentru lucrările ascunse în pământ sau în construcție, acestea fiind realizate conform normativelor aplicabile, cu respectarea cantităților și calității materialelor încorporate;",
                      "Societatea își asumă răspunderea privind respectarea măsurilor de prevenire și stingere a incendiilor pentru instalația executată — instalația respectă prevederile Ord. nr. 163/2007;",
                      "Sunt îndeplinite toate condițiile tehnice și de instruire a beneficiarului pentru punerea în funcțiune a instalației executate;",
                      f"Perioada de garanție a lucrărilor executate este de {ctx.e('warranty_months')} de luni de la punerea în funcțiune, perioadă în care executantul se obligă să "
                      "remedieze fără plată orice defecțiune datorată nerespectării clauzelor și specificațiilor contractuale sau a prevederilor reglementărilor tehnice aplicabile."]),
        sign(ex_sig(ctx), ben_sig(ctx))]


def equipment_lines(ctx):
    rows = [["Echipament", "Cantitate", "Model / detalii"]]
    for inv in inverters(ctx):
        count = max(1, int(num(inv.get("count") or inv.get("quantity"), 1)))
        rows.append(["Invertor", f"{count} buc", escape(inv.get("brand_model") or M)])
        rsd = inv.get("rsd") or {}
        if rsd.get("enabled"):
            rows.append(["Oprire rapidă stringuri fotovoltaice (RSD)", "1 buc", escape(rsd.get("brand_model") or M)])
    for p in panel_rows(ctx):
        total_panels = int(num(p["n"]) * num(p.get("count"), 1))
        rows.append(["Panouri fotovoltaice", f"{total_panels} buc" if total_panels else M, escape(p["model"] or M)])
    for b in storage(ctx):
        rows.append(["Sistem de stocare", f"{b.get('modules') or 1} buc", escape(f"{b.get('model')} · {b.get('kwh') or ''} kWh")])
    if ctx.raw("smart_meter_type"):
        rows.append(["Smart meter", "1 buc", ctx.v("smart_meter_type")])
    if ctx.s.get("kit_bmp"):
        rows.append(["Kit panou electric (BMP)", "1 buc", ctx.e("kit_bmp")])
    if ctx.s.get("kit_structure"):
        rows.append(["Kit structură montaj + materiale electrice mărunte", "1 set", ctx.e("kit_structure")])
    return rows


def doc_pv_receptie(ctx):
    dec = ctx.raw("receptie_decision")
    others = ctx.v("receptie_others", "nu este cazul")
    out = hdr() + [
        B("title", "PROCES-VERBAL DE RECEPȚIE LA TERMINAREA LUCRĂRILOR"), B("sub", "privind lucrarea de realizare a centralei electrice fotovoltaice"),
        B("b", "1. Părțile"),
        B("p", f"<b>Beneficiar (investitor):</b> {ctx.name}, loc de consum {ctx.loc}, telefon {ctx.v('phone')}, cod identificare loc consum {ctx.v('nlc', '—')}, POD {ctx.v('pod')}"),
        B("p", f"<b>Executant:</b> {ctx.company}, cu sediul în {ctx.e('address')}, CUI {ctx.e('cui')}, nr. înreg. Registrul Comerțului {ctx.e('regcom')}, e-mail "
               f"{ctx.e('email')}, autorizată ANRE conform atestat {ctx.e('anre_attest')}, reprezentată prin {ctx.rep}."),
        B("b", "2. Obiectul recepției — centrala fotovoltaică compusă din:"), B("table", equipment_lines(ctx), [60, 24, 90], True),
        B("b", "3. Comisia de recepție"),
        B("p", f"Comisia de recepție și-a desfășurat activitatea la data de {ro_date(ctx.raw('receptie_date')) or M}, fiind formată din: {ctx.name} (beneficiar) și "
               f"{ctx.rep} (executant). Alte persoane participante: {others}."),
        B("b", "4. Constatările comisiei"),
        B("bullets", [escape(x.strip()) for x in str(ctx.raw("receptie_findings") or "").split("\n") if x.strip()] or [M]),
        B("b", "5. Hotărârea comisiei"),
        B("p", f"Comisia de recepție, în urma constatărilor făcute, propune: <b>{escape(str(dec)) if dec else M}</b>.")]
    if ctx.raw("receptie_motivation"):
        out.append(B("p", f"<b>Motivare:</b> {ctx.v('receptie_motivation')}"))
    if ctx.raw("receptie_recommendation"):
        out.append(B("p", f"<b>Recomandare:</b> {ctx.v('receptie_recommendation')}"))
    out.append(sign(ex_sig(ctx), ben_sig(ctx)))
    return out


def doc_serii(ctx):
    rows = [["Echipament", "Serie"]]
    cef = ctx.r.get("cef") or {}
    serials = (ctx.r.get("pif") or {}).get("serials") or {}
    inverter_serials = serials.get("inverters") or {}
    for i, inv in enumerate(inverters(ctx)):
        count = max(1, min(100, int(num(inv.get("count") or inv.get("quantity"), 1) or 1)))
        for unit in range(count):
            key = f"{i}.{unit}"
            label = f"Invertor {i + 1}" + (f" — unitatea {unit + 1}" if count > 1 else "")
            value = inverter_serials.get(key) or (inv.get("serial") if count == 1 else "")
            rows.append([f"{label} {escape(inv.get('brand_model') or '')}", escape(str(value or ""))])
    panel_serials = serials.get("panels")
    if isinstance(panel_serials, str):
        panel_serials = panel_serials.splitlines()
    # Keep empty slots between serial numbers: a missing serial must not shift
    # every following serial onto the wrong physical panel/model.
    panel_serials = [str(value).strip() for value in (panel_serials or [])]
    if not any(panel_serials) and ctx.raw("panel_serials"):
        legacy = str(ctx.raw("panel_serials"))
        panel_serials = [value.strip() for value in legacy.splitlines()]
    while panel_serials and not panel_serials[-1]:
        panel_serials.pop()

    panel_models_by_serial = []
    for inv in inverters(ctx):
        if inv.get("battery_only") or inv.get("no_panels"):
            continue
        quantity = max(1, min(100, int(num(inv.get("count") or inv.get("quantity"), 1) or 1)))
        for string in inv.get("strings") or []:
            panels = max(0, int(num(string.get("panels")))) * quantity
            model = string.get("panel_model") or inv.get("panel_model") or ""
            panel_models_by_serial.extend([model] * panels)

    # Match the Reenergy PIF layout: one line per configured panel, even when
    # its serial has not yet been recorded. Never invent a serial or a model.
    for i, model in enumerate(panel_models_by_serial):
        value = panel_serials[i] if i < len(panel_serials) else ""
        rows.append([f"Panou {i + 1} {escape(model)}".strip(), escape(value)])
    for i in range(len(panel_models_by_serial), len(panel_serials)):
        value = panel_serials[i]
        if value:
            rows.append([f"Panou suplimentar {i + 1 - len(panel_models_by_serial)} — model neidentificat", escape(value)])
    battery_serials = serials.get("batteries") or {}
    battery_items = []
    for i, inv in enumerate(cef.get("inverters") or []):
        battery = inv.get("battery") or {}
        if inv.get("battery_mode") == "own" and battery.get("model"):
            count = max(1, min(100, int(num(battery.get("modules") or battery.get("count"), 1) or 1)))
            battery_items.extend((f"inv-{i}-{unit}", f"Baterie invertor {i + 1}" + (f" — modulul {unit + 1}" if count > 1 else ""), battery.get("model"), battery.get("serial") if count == 1 else "") for unit in range(count))
    for i, battery in enumerate(cef.get("shared_batteries") or []):
        count = max(1, min(100, int(num(battery.get("modules") or battery.get("count"), 1) or 1)))
        battery_items.extend((f"shared-{i}-{unit}", f"Baterie {i + 1}" + (f" — modulul {unit + 1}" if count > 1 else ""), battery.get("model"), battery.get("serial") if count == 1 else "") for unit in range(count))
    if not battery_items:
        battery_items = [(f"legacy-{i}", "Baterie", b.get("model"), b.get("serial")) for i, b in enumerate(storage(ctx))]
    rows.extend([[f"{label} {escape(model or '')}", escape(str(battery_serials.get(key) or legacy_serial or ""))] for key, label, model, legacy_serial in battery_items])
    return hdr() + [B("title", "ANEXĂ — SERII ECHIPAMENTE"), B("table", rows, [90, 84], True),
                    sign(["Am predat — Executant,", f"<b>{ctx.company}</b>", ctx.rep, "semnătura și ștampila"], ["Am primit — Beneficiar,", f"<b>{ctx.name}</b>", "semnătura"])]
def doc_pv_pif(ctx):
    st = storage(ctx)
    invs = inverters(ctx)
    tests = ctx.r.get("tests") or {}
    dec = ctx.raw("pif_decision")
    pd = ro_date(ctx.raw("pif_date")) or M
    anti = ctx.raw("anti_relay_present")
    result_rows = [["Verificare", "Rezultat DA/NU", "Valori măsurate / observații"]]
    for i, label in enumerate(TESTS_A):
        item = tests.get(f"a{i}") or {}
        result_rows.append([label, escape(str(item.get("ok") or "")), escape(str(item.get("obs") or ""))])
    for i, (freq, duration) in enumerate(FREQ):
        item = tests.get(f"f{i}") or {}
        result_rows.append([f"Frecvență {freq} · {duration}", escape(str(item.get("ok") or "")), escape(str(item.get("obs") or ""))])
    for i, label in enumerate(CHECKS):
        item = tests.get(f"c{i}") or {}
        result_rows.append([label, escape(str(item.get("ok") or "")), escape(str(item.get("obs") or ""))])
    has_results = any((tests.get(f"{prefix}{i}") or {}).get("ok") or (tests.get(f"{prefix}{i}") or {}).get("obs")
                      for prefix, count in (("a", len(TESTS_A)), ("f", len(FREQ)), ("c", len(CHECKS)))
                      for i in range(count))
    return hdr() + [
        B("title", "PROCES-VERBAL DE PUNERE ÎN FUNCȚIUNE — FIȘĂ DE LUCRU"),
        B("sub", f"a sistemului de producere a energiei electrice — Centrala electrică fotovoltaică CEF {ctx.cef_kw}"),
        B("small", "Document precompletat cu datele salvate. Generarea nu confirmă efectuarea probelor, măsurători, conformitatea sau admiterea instalației. Completați constatările și decizia numai după verificarea efectivă; nu semnați o concluzie neconfirmată."),
        B("table", [["Denumire beneficiar", f"<b>{ctx.name}</b>"], ["Loc de consum", ctx.loc], ["POD", ctx.v("pod")],
                    ["Data introdusă pentru PIF", pd], ["Tip cerere AFM", (escape(str(ctx.raw('afm'))).upper() if ctx.raw("afm") else M)]], [50, 124], False),
        B("b", "Echipamente centrală fotovoltaică"),
        B("bullets", [f"Model invertor selectat: <b>{'; '.join(escape(i.get('brand_model') or '') for i in invs) or M}</b>",
                      f"Număr + model panouri: <b>{'; '.join(f'{p[chr(110)]} × {escape(p[chr(109)+chr(111)+chr(100)+chr(101)+chr(108)])} × {fmt(p[chr(119)], 0)} W' for p in panel_rows(ctx)) or M}</b>",
                      f"Sistem stocare selectat: <b>{'; '.join(escape(b.get('model')) for b in st) if st else 'NU este declarat în dosar'}</b>",
                      f"Bloc de măsură și utilizare: <b>{ctx.v('bmp_desc')}</b>",
                      f"Protecție antiinsularizare: <b>{escape(str(anti)).upper() if anti else 'NECONFIRMATĂ'}</b>"]),
        B("b", "I. Date executant"),
        B("p", f"Denumire instalator: {ctx.company}, {ctx.e('cui')}, {ctx.e('regcom')}, email: {ctx.e('email')}, telefon: {ctx.e('phone')}, reprezentant: {ctx.rep}, ANRE: {ctx.e('anre_attest')}"),
        B("b", "II. Verificări și constatări"),
        B("p", "Verificați instalația și consemnați rezultatul real pentru fiecare probă. Valorile și observațiile nu se deduc din modelul echipamentului."),
        B("table", result_rows, [78, 28, 68], True),
        B("b", "III. Concluzie"),
        B("p", f"Decizie introdusă în dosar: <b>{escape(str(dec)) if dec else 'NECOMPLETATĂ — se selectează după verificări'}</b>."),
        B("p", "Punerea sub tensiune se aprobă numai după completarea și verificarea rezultatelor, a protecțiilor și a documentelor aplicabile."),
        B("p", f"Nr. proces-verbal: {ctx.v('pif_no')} · Data PIF introdusă: {pd}"),
        B("small", "Acest model nu înlocuiește măsurătorile, probele la fața locului sau verificarea și semnarea de către persoanele competente."),
        sign(ex_sig(ctx, "Reprezentantul firmei executante,"), ben_sig(ctx)),
    ]




TESTS_A = ["Răspunsul la variațiile de frecvență — f > 50,2 Hz (RFA-CR)", "Răspunsul la variațiile de frecvență — f < 49,8 Hz (RFA-SC)",
           "Răspunsul la variațiile de frecvență — f ∈ (49,8–50,2) Hz", "Funcționarea în domeniul de frecvență (47,5–51,5 Hz)",
           "ROCOF — 2 Hz/s, fereastră de timp 500 ms", "ROCOF — 1,5 Hz/s, fereastră de timp 1 s", "ROCOF — 1,25 Hz/s, fereastră de timp 2 s",
           "Reconectarea automată la revenirea parametrilor (frecvență și tensiune)", "LVRT (FRT)", "Schimb de date între unitatea generatoare și EMS/DMS-SCADA"]
TESTS_A_CAT = ["Certificat de tip/rezultate teste efectuate de laboratoare recunoscute"] * 7 + [
    "Certificat de tip/rezultate teste efectuate de laboratoare recunoscute · Teste: după deconectarea prin protecții",
    "Certificat de tip/rezultate teste efectuate de laboratoare recunoscute (opțional)", "Dacă e cazul"]
FREQ = [("47,5–48,5 Hz", "Minimum 30 de minute"), ("48,5–49 Hz", "Minimum 30 de minute"), ("49–51 Hz", "Nelimitat"), ("51,0–51,5 Hz", "30 de minute")]
CHECKS = ["ROCOF — declarație producător", "Răspuns la variațiile de frecvență 50,2–51,5 Hz (statism, valoare de pornire 50,2 Hz)",
          "Scăderea Pmax la scăderea frecvenței sub 49 Hz", "Reconectare după defect (condiții, durată). Se acceptă în domeniul 47,5–50,2 Hz. Se testează la PIF",
          "Domeniul de tensiune", "Valorile setate protecții pentru tensiune și frecvență", "Capabilitatea de trecere peste defect (diagrama LVRT), dacă este cazul"]


def doc_pv_teste(ctx):
    invs = inverters(ctx)
    st = storage(ctx)
    t = ctx.r.get("tests") or {}
    pif_checks = ctx.r.get("pif_checks") or {}
    verdict = str(t.get("verdict") or "").strip()
    od_observations = str(t.get("od_observations") or "").strip()
    pif_fields = [
        ["Data procesului-verbal", ro_date(ctx.raw("pif_date")) or M],
        ["Serie contor producere", ctx.v("production_meter_serial")],
        ["Reprezentant OD prezent", ctx.v("pif_representative")],
        ["Început probe", ro_date(ctx.raw("pif_test_start")) or M],
        ["Sfârșit probe", ro_date(ctx.raw("pif_test_end")) or M],
        ["Data punerii sub tensiune", ro_date(ctx.raw("energize_date")) or M],
        ["Tensiune măsurată la punctul de delimitare (V)", ctx.v("pif_voltage_v")],
        ["Inginer semnatar", ctx.v("pif_engineer")],
    ]
    functional_checks = [
        ("Reglaje protecții (buletin reglaj)", "protection_settings"),
        ("Seriile corespund echipamentelor montate", "serials_confirmed"),
        ("Test anti-insularizare", "anti_islanding"),
        ("Priză de pământ (PRAM ≤ 4 Ω)", "pram_ok"),
    ]
    out = [B("p", f"Nr. proces-verbal: <b>{ctx.v('pif_no')}</b><br/>POD <b>{ctx.v('pod')}</b>"),
           B("title", "PROCES-VERBAL — TESTE ȘI VERIFICĂRI PIF"),
           B("sub", f"aferente instalației de utilizare și producere situată în {ctx.loc}"),
           B("small", "Fișă de lucru pentru completarea datelor și consemnarea probelor efectuate. Datele de recepție, tensiunile și verificările se introduc de personalul responsabil; nu sunt deduse sau completate automat."),
           B("b", "Date tehnice ale instalației de producere"),
           B("p", f"CEF {ctx.cef_kw} · POD {ctx.v('pod')}<br/>Serii invertor: {'; '.join(escape(i.get('serial')) for i in invs if i.get('serial')) or M}<br/>"
                  f"Modele invertor: {'; '.join(escape(i.get('brand_model') or '') for i in invs) or M}<br/>"
                  f"Sistem de stocare declarat: {'DA' if st else 'NU / nespecificat'}"),
           B("p", "Rezultatul probelor și verificărilor tehnice se consemnează mai jos numai după efectuarea lor efectivă."),
           B("b", "Date PV Teste și punere sub tensiune"),
           B("table", [["Câmp", "Valoare"]] + [[escape(label), value] for label, value in pif_fields], [60, 110], True),
           B("b", "Verificări funcționale consemnate"),
           B("table", [["Verificare", "Stare"]] + [[escape(label), "Confirmată" if pif_checks.get(key) is True else "Necompletată"] for label, key in functional_checks], [125, 45], True),
           B("pagebreak")] + hdr() + [
           B("title", "Teste și verificări — rezultate"),
           B("sub", "Ordin ANRE nr. 228/2018, cu modificările și completările aplicabile. Completați valorile obținute acolo unde se efectuează măsurători."),
           B("table", [["Tip test", "Referință / cerință", "Corespunde DA/NU", "Valori măsurate / observații"]]
             + [[x, TESTS_A_CAT[i], escape(str((t.get(f"a{i}") or {}).get("ok") or "")), escape(str((t.get(f"a{i}") or {}).get("obs") or ""))]
                for i, x in enumerate(TESTS_A)], [48, 62, 22, 42], True),
           B("table", [["Domeniul de frecvență", "Durata de funcționare", "Există DA/NU", "Observații"]]
             + [[f, d, escape(str((t.get(f"f{i}") or {}).get("ok") or "")), escape(str((t.get(f"f{i}") or {}).get("obs") or ""))]
                for i, (f, d) in enumerate(FREQ)], [42, 48, 30, 54], True),
           B("table", [["Verificare", "Există DA/NU", "Valori / observații"]]
             + [[x, escape(str((t.get(f"c{i}") or {}).get("ok") or "")), escape(str((t.get(f"c{i}") or {}).get("obs") or ""))]
                for i, x in enumerate(CHECKS)], [90, 30, 54], True),
           B("small", "Nu se bifează automat «DA» și nu se inventează valori. Dacă rezultatul sau observația lipsesc, câmpul rămâne necompletat."),
           B("table", [["Verdict recepție probe", escape(verdict) if verdict else "— necompletat —"],
                       ["Observații", escape(od_observations) if od_observations else "—"]], [42, 132], True),
           B("p", "Concluzia și declarația reprezentantului executantului se completează și se semnează numai după confirmarea rezultatelor de mai sus."),
           sign(ex_sig(ctx, "Reprezentantul firmei executante,"), [])]
    return out




def doc_buletin_priza(ctx):
    meas, psi = num(ctx.raw("grounding_ohm"), None), num(ctx.raw("soil_psi"), None)
    lim = num(ctx.raw("grounding_limit"), None)
    calc = meas * psi if meas is not None and psi is not None else None
    md = ctx.raw("measure_date")
    meter_device = str(ctx.raw("meter_device") or "").strip()
    meter_serial = str(ctx.raw("meter_serial") or "").strip()
    meter_valid = str(ctx.raw("meter_valid") or "").strip()
    measured = (all(value is not None for value in (meas, psi, lim)) and bool(md)
                and bool(meter_device) and bool(meter_serial) and bool(meter_valid))
    ok = ("DA" if calc <= lim else "NU") if measured else "NECOMPLETAT"
    valid = M
    if measured:
        try:
            valid = (datetime.fromisoformat(str(md)[:10]) + timedelta(days=365)).strftime("%d.%m.%Y")
        except ValueError:
            measured = False
            ok = "NECOMPLETAT"
    return hdr() + [
        B("title", ("BULETIN DE VERIFICARE ȘI MĂSURARE INSTALAȚII DE LEGARE LA PĂMÂNT" if measured else "FIȘĂ DE LUCRU — BULETIN PRAM NEFINALIZAT")),
        B("small", "Măsurătorile, datele aparatului și concluzia se completează numai după verificarea efectivă la fața locului; valorile lipsă nu sunt estimate." if not measured else "Document completat cu măsurătorile înregistrate și aparatul cu certificat metrologic valabil selectat în dosar."),
        B("sub", f"NR. {ctx.v('bulletin_no')} din {ro_date(md) or M}"),
        B("p", f"<b>Client:</b> {ctx.name} · <b>Adresa:</b> {ctx.loc}"),
        B("p", f"<b>Obiectivul:</b> {ctx.v('measure_object')} · <b>Data verificărilor/măsurătorilor:</b> {ro_date(md) or M}"),
        B("table", [["Verificarea/măsurarea instalațiilor de legare la pământ", "p.p. nr. 1"], ["Starea solului", ctx.v("soil")],
                    ["Valoarea coeficientului Ѱ (funcție de starea solului: 1,5 / 1,3 / 1,1)", f"{psi:.2f}" if psi is not None else M],
                    ["Valoarea rezistenței de dispersie măsurată (Ω)", f"{meas:.2f}" if meas is not None else M],
                    ["Valoarea rezistenței de dispersie calculată în funcție de starea solului (Ω)", f"<b>{calc:.2f}</b>" if calc is not None else M],
                    [f"Concluzii — corespunde (da/nu){f' · valoare admisă ≤ {fmt(lim)} Ω' if lim is not None else ''}", f"<b>{ok}</b>"]], [140, 34], True),
        B("p", f"<b>Aparat de măsură folosit:</b> {ctx.v('meter_device')} · <b>Seria:</b> {ctx.v('meter_serial')} · <b>Certificat metrologic valabil până la:</b> {ro_date(meter_valid) or M}"),

        B("small", f"Prezentul buletin de verificări este valabil 1 an de la data efectuării măsurătorii. Valabil până la <b>{valid}</b>." if measured else "Buletinul rămâne fișă de lucru până la înregistrarea măsurătorilor și selectarea aparatului cu metrologie valabilă."),
        sign(ex_sig(ctx, "Reprezentantul firmei executante,"), [])]


REGLAJ = [("u1", "Funcția protecție tensiune maximală treapta I"), ("u2", "Funcția protecție tensiune minimală treapta II"),
          ("f1", "Funcția de protecție de frecvență treapta I"), ("f2", "Funcția de protecție de frecvență treapta II"),
          ("u10", "Funcția de protecție maximă de tensiune (valoare mediată la 10 minute)"), ("rec", "Pornire inițială și repornire invertor după întrerupere tensiune RED"),
          ("hvrt", "Funcție HVRT"), ("lvrt", "Funcție LVRT"), ("droop", "Statism la variația frecvenței")]


def doc_buletin_reglaj(ctx):
    rg = ctx.r.get("reglaj") or {}
    invs = inverters(ctx)
    values_complete = all(
        str((rg.get(key) or {}).get("val") or "").strip()
        and str((rg.get(key) or {}).get("t") or "").strip()
        for key, _ in REGLAJ
    )
    verified = rg.get("verified_by_installer") is True and values_complete
    title = "BULETIN REGLAJ" if verified else "FIȘĂ DE LUCRU — REGLAJE INVERTOR"
    intro = (
        "a fost programat conform valorilor de protecție prezentate mai jos, verificate efectiv pe invertor, "
        "cu funcțiile de protecție active, conform Ordinului ANRE nr. 132/2020."
        if verified else
        "Document de lucru generat din datele dosarului. Valorile de mai jos nu confirmă programarea sau testarea invertorului. "
        "Completați după măsurare/verificare efectivă, apoi marcați confirmarea instalatorului."
    )
    rows = [[lbl, escape(str((rg.get(key) or {}).get("val") or "")), escape(str((rg.get(key) or {}).get("t") or ""))] for key, lbl in REGLAJ]
    story = [
        B("title", title),
        B("p", f"<b>Denumire beneficiar:</b> {ctx.name}<br/><b>Loc de consum centrală fotovoltaică:</b> {ctx.loc}<br/><b>CEF:</b> {ctx.cef_kw} · <b>POD:</b> {ctx.v('pod')}"),
        B("p", f"<b>Firmă:</b> {ctx.company} · {ctx.e('address')}"),
        B("p", "<br/>".join(f"Model invertor: <b>{escape(i.get('brand_model') or M)}</b> · Putere: <b>{fmt(num(i.get('p_nom_kw')))} kW</b>" for i in invs) or M),
        B("p", intro),
        B("table", [["PROTECȚIE", "Valoare declarată", "Timp (sec)"]] + rows, [110, 34, 30], True),
    ]
    if verified:
        story += [
            B("p", f"Subsemnatul <b>{ctx.name}</b>, în calitate de beneficiar, mă oblig să nu modific setările de protecție verificate mai sus."),
            sign(ex_sig(ctx, "Instalator,"), ben_sig(ctx)),
            B("p", f"Data: {ctx.date}"),
        ]
    return hdr() + story



def doc_autenticitate(ctx):
    rows = [["Nr. crt.", "Documente anexate cererii"]] + [[str(i + 1), escape(t)] for i, t in enumerate(ctx.opis_titles)]
    return hdr() + [
        B("title", "DECLARAȚIE AUTENTICITATE DATE ŞI CONFORMITATE CU ORIGINALUL"), B("sub", f"pentru locul de consum situat în {ctx.loc}"),
        B("p", f"Subsemnatul <b>{ctx.name}</b>, domiciliat în {ctx.v('hq_address')}, CNP/CUI: {ctx.v('idcode')}, confirm autenticitatea datelor cuprinse în cererea de "
               "racordare pentru locul de consum arătat mai sus şi declar pe propria răspundere că documentele anexate sunt conforme cu originalul."),
        B("table", rows, [16, 158], True), sign(["Data", f"<b>{ctx.date}</b>"], ben_sig(ctx))]


def doc_decl_beneficiar(ctx):
    return hdr() + [B("title", "DECLARAȚIE PE PROPRIA RĂSPUNDERE"), B("sub", "a titularului locului de consum"),
                    B("p", f"Subsemnatul(a) <b>{ctx.name}</b>, CNP/CUI <b>{ctx.v('idcode')}</b>, domiciliat(ă) în {ctx.v('hq_address')}, declar pe propria răspundere că mă oblig "
                           "să respect instrucțiunile de exploatare ale echipamentelor și să nu modific setările de protecție ale invertorului fără acordul operatorului de distribuție."),
                    sign(["Data", f"<b>{ctx.date}</b>"], ["Declarant,", f"<b>{ctx.name}</b>", "semnătura"])]


def doc_nota_gdpr(ctx):
    """DEER standard GDPR notice signed by the beneficiary.

    The official wording is not stored in code. When settings key ``gdpr_text``
    is present its body is rendered paragraph by paragraph (blank-line split);
    otherwise every official section heading is followed by a visible
    placeholder line so the document is obviously incomplete.
    """
    out = hdr() + [B("title", GDPR_TITLE)]
    body = ctx.s.get("gdpr_text")
    if body and str(body).strip():
        for para in re.split(r"\n\s*\n", str(body).strip()):
            para = para.strip()
            if para:
                out.append(B("p", escape(para).replace("\n", "<br/>")))
    else:
        for heading in GDPR_SECTIONS:
            out.append(B("b", heading))
            if heading == "DATELE NOASTRE DE CONTACT":
                out.append(B("p", f"Distribuția Energie Electrică România S.A. — sediul central: {M}<br/>"
                                  f"Telefon: {M} · E-mail: {M}<br/>"
                                  f"Responsabil cu protecția datelor (DPO): {M} · E-mail DPO: {M}"))
            else:
                out.append(B("p", GDPR_FILL))
    out.append(sign(["Data", f"<b>{ctx.date}</b>"], ben_sig(ctx)))
    return out


EQUIPMENT_SLOTS = [
    ("inverter_datasheet", "Fișă tehnică invertor"),
    ("inverter_cert", "Certificat de conformitate / EMC invertor"),
    ("module_datasheet", "Fișă tehnică modul fotovoltaic"),
    ("module_cert", "Certificat de conformitate modul fotovoltaic"),
    ("battery_datasheet", "Fișă tehnică baterie"),
    ("battery_cert", "Certificat de conformitate baterie"),
]


def equipment_slots(ctx):
    """Ordered equipment attachment slots for the technical documentation divider.

    Returns ``[(slot, label, path_or_None), ...]`` in the official sub-order
    (inverter datasheet, inverter certificate, module datasheet, module
    certificate, battery datasheet, battery certificate). ``path`` is the
    storage path from ``ctx.r["equipment_docs"][slot]["storage_path"]``.

    ``render()`` cannot resolve storage objects itself, so the caller
    (``server.py`` / the prosumator PDF route) must append each attached PDF
    after the divider page, in exactly this order.
    """
    docs = ctx.r.get("equipment_docs") or {}
    out = []
    for slot, label in EQUIPMENT_SLOTS:
        f = docs.get(slot) or {}
        path = f.get("storage_path") if isinstance(f, dict) else None
        out.append((slot, label, path or None))
    return out


def doc_documentatie_echipamente(ctx):
    """Divider page for manufacturer datasheets / conformity certificates.

    The attached PDFs themselves are merged by the route after this page; this
    builder only produces the cover/divider with the equipment inventory.
    """
    slots = {slot: path for slot, _label, path in equipment_slots(ctx)}
    rows = [["Nr.", "Echipament", "Model / detalii", "Document atașat (fișă tehnică / certificat)"]]
    n = 0
    for inv in inverters(ctx):
        n += 1
        attached = bool(slots.get("inverter_datasheet") or slots.get("inverter_cert"))
        rows.append([str(n), "Invertor", escape(inv.get("brand_model") or M), "DA" if attached else "—"])
    for p in panel_rows(ctx):
        n += 1
        attached = bool(slots.get("module_datasheet") or slots.get("module_cert"))
        rows.append([str(n), "Panouri fotovoltaice", escape(p.get("model") or M), "DA" if attached else "—"])
    for b in storage(ctx):
        n += 1
        attached = bool(slots.get("battery_datasheet") or slots.get("battery_cert"))
        rows.append([str(n), "Sistem de stocare", escape(f"{b.get('model')} · {b.get('kwh') or ''} kWh"), "DA" if attached else "—"])
    if n == 0:
        rows.append(["—", "Nu sunt configurate echipamente în dosar", M, "—"])
    return hdr() + [
        B("title", "DOCUMENTAȚIE TEHNICĂ ȘI CERTIFICATE DE CONFORMITATE ALE ECHIPAMENTELOR"),
        B("p", f"<b>Beneficiar:</b> {ctx.name}<br/><b>Loc de consum:</b> {ctx.loc}<br/><b>POD:</b> {ctx.v('pod')}"),
        B("p", "Prezenta secțiune cuprinde fișele tehnice și certificatele de conformitate ale echipamentelor, "
               "așa cum au fost puse la dispoziție de furnizorul de echipamente. Documentele atașate sunt inserate "
               "în continuare, în ordinea din tabel."),
        B("table", rows, [8, 34, 62, 70], True),
        B("small", "Coloana „Document atașat” indică dacă fișa tehnică / certificatul corespunzător este încărcat în dosar. "
                   "Documentele marcate cu „—” trebuie solicitate furnizorului de echipamente."),
    ]


def doc_schema(ctx):
    return [B("schema")]


# Official dossier order, read page by page from the company's signed reference
# dossier. Everything that iterates the dossier must use ORDER, never the
# insertion order of DOCS.
ORDER = [
    "notificare",
    "date_stocare",
    "nota_gdpr",
    "imputernicire",
    "declaratie_afm",
    "declaratie_executant",
    "declaratie_conformitate",
    "pv_receptie",
    "serii",
    "pv_pif",
    "buletin_priza",
    "buletin_reglaj",
    "declaratie_autenticitate",
    "schema_cef",
    "documentatie_echipamente",
]

# Documents usable individually but NOT part of the "all" bundle. The test
# protocol is delivered as its own PDF; the beneficiary declaration is an
# optional extra. ``schema`` is the legacy alias of ``schema_cef`` and stays
# individually available.
SEPARATE = ["pv_teste", "declaratie_beneficiar", "schema"]


DOCS = {
    "notificare": ("Anexa 2 — Notificare (Ord. ANRE 19/2022)", doc_notificare),
    "date_stocare": ("Date despre instalația de stocare", doc_storage),
    "nota_gdpr": ("Notă de informare GDPR (DEER)", doc_nota_gdpr),
    "schema_cef": ("Schemă monofilară", doc_schema),
    "declaratie_afm": ("Declarație accesare fonduri (AFM)", doc_afm),
    "buletin_reglaj": ("Buletin reglaj", doc_buletin_reglaj),
    "buletin_priza": ("Buletin de verificare și măsurare priză de pământ", doc_buletin_priza),
    "pv_pif": ("Proces-verbal de punere în funcțiune", doc_pv_pif),
    "pv_teste": ("PV teste și verificări PIF (Ord. ANRE 228/2018)", doc_pv_teste),
    "pv_receptie": ("Proces-verbal de recepție la terminarea lucrărilor", doc_pv_receptie),
    "serii": ("Anexă — serii echipamente", doc_serii),
    "declaratie_executant": ("Declarația executantului (Ord. ANRE 59/2013)", doc_decl_executant),
    "declaratie_conformitate": ("Declarație de conformitate (HGR 1022/2002)", doc_decl_conformitate),
    "imputernicire": ("Împuternicire", doc_imputernicire),
    "declaratie_autenticitate": ("Declarație autenticitate date și conformitate cu originalul (opis)", doc_autenticitate),
    "declaratie_beneficiar": ("Declarație beneficiar (suplimentar)", doc_decl_beneficiar),
    "documentatie_echipamente": ("Documentație tehnică și certificate de conformitate ale echipamentelor", doc_documentatie_echipamente),
    "schema": ("Schemă monofilară", doc_schema),
}


# ---------- PDF renderer ----------

def pdf_header(ctx):
    left = Paragraph(f"<b><font size=10>{ctx.company}</font></b><br/>{ctx.e('cui', '')} · {ctx.e('regcom', '')}<br/>Atestat ANRE {ctx.e('anre_attest', '')}", S["hdrl"])
    right = Paragraph(f"{ctx.e('phone', '')}<br/>{ctx.e('email', '')}<br/>{ctx.e('address', '')}", S["hdrr"])
    logo = _company_logo(ctx.s, 22 * mm, 13 * mm)
    if logo:
        left = Table([[logo, left]], colWidths=[24 * mm, 63 * mm])
        left.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
    t = Table([[left, right]], colWidths=[87 * mm, 87 * mm])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.6, GRID), ("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return [t, Spacer(1, 10)]


def pdf_table(rows, widths, head, fs=None, total_mm=174):
    st_c, st_h = S["cell"], S["cellb"]
    if fs:
        st_c = ParagraphStyle("cx", parent=S["cell"], fontSize=fs, leading=fs + 2)
        st_h = ParagraphStyle("hx", parent=S["cellb"], fontSize=fs, leading=fs + 2)
    total = sum(widths)
    cw = [w / total * total_mm * mm for w in widths]
    data = [[Paragraph(str(c), st_h if (head and i == 0) or (str(c).startswith("TOTAL")) else st_c) for c in row] for i, row in enumerate(rows)]
    t = Table(data, colWidths=cw, repeatRows=1 if head else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.5, GRID), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    if head:
        st.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef1f5")))
    t.setStyle(TableStyle(st))
    return t


def split_sig(lines):
    i = next((k for k, x in enumerate(lines) if x.startswith(("semnătura", "numele", "(ștampil"))), len(lines))
    return lines[:i], lines[i:]


IMG_LOADER = None
_IMG_CACHE = {}
DEFAULT_COMPANY_LOGO_B64 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brand-assets", "dns-energy-official.png.b64")


def _img(path, w, h):
    try:
        if path not in _IMG_CACHE:
            _IMG_CACHE[path] = IMG_LOADER(path)
        return Image(io.BytesIO(_IMG_CACHE[path]), width=w, height=h, kind="proportional")
    except Exception:
        return None

def company_logo_bytes(settings):
    logo_file = (settings or {}).get("header_logo") or {}
    path = logo_file.get("storage_path") if isinstance(logo_file, dict) else None
    if path and IMG_LOADER:
        try:
            data = IMG_LOADER(path)
            if data:
                return data
        except Exception:
            pass
    try:
        with open(DEFAULT_COMPANY_LOGO_B64, "rt", encoding="ascii") as logo:
            return base64.b64decode(logo.read().strip(), validate=True)
    except OSError:
        return None


def _company_logo(settings, w, h):
    logo_file = (settings or {}).get("header_logo") or {}
    path = logo_file.get("storage_path") if isinstance(logo_file, dict) else None
    logo = _img(path, w, h) if path else None
    if logo:
        return logo
    data = company_logo_bytes(settings)
    if data:
        try:
            return Image(io.BytesIO(data), width=w, height=h, kind="proportional")
        except Exception:
            pass
    return None


def _signature_paths(lines, s):
    # Names in the document may be HTML-escaped or differ only by case/diacritics.
    def norm(value):
        value = unescape(str(value or ""))
        value = unicodedata.normalize("NFKD", value)
        return re.sub(r"\s+", " ", "".join(ch for ch in value if not unicodedata.combining(ch))).casefold().strip()

    txt = norm(" ".join(str(line) for line in lines))
    paths = []
    for name, path in (s.get("_sigs") or {}).items():
        normalized_name = norm(name)
        if normalized_name and normalized_name in txt and path:
            paths.append(("signature", path))
            break
    company = norm(s.get("company"))
    has_company_sign_block = company and company in txt and ("semnatura" in txt or "stampila" in txt)
    if s.get("_stamp_path") and has_company_sign_block:
        paths.append(("stamp", s["_stamp_path"]))
    return paths


def sig_images(lines, s):
    if not IMG_LOADER:
        return []
    images = []
    for kind, path in _signature_paths(lines, s):
        width, height = (34, 14) if kind == "signature" else (24, 24)
        image = _img(path, width * mm, height * mm)
        if image:
            images.append(image)
    return images

def pdf_sign(left, right, s=None):
    def col(lines):
        if not lines:
            return ""
        top, bot = split_sig(lines)
        imgs = sig_images(lines, s or {})
        foot = f"<font size=8 color='#555555'>________________________________<br/>{'<br/>'.join(bot)}</font>"
        if not imgs:
            return Paragraph("<br/>".join(top) + "<br/><br/><br/>" + foot, S["sig"])
        row = Table([imgs], colWidths=[37 * mm] * len(imgs))
        row.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        return [Paragraph("<br/>".join(top), S["sig"]), row, Paragraph(foot, S["sig"])]
    if not right:
        t = Table([[col(left)]], colWidths=[174 * mm])
        t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    else:
        t = Table([[col(left), col(right)]], colWidths=[87 * mm, 87 * mm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return KeepTogether([Spacer(1, 14), t, Spacer(1, 8)])


def to_flow(blocks, ctx):
    out = []
    for b in blocks:
        k = b[0]
        if k == "hdr":
            out += pdf_header(ctx)
        elif k == "title":
            out.append(Paragraph(b[1], S["h"]))
        elif k in ("sub", "c", "p", "r", "b", "small"):
            if _has_pdf_placeholder(b[1]):
                continue
            out.append(Paragraph(b[1], S[k]))
        elif k == "bullets":
            out += [Paragraph(x, S["li"], bulletText="•" if (len(b) < 3 or b[2]) else None)
                    for x in b[1] if not _has_pdf_placeholder(x)]
        elif k == "table":
            rows = _clean_pdf_table(b[1])
            if rows:
                out += [pdf_table(rows, b[2], b[3], b[4] if len(b) > 4 else None), Spacer(1, 6)]
        elif k == "sign":
            out.append(pdf_sign(b[1], b[2], ctx.s))
        elif k == "pagebreak":
            out.append(PageBreak())
    return out


def _draft(c, doc):
    c.saveState()
    c.setFont("LSB", 70); c.setFillColor(colors.Color(0.8, 0.1, 0.1, alpha=0.12))
    w, h = c._pagesize
    c.translate(w / 2, h / 2); c.rotate(40); c.drawCentredString(0, 0, "CIORNĂ")
    c.restoreState()


def _test_watermark(c, doc):
    c.saveState()
    c.setFont("LSB", 25)
    c.setFillColor(colors.Color(0.72, 0.08, 0.08, alpha=0.24))
    w, h = c._pagesize
    c.translate(w / 2, h / 2)
    c.rotate(35)
    c.drawCentredString(0, 0, "TEST - DATE SINTETICE")
    c.restoreState()


def _dns_footer(c, doc, settings, logo_data):
    """Brand generated DNS Energy pages without altering attached official PDFs."""
    c.saveState()
    page_w, page_h = c._pagesize
    landscape_page = page_w > page_h
    margin = (12 if landscape_page else 18) * mm
    line_y = (8.5 if landscape_page else 11.5) * mm
    logo_y = (1.5 if landscape_page else 3.0) * mm
    c.setStrokeColor(colors.HexColor("#d8dee7"))
    c.setLineWidth(0.45)
    c.line(margin, line_y, page_w - margin, line_y)

    label_x = margin
    if logo_data:
        try:
            logo = ImageReader(io.BytesIO(logo_data))
            image_w, image_h = logo.getSize()
            scale = min((18 * mm) / image_w, (5 * mm) / image_h)
            rendered_w, rendered_h = image_w * scale, image_h * scale
            c.drawImage(logo, margin, logo_y, rendered_w, rendered_h, mask="auto")
            label_x += rendered_w + 2 * mm
        except Exception:
            pass
    c.setFont("LS", 6.5)
    c.setFillColor(colors.HexColor("#667085"))
    c.drawString(label_x, logo_y + (1.3 if landscape_page else 1.5) * mm,
                 "DNS Energy · dns-energy.ro")
    c.restoreState()


def render(doc_keys, rec, settings, client, opis_titles=None, draft=False):
    test_mode = bool((rec or {}).get("is_test"))
    ctx = Ctx(CEF.flatten(rec), settings, client, opis_titles)
    buf = io.BytesIO()
    pw, ph = A4
    watermark = _test_watermark if test_mode else (_draft if draft else None)
    logo_data = company_logo_bytes(settings)
    def on_page(c, doc):
        if watermark:
            watermark(c, doc)
        _dns_footer(c, doc, settings, logo_data)
    port = PageTemplate("port", [Frame(18 * mm, 14 * mm, pw - 36 * mm, ph - 28 * mm, id="fp")], pagesize=A4, onPage=on_page)
    land = PageTemplate("land", [Frame(12 * mm, 10 * mm, ph - 24 * mm, pw - 20 * mm, id="fl")], pagesize=landscape(A4), onPage=on_page)
    first_land = bool(doc_keys) and doc_keys[0] in ("schema_cef", "schema")
    pdf = BaseDocTemplate(buf, pageTemplates=[land, port] if first_land else [port, land], title=f"DNS Energy — {ctx.raw('name') or ''}")
    story = []
    keys = list(doc_keys)
    for i, k in enumerate(keys):
        if k in ("schema_cef", "schema"):
            def schema_paragraph(text, style="p"):
                return Spacer(1, 0) if _has_pdf_placeholder(text) else Paragraph(text, S[style])
            def schema_table(rows, widths, head=True):
                cleaned = _clean_pdf_table(rows)
                return pdf_table(cleaned, [x / mm for x in widths], head, None, 273) if cleaned else Spacer(1, 0)
            draw, tbl = schema_cef.story(ctx, schema_paragraph, schema_table, S)
            if i:
                story += [NextPageTemplate("land"), PageBreak()]
            story += draw + [PageBreak()] + tbl + [NextPageTemplate("port")]
            continue
        if i:
            story.append(PageBreak())
        blocks = DOCS[k][1](ctx)
        if k == "pv_receptie":
            seen_sign = False
            unique_blocks = []
            for block in blocks:
                if block[0] == "sign":
                    if seen_sign:
                        continue
                    seen_sign = True
                unique_blocks.append(block)
            blocks = unique_blocks
        if not any(isinstance(b, (list, tuple)) and b and b[0] == "sign" for b in blocks):
            blocks = blocks + [sign(ex_sig(ctx), ben_sig(ctx))]
        story += to_flow(blocks, ctx)
    pdf.build(story)
    return buf.getvalue()


# ---------- DOCX renderer ----------
def render_docx(doc_key, rec, settings, client, opis_titles=None, blocks=None, ctx=None):
    from docx import Document
    from docx.shared import Pt, Mm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.section import WD_ORIENT
    import pymupdf
    ctx = ctx or Ctx(CEF.flatten(rec), settings, client, opis_titles)
    d = Document()
    sec = d.sections[0]
    sec.page_width, sec.page_height = Mm(210), Mm(297)
    sec.left_margin = sec.right_margin = Mm(18)
    sec.top_margin = sec.bottom_margin = Mm(14)
    st = d.styles["Normal"]; st.font.name = "Arial"; st.font.size = Pt(10)

    def runs(p, text, size=None, bold=False):
        text = re.sub(r"<font[^>]*>|</font>", "", text).replace("<br/>", "\n")
        for part in re.split(r"(<b>.*?</b>)", text, flags=re.S):
            if not part:
                continue
            b = part.startswith("<b>")
            r = p.add_run(re.sub(r"</?b>", "", part).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#x27;", "'"))
            r.bold = b or bold
            if size:
                r.font.size = Pt(size)
        return p

    def para(text, align=None, size=None, bold=False):
        p = d.add_paragraph()
        if align:
            p.alignment = align
        return runs(p, text, size, bold)

    if isinstance(doc_key, (list, tuple)) and len(doc_key) == 1:
        doc_key = doc_key[0]
    keys = list(doc_key) if isinstance(doc_key, (list, tuple)) else None
    if blocks is None and doc_key in ("schema_cef", "schema"):
        sec.orientation = WD_ORIENT.LANDSCAPE
        sec.page_width, sec.page_height = Mm(297), Mm(210)
        pdfb = render([doc_key], rec, settings, client)
        src = pymupdf.open(stream=pdfb, filetype="pdf")
        for i, page in enumerate(src):
            if i:
                d.add_page_break()
            d.add_picture(io.BytesIO(page.get_pixmap(dpi=150).tobytes("png")), width=Mm(265))
    else:
        if blocks is None:
            blocks = []
            doc_keys = list(keys or [doc_key])
            # Official OD privacy notices are separate OPIS attachments, not generated DOCX templates.
            for i, k in enumerate(doc_keys):
                if i:
                    blocks.append(B("pagebreak"))
                doc_blocks = DOCS[k][1](ctx)
                if k == "pv_receptie":
                    seen_sign = False
                    unique_blocks = []
                    for block in doc_blocks:
                        if block[0] == "sign":
                            if seen_sign:
                                continue
                            seen_sign = True
                        unique_blocks.append(block)
                    doc_blocks = unique_blocks
                if not any(isinstance(b, (list, tuple)) and b and b[0] == "sign" for b in doc_blocks):
                    doc_blocks = doc_blocks + [sign(ex_sig(ctx), ben_sig(ctx))]
                blocks += doc_blocks
        for b in blocks:
            k = b[0]
            if k == "hdr":
                t = d.add_table(rows=1, cols=2)
                runs(t.cell(0, 0).paragraphs[0], f"<b>{ctx.company}</b>\n{ctx.e('cui', '')} · {ctx.e('regcom', '')}\nAtestat ANRE {ctx.e('anre_attest', '')}", 8)
                pr = t.cell(0, 1).paragraphs[0]; pr.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                runs(pr, f"{ctx.e('phone', '')}\n{ctx.e('email', '')}\n{ctx.e('address', '')}", 8)
                d.add_paragraph("_" * 86).runs[0].font.color.rgb = RGBColor(0x9a, 0xa7, 0xb8)
            elif k == "title":
                para(b[1], WD_ALIGN_PARAGRAPH.CENTER, 13, True)
            elif k == "sub":
                para(b[1], WD_ALIGN_PARAGRAPH.CENTER, 9.5)
            elif k == "c":
                para(b[1], WD_ALIGN_PARAGRAPH.CENTER, 10, True)
            elif k == "r":
                para(b[1], WD_ALIGN_PARAGRAPH.RIGHT)
            elif k == "b":
                para(b[1], None, 10, True)
            elif k == "small":
                para(b[1], None, 8)
            elif k == "p":
                para(b[1], WD_ALIGN_PARAGRAPH.JUSTIFY)
            elif k == "bullets":
                for x in b[1]:
                    runs(d.add_paragraph(style="List Bullet" if (len(b) < 3 or b[2]) else None), x)
            elif k == "table":
                rows = b[1]
                t = d.add_table(rows=len(rows), cols=len(rows[0])); t.style = "Table Grid"
                fs = 7 if len(rows[0]) > 8 else 8.5
                for i, row in enumerate(rows):
                    for j, c in enumerate(row):
                        runs(t.cell(i, j).paragraphs[0], str(c), fs, bold=(i == 0 and b[3]))
                d.add_paragraph()
            elif k == "sign":
                t = d.add_table(rows=1, cols=2)
                for j, lines in enumerate([b[1], b[2]]):
                    if lines:
                        p = t.cell(0, j).paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        top, bot = split_sig(lines)
                        runs(p, "\\n".join(top), 9)
                        if IMG_LOADER:
                            for kind, path in _signature_paths(lines, ctx.s):
                                try:
                                    raw_image = IMG_LOADER(path)
                                    if raw_image:
                                        width = Mm(34 if kind == "signature" else 24)
                                        p.add_run().add_picture(io.BytesIO(raw_image), width=width)
                                        p.add_run(" ")
                                except Exception:
                                    continue
                        runs(p, "\\n\\n________________________\\n" + "\\n".join(bot), 9)
                d.add_paragraph()
            elif k == "pagebreak":
                d.add_page_break()
    out = io.BytesIO()
    d.save(out)
    return out.getvalue()


