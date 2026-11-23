import asyncio
import sys
import threading
import types

import ai_extract
import pytest


def test_local_ocr_keeps_readable_pages_when_one_page_fails(monkeypatch):
    class FakeDocument:
        def __init__(self):
            self.closed = False

        def __len__(self):
            return 7

        def close(self):
            self.closed = True

    document = FakeDocument()
    fake_pymupdf = types.ModuleType("pymupdf")
    fake_pymupdf.open = lambda **kwargs: document

    calls = []

    def to_markdown(_doc, **kwargs):
        calls.append(kwargs)
        page = kwargs["pages"][0]
        if page == 1:
            raise RuntimeError("bad scan page")
        return f"page {page + 1} text"

    fake_llm = types.ModuleType("pymupdf4llm")
    fake_llm.to_markdown = to_markdown
    fake_ocr_package = types.ModuleType("pymupdf4llm.ocr")
    fake_ocr_package.rapidocr_api = types.SimpleNamespace(exec_ocr=object())
    fake_llm.__path__ = []
    monkeypatch.setitem(sys.modules, "pymupdf", fake_pymupdf)
    monkeypatch.setitem(sys.modules, "pymupdf4llm", fake_llm)
    monkeypatch.setitem(sys.modules, "pymupdf4llm.ocr", fake_ocr_package)

    result = ai_extract._ocr_document_text(b"pdf", "application/pdf")

    assert result == "page 1 text\n\npage 3 text\n\npage 4 text\n\npage 5 text\n\npage 6 text"
    assert [call["pages"] for call in calls] == [[0], [1], [2], [3], [4], [5]]
    assert all(call["ocr_dpi"] == ai_extract.OCR_DPI for call in calls)
    assert document.closed


def test_timed_out_ocr_keeps_slot_until_background_thread_finishes(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    processed = []

    def fake_ocr(content, _mime):
        processed.append(content)
        if content == b"first":
            started.set()
            release.wait(timeout=2)
        return content.decode()

    monkeypatch.setattr(ai_extract, "_ocr_document_text", fake_ocr)
    monkeypatch.setattr(ai_extract, "LOCAL_OCR_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(ai_extract, "LOCAL_OCR_QUEUE_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(ai_extract, "_LOCAL_OCR_LOCK", asyncio.Lock())

    async def scenario():
        with pytest.raises(ValueError, match="durează prea mult"):
            await ai_extract._run_local_ocr(b"first", "application/pdf")
        assert await asyncio.to_thread(started.wait, 1)
        with pytest.raises(ValueError, match="altă citire"):
            await ai_extract._run_local_ocr(b"second", "application/pdf")
        release.set()
        await asyncio.sleep(0.05)
        # Once the blocked worker releases the slot, allow normal thread
        # startup time; the 10 ms timeout above is only for the lock behavior.
        monkeypatch.setattr(ai_extract, "LOCAL_OCR_TIMEOUT_SECONDS", 1.0)
        assert await ai_extract._run_local_ocr(b"second", "application/pdf") == "second"

    asyncio.run(scenario())
    assert processed == [b"first", b"second"]
