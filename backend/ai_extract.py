import base64
import os
import json
import re
import uuid
import tempfile
from ai_provider import LlmChat, UserMessage, FileContentWithMimeType, ImageContent, TextDelta, StreamDone

OPERATORS = ["DEER — Transilvania Nord", "DEER — Transilvania Sud", "DEER — Muntenia Nord", "Delgaz Grid",
             "Distribuție Energie Oltenia", "Rețele Electrice România", "Alt operator"]

PROMPT = f"""Ești expert în dosare de racordare prosumatori din România. Extrage datele din documentul atașat și răspunde DOAR cu un obiect JSON valid, fără text suplimentar, cu cheile:
client_name (nume beneficiar/titular), owner_name (proprietar CF), cnp (CNP sau CUI), address (adresa loc de consum), hq_address (domiciliu din CI), consumption_address (adresa de pe factură), id_series (serie CI), id_number (număr CI), cf_nr (număr carte funciară), cadastral_nr (număr cadastral), county (județ), pod (cod loc de consum / POD), supplier (furnizor energie), phone, email, doc_type (tip document), summary (rezumat scurt),
operator (alege EXACT una dintre: {OPERATORS}; Bihor/Cluj/Satu Mare/Sălaj/Maramureș/Bistrița => "DEER — Transilvania Nord"; Alba/Brașov/Covasna/Harghita/Mureș/Sibiu => "DEER — Transilvania Sud"; Prahova/Buzău/Brăila/Galați/Vrancea/Focșani => "DEER — Muntenia Nord"),
power (putere instalată/evacuată kW, număr), apparent_kva (număr), supply ("Monofazat" sau "Trifazat"), bransament_kw (putere aprobată loc consum, număr sau null),
system_type ("On-grid", "Hibrid cu baterie" sau "Off-grid"), inverter (marcă și model), inverter_kw (număr), inverter_count (număr),
panels (marcă și model module), panel_count (număr), panel_w (W per modul, număr), battery (marcă și model sau null), battery_kwh, battery_ah, battery_v (numere sau null),
grounding_ohm (rezistența prizei de pământ măsurată, număr sau null), date (data documentului YYYY-MM-DD), atr (nr ATR/aviz dacă există), afm ("Da" sau "Nu"),
executant_rep (reprezentant executant), notes (scurt rezumat în română al documentului și lista documentelor conținute).
Folosește null pentru valorile lipsă."""


def _parse(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    data = json.loads(m.group(0)) if m else {}
    return {k: v for k, v in data.items() if v not in (None, "", "null")}


def _images(content: bytes, mime: str) -> list:
    if mime == "application/pdf":
        import pymupdf
        doc = pymupdf.open(stream=content, filetype="pdf")
        out = []
        for page in list(doc)[:4]:
            r = page.rect
            zoom = min(1600 / max(r.width, r.height), 2.5)
            out.append(ImageContent(image_base64=base64.b64encode(page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).tobytes("png")).decode()))
        return out

    from io import BytesIO
    from PIL import Image, ImageOps
    if mime in {"image/heic", "image/heif", "image/heic-sequence", "image/heif-sequence"}:
        from pillow_heif import register_heif_opener
        register_heif_opener()
    with Image.open(BytesIO(content)) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((2000, 2000))
        png = BytesIO()
        image.save(png, format="PNG", optimize=True)
    return [ImageContent(image_base64=base64.b64encode(png.getvalue()).decode())]


def extract_office_text(content: bytes, mime: str) -> str:
    """Read text from supported Office files without evaluating formulas or macros."""
    from io import BytesIO
    chunks = []
    if mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        from docx import Document
        document = Document(BytesIO(content))
        chunks.extend(p.text for p in document.paragraphs if p.text.strip())
        for table in document.tables:
            for row in table.rows:
                chunks.append(" | ".join(cell.text.strip() for cell in row.cells))
    elif mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        from openpyxl import load_workbook
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        for sheet in workbook.worksheets[:10]:
            chunks.append(f"[Foaia: {sheet.title}]")
            for row in sheet.iter_rows(max_row=150, values_only=True):
                cells = [str(value).strip() for value in row if value is not None and str(value).strip()]
                if cells:
                    chunks.append(" | ".join(cells))
        workbook.close()
    else:
        raise ValueError("Citirea automată este disponibilă pentru DOCX și XLSX; fișierul poate rămâne atașat pentru verificare manuală.")
    text = "\n".join(chunks).strip()
    if not text:
        raise ValueError("Fișierul Office nu conține text lizibil.")
    return text[:24000]


async def extract_gpt_text(text: str, doc_type: str = "other") -> dict:
    chat = LlmChat(api_key=os.environ["OPENAI_API_KEY"], session_id=f"extract-{uuid.uuid4()}",
                   system_message="Extragi date structurate din documente românești. Răspunzi doar JSON.").with_model("openai", "gpt-4.1-mini")
    out = ""
    hint = {
        "ci": "Extrage titularul, CNP, seria/numărul și domiciliul din CI.",
        "factura": "Extrage titularul, POD-ul, operatorul, furnizorul, adresa locului de consum și puterea aprobată.",
        "cf": "Extrage proprietarul, numărul CF și numărul cadastral.",
        "other": "Identifică documentul și rezumă-l; extrage doar datele relevante care apar explicit.",
    }.get(doc_type, "Identifică documentul și extrage datele vizibile.")
    prompt = PROMPT + "\n\n" + hint + "\n\nTEXT EXTRAS DIN DOCUMENT (poate conține erori de OCR; nu deduce valori lipsă):\n" + text
    async for ev in chat.stream_message(UserMessage(text=prompt)):
        if isinstance(ev, TextDelta):
            out += ev.content
        elif isinstance(ev, StreamDone):
            break
    data = _parse(out)
    if not data:
        raise ValueError("AI nu a putut identifica date structurate în acest document.")
    return data


def extract_office_local(content: bytes, mime: str, doc_type: str = "other") -> dict:
    text = extract_office_text(content, mime)
    try:
        fields = _fallback_text_fields(text, doc_type)
    except ValueError:
        fields = {"doc_type": "Document Office", "summary": "Textul documentului a fost citit local; nu s-au găsit etichete clare pentru extragerea automată a câmpurilor."}
        fields["_engine"] = "Citire locală Office"
    return fields


async def extract_gpt(content: bytes, mime: str, doc_type: str = "auto") -> dict:
    chat = LlmChat(api_key=os.environ["OPENAI_API_KEY"], session_id=f"extract-{uuid.uuid4()}",
                   system_message="Extragi date structurate din documente tehnice românești. Răspunzi doar JSON.").with_model("openai", "gpt-4.1-mini")
    out = ""
    hints = {
        "ci": "Document de identitate: extrage titularul, CNP, serie/număr, domiciliul și nu confunda domiciliul cu locul de consum.",
        "factura": "Factură de energie: extrage POD, operator, furnizor, adresa locului de consum, titularul și puterea aprobată dacă apare.",
        "cf": "Extras de carte funciară: extrage proprietarul, numărul CF și numărul cadastral. Nu inventa date lipsă.",
        "other": "Identifică tipul documentului și rezumă-l; extrage datele relevante numai dacă sunt vizibile.",
    }
    prompt = PROMPT + "\n\nTip document selectat: " + hints.get(doc_type, "Identifică tipul documentului.") + " Nu deduce și nu completa valori absente."
    async for ev in chat.stream_message(UserMessage(text=prompt, file_contents=_images(content, mime))):
        if isinstance(ev, TextDelta):
            out += ev.content
        elif isinstance(ev, StreamDone):
            break
    return _parse(out)


def _labeled_value(text: str, labels: str) -> str | None:
    match = re.search(rf"(?:{labels})\s*[:：-]\s*([^\r\n]+)", text, re.I)
    if not match:
        return None
    value = re.split(r"\s{3,}|\s+(?:POD|CNP|CUI|Furnizor|Operator|Telefon|E-mail|Email|Adresă|Adresa)\s*[:：-]", match.group(1), maxsplit=1, flags=re.I)[0]
    value = re.sub(r"\s+", " ", value).strip(" .,:;-")
    return value[:160] or None


def _fallback_text_fields(text: str, doc_type: str) -> dict:
    # Extract only explicitly labelled values from selectable PDF text. This
    # intentionally leaves ambiguous name/address fields empty rather than guessing.
    fields = {}
    labels = {
        "client_name": r"(?:titular(?:ul)?(?:\s+(?:contractului|locului\s+de\s+consum))?|nume(?:le)?(?:\s+(?:clientului|beneficiarului|titularului))?|beneficiar)",
        "consumption_address": r"(?:adresa\s+locului\s+de\s+consum|locul\s+de\s+consum|adresa\s+de\s+consum)",
        "hq_address": r"(?:domiciliu(?:l)?(?:\s+din\s+actul\s+de\s+identitate)?|adresa\s+de\s+domiciliu|domiciliat(?:ă)?\s+în)",
        "pod": r"(?:POD|CLC|codul?\s+punctului\s+de\s+consum)",
        "supplier": r"(?:furnizor(?:ul)?\s+(?:de\s+)?energie)",
        "operator": r"(?:operator(?:ul)?\s+de\s+distribuție|operator(?:ul)?\s+de\s+distributie)",
        "owner_name": r"(?:proprietar(?:ul)?(?:\s+tabular)?|titular(?:ul)?\s+dreptului\s+de\s+proprietate)",
        "cf_nr": r"(?:carte\s+funciară(?:\s+nr\.?)?|număr(?:ul)?\s+CF)",
        "cadastral_nr": r"(?:număr(?:ul)?\s+cadastral|nr\.\s+cadastral)",
        "county": r"(?:județ|judet)",
        "phone": r"(?:telefon|tel\.?)",
        "email": r"(?:e-mail|email)",
    }

    for key, pattern in labels.items():
        value = _labeled_value(text, pattern)
        if value:
            fields[key] = value

    if doc_type == "ci":
        cnp = re.search(r"(?:CNP|cod\s+numeric\s+personal)\s*[:：-]?\s*(\d{13})(?!\d)", text, re.I)
        series = re.search(r"(?:seria|serie)\s*[:：-]?\s*([A-Z]{2})\b", text, re.I)
        number = re.search(r"(?:nr\.?|număr(?:ul)?)\s*(?:CI|carte\s+de\s+identitate)?\s*[:：-]?\s*(\d{6})\b", text, re.I)
        if cnp:
            fields["cnp"] = cnp.group(1)
        if series:
            fields["id_series"] = series.group(1).upper()
        if number:
            fields["id_number"] = number.group(1)
        surname = _labeled_value(text, r"(?:nume(?:le)?(?:\s+de\s+familie)?)")
        given_name = _labeled_value(text, r"(?:prenume(?:le)?)")
        if surname and given_name:
            fields.setdefault("client_name", f"{surname} {given_name}")
        elif surname:
            fields.setdefault("client_name", surname)
    elif doc_type == "factura":
        cnp = re.search(r"(?:CNP|CUI|cod\s+numeric\s+personal|cod\s+unic\s+de\s+înregistrare)\s*[:：-]?\s*(\d{8,13})\b", text, re.I)
        if cnp:
            fields["cnp"] = cnp.group(1)
        approved_power = re.search(
            r"(?:putere\s+aprobată|putere\s+aprobata|puterea\s+aprobată|puterea\s+aprobata|putere\s+contractată|putere\s+contractata)\s*[:：-]?\s*(\d+(?:[.,]\d+)?)\s*(?:kW)?\b",
            text, re.I,
        )
        if approved_power:
            fields["bransament_kw"] = float(approved_power.group(1).replace(",", "."))

    operator_text = text.lower()
    for key, needles in {
        "DEER — Transilvania Nord": ("distribuție energie electrică românia - zona transilvania nord", "deer transilvania nord"),
        "DEER — Transilvania Sud": ("deer transilvania sud",),
        "DEER — Muntenia Nord": ("deer muntenia nord",),
        "Delgaz Grid": ("delgaz grid",),
        "Distribuție Energie Oltenia": ("distribuție energie oltenia", "distributie energie oltenia"),
        "Rețele Electrice România": ("rețele electrice", "retele electrice"),
    }.items():
        if any(needle in operator_text for needle in needles):
            fields.setdefault("operator", key)
            break
    if doc_type == "factura" and fields.get("consumption_address"):
        fields.setdefault("address", fields["consumption_address"])
    if not fields:
        raise ValueError("PDF-ul conține text, dar nu am găsit câmpuri cu etichete suficient de clare. Verifică documentul și completează manual.")
    fields["doc_type"] = {"ci": "Carte de identitate", "factura": "Factură energie", "cf": "Carte funciară"}.get(doc_type, "Document PDF")
    fields["summary"] = "Date extrase local din etichetele vizibile ale PDF-ului. Câmpurile neidentificate nu au fost deduse."
    fields["_engine"] = "Extragere locală PDF"
    return fields


async def extract_pdf(content: bytes, mime: str, doc_type: str = "auto", use_ai: bool = True) -> dict:
    # For PDFs, fall back to explicitly labelled selectable text when the AI
    # service fails. Never infer missing values from surrounding context.
    if use_ai:
        try:
            return await extract_gpt(content, mime, doc_type)
        except Exception:
            if mime != "application/pdf":
                raise
    elif mime != "application/pdf":
        raise ValueError("Citirea imaginilor scanate necesită funcția AI activă.")

    import pymupdf
    doc = pymupdf.open(stream=content, filetype="pdf")
    text = "\n".join(page.get_text("text") for page in list(doc)[:12]).strip()
    if not text:
        raise ValueError("PDF-ul nu conține text selectabil. Pentru citirea unui scan este necesară funcția AI.")
    return _fallback_text_fields(text, doc_type)
