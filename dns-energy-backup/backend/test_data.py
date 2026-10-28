import io, copy
from datetime import datetime, timedelta, timezone
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import docgen
from sld_demo import DEMO_REC

TEST_COLLECTIONS = ["clients", "prosumator", "diu", "pram", "staff", "instruments", "catalog", "documents", "works", "mono", "equipment"]


def placeholder_pdf(title: str) -> bytes:
    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=A4)
    c.setFont("LSB", 16); c.drawString(60, 760, "DOCUMENT DE TEST")
    c.setFont("LS", 11); c.drawString(60, 735, title[:90])
    c.drawString(60, 715, "Fișier fictiv generat automat pentru verificarea fluxului. Nu este document oficial.")
    c.save()
    return b.getvalue()


def build(stamp: str, test_email: str | None, files: dict) -> dict:
    """files: name -> stored file dict. Returns docs per collection (without owner/id)."""
    today = datetime.now(timezone.utc).date()
    exp = (today + timedelta(days=365)).isoformat()
    name = f"TEST — Popescu Ion ({stamp})"
    auth = lambda t, nr: [{"type": t, "number": nr, "issuer": "ANRE (TEST)", "category": "TEST", "issued": today.isoformat(), "expires": exp,
                           "file": files["auth"], "verified": True}]
    staff = [{"key": "designer", "name": f"TEST Proiectant {stamp}", "qualification": "Inginer electrician (TEST)", "email": test_email or "",
              "auths": auth("Atestat ANRE proiectare (TEST)", "T-001"), "signature_authorized": True},
             {"key": "verifier", "name": f"TEST Verificator {stamp}", "qualification": "Verificator proiecte (TEST)", "email": test_email or "",
              "auths": auth("Atestat verificator (TEST)", "T-002"), "signature_authorized": True}]
    inst = {"maker_model": "Telurometru TEST-100", "serial": "TST-0001", "cert_name": "Certificat de etalonare (TEST)", "cert_no": "CE-TEST-1",
            "issued": today.isoformat(), "expires": exp, "file": files["cert"]}
    cat = [{"category": "Invertor", "brand_model": "Invertor hibrid 10 kW (TEST)", "type": "Hibrid", "phases": "Trifazat", "p_nom_kw": 10, "p_max_kw": 11,
            "vdc_max": 1000, "mppt_min": 160, "mppt_max": 850, "mppt_count": 2, "imax_mppt": 20},
           {"category": "Panou", "brand_model": "Modul 450 W (TEST)", "w": 450, "voc": 41.0, "vmp": 34.5, "isc": 13.9, "coef_voc": -0.27},
           {"category": "Baterie", "brand_model": "Baterie LV 10 kWh (TEST)", "kwh": 10, "voltage": 51.2, "coupling": "DC"},
           {"category": "Smart meter", "brand_model": "Smart meter trifazat (TEST)"}]
    for c in cat:
        c["datasheet"], c["conformity"] = files["datasheet"], files["conformity"]
    client = {"kind": "Persoană fizică", "name": name, "idcode": "1800101000000", "ci_series": "XX 000000", "hq_address": "Str. Test nr. 1, Localitate Test",
              "phone": "0700000000", "email": test_email or "", "address": "Str. Test nr. 1", "locality": "Localitate Test", "county": "Test",
              "pod": "RO000E000000TEST", "nlc": "TEST-NLC", "cadastral_nr": "00000", "cf_nr": "00000", "supplier": "Furnizor TEST",
              "operator": "Distribuție Energie Electrică România (DEER)", "docs": {k: [files["clientdoc"]] for k in ("factura", "ci", "cf")}}
    cef = copy.deepcopy(DEMO_REC["cef"])
    cef["grid"]["grounding_limit"] = 4
    pros = {"number": f"TEST-PROS-{stamp}", "client_name": name, "status": "În pregătire", "project_no": f"TEST-{stamp}", "cef": cef,
            "apparent_kva": 11, "power": 10, "doc_date": today.isoformat(), "date": today.isoformat(), "internal_pi": 0.1, "internal_pmax": 0.1,
            "afm": "Nu", "doc_no": "T-1", "bulletin_no": "PRAM-TEST-1", "measure_date": today.isoformat(), "measure_object": "Priză de pământ CEF (TEST)",
            "soil": "uscat", "soil_psi": 1.2, "grounding_ohm": 3.2, "grounding_limit": 4, "pif_date": today.isoformat(), "pif_decision": "Admis (TEST)",
            "bmp_desc": "BMP trifazat (TEST)", "anti_relay_present": "Nu", "reconnect_min": 5, "receptie_date": today.isoformat(),
            "receptie_decision": "Admis (TEST)", "receptie_findings": "Fără observații (TEST)", "operator": client["operator"], "pod": client["pod"],
            "reglaj": {k: {"val": "conform setări TEST", "t": "0,2"} for k, _ in docgen.REGLAJ},
            "tests": {**{f"a{i}": {"ok": "DA"} for i in range(len(docgen.TESTS_A))}, **{f"f{i}": {"ok": "DA"} for i in range(len(docgen.FREQ))},
                      **{f"c{i}": {"ok": "DA"} for i in range(len(docgen.CHECKS))}}, "is_test": True}
    diu = {"number": f"TEST-DIU-{stamp}", "client_name": name, "type": "Sistem fotovoltaic", "power": 10, "address": client["address"],
           "operator": client["operator"], "status": "În lucru"}
    pram = {"number": f"PRAM-TEST-{stamp}", "date": today.isoformat(), "author": staff[1]["name"]}
    return {"staff": staff, "instrument": inst, "catalog": cat, "client": client, "prosumator": pros, "diu": diu, "pram": pram}
