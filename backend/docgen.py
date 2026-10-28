import io
import os
import re
import math
from html import escape
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
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


ALIASES = {"idcode": ["cnp"], "name": ["client_name"]}


CLIENT_KEYS = {"name", "idcode", "kind", "regcom", "ci_series", "rep_name", "rep_role", "hq_address", "phone", "email", "iban", "bank",
               "address", "locality", "county", "pod", "nlc", "cadastral_nr", "cf_nr", "supplier", "operator"}


class Ctx:
    """Dossier data resolved from client sheet (client fields) / dossier record -> executant settings. Missing = None."""

    def __init__(self, rec, settings, client, opis_titles=None):
        self.r, self.s, self.c = rec, settings or {}, client or {}
        self.opis_titles = opis_titles or []
        self.used = set()

    def raw(self, k):
        self.used.add(k)
        order = (self.c, self.r) if (k in CLIENT_KEYS and self.c) else (self.r, self.c)
        for src in order:
            if src.get(k) not in (None, ""):
                return src.get(k)
        for a in ALIASES.get(k, []):
            for src in order:
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


# ---------- blocks ----------
def B(kind, *a):
    return (kind, *a)


def hdr():
    return [B("hdr")]


def sign(left, right):
    return B("sign", left, right)


def ex_sig(ctx, label="Executant,"):
    return [label, f"<b>{ctx.company}</b>", ctx.rep, "semnătura și ștampila"]


def ben_sig(ctx, label="Beneficiar,"):
    return [label, f"<b>{ctx.name}</b>", "semnătura"]


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
        n = sum(int(num(s.get("panels"))) for s in inv.get("strings") or [])
        w = num(inv.get("panel_w"))
        rows.append({"n": n, "model": inv.get("panel_model") or "", "w": w, "kw": n * w / 1000})
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
        rows.append([str(i + 1), str(p["n"] or ""), escape(p["model"]), f"{p['w'] / 1000:.3f}" if p["w"] else "", f"{p['kw']:.2f}" if p["kw"] else "",
                     f"{p['kw']:.2f}" if p["kw"] else "", f"{p['kw']:.2f}" if p["kw"] else "", ""])
    tk = sum(p["kw"] for p in pr)
    rows.append(["TOTAL:", "", "", "", f"{tk:.2f}" if tk else "", f"{tk:.2f}" if tk else "", "", ""])
    out.append(B("table", rows, [12, 16, 30, 20, 24, 26, 28, 18], True))
    out.append(B("b", "Invertoare:"))
    rows = [["Nr. crt.", "Nr. invertoare", "Tipul invertoarelor", "Un invertor (c.a.) (V)", "Pi invertor (c.a.) (kW)", "Pmax invertor evacuată în reţea (c.a.) (kW)",
             "Pmax centrală formată din module generatoare (c.a.) (kW)", "Observaţii"]]
    tpi = tpm = 0
    for i, inv in enumerate(invs):
        pi, pm = num(inv.get("p_nom_kw")), num(inv.get("p_limit_kw")) or num(inv.get("p_max_kw")) or num(inv.get("p_nom_kw"))
        tpi += pi; tpm += pm
        un = "400" if "mono" not in str(inv.get("phases") or ("Trifazat" if tri else "Monofazat")).lower() else "230"
        rows.append([str(i + 1), "1", escape(inv.get("brand_model") or ""), un, f"{pi:.2f}" if pi else "", f"{pm:.2f}" if pm else "", "", ""])
    rows.append(["TOTAL:", str(len(invs)) if invs else "", "", "", f"{tpi:.2f}" if tpi else "", f"{tpm:.2f}" if tpm else "", f"{tk:.2f}" if tk else "", ""])
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
            B("p", "b) echipamentele de măsurare a energiei electrice montate în instalaţiile de utilizare, altele decât cele aparţinând operatorilor de distribuţie, "
                   "şi caracteristicile acestora, respectiv: serie contor, tip contor, date tehnice:"),
            B("p", "[  ] NU     [ X ] DA" if sl else "[ X ] NU     [  ] DA")]
    if sl:
        out.append(B("table", [["Nr. crt.", "Serie contor", "Tip contor", "Date tehnice"],
                               ["1", ctx.v("smart_meter_serial"), ctx.v("smart_meter_type"), ctx.v("smart_meter_data")]], [14, 40, 70, 50], True))
    out += [B("p", "Declar pe propria răspundere că datele şi informaţiile cuprinse în prezenta notificare sunt autentice şi că documentele anexate, în copie, sunt conforme cu originalul."),
            sign(["Data", f"<b>{ctx.date}</b>"], ["Solicitant/Împuternicit,", f"<b>{ctx.name}</b>", "numele, prenumele şi semnătura"])]
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
    rows = [["Nr.", "Producător / model", "Capacitate nominală (kWh)", "Tensiune (V)", "Capacitate (Ah)",
             "Tehnologie", "Cuplare", "Nr. module", "Serie"]]
    for i, b in enumerate(bats, 1):
        rows.append([
            str(i), escape(str(b.get("model") or M)),
            escape(str(b.get("kwh") if b.get("kwh") is not None else M)),
            escape(str(b.get("voltage") if b.get("voltage") is not None else M)),
            escape(str(b.get("ah") if b.get("ah") is not None else M)),
            escape(str(b.get("tech") or M)),
            escape(str(b.get("coupling") or M)),
            escape(str(b.get("modules") if b.get("modules") is not None else M)),
            escape(str(b.get("serial") or M)),
        ])
    if not bats:
        rows.append(["—", "Nu este declarat un sistem de stocare în datele dosarului", M, M, M, M, M, M, M])
    return hdr() + [
        B("title", "DATE DESPRE INSTALAȚIA DE STOCARE"),
        B("p", f"<b>Beneficiar:</b> {ctx.name}<br/><b>Loc de consum:</b> {ctx.loc}<br/><b>POD:</b> {ctx.v('pod')}"),
        B("table", rows, [6, 27, 15, 10, 10, 12, 10, 10, 14], True),
        B("small", "Datele sunt preluate din configurația dosarului. Câmpurile marcate cu „—” trebuie completate/verificate pe baza etichetei și fișei tehnice a echipamentului."),
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
        rows.append(["Invertor", "1 buc", escape(inv.get("brand_model") or M)])
    for p in panel_rows(ctx):
        rows.append(["Panouri fotovoltaice", f"{p['n']} buc" if p["n"] else M, escape(p["model"] or M)])
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
    for inv in inverters(ctx):
        rows.append([f"Invertor {escape(inv.get('brand_model') or '')}", escape(inv.get("serial") or "")])
    for p in panel_rows(ctx):
        rows.append([f"{p['n']}× panou {escape(p['model'])}", escape(ctx.raw("panel_serials") or "")])
    for b in storage(ctx):
        rows.append([f"Baterie {escape(b.get('model'))}", escape(b.get("serial") or "")])
    return hdr() + [B("title", "ANEXĂ — SERII ECHIPAMENTE"), B("table", rows, [90, 84], True),
                    sign(["Am predat — Executant,", f"<b>{ctx.company}</b>", ctx.rep, "semnătura și ștampila"], ["Am primit — Beneficiar,", f"<b>{ctx.name}</b>", "semnătura"])]


def doc_pv_pif(ctx):
    st = storage(ctx)
    invs = inverters(ctx)
    dec = ctx.raw("pif_decision")
    pd = ro_date(ctx.raw("pif_date")) or M
    anti = ctx.raw("anti_relay_present")
    return hdr() + [
        B("title", "PROCES-VERBAL DE PUNERE ÎN FUNCȚIUNE FINALĂ"),
        B("sub", f"a sistemului de producere a energiei electrice — Centrala electrică fotovoltaică CEF {ctx.cef_kw}"),
        B("table", [["Denumire beneficiar", f"<b>{ctx.name}</b>"], ["Loc de consum", ctx.loc], ["POD", ctx.v("pod")],
                    ["Tip cerere AFM", (escape(str(ctx.raw('afm'))).upper() if ctx.raw("afm") else M)]], [50, 124], False),
        B("b", "Echipamente centrală fotovoltaică"),
        B("bullets", [f"Model invertor utilizat (acreditat de Operatorul de Distribuție): <b>{'; '.join(escape(i.get('brand_model') or '') for i in invs) or M}</b>",
                      f"Număr + model panouri fotovoltaice: <b>{'; '.join(f'{p[chr(110)]} × {escape(p[chr(109)+chr(111)+chr(100)+chr(101)+chr(108)])} × {fmt(p[chr(119)], 0)} W' for p in panel_rows(ctx)) or M}</b>",
                      f"Sistem stocare: <b>{'; '.join(escape(b.get('model')) for b in st) if st else 'NU'}</b>",
                      f"Existența blocului de măsură și utilizare sigilabil, dimensionat conform puterii instalate în centrala fotovoltaică, între invertor și tabloul "
                      f"electric al clientului: <b>{ctx.v('bmp_desc')}</b>",
                      "Existența protecției suplimentare privind montarea releului de antiinsularizare la CEF cu P>30 kWp (cf. ORD. ANRE 132/2020 art. 1 pct. 6, art. 2a): "
                      f"<b>{escape(str(anti)).upper() if anti else M}</b>"]),
        B("b", "I. Date generale"),
        B("p", f"Denumire instalator: {ctx.company}, {ctx.e('cui')}, {ctx.e('regcom')}, email: {ctx.e('email')}, telefon: {ctx.e('phone')}, contact: {ctx.rep}, ANRE: {ctx.e('anre_attest')}"),
        B("p", f"Comisia de recepție convocată la data de {pd}."),
        B("b", "II. Constatări"),
        B("p", "În calitate de instalator autorizat ANRE, atestăm că această lucrare corespunde din punct de vedere tehnic și electric, cu respectarea cerințelor din "
               "Ordinele ANRE 59/2013, 228/2018, 132/2020, 15/2022, 19/2022, 133/2022, 4/2023, a condițiilor tehnice în vigoare care permit punerea sub tensiune, inclusiv "
               "a celor de protecție a muncii și PSI, normelor, prescripțiilor și normativelor în vigoare, respectiv a normativului I7, în vigoare cu actualizările aferente, "
               "punându-se astfel sub tensiune în perioada de probă finală."),
        B("p", "a) În urma examinării documentației prezentate, a rezultatelor probelor tehnologice și a cercetării pe teren a lucrărilor executate s-a constatat: "
               "respectarea ORD ANRE 15/2022, ORD ANRE 19/2022, ORD ANRE 133/2022, ORD ANRE 132/2020. <b>INSTALAȚIA FOTOVOLTAICĂ POATE FI PUSĂ SUB TENSIUNE</b> de către "
               "Operatorul de Distribuție / instalatorul sistemului fotovoltaic și respectă normativul I7."),
        B("p", "b) Au fost efectuate probele și s-au verificat condițiile tehnice de racordare la rețelele electrice de interes public pentru prosumatorul cu injecție de "
               "putere activă în rețea, în conformitate cu Ordinul ANRE nr. 228/2018 cu modificările și completările ulterioare, și s-au constatat următoarele:"),
        B("bullets", [f"reconectarea instalațiilor de producere la rețeaua electrică s-a realizat după un interval de {ctx.v('reconnect_min')} minute de la reapariția tensiunii în rețea;",
                      "s-a verificat nefuncționarea centralei în regim insularizat, prin dotarea cu protecții care întrerup injecția puterii active în rețea la apariția unui asemenea regim;",
                      "s-a realizat protecția instalației de producere, a invertoarelor componente și a instalațiilor auxiliare, împotriva defectelor din instalațiile proprii sau împotriva impactului rețelei electrice asupra acestora;",
                      "prosumatorul asigură în punctul de racordare/delimitare calitatea energiei electrice în conformitate cu standardele în vigoare;",
                      "se respectă Standardul de Performanță privind evacuarea surplusului de energie electrică în rețeaua electrică de JT/MT aferentă Operatorului de Distribuție;",
                      "se respectă ORD. ANRE 15/2022, actualizat prin ORD. ANRE 19/2022, privind montarea unui bloc de măsură și protecție sigilabil în instalația de utilizare, dimensionat conform puterii instalate, racordat între invertorul fotovoltaic și tabloul electric general al beneficiarului;",
                      "se respectă ORD. ANRE 132/2020 privind implementarea reglajelor de interfață asupra invertorului, astfel încât la debitarea surplusului nivelul tensiunii în punctul de delimitare se încadrează în Standardul de Performanță."], False),
        B("p", "În conformitate cu cele menționate anterior, declarăm pe propria răspundere faptul că Operatorul de Distribuție poate instala în cadrul blocului de măsură "
               "și protecție montat în instalația de utilizare contorul de energie electrică ce va înregistra cantitatea de energie electrică produsă de centrala fotovoltaică "
               "(cf. art. 45 alin. 1 lit. a1 din Legea nr. 123/2012)."),
        B("p", "c) Alte constatări: prosumatorul are obligația să exploateze și să întrețină instalațiile proprii în conformitate cu prescripțiile în vigoare, fiind răspunzător "
               "de orice modificare neautorizată ulterioară adusă instalației de producere fără înștiințarea Operatorului de Distribuție Regional."),
        B("b", "III. Concluzii"),
        B("p", f"1. Pe baza constatărilor și concluziilor consemnate mai sus, comisia de recepție hotărăște: <b>{escape(str(dec)) if dec else M}</b>."),
        B("p", "2. Modificarea sistemului fotovoltaic, a protecțiilor și reglajelor de interfață, în mod diferit față de ORD. ANRE 132/2020, înainte, în cadrul perioadei de "
               "probă sau după punerea în funcțiune finală, îi permite Operatorului de Distribuție deconectarea sistemului fotovoltaic de la rețea până la remedierea neconformităților."),
        B("p", "3. Beneficiarul se angajează să informeze Operatorul de Distribuție pentru orice modificare survenită în instalația de utilizare a grupului generator, după "
               "punerea în funcțiune a acestuia în perioada de probă / după emiterea Certificatului de Racordare tip Prosumator."),
        B("p", f"4. Prezentul proces-verbal a fost încheiat azi {pd}, în două exemplare originale."),
        B("p", "5. Cunoscând prevederile art. 326 din Codul Penal cu privire la falsul în declarații, declarăm (atât beneficiarul, cât și instalatorul sistemului fotovoltaic) "
               "pe propria răspundere faptul că documentele depuse la Dosarul de Prosumator corespund realității, iar cele prezentate în format electronic sunt conforme cu originalul."),
        B("small", "NOTĂ: după emiterea Certificatului de Racordare tip Prosumator, beneficiarul se angajează să informeze furnizorul de energie electrică în vederea întocmirii Contractului de Furnizare tip Prosumator."),
        sign(ex_sig(ctx, "Instalator/Executant,"), ben_sig(ctx)),
        B("p", "Observații OD: ________________________________________________________________")]


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
    pd = ro_date(ctx.raw("pif_date")) or M
    period = f"{ro_date(ctx.raw('test_from')) or M} — {ro_date(ctx.raw('test_to')) or M}"
    out = [B("p", f"Nr. înregistrare OD …………………………………/…………………………………<br/>aferent cererii de punere sub tensiune nr. …………………………………<br/>POD <b>{ctx.v('pod')}</b>"),
           B("title", "PROCES VERBAL"), B("sub", f"de efectuare a testelor și verificărilor de punere în funcțiune a instalației de utilizare și producere<br/>situată în {ctx.loc}"),
           B("p", f"încheiat azi {pd} cu ocazia efectuării testelor și verificărilor de punere în funcțiune a instalației de utilizare/producere {ctx.cef_kw}"),
           B("b", "Datele tehnice ale instalației de producere:"),
           B("p", f"1. Seria invertorului: {'; '.join(escape(i.get('serial')) for i in invs if i.get('serial')) or M}<br/>tipul invertorului: "
                  f"<b>{'; '.join(escape(i.get('brand_model') or '') for i in invs) or M}</b>"),
           B("p", f"2. Montajul CEF {ctx.cef_kw} este în conformitate cu ATR {ctx.v('atr')}"),
           B("p", f"3. Tipul / seria contorului montat de prosumator pe partea de producere este {ctx.v('production_meter')}"),
           B("p", f"4. Sistemul [ {'Da' if st else 'Nu'} ] are sistem de stocare"),
           B("p", f"În perioada {period} au fost efectuate testele și s-au verificat condițiile tehnice de racordare la RED pentru prosumatorul cu injecție de "
                  "putere activă în rețea, în conformitate cu Ord. ANRE 228/2018 cu modificările și completările ulterioare."),
           B("p", "S-au constatat următoarele:"),
           B("bullets", [f"1. Reconectarea instalațiilor de producere a energiei electrice aparținând prosumatorului, la rețeaua electrică s-a realizat după {ctx.v('reconnect_min')} minute de la reapariția tensiunii în rețea;",
                         "2. S-a verificat nefuncționarea centralei în regim insularizat, aceasta realizându-se prin dotarea cu protecții/protecții integrate a echipamentului care să întrerupă injecția puterii active în rețea a prosumatorului la apariția unui asemenea regim;",
                         "3. S-a realizat protecția instalației de producere a energiei electrice, a invertorului/invertoarelor componente și a instalațiilor auxiliare, (după caz a sistemului de stocare a energiei) și a instalației electrice aferente locului de consum împotriva defectelor din instalațiile proprii și împotriva impactului rețelei electrice asupra acestora, la acționarea protecțiilor de declanșare a prosumatorului ori la incidente în rețea (supratensiuni tranzitorii, acționări ale protecțiilor în rețea, scurtcircuite cu și fără punere la pământ), cât și în cazul apariției unor condiții tehnice excepționale/anormale de funcționare;",
                         "4. Prosumatorul cu injecție de putere activă în rețea asigură în punctul de racordare/delimitare (după caz), calitatea energiei electrice în conformitate cu standardele în vigoare."], False),
           B("p", f"Subsemnatul {ctx.rep}, reprezentant al firmei executante {ctx.company} (atestat ANRE {ctx.e('anre_attest')}, cu valabilitate până la "
                  f"{ro_date(ctx.s.get('anre_valid')) or M}), declar că instalația de producere a fost realizată cu respectarea normativelor, reglementărilor, prescripțiilor și legislației în vigoare și se poate pune în funcțiune."),
           B("p", "<b>Atât Executantul cât și Prosumatorul au obligația ca, până la încheierea contractului de vânzare-cumpărare între Prosumator și Furnizorul de energie "
                  "electrică, SĂ NU INJECTEZE ENERGIE ELECTRICĂ în rețeaua operatorului de distribuție.</b> De asemenea, Prosumatorul și Executantul (cu drepturi de "
                  "parametrizare a invertorului) își asumă responsabilitatea pentru menținerea în funcțiune a tuturor protecțiilor, respectiv menținerea parametrilor testați aferenți unității de producție (inclusiv a invertorului)."),
           sign(["Prosumator,", f"<b>{ctx.name}</b>", "semnătura"], ["Reprezentant firmă executantă<br/>care a verificat și efectuat testele,", ctx.rep, "semnătura și ștampila"]),
           B("b", "Observații OD privind instalația de utilizare de la locul de consum și producere"),
           B("p", "OD a sigilat: [  ] contorul pe partea de producere, din instalația prosumatorului<br/>[  ] contorul pe sistemul de stocare<br/>[  ] contorul în punctul de delimitare"),
           B("p", "Observații (dacă este cazul)<br/>………………………………………………………………………………………………………<br/>………………………………………………………………………………………………………"),
           B("p", "Data …………………………………<br/>Reprezentant OD,<br/>…………………………………"),
           B("pagebreak")] + hdr() + [
           B("title", "Teste și Verificări"),
           B("sub", "aferente Normei Tehnice „Condiții tehnice de racordare la rețelele electrice de interes public pentru prosumatorii cu injecție de putere activă în rețea” — "
                    "Ordin ANRE nr. 228/2018 cu modificările și completările ulterioare —<br/>anexă la procesul verbal de efectuare a probelor de punere în funcțiune a instalației de utilizare și producere — de categorie A — (PGM)"),
           B("table", [["Tip Test", "Categoria A", "Corespunde DA/NU", "Observații*"]] +
             [[x, TESTS_A_CAT[i], escape(str((t.get(f"a{i}") or {}).get("ok") or "")), escape(str((t.get(f"a{i}") or {}).get("obs") or ""))] for i, x in enumerate(TESTS_A)],
             [55, 70, 22, 27], True),
           B("small", "* Acolo unde se fac teste se vor trece valorile obținute.<br/>Certificatul de echipament conține: domeniul de frecvență — durate, valoare frecvență; se verifică și protecțiile."),
           B("table", [["Domeniul de frecvență", "Durata de funcționare", "Există (DA/NU)", "Observații"]] +
             [[f, d, escape(str((t.get(f"f{i}") or {}).get("ok") or "")), escape(str((t.get(f"f{i}") or {}).get("obs") or ""))] for i, (f, d) in enumerate(FREQ)],
             [45, 55, 30, 44], True),
           B("table", [["", "Există (DA/NU)", "Observații"]] +
             [[x, escape(str((t.get(f"c{i}") or {}).get("ok") or "")), escape(str((t.get(f"c{i}") or {}).get("obs") or ""))] for i, x in enumerate(CHECKS)],
             [110, 30, 34], True),
           B("b", "Notă"),
           B("p", f"Prezenta se anexează la Procesul Verbal nr. {ctx.v('pif_no', '—')} din data de {pd} de efectuare a probelor de punere în funcțiune a instalației de utilizare și producere situată în {ctx.loc}."),
           B("p", "Acolo unde verificarea conformității se bazează pe certificatele de echipamente ale unității generatoare, se vor anexa și acestea."),
           sign(["Prosumator,", f"<b>{ctx.name}</b>", "semnătura"], ["Reprezentant firmă executantă<br/>care a verificat și efectuat testele,", ctx.rep, "semnătura și ștampila"])]
    return out


def doc_buletin_priza(ctx):
    meas, psi = num(ctx.raw("grounding_ohm"), None), num(ctx.raw("soil_psi"), None)
    lim = num(ctx.raw("grounding_limit"), None)
    calc = meas * psi if meas is not None and psi is not None else None
    ok = ("DA" if calc <= lim else "NU") if calc is not None and lim is not None else M
    md = ctx.raw("measure_date")
    valid = (datetime.fromisoformat(str(md)[:10]) + timedelta(days=365)).strftime("%d.%m.%Y") if md else M
    return hdr() + [
        B("title", "BULETIN DE VERIFICARE ȘI MĂSURARE INSTALAȚII DE LEGARE LA PĂMÂNT"), B("sub", f"NR. {ctx.v('bulletin_no')} din {ro_date(md) or M}"),
        B("p", f"<b>Client:</b> {ctx.name} · <b>Adresa:</b> {ctx.loc}"),
        B("p", f"<b>Obiectivul:</b> {ctx.v('measure_object')} · <b>Data verificărilor/măsurătorilor:</b> {ro_date(md) or M}"),
        B("table", [["Verificarea/măsurarea instalațiilor de legare la pământ", "p.p. nr. 1"], ["Starea solului", ctx.v("soil")],
                    ["Valoarea coeficientului Ѱ (funcție de starea solului: 1,5 / 1,3 / 1,1)", f"{psi:.2f}" if psi is not None else M],
                    ["Valoarea rezistenței de dispersie măsurată (Ω)", f"{meas:.2f}" if meas is not None else M],
                    ["Valoarea rezistenței de dispersie calculată în funcție de starea solului (Ω)", f"<b>{calc:.2f}</b>" if calc is not None else M],
                    [f"Concluzii — corespunde (da/nu){f' · valoare admisă ≤ {fmt(lim)} Ω' if lim is not None else ''}", f"<b>{ok}</b>"]], [140, 34], True),
        B("p", f"<b>Aparat de măsură folosit:</b> {ctx.e('meter_device')} · seria {ctx.e('meter_serial')} · buletin metrologic valabil până la {ro_date(ctx.s.get('meter_valid')) or M}"),
        B("small", f"Prezentul buletin de verificări este valabil 1 an de la data efectuării măsurătorii. Valabil până la <b>{valid}</b>."),
        sign(["Verificat,", f"<b>{ctx.company}</b>", ctx.rep, "semnătura și ștampila"], ben_sig(ctx))]


REGLAJ = [("u1", "Funcția protecție tensiune maximală treapta I"), ("u2", "Funcția protecție tensiune minimală treapta II"),
          ("f1", "Funcția de protecție de frecvență treapta I"), ("f2", "Funcția de protecție de frecvență treapta II"),
          ("u10", "Funcția de protecție maximă de tensiune (valoare mediată la 10 minute)"), ("rec", "Pornire inițială și repornire invertor după întrerupere tensiune RED"),
          ("hvrt", "Funcție HVRT"), ("lvrt", "Funcție LVRT"), ("droop", "Statism la variația frecvenței")]


def doc_buletin_reglaj(ctx):
    rg = ctx.r.get("reglaj") or {}
    invs = inverters(ctx)
    return hdr() + [
        B("title", "BULETIN REGLAJ"),
        B("p", f"<b>Denumire beneficiar:</b> {ctx.name}<br/><b>Loc de consum centrală fotovoltaică:</b> {ctx.loc}<br/><b>CEF:</b> {ctx.cef_kw} · <b>POD:</b> {ctx.v('pod')}"),
        B("p", f"Noi, firma <b>{ctx.company}</b>, cu sediul în {ctx.e('address')}, declarăm că invertorul:"),
        B("p", "<br/>".join(f"Model invertor utilizat: <b>{escape(i.get('brand_model') or M)}</b> · Putere: <b>{fmt(num(i.get('p_nom_kw')))} kW</b>" for i in invs) or M),
        B("p", "a fost programat conform valorilor de protecție prezentate mai jos în tabelul reglajelor, cu funcțiile de protecție active și implementate în unitatea de "
               "producție fotovoltaică executată la adresa mai sus menționată, conform Ordinului ANRE nr. 132/2020."),
        B("table", [["PROTECȚIE", "Valoare setată", "Timp (sec)"]] +
          [[lbl, escape(str((rg.get(k) or {}).get("val") or "")), escape(str((rg.get(k) or {}).get("t") or ""))] for k, lbl in REGLAJ], [110, 34, 30], True),
        B("p", f"Subsemnatul <b>{ctx.name}</b>, în calitate de beneficiar, mă oblig să nu modific setările de protecție mai sus menționate și să nu permit accesul "
               "persoanelor neautorizate în instalația CEF executată, în scopul modificării parametrilor de funcționare implementați în invertor la punerea în funcțiune."),
        sign(ex_sig(ctx, "Instalator,"), ben_sig(ctx)), B("p", f"Data: {ctx.date}")]


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


def doc_schema(ctx):
    return [B("schema")]


DOCS = {
    "notificare": ("Anexa 2 — Notificare (Ord. ANRE 19/2022)", doc_notificare),
    "schema_cef": ("Schemă monofilară", doc_schema),
    "date_stocare": ("Date despre instalația de stocare", doc_storage),
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
    "schema": ("Schemă monofilară", doc_schema),
}


# ---------- PDF renderer ----------
def pdf_header(ctx):
    left = Paragraph(f"<b><font size=10>{ctx.company}</font></b><br/>{ctx.e('cui', '')} · {ctx.e('regcom', '')}<br/>Atestat ANRE {ctx.e('anre_attest', '')}", S["hdrl"])
    right = Paragraph(f"{ctx.e('phone', '')}<br/>{ctx.e('email', '')}<br/>{ctx.e('address', '')}", S["hdrr"])
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


def _img(path, w, h):
    try:
        if path not in _IMG_CACHE:
            _IMG_CACHE[path] = IMG_LOADER(path)
        return Image(io.BytesIO(_IMG_CACHE[path]), width=w, height=h, kind="proportional")
    except Exception:
        return None


def sig_images(lines, s):
    txt = " ".join(lines)
    imgs = []
    if not IMG_LOADER:
        return imgs
    for nm, p in (s.get("_sigs") or {}).items():
        if nm and escape(nm) in txt:
            i = _img(p, 34 * mm, 14 * mm)
            if i:
                imgs.append(i)
            break
    company = escape(str(s.get("company") or ""))
    if s.get("_stamp_path") and "ștampil" in txt and company and company in txt:
        i = _img(s["_stamp_path"], 24 * mm, 24 * mm)
        if i:
            imgs.append(i)
    return imgs


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
            out.append(Paragraph(b[1], S[k]))
        elif k == "bullets":
            out += [Paragraph(x, S["li"], bulletText="•" if (len(b) < 3 or b[2]) else None) for x in b[1]]
        elif k == "table":
            out += [pdf_table(b[1], b[2], b[3], b[4] if len(b) > 4 else None), Spacer(1, 6)]
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


def render(doc_keys, rec, settings, client, opis_titles=None, draft=False):
    ctx = Ctx(CEF.flatten(rec), settings, client, opis_titles)
    buf = io.BytesIO()
    pw, ph = A4
    on = _draft if draft else (lambda c, d: None)
    port = PageTemplate("port", [Frame(18 * mm, 14 * mm, pw - 36 * mm, ph - 28 * mm, id="fp")], pagesize=A4, onPage=on)
    land = PageTemplate("land", [Frame(12 * mm, 10 * mm, ph - 24 * mm, pw - 20 * mm, id="fl")], pagesize=landscape(A4), onPage=on)
    first_land = bool(doc_keys) and doc_keys[0] in ("schema_cef", "schema")
    pdf = BaseDocTemplate(buf, pageTemplates=[land, port] if first_land else [port, land], title=f"D-ENERGY — {ctx.raw('name') or ''}")
    story = []
    for i, k in enumerate(doc_keys):
        if k in ("schema_cef", "schema"):
            draw, tbl = schema_cef.story(ctx, lambda t, st="p": Paragraph(t, S[st]), lambda rows, w, head=True: pdf_table(rows, [x / mm for x in w], head, None, 273), S)
            if i:
                story += [NextPageTemplate("land"), PageBreak()]
            story += draw + [PageBreak()] + tbl + [NextPageTemplate("port")]
            continue
        if i:
            story.append(PageBreak())
        story += to_flow(DOCS[k][1](ctx), ctx)
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
            for i, k in enumerate(keys or [doc_key]):
                if i:
                    blocks.append(B("pagebreak"))
                blocks += DOCS[k][1](ctx)
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
                        runs(p, "\n".join(top) + "\n\n\n________________________\n" + "\n".join(bot), 9)
                d.add_paragraph()
            elif k == "pagebreak":
                d.add_page_break()
    out = io.BytesIO()
    d.save(out)
    return out.getvalue()
