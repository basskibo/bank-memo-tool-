"""
Citation Validator — SPEC.md 3.1.3

Namerno BEZ LLM poziva: ovo je deterministička provera da li source_snippet zaista postoji na
navedenoj strani izvornog dokumenta. Ovo je najvažniji guardrail u celom POC-u (SPEC.md sekcija 5
— "citation integrity" je 100%-zahtev čak i u dijagnostičkom merenju).
"""
import re
from typing import Callable

from src.models.schemas import ExtractedField, IngestedDocument

_PAGE_MARKER = re.compile(r"\[PAGE\s+\d+\]", re.IGNORECASE)
_ONLY_PAGE_MARKER = re.compile(r"^\[PAGE\s+\d+\]$", re.IGNORECASE)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _strip_page_markers(snippet: str) -> str:
    return _PAGE_MARKER.sub(" ", snippet).strip()


def _snippet_on_page(snippet: str, page_text: str) -> bool:
    if not snippet:
        return False
    return _normalize(snippet) in _normalize(page_text)


def _find_value_span(value: str, page_text: str) -> re.Match[str] | None:
    compact = value.strip()
    if not compact:
        return None
    match = re.search(re.escape(compact), page_text, flags=re.IGNORECASE)
    if match:
        return match
    # Allow extra whitespace in the page (PDF extraction often inserts newlines).
    flexible = re.sub(r"\\ ", r"\\s+", re.escape(compact))
    return re.search(flexible, page_text, flags=re.IGNORECASE)


def _recover_snippet_from_page(value: str, page_text: str, *, pad: int = 48) -> str | None:
    match = _find_value_span(value, page_text)
    if match is None:
        return None
    start = max(0, match.start() - pad)
    end = min(len(page_text), match.end() + pad)
    snippet = re.sub(r"\s+", " ", page_text[start:end].strip())
    return snippet or None


def _append_note(field: ExtractedField, note: str) -> None:
    field.validation_note = (field.validation_note + " " if field.validation_note else "") + note


def validate_citations(
    fields: list[ExtractedField],
    document: IngestedDocument,
    on_field: Callable[[str, int, int], None] | None = None,
) -> list[ExtractedField]:
    pages_by_number = {p.page_number: p.text for p in document.pages}
    validated: list[ExtractedField] = []
    total = len(fields)

    for i, field in enumerate(fields, start=1):
        if on_field:
            on_field(field.field_name, i, total)
        page_text = pages_by_number.get(field.source_page)

        if not field.value.strip():
            field.status = "needs_review"
            _append_note(
                field,
                "[citation_validator] value is empty — cannot be confirmed regardless of citation",
            )
        elif page_text is None:
            field.status = "needs_review"
            field.validation_note = (
                f"[citation_validator] source_page {field.source_page} does not exist in document"
            )
        else:
            cleaned = _strip_page_markers(field.source_snippet)
            if cleaned != field.source_snippet.strip():
                field.source_snippet = cleaned

            marker_only = (not field.source_snippet.strip()) or bool(
                _ONLY_PAGE_MARKER.fullmatch(field.source_snippet.strip())
            )
            if marker_only or not _snippet_on_page(field.source_snippet, page_text):
                recovered = _recover_snippet_from_page(field.value, page_text)
                if recovered:
                    field.source_snippet = recovered
                else:
                    field.status = "needs_review"
                    _append_note(
                        field,
                        "[citation_validator] snippet not found verbatim on cited page — "
                        "possible hallucinated citation, do not treat as confirmed",
                    )

        validated.append(field)

    return validated
