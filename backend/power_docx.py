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


def _cef_rows(rec):
    cef = rec.get("cef") or {}
    inverters = cef.get("inverters") or []
    panel_rows = {}
    inverter_rows = []
    battery = cef.get("battery") or rec.get("battery") or {}
    for inv in inverters:
        model = _first(inv.get("brand_model"), inv.get("model"))
        strings = inv.get("strings") or []
        grouped = {}
        for string in strings:
            panel = _first(string.get("panel_model"), inv.get("panel_model"))
            grouped.setdefault(panel or "Model panou neprecizat", 0)
            try:
                grouped[panel or "Model panou neprecizat"] += int(float(string.get("panels") or 0))
            except (TypeError, ValueError):
                pass
        for string in strings:
            panel = _first(string.get("panel_model"), inv.get("panel_model")) or "Model panou neprecizat"
            try:
                count = int(float(string.get("panels") or 0))
                watt = float(string.get("panel_w") or inv.get("panel_w") or 0)
            except (TypeError, ValueError):
                count, watt = 0, 0
            panel_rows.setdefault(panel, [0, 0.0])
            panel_rows[panel][0] += count
            panel_rows[panel][1] += watt * count / 1000
        phases = _first(inv.get("phases")).casefold()
        voltage = "400" if "tri" in phases or "3" in phases else ("230" if phases else "")
        battery_only = bool(inv.get("battery_only") or inv.get("no_panels"))
        maximum = "0" if battery_only else _first(inv.get("p_max_kw"), inv.get("p_nom_kw"))
        inverter_rows.append([
            str(len(inverter_rows) + 1), "1", model, voltage, _first(inv.get("p_nom_kw")),
            maximum, maximum, "Invertor baterie fără panouri; evacuare 0 kW" if battery_only else "",
        ])
    panels = []
    for index, (model, (count, power)) in enumerate(panel_rows.items(), start=1):
        unit_power = (power / count) if count else 0
        panels.append([str(index), str(count), model, f"{unit_power:.3f}" if unit_power else "",
                       f"{power:.3f}" if power else "", f"{power:.3f}" if power else "",
                       f"{power:.3f}" if power else "", ""])
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

    for table_index, table in enumerate(doc.tables):
        if table_index == 0 and len(table.rows) >= 3:
            _set_cell(table.rows[1].cells[1], requested)
            _set_cell(table.rows[2].cells[1], requested_kva)
        elif table_index == 1:
            receptors = rec.get("receptors") or []
            _write_rows(table, [[str(i + 1), _first(row.get("name")), _first(row.get("kw"), row.get("power_kw")), _first(row.get("notes"))]
                                for i, row in enumerate(receptors) if isinstance(row, dict)])
        elif table_index == 4:
            _write_rows(table, all_panels)
        elif table_index == 5:
            _write_rows(table, inverter_rows)
        elif table_index == 7:
            if battery:
                _set_cell(table.rows[1].cells[0], "Detalii schemă alimentare")
                _set_cell(table.rows[1].cells[1], _first(battery.get("connection"), battery.get("model")))
                _set_cell(table.rows[2].cells[1], _first(battery.get("ah")))
        elif table_index == 8:
            meter = cef.get("smart_meter") or rec.get("smart_meter") or {}
            meter_model = _first(meter.get("model"), rec.get("smart_meter_type"))
            if meter.get("separate") or meter_model:
                _set_cell(table.rows[1].cells[0], "1")
                _set_cell(table.rows[1].cells[1], _first(meter.get("serial"), rec.get("smart_meter_serial")))
                _set_cell(table.rows[1].cells[2], meter_model)
                _set_cell(table.rows[1].cells[3], _first(meter.get("technical_data")))
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
