import asyncio
import io

from pypdf import PdfReader
from reportlab.pdfgen import canvas

import docgen
import opis
from opis import dossier_order, storage_missing_fields


def _storage_context(batteries):
    record = {"cef": {"inverters": [], "shared_batteries": batteries}}
    settings = {"company": "DNS HOSTESS SRL", "rep": "Inginer test"}
    client = {
        "name": "Beneficiar test",
        "address": "Str. Test nr. 1",
        "locality": "Oradea",
        "county": "Bihor",
        "pod": "POD-TEST",
    }
    return docgen.Ctx(record, settings, client)


def _storage_row(ctx):
    blocks = docgen.doc_storage(ctx)
    table = next(block for block in blocks if block[0] == "table")
    return table[1][1]


def test_storage_document_calculates_total_capacity_from_modules():
    ctx = _storage_context([{
        "model": "Dyness Test",
        "kwh": 4.8,
        "modules": 3,
        "voltage": 51.2,
        "ah": 100,
        "tech": "LV",
        "coupling": "DC",
    }])

    row = _storage_row(ctx)

    assert row[2] == "14,4"
    assert row[3] == "4,8"
    assert row[6] == "LV"
    assert row[7] == "DC"
    assert row[8] == "3"


def test_storage_document_does_not_invent_total_when_module_count_is_missing():
    ctx = _storage_context([{"model": "Battery Test", "kwh": 5.12}])

    row = _storage_row(ctx)

    assert row[2] == docgen.M
    assert row[3] == "5,12"
    assert storage_missing_fields({"model": "Battery Test", "kwh": 5.12}) == [
        "Battery Test: completează/verifică numărul modulelor, tensiunea nominală, capacitatea în Ah, clasa bateriei LV/HV, tipul de cuplare"
    ]


def test_dossier_positions_follow_submission_order():
    positions = [
        {"key": "schema", "title": "Schemă"},
        {"key": "date_stocare", "title": "Date stocare"},
        {"key": "notificare", "title": "Notificare"},
        {"key": "priza", "title": "PRAM"},
        {"key": "cat_datasheet_battery", "title": "Fișă baterie"},
        {"key": "cf", "title": "Extras de carte funciară"},
        {"key": "factura", "title": "Factură furnizor de energie"},
        {"key": "certificat", "title": "Act de identitate"},
        {"key": "fotografii_instalatie", "title": "Fotografii instalație"},
        {"key": "fotografii_lucrare", "title": "Fotografii lucrare"},
    ]

    ordered = sorted(positions, key=dossier_order)

    assert [position["key"] for position in ordered] == [
        "certificat", "factura", "cf", "notificare", "date_stocare",
        "priza", "schema", "fotografii_instalatie", "cat_datasheet_battery", "fotografii_lucrare",
    ]

def test_client_slot_export_keeps_originals_and_dossier_upload(monkeypatch):
    monkeypatch.setattr(opis, "file_pdf", lambda data, _content_type: data)
    position = {
        "key": "fotografii_instalatie",
        "source": "client",
        "files": [{"storage_path": "client-photo-1", "content_type": "image/jpeg"}],
        "upload": {"storage_path": "dossier-photo-2", "content_type": "image/jpeg"},
    }

    result = asyncio.run(opis.position_pdf(
        position, {}, {}, {}, {}, lambda path: (path.encode(), "image/jpeg")
    ))

    assert result == [b"client-photo-1", b"dossier-photo-2"]


def _marker_pdf(text):
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream)
    pdf.drawString(40, 760, text)
    pdf.save()
    return stream.getvalue()


def test_export_bundle_places_authenticity_before_schema_and_equipment(monkeypatch):
    async def fake_position_pdf(position, *_args, **_kwargs):
        return [_marker_pdf(position["marker"])]

    monkeypatch.setattr(opis, "position_pdf", fake_position_pdf)
    monkeypatch.setattr(opis.docgen, "render", lambda *_args, **_kwargs: _marker_pdf("AUTHENTICITY"))
    monkeypatch.setattr(opis, "_incomplete_report", lambda *_args: _marker_pdf("INTERNAL REVIEW"))

    class Logger:
        def error(self, *_args, **_kwargs):
            raise AssertionError("Unexpected PDF bundle error")

    positions_info = {
        "titles": {},
        "complete": True,
        "positions": [
            {"key": "notificare", "source": "manual", "marker": "OFFICIAL FORM"},
            {"key": "fotografii_instalatie", "source": "client", "files": [_marker_pdf("INSTALLATION PHOTOS")], "marker": "INSTALLATION PHOTOS"},
            {"key": "schema", "source": "generat", "marker": "SINGLE-LINE DIAGRAM"},
            {"key": "cat_datasheet_panel", "source": "catalog", "marker": "PANEL DATASHEET"},
            {"key": "fotografii_lucrare", "source": "client", "files": [_marker_pdf("WORK PHOTOS")], "marker": "WORK PHOTOS"},
        ],
    }
    output = asyncio.run(opis.export_bundle(positions_info, {}, {}, {}, None, Logger()))
    pages = PdfReader(io.BytesIO(output)).pages
    page_text = [page.extract_text() for page in pages]

    assert len(page_text) == 7
    expected = ["OFFICIAL FORM", "INSTALLATION PHOTOS", "AUTHENTICITY", "SINGLE-LINE DIAGRAM", "PANEL DATASHEET", "WORK PHOTOS", "INTERNAL REVIEW"]
    actual = [
        next(marker for marker in expected if marker in text)
        for text in page_text
    ]
    assert actual == expected

