from types import SimpleNamespace

import diu_doc


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
