import asyncio
import io
import sys
import zipfile
from types import SimpleNamespace

from pypdf import PdfReader
from reportlab.pdfgen import canvas

import docgen
import opis
from opis import _package_group, dossier_order, storage_missing_fields


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


def test_generated_documents_use_reviewed_dossier_identity_with_client_fallback():
    ctx = docgen.Ctx(
        {"kind": "Persoană juridică", "name": "DNS Dossier", "cnp": "RO123"},
        {},
        {"kind": "Persoană fizică", "name": "DNS Client", "idcode": "123"},
    )

    assert ctx.pj is True
    assert ctx.name == "DNS Dossier"
    assert ctx.raw("idcode") == "RO123"
    assert ctx.raw("phone") is None


def test_generated_documents_fall_back_to_master_client_when_dossier_field_is_empty():
    ctx = docgen.Ctx({"name": ""}, {}, {"name": "Client existent", "phone": "0740000000"})

    assert ctx.name == "Client existent"
    assert ctx.raw("phone") == "0740000000"


def test_dossier_snapshot_overrides_stale_client_identity_and_keeps_other_client_fields():
    snapshot = opis.dossier_client_snapshot(
        {"kind": "Persoană juridică", "client_name": "DNS Firmă", "cnp": "RO123", "county": "Bihor"},
        {"kind": "Persoană fizică", "name": "Nume vechi", "idcode": "123", "county": "Cluj", "email": "office@example.test"},
    )

    assert snapshot["kind"] == "Persoană juridică"
    assert snapshot["name"] == "DNS Firmă"
    assert snapshot["idcode"] == "RO123"
    assert snapshot["county"] == "Bihor"
    assert snapshot["email"] == "office@example.test"


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
        "priza", "notificare", "date_stocare", "certificat", "factura", "cf",
        "fotografii_instalatie", "schema", "cat_datasheet_battery", "fotografii_lucrare",
    ]


def test_full_packet_order_matches_the_signed_reenergy_reference():
    positions = [{"key": key} for key in (
        "priza", "notificare", "date_stocare", "gdpr", "imputernicire", "afm",
        "executant", "conformitate", "receptie", "serii", "pif", "reglaj",
        "declaratie_autenticitate", "schema", "cat_datasheet_inverter", "fotografii_lucrare",
    )]

    ordered = sorted(positions, key=dossier_order)

    assert [position["key"] for position in ordered] == [
        "priza", "notificare", "date_stocare", "gdpr", "imputernicire", "afm",
        "executant", "conformitate", "receptie", "serii", "pif", "reglaj",
        "declaratie_autenticitate", "schema", "cat_datasheet_inverter", "fotografii_lucrare",
    ]


def test_installation_photos_stay_in_submission_pdf_and_work_photos_close_technical_annexes():
    assert _package_group("fotografii_instalatie", "client") == 0
    assert _package_group("fotografii_lucrare", "client") == 3
    assert _package_group("schema", "generat") == 2
    assert _package_group("priza", "generat") == 1


def test_submission_zip_keeps_installation_photos_with_forms_and_work_photos_last(monkeypatch):
    async def fake_position_pdf(position, *_args, **_kwargs):
        return [_marker_pdf(position["marker"])]

    monkeypatch.setattr(opis, "position_pdf", fake_position_pdf)
    monkeypatch.setattr(opis.docgen, "render", lambda *_args, **_kwargs: _marker_pdf("AUTHENTICITY"))
    monkeypatch.setattr(opis, "_incomplete_report", lambda *_args: None)

    class Logger:
        def error(self, *_args, **_kwargs):
            raise AssertionError("Unexpected ZIP export error")

    info = {
        "titles": {},
        "complete": True,
        "positions": [
            {"key": "priza", "source": "generat", "marker": "PRAM"},
            {"key": "notificare", "source": "manual", "marker": "OFFICIAL FORM"},
            {"key": "fotografii_instalatie", "source": "client", "marker": "INSTALLATION PHOTOS"},
            {"key": "schema", "source": "generat", "marker": "SINGLE-LINE DIAGRAM"},
            {"key": "cat_datasheet_panel", "source": "catalog", "marker": "PANEL DATASHEET"},
            {"key": "fotografii_lucrare", "source": "client", "marker": "WORK PHOTOS"},
        ],
    }
    output = asyncio.run(opis.export_package_zip(dict(info), {}, {}, {}, None, Logger(), 4))
    single_output = asyncio.run(opis.export_package_zip(dict(info), {}, {}, {}, None, Logger(), 1))

    with zipfile.ZipFile(io.BytesIO(output)) as archive:
        assert archive.namelist() == [
            "01_Acte_si_formulare.pdf", "02_Probe_PRAM_PIF.pdf",
            "03_Schema_si_fise_tehnice.pdf", "04_Fotografii.pdf", "00_CITESTE.txt",
        ]
        pdf_text = {
            name: " ".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(archive.read(name))).pages)
            for name in archive.namelist() if name.endswith(".pdf")
        }

    assert "INSTALLATION PHOTOS" in pdf_text["01_Acte_si_formulare.pdf"]
    assert "WORK PHOTOS" in pdf_text["04_Fotografii.pdf"]
    assert "AUTHENTICITY" in pdf_text["02_Probe_PRAM_PIF.pdf"]

    with zipfile.ZipFile(io.BytesIO(single_output)) as archive:
        pages = PdfReader(io.BytesIO(archive.read("01_Dosar_complet.pdf"))).pages
        page_text = [page.extract_text() or "" for page in pages]
    expected = ["PRAM", "OFFICIAL FORM", "INSTALLATION PHOTOS", "AUTHENTICITY",
                "SINGLE-LINE DIAGRAM", "PANEL DATASHEET", "WORK PHOTOS"]
    actual = [next(marker for marker in expected if marker in text) for text in page_text]
    assert actual == expected


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


def test_official_operator_form_failure_returns_explicit_fallback_instead_of_blank(monkeypatch):
    async def unavailable(*_args, **_kwargs):
        raise ValueError("HTTP 403")

    atr_module = SimpleNamespace(
        _fetch_registry_annex=unavailable,
        ATR=SimpleNamespace(render_operator_annex_prep=lambda *_args, **_kwargs: _marker_pdf("WORKSHEET ONLY")),
    )
    monkeypatch.setitem(sys.modules, "atr_routes", atr_module)
    position = {
        "key": "notificare",
        "official_operator_form": {
            "operator_key": "delgaz",
            "annex_no": 2,
            "title": "Formular oficial Delgaz",
            "url": "https://delgaz.ro/forms/anexa-2.pdf",
        },
    }

    parts = asyncio.run(opis.position_pdf(position, {}, {}, {}, {}, lambda _path: None))

    pages = [
        page
        for part in parts
        for page in PdfReader(io.BytesIO(part)).pages
    ]
    text = " ".join(page.extract_text() or "" for page in pages)
    assert "WORKSHEET ONLY" in text
    assert "FORMULARUL OFICIAL NU A PUTUT FI DESCĂRCAT" in text
    links = [
        annotation.get_object().get("/A", {}).get("/URI")
        for page in pages
        for annotation in page.get("/Annots", [])
    ]
    assert "https://delgaz.ro/forms/anexa-2.pdf" in links
    assert position["_official_form_unavailable"] is True


def test_bundle_keeps_official_form_fallback_and_marks_export_incomplete(monkeypatch):
    fallback = _marker_pdf("OFFICIAL FORM UNAVAILABLE — USE OFFICIAL LINK")

    async def unavailable_form(position, *_args, **_kwargs):
        position["_official_form_unavailable"] = True
        return [fallback]

    monkeypatch.setattr(opis, "position_pdf", unavailable_form)
    monkeypatch.setattr(opis.docgen, "render", lambda *_args, **_kwargs: _marker_pdf("AUTHENTICITY"))

    class Logger:
        def warning(self, *_args, **_kwargs):
            pass

        def error(self, *_args, **_kwargs):
            raise AssertionError("Unexpected PDF bundle error")

    info = {
        "titles": {},
        "complete": True,
        "positions": [{"key": "notificare", "title": "Formular oficial Delgaz"}],
    }
    output = asyncio.run(opis.export_bundle(info, {}, {}, {}, None, Logger()))
    text = " ".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(output)).pages)

    assert "OFFICIAL FORM UNAVAILABLE" in text
    assert "AUTHENTICITY" in text
    assert "CIORNĂ" in text
    assert info["export_has_unavailable_items"] is True


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


def test_export_bundle_repeats_pram_after_commissioning_as_in_the_signed_reference(monkeypatch):
    async def fake_position_pdf(position, *_args, **_kwargs):
        return [_marker_pdf(position["marker"])]

    monkeypatch.setattr(opis, "position_pdf", fake_position_pdf)
    monkeypatch.setattr(opis.docgen, "render", lambda *_args, **_kwargs: _marker_pdf("AUTHENTICITY"))
    monkeypatch.setattr(opis, "_incomplete_report", lambda *_args: None)

    class Logger:
        def error(self, *_args, **_kwargs):
            raise AssertionError("Unexpected PDF bundle error")

    info = {
        "titles": {}, "complete": True,
        "positions": [
            {"key": "priza", "source": "generat", "marker": "PRAM"},
            {"key": "notificare", "source": "manual", "marker": "OFFICIAL FORM"},
            {"key": "serii", "source": "generat", "marker": "EQUIPMENT SERIES"},
            {"key": "pif", "source": "generat", "marker": "PIF"},
            {"key": "reglaj", "source": "generat", "marker": "SETTINGS"},
            {"key": "schema", "source": "generat", "marker": "SCHEMA"},
        ],
    }

    output = asyncio.run(opis.export_bundle(info, {}, {}, {}, None, Logger()))
    texts = [page.extract_text() or "" for page in PdfReader(io.BytesIO(output)).pages]
    markers = [next((marker for marker in ("PRAM", "OFFICIAL FORM", "EQUIPMENT SERIES", "PIF", "SETTINGS", "AUTHENTICITY", "SCHEMA") if marker in text), "") for text in texts]

    assert markers == ["PRAM", "OFFICIAL FORM", "EQUIPMENT SERIES", "PIF", "PRAM", "SETTINGS", "AUTHENTICITY", "SCHEMA"]


def test_submission_zip_preserves_reference_order_and_repeats_pram_after_pif(monkeypatch):
    async def fake_position_pdf(position, *_args, **_kwargs):
        return [_marker_pdf(position["marker"])]

    monkeypatch.setattr(opis, "position_pdf", fake_position_pdf)
    monkeypatch.setattr(opis.docgen, "render", lambda *_args, **_kwargs: _marker_pdf("AUTHENTICITY"))
    monkeypatch.setattr(opis, "_incomplete_report", lambda *_args: None)

    class Logger:
        def error(self, *_args, **_kwargs):
            raise AssertionError("Unexpected ZIP export error")

    info = {
        "titles": {}, "complete": True,
        "positions": [
            {"key": "priza", "source": "generat", "marker": "PRAM"},
            {"key": "notificare", "source": "manual", "marker": "OFFICIAL FORM"},
            {"key": "date_stocare", "source": "generat", "marker": "STORAGE"},
            {"key": "serii", "source": "generat", "marker": "EQUIPMENT SERIES"},
            {"key": "pif", "source": "generat", "marker": "PIF"},
            {"key": "reglaj", "source": "generat", "marker": "SETTINGS"},
            {"key": "schema", "source": "generat", "marker": "SCHEMA"},
        ],
    }

    output = asyncio.run(opis.export_package_zip(info, {}, {}, {}, None, Logger(), 1))
    with zipfile.ZipFile(io.BytesIO(output)) as archive:
        pages = PdfReader(io.BytesIO(archive.read("01_Dosar_complet.pdf"))).pages
    texts = [page.extract_text() or "" for page in pages]
    expected = ["PRAM", "OFFICIAL FORM", "STORAGE", "EQUIPMENT SERIES", "PIF", "PRAM", "SETTINGS", "AUTHENTICITY", "SCHEMA"]
    actual = [next(marker for marker in expected if marker in text) for text in texts]

    assert actual == expected


def test_submission_zip_preserves_uploaded_originals_separately_from_compiled_pdfs(monkeypatch):
    original = b"%PDF-1.4 signed original source bytes"

    async def fake_position_pdf(_position, *_args, **_kwargs):
        return [_marker_pdf("SIGNED SOURCE COPY")]

    monkeypatch.setattr(opis, "position_pdf", fake_position_pdf)
    monkeypatch.setattr(opis.docgen, "render", lambda *_args, **_kwargs: _marker_pdf("AUTHENTICITY"))
    monkeypatch.setattr(opis, "_incomplete_report", lambda *_args: None)

    class Logger:
        def error(self, *_args, **_kwargs):
            raise AssertionError("Unexpected ZIP export error")

    source_file = {"storage_path": "client/signed-annex.pdf", "original_filename": "Anexa semnata.pdf",
                   "content_type": "application/pdf"}
    info = {"titles": {}, "complete": True, "positions": [{
        "key": "notificare", "title": "Cerere oficială semnată", "source": "manual",
        "files": [source_file], "upload": source_file,
    }]}
    package = asyncio.run(opis.export_package_zip(
        info, {}, {}, {}, lambda path: (original, "application/pdf"), Logger(), 1
    ))

    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        names = archive.namelist()
        source_names = [name for name in names if name.startswith("Documente originale/")]
        assert len(source_names) == 1
        assert archive.read(source_names[0]) == original
        assert "01_Dosar_complet.pdf" in names
        manifest = archive.read("00_CITESTE.txt").decode()

    assert "verificarea semnăturilor" in manifest
    assert "Anexa semnata.pdf" in source_names[0]

