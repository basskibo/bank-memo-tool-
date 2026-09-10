from src.models.field_display import (
    emphasize_bracket_spans,
    enrich_field_unit,
    format_field_display_value,
    infer_document_currency,
)
from src.models.schemas import ExtractedField, IngestedDocument, IngestedPage


def _field(**kwargs) -> ExtractedField:
    defaults = dict(
        field_name="total_assets",
        value="96,500,000",
        unit=None,
        source_document_id="doc1",
        source_page=1,
        source_snippet="Total Assets | 96,500,000",
        confidence=0.9,
        status="confirmed",
    )
    defaults.update(kwargs)
    return ExtractedField(**defaults)


def test_format_with_unit():
    f = _field(unit="EGP")
    assert format_field_display_value(f) == "EGP 96,500,000"


def test_enrich_from_document_header():
    doc = IngestedDocument(
        document_id="d1",
        source_file="x.pdf",
        document_type="financial_statement",
        quality_ok=True,
        pages=[IngestedPage(page_number=1, text="All amounts in EGP unless otherwise stated.\nTotal Assets 96,500,000", source_file="x.pdf")],
    )
    enriched = enrich_field_unit(_field(), doc)
    assert enriched.unit == "EGP"
    assert format_field_display_value(enriched) == "EGP 96,500,000"


def test_format_infers_from_document_when_no_unit():
    doc = IngestedDocument(
        document_id="d1",
        source_file="x.pdf",
        document_type="financial_statement",
        quality_ok=True,
        pages=[IngestedPage(page_number=1, text="All amounts in EGP unless otherwise stated.", source_file="x.pdf")],
    )
    assert format_field_display_value(_field(), doc) == "EGP 96,500,000"

    doc = IngestedDocument(
        document_id="d1",
        source_file="x.pdf",
        document_type="financial_statement",
        quality_ok=True,
        pages=[IngestedPage(page_number=1, text="(All figures in USD unless otherwise stated.)", source_file="x.pdf")],
    )
    assert infer_document_currency(doc) == "USD"


def test_emphasize_bracket_spans_bold_italic():
    text = (
        'p.1 — "Misr Pharma" · [citation_validator] snippet not found verbatim '
        'on cited page [PAGE 1]'
    )
    out = emphasize_bracket_spans(text)
    assert "<strong><em>[citation_validator]</em></strong>" in out
    assert "<strong><em>[PAGE 1]</em></strong>" in out
    assert "Misr Pharma" in out
    assert "***" not in out


def test_emphasize_bracket_spans_escapes_other_markdown():
    out = emphasize_bracket_spans("note *not italic* [auto: below confidence threshold]")
    assert "*not italic*" in out
    assert "***" not in out
    assert "<strong><em>[auto: below confidence threshold]</em></strong>" in out
