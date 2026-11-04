from ai_context import redact_dossier_context


def test_ai_context_redacts_personal_identifiers_recursively_and_keeps_technical_data():
    source = {
        "client_name": "Client Test",
        "date_dosar": {"address": "Strada Test 1", "pod": "RO123", "power": 10},
        "client": {"name": "Client Test", "phone": "0700000000", "email": "client@example.test"},
        "configurare_cef": {"invertoare": [{"model": "Model X", "kw": 8}], "erori": []},
        "opis": [{"document": "Carte funciară", "status": "Lipsește"}],
    }

    result = redact_dossier_context(source)

    assert result == {
        "date_dosar": {"power": 10},
        "client": {},
        "configurare_cef": {"invertoare": [{"model": "Model X", "kw": 8}], "erori": []},
        "opis": [{"document": "Carte funciară", "status": "Lipsește"}],
    }
    assert source["client"]["phone"] == "0700000000"  # filtering does not mutate stored input
