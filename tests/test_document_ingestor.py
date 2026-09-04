import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents.document_ingestor import ingest_document
from src.config import SAMPLE_DOCS_DIR


def test_ingest_clean_financial_statement():
    doc = ingest_document(Path(SAMPLE_DOCS_DIR) / "acme_trading_financial_statements_fy2023.pdf")
    assert doc.quality_ok is True
    assert doc.document_type == "financial_statement"
    assert len(doc.pages) >= 1
    assert "Acme Trading" in doc.full_text()
    assert "12,450,000" in doc.full_text()  # total assets vrednost mora biti čitljiva


def test_ingest_loan_application():
    doc = ingest_document(Path(SAMPLE_DOCS_DIR) / "acme_trading_loan_application.pdf")
    assert doc.document_type == "loan_application"
    assert "2,000,000" in doc.full_text()


def test_ingest_low_quality_document_still_extracts_text():
    # Ovaj dokument nije skeniran (i dalje je text-PDF), pa se OČEKUJE quality_ok=True na nivou
    # Document Ingestor-a — problem sa njim je SADRŽAJ (konflikti, nejasnoća), ne čitljivost teksta.
    # Taj problem hvata Financial Wizard / Citation Validator, ne Ingestor. Vidi SPEC.md 3.1.1 vs 3.1.2.
    doc = ingest_document(Path(SAMPLE_DOCS_DIR) / "beta_supplies_low_quality.pdf")
    assert doc.quality_ok is True
    assert "Beta Supplies" in doc.full_text()
