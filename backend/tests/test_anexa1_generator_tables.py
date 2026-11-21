import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from power_doc import _generator_tables


def _number(value):
    return float(str(value).replace(",", "."))


def test_anexa1_lists_each_panel_model_with_its_own_count_and_power():
    rows, inverters, _ = _generator_tables([
        {
            "brand_model": "Hybrid TEST 15",
            "count": 2,
            "p_nom_kw": 15,
            "p_max_kw": 15,
            "panel_model": "Jinko 510",
            "panel_w": 510,
            "strings": [
                {"panel_model": "Jinko 510", "panel_w": 510, "panels": 10},
                {"panel_model": "AIKO 500", "panel_w": 500, "panels": 12},
            ],
        }
    ])

    panel_rows = rows[1:]
    assert len(panel_rows) == 2
    by_model = {row[2]: row for row in panel_rows}
    assert by_model["AIKO 500"][1] == "24"
    assert _number(by_model["AIKO 500"][3]) == 0.5
    assert _number(by_model["AIKO 500"][4]) == 12
    assert _number(by_model["AIKO 500"][6]) == 6
    assert by_model["Jinko 510"][1] == "20"
    assert _number(by_model["Jinko 510"][3]) == 0.51
    assert _number(by_model["Jinko 510"][4]) == 10.2
    assert _number(by_model["Jinko 510"][6]) == 5.1
    assert inverters[1][2] == "Hybrid TEST 15"


def test_anexa1_battery_only_hybrid_has_zero_grid_export():
    rows, inverters, notes = _generator_tables([
        {
            "brand_model": "Hybrid TEST 8",
            "count": 1,
            "p_nom_kw": 8,
            "p_max_kw": 8,
            "p_limit_kw": 8,
            "battery_only": True,
            "panel_model": "Must not appear as PV",
            "panel_w": 510,
            "strings": [],
        }
    ])

    assert rows[1][1] == "0"
    assert "Fără panouri (doar baterie)" in rows[1][2]
    assert "Must not appear as PV" not in rows[1][2]
    assert inverters[1][5] == "0"
    assert "injecție 0 kW" in inverters[1][6]
    assert "putere evacuată 0 kW" in notes[0]
