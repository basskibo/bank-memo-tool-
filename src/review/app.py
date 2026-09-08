"""
SCB Credit Memo Portal — Streamlit UI for the POC.

Implements the [HUMAN REVIEW] steps from SPEC.md 3.2: drag-and-drop documents, watch the
pipeline process them live (which capability is running, which field/section is being worked
on), review anything flagged, generate a draft memo, and download a report.

Layout: a document queue lives in the sidebar (compact, independently scrollable, with a
"process all pending" batch action) and the main panel only ever renders the ONE currently
selected document's detail — this is what keeps the page usable once several documents have
been added, instead of stacking full result panels for every document on one long page.

Run: .venv/bin/streamlit run src/review/app.py
"""
import hashlib
import html
import re
import sys
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # so src.* / reports.* imports work

from reports.live_report import build_batch_report_pdf, build_live_report_pdf
from src.agents.narrative_synthesizer import synthesize_memo
from src.config import SAMPLE_DOCS_DIR
from src.models.field_display import build_memo_footnotes, format_field_display_value
from src.orchestration.graph import apply_human_review, run_extraction
from src.review.pipeline_messages import (
    msg_cancelled,
    msg_error,
    msg_extract_complete,
    msg_extract_field,
    msg_ingest_start,
    msg_memo_done,
    msg_memo_section,
    msg_memo_start,
    pipeline_progress,
    render_live_pipeline_log,
)
from src.review.processing_animation import render_processing_animation_html

_REVIEW_DIR = Path(__file__).resolve().parent
SCB_LOGO_PATH = _REVIEW_DIR / "assets" / "scb_logo.svg"
SCB_LOGO_SVG = SCB_LOGO_PATH.read_text(encoding="utf-8")

st.set_page_config(page_title="SCB Credit Memo Portal", page_icon="🏦", layout="wide")
st.logo(str(SCB_LOGO_PATH), size="medium")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20,400,0,0&display=swap');

.msi {
    font-family: 'Material Symbols Outlined';
    font-weight: normal;
    font-style: normal;
    font-size: 1.1em;
    line-height: 1;
    letter-spacing: normal;
    text-transform: none;
    display: inline-block;
    white-space: nowrap;
    word-wrap: normal;
    direction: ltr;
    vertical-align: -0.2em;
    -webkit-font-smoothing: antialiased;
}

:root {
    --scb-blue: #0047BA;
    --scb-blue-dark: #003a96;
    --scb-blue-soft: #e8f1fb;
    --scb-text: #282C30;
    --scb-text-muted: #5c6670;
    --scb-border: #dde5ee;
    --scb-bg: #f7f9fc;
}

html, body, .stApp { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; color: var(--scb-text); }

.block-container { padding-top: 1.3rem; padding-bottom: 2rem; max-width: 1180px; }

.scb-header {
    background: white;
    padding: 1.15rem 1.6rem;
    border-radius: 16px;
    color: var(--scb-text);
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    gap: 1.1rem;
    border: 1px solid var(--scb-border);
    box-shadow: 0 4px 18px rgba(0, 71, 186, 0.08);
}
.scb-header-logo svg { width: auto; height: 34px; display: block; }
.scb-header-text h1 { margin: 0; font-size: 1.22rem; font-weight: 700; letter-spacing: -0.01em; color: var(--scb-text); }
.scb-header-text p { margin: 0.2rem 0 0; color: var(--scb-text-muted); font-size: 0.82rem; }
.scb-footer { opacity: 0.45; font-size: 0.75rem; margin-top: 2.5rem; text-align: center; }

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #ffffff 0%, var(--scb-bg) 100%);
    border-right: 1px solid var(--scb-border);
}
section[data-testid="stSidebar"] > div { padding-top: 0 !important; }
section[data-testid="stSidebar"] .block-container {
    padding-top: 0.35rem !important;
    padding-bottom: 1.25rem;
}
[data-testid="stSidebarHeader"] {
    padding: 0.35rem 0.5rem 0.25rem 0.75rem !important;
    min-height: 0 !important;
}
[data-testid="stSidebarHeader"] img {
    max-height: 1.75rem !important;
    width: auto !important;
    object-fit: contain !important;
}

.sidebar-portal-head {
    margin: 0 0 1rem 0;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid var(--scb-border);
}
.sidebar-portal-title {
    font-size: 0.95rem; font-weight: 700; letter-spacing: -0.02em; color: var(--scb-text);
}
.sidebar-portal-sub {
    font-size: 0.74rem; font-weight: 600; color: var(--scb-text-muted);
    letter-spacing: 0.02em; margin-top: 0.15rem;
}

.sidebar-section-label {
    font-size: 0.68rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
    color: var(--scb-text-muted); margin: 0 0 0.55rem 0;
}
.sidebar-hint { font-size: 0.78rem; color: var(--scb-text-muted); margin: 0 0 0.75rem 0; line-height: 1.45; }

section[data-testid="stSidebar"] [data-testid="stFileUploader"] {
    background: white; border: 1.5px dashed #c5d3e0; border-radius: 12px;
    padding: 0.35rem 0.5rem 0.65rem; margin-bottom: 0.65rem;
}
section[data-testid="stSidebar"] [data-testid="stFileUploader"]:hover {
    border-color: var(--scb-blue); background: var(--scb-blue-soft);
}
section[data-testid="stSidebar"] [data-testid="stFileUploader"] label {
    font-size: 0.82rem !important; color: var(--scb-text) !important;
}
section[data-testid="stSidebar"] [data-testid="stFileUploader"] small {
    font-size: 0.72rem !important; color: var(--scb-text-muted) !important;
}

.queue-stats {
    display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.75rem;
}
.queue-stat {
    background: white; border: 1px solid var(--scb-border); border-radius: 999px;
    padding: 0.22rem 0.65rem; font-size: 0.72rem; font-weight: 600; color: var(--scb-text-muted);
}
.queue-stat strong { color: var(--scb-blue); }

.doc-card {
    background: white; border: 1px solid var(--scb-border); border-radius: 12px;
    padding: 0.8rem 0.9rem; margin-bottom: 0.35rem;
    box-shadow: 0 1px 3px rgba(15, 35, 55, 0.04);
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.doc-card-active {
    border-color: var(--scb-blue); background: var(--scb-blue-soft);
    box-shadow: 0 0 0 3px rgba(0, 71, 186, 0.12);
}
.doc-card-company {
    font-size: 0.88rem; font-weight: 700; color: var(--scb-text); line-height: 1.3;
}
.doc-card-kind {
    font-size: 0.78rem; color: var(--scb-blue); font-weight: 600; margin-top: 0.2rem; line-height: 1.35;
}
.doc-card-file {
    font-size: 0.68rem; color: var(--scb-text-muted); margin-top: 0.35rem;
    word-break: break-all; line-height: 1.4;
}
.doc-card-footer {
    display: flex; align-items: center; justify-content: space-between; gap: 0.5rem;
    flex-wrap: wrap; margin-top: 0.55rem;
}
.doc-card-size {
    font-size: 0.66rem; color: var(--scb-text-muted); font-weight: 600; white-space: nowrap;
}
.doc-card-hint {
    font-size: 0.72rem; color: var(--scb-text-muted); margin-top: 0.5rem;
    padding-top: 0.5rem; border-top: 1px solid var(--scb-border); line-height: 1.4;
}
.doc-card-hint-active { color: var(--scb-blue); font-weight: 600; }

.doc-badge {
    display: inline-flex; align-items: center; gap: 0.25rem;
    font-size: 0.66rem; font-weight: 700; padding: 0.18rem 0.55rem;
    border-radius: 999px; letter-spacing: 0.02em;
}
.doc-badge-pending { background: #f1f3f6; color: var(--scb-text-muted); }
.doc-badge-processing { background: var(--scb-blue-soft); color: var(--scb-blue); }
.doc-badge-review  { background: #fff4e5; color: #9a6200; }
.doc-badge-ready   { background: #e8f7ed; color: #157a3a; }
.doc-badge-done    { background: var(--scb-blue-soft); color: var(--scb-blue); }
.doc-card-processing {
    border-color: var(--scb-blue); background: var(--scb-blue-soft);
    box-shadow: 0 0 0 3px rgba(0, 71, 186, 0.12);
}
.doc-badge-processing::before {
    content: ""; display: inline-block; width: 0.45rem; height: 0.45rem; border-radius: 50%;
    background: var(--scb-blue); margin-right: 0.3rem;
    animation: doc-pulse 1s ease-in-out infinite;
}
@keyframes doc-pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.45; transform: scale(0.85); }
}

section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
    margin-bottom: 0.85rem; gap: 0.35rem;
}
section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] .stButton > button {
    min-height: 2rem; padding: 0.25rem 0.5rem; font-size: 0.78rem; border-radius: 8px;
}
section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] [data-testid="column"]:last-child .stButton > button {
    color: var(--scb-text-muted); border-color: var(--scb-border); background: white;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"],
section[data-testid="stSidebar"] .stButton > button[kind="primary"] p,
section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"],
section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] p {
    background: var(--scb-blue) !important;
    border: none !important;
    color: #ffffff !important;
    border-radius: 10px;
    font-weight: 700;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover,
section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"]:hover {
    background: var(--scb-blue-dark) !important;
    color: #ffffff !important;
}

section[data-testid="stSidebar"] hr { margin: 1rem 0; border-color: var(--scb-border); }
section[data-testid="stSidebar"] h4 { display: none; }

.stButton > button[kind="primary"],
.stButton > button[kind="primary"] p,
.stButton > button[data-testid="baseButton-primary"],
.stButton > button[data-testid="baseButton-primary"] p {
    background: var(--scb-blue) !important;
    border-color: var(--scb-blue) !important;
    color: #ffffff !important;
}
.stButton > button[kind="primary"]:hover,
.stButton > button[kind="primary"]:hover p,
.stButton > button[data-testid="baseButton-primary"]:hover,
.stButton > button[data-testid="baseButton-primary"]:hover p {
    background: var(--scb-blue-dark) !important;
    border-color: var(--scb-blue-dark) !important;
    color: #ffffff !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 71, 186, 0.22);
}
.stButton > button[kind="primary"]:disabled,
.stButton > button[kind="primary"]:disabled p,
.stButton > button[data-testid="baseButton-primary"]:disabled,
.stButton > button[data-testid="baseButton-primary"]:disabled p {
    background: #8eb5e8 !important;
    border-color: #8eb5e8 !important;
    color: #ffffff !important;
    opacity: 0.85;
}

.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    transition: transform 0.12s ease, box-shadow 0.12s ease;
}
.stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0, 71, 186, 0.12); }

div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 12px !important; }

/* Dashboard-style stat cards instead of Streamlit's bare metric look */
div[data-testid="stMetric"] {
    background: white; border: 1px solid var(--scb-border); border-radius: 12px;
    padding: 0.95rem 1.15rem; box-shadow: 0 1px 4px rgba(40, 44, 48, 0.05);
}
div[data-testid="stMetricLabel"] { font-weight: 600; color: var(--scb-text-muted); font-size: 0.82rem; }
div[data-testid="stMetricValue"] { color: var(--scb-blue); font-weight: 800; }

.value-chip {
    display: inline-block; background: var(--scb-blue-soft); color: var(--scb-blue); font-weight: 700;
    padding: 0.15rem 0.55rem; border-radius: 6px; font-size: 0.88rem;
    border: 1px solid #cddff5;
}
.review-field-name { font-weight: 700; color: var(--scb-text); font-size: 0.92rem; margin-bottom: 0.25rem; }
.review-field-name .warn-icon { color: #b5750a; margin-right: 0.35rem; font-size: 1rem; }

/* Bigger, more prominent tab bar */
button[data-baseweb="tab"] {
    font-size: 0.98rem !important;
    font-weight: 600 !important;
    padding: 0.9rem 1.5rem !important;
    color: var(--scb-text-muted) !important;
}
button[data-baseweb="tab"] p { font-size: 0.98rem !important; font-weight: 600 !important; }
button[data-baseweb="tab"][aria-selected="true"] { color: var(--scb-blue) !important; }
[data-baseweb="tab-highlight"] {
    background-color: var(--scb-blue) !important;
    height: 3px !important;
    border-radius: 3px 3px 0 0;
}
[data-baseweb="tab-border"] { background-color: var(--scb-border) !important; }
[data-baseweb="tab-list"] { gap: 0.3rem !important; }

hr { margin: 0.9rem 0; }
</style>
""", unsafe_allow_html=True)


def _sidebar_brand_html() -> str:
    return """
<div class="sidebar-portal-head">
  <div class="sidebar-portal-title">Credit Memo Portal</div>
  <div class="sidebar-portal-sub">Document queue</div>
</div>"""


def header(subtitle: str) -> None:
    st.markdown(f"""
    <div class="scb-header">
      <div class="scb-header-logo">{SCB_LOGO_SVG}</div>
      <div class="scb-header-text">
        <h1>Credit Memo Portal — Proof of Concept</h1>
        <p>{subtitle} Synthetic/test use only — not a production system, not a credit decision.</p>
      </div>
    </div>
    """, unsafe_allow_html=True)


if "runs" not in st.session_state:
    st.session_state.runs = {}  # doc_id -> {name, bytes, document, fields, memo}
if "active_doc" not in st.session_state:
    st.session_state.active_doc = None
if "processing_doc_id" not in st.session_state:
    st.session_state.processing_doc_id = None
if "cancel_requested" not in st.session_state:
    st.session_state.cancel_requested = False
if "proc_thread" not in st.session_state:
    st.session_state.proc_thread = None
if "proc_finished" not in st.session_state:
    st.session_state.proc_finished = False
if "proc_shared" not in st.session_state:
    st.session_state.proc_shared = None
if "batch_pending_ids" not in st.session_state:
    st.session_state.batch_pending_ids = None
if "batch_current_id" not in st.session_state:
    st.session_state.batch_current_id = None


@st.dialog("Cancel processing?")
def _confirm_cancel_dialog() -> None:
    st.markdown(
        "Stop extraction for this document? "
        "The pipeline will finish the current step, then halt. "
        "Progress so far stays in the log — nothing is lost."
    )
    c1, c2 = st.columns(2)
    if c1.button("Yes, stop", type="primary", width="stretch"):
        _request_cancel_processing()
        st.rerun()
    if c2.button("Continue processing", width="stretch"):
        st.rerun()


def _is_processing(doc_id: str | None = None) -> bool:
    active = st.session_state.processing_doc_id
    if doc_id is None:
        return active is not None
    return active == doc_id


def _clear_processing_state() -> None:
    st.session_state.processing_doc_id = None
    st.session_state.cancel_requested = False
    st.session_state.proc_thread = None
    st.session_state.proc_finished = False
    st.session_state.proc_shared = None


def _doc_id(name: str, data: bytes) -> str:
    return hashlib.sha1(name.encode() + data[:1024]).hexdigest()[:10]


def _status_badge_html(run: dict, doc_id: str) -> str:
    if _is_processing(doc_id):
        log = run.get("progress_log") or []
        if log:
            _, phase, _, current, total = pipeline_progress(log)
            return (
                f'<span class="doc-badge doc-badge-processing">'
                f'Processing · {current}/{total}</span>'
            )
        return '<span class="doc-badge doc-badge-processing">Processing</span>'
    if run["memo"] is not None:
        return '<span class="doc-badge doc-badge-done">Memo ready</span>'
    if run["fields"] is None:
        return '<span class="doc-badge doc-badge-pending">Not processed</span>'
    needs = sum(1 for f in run["fields"] if f.status == "needs_review")
    if needs:
        return f'<span class="doc-badge doc-badge-review">{needs} to review</span>'
    return '<span class="doc-badge doc-badge-ready">Ready</span>'


def _sample_companies() -> list[str]:
    return sorted({p.parent.name for p in Path(SAMPLE_DOCS_DIR).glob("**/*.pdf")})


def _company_display(folder: str) -> str:
    return folder.replace("_", " ").title()


def _short_sample_label(path: Path) -> str:
    rel = path.relative_to(SAMPLE_DOCS_DIR)
    folder = rel.parent.name
    stem = rel.stem
    suffix = stem[len(folder) + 1:] if stem.startswith(f"{folder}_") else stem
    labels = {
        "financial_statements_fy2023": "Financial statements · FY2023",
        "financial_statements_fy2024": "Financial statements · FY2024",
        "loan_application": "Loan application",
        "low_quality": "Low quality scan",
    }
    return labels.get(suffix, suffix.replace("_", " ").title())


def _sample_docs_for_company(company: str) -> list[Path]:
    return sorted(Path(SAMPLE_DOCS_DIR).glob(f"{company}/*.pdf"))


def _doc_kind_label(name: str) -> str:
    filename, folder, _ = _doc_display_parts(name)
    if folder:
        # _short_sample_label expects a path rooted at SAMPLE_DOCS_DIR (it calls .relative_to()
        # on it) — `name` here is already the *relative* "<folder>/<filename>" string, so it must
        # be re-rooted, not just joined, or relative_to() raises ValueError.
        return _short_sample_label(Path(SAMPLE_DOCS_DIR) / folder / filename)
    return Path(filename).stem.replace("_", " ").title()


def _queue_item_hint(run: dict, doc_id: str) -> tuple[str, bool]:
    """Return (status line for the card, whether to highlight as active processing)."""
    if _is_processing(doc_id):
        log = run.get("progress_log") or []
        if log:
            _, phase, _, current, total = pipeline_progress(log)
            return f"In progress · {phase} ({current}/{total})", True
        return "In progress…", True
    if run["fields"] is None:
        return "Queued — not processed yet", False
    if run["memo"] is not None:
        return "Memo ready to review and download", False
    needs = sum(1 for f in run["fields"] if f.status == "needs_review")
    if needs:
        return f"{needs} field(s) flagged for review", False
    confirmed = sum(1 for f in run["fields"] if f.status == "confirmed")
    return f"{confirmed} fields confirmed · ready for memo", False


def _doc_display_parts(name: str) -> tuple[str, str, str]:
    """Return (filename, folder hint, full path) for sidebar cards."""
    parts = Path(name).parts
    if len(parts) >= 2:
        return parts[-1], parts[-2], name
    return name, "", name


def _sidebar_doc_card_html(run: dict, doc_id: str, *, active: bool) -> str:
    filename, folder, full = _doc_display_parts(run["name"])
    company = _company_display(folder) if folder else "Uploaded document"
    kind = _doc_kind_label(run["name"])
    size_kb = len(run["bytes"]) / 1024
    badge = _status_badge_html(run, doc_id)
    hint, hint_active = _queue_item_hint(run, doc_id)
    processing = _is_processing(doc_id)
    active_class = " doc-card-active" if active else ""
    processing_class = " doc-card-processing" if processing else ""
    hint_class = " doc-card-hint-active" if hint_active else ""
    return (
        f'<div class="doc-card{active_class}{processing_class}" title="{html.escape(full)}">'
        f'<div class="doc-card-company">{html.escape(company)}</div>'
        f'<div class="doc-card-kind">{html.escape(kind)}</div>'
        f'<div class="doc-card-file">{html.escape(filename)}</div>'
        f'<div class="doc-card-footer">{badge}'
        f'<span class="doc-card-size">{size_kb:.1f} KB</span></div>'
        f'<div class="doc-card-hint{hint_class}">{html.escape(hint)}</div>'
        f"</div>"
    )


def _render_sidebar_queue_items() -> None:
    # No per-item "Open" button here on purpose: switching documents happens via the tabs in the
    # main panel now (one tab per document, plus an Overview tab) — much less clicking than the
    # old sidebar-only navigation. The sidebar is just the queue: what's in it, and remove.
    for doc_id, run in st.session_state.runs.items():
        st.html(_sidebar_doc_card_html(run, doc_id, active=False))
        if st.button("Remove", key=f"remove_{doc_id}", width="stretch"):
            del st.session_state.runs[doc_id]
            if st.session_state.active_doc == doc_id:
                st.session_state.active_doc = None
            st.rerun()


@st.fragment(run_every=0.5)
def _sidebar_queue_live() -> None:
    if not (_is_processing() or st.session_state.batch_pending_ids is not None):
        return
    _render_sidebar_queue_items()


def add_run(name: str, data: bytes) -> str:
    doc_id = _doc_id(name, data)
    if doc_id not in st.session_state.runs:
        st.session_state.runs[doc_id] = {
            "name": name, "bytes": data, "document": None, "fields": None, "memo": None,
            "progress_log": [],
        }
        st.toast(f"Added {name}", icon=":material/description:")
    return doc_id


def _render_log(log: list[dict], placeholder=None, progress_placeholder=None) -> None:
    if progress_placeholder is not None:
        frac, phase, detail, current, total = pipeline_progress(log)
        progress_placeholder.progress(
            frac,
            text=f"{phase} — {detail} ({current}/{total} steps)",
        )
    html_doc = render_live_pipeline_log(log)
    if placeholder is not None:
        with placeholder:
            st.html(html_doc, unsafe_allow_javascript=True)
    else:
        st.html(html_doc, unsafe_allow_javascript=True)


def _flush_log(log: list[dict], placeholder, progress_placeholder=None) -> None:
    _render_log(log, placeholder, progress_placeholder)


def _show_pipeline_log(log: list[dict]) -> None:
    frac, phase, detail, current, total = pipeline_progress(log)
    st.progress(frac, text=f"{phase} — {detail} ({current}/{total} steps)")
    _render_log(log)


def _pipeline_log_label(log: list[dict]) -> str:
    _, phase, _, current, total = pipeline_progress(log)
    if current >= total and log:
        return f"Pipeline log — complete ({total}/{total} steps)"
    if current > 0:
        return f"Pipeline log — {phase} ({current}/{total} steps)"
    return "Pipeline log"


@st.fragment(run_every=2)
def _processing_visual_fragment(doc_id: str) -> None:
    """Lottie + phase caption — refreshed every 2s to avoid flicker from the log poll."""
    if not _is_processing(doc_id):
        return
    log = st.session_state.runs[doc_id].setdefault("progress_log", [])
    st.html(
        render_processing_animation_html(log, animation_id=f"proc-lottie-{doc_id}"),
        unsafe_allow_javascript=True,
    )


@st.fragment(run_every=0.5)
def _processing_log_fragment(doc_id: str) -> None:
    """Refresh log/progress in-place — avoids full-page rerun every few hundred ms."""
    if not _is_processing(doc_id):
        return
    shared = st.session_state.get("proc_shared")
    if shared is not None and shared["done"].is_set():
        _apply_processing_outcome()
        return
    log = st.session_state.runs[doc_id].setdefault("progress_log", [])
    with st.expander(
        _pipeline_log_label(log),
        expanded=True,
        key=f"pipeline_log_live_{doc_id}",
    ):
        progress_placeholder = st.empty()
        log_placeholder = st.empty()
        _flush_log(log, log_placeholder, progress_placeholder)


def process_run_data(
    name: str,
    pdf_bytes: bytes,
    log: list[dict],
    log_placeholder=None,
    progress_placeholder=None,
    cancel_check: Callable[[], bool] | None = None,
) -> dict:
    """Ingest -> extract -> validate. No Streamlit session state — safe in worker threads."""
    def append(entry: dict) -> None:
        log.append(entry)
        if log_placeholder is not None:
            _flush_log(log, log_placeholder, progress_placeholder)

    if cancel_check and cancel_check():
        append(msg_cancelled())
        return {"success": False, "document": None, "fields": None}

    append(msg_ingest_start(name))
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    def progress_cb(field_name: str, i: int, total: int) -> None:
        append(msg_extract_field(field_name, i, total))

    result = run_extraction(
        tmp_path, on_progress=progress_cb, on_log=append, cancel_check=cancel_check,
    )

    if cancel_check and cancel_check():
        append(msg_cancelled())
        return {"success": False, "document": None, "fields": None}
    if result.get("error") == "cancelled":
        append(msg_cancelled())
        return {"success": False, "document": None, "fields": None}
    if result.get("error"):
        append(msg_error(result["error"]))
        return {"success": False, "document": None, "fields": None}

    append(msg_extract_complete())
    return {
        "success": True,
        "document": result["document"],
        "fields": result["fields"],
    }


def _processing_worker(shared: dict) -> None:
    shared["outcome"] = process_run_data(
        shared["name"],
        shared["bytes"],
        shared["log"],
        cancel_check=shared["cancel"].is_set,
    )
    shared["done"].set()


def _start_background_processing(doc_id: str) -> None:
    """Snapshot document data on the main thread, then run extraction in the background."""
    run = st.session_state.runs[doc_id]
    log = run.setdefault("progress_log", [])
    shared = {
        "doc_id": doc_id,
        "name": run["name"],
        "bytes": run["bytes"],
        "log": log,
        "cancel": threading.Event(),
        "done": threading.Event(),
        "outcome": None,
    }
    st.session_state.proc_shared = shared
    st.session_state.processing_doc_id = doc_id
    st.session_state.cancel_requested = False
    st.session_state.proc_finished = False
    thread = threading.Thread(target=_processing_worker, args=(shared,), daemon=True)
    st.session_state.proc_thread = thread
    thread.start()


def _apply_processing_outcome() -> None:
    """Merge worker results into session state — must run on the main Streamlit thread."""
    shared = st.session_state.get("proc_shared")
    if shared is None or not shared["done"].is_set():
        return

    doc_id = shared["doc_id"]
    outcome = shared.get("outcome") or {}
    if outcome.get("success"):
        st.session_state.runs[doc_id]["document"] = outcome["document"]
        st.session_state.runs[doc_id]["fields"] = outcome["fields"]

    st.session_state.proc_shared = None
    _clear_processing_state()
    st.rerun()


def _request_cancel_processing() -> None:
    st.session_state.cancel_requested = True
    shared = st.session_state.get("proc_shared")
    if shared is not None:
        shared["cancel"].set()


# --- Sidebar: upload + document queue --------------------------------------
with st.sidebar:
    st.markdown(_sidebar_brand_html(), unsafe_allow_html=True)

    st.markdown('<p class="sidebar-section-label">Upload</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sidebar-hint">Drop PDF credit documents here, or pick a sample below.</p>',
        unsafe_allow_html=True,
    )
    uploaded_files = st.file_uploader(
        "Upload PDFs", type=["pdf"], accept_multiple_files=True,
        label_visibility="collapsed",
    )
    for uf in uploaded_files or []:
        new_id = add_run(uf.name, uf.getvalue())
        if st.session_state.active_doc is None:
            st.session_state.active_doc = new_id

    with st.expander("Browse sample documents", expanded=False):
        companies = _sample_companies()
        company = st.selectbox(
            "Company",
            companies,
            format_func=_company_display,
            label_visibility="visible",
        )
        company_docs = _sample_docs_for_company(company)
        chosen = st.selectbox(
            "Document",
            company_docs,
            format_func=_short_sample_label,
            label_visibility="visible",
        )
        st.caption(str(chosen.relative_to(SAMPLE_DOCS_DIR)))
        if st.button(":material/add: Add to queue", width="stretch", key="add_sample_doc"):
            label = str(chosen.relative_to(SAMPLE_DOCS_DIR))
            new_id = add_run(label, chosen.read_bytes())
            st.session_state.active_doc = new_id
            st.rerun()

    st.divider()

    run_count = len(st.session_state.runs)
    pending_ids = [d for d, r in st.session_state.runs.items() if r["fields"] is None]
    ready_count = sum(
        1 for r in st.session_state.runs.values()
        if r["fields"] is not None and r["memo"] is None
    )
    st.markdown('<p class="sidebar-section-label">Queue</p>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="queue-stats">'
        f'<span class="queue-stat"><strong>{run_count}</strong> total</span>'
        f'<span class="queue-stat"><strong>{len(pending_ids)}</strong> pending</span>'
        f'<span class="queue-stat"><strong>{ready_count}</strong> ready</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    batch_running = st.session_state.batch_pending_ids is not None
    if len(st.session_state.runs) > 1 and pending_ids:
        if st.button(
            f":material/play_arrow: Process all pending ({len(pending_ids)})",
            type="primary",
            width="stretch",
            disabled=_is_processing() or batch_running,
        ):
            st.session_state.batch_pending_ids = list(pending_ids)
            st.rerun()
    if batch_running:
        st.caption("Batch running in the main panel →")

    if not st.session_state.runs:
        st.markdown(
            '<p class="sidebar-hint">No documents yet. Upload a PDF or add a sample.</p>',
            unsafe_allow_html=True,
        )
    elif _is_processing() or st.session_state.batch_pending_ids is not None:
        _sidebar_queue_live()
    else:
        _render_sidebar_queue_items()

# --- Main panel ---------------------------------------------------------------

# Batch: one document per page rerun (no 350ms polling), completed docs collapsed above.
if st.session_state.batch_pending_ids is not None:
    batch_ids = st.session_state.batch_pending_ids
    total = len(batch_ids)
    completed_count = sum(
        1 for d in batch_ids
        if d in st.session_state.runs and st.session_state.runs[d]["fields"] is not None
    )
    header(subtitle=f"Processing batch — {completed_count}/{total} complete.")
    st.subheader(f":material/sync: Batch processing — {completed_count}/{total} documents")

    for doc_id in batch_ids:
        batch_run = st.session_state.runs.get(doc_id)
        if not batch_run or batch_run["fields"] is None:
            continue
        with st.expander(
            f":material/check_circle: {_pipeline_log_label(batch_run['progress_log'])} — {batch_run['name']}",
            expanded=False,
            key=f"batch_done_{doc_id}",
        ):
            _show_pipeline_log(batch_run["progress_log"])

    next_id = next(
        (d for d in batch_ids if d in st.session_state.runs and st.session_state.runs[d]["fields"] is None),
        None,
    )
    if next_id is None:
        st.session_state.batch_pending_ids = None
        st.session_state.batch_current_id = None
        if st.session_state.active_doc is None and batch_ids:
            st.session_state.active_doc = batch_ids[0]
        st.rerun()

    next_run = st.session_state.runs[next_id]
    st.markdown(f"**Processing now:** {next_run['name']}")
    log = next_run.setdefault("progress_log", [])

    if st.session_state.batch_current_id != next_id:
        st.session_state.batch_current_id = next_id
        log.clear()
        _start_background_processing(next_id)

    if _is_processing(next_id):
        _processing_visual_fragment(next_id)
        _processing_log_fragment(next_id)
    else:
        shared = st.session_state.get("proc_shared")
        if shared is not None and shared["done"].is_set():
            _apply_processing_outcome()
        else:
            with st.expander(
                _pipeline_log_label(log),
                expanded=True,
                key=f"batch_active_{next_id}",
            ):
                _show_pipeline_log(log)

    st.stop()

def _tab_label(doc_id: str) -> str:
    run = st.session_state.runs[doc_id]
    filename, folder, _ = _doc_display_parts(run["name"])
    if folder:
        kind = _doc_kind_label(run["name"])
        short_kind = (kind.replace("Financial statements · ", "")
                          .replace("Loan application", "Loan")
                          .replace("Low quality scan", "Low quality"))
        base = f"{_company_display(folder)} · {short_kind}"
    else:
        base = Path(filename).stem.replace("_", " ").title()
        if len(base) > 28:
            base = base[:26] + "…"

    if _is_processing(doc_id):
        return f":material/sync: {base}"
    if run["memo"] is not None:
        return f":material/task_alt: {base}"
    if run["fields"] is None:
        return f":material/schedule: {base}"
    if any(f.status == "needs_review" for f in run["fields"]):
        return f":material/flag: {base}"
    return f":material/check_circle: {base}"


def render_overview_tab(doc_ids: list[str]) -> None:
    rows = []
    for doc_id in doc_ids:
        run = st.session_state.runs[doc_id]
        filename, folder, _ = _doc_display_parts(run["name"])
        company = _company_display(folder) if folder else "Uploaded document"
        kind = _doc_kind_label(run["name"])
        fields = run["fields"]
        if _is_processing(doc_id):
            status = "Processing…"
        elif fields is None:
            status = "Not processed"
        elif run["memo"] is not None:
            status = "Memo ready"
        else:
            needs = sum(1 for f in fields if f.status == "needs_review")
            status = f"{needs} to review" if needs else "Ready for memo"
        rows.append({
            "Company": company,
            "Document": kind,
            "Status": status,
            "Confirmed": sum(1 for f in fields if f.status == "confirmed") if fields else 0,
            "Needs review": sum(1 for f in fields if f.status == "needs_review") if fields else 0,
        })

    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True,
                  height=min(400, 38 + 35 * len(rows)))

    pending = sum(1 for d in doc_ids if st.session_state.runs[d]["fields"] is None)
    ready = sum(1 for d in doc_ids
                if st.session_state.runs[d]["fields"] is not None
                and st.session_state.runs[d]["memo"] is None)
    done = sum(1 for d in doc_ids if st.session_state.runs[d]["memo"] is not None)
    m1, m2, m3 = st.columns(3)
    m1.metric("Not processed", pending)
    m2.metric("Ready for memo", ready)
    m3.metric("Memo ready", done)

    pending_ids = [d for d in doc_ids if st.session_state.runs[d]["fields"] is None]
    if pending_ids:
        batch_running = st.session_state.batch_pending_ids is not None
        if st.button(
            f":material/play_arrow: Process all pending ({len(pending_ids)})",
            type="primary",
            disabled=_is_processing() or batch_running,
            key="overview_process_all_pending",
        ):
            st.session_state.batch_pending_ids = list(pending_ids)
            st.rerun()

    processed_ids = [d for d in doc_ids if st.session_state.runs[d]["fields"] is not None]
    st.divider()
    st.markdown("#### Overall result")
    st.caption("One PDF covering every document in the queue — the summary above plus each "
               "document's extracted fields and draft memo (where generated).")
    if st.button(":material/summarize: Generate batch report", type="primary",
                  disabled=not processed_ids, key="gen_batch_report"):
        batch_runs = [
            {"name": st.session_state.runs[d]["name"],
             "fields": st.session_state.runs[d]["fields"],
             "memo": st.session_state.runs[d].get("memo")}
            for d in doc_ids
        ]
        batch_pdf_path = Path(tempfile.gettempdir()) / "scb_batch_report.pdf"
        build_batch_report_pdf(batch_runs, batch_pdf_path)
        st.session_state["batch_report_path"] = str(batch_pdf_path)
        st.rerun()

    batch_report_path = st.session_state.get("batch_report_path")
    if batch_report_path and Path(batch_report_path).exists():
        st.download_button(
            ":material/download: Download batch report (PDF)",
            data=Path(batch_report_path).read_bytes(),
            file_name="scb_batch_credit_memo_report.pdf",
            mime="application/pdf",
            key="download_batch_report",
        )


def render_document_detail(doc_id: str) -> None:
    run = st.session_state.runs[doc_id]

    if run["fields"] is None:
        st.subheader(f":material/description: {run['name']}")
        log = run.setdefault("progress_log", [])
        is_processing = _is_processing(doc_id)

        if is_processing:
            if st.session_state.proc_thread is None:
                _start_background_processing(doc_id)
            _processing_visual_fragment(doc_id)
            _processing_log_fragment(doc_id)
        else:
            with st.expander(
                _pipeline_log_label(log),
                expanded=bool(log),
                key=f"pipeline_log_{doc_id}",
            ):
                if log:
                    progress_placeholder = st.empty()
                    log_placeholder = st.empty()
                    _flush_log(log, log_placeholder, progress_placeholder)
                else:
                    st.caption("Press **Process this document** to start.")

        btn_col, cancel_col = st.columns([4, 1])
        with btn_col:
            start_clicked = st.button(
                ":material/play_arrow: Process this document",
                type="primary",
                disabled=is_processing,
                key=f"process_{doc_id}",
            )
        with cancel_col:
            cancel_clicked = st.button(
                "Cancel",
                disabled=not is_processing,
                key=f"cancel_{doc_id}",
            )

        if cancel_clicked:
            _confirm_cancel_dialog()

        if start_clicked and not is_processing:
            log.clear()
            _start_background_processing(doc_id)
            st.rerun()

        return

    with st.expander(
        _pipeline_log_label(run.setdefault("progress_log", [])),
        expanded=False,
        key=f"pipeline_log_done_{doc_id}",
    ):
        _show_pipeline_log(run["progress_log"])

    needs = sum(1 for f in run["fields"] if f.status == "needs_review")
    if needs:
        st.warning(f"Processing complete — **{needs}** field{'s' if needs != 1 else ''} need reviewer attention.")
    else:
        st.success("Processing complete — all extracted fields passed validation. Review the results below.")
    fields = run["fields"]
    document = run.get("document")
    confirmed = [f for f in fields if f.status == "confirmed"]
    needs_review = [f for f in fields if f.status == "needs_review"]

    st.subheader(f":material/description: {run['name']}")
    m1, m2 = st.columns(2)
    m1.metric("Confirmed fields", len(confirmed))
    m2.metric("Needs review", len(needs_review))

    if fields:
        df = pd.DataFrame([
            {
                "Field": f.field_name,
                # Plain typographic symbols here on purpose, not colour emoji — this text goes
                # into a dataframe cell, which renders raw text only (no Streamlit icon shorthand,
                # no HTML), so a "✅" would just look like clip-art. "✓" reads clean either way.
                "Status": "✓ Confirmed" if f.status == "confirmed" else "⚠ Needs review",
                "Value": format_field_display_value(f, document),
                "Page": f.source_page,
                "Confidence": round(f.confidence, 2),
            }
            for f in fields
        ])

        def _highlight_needs_review(row: pd.Series) -> list[str]:
            if row["Status"].startswith("⚠"):
                return ["background-color: #fef3e2; color: #7a5200"] * len(row)
            return [""] * len(row)

        styled = df.style.apply(_highlight_needs_review, axis=1).format({"Confidence": "{:.2f}"})
        st.dataframe(styled, width="stretch", hide_index=True,
                      height=min(320, 38 + 35 * len(df)))
        with st.expander(":material/source: Show sources for all fields"):
            for f in fields:
                marker = ":material/check_circle:" if f.status == "confirmed" else ":material/warning:"
                st.markdown(f"{marker} **{f.field_name}** — p.{f.source_page}: *\"{f.source_snippet}\"*")

    decisions = {}
    if needs_review:
        st.markdown(f"**Needs review ({len(needs_review)})**")
        for f in needs_review:
            with st.container(border=True):
                st.markdown(
                    f'<div class="review-field-name">'
                    f'<span class="msi warn-icon">warning</span>'
                    f'{html.escape(f.field_name)}</div>'
                    f'<span class="value-chip">{html.escape(format_field_display_value(f, document))}</span>',
                    unsafe_allow_html=True,
                )
                st.caption(f"p.{f.source_page} — \"{f.source_snippet}\" · {f.validation_note or ''}")
                c1, c2 = st.columns([3, 1])
                corrected = c1.text_input("Corrected value", value=f.value,
                                            key=f"val_{doc_id}_{f.field_name}",
                                            label_visibility="collapsed")
                confirm = c2.checkbox("Confirm", key=f"confirm_{doc_id}_{f.field_name}")
                if confirm:
                    decisions[f.field_name] = {"value": corrected, "status": "confirmed"}

        if st.button(":material/task_alt: Apply reviewer decisions", key=f"apply_{doc_id}"):
            st.session_state.runs[doc_id]["fields"] = apply_human_review(fields, decisions)
            st.rerun()

    all_confirmed = [f for f in st.session_state.runs[doc_id]["fields"] if f.status == "confirmed"]
    remaining = [f for f in st.session_state.runs[doc_id]["fields"] if f.status == "needs_review"]

    st.divider()
    st.markdown("#### 2. Generate report")
    if st.button(":material/description: Generate draft memo + report", type="primary",
                  disabled=not all_confirmed, key=f"genmemo_{doc_id}"):
        memo_log: list[dict] = []
        with st.container(border=True):
            st.markdown("**Memo log**")
            memo_placeholder = st.empty()

        def append_memo(entry: dict) -> None:
            memo_log.append(entry)
            _flush_log(memo_log, memo_placeholder)

        append_memo(msg_memo_start())

        def memo_progress_cb(title: str, i: int, total: int) -> None:
            append_memo(msg_memo_section(title, i, total))

        memo = synthesize_memo(
            client_name=next((f.value for f in all_confirmed if f.field_name == "company_name"),
                              run["name"]),
            confirmed_fields=all_confirmed,
            open_exceptions=[f.field_name for f in remaining],
            on_progress=memo_progress_cb,
        )
        append_memo(msg_memo_done())
        st.session_state.runs[doc_id]["memo_log"] = memo_log
        st.session_state.runs[doc_id]["memo"] = memo
        st.rerun()

    memo = run.get("memo")
    if memo:
        if run.get("memo_log"):
            with st.container(border=True):
                st.markdown("**Memo log**")
                _show_pipeline_log(run["memo_log"])
        if memo.guardrail_violations:
            st.error("Guardrail violation — this draft contains a figure without a confirmed source:")
            for v in memo.guardrail_violations:
                st.write(f"- {v}")
        else:
            st.success("Every figure in this draft is traceable to a confirmed field.")

        display_sections, sources = build_memo_footnotes(
            memo.sections, all_confirmed, document=run.get("document"),
        )
        with st.container(border=True):
            for section in display_sections:
                st.markdown(f"##### {section['title']}")
                html_text = re.sub(r"\{\{(\d+)\}\}", r"<sup>\1</sup>", section["text"])
                st.markdown(html_text, unsafe_allow_html=True)

            if sources:
                st.markdown("---")
                st.markdown("**Sources**")
                for src in sources:
                    st.caption(f"[{src['number']}] **{src['field_name']}** = {src['value']} "
                               f"— p.{src['page']}: \"{src['snippet']}\"")
        if memo.open_exceptions:
            st.warning(f"Open exceptions (not included above): {', '.join(memo.open_exceptions)}")

        pdf_path = Path(tempfile.gettempdir()) / f"scb_report_{doc_id}.pdf"
        build_live_report_pdf(run["name"], st.session_state.runs[doc_id]["fields"], memo, pdf_path)
        st.download_button(
            ":material/download: Download report (PDF)",
            data=pdf_path.read_bytes(),
            file_name=f"credit_memo_report_{Path(run['name']).stem}.pdf",
            mime="application/pdf",
            key=f"download_{doc_id}",
        )


doc_ids = list(st.session_state.runs.keys())

# Header is rendered exactly once, above the tab bar — tabs (when present) live below it, not
# above, so the page identity is always visible regardless of which document/tab is open.
if not doc_ids:
    header(subtitle="Upload a credit document to see the pipeline extract, cite, and draft a "
                     "memo in real time.")
    st.info(":material/upload_file: Add one or more documents from the sidebar (drag-and-drop, "
            "or pick a sample) to get started. With more than one queued, use "
            "**Process all pending** to run them together instead of one at a time.")
elif len(doc_ids) == 1:
    # Single document: skip the tab bar entirely, nothing to switch between.
    header(subtitle=f"Working on <b>{st.session_state.runs[doc_ids[0]]['name']}</b>.")
    render_document_detail(doc_ids[0])
else:
    header(subtitle=f"{len(doc_ids)} documents in the queue.")
    tabs = st.tabs([":material/dashboard: Overview"] + [_tab_label(d) for d in doc_ids])
    with tabs[0]:
        render_overview_tab(doc_ids)
    for tab, doc_id in zip(tabs[1:], doc_ids):
        with tab:
            render_document_detail(doc_id)

st.markdown(
    '<p class="scb-footer">SCB Credit Memo Portal — internal proof-of-concept. '
    "See poc/SPEC.md and poc/PLAN.md for scope, methodology, and what this does not do.</p>",
    unsafe_allow_html=True,
)
