import power_diu_sync as sync


def _power(supply="Trifazat", breaker=40, inverter_breaker=25):
    return {
        "new_supply": supply,
        "power_cef": {
            "grid": {"supply": supply, "earthing": "TN-S", "tg_breaker_a": breaker, "bmp_a": 32},
            "inverters": [{
                "brand_model": "Inverter test",
                "count": 2,
                "ac": {"breaker_a": inverter_breaker, "section": 6, "cable_type": "RVK 5x6", "length_m": 12},
                "rcd_ma": 30,
                "rcd_type": "Tip A",
                "battery_mode": "own",
                "battery": {"model": "Baterie test", "kwh": 10},
            }],
            "shared_batteries": [],
        },
    }


def test_power_request_maps_declared_design_into_diu_without_pram_measurements():
    fields = sync.power_cef_diu_fields(_power())

    assert fields["supply"] == "Trifazat"
    assert fields["earthing"] == "TN-S"
    assert fields["tg_breaker_a"] == 40
    assert fields["type"] == "Sistem fotovoltaic hibrid"
    assert fields["cef"]["inverters"][0]["brand_model"] == "Inverter test"
    assert fields["cef"]["inverters"][0]["battery"]["model"] == "Baterie test"
    assert fields["circuits"] == [{
        "name": "INV1 — Inverter test × 2 buc.",
        "breaker_a": 25,
        "curve": "C",
        "section": 6,
        "cable": "RVK 5x6",
        "length": 12,
        "rcd_ma": 30,
        "rcd_type": "A",
    }]
    assert "pram_m" not in fields
    assert "earth_ohm" not in fields
    assert "power_cef_snapshot" not in fields


def test_power_request_fills_empty_diu_fields():
    fields = sync.power_cef_diu_sync({"circuits": []}, _power())

    assert fields["tg_breaker_a"] == 40
    assert fields["circuits"][0]["breaker_a"] == 25


def test_power_request_refreshes_unchanged_fields_but_preserves_manual_edits():
    old_power = _power()
    old_fields = sync.power_cef_diu_fields(old_power)
    rec = {
        **{key: value for key, value in old_fields.items() if key != "power_cef_snapshot"},
        "power_cef_snapshot": old_fields,
        "tg_breaker_a": 50,  # manually edited after the original synchronization
    }

    fields = sync.power_cef_diu_sync(rec, _power(supply="Monofazat", breaker=63, inverter_breaker=32))

    assert fields["supply"] == "Monofazat"  # still matches prior synchronized value
    assert fields["circuits"][0]["breaker_a"] == 32
    assert "tg_breaker_a" not in fields  # manual value is not overwritten
    assert fields["power_cef_snapshot"]["tg_breaker_a"] == 63


def test_power_request_preserves_manual_diu_cef_edits_after_initial_sync():
    old_power = _power()
    old_fields = sync.power_cef_diu_fields(old_power)
    manual = {"grid": {}, "inverters": [{"brand_model": "Manual DI-U equipment"}]}
    rec = {"cef": manual, "power_cef_snapshot": old_fields}

    refreshed = sync.power_cef_diu_sync(rec, _power())

    assert "cef" not in refreshed


def test_power_request_does_not_infer_photovoltaic_type_without_declared_equipment():
    fields = sync.power_cef_diu_fields({"new_supply": "Monofazat", "power_cef": {"grid": {}, "inverters": []}})

    assert fields["supply"] == "Monofazat"
    assert "type" not in fields


def test_linked_prosumer_copies_full_equipment_configuration_into_diu():
    prosumer = {
        "id": "pros-1",
        "cef": {
            "grid": {"meter": "Smart meter example"},
            "inverters": [{
                "brand_model": "Hybrid 10kW", "panel_model": "Panel 450W",
                "strings": [{"panels": 12, "mppt": 1}], "panel_w": 450,
                "battery_mode": "own", "battery": {"model": "Battery 10kWh", "kwh": 10},
            }],
            "shared_batteries": [],
        },
    }

    mapped = sync.prosumer_cef_diu_sync({"pros_id": "pros-1"}, prosumer)

    assert mapped["cef"]["inverters"][0]["brand_model"] == "Hybrid 10kW"
    assert mapped["cef"]["inverters"][0]["panel_model"] == "Panel 450W"
    assert mapped["cef"]["inverters"][0]["battery"]["model"] == "Battery 10kWh"
    assert mapped["prosumer_cef_snapshot"] == mapped["cef"]


def test_linked_prosumer_refreshes_unchanged_cef_but_preserves_manual_diu_edits():
    previous = {"grid": {}, "inverters": [{"brand_model": "Old"}], "shared_batteries": []}
    source = {"grid": {}, "inverters": [{"brand_model": "New"}], "shared_batteries": []}
    prosumer = {"id": "pros-1", "cef": source}

    unchanged = sync.prosumer_cef_diu_sync({"pros_id": "pros-1", "cef": previous, "prosumer_cef_snapshot": previous}, prosumer)
    edited = sync.prosumer_cef_diu_sync({"pros_id": "pros-1", "cef": {"inverters": [{"brand_model": "Manual"}]}, "prosumer_cef_snapshot": previous}, prosumer)

    assert unchanged["cef"] == source
    assert "cef" not in edited
    assert edited["prosumer_cef_snapshot"] == source


