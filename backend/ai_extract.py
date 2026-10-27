import os
import json
import re
import uuid
import tempfile
from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType, TextDelta, StreamDone

OPERATORS = ["DEER — Transilvania Nord", "DEER — Transilvania Sud", "DEER — Muntenia Nord", "Delgaz Grid",
             "Distribuție Energie Oltenia", "Rețele Electrice România", "Alt operator"]

PROMPT = f"""Ești expert în dosare de racordare prosumatori din România. Extrage datele din documentul atașat și răspunde DOAR cu un obiect JSON valid, fără text suplimentar, cu cheile:
client_name (nume beneficiar), cnp (CNP sau CUI), address (adresa loc de consum completă), county (județ), pod (cod loc de consum / POD), phone, email,
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


async def extract_pdf(content: bytes, mime: str) -> dict:
    suffix = ".pdf" if "pdf" in mime else ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(content)
        path = f.name
    try:
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"extract-{uuid.uuid4()}",
                       system_message="Extragi date structurate din documente tehnice românești. Răspunzi doar JSON.") \
            .with_model("gemini", "gemini-3-flash-preview")
        out = ""
        async for ev in chat.stream_message(UserMessage(text=PROMPT, file_contents=[FileContentWithMimeType(file_path=path, mime_type=mime)])):
            if isinstance(ev, TextDelta):
                out += ev.content
            elif isinstance(ev, StreamDone):
                break
        return _parse(out)
    finally:
        os.unlink(path)
