import io

from pypdf import PdfReader

import docgen
import diu_doc


def _blocks(record):
    return docgen.doc_buletin_priza(docgen.Ctx(record, {}, {}))


def _text(blocks):
    return " ".join(str(part) for block in blocks for part in block)


def test_pram_without_measured_values_is_a_work_sheet():
    output = _text(_blocks({}))

    assert "FIȘĂ DE LUCRU" in output
    assert "NEFINALIZAT" in output
    assert "valorile lipsă nu sunt estimate" in output
    assert "valabil 1 an" not in output
    assert "NECOMPLETAT" in output


def test_pram_with_recorded_measurements_has_validity_period():
    output = _text(_blocks({
        "grounding_ohm": 4.0,
        "soil_psi": 1.2,
        "grounding_limit": 5.0,
        "measure_date": "2026-10-01",
    }))

    assert "BULETIN DE VERIFICARE" in output
    assert "valabil 1 an" in output
    assert "Valabil până la <b>01.10.2027</b>" in output


def test_pram_invalid_measurement_date_remains_a_work_sheet():
    output = _text(_blocks({
        "grounding_ohm": 4.0,
        "soil_psi": 1.2,
        "grounding_limit": 5.0,
        "measure_date": "not-a-date",
    }))

    assert "FIȘĂ DE LUCRU" in output
    assert "valabil 1 an" not in output

def test_synthetic_pram_pdf_has_test_watermark():
    pdf = docgen.render(
        ["buletin_priza"],
        {
            "is_test": True,
            "grounding_ohm": 3.2,
            "soil_psi": 1.2,
            "grounding_limit": 4,
            "measure_date": "2026-10-30",
        },
        {},
        {},
    )
    text = "\\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages)

    assert "TEST - DATE SINTETICE" in text



def test_diu_ddr_requires_measured_trip_current_before_completion():
    record = {
        "client_name": "Client test",
        "address": "Adresă test",
        "operator": "DEER",
        "pram_m": {"date": "2026-10-30"},
        "circuits": [{"name": "Circuit test", "rcd_ma": 30, "rcd_i": "", "rcd_t": 100}],
    }
    settings = {"company": "Firmă test", "anre_attest": "Atestat test", "rep": "Reprezentant test"}

    missing = diu_doc.missing("pram_ddr", record, settings)

    assert any("Curent declanșare DDR" in item for item in missing)
    assert not any("Timp declanșare DDR" in item for item in missing)

    record["circuits"][0]["rcd_i"] = 22
    missing = diu_doc.missing("pram_ddr", record, settings)
    assert not any("Curent declanșare DDR" in item for item in missing)
