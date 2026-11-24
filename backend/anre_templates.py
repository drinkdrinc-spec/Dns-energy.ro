import base64
import io
import re
import unicodedata
import uuid
import logging
from copy import deepcopy
from pathlib import Path
from datetime import datetime, timezone, date

from fastapi import HTTPException, Depends, UploadFile, File, Header, Query, Response
from docx import Document
from docx.table import _Row
from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn
from pypdf import PdfReader, PdfWriter

import server as S
import anre_doc as AD

db, api, get_current_user = S.db, S.api_router, S.get_current_user
KEYS = {"cerere": "Cerere-tip ANRE", "organigrama": "Organigrama", "dotari": "Lista dotărilor (Anexa nr. 5)", "personal": "Fișa structurii de personal (Anexa nr. 7)",
        "decl_9": "Declarație pe propria răspundere (Anexa nr. 9)", "decl_10": "Declarație prelucrare date (Anexa nr. 10)"}
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PH = {"firma": "denumirea firmei", "cui": "CUI", "regcom": "nr. Registrul Comerțului", "sediu": "sediul social", "reprezentant": "reprezentant legal", "functie": "funcția reprezentantului",
      "email": "e-mail", "telefon": "telefon", "nr_atestat": "nr. atestat existent", "tipuri_atestat_existent": "tipuri atestat existent", "valabil_pana": "valabilitate atestat existent",
      "tip_solicitare": "tipul solicitării", "tipuri_solicitate": "tipuri de atestat solicitate", "data": "data generării", "lista_personal": "personal (text, câte un rând)",
      "lista_dotari": "dotări (text, câte un rând)", "p.nr / p.name / p.role / p.grade / p.license / p.license_valid / p.contract": "rând de tabel repetat pentru fiecare angajat (Word)",
      "e.nr / e.name / e.serial / e.ownership / e.calibration": "rând de tabel repetat pentru fiecare dotare (Word)"}
RX = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")
now = lambda: datetime.now(timezone.utc).isoformat()


def platform_only(user):
    if user["uid"] != S.PLATFORM["id"]:
        raise HTTPException(status_code=403, detail="Doar administratorul platformei gestionează formularele oficiale")


def ctx(d):
    c = d.get("company") or {}
    st, eq = d.get("staff") or [], d.get("equipment") or []
    return {"firma": c.get("name"), "cui": c.get("cui"), "regcom": c.get("regcom"), "sediu": c.get("address"), "reprezentant": c.get("rep_name"), "functie": c.get("rep_role"),
            "email": c.get("email"), "telefon": c.get("phone"), "nr_atestat": c.get("attest_no"), "tipuri_atestat_existent": c.get("attest_types"), "valabil_pana": c.get("attest_valid"),
            "tip_solicitare": AD.TYPES.get(d.get("kind")), "tipuri_solicitate": ", ".join(d.get("target_types") or []), "data": date.today().strftime("%d.%m.%Y"),
            "lista_personal": "\n".join(f"{i + 1}. {x.get('name') or ''} — {x.get('role') or ''} — {x.get('grade') or ''} — {x.get('license') or ''} {x.get('license_valid') or ''}" for i, x in enumerate(st)),
            "lista_dotari": "\n".join(f"{i + 1}. {x.get('name') or ''} — {x.get('serial') or ''} — {x.get('ownership') or ''} — {x.get('calibration') or ''}" for i, x in enumerate(eq))}


def _sub(text, c):
    return RX.sub(lambda m: str(c[m.group(1)]) if c.get(m.group(1)) not in (None, "") else (AD.M if m.group(1) in c or m.group(1)[:2] in ("p.", "e.") else m.group(0)), text)


def _para(p, c):
    if "{{" in p.text and p.runs:
        t = _sub(p.text, c)
        p.runs[0].text = t
        for r in p.runs[1:]:
            r.text = ""


def _cells(cells, c):
    for cell in cells:
        for p in cell.paragraphs:
            _para(p, c)
        for t in cell.tables:
            _table(t, c)


def _table(t, c):
    for row in list(t.rows):
        txt = "".join(x.text for x in row.cells)
        pre = "p" if "{{p." in txt else "e" if "{{e." in txt else None
        if not pre:
            _cells(row.cells, c)
            continue
        tr = row._tr
        for i, it in enumerate(c["_" + pre] or [{}]):
            new = deepcopy(tr)
            tr.addprevious(new)
            _cells(_Row(new, t).cells, {**c, **{f"{pre}.{k}": v for k, v in it.items()}, f"{pre}.nr": i + 1})
        tr.getparent().remove(tr)


def fill_docx(data, d):
    c = {**ctx(d), "_p": d.get("staff") or [], "_e": d.get("equipment") or []}
    doc = Document(io.BytesIO(data))
    for p in doc.paragraphs:
        _para(p, c)
    for t in doc.tables:
        _table(t, c)
    for s in doc.sections:
        for part in (s.header, s.footer):
            for p in part.paragraphs:
                _para(p, c)
            for t in part.tables:
                _table(t, c)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def pdf_fields(data):
    try:
        return list((PdfReader(io.BytesIO(data)).get_fields() or {}).keys())
    except Exception:
        return []


def fill_pdf(data, d):
    r = PdfReader(io.BytesIO(data))
    fields = r.get_fields() or {}
    c = ctx(d)
    vals = {k: str(c.get(k) or "") for k in fields if k in c}
    w = PdfWriter(clone_from=r)
    for page in w.pages:
        w.update_page_form_field_values(page, vals, auto_regenerate=False)
    w.set_need_appearances_writer(True)
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()



OFFICIAL_SOURCE_URL = "https://anre.ro/participanti-la-piata-de-energie/persoane-juridice/energie-electrica/"
OFFICIAL_BUNDLE_PATH = Path(__file__).parent / "templates" / "anre" / "atestate_order_134_2021.docx.b64"
OFFICIAL_ANNEXES = {"cerere": 4, "dotari": 5, "personal": 7, "decl_9": 9, "decl_10": 10}
EQUIPMENT_GROUPS = {
    "spatii": ("spatii tehnologice netehnologice", "spatii tehnologice", "spatii"),
    "utilaje": ("utilaje",),
    "topografice": ("echipamente topografice", "echipamente topografice", "topografice"),
    "scule": ("scule dispozitive", "scule", "dispozitive"),
    "masura": ("aparate de masura incercare verificare", "aparate de masura", "masura"),
    "birotica": ("birotica hardware software", "birotica", "hardware software"),
}
GROUP_NAMES = {
    "spatii": "Spații tehnologice/netehnologice",
    "utilaje": "Utilaje",
    "topografice": "Echipamente topografice",
    "scule": "Scule, dispozitive",
    "masura": "Aparate de măsură, încercare, verificare",
    "birotica": "Birotică, hardware, software",
}


def official_template_info(key: str) -> dict | None:
    annex = OFFICIAL_ANNEXES.get(key)
    if annex is None or not OFFICIAL_BUNDLE_PATH.exists():
        return None
    return {"name": f"ANRE · Anexa nr. {annex} · Ordinul nr. 134/2021",
            "source_url": OFFICIAL_SOURCE_URL, "annex": annex}


def _norm(value):
    value = unicodedata.normalize("NFD", str(value or "")).encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _official_doc():
    encoded = OFFICIAL_BUNDLE_PATH.read_text(encoding="ascii").strip()
    return Document(io.BytesIO(base64.b64decode(encoded, validate=True)))


def _paragraph_text(node, document):
    return Paragraph(node, document._body).text.strip()


def _trim_to_annex(document, annex):
    body = document._element.body
    children = list(body)
    markers = []
    for index, child in enumerate(children):
        if child.tag != qn("w:p"):
            continue
        match = re.fullmatch(r"Anexa\s+nr\.\s*(\d+)", _paragraph_text(child, document), re.IGNORECASE)
        if match:
            markers.append((index, int(match.group(1))))
    selected = next((index for index, number in markers if number == annex), None)
    if selected is None:
        raise ValueError(f"Anexa nr. {annex} nu există în modelul oficial ANRE încărcat")
    following = next((index for index, number in markers if index > selected), len(children))
    for index, child in enumerate(children):
        if (index < selected or index >= following) and child.tag != qn("w:sectPr"):
            body.remove(child)


def _set_paragraph(paragraph, value):
    if paragraph.runs:
        paragraph.runs[0].text = str(value)
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(str(value))


def _company_value(company, key):
    return str(company.get(key) or "[DE COMPLETAT]").strip()


def _replace_annex4(document, data):
    company = data.get("company") or {}
    name = _company_value(company, "rep_name")
    role = _company_value(company, "rep_role")
    cnp = _company_value(company, "rep_cnp")
    series = _company_value(company, "rep_id_series")
    number = _company_value(company, "rep_id_number")
    issuer = _company_value(company, "rep_id_issuer")
    issue_date = _company_value(company, "rep_id_date")
    firm = _company_value(company, "name")
    address = _company_value(company, "address")
    types = ", ".join(data.get("target_types") or []) or "[DE COMPLETAT]"
    request = AD.TYPES.get(data.get("kind"), "[DE COMPLETAT]")
    paragraphs = list(document.paragraphs)
    for paragraph in paragraphs:
        text = paragraph.text.strip()
        if text.startswith("Subsemnatul"):
            _set_paragraph(paragraph,
                f"Subsemnatul {name}, cod numeric personal {cnp}, posesor al actului de identitate seria {series} nr. {number}, "
                f"eliberat de {issuer} la data {issue_date}, în calitate de {role}, reprezentant legal al operatorului economic "
                f"{firm}, cu sediul social la {address}, solicit {request.lower()} pentru tipurile de atestate: {types}.")
        elif text.startswith("Menţionez") or text.startswith("Menționez"):
            _set_paragraph(paragraph,
                f"Menționez că operatorul economic pe care îl reprezint este înmatriculat la Registrul Comerțului cu nr. "
                f"{_company_value(company, 'regcom')}, are CUI nr. {_company_value(company, 'cui')} și contul nr. "
                f"{_company_value(company, 'bank_account')} deschis la {_company_value(company, 'bank_name')}, "
                f"sucursala {_company_value(company, 'bank_branch')}.")
        elif text.startswith("În scopul comunicării"):
            _set_paragraph(paragraph,
                f"În scopul comunicării cu ANRE pot fi contactat la sediul operatorului economic, telefon "
                f"{_company_value(company, 'phone')}, fax {_company_value(company, 'fax')}, e-mail "
                f"{_company_value(company, 'email')}.")
        elif text.startswith("Data"):
            _set_paragraph(paragraph, f"Data: {date.today().strftime('%d.%m.%Y')}")


def _fill_table_cell(cell, value):
    cell.text = str(value or "")


def _equipment_group(item):
    value = _norm(item.get("group") or item.get("category") or "")
    for key, terms in EQUIPMENT_GROUPS.items():
        if any(term in value for term in terms):
            return key
    return None


def _fill_equipment_table(table, data):
    grouped = {key: [] for key in GROUP_NAMES}
    for item in data.get("equipment") or []:
        key = _equipment_group(item)
        if key:
            grouped[key].append(item)
    rows = list(table.rows)
    section_rows = {}
    for index, row in enumerate(rows):
        first = _norm(row.cells[0].text)
        for key, terms in EQUIPMENT_GROUPS.items():
            if any(term in first for term in terms):
                section_rows[key] = index
                break
    ordered_sections = sorted(section_rows.items(), key=lambda item: item[1])
    for group_index, (key, start) in enumerate(ordered_sections):
        end = ordered_sections[group_index + 1][1] if group_index + 1 < len(ordered_sections) else len(rows)
        data_rows = [rows[i] for i in range(start + 1, end) if _norm(rows[i].cells[0].text) in ("1", "2", "")]
        items = grouped[key]
        while len(data_rows) < len(items):
            source = data_rows[-1] if data_rows else rows[start]
            tr = deepcopy(source._tr)
            source._tr.addnext(tr)
            inserted = _Row(tr, table)
            data_rows.append(inserted)
        for index, row in enumerate(data_rows):
            item = items[index] if index < len(items) else None
            if not item:
                for cell in row.cells:
                    _fill_table_cell(cell, "")
                continue
            _fill_table_cell(row.cells[0], index + 1)
            _fill_table_cell(row.cells[1], item.get("name"))
            _fill_table_cell(row.cells[2], item.get("quantity"))
            _fill_table_cell(row.cells[3], item.get("ownership"))


def _fill_staff_table(table, data):
    staff = data.get("staff") or []
    rows = list(table.rows)
    data_rows = rows[1:]
    while len(data_rows) < len(staff):
        source = data_rows[-1] if data_rows else rows[0]
        tr = deepcopy(source._tr)
        source._tr.addnext(tr)
        data_rows.append(_Row(tr, table))
    for index, row in enumerate(data_rows):
        person = staff[index] if index < len(staff) else None
        values = ["", "", "", "", "", "", ""]
        if person:
            license_text = "; ".join(str(value) for value in (
                person.get("grade"), person.get("license"),
                f"valabilă până la {person.get('license_valid')}" if person.get("license_valid") else None
            ) if value)
            values = [index + 1, person.get("name"), person.get("education"), person.get("role"),
                      person.get("contract"), person.get("contract_duration"), license_text]
        for cell, value in zip(row.cells, values):
            _fill_table_cell(cell, value)


def fill_official_annex(key, data):
    annex = OFFICIAL_ANNEXES[key]
    document = _official_doc()
    _trim_to_annex(document, annex)
    if key == "cerere":
        _replace_annex4(document, data)
    elif key == "decl_9":
        company = data.get("company") or {}
        for paragraph in document.paragraphs:
            if paragraph.text.strip().startswith("Subsemnatul,"):
                _set_paragraph(paragraph,
                    f"Subsemnatul, {_company_value(company, 'rep_name')}, cod numeric personal {_company_value(company, 'rep_cnp')}, "
                    f"posesor al actului de identitate seria {_company_value(company, 'rep_id_series')} nr. "
                    f"{_company_value(company, 'rep_id_number')}, eliberat de {_company_value(company, 'rep_id_issuer')} la data "
                    f"{_company_value(company, 'rep_id_date')}, în calitate de {_company_value(company, 'rep_role')}, "
                    f"reprezentant legal al operatorului economic {_company_value(company, 'name')}, cu sediul în "
                    f"{_company_value(company, 'address')}, înregistrat la Registrul Comerțului cu nr. "
                    f"{_company_value(company, 'regcom')}, având CUI nr. {_company_value(company, 'cui')}, cunoscând prevederile art. 326 din Codul penal privind falsul în declarații, declar pe propria răspundere următoarele:")
    elif key == "dotari" and document.tables:
        _fill_equipment_table(document.tables[0], data)
    elif key == "personal" and document.tables:
        _fill_staff_table(document.tables[0], data)
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


async def filled(key, d):
    t = await db.anre_templates.find_one({"key": key}, {"_id": 0})
    if t:
        data = S.get_object(t["path"])[0]
        if t["type"] == DOCX:
            return fill_docx(data, d), DOCX, f"{key}.docx"
        if t.get("fields"):
            return fill_pdf(data, d), "application/pdf", f"{key}.pdf"
    if key in OFFICIAL_ANNEXES and OFFICIAL_BUNDLE_PATH.exists():
        try:
            return fill_official_annex(key, d), DOCX, f"ANRE_Anexa_{OFFICIAL_ANNEXES[key]}.docx"
        except Exception as exc:
            logging.getLogger(__name__).warning("Nu s-a putut precompleta Anexa ANRE %s: %s", key, type(exc).__name__)
    return None


@api.get("/admin/anre/templates")
async def tpl_list(user: dict = Depends(get_current_user)):
    platform_only(user)
    have = {t["key"]: t for t in await db.anre_templates.find({}, {"_id": 0, "path": 0}).to_list(50)}
    return {"items": [{"key": k, "label": l, "template": have.get(k), "official_default": official_template_info(k)} for k, l in KEYS.items()], "placeholders": PH}


@api.post("/admin/anre/templates/{key}")
async def tpl_upload(key: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    platform_only(user)
    if key not in KEYS:
        raise HTTPException(status_code=400, detail="Formular necunoscut")
    data, ct = await file.read(), file.content_type or ""
    if (file.filename or "").lower().endswith(".docx"):
        ct = DOCX
    ok = (ct == "application/pdf" and data.startswith(b"%PDF")) or (ct == DOCX and data.startswith(b"PK"))
    if not ok or len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Încărcați formularul oficial ca PDF sau Word (.docx), maxim 15 MB")
    if ct == DOCX:
        try:
            doc = Document(io.BytesIO(data))
            txt = "\n".join(p.text for p in doc.paragraphs) + "".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
        except Exception:
            raise HTTPException(status_code=400, detail="Fișierul Word nu poate fi citit")
        fields = sorted(set(RX.findall(txt)))
    else:
        fields = pdf_fields(data)
    st = S.put_object(f"{S.APP_NAME}/anre_templates/{key}_{uuid.uuid4().hex[:6]}_{(file.filename or 'formular')[-50:]}", data, ct)
    t = {"key": key, "path": st["path"], "name": file.filename, "type": ct, "size": len(data), "fields": fields,
         "matched": [f for f in fields if f in ctx({}) or f[:2] in ("p.", "e.")], "at": now(), "by": user.get("email")}
    await db.anre_templates.update_one({"key": key}, {"$set": t}, upsert=True)
    await S.audit(user, "formular oficial ANRE încărcat", "anre", key, [file.filename or ""])
    return await tpl_list(user)


@api.delete("/admin/anre/templates/{key}")
async def tpl_delete(key: str, user: dict = Depends(get_current_user)):
    platform_only(user)
    await db.anre_templates.delete_one({"key": key})
    await S.audit(user, "formular oficial ANRE eliminat", "anre", key, [])
    return await tpl_list(user)


@api.get("/admin/anre/templates/{key}/file")
async def tpl_file(key: str, authorization: str = Header(None), auth: str = Query(None)):
    user = await S.user_from_token(authorization, auth)
    platform_only(user)
    t = await db.anre_templates.find_one({"key": key}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Formular neîncărcat")
    return Response(content=S.get_object(t["path"])[0], media_type=t["type"], headers={"Content-Disposition": S.disp("inline", t["name"] or key), "Cache-Control": "no-store"})
