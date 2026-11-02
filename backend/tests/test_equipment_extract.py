"""Network-free extraction checks for explicit battery protection data."""
from equipment_extract import extract_equipment_specs


def test_battery_dc_breaker_values_are_extracted_from_explicit_labels():
    text = """
    Built-in DC circuit breaker rated current: 125 A
    DC circuit breaker rated voltage: 60 V
    Number of DC circuit breaker poles: 2P
    DC circuit breaker rated breaking capacity (Icu): 10 kA
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

def test_smart_meter_datasheet_extracts_only_explicit_model_specs():
    text = """
    Three phase 100A direct fed
    Nominal voltage(Un) 3x230/400 V ac
    Maximum rated current (Imax) 100A
    Operational frequency range 50 or 60Hz
    Accuracy class Class1/Class B
    SDM630-Modbus 3PH-4W, 3PH-3W, 1PH-2W, 3x230(400)V, 0.5~10(100)A, 50/60Hz, backlighted LCD display, 2 pulse outputs, RS485 Modbus RTU.
    """
    result = extract_equipment_specs("Smart meter", text)
    assert result["phases"] == "Trifazat"
    assert result["current_max_a"] == 100
    assert result["voltage_nominal_v"] == "3x230/400 V ac"
    assert result["frequency_hz"] == "50 or 60Hz"
    assert result["accuracy_class"] == "Class1/Class B"
    assert result["protocol"] == "RS485 Modbus RTU"
    assert result["wiring"] == "3PH-4W, 3PH-3W, 1PH-2W"
