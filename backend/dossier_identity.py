import re


def normalize_identity_code(value):
    """Normalize CNP/CUI formatting for consistency checks without weakening identity matching."""
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def identity_codes_conflict(document_code, client_code):
    """Only report a conflict when both codes are present and differ after formatting is removed."""
    document = normalize_identity_code(document_code)
    client = normalize_identity_code(client_code)
    return bool(document and client and document != client)

