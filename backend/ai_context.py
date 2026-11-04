"""Privacy filtering for dossier context sent to external AI providers."""

PRIVATE_DOSSIER_KEYS = frozenset({
    "name", "client_name", "beneficiary_name", "client_id", "dossier_id", "user_id", "uid",
    "cnp", "cui", "idcode", "id_number", "id_series", "series", "phone", "email",
    "address", "hq_address", "postal_code", "pod", "cf_nr", "cadastral_nr",
    "iban", "token", "owner", "password", "secret",
})


def redact_dossier_context(value):
    """Recursively remove direct identifiers while retaining technical review data."""
    if isinstance(value, dict):
        return {
            key: redact_dossier_context(item)
            for key, item in value.items()
            if str(key).casefold() not in PRIVATE_DOSSIER_KEYS
        }
    if isinstance(value, list):
        return [redact_dossier_context(item) for item in value]
    return value
