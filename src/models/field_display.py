"""Format extracted field values for display (currency, units)."""
from __future__ import annotations

import html
import re

from src.models.schemas import ExtractedField, IngestedDocument, MemoSection

_FOOTNOTE_TAG = re.compile(r"\[(\w+)\]")
_BRACKET_SPAN = re.compile(r"\[([^\[\]]+)\]")

MONETARY_FIELDS = frozenset({
    "total_assets",
    "total_liabilities",
    "total_equity",
    "annual_revenue",
    "net_income",
    "requested_facility_amount",
})

_CURRENCY_IN_TEXT = re.compile(
    r"\b(EGP|USD|EUR|GBP|LE|L\.E\.|Egyptian Pound?s?)\b",
    re.IGNORECASE,
)
_VALUE_HAS_CURRENCY = re.compile(r"\b(EGP|USD|EUR|GBP|LE|L\.E\.)\b", re.IGNORECASE)
_DOC_CURRENCY_HINT = re.compile(
    r"(?:All amounts in|All figures in|Amount \()"
    r"[\s\w—\-]*?(EGP|Egyptian Pounds?|USD|EUR|GBP)",
    re.IGNORECASE,
)


def _normalize_currency(raw: str) -> str:
    upper = raw.strip().upper().rstrip(".")
    if upper in {"LE", "L.E", "EGYPTIAN POUND", "EGYPTIAN POUNDS"}:
        return "EGP"
    return upper


def emphasize_bracket_spans(text: str) -> str:
    """Keep `[...]` visible but bold+italic.

    GFM treats `[label]` as a link, so `***[label]***` leaks literal asterisks in
    `st.caption`. HTML emphasis avoids that; callers must pass unsafe_allow_html=True.
    """
    if not text:
        return ""
    parts: list[str] = []
    last = 0
    for match in _BRACKET_SPAN.finditer(text):
        parts.append(html.escape(text[last:match.start()]))
        inner = html.escape(match.group(1))
        parts.append(f"<strong><em>[{inner}]</em></strong>")
        last = match.end()
    parts.append(html.escape(text[last:]))
    return "".join(parts)


def infer_currency_from_text(text: str) -> str | None:
    if not text:
        return None
    match = _DOC_CURRENCY_HINT.search(text)
    if match:
        return _normalize_currency(match.group(1))
    match = _CURRENCY_IN_TEXT.search(text)
    if match:
        return _normalize_currency(match.group(1))
    return None


def infer_document_currency(document: IngestedDocument) -> str | None:
    return infer_currency_from_text(document.full_text()[:4000])


def enrich_field_unit(field: ExtractedField, document: IngestedDocument | None = None) -> ExtractedField:
    """Fill missing `unit` for monetary fields from snippet or document header."""
    if field.field_name not in MONETARY_FIELDS or field.unit:
        return field
    unit = infer_currency_from_text(field.source_snippet)
    if not unit and document is not None:
        unit = infer_document_currency(document)
    if unit:
        return field.model_copy(update={"unit": unit})
    return field


def format_field_display_value(
    field: ExtractedField,
    document: IngestedDocument | None = None,
) -> str:
    value = field.value.strip()
    if field.field_name not in MONETARY_FIELDS:
        return value
    if _VALUE_HAS_CURRENCY.search(value):
        return value
    unit = field.unit or infer_currency_from_text(field.source_snippet)
    if not unit and document is not None:
        unit = infer_document_currency(document)
    if unit:
        return f"{_normalize_currency(unit)} {value}"
    return value


def build_memo_footnotes(
    sections: list[MemoSection],
    confirmed_fields: list[ExtractedField],
    document: IngestedDocument | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Replace inline `[field_name]` citation markers with numbered footnote placeholders
    (`{{1}}`, `{{2}}`, ...) and build a single consolidated source list for the whole memo.

    Kept separate from the guardrail check in narrative_synthesizer.py on purpose: that check
    validates the ORIGINAL `[field_name]`-tagged text, this only reformats it for display. The
    placeholder token (not raw HTML/XML) lets each renderer (Streamlit vs ReportLab) apply its
    own superscript syntax — see app.py / reports/live_report.py.
    """
    fields_by_name = {f.field_name: f for f in confirmed_fields}
    field_to_number: dict[str, int] = {}
    sources: list[dict] = []

    def repl(match: re.Match) -> str:
        name = match.group(1)
        if name not in field_to_number:
            field_to_number[name] = len(field_to_number) + 1
            f = fields_by_name.get(name)
            sources.append({
                "number": field_to_number[name],
                "field_name": name,
                "value": format_field_display_value(f, document) if f else name,
                "page": f.source_page if f else None,
                "snippet": f.source_snippet if f else "",
            })
        return f"{{{{{field_to_number[name]}}}}}"

    processed_sections = [
        {"title": s.title, "text": _FOOTNOTE_TAG.sub(repl, s.text)} for s in sections
    ]
    return processed_sections, sources
