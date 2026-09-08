"""Human-readable pipeline progress messages for the review UI."""
from __future__ import annotations

import html

from src.models.schemas import IngestedDocument, POC_FIELD_NAMES

EXTRACT_FIELD_COUNT = len(POC_FIELD_NAMES)
# ingest (2) + extract (N fields) + validate start (1) + validate each extracted field (up to N) + summary (1)
PIPELINE_MAX_STEPS = 2 + EXTRACT_FIELD_COUNT + 1 + EXTRACT_FIELD_COUNT + 1

# stage -> CSS modifier class
STAGE_INGEST = "ingest"
STAGE_EXTRACT = "extract"
STAGE_VALIDATE = "validate"
STAGE_MEMO = "memo"
STAGE_DONE = "done"
STAGE_ERROR = "error"

FIELD_STEPS: dict[str, tuple[str, str]] = {
    "company_name": (
        "Financial Wizard",
        "Identifying the legal name of the applicant company",
    ),
    "reporting_period": (
        "Financial Wizard",
        "Determining which fiscal period this document covers",
    ),
    "total_assets": (
        "Financial Wizard",
        "Reading total assets from the statement of financial position",
    ),
    "total_liabilities": (
        "Financial Wizard",
        "Reading total liabilities from the balance sheet",
    ),
    "total_equity": (
        "Financial Wizard",
        "Reading shareholders' equity / total equity",
    ),
    "annual_revenue": (
        "Financial Wizard",
        "Extracting annual revenue from the income statement",
    ),
    "net_income": (
        "Financial Wizard",
        "Extracting net profit / net income for the period",
    ),
    "existing_bank_facilities": (
        "Financial Wizard",
        "Summarising existing bank facilities and utilisation",
    ),
    "requested_facility_amount": (
        "Financial Wizard",
        "Finding the requested facility amount in the application",
    ),
    "collateral_offered": (
        "Financial Wizard",
        "Extracting collateral and security offered",
    ),
}

MEMO_SECTIONS: dict[str, str] = {
    "Company Overview": "Drafting the company overview section of the credit memo",
    "Financial Summary": "Summarising confirmed financial figures with citations",
    "Facility Request": "Describing the requested facility and intended use of proceeds",
    "Existing Bank Facilities": "Documenting existing banking relationships and exposures",
}


def log_entry(stage: str, label: str, message: str, step: str | None = None, *, highlight: bool = False) -> dict:
    return {"stage": stage, "label": label, "message": message, "step": step, "highlight": highlight}


def msg_ingest_start(filename: str) -> dict:
    return log_entry(
        STAGE_INGEST,
        "Document Ingestor",
        f"Opening PDF and extracting text from all pages of {filename}",
    )


def msg_ingest_done(document: IngestedDocument) -> dict:
    pages = len(document.pages)
    quality = "text is readable" if document.quality_ok else "quality issues detected"
    message = (
        f"Parsed {pages} page{'s' if pages != 1 else ''} · "
        f"classified as {document.document_type.replace('_', ' ')} · {quality}"
    )
    if document.quality_notes:
        # Puni razlog (npr. konkretna OCR/vision greška) — bez ovoga korisnik nema način da
        # vidi ZAŠTO je dokument odbijen a da ne otvara terminal (SPEC.md 8.2 princip: razlog,
        # ne samo "odbijeno").
        message += f"\n\n{document.quality_notes}"
    return log_entry(
        STAGE_INGEST,
        "Document Ingestor",
        message,
    )


def msg_extract_field(field_name: str, i: int, total: int) -> dict:
    label, message = FIELD_STEPS.get(
        field_name,
        ("Financial Wizard", f"Extracting {field_name.replace('_', ' ')}"),
    )
    return log_entry(STAGE_EXTRACT, label, message, step=f"{i}/{total}")


def msg_validate_start() -> dict:
    return log_entry(
        STAGE_VALIDATE,
        "Citation Validator",
        "Starting citation checks — verifying each extracted value against its source page",
    )


def msg_validate_field(field_name: str, i: int, total: int) -> dict:
    label = field_name.replace("_", " ")
    return log_entry(
        STAGE_VALIDATE,
        "Citation Validator",
        f"Verifying source citation for {label}",
        step=f"{i}/{total}",
    )


def msg_validate_done(confirmed: int, needs_review: int) -> dict:
    parts = [f"{confirmed} confirmed"]
    if needs_review:
        parts.append(f"{needs_review} flagged for review")
    return log_entry(
        STAGE_VALIDATE,
        "Citation Validator",
        "Validation complete · " + " · ".join(parts),
    )


def msg_extract_complete() -> dict:
    return log_entry(
        STAGE_DONE,
        "Processing complete",
        "All capabilities finished — extracted fields are ready for review",
        highlight=True,
    )


def msg_error(detail: str) -> dict:
    return log_entry(STAGE_ERROR, "Pipeline", detail)


def msg_cancelled() -> dict:
    return log_entry(
        STAGE_ERROR,
        "Processing stopped",
        "Extraction was cancelled — partial progress is kept in the log above",
        highlight=True,
    )


def msg_memo_start() -> dict:
    return log_entry(
        STAGE_MEMO,
        "Narrative Synthesizer",
        "Starting draft memo — only confirmed fields will be used",
    )


def msg_memo_section(title: str, i: int, total: int) -> dict:
    message = MEMO_SECTIONS.get(title, f"Writing memo section: {title}")
    return log_entry(STAGE_MEMO, "Narrative Synthesizer", message, step=f"{i}/{total}")


def msg_memo_done() -> dict:
    return log_entry(
        STAGE_DONE,
        "Memo ready",
        "Draft memo and report are ready to download",
        highlight=True,
    )


PIPELINE_LOG_CSS = """
.pipeline-log {
    display: flex; flex-direction: column; gap: 0.55rem;
    max-height: 400px; overflow-y: auto; padding: 0.15rem 0.1rem;
    scroll-behavior: auto;
}
.pipeline-log-empty {
    color: #8a96a3; font-size: 0.88rem; font-style: italic; padding: 0.5rem 0.2rem;
}
.log-entry {
    display: flex; align-items: flex-start; gap: 0.75rem;
    padding: 0.65rem 0.85rem; border-radius: 10px;
    background: #f8fafc; border: 1px solid #e8edf2;
}
.log-entry-ingest   { border-left: 3px solid #0047BA; }
.log-entry-extract  { border-left: 3px solid #6b4fbb; }
.log-entry-validate { border-left: 3px solid #c27803; }
.log-entry-memo     { border-left: 3px solid #0047BA; }
.log-entry-done     { border-left: 3px solid #158a44; background: #f0faf4; }
.log-entry-complete {
    border: 2px solid #158a44 !important;
    border-left: 6px solid #158a44 !important;
    background: linear-gradient(135deg, #dff5e7 0%, #f0faf4 100%) !important;
    padding: 1rem 1.15rem !important;
    margin-top: 0.4rem;
    box-shadow: 0 4px 14px rgba(21, 138, 68, 0.16);
}
.log-complete-icon {
    flex: 0 0 auto; width: 2.25rem; height: 2.25rem; border-radius: 50%;
    background: #158a44; color: white; font-weight: 800; font-size: 1.15rem;
    display: flex; align-items: center; justify-content: center; line-height: 1;
    box-shadow: 0 2px 6px rgba(21, 138, 68, 0.35);
}
.log-complete-title {
    font-size: 1.05rem; font-weight: 800; color: #0d5c2e;
    letter-spacing: -0.01em; margin-bottom: 0.2rem;
}
.log-complete-message { font-size: 0.92rem; color: #1a5432; font-weight: 600; line-height: 1.45; }
.log-entry-error    { border-left: 3px solid #c0392b; background: #fef5f4; }
.log-entry-complete.log-entry-error {
    border-color: #c0392b !important;
    border-left-color: #c0392b !important;
    background: linear-gradient(135deg, #fdecea 0%, #fef5f4 100%) !important;
    box-shadow: 0 4px 14px rgba(192, 57, 43, 0.14);
}
.log-entry-complete.log-entry-error .log-complete-icon {
    background: #c0392b;
    box-shadow: 0 2px 6px rgba(192, 57, 43, 0.35);
}
.log-entry-complete.log-entry-error .log-complete-title { color: #922b21; }
.log-entry-complete.log-entry-error .log-complete-message { color: #7b241c; }
.log-step {
    flex: 0 0 auto; min-width: 2.1rem; font-size: 0.72rem; font-weight: 700;
    color: #64707c; background: white; border: 1px solid #dde4ea;
    border-radius: 6px; padding: 0.2rem 0.35rem; text-align: center; margin-top: 0.1rem;
}
.log-step-empty { visibility: hidden; }
.log-body { flex: 1; min-width: 0; }
.log-label {
    font-size: 0.72rem; font-weight: 700; letter-spacing: 0.03em;
    text-transform: uppercase; color: #64707c; margin-bottom: 0.15rem;
}
.log-message { font-size: 0.88rem; color: #1a2430; line-height: 1.45; white-space: pre-wrap; }
"""



def _current_step_from_log(entries: list[dict]) -> int:
    """Map log state to a 1..PIPELINE_MAX_STEPS index (robust to duplicate log lines)."""
    if not entries:
        return 0

    last = entries[-1]
    stage = last.get("stage")
    step = last.get("step")

    if last.get("highlight") and stage == STAGE_DONE:
        return PIPELINE_MAX_STEPS

    if step and "/" in step:
        i, _ = (int(part) for part in step.split("/", 1))
        if stage == STAGE_EXTRACT:
            return min(2 + i, PIPELINE_MAX_STEPS)
        if stage == STAGE_VALIDATE:
            return min(2 + EXTRACT_FIELD_COUNT + 1 + i, PIPELINE_MAX_STEPS)
        if stage == STAGE_MEMO:
            return PIPELINE_MAX_STEPS

    message = last.get("message", "")
    if stage == STAGE_VALIDATE and "Validation complete" in message:
        return min(2 + EXTRACT_FIELD_COUNT + 1 + EXTRACT_FIELD_COUNT, PIPELINE_MAX_STEPS)
    if stage == STAGE_VALIDATE and "Starting citation" in message:
        return 2 + EXTRACT_FIELD_COUNT + 1

    if stage == STAGE_INGEST:
        return min(sum(1 for e in entries if e.get("stage") == STAGE_INGEST), 2)

    non_terminal = [
        e for e in entries
        if not (e.get("highlight") and e.get("stage") in (STAGE_DONE, STAGE_ERROR))
    ]
    return min(len(non_terminal), PIPELINE_MAX_STEPS)


def pipeline_progress(entries: list[dict]) -> tuple[float, str, str, int, int]:
    """Return fraction (0-1), phase label, detail text, current step, max steps."""
    if not entries:
        return 0.0, "Ready", "Waiting to start…", 0, PIPELINE_MAX_STEPS

    last = entries[-1]
    if last.get("highlight") and last.get("stage") == STAGE_DONE:
        return 1.0, "Complete", last.get("message", ""), PIPELINE_MAX_STEPS, PIPELINE_MAX_STEPS
    if last.get("highlight") and last.get("stage") == STAGE_ERROR:
        current = _current_step_from_log(entries)
        return current / PIPELINE_MAX_STEPS, "Stopped", last.get("message", ""), current, PIPELINE_MAX_STEPS

    current = _current_step_from_log(entries)
    fraction = min(current / PIPELINE_MAX_STEPS, 0.98)
    phase_map = {
        STAGE_INGEST: "Document Ingestor",
        STAGE_EXTRACT: "Financial Wizard",
        STAGE_VALIDATE: "Citation Validator",
        STAGE_MEMO: "Narrative Synthesizer",
    }
    phase = phase_map.get(last.get("stage"), "Pipeline")
    detail = last.get("message", "")
    step = last.get("step")
    if step:
        detail = f"{detail} ({step})"
    return fraction, phase, detail, current, PIPELINE_MAX_STEPS


def _render_log_entry(e: dict) -> str:
    stage = html.escape(e["stage"])
    label = html.escape(e["label"])
    message = html.escape(e["message"])
    if e.get("highlight") or e["stage"] == STAGE_DONE:
        return (
            f'<div class="log-entry log-entry-{stage} log-entry-complete">'
            f'<div class="log-complete-icon" aria-hidden="true">✓</div>'
            f'<div class="log-body">'
            f'<div class="log-complete-title">{label}</div>'
            f'<div class="log-complete-message">{message}</div>'
            f"</div></div>"
        )
    step = e.get("step") or ""
    step_html = f'<span class="log-step">{html.escape(step)}</span>' if step else '<span class="log-step log-step-empty"></span>'
    return (
        f'<div class="log-entry log-entry-{stage}">'
        f"{step_html}"
        f'<div class="log-body">'
        f'<div class="log-label">{label}</div>'
        f'<div class="log-message">{message}</div>'
        f"</div></div>"
    )


def render_pipeline_log(entries: list[dict]) -> str:
    if not entries:
        return '<div class="pipeline-log pipeline-log-empty">Waiting to start…</div>'

    rows = [_render_log_entry(e) for e in entries]
    return '<div class="pipeline-log">' + "".join(rows) + '<div id="log-end"></div></div>'


def render_live_pipeline_log(entries: list[dict]) -> str:
    """HTML fragment for st.html — log entries with auto-scroll to newest."""
    body = render_pipeline_log(entries)
    return f"""<style>{PIPELINE_LOG_CSS}</style>
{body}
<script>
(function() {{
  function scrollToBottom() {{
    var log = document.querySelector('.pipeline-log');
    if (!log) return;
    log.scrollTop = log.scrollHeight;
  }}
  scrollToBottom();
  requestAnimationFrame(scrollToBottom);
  setTimeout(scrollToBottom, 30);
}})();
</script>"""
