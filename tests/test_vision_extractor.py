import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents import vision_extractor as ve
from src.agents.financial_wizard import extract_fields
from src.models.schemas import IngestedDocument, IngestedPage


def _img():
    return Image.new("RGB", (64, 64), "white")


def _resp(content: str, ok: bool = True, status: int = 200):
    r = MagicMock()
    r.ok = ok
    r.status_code = status
    r.json.return_value = {"choices": [{"message": {"content": content}}]}
    r.text = content
    return r


# ---- single-call path (default) ----

def test_single_call_parses_transcription_and_fields():
    payload = (
        '{"transcription": "Total Assets ١٢٩٬٤٠٠٬٠٠٠",'
        ' "fields": [{"field_name": "total_assets", "value": "١٢٩,٤٠٠,٠٠٠", "unit": "EGP",'
        ' "source_page": 1, "source_snippet": "[PAGE 1] Total Assets ١٢٩٬٤٠٠٬٠٠٠",'
        ' "confidence": 0.95, "status": "confirmed", "validation_note": null}]}'
    )
    with patch("requests.post", return_value=_resp(payload)) as post:
        transcription, fields, err = ve.extract_page(_img(), 1, "financial_statement")

    assert post.call_count == 1  # ONE VL call
    assert err is None
    assert transcription.startswith("Total Assets")
    assert fields[0]["field_name"] == "total_assets"
    assert "[PAGE" not in fields[0]["source_snippet"]
    assert fields[0]["value"] == "129,400,000"  # Arabic-Indic normalised


def test_single_call_drops_empty_value_fields():
    payload = '{"transcription": "text", "fields": [{"field_name": "existing_bank_facilities", "value": "None", "source_page": 1, "source_snippet": "x", "confidence": 0.7, "status": "needs_review"}]}'
    with patch("requests.post", return_value=_resp(payload)):
        _, fields, err = ve.extract_page(_img(), 1, "financial_statement")
    assert err is None and fields == []


def test_single_call_falls_back_to_two_calls_when_no_transcription():
    single = '{"transcription": "", "fields": []}'
    transcribe = "Net profit 9,600,000"
    extract = '[{"field_name": "net_income", "value": "9,600,000", "unit": "EGP", "source_page": 2, "source_snippet": "Net profit 9,600,000", "confidence": 0.9, "status": "confirmed"}]'
    with patch("requests.post", side_effect=[_resp(single), _resp(transcribe), _resp(extract)]) as post:
        transcription, fields, err = ve.extract_page(_img(), 2, "financial_statement")
    assert post.call_count == 3  # 1 single + 2 fallback
    assert transcription == "Net profit 9,600,000"
    assert fields[0]["field_name"] == "net_income"


def test_single_call_falls_back_when_unparseable():
    transcribe = "some text"
    extract = '[]'
    with patch("requests.post", side_effect=[_resp("not json"), _resp(transcribe), _resp(extract)]) as post:
        transcription, fields, err = ve.extract_page(_img(), 1, "unknown")
    assert post.call_count == 3
    assert transcription == "some text"


def test_network_error_on_first_call_falls_back_then_also_fails():
    with patch("requests.post", side_effect=OSError("connection refused")):
        transcription, fields, err = ve.extract_page(_img(), 1, "unknown")
    assert transcription == "" and fields == []
    assert err and "network" in err


# ---- Financial Wizard consumes prefetched fields (no LLM) ----

def _doc_with_prefetched(fields: list[dict], doc_type: str = "financial_statement"):
    return IngestedDocument(
        document_id="d1", source_file="x.pdf", document_type=doc_type,
        pages=[IngestedPage(page_number=1, text="Total Assets 129,400,000", source_file="x.pdf", ocr_used=True)],
        quality_ok=True, quality_notes=None, vision_prefetched_fields=fields,
    )


def test_financial_wizard_consumes_prefetched_without_llm():
    doc = _doc_with_prefetched([{
        "field_name": "total_assets", "value": "129,400,000", "unit": "EGP",
        "source_page": 1, "source_snippet": "Total Assets 129,400,000",
        "confidence": 0.95, "status": "confirmed", "validation_note": None,
    }])
    with patch("src.agents.financial_wizard.complete_json") as llm:
        out = extract_fields(doc)
    llm.assert_not_called()
    assert [f.field_name for f in out] == ["total_assets"]
    assert out[0].value == "129,400,000"


def test_prefetched_keeps_higher_confidence_on_duplicate():
    doc = _doc_with_prefetched([
        {"field_name": "total_assets", "value": "1", "source_page": 1,
         "source_snippet": "a", "confidence": 0.6, "status": "needs_review"},
        {"field_name": "total_assets", "value": "129,400,000", "source_page": 1,
         "source_snippet": "Total Assets 129,400,000", "confidence": 0.95, "status": "confirmed"},
    ])
    out = extract_fields(doc)
    assert len(out) == 1 and out[0].value == "129,400,000"


def test_prefetched_below_threshold_is_forced_to_needs_review():
    doc = _doc_with_prefetched([{
        "field_name": "total_assets", "value": "129,400,000", "source_page": 1,
        "source_snippet": "Total Assets 129,400,000", "confidence": 0.55, "status": "confirmed",
    }])
    out = extract_fields(doc)
    assert out[0].status == "needs_review"


def test_prefetched_drops_loan_only_field_on_financial_statement():
    doc = _doc_with_prefetched([
        {"field_name": "requested_facility_amount", "value": "5", "source_page": 1,
         "source_snippet": "x", "confidence": 0.9, "status": "confirmed"},
    ], doc_type="financial_statement")
    assert extract_fields(doc) == []


def test_empty_prefetched_list_still_skips_llm():
    doc = _doc_with_prefetched([])
    with patch("src.agents.financial_wizard.complete_json") as llm:
        out = extract_fields(doc)
    llm.assert_not_called()
    assert out == []
