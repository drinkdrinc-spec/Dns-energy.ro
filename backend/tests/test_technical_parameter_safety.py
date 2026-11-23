"""Local, network-free regression tests for catalogue-derived PV string calculations."""
import cef
import sizing


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


def test_default_string_fuse_does_not_block_when_parallel_count_does_not_require_it():
    inverter = sample_inverter()
    inverter["panel_isc"] = 13.9
    checked = cef.check({"grid": {"supply": "Trifazat"}, "inverters": [inverter]})
    sized = sizing.compute({"cef": {"grid": {"supply": "Trifazat"}, "inverters": [inverter]}})

    assert not any("siguranța gPV" in error for error in checked["errors"])
    fuse = next(item for item in sized["items"] if item["label"] == "Separator fuzibil gPV / string")
    assert fuse["value"] == "15 A"
    assert fuse["ok"] is None
    assert any("siguranța gPV propusă" in warning for warning in checked["warnings"])


def test_parallel_strings_keep_fuse_rating_block_when_protection_is_required():
    inverter = sample_inverter()
    inverter["panel_isc"] = 13.9
    inverter["strings"] = [{"panels": 10, "mppt": 1} for _ in range(3)]
    checked = cef.check({"grid": {"supply": "Trifazat"}, "inverters": [inverter]})

    assert any("siguranța gPV de 15 A nu se încadrează" in error for error in checked["errors"])


def test_inverter_ac_cable_rejects_sections_outside_requested_phase_ranges():
    for supply, section, expected in [
        ("Monofazat", 4, "3×6–3×16 mm²"),
        ("Monofazat", 25, "3×6–3×16 mm²"),
        ("Trifazat", 4, "5×6–5×50 mm²"),
        ("Trifazat", 70, "5×6–5×50 mm²"),
    ]:
        inverter = sample_inverter()
        inverter["phases"] = supply
        inverter["ac"] = {"section": section, "breaker_a": 16}
        checked = cef.check({"grid": {"supply": supply}, "inverters": [inverter]})

        assert any(expected in error for error in checked["errors"])


def test_bmp_to_board_feeder_rejects_section_below_requested_minimum():
    checked = cef.check({"grid": {
        "supply": "Monofazat", "bransament_kw": 5, "bmp_a": 32, "column_section": 10,
    }})

    assert any("Coloana BMP–TG (10 mm²) este în afara domeniului DNS" in error for error in checked["errors"])


def test_battery_cable_proposal_uses_conservative_standard_table():
    result = cef.battery_cable_proposal({"i_max": 40, "voltage": 51.2})
    assert result["section"] == 10
    assert result["iz"] == 57
    assert result["fuse_a"] is None  # manufacturer maximum fuse is still unknown
    assert result["source"].startswith("IEC 60364-5-52")
    assert "preliminară" in result["note"]


def test_battery_cable_proposal_checks_voltage_drop_when_length_is_known():
    result = cef.battery_cable_proposal({"i_max": 40, "voltage": 51.2, "cable_length": 3})
    assert result["section"] == 16
    assert result["du"] <= 1
    assert result["fuse_a"] is None


def test_battery_cable_proposal_does_not_guess_without_battery_current_or_voltage():
    missing_current = cef.battery_cable_proposal({"voltage": 51.2})
    assert missing_current["section"] is None
    assert missing_current["fuse_a"] is None
    missing_voltage = cef.battery_cable_proposal({"i_max": 40, "cable_length": 3})
    assert missing_voltage["section"] is None
    assert "tensiunea nominală" in missing_voltage["note"]


def test_battery_fuse_is_proposed_only_below_documented_maximum():
    valid = cef.battery_cable_proposal({"i_max": 40, "max_fuse_a": 50})
    assert valid["fuse_a"] == 50
    too_low = cef.battery_cable_proposal({"i_max": 40, "max_fuse_a": 40})
    assert too_low["fuse_a"] is None

def test_sizing_autofill_does_not_guess_battery_fuse_without_datasheet_limit():
    inverter = {
        **sample_inverter(),
        "battery_mode": "own",
        "battery": {"model": "Baterie test", "i_max": 40, "voltage": 51.2},
    }
    result, filled = sizing.apply({"grid": {"supply": "Trifazat"}, "inverters": [inverter]})
    assert "fuse_a" not in result["inverters"][0]["battery"]
    assert not any(path.endswith(".battery.fuse_a") for path in filled)


def test_sizing_autofill_respects_battery_datasheet_fuse_limit():
    inverter = {
        **sample_inverter(),
        "battery_mode": "own",
        "battery": {"model": "Baterie test", "i_max": 40, "voltage": 51.2, "max_fuse_a": 50},
    }
    result, filled = sizing.apply({"grid": {"supply": "Trifazat"}, "inverters": [inverter]})
    assert result["inverters"][0]["battery"]["fuse_a"] == 50
    assert "cef.inverters.0.battery.fuse_a" in filled



def test_catalog_backfill_fills_only_missing_verified_battery_fields():
    from catalog_seed import missing_seed_values

    seed = {
        "i_max": 7.5,
        "coupling": "DC",
        "voltage_1ph": 450,
        "voltage_3ph": 600,
        "i_max_source_url": "https://manufacturer.example/certificate.pdf",
    }
    existing = {"i_max": None, "coupling": "", "voltage_1ph": 0, "voltage_3ph": None}
    assert missing_seed_values(existing, seed) == {
        "i_max": 7.5,
        "coupling": "DC",
        "voltage_1ph": 450,
        "voltage_3ph": 600,
        "i_max_source_url": "https://manufacturer.example/certificate.pdf",
    }


def test_catalog_backfill_never_overwrites_existing_user_values():
    from catalog_seed import missing_seed_values

    existing = {"i_max": 9, "coupling": "AC", "voltage_1ph": 230, "voltage_3ph": 400, "i_max_source_url": "manual.pdf"}
    seed = {"i_max": 7.5, "coupling": "DC", "voltage_1ph": 450, "voltage_3ph": 600, "i_max_source_url": "official.pdf"}
    assert missing_seed_values(existing, seed) == {}


def test_catalog_backfill_fills_missing_rsd_model_ratings_but_preserves_manual_values():
    from catalog_seed import missing_seed_values

    seed = {
        "string_count": 2, "poles": 4, "voltage_min_v": 300, "voltage_max_v": 1500,
        "current_1000v_a": 40, "current_1200v_a": 30, "current_1500v_a": 20,
        "ac_voltage_min_v": 100, "ac_voltage_max_v": 270, "ip_rating": "66", "protection_class": "II",
    }
    existing = {"category": "RSD", "string_count": None, "poles": 4, "voltage_min_v": 0,
                "current_1000v_a": 32, "current_1200v_a": None, "ip_rating": "65"}

    assert missing_seed_values(existing, seed) == {
        "string_count": 2, "voltage_min_v": 300, "voltage_max_v": 1500,
        "current_1200v_a": 30, "current_1500v_a": 20,
        "ac_voltage_min_v": 100, "ac_voltage_max_v": 270, "protection_class": "II",
    }


def test_selected_rsd_is_checked_against_string_voltage_and_current():
    import sizing

    inverter = {
        "brand_model": "Invertor test", "type": "On-grid", "phases": "Trifazat",
        "p_nom_kw": 5, "p_max_kw": 5, "vdc_max": 1000, "mppt_min": 100,
        "mppt_max": 850, "mppt_count": 1, "imax_mppt": 20, "isc_max_mppt": 20,
        "panel_model": "Panou test", "panel_w": 500, "panel_voc": 45,
        "panel_vmp": 37, "panel_isc": 12, "panel_coef_voc": -0.3,
        "panel_coef_vmp": -0.3, "strings": [{"panels": 10, "mppt": 1}],
        "rsd": {"enabled": True, "brand_model": "PROJOY PEFS-EL40H-4(P2) 2-STRING",
                "string_count": 2, "poles": 4, "voltage_max_v": 1500,
                "current_300v_a": 40, "current_600v_a": 40, "current_800v_a": 40,
                "current_1000v_a": 40, "current_1200v_a": 30, "current_1500v_a": 20},
    }
    result = sizing.compute({"cef": {"tmin": -10, "grid": {}, "inverters": [inverter]}}, {})
    checks = [item for item in result["items"] if item["group"] == "RSD INV 1"]
    assert next(item for item in checks if item["label"] == "Canale/stringuri și poli RSD")["ok"] is True
    assert next(item for item in checks if item["label"] == "Tensiune de proiectare RSD")["ok"] is True
    assert next(item for item in checks if item["label"] == "Curent admis RSD la 600 V")["ok"] is True

    inverter["rsd"]["current_600v_a"] = 10
    result = sizing.compute({"cef": {"tmin": -10, "grid": {}, "inverters": [inverter]}}, {})
    current_check = next(item for item in result["items"] if item["label"] == "Curent admis RSD la 600 V")
    assert current_check["ok"] is False
    assert any("RSD INV 1" in error and "NECONFORM" in error for error in result["errors"])
def test_mixed_panel_models_use_each_strings_current_and_voltage_for_checks():
    inverter = {
        **sample_inverter(),
        "isc_max_mppt": 25,
        "dc": {"length_m": 100},
        "strings": [
            {"panels": 10, "mppt": 1, "panel_model": "Panel A", "panel_w": 500,
             "panel_voc": 40, "panel_vmp": 30, "panel_isc": 15, "panel_imp": 14},
            {"panels": 10, "mppt": 2, "panel_model": "Panel B", "panel_w": 400,
             "panel_voc": 50, "panel_vmp": 40, "panel_isc": 10, "panel_imp": 8},
        ],
    }
    result = cef.check({"grid": {"supply": "Trifazat"}, "inverters": [inverter]})
    sizing_result = sizing.compute({"cef": {"tmin": -10, "grid": {"supply": "Trifazat"},
                                               "inverters": [inverter]}}, {})
    items = sizing_result["items"]
    mppt_1 = next(item for item in items if item["label"] == "MPPT 1 — Imp total în funcționare")
    mppt_2 = next(item for item in items if item["label"] == "MPPT 2 — Imp total în funcționare")
    assert mppt_1["value"] == "14 A"
    assert mppt_2["value"] == "8 A"
    # The 14 A, 300 V string needs 25 mm² at 100 m to meet the 1% proposal.
    # Combining its current with the other string's higher voltage would under-size it.
    assert result["inverters"][0]["proposals"]["dc"]["section"] == 25
