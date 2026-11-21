import docgen
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
    ]

    ordered = sorted(positions, key=dossier_order)

    assert [position["key"] for position in ordered] == [
        "priza", "notificare", "date_stocare", "schema", "cat_datasheet_battery"
    ]
