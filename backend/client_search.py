import re


NUMERIC_CLIENT_SEARCH_FIELDS = ("idcode", "cnp", "id_number", "phone", "pod")
TEXT_CLIENT_SEARCH_FIELDS = ("name", "email", "phone", "pod", "address", "locality", "county")


def _base_filters(scope: dict) -> list[dict]:
    return [
        scope,
        {"is_test": {"$ne": True}},
        {"name": {"$not": re.compile(r"\bTEST\b", re.I)}},
    ]


def build_client_search_queries(scope: dict, term: str) -> list[dict] | None:
    """Build scoped queries that use a single-field prefix index for numeric searches."""
    term = str(term or "").strip()
    if len(term) < 2:
        return None

    base = _base_filters(scope)
    if term.isdigit():
        pattern = re.compile("^" + re.escape(term))
        # A multi-field $or combined with a global updated_at sort made MongoDB
        # prefer owner+updated_at and scan every client for the tenant. Separate
        # indexed prefix lookups bound the scanned range before we merge results.
        return [
            {"$and": [*base, {field: pattern}]}
            for field in NUMERIC_CLIENT_SEARCH_FIELDS
        ]

    pattern = re.compile(re.escape(term), re.IGNORECASE)
    field_query = {"$or": [{field: pattern} for field in TEXT_CLIENT_SEARCH_FIELDS]}
    return [{"$and": [*base, field_query]}]
