"""
Financial Wizard — SPEC.md 3.1.2

Izvlači fiksan skup polja (models.schemas.POC_FIELD_NAMES) iz jednog IngestedDocument-a.
Pravilo iz SPEC-a: ne piše vrednost bez izvora, ne nagađa kod nejasnoće/konflikta.

Implementaciona napomena (ne menja SPEC contract, samo KAKO se poziva LLM):
za mlx/api se polja vuku u JEDNOM JSON nizu (10× manje prefilla dokumenta). Ollama i dalje
ide po jednom polju jer su mali modeli tu nepouzdani. `POC_EXTRACT_BATCH=0` forsira stari režim.
"""
import re
import warnings
from typing import Callable

from pydantic import ValidationError

from src.config import extract_batch_enabled
from src.llm_client import complete_json
from src.models.field_display import enrich_field_unit
from src.models.schemas import CONFIDENCE_THRESHOLD, POC_FIELD_NAMES, ExtractedField, IngestedDocument

MONETARY_FIELDS = frozenset({
    "total_assets", "total_liabilities", "total_equity",
    "annual_revenue", "net_income", "requested_facility_amount",
})
# Free-text fields — a description, possibly listing SEVERAL facilities/items with amounts.
# Small models tend to collapse these to one bare number; the prompt has to push back.
NARRATIVE_FIELDS = frozenset({"existing_bank_facilities", "collateral_offered"})
# Loan-application-only (prompt rule 7). Skip the LLM call on financial statements.
LOAN_ONLY_FIELDS = frozenset({"requested_facility_amount", "collateral_offered"})
# Fields a clean financial statement / loan application really should contain — if one of these
# comes back empty from a local model, retry it once with a blunter prompt before giving up.
FS_CORE_FIELDS = frozenset({
    "company_name", "reporting_period", "total_assets", "total_liabilities", "total_equity",
    "annual_revenue", "net_income", "existing_bank_facilities",
})
LOAN_CORE_FIELDS = frozenset({
    "company_name", "existing_bank_facilities", "requested_facility_amount", "collateral_offered",
})
PER_FIELD_MAX_TOKENS = 640   # noisy OCR snippets were truncating a 384-token response mid-string
NARRATIVE_MAX_TOKENS = 900   # free-text fields need room for a multi-facility description
BATCH_MAX_TOKENS = 2048

_PAGE_MARKER = re.compile(r"\[PAGE\s+\d+\]", re.IGNORECASE)


def _sanitize_source_snippet(snippet: object) -> str:
    """Drop `[PAGE n]` wrappers the model copies from full_text(); keep real page-body text."""
    cleaned = _PAGE_MARKER.sub(" ", str(snippet)).strip()
    return cleaned


FIELD_SYSTEM_PROMPT = """You are the Financial Wizard capability of a credit memo agent.

Your job: extract ONE specific requested field from a bank document. If you extract a value, you
must cite the EXACT page number and an EXACT text snippet copied verbatim from that page that
supports it.

Rules (do not break these):
1. If the requested field is NOT genuinely present anywhere in the document, output exactly: {}
   Never invent a placeholder or estimated value.
2. `source_snippet` must be text copied verbatim from the PAGE BODY you cite — not a paraphrase.
   Never use the `[PAGE n]` marker itself as `source_snippet`. That marker is only a delimiter
   in this prompt; it does not appear in the document. Copy ONE short line (at most ~120
   characters) that contains the extracted value (e.g. "Legal name Misr Pharma Distribution
   S.A.E.") — do not copy a whole paragraph.
3. If the value is ambiguous, contradicted elsewhere in the document, missing required context
   (e.g. unclear currency/unit), or stated only as an approximation, set status="needs_review"
   and confidence below 0.7, and explain why in `validation_note`.
4. If the value is stated clearly and unambiguously, set status="confirmed" and confidence >= 0.7.
5. Output ONLY a single raw JSON object as the top-level value — NOT a list, NOT wrapped in
   another key. Either exactly `{}` (field not found) or:
   {"field_name": str, "value": str, "unit": str|null, "source_page": int,
    "source_snippet": str, "confidence": float, "status": "confirmed"|"needs_review",
    "validation_note": str|null}
6. For monetary amounts (balances, revenue, income, facility amounts): put ONLY the numeric
   amount in `value` (e.g. "96,500,000") and the currency code in `unit` (e.g. "EGP", "USD")
   exactly as stated in the document header or line item. If currency is not clear, set
   status="needs_review" and explain in `validation_note` — do not guess.
7. `requested_facility_amount` and `collateral_offered` describe a NEW facility being formally
   requested for approval — they only apply to credit/loan APPLICATION documents. A financial
   statement's "Bank Borrowings and Credit Facilities" note describes EXISTING, already-granted
   facilities, even when it states a facility's approved limit (e.g. "Project finance facility of
   EGP 40,000,000... drawn EGP 28,500,000"). Do NOT extract `requested_facility_amount` from such
   a note just because an amount appears there — that amount belongs under
   `existing_bank_facilities`, not a new request. Only extract these two fields when the document
   itself is an application/request for a new facility.
"""

BATCH_SYSTEM_PROMPT = """You are the Financial Wizard capability of a credit memo agent.

Extract EVERY listed field from a bank document in ONE response. Same citation rules as a
single-field extract.

Rules:
1. Output ONLY a JSON array as the top-level value. Each element is either omitted (field not
   present) or:
   {"field_name": str, "value": str, "unit": str|null, "source_page": int,
    "source_snippet": str, "confidence": float, "status": "confirmed"|"needs_review",
    "validation_note": str|null}
   Do not wrap the array in another object. Use [] if nothing is present.
2. `source_snippet` must be verbatim PAGE BODY text — never the `[PAGE n]` delimiter.
3. Monetary amounts: numeric `value` (e.g. "96,500,000") and currency in `unit`.
4. `requested_facility_amount` and `collateral_offered` only belong on a loan/credit APPLICATION.
   Do not fill them from an existing-facilities note on a financial statement.
5. Do not invent values. Prefer needs_review over guessing.
"""


def _parse_one_field(raw: dict, field_name: str, document_id: str) -> ExtractedField | None:
    if not raw:
        return None  # model correctly reported "not present" as {}
    if isinstance(raw, list):
        # Odbrana: ako model ipak vrati niz sa jednim elementom umesto golog objekta.
        raw = raw[0] if raw else {}
        if not raw:
            return None
    try:
        field = ExtractedField(
            field_name=raw.get("field_name", field_name),
            value=str(raw["value"]),
            unit=raw.get("unit"),
            source_document_id=document_id,
            source_page=int(raw["source_page"]),
            source_snippet=_sanitize_source_snippet(raw["source_snippet"]),
            confidence=float(raw["confidence"]),
            status=raw["status"],
            validation_note=raw.get("validation_note"),
        )
    except (KeyError, ValueError, TypeError, ValidationError) as exc:
        warnings.warn(f"[financial_wizard] preskočeno polje '{field_name}' — malformisan odgovor "
                       f"modela: {raw!r} ({exc})")
        return None

    # Guardrail: enforce confidence threshold regardless of what the model claims as status
    if field.confidence < CONFIDENCE_THRESHOLD and field.status == "confirmed":
        field.status = "needs_review"
        field.validation_note = (field.validation_note or "") + " [auto: below confidence threshold]"
    return field


def _target_field_names(document: IngestedDocument) -> list[str]:
    if document.document_type == "financial_statement":
        return [n for n in POC_FIELD_NAMES if n not in LOAN_ONLY_FIELDS]
    return list(POC_FIELD_NAMES)


_NARRATIVE_HINT = {
    "existing_bank_facilities": (
        "This is a FREE-TEXT field, NOT a single number. Copy the full bank-facilities / banking-"
        "relationships text: EVERY facility, its bank, its amount and any utilisation %. If the "
        "document lists two or three facilities, `value` must mention all of them. Do not reduce "
        "it to one number.\n"
    ),
    "collateral_offered": (
        "This is a FREE-TEXT description of security offered (mortgages, receivables assignment, "
        "pledges, guarantees). Copy the whole description into `value`. NEVER put a bare number "
        "here — a valuation figure inside the text is fine, but the value is the description.\n"
    ),
}


def _user_prompt_one(document: IngestedDocument, field_name: str, *, blunt: bool = False) -> str:
    hint = ""
    if field_name in NARRATIVE_FIELDS:
        hint = _NARRATIVE_HINT[field_name]
    elif field_name in MONETARY_FIELDS:
        hint = "This is a monetary amount — currency into `unit`, the number into `value`.\n"
    if blunt:
        hint += (
            f"You previously returned nothing for `{field_name}`. It almost certainly IS in this "
            "document — read every page again and extract it. Only return {} if you are certain "
            "it is genuinely absent.\n"
        )
    return (
        f"Field to extract: {field_name}\n"
        f"Document type (classified during ingestion): {document.document_type}\n"
        + hint
        + f"\nDocument (pages delimited by [PAGE n] markers — do NOT copy those markers):\n\n{document.full_text()}"
    )


def _user_prompt_batch(document: IngestedDocument, field_names: list[str]) -> str:
    listed = "\n".join(f"- {name}" for name in field_names)
    return (
        f"Document type (classified during ingestion): {document.document_type}\n"
        f"Fields to extract (one JSON object per found field; omit missing fields):\n{listed}\n"
        f"\nDocument (pages delimited by [PAGE n] markers — do NOT copy those markers):\n\n{document.full_text()}"
    )


def _collect_parsed(
    raw: dict | list,
    field_names: list[str],
    document: IngestedDocument,
) -> list[ExtractedField]:
    if isinstance(raw, dict) and not raw:
        return []
    items: list = []
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        if "field_name" in raw:
            items = [raw]
        else:
            # {"company_name": {...}, ...} or {"fields": [...]}
            nested = raw.get("fields")
            if isinstance(nested, list):
                items = nested
            else:
                items = [v for v in raw.values() if isinstance(v, dict)]
    by_name: dict[str, ExtractedField] = {}
    wanted = set(field_names)
    for item in items:
        if isinstance(item, list):
            item = item[0] if item else {}
        if not isinstance(item, dict):
            continue
        name = item.get("field_name")
        if name not in wanted:
            continue
        field = _parse_one_field(item, name, document.document_id)
        if field:
            by_name[field.field_name] = enrich_field_unit(field, document)
    return [by_name[n] for n in field_names if n in by_name]


def _fields_from_prefetched(
    document: IngestedDocument,
    field_names: list[str],
    on_progress: Callable[[str, int, int], None] | None,
) -> list[ExtractedField]:
    """Consume raw field dicts the fused vision engine produced from the page images.

    Same guardrails as every other path (`_parse_one_field` enforces the confidence threshold
    and schema). If two pages report the same field, keep the higher-confidence one.
    """
    wanted = set(field_names)
    best: dict[str, ExtractedField] = {}
    for raw in document.vision_prefetched_fields or []:
        if not isinstance(raw, dict):
            continue
        name = raw.get("field_name")
        if name not in wanted:
            continue
        field = _parse_one_field(raw, name, document.document_id)
        if not field:
            continue
        field = enrich_field_unit(field, document)
        prev = best.get(field.field_name)
        if prev is None or field.confidence > prev.confidence:
            best[field.field_name] = field
    ordered = [best[n] for n in field_names if n in best]
    if on_progress and field_names:
        on_progress(field_names[-1], len(field_names), len(field_names))
    return ordered


def _core_fields_for(document: IngestedDocument) -> frozenset[str]:
    if document.document_type == "loan_application":
        return LOAN_CORE_FIELDS
    if document.document_type == "financial_statement":
        return FS_CORE_FIELDS
    return frozenset()


def _extract_one(document: IngestedDocument, field_name: str, *, blunt: bool = False) -> ExtractedField | None:
    max_tokens = NARRATIVE_MAX_TOKENS if field_name in NARRATIVE_FIELDS else PER_FIELD_MAX_TOKENS
    raw = complete_json(
        FIELD_SYSTEM_PROMPT,
        _user_prompt_one(document, field_name, blunt=blunt),
        max_tokens=max_tokens,
    )
    field = _parse_one_field(raw, field_name, document.document_id)
    return enrich_field_unit(field, document) if field else None


def _extract_fields_per_field(
    document: IngestedDocument,
    field_names: list[str],
    on_progress: Callable[[str, int, int], None] | None,
    cancel_check: Callable[[], bool] | None,
) -> list[ExtractedField]:
    total = len(field_names)
    core = _core_fields_for(document)
    fields: list[ExtractedField] = []
    for i, field_name in enumerate(field_names, start=1):
        if cancel_check and cancel_check():
            break
        if on_progress:
            on_progress(field_name, i, total)
        field = _extract_one(document, field_name)
        # A core field that came back empty from a small model is usually a miss, not a genuine
        # absence — give it one more shot with a blunter prompt before accepting the gap.
        if field is None and field_name in core:
            field = _extract_one(document, field_name, blunt=True)
        if field:
            fields.append(field)
    return fields


def extract_fields(
    document: IngestedDocument,
    on_progress: Callable[[str, int, int], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> list[ExtractedField]:
    if not document.quality_ok:
        return []  # Document Ingestor already flagged this — Financial Wizard doesn't guess on it

    field_names = _target_field_names(document)

    # Fused vision engine (POC_OCR_ENGINE=mlx_vision_extract) already extracted the fields from
    # the page images. Run them through the SAME guardrails as any other path — no LLM call here.
    if document.vision_prefetched_fields is not None:
        return _fields_from_prefetched(document, field_names, on_progress)

    if not extract_batch_enabled():
        return _extract_fields_per_field(document, field_names, on_progress, cancel_check)

    total = len(field_names)
    if on_progress and field_names:
        on_progress(field_names[0], 1, total)
    if cancel_check and cancel_check():
        return []
    raw = complete_json(
        BATCH_SYSTEM_PROMPT,
        _user_prompt_batch(document, field_names),
        max_tokens=BATCH_MAX_TOKENS,
    )
    fields = _collect_parsed(raw, field_names, document)
    min_ok = max(1, (len(field_names) + 1) // 2)
    if len(fields) < min_ok:
        warnings.warn(
            "[financial_wizard] batch extract too sparse "
            f"({len(fields)}/{len(field_names)}) — falling back to per-field",
        )
        return _extract_fields_per_field(document, field_names, on_progress, cancel_check)
    if on_progress:
        on_progress(field_names[-1], total, total)
    return fields
