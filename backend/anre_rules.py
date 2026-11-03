import re


def has_attestation_type(value, required):
    """Match complete ANRE attestation codes, never substrings such as Bi/Bp for B."""
    values = value if isinstance(value, (list, tuple, set)) else [value]
    tokens = {
        token.strip().upper()
        for item in values
        for token in re.split(r"[,;|/\s]+", str(item or ""))
        if token.strip()
    }
    return str(required or "").strip().upper() in tokens
