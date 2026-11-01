import io
from html import escape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

import docgen as D

S, M = D.S, D.M
REG = "Regulamentul pentru atestarea operatorilor economici care proiectează, execută și verifică instalații electrice, aprobat prin Ordinul ANRE nr. 134/2021"
NOTE = "Completat automat după structura anexei din Regulament — verificați cu formularul oficial în vigoare publicat pe www.anre.ro înainte de semnare și depunere."
TYPES = {"nou": "Atestat nou", "b_c1a": "Extindere B → C1A", "b_c2a": "Extindere B → C2A", "modificare": "Modificarea datelor atestatului", "vizare": "Vizare periodică", "altele": "Altă solicitare"}
A_G = [("cert_constatator", "Certificat constatator ONRC (emis cu max. 30 de zile înainte de depunere; activitățile atestate în obiectul de activitate)", "art. 14 alin. (1) lit. a)", "client"),
       ("organigrama", "Organigrama operatorului economic, datată și semnată de reprezentantul legal", "art. 14 alin. (1) lit. b)", "generat_verificare"),
       ("dotari", "Lista dotărilor tehnico-materiale (model Anexa nr. 5; minimul din Anexa nr. 6)", "art. 14 alin. (1) lit. c)", "generat_verificare"),
       ("personal", "Fișa cu structura de personal (model Anexa nr. 7; min. 2 electricieni autorizați conform Anexei nr. 8)", "art. 14 alin. (1) lit. d)", "generat_verificare"),
       ("autorizari", "Legitimațiile / autorizările ANRE ale electricienilor din structura minimă", "art. 14 alin. (1) lit. d), Anexa nr. 8", "client"),
       ("revisal", "Raport per salariat REVISAL asumat de reprezentantul legal / contracte de prestări servicii", "art. 14 alin. (1) lit. e)", "client"),
       ("decl_9", "Declarație pe propria răspundere privind menținerea dotărilor și personalului (Anexa nr. 9)", "art. 14 alin. (1) lit. f)", "generat_verificare"),
       ("decl_10", "Declarație de consimțământ privind prelucrarea datelor cu caracter personal (Anexa nr. 10)", "art. 14 alin. (1) lit. g)", "generat_verificare")]


def opis_items(kind: str) -> list:
    cer = [("cerere", f"Cerere — {TYPES.get(kind, '')} (formular-tip ANRE)", "Regulament, cererea-tip", "generat_verificare")]
    if kind in ("nou", "b_c1a", "b_c2a"):
        it = cer + A_G + [("tarif", "Dovada achitării tarifului ANRE de emitere (taxă externă, se plătește separat către ANRE)", "art. 13 și art. 14 alin. (1) lit. h)", "client")]
    elif kind == "vizare":
        it = cer + [x for x in A_G] + [
            ("atestat_original", "Originalul atestatului deținut", "art. 24 alin. (1)", "client"),
            ("tarif_vizare", "Dovada achitării tarifului ANRE de vizare a atestatului", "art. 24 alin. (1)", "client")]
    elif kind == "modificare":
        it = cer + [("cert_constatator", A_G[0][1], "art. 26 alin. (2)", "client"),
                    ("acte_modificare", "Documente care dovedesc modificarea datelor (acte ONRC, hotărâri etc.)", "art. 26 alin. (2)", "client"),
                    ("tarif_modificare", "Dovada achitării tarifului ANRE de modificare a atestatului", "art. 26 alin. (2)", "client"),
                    ("atestat_original", "Originalul atestatului deținut", "art. 26 alin. (4)", "client")]
    else:
        it = cer + [("alte", "Documente cerute de procedura aplicabilă (stabilite împreună cu consultantul)", "de stabilit conform Regulamentului", "client")]
    return [{"nr": i + 1, "key": k, "title": t, "basis": b, "source": s} for i, (k, t, b, s) in enumerate(it)]


def _doc(story, title):
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm, title=title).build(story)
    return buf.getvalue()


def e(v):
    return escape(str(v)) if v not in (None, "") else M


def head(d, title):
    c = d.get("company") or {}
    return [Paragraph(f"<b>{e(c.get('name'))}</b> · CUI {e(c.get('cui'))} · {e(c.get('regcom'))} · {e(c.get('address'))}", S["small"]), Spacer(1, 8),
            Paragraph(title, S["h"]), Paragraph(f"<i>{NOTE}</i>", S["small"]), Spacer(1, 6)]


def sig(d):
    c = d.get("company") or {}
    return [Spacer(1, 14), Paragraph(f"Data: {M}<br/>Reprezentant legal: <b>{e(c.get('rep_name'))}</b>, {e(c.get('rep_role'))}<br/>Semnătura: {M}", S["p"])]


def table(rows, w):
    return D.pdf_table(rows, w, True, 8, 170)


def render(key, d) -> bytes:
    c = d.get("company") or {}
    staff, eq = d.get("staff") or [], d.get("equipment") or []
    if key == "cerere":
        s = head(d, f"CERERE — {TYPES.get(d.get('kind'), '').upper()}") + [
            Paragraph("Către: Autoritatea Națională de Reglementare în Domeniul Energiei (ANRE)", S["p"]),
            Paragraph(f"Subscrisa <b>{e(c.get('name'))}</b>, cu sediul social în {e(c.get('address'))}, CUI {e(c.get('cui'))}, înregistrată la Registrul Comerțului sub nr. {e(c.get('regcom'))}, "
                      f"telefon {e(c.get('phone'))}, e-mail {e(c.get('email'))}, reprezentată legal prin {e(c.get('rep_name'))} ({e(c.get('rep_role'))}), solicit "
                      f"<b>{e(TYPES.get(d.get('kind')))}</b> pentru tipul/tipurile de atestat: <b>{e(', '.join(d.get('target_types') or []))}</b>.", S["p"]),
            Paragraph(f"Atestat existent: nr. {e(c.get('attest_no'))}, tipuri {e(c.get('attest_types'))}, valabil până la {e(c.get('attest_valid'))}.", S["p"]),
            Paragraph("Anexez documentele din opisul atașat.", S["p"])] + sig(d)
    elif key == "organigrama":
        s = head(d, "ORGANIGRAMA OPERATORULUI ECONOMIC") + [Paragraph(f"Conducere: {e(c.get('rep_name'))} — {e(c.get('rep_role'))}", S["p"]),
            table([["Compartiment", "Responsabil", "Activități"]] + [[e(x.get("dept")), e(x.get("name")), e(x.get("activity"))] for x in d.get("org") or []] or [[M, M, M]], [35, 30, 35])] + sig(d)
    elif key == "dotari":
        s = head(d, "LISTA DOTĂRILOR TEHNICO-MATERIALE (Anexa nr. 5)") + [table([["Nr.", "Denumire dotare", "Serie / buc.", "Proprietate / folosință", "Valabilitate verificare metrologică"]] +
            [[str(i + 1), e(x.get("name")), e(x.get("serial")), e(x.get("ownership")), e(x.get("calibration"))] for i, x in enumerate(eq)] or [["—", M, M, M, M]], [7, 38, 18, 18, 19])] + sig(d)
    elif key == "personal":
        s = head(d, "FIȘA CU STRUCTURA DE PERSONAL (Anexa nr. 7)") + [table([["Nr.", "Nume și prenume", "Funcție", "Grad/tip autorizare ANRE", "Nr. legitimație / valabilitate", "Contract"]] +
            [[str(i + 1), e(x.get("name")), e(x.get("role")), e(x.get("grade")), e(x.get("license")), e(x.get("contract"))] for i, x in enumerate(staff)] or [["—", M, M, M, M, M]], [6, 24, 16, 18, 20, 16])] + sig(d)
    elif key == "decl_9":
        s = head(d, "DECLARAȚIE PE PROPRIA RĂSPUNDERE (Anexa nr. 9)") + [Paragraph(
            f"Subsemnatul {e(c.get('rep_name'))}, în calitate de reprezentant legal al {e(c.get('name'))}, CUI {e(c.get('cui'))}, declar pe propria răspundere că operatorul economic "
            "va menține pe toată durata de valabilitate a atestatului dotările tehnico-materiale și numărul minim de personal autorizat prevăzute de Regulament pentru tipul de atestat solicitat "
            "și că va comunica ANRE orice modificare a acestora, în condițiile Regulamentului.", S["p"])] + sig(d)
    elif key == "decl_10":
        s = head(d, "DECLARAȚIE PRIVIND PRELUCRAREA DATELOR CU CARACTER PERSONAL (Anexa nr. 10)") + [Paragraph(
            f"Subsemnatul {e(c.get('rep_name'))}, reprezentant legal al {e(c.get('name'))}, îmi exprim consimțământul ca ANRE să prelucreze datele cu caracter personal din documentele depuse, "
            "în scopul soluționării solicitării, conform Regulamentului (UE) 2016/679.", S["p"])] + sig(d)
    else:
        raise KeyError(key)
    return _doc(s, key)


def opis_pdf(d, items) -> bytes:
    rows = [["Nr.", "Document", "Temei", "Sursă", "Status"]] + [[str(i["nr"]), escape(i["title"]), escape(i["basis"]), i["source_label"], escape(i["status"])] for i in items]
    return _doc(head(d, f"OPIS — {TYPES.get(d.get('kind'), '')}") + [Paragraph(f"Temei general: {REG}.", S["small"]), table(rows, [6, 42, 20, 14, 18])] + sig(d), "opis")


def report_pdf(d, rep) -> bytes:
    s = head(d, "RAPORT FINAL DE VERIFICARE A DOSARULUI") + [Paragraph(f"Generat: {e(rep['at'][:16].replace('T', ' '))} UTC · Rezultat: <b>{'fără blocaje' if rep['ok'] else 'există lipsuri'}</b>", S["p"])]
    for t, k in (("Documente prezente", "present"), ("Documente lipsă", "missing"), ("Expirate / necesită verificare", "review"), ("Formulare incomplete", "incomplete"),
                 ("Neconcordanțe", "issues"), ("Acțiuni rămase pentru client", "actions")):
        s += [Paragraph(f"<b>{t}</b>", S["b"])] + [Paragraph("• " + escape(x), S["li"]) for x in rep[k] or ["—"]]
    s.append(Paragraph("Raportul nu certifică autenticitatea documentelor și nu garantează aprobarea ANRE. Depunerea se face de solicitant / reprezentantul împuternicit prin canalul oficial ANRE.", S["small"]))
    return _doc(s, "raport")


_ = PageBreak
