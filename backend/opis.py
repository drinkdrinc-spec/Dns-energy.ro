import io
import datetime
import zipfile
from html import escape
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib import colors
import docgen
import sizing as SZ
import sld as SLD
import pif_doc as PIFDOC

STATUSES = ["de completat", "generat", "necesită semnătură", "atașat"]


class SubmissionPackageIncomplete(ValueError):
    """Raised when a submission package contains missing or unavailable evidence."""


def _require_complete_submission(positions_info):
    if positions_info.get("complete") and not positions_info.get("export_has_unavailable_items"):
        return
    missing = int(positions_info.get("missing_total") or 0)
    if missing:
        raise SubmissionPackageIncomplete(
            f"Dosarul are {missing} elemente de completat sau verificat. Completează opisul înainte de exportul pentru depunere."
        )
    raise SubmissionPackageIncomplete(
        "Unul sau mai multe documente nu au putut fi incluse. Verifică opisul și reîncearcă exportul."
    )
CLIENT_SLOTS = {"factura": "Factură furnizor de energie", "certificat": "Certificat de înregistrare", "constatator": "Certificat constatator",
                "ci": "Act de identitate", "cf": "Extras de carte funciară", "imputernicire": "Împuternicire / mandat",
                "fotografii_instalatie": "Fotografii instalație", "fotografii_lucrare": "Fotografii lucrare", "alt_document": "Alt document"}
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
       ("date_stocare", "Date despre instalația de stocare", ["date_stocare"], [], []),
       ("schema", "Schemă monofilară", ["sld"], [], []),
       ("fisa_tehnica", "Fișă tehnică instalație — echipamente, cabluri și protecții", ["fisa_tehnica"], [], []),
       ("afm", "Declarație accesare fonduri (AFM)", ["declaratie_afm"], ["afm", "doc_date"], []),
       ("reglaj", "Buletin reglaj", ["buletin_reglaj"], ["doc_date"], []),
       ("priza", "Buletin de verificare și măsurare priză de pământ", ["buletin_priza"],
        ["bulletin_no", "measure_date", "measure_object", "soil", "soil_psi", "grounding_ohm", "grounding_limit"], ["meter_device", "meter_serial", "meter_valid"]),
       ("pif", "Proces-verbal de punere în funcțiune", ["pv_pif", "pv_teste"], ["pif_date", "pif_decision", "bmp_desc", "anti_relay_present", "reconnect_min", "afm"], ["anre_valid"]),
       ("receptie", "Proces-verbal de recepție la terminarea lucrărilor", ["pv_receptie"], ["receptie_date", "receptie_decision", "receptie_findings"], []),
       ("executant", "Declarația executantului (Ord. ANRE 59/2013)", ["declaratie_executant"], ["doc_no", "doc_date"], []),
       ("conformitate", "Declarație de conformitate (HGR 1022/2002)", ["declaratie_conformitate"], ["doc_date"], ["warranty_months"]),
       ("imputernicire", "Împuternicire", ["imputernicire"], ["county"], [])]
COMMON = ["name", "idcode", "hq_address", "phone", "address", "county", "pod", "operator"]
EXEC = ["company", "cui", "regcom", "address", "phone", "email", "anre_attest", "rep"]

# Missing shared values should affect only documents that actually print them.
DOC_COMMON = {
    "notificare": (COMMON, EXEC), "date_stocare": (["name", "address", "pod"], ["company", "rep"]), "schema": (["name", "address", "county", "pod", "operator"], ["company", "rep"]),
    "fisa_tehnica": (["name", "address", "county", "pod", "operator"], ["company", "rep"]),
    "afm": (["name", "idcode", "hq_address"], []), "reglaj": (["name", "address"], ["company", "rep"]),
    "priza": (["name", "address", "county"], ["company", "rep"]),
    "pif": (["name", "address", "county"], ["company", "rep"]),
    "receptie": (["name", "address", "county"], ["company", "rep"]),
    "executant": (["name", "address"], EXEC), "conformitate": (["name", "address"], EXEC),
    "imputernicire": (["name", "idcode", "hq_address", "county"], EXEC),
}


def storage_missing_fields(battery):
    """List storage-sheet values that must be verified before submission."""
    missing = []
    model = str(battery.get("model") or "Baterie")
    for field, label in (("kwh", "capacitatea în kWh pe modul"),
                         ("modules", "numărul modulelor"),
                         ("voltage", "tensiunea nominală"),
                         ("ah", "capacitatea în Ah"),
                         ("tech", "clasa bateriei LV/HV"),
                         ("coupling", "tipul de cuplare")):
        value = battery.get(field)
        if field in ("kwh", "modules", "voltage", "ah"):
            number = docgen.num(value, None)
            if number is None or number <= 0:
                missing.append(label)
        elif value in (None, ""):
            missing.append(label)
    return [f"{model}: completează/verifică " + ", ".join(missing)] if missing else []


def dossier_client_snapshot(rec, client):
    """Overlay reviewed dossier values on the linked client, preserving client fallbacks."""
    rec, snapshot = rec or {}, dict(client or {})
    for key in docgen.CLIENT_KEYS:
        if rec.get(key) not in (None, ""):
            snapshot[key] = rec[key]
    for key, aliases in docgen.ALIASES.items():
        if rec.get(key) not in (None, ""):
            continue
        for alias in aliases:
            if rec.get(alias) not in (None, ""):
                snapshot[key] = rec[alias]
                break
    return snapshot


def dossier_order(p):
    """Order the packet to match the supplied signed Reenergy dossier example."""
    key = p.get("key", "")
    priority = {
        # Signed reference: PRAM, operator form, storage, privacy notice,
        # mandate and AFM declaration are the opening submission documents.
        "priza": 5, "metrologie_pram": 7, "notificare": 10,
        "date_stocare": 20, "gdpr": 30, "imputernicire": 40, "afm": 50,
        # Keep uploaded client evidence in the packet without displacing the
        # equipment and commissioning documents that follow it in the sample.
        "certificat": 52, "factura": 53, "cf": 54,
        "fotografii_instalatie": 55, "alt_document": 56,
        "executant": 60, "anre_firma": 61, "conformitate": 65,
        "receptie": 70, "serii": 75, "pif": 80, "pif_pv": 82,
        # The reference dossier includes its PRAM report again after PIF.
        "reglaj": 90, "declaratie_autenticitate": 100, "opis": 101,
        "schema": 110, "fisa_tehnica": 115,
        "fotografii_lucrare": 130,
    }
    if key.startswith("cat_"):
        return (116, p.get("title", "").lower())
    return (priority.get(key, 500), p.get("title", "").lower())


def catalog_refs(rec):
    c = rec.get("cef") or {}
    inv, pan, bat, rsd = [], [], [], []
    for i in c.get("inverters") or []:
        inv.append((i.get("catalog_id"), i.get("brand_model")))
        pan.append((i.get("panel_catalog_id"), i.get("panel_model")))
        rsd_config = i.get("rsd") or {}
        if rsd_config.get("enabled"):
            rsd.append((rsd_config.get("catalog_id"), rsd_config.get("brand_model")))
        if i.get("battery_mode") == "own":
            bat.append(((i.get("battery") or {}).get("catalog_id"), (i.get("battery") or {}).get("model")))
    bat += [(b.get("catalog_id"), b.get("model")) for b in c.get("shared_batteries") or []]
    g = c.get("grid") or {}
    met = [(g.get("meter_catalog_id"), g.get("meter"))] if g.get("meter") else []
    if not c.get("inverters"):
        inv = [(None, rec.get("inverter"))] if rec.get("inverter") else []
        pan = [(None, rec.get("panels"))] if rec.get("panels") else []
        bat = [(None, rec.get("battery"))] if rec.get("battery") else []
    def dedup(items):
        # Keep distinct catalog records even when two records share a display name.
        # Fall back to a normalized model name only for equipment not linked by ID.
        out = {}
        for cid, model in items:
            name = str(model or "").strip()
            if not name:
                continue
            identity = ("id", str(cid)) if cid else ("model", name.casefold())
            out[identity] = (cid, name)
        return list(out.values())

    return dedup(inv), dedup(pan), dedup(bat), dedup(met), dedup(rsd)


async def authorization_files(db, owner, rec, settings):
    """Return only uploaded, current company, signer and PRAM evidence for a dossier export."""
    files, seen = [], set()
    today = datetime.date.today().isoformat()

    def add_file(file):
        file = file or {}
        path = file.get("storage_path")
        if path and path not in seen:
            seen.add(path)
            files.append(file)

    company_file = settings.get("anre_file") or {}
    company_expiry = str(settings.get("anre_valid") or "")
    if company_file.get("storage_path") and (not company_expiry or company_expiry >= today):
        add_file(company_file)

    snapshot = rec.get("snapshot") or {}
    signers = snapshot.get("signers") or rec.get("signers") or {}
    signer_roles = {"executant", "resp_tehnic", "electrician", "verifier", "measurer", "designer"}
    for staff_id in dict.fromkeys(value for role, value in signers.items() if role in signer_roles and isinstance(value, str) and value):
        person = await db.staff.find_one({"owner": owner, "id": staff_id}, {"_id": 0})
        for auth in (person or {}).get("auths") or []:
            expiry = str(auth.get("expires") or "")
            file = auth.get("file") or {}
            if auth.get("verified") and file.get("storage_path") and (not expiry or expiry >= today):
                add_file(file)

    if rec.get("pram_source") not in ("third_party", "none"):
        instrument_id = rec.get("instrument_id")
        instrument = await db.instruments.find_one({"owner": owner, "id": instrument_id}, {"_id": 0}) if instrument_id else None
        meter_file = (instrument or {}).get("file") or {}
        expiry = str((instrument or {}).get("expires") or "")
        if instrument and instrument.get("active") is not False and instrument.get("measures_grounding") is not False and meter_file.get("storage_path") and (not expiry or expiry >= today):
            add_file(meter_file)
    return files


async def prosumer_official_operator_form(rec, client, pros, power_increase):
    """Resolve the official operator annex for the dossier's actual request."""
    import atr_routes as ATR_ROUTES

    operator = str(rec.get("operator") or client.get("operator") or "")
    operator_key = ATR_ROUTES.ATR.op_key(operator)
    if operator_key not in {"rer", "delgaz", "oltenia"}:
        return None

    cef = pros.get("cef") or {}
    grid = cef.get("grid") or {}
    request_rec = {
        **rec,
        "request_type": "spor" if power_increase else "mod_fara",
        "supply": rec.get("supply") or pros.get("supply") or grid.get("supply") or "",
    }
    annex_no, forms = await ATR_ROUTES._registry_forms_for_request(operator_key, request_rec, pros)
    if annex_no is None or not forms:
        return None
    form = forms[0]
    return {
        **form,
        "operator_key": operator_key,
        "annex_no": annex_no,
        "title": form.get("title") or f"Anexa {annex_no} — formular oficial prosumator",
    }


async def build_positions(db, owner, rec, client, settings, public_documents=None):
    # Keep the dossier's reviewed identity and consumption snapshot authoritative
    # throughout the opis, official-form checks and generated documents. The linked
    # client remains the fallback for values that were not captured on this dossier.
    client = dossier_client_snapshot(rec, client)
    kind = str(client.get("kind") or "").strip().casefold()
    pj = "jurid" in kind or kind in ("pj", "company", "firmă", "firma")
    ctx = docgen.Ctx(docgen.CEF.flatten(rec), settings, client)
    opis = rec.get("opis") or {}
    req_common = COMMON + (["regcom", "rep_name", "rep_role"] if pj else [])
    pos = []
    cdocs = client.get("docs") or {}

    common = [L.get(k, k) for k in req_common if ctx.raw(k) in (None, "")] + [EL.get(k, k) for k in EXEC if settings.get(k) in (None, "")]
    if not settings.get("_stamp_path"):
        common.append("Încarcă imaginea reală a ștampilei firmei în Setări de bază → Firmă")

    def missing(keys, ekeys):
        m = [L.get(k, k) for k in keys if ctx.raw(k) in (None, "")]
        m += [EL.get(k, k) for k in ekeys if settings.get(k) in (None, "")]
        return list(dict.fromkeys(m))

    res_sld = SZ.compute(rec, client)
    st_sld = SZ.state(rec, client, settings)
    for key, title, docs, keys, ekeys in GEN:
        # AFM declaration belongs in the generated bundle only when the
        # installer explicitly selected AFM financing for this dossier.
        if key == "afm" and str(ctx.raw("afm") or rec.get("afm") or "").strip().casefold() not in {"da", "yes", "true", "1"}:
            continue
        if key == "imputernicire":
            pos.append({"key": key, "title": "Împuternicire / mandat", "source": "client",
                        "slots": ["imputernicire"], "files": cdocs.get("imputernicire") or [], "missing": []})
            continue
        if key == "date_stocare" and not docgen.storage(ctx):
            continue
        if key == "notificare" and ctx.power_increase:
            operator_name = str(rec.get("operator") or client.get("operator") or "").casefold()
            is_deer = ("deer" in operator_name or "distributie energie electrica" in operator_name
                       or "distribuție energie electrică" in operator_name)
            if is_deer:
                pos.append({"key": key, "title": "Cerere de racordare — Anexa 1 DEER (formular oficial Word precompletat)",
                            "source": "generat", "docs": [], "docx_only": True,
                            "missing": ["Verifică formularul oficial și completează/semnează câmpurile rămase necompletate."]})
            else:
                official_form = await prosumer_official_operator_form(rec, client, rec, True)
                if official_form:
                    pos.append({"key": key,
                                "title": f"Cerere de racordare — {official_form['title']}",
                                "source": "official", "docs": [], "official_operator_form": official_form,
                                "missing": ["Verifică formularul oficial, completează câmpurile rămase necompletate și semnează-l."] + missing(keys, ekeys)})
                else:
                    pos.append({"key": key, "title": "Cerere de racordare — formularul oficial al operatorului",
                                "source": "manual", "files": [],
                                "missing": ["Deschide formularul oficial curent al operatorului în Registrul de formulare și atașează-l după completare."]})
            continue
        if key == "notificare":
            operator_name = str(rec.get("operator") or client.get("operator") or "").casefold()
            is_deer = ("deer" in operator_name or "distributie energie electrica" in operator_name
                       or "distribuție energie electrică" in operator_name)
            if is_deer:
                official_missing = []
                official_fields = [
                    (client.get("name") or rec.get("client_name"), "Numele solicitantului"),
                    (client.get("county") or rec.get("county"), "Județul locului de consum"),
                    (client.get("locality") or rec.get("locality"), "Localitatea locului de consum"),
                    (client.get("postal_code") or rec.get("postal_code"), "Codul poștal al solicitantului"),
                    (client.get("hq_address") or rec.get("hq_address"), "Domiciliul/sediul solicitantului"),
                    (client.get("phone") or rec.get("phone"), "Telefonul solicitantului"),
                    (client.get("email") or rec.get("email"), "E-mailul solicitantului"),
                    (client.get("cui") or client.get("cnp") or client.get("idcode") or rec.get("cui") or rec.get("cnp") or rec.get("idcode"), "CNP/CUI"),
                    (rec.get("address") or client.get("address"), "Adresa locului de consum"),
                    (rec.get("pod") or client.get("pod"), "POD"),
                    (rec.get("cf_nr") or client.get("cf_nr"), "Numărul cărții funciare"),
                    (rec.get("cadastral_nr") or client.get("cadastral_nr"), "Numărul cadastral"),
                    (rec.get("p_evac_kw") or rec.get("power"), "Puterea evacuată kW"),
                    (rec.get("p_evac_kva"), "Puterea evacuată kVA"),
                ]
                if pj:
                    official_fields.extend([
                        (client.get("registration_no") or client.get("regcom") or rec.get("regcom"), "Numărul Registrului Comerțului"),
                        (client.get("rep_name") or rec.get("rep_name"), "Reprezentantul legal"),
                        (client.get("rep_role") or rec.get("rep_role"), "Calitatea reprezentantului"),
                    ])
                for value, label in official_fields:
                    if value in (None, ""):
                        official_missing.append(label)
                if not (rec.get("cef") or {}).get("inverters"):
                    official_missing.append("Configurare CEF (invertoare, stringuri)")
                pos.append({"key": key, "title": "Notificare oficială DEER — Anexa 2",
                            "source": "generat", "docs": [], "docx_only": True,
                            "official_doc_endpoint": "anexa2",
                            "official_form_label": "Anexa 2 DEER",
                            "missing": ["Descarcă formularul oficial, verifică datele, semnează-l și încarcă PDF-ul semnat.", *official_missing]})
                continue
            official_form = await prosumer_official_operator_form(rec, client, rec, False)
            if official_form:
                form_missing = list(dict.fromkeys(
                    ["Verifică formularul oficial, completează eventualele câmpuri rămase goale și semnează-l."]
                    + missing(keys, ekeys) + missing(*DOC_COMMON.get(key, ([], [])))))
                pos.append({"key": key,
                            "title": f"Notificare / cerere prosumator — {official_form['title']}",
                            "source": "official", "docs": ["notificare"],
                            "official_operator_form": official_form,
                            "missing": form_missing})
                continue
            pos.append({"key": key,
                        "title": "Formularul oficial de notificare / cerere al operatorului",
                        "source": "manual", "files": [],
                        "missing": ["Formularul oficial curent nu este disponibil în registru. Încarcă formularul publicat de operator după completare și semnare; nu folosi formular generic la depunere."]})
            continue
        if key == "priza" and rec.get("pram_source") == "none":
            if PIFDOC.filled(rec):
                pos.append({"key": "pif_pv", "title": PIFDOC.TITLE, "source": "generat", "docs": ["pif_pv"], "missing": [], "files": []})
            continue
        if key == "priza" and rec.get("pram_source") == "third_party":
            uploaded_pram = rec.get("pram_file") or {}
            pos.append({"key": key, "title": title + " — document încărcat", "source": "manual",
                        "files": [uploaded_pram] if uploaded_pram.get("storage_path") else [],
                        "missing": [] if uploaded_pram.get("storage_path") else ["Încarcă PDF-ul buletinului PRAM emis de firma terță"]})
            if PIFDOC.filled(rec):
                pos.append({"key": "pif_pv", "title": PIFDOC.TITLE, "source": "generat", "docs": ["pif_pv"], "missing": [], "files": []})
            continue
        m = missing(keys, ekeys)
        shared_keys, shared_exec = DOC_COMMON.get(key, ([], []))
        m += missing(shared_keys, shared_exec)
        m = list(dict.fromkeys(m))
        if key == "date_stocare":
            for battery in docgen.storage(ctx):
                m.extend(storage_missing_fields(battery))
        if key == "notificare" and not (ctx.raw("inverter") or ctx.raw("panels")):
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
            values = [x for x in rg.values() if isinstance(x, dict)]
            if not values or any(not x.get("val") for x in values):
                m.append("Valori reglaje protecții")
        if key == "pif" and not PIFDOC.filled(rec):
            m.append("Rezultate PIF măsurate efectiv — completați data și valorile reale")
        pos.append({"key": key, "title": title, "source": "generat", "docs": docs, "missing": m, "files": []})
        if key == "priza" and PIFDOC.filled(rec):
            pos.append({"key": "pif_pv", "title": PIFDOC.TITLE, "source": "generat", "docs": ["pif_pv"], "missing": [], "files": []})

    # Keep commissioning-only records outside the submission packet until that workflow stage.
    # They remain editable in the PIF section and are included once measurements exist or the dossier reaches PIF.
    workflow_stages = {
        str(rec.get(field) or "").strip().casefold()
        for field in ("workflow_status", "status", "operator_stage")
    }
    pif_workflow_stages = {
        "probe și punere în funcțiune", "pv teste / pif", "prosumator activ", "finalizat",
        "recepția instalației electrice de racordare", "punerea sub tensiune a instalației de utilizare",
    }
    pif_documents_active = bool(workflow_stages & pif_workflow_stages) or PIFDOC.filled(rec)
    if not pif_documents_active:
        pos = [item for item in pos if item.get("key") not in {"pif", "receptie", "pif_pv"}]
    else:
        # Match the reference's dedicated equipment-serial annex. Keep it a
        # separate item so it can be completed at PIF without blocking filing.
        pos.append({"key": "serii", "title": "Anexă — serii echipamente (PIF)",
                    "source": "generat", "docs": ["serii"], "missing": [], "files": []})

    for key, slots, title in [("factura", ["factura"], "Factură furnizor de energie"),
                              ("certificat", ["certificat", "constatator"] if pj else ["ci"], "Certificat de înregistrare" if pj else "Act de identitate"),
                              ("cf", ["cf"], "Extras de carte funciară — dacă este solicitat de operator")]:
        files = [f for s in slots for f in (cdocs.get(s) or [])]
        pos.append({"key": key, "title": title, "source": "client", "slots": slots, "files": files,
                    "missing": [] if files or key == "cf" and not rec.get("cf_required") else [f"Încarcă în fișa clientului: {', '.join(CLIENT_SLOTS[s] for s in slots)}"]})

    # Add photo and extra-document upload rows shown on the dossier card.
    # Installation photos belong in the main packet; work photos follow the
    # technical annex. Client uploads remain original files in storage.
    for key, slot, title in (
        ("fotografii_instalatie", "fotografii_instalatie", "Fotografii instalație"),
        ("fotografii_lucrare", "fotografii_lucrare", "Fotografii lucrare — anexă tehnică"),
        ("alt_document", "alt_document", "Alt document client"),
    ):
        files = cdocs.get(slot) or []
        pos.append({"key": key, "title": title, "source": "client", "slots": [slot],
                    "files": files, "missing": []})

    # Include original company and PRAM evidence in the dossier packet.
    # These documents must be uploaded by the company; never synthesize them.
    anre_file = settings.get("anre_file") or {}
    anre_missing = []
    if not anre_file.get("storage_path"):
        anre_missing.append("Încarcă atestatul ANRE al firmei în Setări de bază → Firmă")
    if not settings.get("anre_valid"):
        anre_missing.append("Completează valabilitatea atestatului ANRE în Setări de bază → Firmă")
    elif settings.get("anre_valid") < datetime.date.today().isoformat():
        anre_missing.append("Atestatul ANRE al firmei este expirat — încarcă atestatul valabil")
    pos.append({"key": "anre_firma", "title": "Atestat ANRE firmă — document justificativ", "source": "company",
                "files": [anre_file] if anre_file.get("storage_path") else [], "missing": anre_missing})

    if rec.get("pram_source") not in ("third_party", "none"):
        instrument_id = rec.get("instrument_id")
        instrument = await db.instruments.find_one({"owner": owner, "id": instrument_id}, {"_id": 0}) if instrument_id else None
        meter_file = (instrument or {}).get("file") or {}
        meter_missing = []
        if not instrument:
            meter_missing.append("Selectează aparatul PRAM și încarcă certificatul lui în Setări de bază → Aparatele de măsură")
        else:
            if not meter_file.get("storage_path"):
                meter_missing.append("Încarcă certificatul metrologic / de etalonare al aparatului selectat")
            if not instrument.get("expires"):
                meter_missing.append("Completează valabilitatea metrologică a aparatului selectat")
            elif instrument.get("expires") < datetime.date.today().isoformat():
                meter_missing.append("Certificatul metrologic al aparatului selectat este expirat — încarcă unul valabil")
        meter_title = "Metrologie aparat PRAM" + (f" — {instrument.get('maker_model')} / seria {instrument.get('serial')}" if instrument else "")
        pos.append({"key": "metrologie_pram", "title": meter_title, "source": "instrument",
                    "files": [meter_file] if meter_file.get("storage_path") else [], "missing": meter_missing})

    # DEER's applicable privacy notice is attached from the official public source for natural-person cases.
    # It is informational; the application never generates a fake consent or signature.
    operator_name = str(rec.get("operator") or client.get("operator") or "").lower()
    is_deer = ("deer" in operator_name or "distributie energie electrica romania" in operator_name
               or "distribuție energie electrică românia" in operator_name)
    notice = (public_documents or {}).get("deer_gdpr_notice")
    if is_deer and not pj:
        if notice and notice.get("storage_path"):
            pos.append({"key": "gdpr", "title": "Notă oficială DEER — informare privind datele personale (februarie 2026)",
                        "source": "official", "files": [notice], "missing": []})
        else:
            pos.append({"key": "gdpr", "title": "Notă oficială DEER privind prelucrarea datelor personale (GDPR)",
                        "source": "manual", "files": [],
                        "missing": ["Nota oficială DEER nu a putut fi preluată automat; reîncearcă sau atașează PDF-ul oficial."]})

    inv, pan, bat, met, rsd = catalog_refs(rec)

    async def cat(cid, kind):
        it = await db.catalog.find_one({"owner": owner, "id": cid}, {"_id": 0}) if cid else None
        f = (it or {}).get(kind)
        # catalog_files marks inaccessible legacy objects explicitly. Keep them
        # visible as missing evidence in the opis, but do not retry a known-dead
        # storage pointer while generating every dossier PDF.
        return [f] if f and f.get("storage_path") and f.get("available") is not False else []

    groups = [("invertor", inv), ("panou", pan)]
    extra = [("baterie", bat), ("smart meter", met), ("RSD", rsd)]
    for label, items in groups + extra:
        for cid, model in items:
            for kind, prefix in (("datasheet", "Fișă tehnică"), ("conformity", "Declarație de conformitate")):
                files = await cat(cid, kind)
                k = f"cat_{kind}_{label.replace(' ', '_')}_{cid or model}"
                pos.append({"key": k, "title": f"{prefix} {label} — {model}", "source": "catalog", "files": files,
                            "missing": [] if files else [f"Încarcă {prefix.lower()} în Catalog echipamente ({model})" + ("" if cid else " și alege modelul din catalog în CEF")]})

    # Put the bundle in a predictable submission order, not in the order features were added.
    pos.sort(key=dossier_order)
    for i, p in enumerate(pos):
        p["nr"] = i + 1
        o = opis.get(p["key"]) or {}
        p["upload"] = o.get("upload")
        p["uploads"] = o.get("uploads") or []
        if p["key"] in ("schema", "fisa_tecnica") and p["upload"] and (p["upload"].get("sld_hash") != st_sld["fingerprint"] or st_sld["status"] != "approved"):
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
        gen_missing = p["missing"]
        has_upload = bool(o.get("upload") or o.get("uploads"))
        if p["source"] == "manual":
            auto = "atașat" if has_upload else "de completat"
        else:
            auto = "de completat" if gen_missing else ("atașat" if (has_upload or (p["source"] != "generat" and p["files"])) else "generat")
        p["auto_status"] = auto
        p["status"] = o.get("status") or auto
        if has_upload:
            p["missing"] = []
    total = sum(len(p["missing"]) for p in pos) + len(common)
    return {"positions": pos, "common_missing": common, "missing_total": total, "complete": total == 0, "titles": [p["title"] for p in pos]}


def file_pdf(data: bytes, ct: str) -> bytes:
    if "pdf" in (ct or ""):
        return data

    # Keep uploaded originals untouched, but scale photographs when they are
    # embedded into dossier bundles. Full-resolution phone images can otherwise
    # make a single PDF 40+ MB and fail to render in mobile Safari.
    image_bytes = data
    try:
        from PIL import Image, ImageOps
        if "heic" in (ct or "").lower() or "heif" in (ct or "").lower():
            from pillow_heif import register_heif_opener
            register_heif_opener()
        with Image.open(io.BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source)
            resampling = getattr(Image, "Resampling", Image)
            image.thumbnail((2400, 2400), resample=resampling.LANCZOS)
            if image.mode in ("RGBA", "LA") or "transparency" in image.info:
                rgba = image.convert("RGBA")
                flattened = Image.new("RGB", rgba.size, "white")
                flattened.paste(rgba, mask=rgba.getchannel("A"))
            else:
                flattened = image.convert("RGB")
            optimized = io.BytesIO()
            flattened.save(optimized, format="JPEG", quality=88, optimize=True, progressive=True)
            image_bytes = optimized.getvalue()
    except Exception:
        # Preserve the existing path for formats Pillow cannot decode.
        pass

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    img = ImageReader(io.BytesIO(image_bytes))
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


def mark_draft(pdf: bytes, text="CIORNĂ") -> bytes:
    writer = PdfWriter()
    for page in PdfReader(io.BytesIO(pdf)).pages:
        writer.add_page(page)
    watermark(writer, text)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


async def position_pdf(p, rec, client, settings, titles, get_object, force_generated=False):
    uploads = [*(p.get("uploads") or []), *([p["upload"]] if p.get("upload") else [])]
    if uploads and not force_generated:
        out = []
        # Keep source documents/photos already in the client record when the
        # dossier card adds more files to the same category.
        if p.get("source") == "client":
            for file in p.get("files") or []:
                data, ct = get_object(file["storage_path"])
                out.append(file_pdf(data, file.get("content_type") or ct))
        for file in uploads:
            data, ct = get_object(file["storage_path"])
            out.append(file_pdf(data, file.get("content_type") or ct))
        return out
    if p.get("docx_only"):
        return []
    official_form = p.get("official_operator_form")
    if official_form:
        import atr_routes as ATR_ROUTES
        operator_key = official_form["operator_key"]
        try:
            official_bytes, _ = await ATR_ROUTES._fetch_registry_annex(official_form, operator_key)
        except Exception as exc:
            worksheet = ATR_ROUTES.ATR.render_operator_annex_prep(
                rec, client, rec, operator_key, official_form["annex_no"], official_form["title"])
            notice = _official_form_unavailable_pdf(official_form, exc)
            p["_official_form_unavailable"] = True
            return [mark_draft(worksheet, "FORMULAR OFICIAL INDISPONIBIL"),
                    mark_draft(notice, "FORMULAR OFICIAL INDISPONIBIL")]
        official_bytes, filled_fields = ATR_ROUTES._prefill_official_pdf(official_bytes, rec, client, rec)
        parts = []
        if not filled_fields:
            parts.append(ATR_ROUTES.ATR.render_operator_annex_prep(
                rec, client, rec, operator_key, official_form["annex_no"], official_form["title"]))
        parts.append(official_bytes)
        return parts
    if p.get("key") in ("schema", "fisa_tehnica"):
        res = SZ.compute(rec, client)
        st = SZ.state(rec, client, settings)
        if p["key"] == "fisa_tehnica":
            return [SLD.tech_sheet(rec, client, settings, res, st)]
        sld = rec.get("sld") or {}
        if st["status"] == "approved" and sld.get("source") == "uploaded" and sld.get("upload"):
            data, ct = get_object(sld["upload"]["storage_path"])
            return [file_pdf(data, sld["upload"].get("content_type") or ct)]
        if st["status"] == "approved":
            # Re-render generated approvals with the current one-page template;
            # the approval fingerprint remains tied to the saved engineering data.
            stamp_path = settings.get("_stamp_path")
            if stamp_path:
                try:
                    settings["_stamp_bytes"], _ = get_object(stamp_path)
                except Exception:
                    settings["_stamp_bytes"] = None
            paths = settings.get("_sigs") or {}
            designer_name = settings.get("designer_name") or ""
            if designer_name and paths.get(designer_name):
                try:
                    signature, _ = get_object(paths[designer_name])
                    settings["_sld_signature_bytes"] = {"designer": signature}
                except Exception:
                    settings["_sld_signature_bytes"] = {}
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


def _official_form_unavailable_pdf(form, reason):
    """Return a clear fallback page with the official source; never substitute a generated form."""
    url = str(form.get("url") or "").strip()
    title = escape(str(form.get("title") or "formularul oficial al operatorului"))
    reason_text = escape(str(reason)[:300])
    story = [
        Paragraph("FORMULARUL OFICIAL NU A PUTUT FI DESCĂRCAT", docgen.S["h"]),
        Paragraph(title, docgen.S["b"]),
        Spacer(1, 5 * mm),
        Paragraph("Fișa de precompletare din acest dosar este doar un document de lucru. Nu înlocuiește formularul oficial și nu trebuie depusă în locul lui.", docgen.S["p"]),
        Paragraph("Descărcați formularul de la operator, completați-l, verificați datele și semnați-l înainte de depunere.", docgen.S["p"]),
    ]
    if url.startswith("https://"):
        story.append(Paragraph(f'<link href="{escape(url, quote=True)}" color="blue">Deschideți sursa oficială a formularului</link>', docgen.S["p"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"Detaliu tehnic: {reason_text}", docgen.S["small"]))
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=20 * mm, bottomMargin=18 * mm, title="Formular oficial indisponibil")
    doc.build(story)
    return buf.getvalue()


def _incomplete_report(positions_info, unavailable):
    rows = []
    for position in positions_info.get("positions", []):
        missing = position.get("missing") or []
        if missing:
            rows.append((position.get("title") or position.get("key") or "Document", missing))
    if positions_info.get("common_missing"):
        rows.insert(0, ("Date comune ale dosarului", positions_info["common_missing"]))
    if unavailable:
        rows.append(("Fișiere atașate care nu au putut fi citite", unavailable))
    if not rows:
        return None
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=20 * mm, bottomMargin=18 * mm, title="Verificare dosar DNS Energy")
    story = [
        Paragraph("LISTĂ DE VERIFICARE — ELEMENTE DE COMPLETAT", docgen.S["h"]),
        Paragraph("Lista de mai jos arată ce date și documente mai trebuie completate sau verificate. Documentele disponibile sunt incluse în pachet; valorile măsurate, semnăturile și formularele oficiale nu sunt inventate. Completează elementele indicate înainte de depunerea la operator.", docgen.S["p"]),
        Spacer(1, 5 * mm),
    ]
    for title, items in rows:
        story.append(Paragraph(escape(str(title)), docgen.S["b"]))
        for item in items:
            story.append(Paragraph("• " + escape(str(item)), docgen.S["li"]))
    doc.build(story)
    return buf.getvalue()


def _pram_repeat_after(positions):
    """Return the last commissioning row after which the reference repeats PRAM."""
    if not any(position.get("key") == "priza" for position in positions):
        return None
    commissioning = [position.get("key") for position in positions
                     if position.get("key") in {"serii", "pif", "pif_pv"}]
    return commissioning[-1] if commissioning else None


async def export_bundle(positions_info, rec, client, settings, get_object, logger, require_complete=False):
    if require_complete:
        _require_complete_submission(positions_info)
    titles = positions_info["titles"]
    w = PdfWriter()
    authenticity_page = docgen.render(["declaratie_autenticitate"], rec, settings, client, titles)
    main_parts = []
    technical_parts = []
    pram_parts = None
    repeat_pram_after = _pram_repeat_after(positions_info.get("positions") or [])
    unavailable = []
    for p in positions_info["positions"]:
        try:
            position_parts = await position_pdf(p, rec, client, settings, titles, get_object)
            if p.get("_official_form_unavailable"):
                unavailable.append(f"{p.get('title') or p.get('key') or 'Formular oficial'} — formularul oficial nu a putut fi descărcat; fișa din pachet este doar de lucru")
            # Match the reference submission layout: the authenticity
            # declaration closes the administrative forms, then the single-line
            # diagram and manufacturer evidence follow as a technical appendix.
            is_technical_appendix = (p.get("key") in ("schema", "fisa_tehnica", "fotografii_lucrare")
                                     or p.get("source") == "catalog")
            (technical_parts if is_technical_appendix else main_parts).extend(position_parts)
            if p.get("key") == "priza":
                pram_parts = list(position_parts)
            if repeat_pram_after and p.get("key") == repeat_pram_after and pram_parts:
                main_parts.extend(pram_parts)
        except Exception as e:
            logger.error(f"bundle skip {p['key']}: {e}")
            unavailable.append(p.get("title") or p.get("key") or "Document atașat")
    positions_info["export_has_unavailable_items"] = bool(unavailable)
    if unavailable:
        positions_info["complete"] = False
    if require_complete:
        _require_complete_submission(positions_info)
    # Keep the internal review/index page out of the official-document order;
    # it remains the final page so staff can see what still needs attention.
    report = _incomplete_report(positions_info, unavailable)
    parts = main_parts + [authenticity_page] + technical_parts
    if report:
        parts.append(report)
    for b in parts:
        try:
            for pg in PdfReader(io.BytesIO(b)).pages:
                w.add_page(pg)
        except Exception as e:
            logger.error(f"bundle merge skip: {e}")
    # Missing files or fields affect only the relevant generated document and
    # the verification list; complete attachments and forms remain unaltered.
    if rec.get("is_test"):
        watermark(w, "DOSAR DE TEST — NEOFICIAL", 38)
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


def _merge_pdf_parts(parts, logger):
    writer = PdfWriter()
    for part in parts:
        try:
            for page in PdfReader(io.BytesIO(part)).pages:
                writer.add_page(page)
        except Exception as exc:
            logger.error(f"package PDF merge skip: {exc}")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _package_group(key, source):
    # Installation photos belong in the submission dossier; work photos are
    # appended after the technical annexes, matching the Reenergy checklist.
    if key == "fotografii_instalatie":
        return 0
    if key == "fotografii_lucrare":
        return 3
    if key in ("priza", "metrologie_pram", "pif", "pif_pv", "receptie", "serii", "reglaj"):
        return 1
    if key in ("schema", "fisa_tecnica") or source == "catalog":
        return 2
    return 0


def _source_file_entries(positions, get_object, max_total=100 * 1024 * 1024):
    """Collect exact uploaded originals separately from the compiled PDFs."""
    files, unavailable, seen = [], [], set()
    used = 0
    for position in positions:
        key = str(position.get("key") or "document")
        title = str(position.get("title") or key)
        candidates = [*(position.get("files") or []), *(position.get("uploads") or [])]
        if position.get("upload"):
            candidates.append(position["upload"])
        safe_key = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in key)[:100] or "document"
        for item in candidates:
            if not isinstance(item, dict):
                continue
            path = item.get("storage_path")
            if not path or path in seen:
                continue
            seen.add(path)
            filename = str(item.get("original_filename") or "document").replace("\\", "/").split("/")[-1]
            filename = "".join(ch for ch in filename if ch.isalnum() or ch in " ._-()")[:180].strip(" .") or "document"
            try:
                data, content_type = get_object(path)
                if used + len(data) > max_total:
                    unavailable.append(f"{title} — originalul {filename} a fost omis, limita de 100 MB a anexelor originale a fost atinsă.")
                    continue
                used += len(data)
                files.append({
                    "archive_name": f"Documente originale/{safe_key}_{len(files) + 1:03d}_{filename}",
                    "title": title,
                    "original_filename": filename,
                    "data": data,
                    "content_type": item.get("content_type") or content_type,
                })
            except Exception:
                unavailable.append(f"{title} — originalul {filename} nu a putut fi citit din arhivă.")
    return {"files": files, "unavailable": unavailable}


    """Build the selected, ordered submission package without duplicating evidence."""
async def export_package_zip(positions_info, rec, client, settings, get_object, logger, file_count=4, require_complete=False):
    if require_complete:
        _require_complete_submission(positions_info)
    count = max(1, min(4, int(file_count or 4)))
    titles = positions_info["titles"]
    ordered_parts = []
    unavailable = []
    pram_parts = None
    repeat_pram_after = _pram_repeat_after(positions_info.get("positions") or [])
    for position in positions_info["positions"]:
        try:
            parts = await position_pdf(position, rec, client, settings, titles, get_object)
            if position.get("_official_form_unavailable"):
                unavailable.append(f"{position.get('title') or position.get('key')} — formular oficial indisponibil; atașează originalul verificat")
            if position.get("source") == "generat" and position.get("missing") and position.get("key") not in ("schema", "fisa_tecnica"):
                parts = [mark_draft(part, "CIORNĂ — DATE DE COMPLETAT") for part in parts]
            group = _package_group(position.get("key"), position.get("source"))
            ordered_parts.extend((group, part) for part in parts)
            if position.get("key") == "priza":
                pram_parts = list(parts)
            if repeat_pram_after and position.get("key") == repeat_pram_after and pram_parts:
                ordered_parts.extend((1, part) for part in pram_parts)
        except Exception as exc:
            logger.error(f"package skip {position.get('key')}: {exc}")
            unavailable.append(position.get("title") or position.get("key") or "Document atașat")

    original_sources = _source_file_entries(positions_info["positions"], get_object)
    unavailable.extend(original_sources["unavailable"])

    if unavailable and positions_info.get("complete"):
    if require_complete:
        positions_info["export_has_unavailable_items"] = bool(unavailable)
        _require_complete_submission(positions_info)
        positions_info["complete"] = False
    authenticity = docgen.render(["declaratie_autenticitate"], rec, settings, client, titles,
                                 draft=not positions_info.get("complete", False))
    if unavailable:
        authenticity = mark_draft(authenticity, "CIORNĂ — FIȘIER LIPSĂ")
    # Keep the original dossier order, inserting the authenticity declaration
    # after paperwork/commissioning records and before technical annexes.
    authenticity_group = 1 if any(group == 1 for group, _ in ordered_parts) else 0
    technical_start = next((i for i, (group, _) in enumerate(ordered_parts) if group >= 2), len(ordered_parts))
    ordered_parts.insert(technical_start, (authenticity_group, authenticity))
    report = _incomplete_report(positions_info, unavailable)
    if report:
        ordered_parts.insert(technical_start + 1, (authenticity_group, report))
    positions_info["export_has_unavailable_items"] = bool(unavailable)

    # Merge adjacent sections for compact layouts, keeping submission order stable.
    layouts = {
        1: [("Dosar_complet", [0, 1, 2, 3])],
        2: [("Dosar_depunere", [0, 1]), ("Anexe_tehnice", [2, 3])],
        3: [("Acte_si_procedura", [0, 1]), ("Schema_si_fise_tehnice", [2]), ("Fotografii", [3])],
        4: [("Acte_si_formulare", [0]), ("Probe_PRAM_PIF", [1]), ("Schema_si_fise_tehnice", [2]), ("Fotografii", [3])],
    }
    archive = io.BytesIO()
    manifest = ["Pachet DNS Energy — documentele rămân în ordinea de depunere.",
                "Documentele marcate CIORNĂ au date sau fișiere de verificat; nu sunt prezentate ca documente finale.",
                "PDF-urile numerotate sunt copii compilate pentru depunere; fișierele originale încărcate sunt păstrate separat pentru verificarea semnăturilor."]
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for item in original_sources["files"]:
            bundle.writestr(item["archive_name"], item["data"])
            manifest.append(f"Original păstrat: {item['archive_name']} — {item['title']}")
        file_index = 0
        for title, group_indices in layouts[count]:
            included_groups = set(group_indices)
            parts = [part for group, part in ordered_parts if group in included_groups]
            if not parts:
                continue
            file_index += 1
            pdf = _merge_pdf_parts(parts, logger)
            if rec.get("is_test"):
                pdf = mark_test(pdf)
            bundle.writestr(f"{file_index:02d}_{title}.pdf", pdf)
            manifest.append(f"{file_index:02d}_{title}.pdf")
        if unavailable:
            manifest.append("Fișiere neincluse / formulare oficiale indisponibile:")
            manifest.extend(f"- {item}" for item in unavailable)
        if positions_info.get("common_missing"):
            manifest.append("Date comune de verificat:")
            manifest.extend(f"- {item}" for item in positions_info["common_missing"])
        bundle.writestr("00_CITESTE.txt", "\n".join(manifest))
    return archive.getvalue()


def mark_test(pdf: bytes, text: str = "DOSAR DE TEST — NEOFICIAL", size: int = 38) -> bytes:
    """Stamp generated PDFs so test content or missing real measurements cannot be mistaken for final evidence."""
    w = PdfWriter()
    for pg in PdfReader(io.BytesIO(pdf)).pages:
        w.add_page(pg)
    watermark(w, text, size)
    o = io.BytesIO(); w.write(o)
    return o.getvalue()


