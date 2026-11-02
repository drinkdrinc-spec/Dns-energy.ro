import docgen


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
