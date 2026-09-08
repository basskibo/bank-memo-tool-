"""
Testovi za Citation Validator (SPEC.md 3.1.3) — posebno regresija za bag nađen uživo u portalu
(2026-09-08): polje sa praznim `value` je prolazilo kao "confirmed" ako je `source_snippet`
tehnički postojao na strani, iako sama vrednost ne nosi nikakvu informaciju.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents.citation_validator import validate_citations
from src.models.schemas import ExtractedField, IngestedDocument, IngestedPage


def _doc(text: str = "Company Name Ltd. Total Assets 1,000,000") -> IngestedDocument:
    return IngestedDocument(
        document_id="doc-1",
        source_file="test.pdf",
        document_type="financial_statement",
        pages=[IngestedPage(page_number=1, text=text, source_file="test.pdf")],
        quality_ok=True,
    )


def _field(**overrides) -> ExtractedField:
    base = dict(
        field_name="company_name",
        value="Company Name Ltd.",
        unit=None,
        source_document_id="doc-1",
        source_page=1,
        source_snippet="Company Name Ltd.",
        confidence=1.0,
        status="confirmed",
        validation_note=None,
    )
    base.update(overrides)
    return ExtractedField(**base)


def test_empty_value_is_never_confirmed_even_with_valid_snippet():
    field = _field(value="", source_snippet="Company Name Ltd.")
    result = validate_citations([field], _doc())[0]
    assert result.status == "needs_review"
    assert "empty" in (result.validation_note or "").lower()


def test_whitespace_only_value_is_never_confirmed():
    field = _field(value="   ", source_snippet="Company Name Ltd.")
    result = validate_citations([field], _doc())[0]
    assert result.status == "needs_review"


def test_valid_value_and_snippet_stays_confirmed():
    field = _field(value="Company Name Ltd.", source_snippet="Company Name Ltd.")
    result = validate_citations([field], _doc())[0]
    assert result.status == "confirmed"


def test_snippet_not_found_still_flags_needs_review():
    field = _field(value="Company Name Ltd.", source_snippet="Nonexistent Snippet")
    result = validate_citations([field], _doc())[0]
    assert result.status == "needs_review"
    assert "hallucinated" in (result.validation_note or "").lower()
