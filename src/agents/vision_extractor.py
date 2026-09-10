"""
Fused vision OCR + field extraction — the VL model both transcribes a scanned page and pulls
the POC fields from it, while it is the only model resident. No 14B swap, no text LLM re-reading
a noisy transcription.

Why (evaluation/FINDINGS.md "Fused VL pass"): the plain `mlx_vision` path is
raster → VL transcription → (stop VL, load 14B) → 14B reads the *transcription* → JSON. Two model
loads per document and the field values are read off noisy OCR text, not the page.

Here, per scanned page, ONE VL call (`POC_FUSED_SINGLE_CALL=1`, default): the model returns
`{"transcription": ..., "fields": [...]}` — verbatim text plus the POC fields, numeric value
normalised to Western digits, snippet copied from its own transcription. If that response has no
transcription or does not parse, it falls back to two focused calls (transcribe, then extract).

The VL server (MLX_VISION_BASE_URL) is the only model loaded. Financial Wizard then only
validates + merges (`_fields_from_prefetched`) — same guardrails as every other path. Contract
unchanged (SPEC 3.1.2): output is still `list[ExtractedField]`.
"""
from __future__ import annotations

import json
import os
import re
import time

from PIL import Image

from src.config import MLX_VISION_BASE_URL, MLX_VISION_MODEL
from src.llm_client import MLX_HTTP_LOCK, _extract_json
from src.logging_setup import get_logger
from src.models.schemas import POC_FIELD_NAMES

log = get_logger("vision_extract")

# Quality-first: this is where the digits are actually read. 2560 px scored best in the
# benchmark (evaluation/FINDINGS.md). Lower it only if a page times out repeatedly.
FUSED_MAX_DIM = 2560
FUSED_TIMEOUT_SECONDS = 240
SINGLE_MAX_TOKENS = 3000  # transcription (~900) + up to 10 field objects (~1800) + slack
TRANSCRIBE_MAX_TOKENS = 1400
EXTRACT_MAX_TOKENS = 1600
# One call per page by default (half the VL invocations, no re-prefill of the image). Falls
# back to the two-call path if the combined response is unparseable or drops most fields.
POC_FUSED_SINGLE_CALL = os.environ.get("POC_FUSED_SINGLE_CALL", "1").strip() not in {"0", "false", "no"}

LOAN_ONLY_FIELDS = frozenset({"requested_facility_amount", "collateral_offered"})
_EMPTY_VALUES = {"", "none", "null", "n/a", "na", "-", "--"}
_PAGE_MARKER = re.compile(r"\[PAGE\s+\d+\]", re.IGNORECASE)
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩،٫", "0123456789,.")

_TRANSCRIBE_PROMPT = (
    "Transcribe every visible line of text on this scanned page exactly as written, in reading "
    "order (right-to-left for Arabic). Do NOT translate. Do NOT change digit scripts — copy "
    "Eastern Arabic-Indic (٠-٩) and Western (0-9) digits exactly as shown. One line per table "
    "row (label then its values). Output only the transcription."
)

_SINGLE_SYSTEM = """You are the Financial Wizard capability of a bank credit-memo agent, reading
ONE scanned page of a financial document as an image.

Output ONLY a JSON object: {"transcription": str, "fields": [ ... ]}

"transcription": every visible line of text on the page, copied exactly, in reading order
(right-to-left for Arabic). Do NOT translate. Do NOT change digit scripts — copy Eastern
Arabic-Indic (٠-٩) and Western digits exactly as shown. One line per table row (label then its
values). NOTE: in this Naskh font the Arabic-Indic zero ٠ is a small dot and the thousands
separator ٬ is also small — read carefully, a number like ٤٥٬٩٠٠٬٠٠٠ is 45,900,000 (three
trailing dots = three zeros).

"fields": a JSON array of the requested fields that GENUINELY appear ON THIS page. Each element:
{"field_name": str, "value": str, "unit": str|null, "source_page": <this page number>,
 "source_snippet": str, "confidence": float, "status": "confirmed"|"needs_review",
 "validation_note": str|null}

Field rules:
1. Omit any field not on this page. Never invent or estimate. Use [] if none apply.
2. "value": for a monetary amount, the NUMBER ONLY in WESTERN digits with thousands separators
   (e.g. "45,900,000") — convert Arabic-Indic digits. Currency code (e.g. "EGP") goes in "unit";
   if no currency is stated on the page, status="needs_review".
3. "source_snippet": ONE short line (<=120 chars) copied VERBATIM from your transcription that
   contains the value. Never paraphrase, never the "[PAGE n]" marker.
4. Ambiguous / contradicted / missing unit / approximate → status="needs_review", confidence
   < 0.7, reason in "validation_note". Clear → status="confirmed", confidence >= 0.7.
5. "requested_facility_amount" and "collateral_offered" only apply to a loan/credit APPLICATION,
   never a financial statement's existing-facilities note.
6. "existing_bank_facilities" and "collateral_offered" are FREE TEXT, never a bare number. For
   "existing_bank_facilities" copy the full note — every facility, its bank, amount and any
   utilisation %. For "collateral_offered" copy the whole description of security offered.
"""

_EXTRACT_SYSTEM = """You are the Financial Wizard capability of a bank credit-memo agent. You are
given a scanned page image and its transcription. Extract the requested fields that GENUINELY
appear on THIS page.

Output ONLY a JSON array. Each element:
{"field_name": str, "value": str, "unit": str|null, "source_page": <page number>,
 "source_snippet": str, "confidence": float, "status": "confirmed"|"needs_review",
 "validation_note": str|null}

Rules:
1. Omit any field not on this page. Never invent or estimate a value. Use [] if none apply.
2. "value": for a monetary amount, the NUMBER ONLY, written in WESTERN digits with thousands
   separators (e.g. "129,400,000") — convert Arabic-Indic digits (١٢٣ → 123) if the page shows
   them. Put the currency code (e.g. "EGP") in "unit". If the currency is not stated on the
   page, set status="needs_review".
3. "source_snippet": a line copied VERBATIM from the transcription above that contains the value
   — same characters, same digit script as the transcription. Never paraphrase, never the
   "[PAGE n]" marker.
4. Ambiguous / contradicted / missing unit / only approximate → status="needs_review",
   confidence < 0.7, reason in "validation_note". Clear and unambiguous → status="confirmed",
   confidence >= 0.7.
5. "requested_facility_amount" and "collateral_offered" describe a NEW facility being applied
   for — only on a loan/credit APPLICATION, never from a financial statement's existing-
   facilities note.
"""


def _page_png_b64(image: Image.Image) -> str:
    import base64
    import io

    resized = image.copy()
    resized.thumbnail((FUSED_MAX_DIM, FUSED_MAX_DIM), Image.LANCZOS)
    buf = io.BytesIO()
    resized.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _target_fields(document_type: str) -> list[str]:
    if document_type == "financial_statement":
        return [n for n in POC_FIELD_NAMES if n not in LOAN_ONLY_FIELDS]
    return list(POC_FIELD_NAMES)


def _vl_call(messages: list[dict], max_tokens: int) -> tuple[str, str | None]:
    import requests

    body = {
        "model": MLX_VISION_MODEL,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": False,
    }
    try:
        with MLX_HTTP_LOCK:
            resp = requests.post(
                f"{MLX_VISION_BASE_URL}/v1/chat/completions", json=body,
                timeout=FUSED_TIMEOUT_SECONDS,
            )
    except Exception as exc:  # noqa: BLE001
        return "", f"'{MLX_VISION_MODEL}' @ {MLX_VISION_BASE_URL} failed (network): {exc}"
    if not resp.ok:
        try:
            detail = resp.json().get("error", resp.text)
        except ValueError:
            detail = resp.text
        if isinstance(detail, dict):
            detail = detail.get("message") or str(detail)
        return "", f"'{MLX_VISION_MODEL}' failed: HTTP {resp.status_code} — {detail}"
    content = ((resp.json().get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    return content, None


def _image_msg(b64: str, text: str) -> dict:
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ],
    }


def _looks_empty(value: object) -> bool:
    return str(value).strip().lower() in _EMPTY_VALUES


def _clean_items(raw_items: object, page_number: int) -> list[dict]:
    items = raw_items if isinstance(raw_items, list) else []
    cleaned: list[dict] = []
    for item in items:
        if not isinstance(item, dict) or "field_name" not in item:
            continue
        if _looks_empty(item.get("value")):
            continue
        item.setdefault("source_page", page_number)
        if "source_snippet" in item:
            item["source_snippet"] = _PAGE_MARKER.sub(" ", str(item["source_snippet"])).strip()
        item["value"] = str(item.get("value", "")).translate(_AR_DIGITS)
        cleaned.append(item)
    return cleaned


def extract_page(
    image: Image.Image, page_number: int, document_type: str,
) -> tuple[str, list[dict], str | None]:
    """Returns (transcription, raw_field_dicts, error_note).

    One VL call per page by default (`POC_FUSED_SINGLE_CALL`): the model transcribes AND extracts
    in one JSON object. Falls back to two focused calls if that response is unusable.
    `raw_field_dicts` are unvalidated — Financial Wizard runs them through `_parse_one_field`.
    """
    b64 = _page_png_b64(image)
    wanted = _target_fields(document_type)

    if POC_FUSED_SINGLE_CALL:
        transcription, fields, err, ok = _extract_page_single(b64, page_number, document_type, wanted)
        if ok:
            return transcription, fields, err
        log.warning("Fused single-call page=%s weak (%s) — falling back to two calls", page_number, err)

    return _extract_page_two_calls(b64, page_number, document_type, wanted)


def _extract_page_single(
    b64: str, page_number: int, document_type: str, wanted: list[str],
) -> tuple[str, list[dict], str | None, bool]:
    started = time.monotonic()
    user_text = (
        f"Page {page_number} of a document classified as: {document_type}.\n"
        f"Fields to extract (only the ones on this page):\n" + "\n".join(f"- {n}" for n in wanted)
    )
    content, err = _vl_call(
        [{"role": "system", "content": _SINGLE_SYSTEM}, _image_msg(b64, user_text)],
        SINGLE_MAX_TOKENS,
    )
    elapsed = time.monotonic() - started
    if err:
        return "", [], f"Fused vision page {page_number}: {err}", False
    try:
        obj = _extract_json(content)
    except (ValueError, json.JSONDecodeError) as exc:
        return "", [], f"unparseable JSON ({exc})", False
    if not isinstance(obj, dict):
        return "", [], "response was not a JSON object", False
    transcription = str(obj.get("transcription") or "").strip()
    fields = _clean_items(obj.get("fields"), page_number)
    # "weak" = no transcription (citation checks would fail) — retry with the focused two-call path
    ok = bool(transcription)
    log.info(
        "Fused single-call page=%s (%.1fs, %s transcript chars, %s field(s), ok=%s)",
        page_number, elapsed, len(transcription), len(fields), ok,
    )
    return transcription, fields, None, ok


def _extract_page_two_calls(
    b64: str, page_number: int, document_type: str, wanted: list[str],
) -> tuple[str, list[dict], str | None]:
    started = time.monotonic()
    transcription, err = _vl_call([_image_msg(b64, _TRANSCRIBE_PROMPT)], TRANSCRIBE_MAX_TOKENS)
    if err:
        log.error("Fused: transcription page=%s failed: %s", page_number, err)
        return "", [], f"Fused vision transcription page {page_number}: {err}"
    transcription = transcription.strip()

    user_text = (
        f"Page {page_number} of a document classified as: {document_type}.\n\n"
        f"Transcription of this page:\n{transcription}\n\n"
        f"Fields to extract (only the ones on this page):\n"
        + "\n".join(f"- {n}" for n in wanted)
    )
    content, err = _vl_call(
        [{"role": "system", "content": _EXTRACT_SYSTEM}, _image_msg(b64, user_text)],
        EXTRACT_MAX_TOKENS,
    )
    elapsed = time.monotonic() - started
    if err:
        log.error("Fused: extract page=%s failed (%.1fs): %s", page_number, elapsed, err)
        return transcription, [], f"Fused vision extract page {page_number}: {err}"
    try:
        obj = _extract_json(content)
    except (ValueError, json.JSONDecodeError) as exc:
        log.error("Fused: extract page=%s unparseable (%.1fs): %s", page_number, elapsed, exc)
        return transcription, [], (
            f"Fused vision extract page {page_number}: model returned no valid JSON ({exc})"
        )
    items = obj if isinstance(obj, list) else obj.get("fields") if isinstance(obj, dict) else []
    cleaned = _clean_items(items, page_number)
    log.info(
        "Fused two-call page=%s done (%.1fs, %s transcript chars, %s field(s))",
        page_number, elapsed, len(transcription), len(cleaned),
    )
    note = None
    if not transcription and not cleaned:
        note = f"Fused vision extract page {page_number} returned nothing usable."
    return transcription, cleaned, note
