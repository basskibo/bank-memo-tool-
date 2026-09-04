"""
Document Ingestor — SPEC.md 3.1.1

POC pojednostavljenje: direktna ekstrakcija teksta iz PDF-a (pdfplumber), bez OCR grane.
Ako testiramo skenirane dokumente, ovde se dodaje pytesseract/pdf2image fallback (SPEC.md 8).
"""
import uuid
from pathlib import Path

import pdfplumber

from src.models.schemas import IngestedDocument, IngestedPage

MIN_CHARS_PER_PAGE_FOR_QUALITY = 30  # ispod ovoga smatramo da je ekstrakcija verovatno neuspešna

FINANCIAL_STATEMENT_MARKERS = ["balance sheet", "income statement"]
LOAN_APPLICATION_MARKERS = ["facility application", "requested facility", "collateral offered"]


def _classify_document_type(full_text: str) -> str:
    lowered = full_text.lower()
    if any(marker in lowered for marker in LOAN_APPLICATION_MARKERS):
        return "loan_application"
    if any(marker in lowered for marker in FINANCIAL_STATEMENT_MARKERS):
        return "financial_statement"
    return "unknown"


def ingest_document(file_path: str | Path) -> IngestedDocument:
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    pages: list[IngestedPage] = []
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append(IngestedPage(page_number=i, text=text, source_file=file_path.name))

    full_text = "\n".join(p.text for p in pages)
    avg_chars = (len(full_text) / len(pages)) if pages else 0

    quality_ok = avg_chars >= MIN_CHARS_PER_PAGE_FOR_QUALITY
    quality_notes = None
    if not quality_ok:
        quality_notes = (
            f"Prosečno {avg_chars:.0f} karaktera po strani — dokument je verovatno skeniran "
            "ili nečitljiv. POC nema OCR granu; dokument se odbija umesto da se nagađa sadržaj "
            "(SPEC.md 8.2 princip)."
        )

    return IngestedDocument(
        document_id=str(uuid.uuid4()),
        source_file=file_path.name,
        document_type=_classify_document_type(full_text),
        pages=pages,
        quality_ok=quality_ok,
        quality_notes=quality_notes,
    )
