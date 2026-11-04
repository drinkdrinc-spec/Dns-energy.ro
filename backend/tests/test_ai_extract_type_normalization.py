from ai_extract import canonical_document_type


def test_explicit_document_type_codes_are_stable():
    assert canonical_document_type("ci") == "ci"
    assert canonical_document_type("factura") == "factura"
    assert canonical_document_type("cf") == "cf"


def test_romanian_extraction_labels_map_to_required_field_groups():
    assert canonical_document_type("Carte de identitate") == "ci"
    assert canonical_document_type("Factură energie") == "factura"
    assert canonical_document_type("Extras de carte funciară") == "cf"


def test_ambiguous_or_unknown_labels_are_not_misclassified():
    assert canonical_document_type("Certificat tehnic") == ""
    assert canonical_document_type(None) == ""
