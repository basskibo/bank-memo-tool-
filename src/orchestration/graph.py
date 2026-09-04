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
from src.models.schemas import ExtractedField, IngestedDocument


class PipelineState(TypedDict):
    file_path: str
    document: IngestedDocument | None
    fields: list[ExtractedField]
    error: str | None
    on_progress: Callable[[str, int, int], None] | None


def node_ingest(state: PipelineState) -> PipelineState:
    try:
        document = ingest_document(state["file_path"])
        return {**state, "document": document}
    except Exception as exc:  # noqa: BLE001 — POC: surface any ingestion failure to state
        return {**state, "error": f"ingest failed: {exc}"}


def node_extract(state: PipelineState) -> PipelineState:
    if state.get("error") or state["document"] is None:
        return state
    fields = extract_fields(state["document"], on_progress=state.get("on_progress"))
    return {**state, "fields": fields}


def node_validate(state: PipelineState) -> PipelineState:
    if state.get("error") or state["document"] is None:
        return state
    validated = validate_citations(state["fields"], state["document"])
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
    file_path: str, on_progress: Callable[[str, int, int], None] | None = None
) -> PipelineState:
    """Ingest -> extract -> validate za jedan dokument. Ovo je ono što se meri u PLAN.md Danu 5."""
    app = build_extraction_graph()
    initial: PipelineState = {
        "file_path": file_path,
        "document": None,
        "fields": [],
        "error": None,
        "on_progress": on_progress,
    }
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
