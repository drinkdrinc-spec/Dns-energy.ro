from cef import string_calc, check


def test_temperature_calculations_require_model_specific_coefficients():
    result = string_calc(
        {"panels": 10, "mppt": 1},
        {"panel_voc": 40, "panel_vmp": 33, "panel_isc": 14, "panel_w": 450},
        -10,
    )

    assert result["voc_stc"] == 400
    assert result["vmp_stc"] == 330
    assert result["voc_cold"] is None
    assert result["vmp_hot"] is None


def test_temperature_calculations_use_exact_supplied_coefficients():
    result = string_calc(
        {"panels": 10, "mppt": 1},
        {
            "panel_voc": 40,
            "panel_vmp": 33,
            "panel_isc": 14,
            "panel_w": 450,
            "panel_coef_voc": -0.25,
            "panel_coef_vmp": -0.29,
        },
        -10,
    )

    assert round(result["voc_cold"], 2) == 435.0
    assert round(result["vmp_hot"], 2) == 286.95


def test_missing_temperature_coefficients_are_reported_as_warnings():
    result = check({
        "grid": {"supply": "Trifazat"},
        "inverters": [{
            "p_nom_kw": 5,
            "p_max_kw": 5,
            "p_limit_kw": 5,
            "phases": "Trifazat",
            "kind": "Hibrid",
            "type": "Hibrid",
            "panel_w": 450,
            "panel_voc": 40,
            "panel_vmp": 33,
            "panel_isc": 14,
            "vdc_max": 1000,
            "mppt_min": 100,
            "mppt_max": 800,
            "mppt_count": 2,
            "imax_mppt": 20,
            "strings": [{"panels": 10, "mppt": 1}],
            "ac": {},
            "dc": {},
        }],
    })

    inverter = result["inverters"][0]
    assert inverter["strings"][0]["voc_cold"] is None
    assert inverter["strings"][0]["vmp_hot"] is None
    assert inverter["voc_cold_max"] is None
    assert any("coeficientul de temperatură Voc" in warning for warning in inverter["warnings"])
    assert any("coeficientul de temperatură Vmp" in warning for warning in inverter["warnings"])
