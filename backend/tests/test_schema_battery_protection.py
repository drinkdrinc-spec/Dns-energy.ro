import json
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

import docgen


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
