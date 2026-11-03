"""Equipment snapshot helpers for ATR requests created without an existing prosumer dossier."""
from __future__ import annotations


def _number(value) -> float:
    try:
        return float(str(value or 0).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def from_request(rec: dict | None) -> dict:
    """Expose explicitly selected ATR equipment in the same shape as a prosumer record.

    This is a snapshot from the ATR form, not a fabricated installation record. Empty
    equipment returns an empty mapping so existing "equipment required" checks remain.
    """
    rec = rec or {}
    cef = rec.get("atr_cef")
    if not isinstance(cef, dict):
        return {}
    inverters = [item for item in (cef.get("inverters") or []) if isinstance(item, dict)]
    batteries = [item for item in (cef.get("shared_batteries") or []) if isinstance(item, dict)]
    if not inverters and not batteries:
        return {}
    total_panels = 0
    total_kwp = 0.0
    total_inverter_kw = 0.0
    for inverter in inverters:
        count = max(1.0, _number(inverter.get("count") or inverter.get("quantity") or 1))
        panels = sum(max(0.0, _number(string.get("panels")))
                     for string in (inverter.get("strings") or []) if isinstance(string, dict))
        total_panels += int(panels * count)
        total_kwp += panels * max(0.0, _number(inverter.get("panel_w"))) * count / 1000
        total_inverter_kw += max(0.0, _number(inverter.get("p_nom_kw"))) * count
        battery = inverter.get("battery") or {}
        if inverter.get("battery_mode") == "own" and isinstance(battery, dict) and battery.get("model"):
            batteries.append(battery)
    snapshot = {
        "cef": cef,
        "operator": rec.get("operator") or "",
        "client_id": rec.get("client_id") or "",
        "client_name": rec.get("client_name") or "",
        "address": rec.get("address") or "",
        "pod": rec.get("pod") or "",
        "supply": rec.get("supply") or (cef.get("grid") or {}).get("supply") or "",
        "bransament_kw": rec.get("p_abs_kw") or "",
        "power": rec.get("p_evac_kw") or "",
        "panel_count": total_panels or "",
        "panel_kwp": round(total_kwp, 4) if total_kwp > 0 else "",
        "inverter_kw": round(total_inverter_kw, 4) if total_inverter_kw > 0 else "",
    }
    if batteries:
        snapshot["cef"] = {**cef, "shared_batteries": batteries}
    return snapshot
