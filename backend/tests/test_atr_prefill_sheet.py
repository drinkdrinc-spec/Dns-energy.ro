from io import BytesIO

from pypdf import PdfReader

import atr_doc as ATR


def test_prefill_sheet_accepts_a_named_procedure_without_claiming_to_be_official():
    content = ATR.render_operator_annex_prep(
        {"deer_case": "Procedură DEER >400 kW"},
        {},
        {},
        "deer",
        "Procedură dedicată",
        "Cerere pentru instalații de producere cu putere > 400 kW",
    )

    assert content.startswith(b"%PDF")
    reader = PdfReader(BytesIO(content))
    rendered = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "PROCEDURĂ DEDICATĂ" in rendered.upper()
    assert "DOCUMENT DE LUCRU" in rendered
    assert "NU ESTE FORMULARUL OFICIAL" in rendered
    assert "Putere instalată fotovoltaică" in rendered


def test_prefill_sheet_includes_selected_smart_meter_without_inventing_presence():
    content = ATR.render_operator_annex_prep(
        {"smart_meter_present": True},
        {},
        {"cef": {"grid": {"meter": "Meter X"}}},
        "rer",
        1,
    )

    rendered = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages)
    assert "Smart meter prezent" in rendered
    assert "DA" in rendered
    assert "Meter X" in rendered


def test_prefill_sheet_marks_smart_meter_presence_unspecified_when_unconfirmed():
    content = ATR.render_operator_annex_prep({}, {}, {}, "rer", 1)

    rendered = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages)
    assert "nespecificat" in rendered
    assert "Smart meter prezent" in rendered

