from dossier_identity import identity_codes_conflict, normalize_identity_code


def test_identity_formatting_matches_the_intake_form_normalization():
    assert normalize_identity_code("RO 123.456/78") == "RO12345678"
    assert not identity_codes_conflict("RO 123.456/78", "ro12345678")


def test_identity_conflict_requires_two_present_and_different_codes():
    assert identity_codes_conflict("1720811051105", "1720811051106")
    assert not identity_codes_conflict("", "1720811051105")
    assert not identity_codes_conflict("1720811051105", "")
