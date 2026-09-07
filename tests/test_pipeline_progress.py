from src.review.pipeline_messages import (
    EXTRACT_FIELD_COUNT,
    PIPELINE_MAX_STEPS,
    msg_extract_complete,
    msg_extract_field,
    msg_ingest_done,
    msg_ingest_start,
    msg_validate_field,
    msg_validate_start,
    pipeline_progress,
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
