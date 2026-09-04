"""
Financial Wizard — SPEC.md 3.1.2

Izvlači fiksan skup polja (models.schemas.POC_FIELD_NAMES) iz jednog IngestedDocument-a.
Pravilo iz SPEC-a: ne piše vrednost bez izvora, ne nagađa kod nejasnoće/konflikta.

Implementaciona napomena (ne menja SPEC contract, samo KAKO se poziva LLM):
manji lokalni modeli (npr. qwen2.5:3b) su se u praksi pokazali nepouzdani kad se traži JSON niz
od više stavki u jednom pozivu — nedosledno vraćaju omotan objekat, goli pojedinačni objekat, ili
samo deo traženih polja. Zato se ovde poziva LLM PO JEDNOM POLJU (10 malih poziva umesto 1 velikog)
— sporije, ali svaki poziv ima trivijalan očekivan oblik odgovora (jedan objekat ili {}), što je
mnogo pouzdanije za slabije modele. SPEC.md izlaz (`list[ExtractedField]`) ostaje isti.
"""
import warnings
from typing import Callable

from pydantic import ValidationError

from src.llm_client import complete_json
from src.models.schemas import CONFIDENCE_THRESHOLD, POC_FIELD_NAMES, ExtractedField, IngestedDocument

FIELD_SYSTEM_PROMPT = """You are the Financial Wizard capability of a credit memo agent.

Your job: extract ONE specific requested field from a bank document. If you extract a value, you
must cite the EXACT page number and an EXACT text snippet copied verbatim from that page that
supports it.

Rules (do not break these):
1. If the requested field is NOT genuinely present anywhere in the document, output exactly: {}
   Never invent a placeholder or estimated value.
2. `source_snippet` must be text copied verbatim from the page you cite — not a paraphrase.
3. If the value is ambiguous, contradicted elsewhere in the document, missing required context
   (e.g. unclear currency/unit), or stated only as an approximation, set status="needs_review"
   and confidence below 0.7, and explain why in `validation_note`.
4. If the value is stated clearly and unambiguously, set status="confirmed" and confidence >= 0.7.
5. Output ONLY a single raw JSON object as the top-level value — NOT a list, NOT wrapped in
   another key. Either exactly `{}` (field not found) or:
   {"field_name": str, "value": str, "unit": str|null, "source_page": int,
    "source_snippet": str, "confidence": float, "status": "confirmed"|"needs_review",
    "validation_note": str|null}
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
            source_snippet=raw["source_snippet"],
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


def extract_fields(
    document: IngestedDocument,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> list[ExtractedField]:
    if not document.quality_ok:
        return []  # Document Ingestor already flagged this — Financial Wizard doesn't guess on it

    total = len(POC_FIELD_NAMES)
    fields: list[ExtractedField] = []
    for i, field_name in enumerate(POC_FIELD_NAMES, start=1):
        if on_progress:
            on_progress(field_name, i, total)
        user_prompt = (
            f"Field to extract: {field_name}\n\n"
            f"Document (pages marked as [PAGE n]):\n\n{document.full_text()}"
        )
        raw = complete_json(FIELD_SYSTEM_PROMPT, user_prompt)
        field = _parse_one_field(raw, field_name, document.document_id)
        if field:
            fields.append(field)

    return fields
