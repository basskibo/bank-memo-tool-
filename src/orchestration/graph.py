"""
Orkestracija — SPEC.md 3.2 (redosled izvršavanja).

LangGraph pokriva automatizovani deo: ingest -> extract -> validate.
Ljudski review (SPEC.md dijagram, [HUMAN REVIEW] koraci) se namerno NE modeluje kao LangGraph
interrupt u POC-u — implementiran je kao eksplicitan poziv iz review UI-ja (src/review/app.py)
između ove automatizovane faze i sinteze memoranduma. Razlog: puni interrupt/checkpoint setup je
produkciona briga (proposal sekcija 4.4), a POC treba da dokaže pristup, ne infrastrukturu.
"""
from typing import Callable, TypedDict

from langgraph.graph import END, StateGraph

from src.agents.citation_validator import validate_citations
from src.agents.document_ingestor import ingest_document
from src.agents.financial_wizard import extract_fields
from src.config import OCR_ENGINE, mlx_autoswap_enabled, vision_fused_extract_enabled
from src.llm_client import LLMNotConfigured, check_provider_ready
from src.logging_setup import get_logger
from src.models.schemas import ExtractedField, IngestedDocument
from src.review.pipeline_messages import (
    msg_ingest_done,
    msg_ingest_ocr_page,
    msg_mlx_loading,
    msg_validate_done,
    msg_validate_field,
    msg_validate_start,
)

log = get_logger("pipeline")


class PipelineState(TypedDict):
    file_path: str
    document: IngestedDocument | None
    fields: list[ExtractedField]
    error: str | None
    on_progress: Callable[[str, int, int], None] | None
    on_log: Callable[[dict], None] | None
    cancel_check: Callable[[], bool] | None


def node_ingest(state: PipelineState) -> PipelineState:
    on_log = state.get("on_log")

    def on_page_ocr(i: int, total: int) -> None:
        if on_log:
            on_log(msg_ingest_ocr_page(i, total, OCR_ENGINE))

    def on_status(message: str) -> None:
        if on_log:
            role = "vision" if "VL" in message else "text"
            on_log(msg_mlx_loading(role))

    try:
        document = ingest_document(
            state["file_path"], on_page_ocr=on_page_ocr, on_status=on_status,
        )
        if on_log:
            on_log(msg_ingest_done(document))
        return {**state, "document": document}
    except Exception as exc:  # noqa: BLE001 — POC: surface any ingestion failure to state
        log.exception("Ingest failed: %s", exc)
        return {**state, "error": f"ingest failed: {exc}"}


def node_extract(state: PipelineState) -> PipelineState:
    if state.get("error") or state["document"] is None:
        return state
    cancel_check = state.get("cancel_check")
    on_log = state.get("on_log")
    try:
        # Fused vision engine already produced the fields from the page images while the VL
        # model was loaded — no text model, no swap. Everything else swaps in the 14B here.
        prefetched = state["document"].vision_prefetched_fields is not None
        if mlx_autoswap_enabled() and not (vision_fused_extract_enabled() and prefetched):
            from src.mlx_servers import ensure_mlx_text

            def on_status(message: str) -> None:
                if on_log:
                    on_log(msg_mlx_loading("text"))

            ensure_mlx_text(on_status=on_status)
        fields = extract_fields(
            state["document"],
            on_progress=state.get("on_progress"),
            cancel_check=cancel_check,
        )
    except Exception as exc:  # noqa: BLE001 — POC: surface extract failures to state
        log.exception("Extract failed: %s", exc)
        return {**state, "error": f"extract failed: {exc}"}
    if cancel_check and cancel_check():
        log.info("Extract cancelled")
        return {**state, "fields": fields, "error": "cancelled"}
    return {**state, "fields": fields}


def node_validate(state: PipelineState) -> PipelineState:
    if state.get("error") or state["document"] is None:
        return state
    if state.get("cancel_check") and state["cancel_check"]():
        log.info("Validate skipped — cancelled")
        return {**state, "error": "cancelled"}
    on_log = state.get("on_log")
    if on_log:
        on_log(msg_validate_start())

    def on_validate_field(field_name: str, i: int, total: int) -> None:
        if on_log:
            on_log(msg_validate_field(field_name, i, total))

    validated = validate_citations(
        state["fields"], state["document"], on_field=on_validate_field,
    )
    if on_log:
        confirmed = sum(1 for f in validated if f.status == "confirmed")
        needs_review = sum(1 for f in validated if f.status == "needs_review")
        on_log(msg_validate_done(confirmed, needs_review))
    return {**state, "fields": validated}


def build_extraction_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("ingest", node_ingest)
    graph.add_node("extract", node_extract)
    graph.add_node("validate", node_validate)
    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "extract")
    graph.add_edge("extract", "validate")
    graph.add_edge("validate", END)
    return graph.compile()


def run_extraction(
    file_path: str,
    on_progress: Callable[[str, int, int], None] | None = None,
    on_log: Callable[[dict], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> PipelineState:
    """Ingest -> extract -> validate za jedan dokument. Ovo je ono što se meri u PLAN.md Danu 5."""
    initial: PipelineState = {
        "file_path": file_path,
        "document": None,
        "fields": [],
        "error": None,
        "on_progress": on_progress,
        "on_log": on_log,
        "cancel_check": cancel_check,
    }
    try:
        check_provider_ready()
    except LLMNotConfigured as exc:
        log.error("Provider not ready: %s", exc)
        return {**initial, "error": str(exc)}
    app = build_extraction_graph()
    return app.invoke(initial)


def apply_human_review(
    fields: list[ExtractedField], decisions: dict[str, dict]
) -> list[ExtractedField]:
    """
    Primeni ljudske odluke na needs_review polja.
    decisions: {field_name: {"value": str, "status": "confirmed"}} — poziva se iz review UI-ja.
    SPEC.md 4.4 princip: svaka izmena mora biti eksplicitna akcija reviewer-a, ne automatska.
    """
    updated = []
    for field in fields:
        decision = decisions.get(field.field_name)
        if decision:
            field = field.model_copy(
                update={
                    "value": decision.get("value", field.value),
                    "status": decision.get("status", field.status),
                    "validation_note": (field.validation_note or "") + " [reviewer confirmed/corrected]",
                }
            )
        updated.append(field)
    return updated
