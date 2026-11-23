from datetime import datetime, timezone

import diu_support


def test_diu_supporting_status_requires_real_company_documents():
    status = diu_support.supporting_status({}, {})

    assert status["available"] == []
    assert any("Atestatul ANRE" in item for item in status["missing"])
    assert any("Ștampila firmei" in item for item in status["missing"])


def test_diu_supporting_status_accepts_valid_selected_metrology():
    today = datetime.now(timezone.utc).date().isoformat()
    meter = {"id": "meter-1", "maker_model": "TA862A", "serial": "1234",
             "expires": today, "file": {"storage_path": "owner/meter.pdf"}}
    
    settings = {"anre_file": {"storage_path": "owner/anre.pdf"}, "anre_valid": today,
                "_stamp_path": "owner/stamp.png"}
    record = {"instrument_id": "meter-1", "pram_m": {"earth_ohm": "2.1"}}

    status = diu_support.supporting_status(record, settings, meter)

    assert status["missing"] == []
    assert "Atestat ANRE firmă" in status["available"]
    assert any("TA862A" in item for item in status["available"])


def test_diu_supporting_status_flags_expired_or_missing_meter_certificate():
    meter = {"id": "meter-1", "maker_model": "TA862A", "expires": "2000-01-01",
             "file": {"storage_path": "owner/expired-meter.pdf"}}
    
    settings = {"anre_file": {"storage_path": "owner/anre.pdf"}, "_stamp_path": "owner/stamp.png"}
    record = {"instrument_id": "meter-1", "pram_m": {"earth_ohm": "2.1"}}

    status = diu_support.supporting_status(record, settings, meter)

    assert any("certificatul metrologic" in item.lower() and "expirat" in item.lower() for item in status["missing"])

