from src.rag.display import chunk_view, parse_policy_text, pretty_doc_label
from src.rag.schemas import RetrievedChunk


def test_parse_sme_tenor_chunk():
    text = (
        "# SME Lending Standards (SYNTHETIC — not real SCB policy) ## Tenor limits "
        "SME working-capital facilities are granted for a maximum tenor of 36 months, "
        "renewable on annual review."
    )
    parsed = parse_policy_text(text)
    assert parsed["title"] == "SME Lending Standards"
    assert parsed["synthetic"] is True
    assert parsed["blocks"][0]["section"] == "Tenor limits"
    assert parsed["blocks"][0]["body"].startswith("SME working-capital")
    assert "#" not in parsed["blocks"][0]["body"]
    assert "SYNTHETIC" not in parsed["blocks"][0]["body"]


def test_parse_arabic_heading():
    text = (
        "# معايير إقراض الشركات الصغيرة والمتوسطة "
        "(وثيقة اصطناعية — ليست سياسة حقيقية للبنك) ## مدة التسهيل "
        "تُمنح تسهيلات رأس المال العامل للشركات الصغيرة والمتوسطة لمدة أقصاها 36 شهراً."
    )
    parsed = parse_policy_text(text)
    assert "اصطناعية" not in parsed["title"]
    assert parsed["synthetic"] is True
    assert parsed["blocks"][0]["section"] == "مدة التسهيل"
    assert parsed["blocks"][0]["body"].startswith("تُمنح")


def test_parse_parenthetical_h2():
    text = (
        "# Prohibited and Restricted Activities (SYNTHETIC — not real SCB policy) "
        "## Restricted (require Head-Office Environmental & Social review) "
        "Credit to oil & gas exploration is restricted."
    )
    parsed = parse_policy_text(text)
    assert parsed["blocks"][0]["section"].startswith("Restricted")
    assert parsed["blocks"][0]["body"].startswith("Credit to oil")


def test_real_corpus_first_chunks_have_no_hashes():
    from src.rag.corpus import build_chunks

    for chunk in build_chunks():
        if not chunk.chunk_id.endswith("#0"):
            continue
        parsed = parse_policy_text(chunk.text)
        assert parsed["title"]
        assert parsed["synthetic"] is True
        assert parsed["blocks"][0]["section"]
        assert parsed["blocks"][0]["body"]
        blob = parsed["title"] + parsed["blocks"][0]["section"] + parsed["blocks"][0]["body"]
        assert "#" not in blob
        assert "SYNTHETIC" not in blob
        assert "اصطناعية" not in parsed["title"]


def test_chunk_view_citation_is_compact():
    hit = RetrievedChunk(
        doc_id="en_sme_lending",
        chunk_id="en_sme_lending#0",
        lang="en",
        text="# SME Lending Standards (SYNTHETIC — not real SCB policy) ## Tenor limits SME x.",
        score=0.52,
    )
    view = chunk_view(hit)
    assert view["title"] == "SME Lending Standards"
    assert view["passage"] == "0"
    assert view["score_pct"] == 52
    assert view["rtl"] is False
    assert pretty_doc_label("en_sme_lending") == "sme lending"
