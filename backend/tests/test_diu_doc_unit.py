from types import SimpleNamespace

import diu_doc
import docgen


def _render_isolation(test_v, riso):
    record = {
        "pram_m": {"test_v": test_v},
        "circuits": [{"name": "Circuit test", "riso": riso}],
    }
    blocks = diu_doc.doc_izol(
        SimpleNamespace(name="Test", loc="Test", company="Firma test", rep="Reprezentant test"),
        record,
        [],
    )
    table = next(block[1] for block in blocks if block[0] == "table")
    return table[-1][-1]


def test_isolation_result_requires_actual_test_voltage():
    assert _render_isolation(None, "250") == "—"
    assert _render_isolation("0", "250") == "—"


def test_isolation_result_uses_recorded_measurement_and_threshold():
    assert _render_isolation("500", "250") == "Corespunde"
    assert _render_isolation("500", "0.5") == "NU corespunde"
    assert _render_isolation("500", None) == "—"


def test_diu_equipment_schedule_lists_selected_rsd():
    ctx = docgen.Ctx({"cef": {"inverters": [{
        "brand_model": "Inverter test", "rsd": {"enabled": True, "brand_model": "PROJOY PEFS-EL40H-4(P2)"},
    }]}}, {}, {})
    rows = docgen.equipment_lines(ctx)

    assert ["Oprire rapidă stringuri fotovoltaice (RSD)", "1 buc", "PROJOY PEFS-EL40H-4(P2)"] in rows
