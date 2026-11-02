"""Network-free extraction checks for explicit battery protection data."""
from equipment_extract import extract_equipment_specs


def test_battery_dc_breaker_values_are_extracted_from_explicit_labels():
    text = """
    Built-in DC circuit breaker rated current: 125 A
    DC circuit breaker rated voltage: 60 V
    Number of DC circuit breaker poles: 2 P
    Rated breaking capacity (Icu): 10 kA
    Integrated DC circuit breaker
    """
    result = extract_equipment_specs("Baterie", text)
    assert result["breaker_a"] == 125
    assert result["breaker_voltage_dc"] == 60
    assert result["breaker_poles"] == 2
    assert result["breaker_icu_ka"] == 10
    assert result["breaker_integrated"] is True


def test_battery_breaker_integration_is_not_guessed_from_conflicting_text():
    text = "Integrated DC circuit breaker. External circuit breaker also required."
    result = extract_equipment_specs("Baterie", text)
    assert "breaker_integrated" not in result


def test_battery_breaker_voltage_on_next_pdf_text_row_is_read():
    text = "DC circuit breaker rated voltage\n60 V"
    result = extract_equipment_specs("Baterie", text)
    assert result["breaker_voltage_dc"] == 60
