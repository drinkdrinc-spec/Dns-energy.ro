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


def test_signed_source_pdf_is_preserved_byte_for_byte_for_zip_archive():
    original = b"%PDF signed source bytes"
    result = diu_support.collect_signed_sources(
        ["garantie"],
        {"garantie": {"storage_path": "signed/original.pdf"}},
        {"garantie": "Certificat de garanție"},
        lambda path: (original, "application/pdf"),
        max_total=1024,
    )

    assert result["issues"] == []
    assert result["files"] == [{
        "key": "garantie",
        "title": "Certificat de garanție",
        "filename": "Documente semnate/garantie.pdf",
        "data": original,
    }]


def test_signed_source_read_failure_and_size_limit_are_reported():
    signed = {"a": {"storage_path": "a.pdf"}, "b": {"storage_path": "b.pdf"}}

    def get_object(path):
        if path == "a.pdf":
            raise OSError("storage unavailable")
        return b"oversized", "application/pdf"

    result = diu_support.collect_signed_sources(
        ["a", "b"], signed, {"a": "Semnat A", "b": "Semnat B"}, get_object,
        max_total=2, limit_label="2 bytes",
    )

    assert result["files"] == []
    assert len(result["issues"]) == 2
    assert any("nu a putut fi citit" in item for item in result["issues"])
    assert any("limita de 2 bytes" in item for item in result["issues"])
