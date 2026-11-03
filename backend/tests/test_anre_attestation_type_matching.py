import pytest

from anre_rules import has_attestation_type


@pytest.mark.parametrize("value", ["Bi", "Bp", "Bi, Bp", "Bi / Bp", ["Bi", "Bp"]])
def test_extension_from_b_does_not_accept_bi_or_bp_substrings(value):
    assert not has_attestation_type(value, "B")


@pytest.mark.parametrize("value", ["B", "B, C1A", "b / c2a", ["Bi", "B"], ["B"]])
def test_exact_b_attestation_is_accepted(value):
    assert has_attestation_type(value, "B")
