from src.review.pipeline_messages import (
    EXTRACT_FIELD_COUNT,
    PIPELINE_MAX_STEPS,
    format_pct,
    msg_error,
    msg_extract_complete,
    msg_extract_field,
    msg_ingest_done,
    msg_ingest_ocr_page,
    msg_ingest_start,
    msg_validate_field,
    msg_validate_start,
    pipeline_progress,
    runtime_model_label,
)


def test_pipeline_progress_empty():
    frac, phase, _, current, total = pipeline_progress([])
    assert frac == 0.0
    assert phase == "Ready"
    assert current == 0
    assert total == PIPELINE_MAX_STEPS


def test_pipeline_progress_extract_step():
    from src.models.schemas import IngestedDocument, IngestedPage

    doc = IngestedDocument(
        document_id="test-doc",
        source_file="doc.pdf",
        document_type="financial_statement",
        quality_ok=True,
        pages=[IngestedPage(page_number=1, text="x", source_file="doc.pdf")],
    )
    log = [msg_ingest_start("doc.pdf"), msg_ingest_done(doc)]
    log.append(msg_extract_field("company_name", 1, EXTRACT_FIELD_COUNT))
    log.append(msg_extract_field("requested_facility_amount", 9, EXTRACT_FIELD_COUNT))

    frac, phase, _, current, total = pipeline_progress(log)
    assert phase == "Financial Wizard"
    assert current == 11  # 2 ingest + 9 extract
    assert total == PIPELINE_MAX_STEPS
    assert frac < 1.0


def test_pipeline_progress_caps_when_log_duplicated():
    log = [msg_ingest_start("doc.pdf")]
    log.extend(msg_extract_field("company_name", 9, EXTRACT_FIELD_COUNT) for _ in range(40))

    _, _, _, current, total = pipeline_progress(log)
    assert current == 11
    assert current <= total


def test_pipeline_progress_complete():
    log = [msg_extract_complete()]
    frac, phase, _, current, total = pipeline_progress(log)
    assert frac == 1.0
    assert phase == "Complete"
    assert current == total == PIPELINE_MAX_STEPS


def test_pipeline_progress_validate_step():
    log = [msg_validate_start(), msg_validate_field("company_name", 3, EXTRACT_FIELD_COUNT)]
    _, phase, _, current, total = pipeline_progress(log)
    assert phase == "Citation Validator"
    assert current == 2 + EXTRACT_FIELD_COUNT + 1 + 3
    assert current <= total


def test_pipeline_progress_error_is_stopped():
    log = [msg_ingest_start("doc.pdf"), msg_error("ANTHROPIC_API_KEY nije podešen")]
    _, phase, detail, current, total = pipeline_progress(log)
    assert phase == "Stopped"
    assert "ANTHROPIC_API_KEY" in detail
    assert current < total


def test_vision_ocr_progress_has_no_cpu_warning():
    entry = msg_ingest_ocr_page(1, 2, "vision")
    assert "OCR strana 1/2" in entry["message"]
    assert "Ollama" in entry["message"]
    assert "CPU" not in entry["message"]
    assert "minuti" not in entry["message"]


def test_mlx_vision_ocr_progress_label():
    entry = msg_ingest_ocr_page(1, 2, "mlx_vision")
    assert "mlx-vlm" in entry["message"]
    assert "Ollama" not in entry["message"]


def test_format_pct_is_scannable():
    assert format_pct(0) == "0%"
    assert format_pct(0.42) == "42%"
    assert format_pct(0.8) == "80%"
    assert format_pct(1) == "100%"
    assert format_pct(0.98) == "98%"


def test_runtime_model_label_ingest_is_pdfplumber():
    log = [msg_ingest_start("acme.pdf")]
    assert runtime_model_label(log) == "pdfplumber (no LLM)"


def test_runtime_model_label_extract_uses_chat_model():
    from src.llm_client import active_chat_model, short_model_id

    log = [msg_extract_field("company_name", 1, EXTRACT_FIELD_COUNT)]
    assert runtime_model_label(log) == short_model_id(active_chat_model())


def test_runtime_model_label_mlx_ocr():
    from src.review.pipeline_messages import ocr_model_label

    entry = msg_ingest_ocr_page(1, 2, "mlx_vision")
    assert runtime_model_label([entry]) == ocr_model_label("mlx_vision")
    assert ocr_model_label("mlx_vision") in entry["message"]


def test_mlx_loading_message_is_model_loader():
    from src.review.pipeline_messages import msg_mlx_loading, runtime_model_label

    vision = msg_mlx_loading("vision")
    assert vision["label"] == "Model loader"
    assert "VL" in vision["message"]
    text = msg_mlx_loading("text")
    assert "14B" in text["message"]
    assert "vl" in runtime_model_label([vision]).lower() or "Qwen" in runtime_model_label([vision])


def test_runtime_model_label_validate_is_rules():
    log = [msg_validate_start()]
    assert runtime_model_label(log) == "citation rules (no LLM)"
