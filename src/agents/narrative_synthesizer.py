"""
Narrative Synthesizer — SPEC.md 3.1.4

Piše nacrt memoranduma SAMO od potvrđenih (status="confirmed") polja. Guardrail posle generisanja
proverava da nijedna brojka u tekstu ne postoji van skupa brojki iz ulaznih polja (SPEC.md 4:
"mandatory citation").

Implementaciona napomena (isti razlog kao u financial_wizard.py): manji lokalni modeli nepouzdano
vraćaju JSON niz od više sekcija u jednom pozivu, pa se ovde piše PO JEDNA SEKCIJA po pozivu —
sporije, ali svaki poziv ima trivijalan očekivan oblik odgovora (jedan objekat).
"""
import re
import warnings
from typing import Callable

from pydantic import ValidationError

from src.llm_client import complete_json
from src.models.schemas import DraftMemo, ExtractedField, MemoSection

SECTION_TITLES = [
    "Company Overview",
    "Financial Summary",
    "Facility Request",
    "Existing Bank Facilities",
]

SECTION_SYSTEM_PROMPT = """You are the Narrative Synthesizer capability of a credit memo agent.

You will receive a list of CONFIRMED financial/credit fields (already validated, safe to use) and
the title of ONE memo section to write. Write only that section, in English. Rules:

1. Never state a number that is not present in the provided fields. If nothing relevant to this
   section is present in the fields, write "Not available in submitted documents" instead of
   guessing — do not skip the response, still return valid JSON.
2. Every sentence that states a figure from a field must reference that field's name in square
   brackets right after the figure, e.g. "Total assets stood at USD 12,450,000 [total_assets]."
3. Output ONLY a single raw JSON object as the top-level value — NOT a list, NOT wrapped:
   {"title": str, "text": str, "cited_fields": [str, ...]}
"""


def _numbers_in(text: str) -> set[str]:
    """
    Skupi numeričke tokene iz teksta radi guardrail provere. Regex-ova [\\d,]* klasa greedy hvata
    i zarez na kraju rečenice (npr. "2023," iz "31 December 2023,") kao deo broja, što bi bez
    normalizacije lažno prijavilo "2023," kao necitiranu vrednost dok se "2023" iz izvornog polja
    ne poklapa string-for-string. rstrip(",.") uklanja tu interpunkciju, ne dira separator hiljada
    unutar broja (npr. "12,450,000" ostaje netaknut jer zarezi tu nisu na kraju stringa).
    """
    raw_matches = re.findall(r"\d[\d,]*\.?\d*", text)
    return {m.rstrip(",.") for m in raw_matches}


def _write_one_section(title: str, fields_payload: list[dict]) -> MemoSection | None:
    user_prompt = f"Section to write: {title}\n\nConfirmed fields:\n{fields_payload}"
    raw = complete_json(SECTION_SYSTEM_PROMPT, user_prompt)
    if isinstance(raw, list):  # odbrana ako model ipak vrati niz sa jednim elementom
        raw = raw[0] if raw else {}
    if not raw:
        return None
    try:
        return MemoSection(
            title=raw.get("title", title),
            text=raw["text"],
            cited_fields=raw.get("cited_fields", []),
        )
    except (KeyError, TypeError, ValidationError) as exc:
        warnings.warn(f"[narrative_synthesizer] preskočena sekcija '{title}' — malformisan "
                       f"odgovor modela: {raw!r} ({exc})")
        return None


def synthesize_memo(
    client_name: str,
    confirmed_fields: list[ExtractedField],
    open_exceptions: list[str],
    on_progress: Callable[[str, int, int], None] | None = None,
) -> DraftMemo:
    if not confirmed_fields:
        raise ValueError("No confirmed fields provided — nothing safe to synthesize a memo from.")

    fields_payload = [
        {"field_name": f.field_name, "value": f.value, "unit": f.unit}
        for f in confirmed_fields
    ]

    total = len(SECTION_TITLES)
    sections = []
    for i, title in enumerate(SECTION_TITLES, start=1):
        if on_progress:
            on_progress(title, i, total)
        section = _write_one_section(title, fields_payload)
        if section:
            sections.append(section)

    memo = DraftMemo(client_name=client_name, sections=sections, open_exceptions=open_exceptions)
    memo.guardrail_violations = _check_citation_guardrail(memo, confirmed_fields)
    return memo


def _check_citation_guardrail(memo: DraftMemo, confirmed_fields: list[ExtractedField]) -> list[str]:
    """SPEC.md sekcija 5: 'da li generisani memo sadrži ijednu brojku bez citata? 0 dozvoljeno.'"""
    allowed_numbers: set[str] = set()
    for f in confirmed_fields:
        allowed_numbers |= _numbers_in(f.value)

    violations = []
    for section in memo.sections:
        used_numbers = _numbers_in(section.text)
        untraceable = used_numbers - allowed_numbers
        if untraceable:
            violations.append(
                f"Section '{section.title}' contains numbers not present in any confirmed "
                f"field: {sorted(untraceable)}"
            )
    return violations
