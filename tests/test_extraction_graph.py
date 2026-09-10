import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm_client import LLMNotConfigured
from src.models.schemas import IngestedDocument, IngestedPage
from src.orchestration.graph import node_extract, run_extraction
from src.review.pipeline_messages import STAGE_ERROR, msg_error


def _doc() -> IngestedDocument:
    return IngestedDocument(
        document_id="test-doc",
        source_file="doc.pdf",
        document_type="financial_statement",
        quality_ok=True,
        pages=[IngestedPage(page_number=1, text="Acme", source_file="doc.pdf")],
    )


def test_run_extraction_preflight_returns_error_without_invoking_graph():
    with (
        patch(
            "src.orchestration.graph.check_provider_ready",
            side_effect=LLMNotConfigured("ANTHROPIC_API_KEY nije podešen"),
        ),
        patch("src.orchestration.graph.build_extraction_graph") as build,
    ):
        result = run_extraction("missing.pdf")

    assert result["error"] is not None
    assert "ANTHROPIC_API_KEY" in result["error"]
    build.assert_not_called()


def test_node_extract_surfaces_auth_typeerror_as_state_error():
    state = {
        "file_path": "doc.pdf",
        "document": _doc(),
        "fields": [],
        "error": None,
        "on_progress": None,
        "on_log": None,
        "cancel_check": None,
    }
    with patch(
        "src.orchestration.graph.extract_fields",
        side_effect=TypeError(
            "Could not resolve authentication method. Expected one of api_key, "
            "auth_token, or credentials to be set."
        ),
    ):
        result = node_extract(state)

    assert result["error"] is not None
    assert "extract failed" in result["error"]
    assert "authentication" in result["error"].lower()


def test_msg_error_is_highlighted_terminal_entry():
    entry = msg_error("ANTHROPIC_API_KEY nije podešen")
    assert entry["stage"] == STAGE_ERROR
    assert entry["highlight"] is True
