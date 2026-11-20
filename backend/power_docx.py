"""Prefill DEER's published Anexa 1 DOCX without inventing applicant data or signatures."""
import io
import re
from functools import lru_cache

import httpx
from docx import Document

DEER_ANEXA1_URL = "https://www.distributie-energie.ro/wp-content/uploads/2023/12/4.-Loc-consum-si_sau-producere-existent-Spor-Putere_Anexa-nr-1.docx"


def _text(value):
    if value in (None, ""):
        return ""
    return str(value).strip()


def _first(*values):
    return next((_text(value) for value in values if _text(value)), "")


def _replace_paragraph(paragraph, values):
    original = "".join(run.text for run in paragraph.runs)
    if not original:
        original = paragraph.text
    index = 0

    def replace(match):
        nonlocal index
        if index >= len(values):
            return match.group(0)
        value = _text(values[index])
        index += 1
        return value if value else match.group(0)

    result = re.sub(r"\.{4,}", replace, original)
    if result == original:
        return
    if paragraph.runs:
        paragraph.runs[0].text = result
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(result)


def _set_cell(cell, value):
    if value in (None, ""):
        return
    cell.text = str(value)


def _ensure_rows(table, count):
    while len(table.rows) < count:
        table.add_row()


def _write_rows(table, rows, start=2):
    if not rows:
        return
    _ensure_rows(table, start + len(rows))
    for row_index, values in enumerate(rows, start=start):
        for col_index, value in enumerate(values):
            if col_index < len(table.rows[row_index].cells):
                _set_cell(table.rows[row_index].cells[col_index], value)


def _number(value):
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _enabled(value):
    return value is True or str(value or "").strip().casefold() in {"1", "true", "yes", "da", "on"}


def _cef_rows(rec):
    cef = rec.get("cef") or {}
    inverters = cef.get("inverters") or []
    panel_rows = {}
    inverter_rows = []
    battery_items = []

    for inv in inverters:
        model = _first(inv.get("brand_model"), inv.get("model"))
        strings = inv.get("strings") or []
        for string in strings:
            panel = _first(string.get("panel_model"), inv.get("panel_model")) or "Model panou neprecizat"
            count = max(0, int(_number(string.get("panels"))))
            watt = _number(string.get("panel_w") or inv.get("panel_w"))
            panel_rows.setdefault(panel, [0, 0.0])
            panel_rows[panel][0] += count
            panel_rows[panel][1] += watt * count / 1000

        phases = _first(inv.get("phases")).casefold()
        voltage = "400" if "tri" in phases or "3" in phases else ("230" if phases else "")
        battery_only = _enabled(inv.get("battery_only")) or _enabled(inv.get("no_panels"))
        units = max(1, int(_number(inv.get("count")) or 1))
        nominal = _number(inv.get("p_nom_kw"))
        limit = 0.0 if battery_only else _number(inv.get("p_limit_kw") or inv.get("p_max_kw") or inv.get("p_nom_kw"))
        inverter_rows.append([
            str(len(inverter_rows) + 1), str(units), model, voltage,
            f"{nominal:.3f}" if nominal else "",
            f"{limit:.3f}" if limit else "0" if battery_only else "",
            f"{limit * units:.3f}" if limit else "0" if battery_only else "",
            "Invertor baterie fără panouri; evacuare 0 kW" if battery_only else "",
        ])

        battery = inv.get("battery") or {}
        if inv.get("battery_mode") == "own" and battery:
            battery_items.append(battery)

    battery_items.extend(cef.get("shared_batteries") or [])
    if not battery_items:
        legacy_battery = cef.get("battery") or rec.get("battery") or {}
        if legacy_battery:
            battery_items.append(legacy_battery)

    panels = []
    for index, (model, (count, power)) in enumerate(panel_rows.items(), start=1):
        unit_power = power / count if count else 0
        panels.append([
            str(index), str(count), model, f"{unit_power:.3f}" if unit_power else "",
            f"{power:.3f}" if power else "", f"{power:.3f}" if power else "",
            f"{power:.3f}" if power else "", "",
        ])

    battery_labels = []
    ah_values = []
    for battery in battery_items:
        model = _first(battery.get("model"), battery.get("brand_model"))
        modules = max(1, int(_number(battery.get("modules")) or 1))
        kwh = _number(battery.get("kwh"))
        ah = _number(battery.get("ah"))
        voltage = _number(battery.get("voltage"))
        label = f"{modules} × {model}" if modules > 1 and model else model
        if kwh:
            label = f"{label} ({kwh * modules:.3f} kWh)" if label else f"{kwh * modules:.3f} kWh"
        if label:
            battery_labels.append(label)
        if ah:
            ah_values.append(ah)

    # Report Ah only when every listed module has the same manufacturer value;
    # do not guess whether the battery modules are connected in series or parallel.
    battery_ah = f"{ah_values[0]:.3f}" if ah_values and all(abs(x - ah_values[0]) < 0.001 for x in ah_values) else ""
    battery = {"details": "; ".join(battery_labels), "ah": battery_ah}
    return panels, inverter_rows, battery


async def render_deer_annex1(rec, client, settings):
    """Return a copy of DEER's current official Anexa 1 DOCX, prefilled from saved records."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=35, headers={"User-Agent": "DNS-Energy/1.0"}) as http:
        response = await http.get(DEER_ANEXA1_URL)
    response.raise_for_status()
    if not response.content.startswith(b"PK"):
        raise ValueError("Formularul oficial DEER nu a fost descărcat în format DOCX.")
    doc = Document(io.BytesIO(response.content))
    c, s = client or {}, settings or {}
    cef = rec.get("cef") or {}
    invs = cef.get("inverters") or []
    all_panels, inverter_rows, battery = _cef_rows(rec)
    panels_count = sum(int(row[0]) for row in all_panels) if all_panels else 0
    kwp = sum(float(row[4]) for row in all_panels) if all_panels else 0
    requested = _first(rec.get("requested_power_kw"), rec.get("requested"), rec.get("power"))
    approved = _first(rec.get("approved_power_kw"), rec.get("approved"), rec.get("bransament_kw"))
    requested_kva = _first(rec.get("requested_kva"), rec.get("power_kva"))
    site_address = _first(rec.get("address"), c.get("address"))
    recipient = _first(c.get("name"), rec.get("client_name"))
    identity = _first(c.get("idcode"), c.get("cnp"), rec.get("cnp"))
    company = _first(s.get("company"))
    rep = _first(s.get("rep"), s.get("representative"))
    phone = _first(c.get("phone"), rec.get("phone"))
    email = _first(c.get("email"), rec.get("email"))
    county = _first(c.get("county"), rec.get("county"))
    locality = _first(c.get("locality"), rec.get("locality"))
    pod = _first(c.get("pod"), rec.get("pod"))
    cf = _first(c.get("cf_nr"), rec.get("cf_nr"))
    cadastral = _first(c.get("cadastral_nr"), rec.get("cadastral_nr"))
    hq = _first(c.get("hq_address"), c.get("address"))
    personal = [
        recipient, county, locality, _first(c.get("postal_code"), rec.get("postal_code")), hq, "", "", "", "", "",
        phone, "", "", email, identity, identity, _first(c.get("regcom"), rec.get("regcom")),
        _first(c.get("rep_name"), rec.get("rep_name")), _first(c.get("rep_role"), rec.get("rep_role")),
        _first(c.get("iban"), rec.get("iban")), _first(c.get("bank"), rec.get("bank")), "",
        company, "", hq, "", "", "", "", "", phone, "", "", email, _first(s.get("anre_attest")), "",
        _first(s.get("anre_issuer"), "ANRE"),
    ]
    for paragraph in doc.paragraphs:
        txt = paragraph.text
        if "Utilizatorul " in txt:
            _replace_paragraph(paragraph, personal)
        elif "obţinerea avizului tehnic de racordare" in txt or "obținerea avizului tehnic de racordare" in txt:
            _replace_paragraph(paragraph, [county, locality, site_address, cf, cadastral])
            paragraph.text = paragraph.text.replace("[]", "[X]", 1)
        elif "Data estimată solicitată" in txt:
            _replace_paragraph(paragraph, [_first(rec.get("energize_date"), rec.get("estimated_energize_date"))])
    paragraphs = doc.paragraphs
    for index, paragraph in enumerate(paragraphs):
        if "Modul de alimentare actual" in paragraph.text:
            current_supply = _first(rec.get("current_supply_desc"), rec.get("current_supply"), rec.get("supply"))
            change_text = _first(rec.get("changes"), rec.get("other_changes"), rec.get("purpose"))
            details = []
            if current_supply:
                details.append(f"Alimentare existentă: {current_supply}")
            if approved:
                details.append(f"Putere aprobată existentă: {approved} kW")
            if requested:
                details.append(f"Putere solicitată: {requested} kW")
            if change_text:
                details.append(change_text)
            if details and index + 1 < len(paragraphs):
                paragraphs[index + 1].text = "; ".join(details)
            break

    # DEER Anexa 1 tables: consumption power (0), receptors (1), export
    # power (2), PV modules (5), inverters (6), storage (8), separate meter (9).
    for table_index, table in enumerate(doc.tables):
        if table_index == 0 and len(table.rows) >= 2:
            _set_cell(table.rows[0].cells[1], requested)
            _set_cell(table.rows[1].cells[1], requested_kva)
        elif table_index == 1:
            receptors = rec.get("receptors") or []
            _write_rows(table, [[str(i + 1), _first(row.get("name")), _first(row.get("kw"), row.get("power_kw")), _first(row.get("notes"))]
                                for i, row in enumerate(receptors) if isinstance(row, dict)])
        elif table_index == 2 and len(table.rows) >= 2:
            grid = cef.get("grid") or {}
            export_kw = _first(
                rec.get("requested_export_kw"), rec.get("power_export_kw"),
                rec.get("p_export_kw"), grid.get("export_limit_kw"),
            )
            if not export_kw:
                total_export = sum(_number(row[6]) for row in inverter_rows)
                export_kw = f"{total_export:.3f}" if total_export else ""
            export_kva = _first(rec.get("requested_export_kva"), rec.get("power_export_kva"))
            _set_cell(table.rows[0].cells[1], export_kw)
            _set_cell(table.rows[1].cells[1], export_kva)
        elif table_index == 5:
            _write_rows(table, all_panels)
        elif table_index == 6:
            _write_rows(table, inverter_rows)
        elif table_index == 8 and battery:
            if len(table.rows[0].cells) > 1:
                _set_cell(table.rows[0].cells[1], battery.get("details"))
            if len(table.rows) > 1 and len(table.rows[1].cells) > 1:
                _set_cell(table.rows[1].cells[1], battery.get("ah"))
        elif table_index == 9:
            grid = cef.get("grid") or {}
            meter_model = _first(grid.get("meter"), rec.get("smart_meter_type"))
            meter_catalog_id = grid.get("meter_catalog_id")
            separate_meter = grid.get("meter_separate") or rec.get("smart_meter_separate")
            if separate_meter or meter_model or meter_catalog_id:
                _set_cell(table.rows[1].cells[0], "1")
                _set_cell(table.rows[1].cells[1], _first(grid.get("meter_serial"), rec.get("smart_meter_serial")))
                _set_cell(table.rows[1].cells[2], meter_model)
                _set_cell(table.rows[1].cells[3], _first(grid.get("meter_technical_data"), rec.get("smart_meter_technical_data")))
    # Only preselect the existing-site option from the explicit request type.
    for paragraph in doc.paragraphs:
        if "Loc de consum şi de producere nou" in paragraph.text and "existent" in paragraph.text.casefold():
            break
        if "Loc de consum şi de producere nou" in paragraph.text:
            paragraph.text = paragraph.text.replace("[]", "[ ]", 1)
        elif "Loc de consum existent/" in paragraph.text:
            paragraph.text = paragraph.text.replace("[]", "[X]", 1)
    doc.core_properties.title = "Anexa 1 DEER — formular oficial precompletat"
    doc.core_properties.subject = "Valorile provin din dosarul DNS Energy; câmpurile fără date rămân necompletate, iar semnătura nu este generată."
    output = io.BytesIO()
    doc.save(output)
    return output.getvalue()
