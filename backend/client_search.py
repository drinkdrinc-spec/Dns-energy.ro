import re


NUMERIC_CLIENT_SEARCH_FIELDS = ("idcode", "cnp", "id_number", "phone", "pod")
TEXT_CLIENT_SEARCH_FIELDS = ("name", "email", "phone", "pod", "address", "locality", "county")


def build_client_search_query(scope: dict, term: str) -> dict | None:
    """Build a tenant-scoped client search, using indexable numeric prefixes."""
    term = str(term or "").strip()
    if len(term) < 2:
        return None

    if term.isdigit():
        # Numeric identifiers are case-free; anchored regexes can use owner+field indexes.
        pattern = re.compile("^" + re.escape(term))
        fields = NUMERIC_CLIENT_SEARCH_FIELDS
    else:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        fields = TEXT_CLIENT_SEARCH_FIELDS

    field_query = {"$or": [{field: pattern} for field in fields]}
    return {
        "$and": [
            scope,
            field_query,
            {"is_test": {"$ne": True}},
            {"name": {"$not": re.compile(r"\bTEST\b", re.I)}},
        ]
    }
