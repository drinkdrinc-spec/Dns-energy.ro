import io

from pypdf import PdfReader

import anre_doc


def test_anre_annex_10_does_not_claim_or_preselect_consent():
    pdf = anre_doc.render("decl_10", {"company": {"name": "DNS Energy"}, "staff": []})
    text = " ".join(
        (page.extract_text() or "")
        for page in PdfReader(io.BytesIO(pdf)).pages
    ).casefold()

    assert "declarație de consimțământ" in text
    assert "numele și prenumele persoanei vizate" in text
    assert "bifează această căsuță cu x" in text
    assert "nu exprimă și nu bifează consimțământul în numele persoanei" in text
    assert "îmi exprim consimțământul" not in text
    assert "[x]" not in text
