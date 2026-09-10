import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents.document_ingestor import ingest_document
from src.config import sample_doc_path


def test_ingest_clean_financial_statement():
    doc = ingest_document(sample_doc_path("acme_trading_financial_statements_fy2023.pdf"))
    assert doc.quality_ok is True
    assert doc.document_type == "financial_statement"
    assert len(doc.pages) >= 1
    assert "Acme Trading" in doc.full_text()
    assert "12,450,000" in doc.full_text()  # total assets vrednost mora biti čitljiva


def test_ingest_loan_application():
    doc = ingest_document(sample_doc_path("acme_trading_loan_application.pdf"))
    assert doc.document_type == "loan_application"
    assert "2,000,000" in doc.full_text()


def test_cairo_textile_pdfs_contain_arabic_script_not_tofu():
    """Regresija: ReportLab Helvetica crta arapski kao .notdef (crni kvadrati / nnnn u text sloju)."""
    arabic_letter = re.compile(
        r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
    )
    for filename in (
        "cairo_textile_financial_statements_fy2023.pdf",
        "cairo_textile_financial_statements_fy2024.pdf",
        "cairo_textile_loan_application.pdf",
    ):
        doc = ingest_document(sample_doc_path(filename))
        text = "\n".join(page.text for page in doc.pages)
        assert "Cairo Textile Exports" in text
        arabic_chars = arabic_letter.findall(text)
        assert len(arabic_chars) >= 8, f"{filename} has no Arabic letters in the text layer"
        assert "\ufffd" not in text
        assert "nnnn" not in text.lower()


def test_misr_pharma_loan_arabic_name_is_real_script():
    arabic_letter = re.compile(
        r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
    )
    doc = ingest_document(sample_doc_path("misr_pharma_loan_application.pdf"))
    text = doc.pages[0].text
    assert "Misr Pharma Distribution" in text
    assert len(arabic_letter.findall(text)) >= 8
    assert "nnnn" not in text.lower()


def test_ingest_low_quality_document_still_extracts_text():
    # Ovaj dokument nije skeniran (i dalje je text-PDF), pa se OČEKUJE quality_ok=True na nivou
    # Document Ingestor-a — problem sa njim je SADRŽAJ (konflikti, nejasnoća), ne čitljivost teksta.
    # Taj problem hvata Financial Wizard / Citation Validator, ne Ingestor. Vidi SPEC.md 3.1.1 vs 3.1.2.
    doc = ingest_document(sample_doc_path("beta_supplies_low_quality.pdf"))
    assert doc.quality_ok is True
    assert "Beta Supplies" in doc.full_text()
