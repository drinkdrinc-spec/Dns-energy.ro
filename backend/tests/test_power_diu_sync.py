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


def test_power_request_fills_empty_diu_fields():
    fields = sync.power_cef_diu_sync({"circuits": []}, _power())

    assert fields["tg_breaker_a"] == 40
    assert fields["circuits"][0]["breaker_a"] == 25


def test_power_request_refreshes_unchanged_fields_but_preserves_manual_edits():
    old_power = _power()
    old_fields = sync.power_cef_diu_fields(old_power)
    rec = {
        **{key: value for key, value in old_fields.items() if key != "power_cef_snapshot"},
        "power_cef_snapshot": old_fields["power_cef_snapshot"],
        "tg_breaker_a": 50,  # manually edited after the original synchronization
    }

    fields = sync.power_cef_diu_sync(rec, _power(supply="Monofazat", breaker=63, inverter_breaker=32))

    assert fields["supply"] == "Monofazat"  # still matches prior synchronized value
    assert fields["circuits"][0]["breaker_a"] == 32
    assert "tg_breaker_a" not in fields  # manual value is not overwritten
    assert fields["power_cef_snapshot"]["grid"]["tg_breaker_a"] == 63


