"""Conservative, local extraction of explicitly labelled equipment specifications.

This parser is a fallback for selectable-text PDFs when the hosted AI provider is
not configured. It does not infer missing values and deliberately drops values
when a label maps to conflicting numbers in the same document.
"""

from __future__ import annotations

import re

_NUMBER = re.compile(r"(?<![\w.])[-+]?(?:\d+(?:[.,]\d+)?)(?!\w)")
_UNIT = re.compile(r"%\s*/\s*°?\s*C|°\s*C|MWh|kWh|Wh|MW|kW|W|kA|mAh|Ah|mA|A|mV|V|poles?|P", re.I)


def _unit_for(tail: str, number_start: int, number_end: int) -> str:
    after = _UNIT.match(tail[number_end:].lstrip())
    if after:
        return after.group(0).replace(" ", "").casefold()
    before = list(_UNIT.finditer(tail[:number_start]))
    return before[-1].group(0).replace(" ", "").casefold() if before else ""


def _labeled_numbers(text: str, labels: tuple[str, ...], units: tuple[str, ...], factor=None):
    lines = (text or "").splitlines()
    found = []
    for label in labels:
        rx = re.compile(label, re.I)
        for index, line in enumerate(lines):
            match = rx.search(line)
            if not match:
                continue
            tail = line[match.end():match.end() + 90]
            number = _NUMBER.search(tail)
            if not number:
                # Manufacturer PDFs often attach units directly to values (for example, 100A).
                # Accept that form only when the suffix is a recognized physical unit.
                candidate = re.search(r"(?<![\w.])[-+]?\d+(?:[.,]\d+)?", tail)
                if candidate and _UNIT.match(tail[candidate.end():].lstrip()):
                    number = candidate
            if not number:
                # Some manufacturer PDFs place the value in the cell immediately
                # below its label. Accept only a line containing a value and unit.
                if index + 1 >= len(lines):
                    continue
                tail = lines[index + 1].strip()
                if not re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?\s*[^\w\s]?\s*(?:%\s*/\s*°?\s*C|°\s*C|MWh|kWh|Wh|MW|kW|W|kA|mAh|Ah|mA|A|mV|V|poles?|P)", tail, re.I):
                    continue
                number = _NUMBER.search(tail)
            if not number:
                continue
            unit = _unit_for(tail, number.start(), number.end())
            if unit not in units:
                continue
            try:
                value = float(number.group(0).replace(",", "."))
            except ValueError:
                continue
            if factor:
                value *= factor(unit)
            if value > 0 or unit.startswith("%"):
                found.append(value)
    unique = {round(value, 6) for value in found}
    return next(iter(unique)) if len(unique) == 1 else None


def _numeric(text: str, label: tuple[str, ...], units: tuple[str, ...], factor=None):
    value = _labeled_numbers(text, label, units, factor)
    if value is None:
        return None
    return int(value) if value.is_integer() else round(value, 6)


def _battery_breaker_poles(text: str):
    """Read a labelled breaker pole count, including compact forms such as 2P."""
    labels = (r"\bnumber\s+of\s+(?:DC\s+)?(?:circuit\s+)?breaker\s+poles\b",
              r"\bbreaker\s+pole\s+count\b",
              r"\bpoles\s+(?:of\s+)?(?:the\s+)?(?:DC\s+)?(?:circuit\s+)?breaker\b")
    found = set()
    for label in labels:
        rx = re.compile(label, re.I)
        for line in (text or "").splitlines():
            match = rx.search(line)
            if not match:
                continue
            number = re.search(r"(?<![\w.])(\d+)\s*(?:P\b|poles?\b)?", line[match.end():match.end() + 90], re.I)
            if number:
                value = int(number.group(1))
                if 1 <= value <= 12:
                    found.add(value)
    return next(iter(found)) if len(found) == 1 else None


def _battery_breaker_integrated(text: str):
    """Return a breaker integration flag only when the datasheet states it unambiguously."""
    integrated = bool(re.search(
        r"\b(?:integrated|built[- ]in|internal)\s+(?:DC\s+)?(?:circuit\s+)?breaker\b|"
        r"\b(?:circuit\s+)?breaker\s+(?:is\s+)?integrated\b", text, re.I))
    external = bool(re.search(
        r"\bexternal\s+(?:DC\s+)?(?:circuit\s+)?breaker\b|"
        r"\bno\s+(?:integrated|internal)\s+(?:DC\s+)?(?:circuit\s+)?breaker\b", text, re.I))
    return True if integrated and not external else False if external and not integrated else None


def _enum(text: str, field: str):
    if field == "phases":
        single = re.search(r"\b(?:single[- ]phase|1[- ]phase|monophase)\b", text, re.I)
        three = re.search(r"\b(?:three[- ]phase|3[- ]phase|triphase)\b", text, re.I)
        return "Monofazat" if single and not three else "Trifazat" if three and not single else None
    if field == "type":
        hybrid = re.search(r"\bhybrid\b", text, re.I)
        battery = re.search(r"\b(?:battery|storage) inverter\b", text, re.I)
        on_grid = re.search(r"\b(?:on[- ]grid|grid[- ]tied)\b", text, re.I)
        matches = [name for name, match in (("Hibrid", hybrid), ("Invertor de baterie (AC)", battery), ("On-grid", on_grid)) if match]
        return matches[0] if len(matches) == 1 else None
    if field == "tech":
        matches = [name for name, pattern in (("LV", r"\b(?:low[- ]voltage|LV battery)\b"), ("HV", r"\b(?:high[- ]voltage|HV battery)\b")) if re.search(pattern, text, re.I)]
        return matches[0] if len(matches) == 1 else None
    if field == "coupling":
        matches = [name for name, pattern in (("AC", r"\bAC[- ]coupl(?:ed|ing)\b"), ("DC", r"\bDC[- ]coupl(?:ed|ing)\b")) if re.search(pattern, text, re.I)]
        return matches[0] if len(matches) == 1 else None
    return None


def extract_equipment_specs(category: str, text: str) -> dict:
    """Return unambiguous, explicitly labelled catalog values from selectable text."""
    if not isinstance(text, str) or not text.strip():
        return {}
    result = {}
    kw_units = ("kw", "w", "mw")
    volt_units = ("v", "mv")
    amp_units = ("a", "ma")
    convert_kw = lambda unit: 0.001 if unit == "w" else 1000 if unit == "mw" else 1
    convert_v = lambda unit: 0.001 if unit == "mv" else 1
    convert_a = lambda unit: 0.001 if unit == "ma" else 1
    convert_kwh = lambda unit: 0.001 if unit == "wh" else 1000 if unit == "mwh" else 1

    if category == "Invertor":
        specs = {
            "p_nom_kw": ((r"\b(?:rated|nominal)\s+(?:ac\s+)?(?:output\s+)?power\b", r"\bP\s*nom\b", r"\bPn\b"), kw_units, convert_kw),
            "p_max_kw": ((r"\bmaximum\s+(?:ac\s+)?(?:output\s+)?power\b", r"\bmax\.?\s+(?:ac\s+)?output\s+power\b"), kw_units, convert_kw),
            "vdc_max": ((r"\bmaximum\s+(?:pv\s+)?dc\s+input\s+voltage\b", r"\bmax\.?\s+dc\s+voltage\b", r"\bUdc\s*max\b"), volt_units, convert_v),
            "mppt_count": ((r"\b(?:number|no\.?)\s+of\s+MPPT(?:\s+trackers?)?\b", r"\bMPPT\s+trackers?\b"), ("",), None),
            "imax_mppt": ((r"\bmaximum\s+input\s+current(?:\s+per\s+MPPT)?\b", r"\bmax\.?\s+input\s+current\s*/\s*MPPT\b"), amp_units, convert_a),
            "isc_max_mppt": ((r"\bmaximum\s+(?:PV\s+)?short[- ]circuit\s+current(?:\s+per\s+MPPT)?\b", r"\bIsc\s+max(?:imum)?\s*/\s*MPPT\b"), amp_units, convert_a),
            "bat_i_max": ((r"\bmaximum\s+(?:charge\s*/\s*discharge|battery)\s+current\b", r"\bmax\.?\s+battery\s+current\b"), amp_units, convert_a),
        }
        for key, (labels, units, factor) in specs.items():
            value = _numeric(text, labels, units, factor)
            if value is not None:
                result[key] = value
        mppt_rx = re.compile(r"\b(?:MPPT|MPP)\s+(?:voltage\s+)?range\b", re.I)
        range_values = re.compile(r"(?P<low>\d+(?:[.,]\d+)?)\s*(?:-|–|—|to)\s*(?P<high>\d+(?:[.,]\d+)?)\s*(?:m?V)\b", re.I)
        ranges = set()
        for line in text.splitlines():
            match = mppt_rx.search(line)
            if not match:
                continue
            tail = line[match.end():match.end() + 80]
            values = range_values.search(tail)
            if values:
                pair = (float(values.group("low").replace(",", ".")),
                        float(values.group("high").replace(",", ".")))
                if values.group(0).lower().endswith("mv"):
                    pair = (pair[0] / 1000, pair[1] / 1000)
                if 0 < pair[0] < pair[1]:
                    ranges.add(pair)
        if len(ranges) == 1:
            low, high = next(iter(ranges))
            result["mppt_min"] = int(low) if low.is_integer() else low
            result["mppt_max"] = int(high) if high.is_integer() else high
        for key in ("type", "phases"):
            value = _enum(text, key)
            if value:
                result[key] = value
    elif category == "Panou":
        specs = {
            "w": ((r"\b(?:rated|nominal|maximum|max\.?)\s+(?:module\s+)?power\b", r"\bP\s*max\b"), kw_units, lambda unit: 1000 if unit == "kw" else 1000000 if unit == "mw" else 1),
            "voc": ((r"\bopen[- ]circuit\s+voltage\b", r"\bVoc\b"), volt_units, convert_v),
            "vmp": ((r"\b(?:voltage| Vmpp?)\s+at\s+(?:maximum|max\.?)\s+power\b", r"\bVmpp\b", r"\bVmp\b"), volt_units, convert_v),
            "isc": ((r"\bshort[- ]circuit\s+current\b", r"\bIsc\b"), amp_units, convert_a),
            "imp": ((r"\bcurrent\s+at\s+(?:maximum|max\.?)\s+power\b", r"\bImpp\b", r"\bImp\b"), amp_units, convert_a),
            "coef_voc": ((r"\b(?:temperature|temp\.?)\s+coefficient\s+(?:of\s+)?Voc\b", r"\bVoc\s+temp(?:erature)?\s+coefficient\b"), ("%/°c", "%/c")),
            "coef_vmp": ((r"\b(?:temperature|temp\.?)\s+coefficient\s+(?:of\s+)?Vmp\b", r"\bVmp\s+temp(?:erature)?\s+coefficient\b"), ("%/°c", "%/c")),
            "temp_noct": ((r"\bNOCT\b",), ("°c", "c")),
            "temp_pmax": ((r"\b(?:temperature|temp\.?)\s+coefficient\s+(?:of\s+)?Pmax\b", r"\bPmax\s+temp(?:erature)?\s+coefficient\b"), ("%/°c", "%/c")),
        }
        for key, spec in specs.items():
            labels, units, *factor = spec
            value = _numeric(text, labels, units, factor[0] if factor else None)
            if value is not None:
                result[key] = value
    elif category == "Baterie":
        specs = {
            "kwh": ((r"\b(?:nominal|usable|rated)\s+(?:energy|capacity)\b", r"\benergy\s+capacity\b"), ("kwh", "wh", "mwh"), convert_kwh),
            "ah": ((r"\b(?:nominal\s+)?capacity\b",), ("ah",)),
            "voltage": ((r"\b(?:nominal|rated)\s+(?:battery\s+)?voltage\b", r"\bbattery\s+voltage\b"), volt_units, convert_v),
            "i_max": ((r"\bmaximum\s+(?:continuous\s+)?discharge\s+current\b", r"\bmax\.?\s+discharge\s+current\b"), amp_units, convert_a),
            "max_fuse_a": ((r"\b(?:maximum|max\.?)\s+(?:recommended\s+)?fuse\b", r"\bmaximum\s+overcurrent\s+protection\b"), amp_units, convert_a),
            "breaker_a": ((r"\b(?:integrated|built[- ]in)\s+(?:DC\s+)?(?:circuit\s+)?breaker\s+(?:rated\s+)?current\b", r"\b(?:DC\s+)?(?:circuit\s+)?breaker\s+(?:rated\s+)?current\b"), amp_units, convert_a),
            "breaker_voltage_dc": ((r"\b(?:DC\s+)?(?:circuit\s+)?breaker\s+(?:rated|nominal)\s+voltage\b", r"\b(?:rated|nominal)\s+(?:DC\s+)?(?:circuit\s+)?breaker\s+voltage\b"), volt_units, convert_v),
            "breaker_poles": ((r"\bnumber\s+of\s+(?:DC\s+)?(?:circuit\s+)?breaker\s+poles\b", r"\bbreaker\s+pole\s+count\b"), ("p", "pole", "poles")),
            "breaker_icu_ka": ((r"\b(?:DC\s+)?(?:circuit\s+)?breaker\s+(?:rated\s+)?breaking\s+capacity\b", r"\bIcu\s+(?:of\s+)?(?:the\s+)?(?:DC\s+)?(?:circuit\s+)?breaker\b"), ("ka",)),
        }
        for key, spec in specs.items():
            labels, units, *factor = spec
            value = _numeric(text, labels, units, factor[0] if factor else None)
            if value is not None:
                result[key] = value
        breaker_poles = _battery_breaker_poles(text)
        if breaker_poles is not None:
            result["breaker_poles"] = breaker_poles
        integration = _battery_breaker_integrated(text)
        if integration is not None:
            result["breaker_integrated"] = integration
        for key in ("tech", "coupling"):
            value = _enum(text, key)
            if value:
                result[key] = value
    elif category == "Smart meter":
        value = _enum(text, "phases")
        if value:
            result["phases"] = value
        current = _numeric(text, (r"\bmaximum\s+rated\s+current\s*\(Imax\)", r"\bmaximum\s+current\s*\(Imax\)", r"\bImax\b"), amp_units, convert_a)
        if current is not None:
            result["current_max_a"] = current

        def labelled_value(patterns):
            values = set()
            lines = text.splitlines()
            for index, line in enumerate(lines):
                for pattern in patterns:
                    match = re.search(pattern, line, re.I)
                    if match:
                        value = re.sub(r"\s+", " ", line[match.end():]).strip(" :;")
                        if not value and index + 1 < len(lines):
                            value = re.sub(r"\s+", " ", lines[index + 1]).strip(" :;")
                        if value:
                            values.add(value[:120])
            return next(iter(values)) if len(values) == 1 else None

        voltage = labelled_value((r"\bNominal voltage(?:\s*\(Un\))?",))
        frequency = labelled_value((r"\bOperational frequency range",))
        accuracy = labelled_value((r"\bAccuracy class",))
        if voltage:
            result["voltage_nominal_v"] = voltage
        if frequency:
            result["frequency_hz"] = frequency
        if accuracy:
            result["accuracy_class"] = accuracy

        normalized_text = re.sub(r"\s+", " ", text)
        model_match = re.search(r"\bSDM630-Modbus\b(.*?)(?=\bSDM630-(?:Mbus|MT|Std|Standard|Pulse|2T|M-DI)\b|$)", normalized_text, re.I)
        if model_match:
            model_segment = model_match.group(1)
            protocol = "RS485 Modbus RTU" if re.search(r"\bRS485\s+Modbus\s+RTU\b", model_segment, re.I) else None
            wiring = re.search(r"\b(3PH-4W,\s*3PH-3W,\s*1PH-2W)\b", model_segment, re.I)
            if protocol:
                result["protocol"] = protocol
            if wiring:
                result["wiring"] = wiring.group(1)
    else:
        return {}
    return result

