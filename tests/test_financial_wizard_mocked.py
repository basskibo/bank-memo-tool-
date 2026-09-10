"""
Smoke test za novu per-field strategiju iz financial_wizard.py, sa mockovanim LLM pozivom
(ne traži pravi Ollama/Anthropic pristup). Simulira tipično "šarmantno nepouzdano" ponašanje
malog modela: nekad goli objekat, nekad {} kad polje ne postoji, nekad niz od jedne stavke.
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents.document_ingestor import ingest_document
from src.agents.financial_wizard import _parse_one_field, _sanitize_source_snippet, extract_fields
from src.config import sample_doc_path


def fake_complete_json(system: str, user: str, max_tokens: int = 4096):
    # Izvuci koje polje se traži iz user prompta (isti format kao u financial_wizard.py)
    field_name = user.split("Field to extract: ", 1)[1].split("\n", 1)[0]

    if field_name == "company_name":
        return {"field_name": "company_name", "value": "Acme Trading LLC", "unit": None,
                 "source_page": 1, "source_snippet": "Acme Trading LLC", "confidence": 0.95,
                 "status": "confirmed", "validation_note": None}
    if field_name == "total_assets":
        # simulira model koji ipak vrati niz od jedne stavke
        return [{"field_name": "total_assets", "value": "12,450,000", "unit": "USD",
                  "source_page": 2, "source_snippet": "Total Assets 12,450,000", "confidence": 0.9,
                  "status": "confirmed", "validation_note": None}]
    if field_name == "requested_facility_amount":
        return {}  # polje ne postoji u ovom dokumentu

    # sva ostala polja: simuliraj "nisko poverenje" da testiramo guardrail threshold
    return {"field_name": field_name, "value": "unclear", "unit": None, "source_page": 1,
             "source_snippet": "n/a", "confidence": 0.4, "status": "confirmed",
             "validation_note": None}


def test_sanitize_source_snippet_drops_page_markers():
    assert _sanitize_source_snippet("[PAGE 1]") == ""
    assert _sanitize_source_snippet("[PAGE 1]\nLegal name Misr Pharma Distribution S.A.E.") == (
        "Legal name Misr Pharma Distribution S.A.E."
    )


def test_parse_one_field_rejects_page_marker_as_snippet_body():
    field = _parse_one_field(
        {
            "field_name": "company_name",
            "value": "Misr Pharma Distribution S.A.E.",
            "unit": None,
            "source_page": 1,
            "source_snippet": "[PAGE 1]",
            "confidence": 0.95,
            "status": "confirmed",
            "validation_note": None,
        },
        "company_name",
        "doc-1",
    )
    assert field is not None
    assert field.source_snippet == ""


def test_extract_fields_handles_mixed_model_response_shapes():
    doc = ingest_document(sample_doc_path("acme_trading_financial_statements_fy2023.pdf"))

    with (
        patch("src.agents.financial_wizard.extract_batch_enabled", return_value=False),
        patch("src.agents.financial_wizard.complete_json", side_effect=fake_complete_json),
    ):
        fields = extract_fields(doc)

    by_name = {f.field_name: f for f in fields}

    assert "requested_facility_amount" not in by_name  # {} -> ispravno izostavljeno

    assert by_name["company_name"].status == "confirmed"
    assert by_name["total_assets"].value == "12,450,000"  # niz-od-jedne-stavke ispravno raspakovan

    # guardrail: confidence 0.4 < CONFIDENCE_THRESHOLD mora prebaciti u needs_review
    # čak i kad model kaže status="confirmed"
    other_field = by_name["net_income"]
    assert other_field.status == "needs_review"
    assert "below confidence threshold" in (other_field.validation_note or "")


def test_extract_fields_skips_loan_only_on_financial_statement():
    doc = ingest_document(sample_doc_path("acme_trading_financial_statements_fy2023.pdf"))
    calls = []

    def capture(system: str, user: str, max_tokens: int = 4096):
        calls.append(user)
        return fake_complete_json(system, user, max_tokens)

    with (
        patch("src.agents.financial_wizard.extract_batch_enabled", return_value=False),
        patch("src.agents.financial_wizard.complete_json", side_effect=capture),
    ):
        extract_fields(doc)

    blob = "\n".join(calls)
    assert "requested_facility_amount" not in blob
    assert "collateral_offered" not in blob
    assert "company_name" in blob


def test_extract_fields_batch_one_llm_call():
    doc = ingest_document(sample_doc_path("acme_trading_financial_statements_fy2023.pdf"))
    calls = []

    def batch_reply(system: str, user: str, max_tokens: int = 4096):
        calls.append(user)
        assert "Fields to extract" in user
        return [
            {"field_name": "company_name", "value": "Acme Trading LLC", "unit": None,
             "source_page": 1, "source_snippet": "Acme Trading LLC", "confidence": 0.95,
             "status": "confirmed", "validation_note": None},
            {"field_name": "total_assets", "value": "12,450,000", "unit": "USD",
             "source_page": 2, "source_snippet": "Total Assets 12,450,000", "confidence": 0.9,
             "status": "confirmed", "validation_note": None},
            {"field_name": "net_income", "value": "unclear", "unit": None, "source_page": 1,
             "source_snippet": "n/a", "confidence": 0.4, "status": "confirmed",
             "validation_note": None},
            {"field_name": "total_liabilities", "value": "8,200,000", "unit": "USD",
             "source_page": 2, "source_snippet": "Total Liabilities 8,200,000", "confidence": 0.9,
             "status": "confirmed", "validation_note": None},
            {"field_name": "total_equity", "value": "4,250,000", "unit": "USD",
             "source_page": 2, "source_snippet": "Total Equity 4,250,000", "confidence": 0.9,
             "status": "confirmed", "validation_note": None},
        ]

    with (
        patch("src.agents.financial_wizard.extract_batch_enabled", return_value=True),
        patch("src.agents.financial_wizard.complete_json", side_effect=batch_reply),
    ):
        fields = extract_fields(doc)

    assert len(calls) == 1
    by_name = {f.field_name: f for f in fields}
    assert by_name["company_name"].status == "confirmed"
    assert by_name["total_assets"].value == "12,450,000"
    assert by_name["net_income"].status == "needs_review"
    assert "requested_facility_amount" not in by_name
