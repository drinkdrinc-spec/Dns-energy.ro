import atr_equipment


def test_atr_equipment_snapshot_keeps_selected_devices_and_calculates_panel_total():
    rec = {
        "operator": "DEER",
        "client_id": "client-test",
        "client_name": "Client test",
        "p_abs_kw": 6,
        "p_evac_kw": 5,
        "atr_cef": {
            "grid": {"supply": "Trifazat"},
            "inverters": [{
                "catalog_id": "inv-1",
                "brand_model": "Test inverter",
                "p_nom_kw": 5,
                "count": 2,
                "panel_catalog_id": "panel-1",
                "panel_model": "Test panel",
                "panel_w": 450,
                "strings": [{"panels": 12, "mppt": 1}],
                "battery_mode": "own",
                "battery": {"catalog_id": "battery-1", "model": "Test battery", "modules": 2},
            }],
            "shared_batteries": [],
        },
    }

    snapshot = atr_equipment.from_request(rec)

    assert snapshot["operator"] == "DEER"
    assert snapshot["panel_count"] == 24
    assert snapshot["panel_kwp"] == 10.8
    assert snapshot["inverter_kw"] == 10
    assert snapshot["cef"]["inverters"][0]["battery"]["model"] == "Test battery"
    assert snapshot["cef"]["shared_batteries"] == []


def test_atr_direct_catalog_equipment_requires_both_documents_per_model():
    cef = {
        "inverters": [{
            "catalog_id": "inv-1",
            "panel_catalog_id": "panel-1",
            "battery_mode": "own",
            "battery": {"catalog_id": "battery-1"},
        }],
        "shared_batteries": [],
        "grid": {},
    }
    files = [
        {"catalog_id": "inv-1", "kind": "Fișă tehnică"},
        {"catalog_id": "inv-1", "kind": "Declarație de conformitate"},
        {"catalog_id": "panel-1", "kind": "datasheet"},
        {"catalog_id": "panel-1", "kind": "conformity"},
        {"catalog_id": "battery-1", "kind": "Fișă tehnică"},
        {"catalog_id": "battery-1", "kind": "Declarație de conformitate"},
    ]

    assert atr_equipment.catalog_documents_complete(cef, files)
    assert not atr_equipment.catalog_documents_complete(cef, files[:-1])


def test_empty_atr_equipment_does_not_create_a_fake_prosumer_snapshot():
    assert atr_equipment.from_request({"atr_cef": {"inverters": [], "shared_batteries": []}}) == {}
    assert not atr_equipment.catalog_documents_complete({"inverters": []}, [])