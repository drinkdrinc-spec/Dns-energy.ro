"""Mapping from power-increase dossiers into DI-U technical records."""

import cef as CEF


def _rcd(value):
    return str(value).replace("Tip", "").replace("tip", "").strip() if value else value


def inverter_circuit_name(index: int, inverter: dict) -> str:
    try:
        count = max(1, int(float(inverter.get("count") or 1)))
    except (TypeError, ValueError):
        count = 1
    model = inverter.get("brand_model") or "invertor"
    return f"INV{index + 1} — {model}" + (f" × {count} buc." if count > 1 else "")


def power_cef_diu_fields(power: dict) -> dict:
    """Map declared power-request design data into DI-U technical fields."""
    cef = power.get("power_cef") if isinstance(power.get("power_cef"), dict) else {}
    grid = cef.get("grid") if isinstance(cef.get("grid"), dict) else {}
    inverters = cef.get("inverters") if isinstance(cef.get("inverters"), list) else []
    fields = {
        "power_cef_snapshot": cef,
        "supply": grid.get("supply") or power.get("new_supply") or power.get("current_supply") or power.get("supply") or "",
        "earthing": grid.get("earthing") or "",
        "tg_breaker_a": grid.get("tg_breaker_a") or "",
        "bmp_a": grid.get("bmp_a") or "",
        "meter_enabled": grid.get("meter_enabled") if grid.get("meter_enabled") is not None else grid.get("meter"),
        "meter": grid.get("meter") or "",
        "meter_serial": grid.get("meter_serial") or "",
        "meter_specs": grid.get("meter_specs") or "",
        "type": "Sistem fotovoltaic hibrid" if CEF.has_storage({"cef": cef}) else "Sistem fotovoltaic on-grid",
        "circuits": [{
            "name": inverter_circuit_name(index, inverter),
            "breaker_a": (inverter.get("ac") or {}).get("breaker_a"),
            "curve": (inverter.get("ac") or {}).get("curve") or "C",
            "section": (inverter.get("ac") or {}).get("section"),
            "cable": (inverter.get("ac") or {}).get("cable_type"),
            "length": (inverter.get("ac") or {}).get("length_m"),
            "rcd_ma": inverter.get("rcd_ma"),
            "rcd_type": _rcd(inverter.get("rcd_type")),
        } for index, inverter in enumerate(inverters) if isinstance(inverter, dict)],
    }
    return {key: value for key, value in fields.items() if value not in (None, "")}


def power_cef_diu_sync(rec: dict, power: dict) -> dict:
    """Prepare safe DI-U synchronization while preserving manual user edits."""
    mapped = power_cef_diu_fields(power)
    previous = rec.get("power_cef_snapshot") if isinstance(rec.get("power_cef_snapshot"), dict) else {}
    previous_fields = power_cef_diu_fields({"power_cef": previous}) if previous else {}
    sync = {"power_cef_snapshot": mapped.get("power_cef_snapshot", {})}
    for key, value in mapped.items():
        if key in ("power_cef_snapshot", "circuits"):
            continue
        old_value = previous_fields.get(key)
        if rec.get(key) in (None, "") or (previous and rec.get(key) == old_value):
            sync[key] = value
    old_circuits = previous_fields.get("circuits")
    if not rec.get("circuits") or (previous and rec.get("circuits") == old_circuits):
        sync["circuits"] = mapped.get("circuits", [])
    return sync

