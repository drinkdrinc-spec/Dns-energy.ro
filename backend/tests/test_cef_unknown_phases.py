import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from cef import check, from_legacy
from sizing import apply, compute


def test_unknown_phase_does_not_propose_ac_or_grid_protection():
    cef = {
        "inverters": [{"brand_model": "TEST inverter", "p_nom_kw": 5, "p_max_kw": 5}],
        "grid": {"bransament_kw": 10},
    }

    result = check(cef)

    assert result["grid"]["tri"] is None
    assert result["grid"]["i_br"] == 0
    assert result["grid"]["main_proposal"] is None
    inverter = result["inverters"][0]
    assert inverter["phase_known"] is False
    assert inverter["proposals"]["ac"]["breaker_a"] is None
    assert inverter["proposals"]["ac"]["section"] is None
    assert any("nu se propun" in warning for warning in result["warnings"])

    report = compute({"cef": cef}, {})
    assert not any(item["label"] == "AC — curent de calcul Ib" for item in report["items"])
    assert report["base"]["grid"]["main_proposal"] is None

    filled, changes = apply(cef)
    assert "cef.inverters.0.ac.breaker_a" not in changes
    assert "cef.inverters.0.ac.section" not in changes


def test_legacy_record_does_not_become_three_phase_by_default():
    record = from_legacy({"inverter": "TEST legacy", "inverter_kw": 5})
    inverter = record["cef"]["inverters"][0]
    assert "phases" not in inverter
    assert check(record["cef"])["inverters"][0]["phase_known"] is False


def test_explicit_supply_still_enables_sizing_proposals():
    result = check({
        "inverters": [{"brand_model": "TEST inverter", "p_nom_kw": 5, "p_max_kw": 5}],
        "grid": {"supply": "Trifazat", "bransament_kw": 10},
    })
    inverter = result["inverters"][0]
    assert inverter["phase_known"] is True
    assert inverter["proposals"]["ac"]["breaker_a"] is not None
    assert result["grid"]["main_proposal"] is not None
