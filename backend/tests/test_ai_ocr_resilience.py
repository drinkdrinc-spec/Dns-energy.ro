import sys
import types

import ai_extract


def test_local_ocr_keeps_readable_pages_when_one_page_fails(monkeypatch):
    class FakeDocument:
        def __init__(self):
            self.closed = False

        def __len__(self):
            return 3

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

    assert result == "page 1 text\n\npage 3 text"
    assert [call["pages"] for call in calls] == [[0], [1], [2]]
    assert all(call["ocr_dpi"] == ai_extract.OCR_DPI for call in calls)
    assert document.closed
