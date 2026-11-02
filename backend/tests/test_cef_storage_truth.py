import cef


def test_hybrid_inverter_type_does_not_claim_a_battery():
    record = {
        "system_type": "Hibrid cu baterie",
        "inverter": "Hybrid inverter model",
        "inverter_kw": 5,
        "battery": "Fără baterie",
    }
    assert cef.has_storage(record) is False
    migrated = cef.from_legacy(record)
    assert migrated["cef"]["inverters"][0]["battery_mode"] == "none"
    assert migrated["cef"]["inverters"][0]["battery"] is None


def test_legacy_battery_is_detected_without_relying_on_system_type():
    assert cef.has_storage({"system_type": "On-grid", "battery": "Huawei LUNA 10 kWh"}) is True
    assert cef.has_storage({"system_type": "Hibrid cu baterie", "battery": "Fără baterie"}) is False


def test_configured_own_and_shared_batteries_are_detected():
    own = {"cef": {"inverters": [{"battery_mode": "own", "battery": {"model": "Battery A"}}]}}
    shared = {"cef": {"inverters": [{"battery_mode": "shared", "shared_battery_id": "b1"}],
                      "shared_batteries": [{"id": "b1", "model": "Battery B"}]}}
    assert cef.has_storage(own) is True
    assert cef.has_storage(shared) is True


def test_shared_battery_record_is_detected_even_when_not_linked_to_an_inverter():
    record = {"cef": {"inverters": [{"battery_mode": "shared", "shared_battery_id": "missing"}],
                      "shared_batteries": [{"id": "b1", "model": "Battery B"}]}}
    assert cef.has_storage(record) is True
    record["cef"]["shared_batteries"] = []
    assert cef.has_storage(record) is False
