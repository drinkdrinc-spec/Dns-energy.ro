import io

from docx import Document
import pytest

import atr_doc


@pytest.mark.parametrize(
    ("deer_case", "inverter_table_index", "detail_table_index"),
    [
        ("Loc existent — spor de putere — Anexa 1", 6, 8),
        ("Loc existent — notificare — Anexa 2", 3, 5),
        ("Loc existent prosumator — actualizare CRR — Anexa 3", None, 0),
        ("Prosumator prin program de finanțare — Anexa 4", 6, 8),
        ("Loc existent ≤10,8 kW — notificare simplificată — Anexa 5", 6, 8),
    ],
)
def test_deer_annexes_keep_battery_details_out_of_inverter_kw_table(deer_case, inverter_table_index, detail_table_index):
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
        "deer_case": deer_case,
        "request_type": "spor de putere" if "spor" in deer_case else "modificare",
    }

    content = atr_doc.render_deer_official_docx(rec, {}, {}, pros)
    doc = Document(io.BytesIO(content))
    inverter_table_text = ""
    inverter_active_power_cells = []
    if inverter_table_index is not None:
        inverter_table_text = " ".join(
            cell.text for row in doc.tables[inverter_table_index].rows for cell in row.cells
        )
        inverter_active_power_cells = [row.cells[4].text.strip() for row in doc.tables[inverter_table_index].rows]
    details_table_text = " ".join(
        cell.text for row in doc.tables[detail_table_index].rows for cell in row.cells
    )

    if inverter_table_index is not None:
        assert "Invertor test 10 kW" in inverter_table_text
        assert "Baterie test 10 kWh" in inverter_table_text
        assert "20 kWh total" in inverter_table_text
        assert "51.2 V DC" in inverter_table_text
        assert "200 Ah/modul" in inverter_table_text
        assert "100 I max/modul A" in inverter_table_text
        assert "cuplare DC" in inverter_table_text
    assert "Baterie test 10 kWh" in details_table_text
    assert "20 kWh" in details_table_text
    assert "51.2 V" in details_table_text
    assert "200 Ah" in details_table_text
    assert "100 A" in details_table_text
    assert "cuplare DC" in details_table_text
    assert "20" not in inverter_active_power_cells
    if inverter_table_index == 6:
        assert "10 kWh/modul" in inverter_table_text

def test_storage_details_ignores_undeclared_batteries():
    pros = {
        "cef": {
            "inverters": [
                {"battery_mode": "own", "battery": {}},
                {"battery_mode": "own", "battery": {"model": "Fără baterie"}},
            ],
            "shared_batteries": [{}, {"model": "Fără baterie"}],
        }
    }
    rec = {"battery": "Fără baterie", "storage": ""}
    assert atr_doc.storage_details(pros, rec) == []
