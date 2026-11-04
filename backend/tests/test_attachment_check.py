import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from attachment_check import verify_dossier_attachments


class MissingLegacyFile(FileNotFoundError):
    pass


def test_unreadable_legacy_attachment_is_reported_and_not_counted_complete():
    info = {
        "positions": [{"key": "factura", "status": "atașat", "auto_status": "atașat",
                       "missing": [], "files": [{"storage_path": "old/factura.pdf", "original_filename": "Factura.pdf"}]}],
        "common_missing": [],
    }

    def unreadable(_path):
        raise MissingLegacyFile("old storage returned 403")

    result = verify_dossier_attachments(info, unreadable, MissingLegacyFile)

    position = result["positions"][0]
    assert result["complete"] is False
    assert result["missing_total"] == 1
    assert position["status"] == position["auto_status"] == "de completat"
    assert "Reîncarcă documentul" in position["missing"][0]


def test_duplicate_attachment_is_checked_once_and_valid_file_stays_complete():
    refs = [{"storage_path": "dns/factura.pdf", "original_filename": "Factura.pdf"}]
    info = {"positions": [{"key": "factura", "status": "atașat", "auto_status": "atașat",
                           "missing": [], "files": refs},
                          {"key": "client_copy", "status": "atașat", "auto_status": "atașat",
                           "missing": [], "files": refs}], "common_missing": []}
    calls = []

    def readable(path):
        calls.append(path)
        return b"pdf", "application/pdf"

    result = verify_dossier_attachments(info, readable, MissingLegacyFile)

    assert calls == ["dns/factura.pdf"]
    assert result["complete"] is True
    assert result["missing_total"] == 0
