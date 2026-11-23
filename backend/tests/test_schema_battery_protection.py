import json
from copy import deepcopy
from io import BytesIO
from pathlib import Path

from PIL import Image as PILImage
from pypdf import PdfReader

import docgen
import pif_doc as PIFDOC
import cef as CEF
import sizing as SZ
import sld as SLD
from sld_demo import DEMO_CLIENT, DEMO_REC


def _sample_cef():
    return json.loads((Path(__file__).parent / "cef_sample.json").read_text(encoding="utf-8"))


def _schema_text(cef):
    rec = {
        "name": "Beneficiar test",
        "address": "Adresa test",
        "operator": "DEER",
        "pod": "POD-TEST",
        "grounding_ohm": 4.2,
        "cef": cef,
    }
    pdf = docgen.render(
        ["schema_cef"],
        rec,
        {"company": "DNS Energy Test", "rep": "Reprezentant Test", "anre_attest": "ATEST"},
        {},
    )
    return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)


def test_schema_pdf_shows_battery_dc_switch_cable_and_documented_protection():
    cef = _sample_cef()
    battery = cef["inverters"][0]["battery"]
    battery.update({
        "i_max": 100,
        "max_fuse_a": 125,
        "fuse_a": 100,
        "cable_section": 35,
        "cable_length": 2,
        "dc_switch_voltage_v": 75,
        "dc_switch_current_a": 125,
    })

    text = _schema_text(cef)

    assert "BATERIE (DC)" in text
    assert "QBAT DC" in text
    assert "75 V / 125 A" in text
    assert "Cablu DC: 35 mm²" in text
    assert "100 A" in text
    assert "Imax 100 A" in text
    assert "Voc rece la Tmin: NECONFIRMAT" in text


def _test_company_logo():
    image = PILImage.new("RGB", (64, 32), (31, 106, 69))
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def test_generated_sld_embeds_configured_company_logo():
    res = SZ.compute(DEMO_REC, DEMO_CLIENT)
    pdf = SLD.render(DEMO_REC, DEMO_CLIENT, {"company": "DNS Energy", "_header_logo_bytes": _test_company_logo()}, res,
                     {"status": "draft"}, fmt="A3", demo=True)
    assert len(PdfReader(BytesIO(pdf)).pages[0].images) == 1


def test_generated_document_header_embeds_configured_company_logo(monkeypatch):
    logo = _test_company_logo()
    docgen._IMG_CACHE.clear()
    monkeypatch.setattr(docgen, "IMG_LOADER", lambda _path: logo)
    rec = {"name": "Beneficiar test", "address": "Adresa test", "operator": "DEER", "pod": "POD-TEST"}
    client = {"name": "Beneficiar test", "address": "Adresa test", "kind": "persoană fizică"}
    settings = {"company": "DNS Energy", "header_logo": {"storage_path": "test/logo.png"}}
    pdf = docgen.render(["declaratie_autenticitate"], rec, settings, client)
    assert len(PdfReader(BytesIO(pdf)).pages[0].images) >= 1


def test_generated_sld_uses_dns_official_logo_by_default():
    res = SZ.compute(DEMO_REC, DEMO_CLIENT)
    pdf = SLD.render(DEMO_REC, DEMO_CLIENT, {"company": "DNS HOSTESS S.R.L."}, res,
                     {"status": "draft"}, fmt="A3", demo=True)
    assert len(PdfReader(BytesIO(pdf)).pages[0].images) == 1


def test_generated_document_header_uses_dns_official_logo_by_default(monkeypatch):
    docgen._IMG_CACHE.clear()
    monkeypatch.setattr(docgen, "IMG_LOADER", None)
    rec = {"name": "Beneficiar test", "address": "Adresa test", "operator": "DEER", "pod": "POD-TEST"}
    client = {"name": "Beneficiar test", "address": "Adresa test", "kind": "persoană fizică"}
    pdf = docgen.render(["declaratie_autenticitate"], rec, {"company": "DNS HOSTESS S.R.L."}, client)
    assert len(PdfReader(BytesIO(pdf)).pages[0].images) >= 1


def test_pif_document_uses_dns_official_logo_by_default(monkeypatch):
    docgen._IMG_CACHE.clear()
    monkeypatch.setattr(docgen, "IMG_LOADER", None)
    pdf = PIFDOC.render(DEMO_REC, DEMO_CLIENT, {"company": "DNS HOSTESS S.R.L."})
    assert len(PdfReader(BytesIO(pdf)).pages[0].images) >= 1


def test_schema_pdf_marks_missing_battery_switch_rating_for_confirmation():
    cef = _sample_cef()
    battery = cef["inverters"][0]["battery"]
    battery.pop("dc_switch_voltage_v", None)
    battery.pop("dc_switch_current_a", None)
    battery.pop("cable_section", None)
    battery.pop("fuse_a", None)

    text = _schema_text(cef)

    assert "BATERIE (DC)" in text
    assert "Qbat DC: tensiune/curent nominal de confirmat" in text
    assert "Cablu DC:" in text


def test_ac_coupled_battery_still_shows_dc_battery_to_inverter_connection():
    cef = _sample_cef()
    battery = cef["inverters"][0]["battery"]
    battery.update({
        "coupling": "AC",
        "i_max": 100,
        "max_fuse_a": 125,
        "fuse_a": 100,
        "cable_section": 35,
        "cable_length": 2,
        "dc_switch_voltage_v": 75,
        "dc_switch_current_a": 125,
    })

    text = _schema_text(cef)

    assert "BATERIE (AC)" in text
    assert "QBAT DC" in text
    assert "75 V / 125 A" in text
    assert "Cablu DC: 35 mm²" in text


def test_shared_battery_total_capacity_multiplies_module_count():
    cef = _sample_cef()

    text = _schema_text(cef)

    assert "3 × 4.8 kWh · total 14.4 kWh" in text

def test_ac_coupled_bess_uses_a_separate_battery_inverter_pcs():
    cef = _sample_cef()
    cef["inverters"][0]["battery_mode"] = "none"
    cef["inverters"][0].pop("battery", None)
    cef["inverters"].append({
        "brand_model": "PCS BESS test",
        "type": "Invertor de baterie (AC)",
        "phases": "Trifazat",
        "p_nom_kw": 5,
        "p_max_kw": 5,
        "p_limit_kw": 5,
        "strings": [],
        "battery_mode": "shared",
        "shared_battery_id": "bess-ac",
        "ac": {"material": "Cu", "install": "C", "length_m": 5, "section": 4, "breaker_a": 16},
    })
    battery = {
        "id": "bess-ac",
        "model": "BESS AC test",
        "kwh": 10,
        "modules": 1,
        "voltage": 100,
        "i_max": 100,
        "max_fuse_a": 125,
        "fuse_a": 100,
        "cable_section": 35,
        "cable_length": 2,
        "dc_switch_voltage_v": 75,
        "dc_switch_current_a": 125,
        "coupling": "AC",
    }
    cef["shared_batteries"] = [battery]

    text = _schema_text(cef)

    assert "BATERIE COMUNĂ (AC)" in text
    assert "Invertor de baterie (AC)" in text
    assert "QBAT DC" in text
    assert "75 V / 125 A" in text
    assert "Cablu DC: 35 mm²" in text
    assert not any("BESS AC test" in error for error in CEF.check(cef)["errors"])


def test_ac_coupled_battery_cannot_be_drawn_as_dc_on_a_pv_inverter():
    cef = _sample_cef()
    cef["inverters"][0]["battery"]["coupling"] = "AC"

    text = _schema_text(cef)
    result = CEF.check(cef)

    assert "PCS AC separat: neconfigurat" in text
    assert any("bateria proprie este setată cu cuplare AC" in error for error in result["errors"])


def test_shared_battery_total_capacity_multiplies_module_count():
    cef = _sample_cef()

    text = _schema_text(cef)

    assert "3 × 4.8 kWh · total 14.4 kWh" in text


def test_battery_cable_ampacity_must_cover_selected_fuse():
    proposal = CEF.battery_cable_proposal({
        "i_max": 33,
        "voltage": 48,
        "max_fuse_a": 63,
        "cable_ampacities": [
            {"section": 6, "ampacity_a": 42},
            {"section": 10, "ampacity_a": 57},
        ],
    })

    assert proposal["fuse_a"] == 50
    assert proposal["section"] == 10
    assert proposal["iz"] >= proposal["fuse_a"]



def _sheet_data(rec):
    result = SZ.compute(rec, DEMO_CLIENT)
    return SLD.sheet_data(
        rec,
        DEMO_CLIENT,
        {"company": "DNS HOSTESS S.R.L."},
        result,
        {"status": "approved", "approvals": {}},
    )


class _CanvasCapture:
    def setFillColor(self, *args, **kwargs):
        pass

    def rect(self, *args, **kwargs):
        pass

    def stringWidth(self, text, font, size):
        return len(text) * size * 0.5


class _TextCapture:
    def __init__(self):
        self.values = []
        self.c = _CanvasCapture()

    def enclosure(self, *args, **kwargs):
        pass

    def text(self, *args, **kwargs):
        self.values.append(str(args[2]))

    def wire(self, *args, **kwargs):
        pass

    def rcd(self, *args, **kwargs):
        pass

    def switch(self, *args, **kwargs):
        pass

    def node(self, *args, **kwargs):
        pass


def test_partial_backup_marks_only_selected_teg_circuits_on_schema():
    rec = deepcopy(DEMO_REC)
    grid = rec["cef"]["grid"]
    grid.update({
        "backup_mode": "Parțial (doar circuite critice)",
        "circuits": [
            {"name": "Iluminat", "breaker": "C10", "backup": True},
            {"name": "Cuptor", "breaker": "C16", "backup": False},
        ],
    })
    capture = _TextCapture()

    SLD.teg_schedule(capture, (0, 0, 220, 100), rec)

    text = " ".join(capture.values)
    assert "Iluminat" in text and "LOAD/EPS" in text
    assert "Cuptor" in text and "rețea" in text
    assert "LOAD/EPS → TEG: Iluminat" in text


def test_total_backup_marks_every_teg_circuit_on_schema():
    rec = deepcopy(DEMO_REC)
    grid = rec["cef"]["grid"]
    grid.update({
        "backup_mode": "Total (tot TEG-ul pe backup)",
        "circuits": [{"name": "Iluminat"}, {"name": "Prize"}],
    })
    capture = _TextCapture()

    SLD.teg_schedule(capture, (0, 0, 220, 100), rec)

    assert all("LOAD/EPS" in value for value in capture.values if value.startswith("C"))
    assert "LOAD/EPS → TEG: Iluminat, Prize" in " ".join(capture.values)


def test_partial_backup_requires_at_least_one_selected_circuit():
    cef = _sample_cef()
    cef["grid"].update({
        "backup_mode": "Parțial (doar circuite critice)",
        "circuits": [{"name": "Iluminat", "backup": False}],
    })
    cef["inverters"][0]["backup"] = {"enabled": True}

    result = CEF.check(cef)

    assert any("nu este bifat niciun circuit TEG" in error for error in result["errors"])


def test_backup_schema_note_states_islanding_separation_and_reconnect_delay():
    rec = deepcopy(DEMO_REC)
    capture = _TextCapture()

    SLD.execution_notes(capture, (0, 0, 500, 500), rec)

    text = " ".join(capture.values)
    assert "QINT separă instalația de RED" in text
    assert "fără injecție în RED" in text
    assert "Reconectare după ≥15 min" in text


def test_mixed_panel_models_keep_separate_string_counts_and_power():
    rec = deepcopy(DEMO_REC)
    inverter = rec["cef"]["inverters"][0]
    inverter["strings"] = [
        {
            "panels": 10,
            "mppt": 1,
            "panel_model": "JINKO JKM510M",
            "panel_w": 510,
            "panel_voc": 49.5,
            "panel_vmp": 41.5,
            "panel_isc": 13.1,
            "panel_coef_voc": -0.28,
        },
        {
            "panels": 8,
            "mppt": 2,
            "panel_model": "AIKO A500",
            "panel_w": 500,
            "panel_voc": 45.5,
            "panel_vmp": 38.5,
            "panel_isc": 14.0,
            "panel_coef_voc": -0.26,
        },
    ]

    data = _sheet_data(rec)
    base_strings = SZ.compute(rec, DEMO_CLIENT)["base"]["inverters"][0]["strings"]
    equipment = next(section[2] for section in data["sections"] if section[0] == "2. Lista echipamentelor")
    panels = [row for row in equipment if row[1] == "Module fotovoltaice"]

    assert [(row[2], row[4]) for row in panels] == [
        ("JINKO JKM510M", "10"),
        ("AIKO A500", "8"),
    ]
    assert [round(row["kwp"], 2) for row in base_strings] == [5.1, 4.0]


def test_battery_only_hybrid_has_zero_export_and_is_identified_in_sheet():
    rec = deepcopy(DEMO_REC)
    pv_export = CEF.check(rec["cef"])["totals"]["export_kw"]
    rec["cef"]["inverters"].append({
        "brand_model": "Deye SUN-8K battery-only",
        "type": "Hibrid",
        "kind": "Hibrid",
        "phases": "Trifazat",
        "p_nom_kw": 8,
        "p_max_kw": 8,
        "p_limit_kw": 8,
        "battery_only": True,
        "no_panels": True,
        "strings": [],
        "battery_mode": "own",
        "battery": {
            "model": "Dyness 16.07 kWh",
            "kwh": 16.07,
            "voltage": 51.2,
            "modules": 1,
            "coupling": "DC",
            "i_max": 100,
        },
    })

    checked = CEF.check(rec["cef"])
    data = _sheet_data(rec)
    equipment = next(section[2] for section in data["sections"] if section[0] == "2. Lista echipamentelor")
    capture = _TextCapture()
    SLD.execution_notes(capture, (0, 0, 500, 500), rec)

    assert checked["totals"]["export_kw"] == pv_export
    assert checked["inverters"][1]["kwp"] == 0
    assert any(row[2] == "Dyness 16.07 kWh" for row in equipment)
    assert any("putere evacuată 0 kW" in value for value in capture.values)

