import io

from docx import Document

import atr_doc


def test_deer_annex2_lists_battery_details_without_mixing_kwh_into_inverter_kw_table():
    pros = {
        "operator": "DEER",
        "cef": {
            "inverters": [{
                "brand_model": "Invertor test 10 kW",
                "p_nom_kw": 10,
                "panel_model": "Panou test 450 W",
                "panel_w": 450,
                "strings": [{"panels": 24, "mppt": 1}],
                "battery_mode": "own",
                "battery": {
                    "model": "Baterie test 10 kWh",
                    "kwh": 10,
                    "modules": 2,
                    "voltage": 51.2,
                    "ah": 200,
                    "i_max": 100,
                    "coupling": "DC",
                },
            }],
        },
    }
    rec = {
        "operator": "DEER",
        "deer_case": "Loc existent — notificare — Anexa 2",
        "request_type": "modificare",
    }

    content = atr_doc.render_deer_official_docx(rec, {}, {}, pros)
    doc = Document(io.BytesIO(content))
    inverter_table_text = " ".join(
        cell.text for row in doc.tables[3].rows for cell in row.cells
    )
    details_table_text = " ".join(
        cell.text for row in doc.tables[5].rows for cell in row.cells
    )

    assert "Invertor test 10 kW" in inverter_table_text
    assert "Baterie test 10 kWh" not in inverter_table_text
    assert "Baterie test 10 kWh" in details_table_text
    assert "20 kWh" in details_table_text
    assert "51.2 V" in details_table_text
    assert "200 Ah" in details_table_text
    assert "100 A" in details_table_text
    assert "cuplare DC" in details_table_text

