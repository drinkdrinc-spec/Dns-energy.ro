"""Local, network-free regression tests for catalogue-derived PV string calculations."""
import cef


def sample_inverter():
    return {
        "brand_model": "Invertor test",
        "type": "On-grid",
        "phases": "Trifazat",
        "p_nom_kw": 10,
        "p_max_kw": 10,
        "vdc_max": 1000,
        "mppt_min": 150,
        "mppt_max": 850,
        "mppt_count": 2,
        "imax_mppt": 20,
        "panel_model": "Panou test",
        "panel_w": 500,
        "panel_voc": 45,
        "panel_vmp": 37,
        "panel_isc": 12,
        "strings": [{"panels": 10, "mppt": 1}],
    }


def test_missing_temperature_coefficients_are_not_invented():
    result = cef.check({"grid": {"supply": "Trifazat"}, "inverters": [sample_inverter()]})
    string = result["inverters"][0]["strings"][0]
    assert string["voc_cold"] is None
    assert string["vmp_hot"] is None
    assert any("coeficientul de temperatură Voc" in warning for warning in result["warnings"])
    assert any("coeficientul de temperatură Vmp" in warning for warning in result["warnings"])


def test_catalog_temperature_coefficients_are_used_when_present():
    inverter = sample_inverter()
    inverter["panel_coef_voc"] = -0.25
    inverter["panel_coef_vmp"] = -0.30
    result = cef.check({"grid": {"supply": "Trifazat"}, "inverters": [inverter]})
    string = result["inverters"][0]["strings"][0]
    assert string["voc_cold"] is not None
    assert string["vmp_hot"] is not None
    assert abs(string["voc_cold"] - (10 * 45 * (1 + (-0.25 / 100) * (-10 - 25)))) < 0.1
    assert abs(string["vmp_hot"] - (10 * 37 * (1 + (-0.30 / 100) * (70 - 25)))) < 0.1


def test_string_power_and_stc_values_remain_available_without_coefficients():
    result = cef.check({"grid": {"supply": "Trifazat"}, "inverters": [sample_inverter()]})
    string = result["inverters"][0]["strings"][0]
    assert string["panels"] == 10
    assert string["kwp"] == 5
    assert string["voc_stc"] == 450
    assert string["vmp_stc"] == 370
