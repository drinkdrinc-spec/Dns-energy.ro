from io import BytesIO

from pypdf import PdfReader
from PIL import Image

import atr_doc as ATR


def test_site_plan_is_omitted_until_user_adds_geometry():
    assert ATR.render_atr_site_plan({"site_plan": {"markers": [], "route": [], "boundary": []}}) == b""


def test_site_plan_pdf_contains_user_markers_and_is_landscape():
    record = {
        "client_name": "Popescu Ion",
        "address": "Strada Exemplu 1",
        "pod": "RO001E0000000000000000",
        "site_plan": {
            "markers": [
                {"id": "m1", "type": "CEF", "label": "Panouri acoperiș", "x": 200, "y": 180},
                {"id": "m2", "type": "BESS", "label": "Baterie", "x": 690, "y": 360},
                {"id": "m3", "type": "TEG", "label": "Tablou general", "x": 500, "y": 470},
            ],
            "route": [{"x": 200, "y": 180}, {"x": 500, "y": 470}, {"x": 690, "y": 360}],
            "boundary": [{"x": 80, "y": 60}, {"x": 900, "y": 80}, {"x": 860, "y": 560}, {"x": 110, "y": 540}],
        },
    }
    data = ATR.render_atr_site_plan(record, {"name": "Popescu Ion"})
    reader = PdfReader(BytesIO(data))
    assert len(reader.pages) == 1
    assert float(reader.pages[0].mediabox.width) > float(reader.pages[0].mediabox.height)
    extracted = reader.pages[0].extract_text()
    assert "Panouri acoperiș" in extracted
    assert "Baterie" in extracted
    assert "fără scară" in extracted


def test_site_plan_pdf_uses_uploaded_plan_image_as_background():
    image = Image.new("RGB", (64, 40), "#dce8f5")
    image_buffer = BytesIO()
    image.save(image_buffer, format="PNG")
    record = {"site_plan": {"markers": [{"id": "m1", "type": "CEF", "label": "CEF", "x": 400, "y": 250}]}}
    data = ATR.render_atr_site_plan(record, {}, (image_buffer.getvalue(), "image/png"))
    page = PdfReader(BytesIO(data)).pages[0]
    assert len(page.images) == 1

