"""
Citation Validator — SPEC.md 3.1.3

Namerno BEZ LLM poziva: ovo je deterministička provera da li source_snippet zaista postoji na
navedenoj strani izvornog dokumenta. Ovo je najvažniji guardrail u celom POC-u (SPEC.md sekcija 5
— "citation integrity" je 100%-zahtev čak i u dijagnostičkom merenju).
"""
import re

from src.models.schemas import ExtractedField, IngestedDocument


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def validate_citations(
    fields: list[ExtractedField], document: IngestedDocument
) -> list[ExtractedField]:
    pages_by_number = {p.page_number: p.text for p in document.pages}
    validated: list[ExtractedField] = []

    for field in fields:
        page_text = pages_by_number.get(field.source_page)

        if page_text is None:
            field.status = "needs_review"
            field.validation_note = (
                f"[citation_validator] source_page {field.source_page} does not exist in document"
            )
        elif _normalize(field.source_snippet) not in _normalize(page_text):
            field.status = "needs_review"
            field.validation_note = (
                (field.validation_note + " " if field.validation_note else "")
                + "[citation_validator] snippet not found verbatim on cited page — "
                "possible hallucinated citation, do not treat as confirmed"
            )
        # if snippet is found and field was already confirmed, leave as-is

        validated.append(field)

    return validated
