import re

from client_search import (
    NUMERIC_CLIENT_SEARCH_FIELDS,
    TEXT_CLIENT_SEARCH_FIELDS,
    build_client_search_query,
)


def _parts(query):
    assert query is not None
    return query["$and"]


def test_numeric_search_is_prefix_scoped_and_excludes_demo_records():
    scope = {"owner": "tenant-123"}
    query = build_client_search_query(scope, "0712")
    parts = _parts(query)

    assert parts[0] == scope
    field_query = next(part for part in parts if "$or" in part)
    assert {next(iter(item)) for item in field_query["$or"]} == set(NUMERIC_CLIENT_SEARCH_FIELDS)
    assert all(item[next(iter(item))].pattern == "^0712" for item in field_query["$or"])
    assert all(item[next(iter(item))].flags == 0 for item in field_query["$or"])
    assert {"is_test": {"$ne": True}} in parts
    name_guard = next(part for part in parts if "name" in part)
    assert name_guard["name"]["$not"].search("Client TEST demo")


def test_text_search_is_case_insensitive_and_escapes_regex_metacharacters():
    query = build_client_search_query({"owner": "tenant-123"}, "Popescu.")
    parts = _parts(query)
    field_query = next(part for part in parts if "$or" in part)

    assert {next(iter(item)) for item in field_query["$or"]} == set(TEXT_CLIENT_SEARCH_FIELDS)
    pattern = field_query["$or"][0][TEXT_CLIENT_SEARCH_FIELDS[0]]
    assert pattern.flags & re.IGNORECASE
    assert pattern.search("Popescu.") is not None
    assert pattern.search("PopescuX") is None


def test_short_term_returns_no_query():
    assert build_client_search_query({"owner": "tenant-123"}, "") is None
    assert build_client_search_query({"owner": "tenant-123"}, "a") is None


def test_numeric_prefix_regex_escapes_special_characters_in_nonstandard_digit_input():
    query = build_client_search_query({"owner": "tenant-123"}, "12+")
    field_query = next(part for part in _parts(query) if "$or" in part)
    assert field_query["$or"][0]["name"].search("12+") is None
