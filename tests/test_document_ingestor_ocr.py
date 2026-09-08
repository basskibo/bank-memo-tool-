"""
Testovi za OCR granu Document Ingestor-a (SPEC.md 3.1.1) — sintetički skenirani arapski dokumenti
generisani preko sample_docs/generate_arabic_scanned_docs.py.
"""
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pdfplumber
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import src.agents.document_ingestor as document_ingestor
from src.agents.document_ingestor import ingest_document
from src.config import sample_doc_path

TESSERACT_AVAILABLE = shutil.which("tesseract") is not None
FS_DOC = "nile_delta_foods_financial_statements_fy2024_arabic_scan.pdf"
LOAN_DOC = "nile_delta_foods_loan_application_arabic_scan.pdf"


def test_scanned_arabic_document_has_no_extractable_text_layer():
    # Ako ovo padne, generator pravi tekst-PDF a ne sken — OCR grana se onda nikad ne bi ni testirala.
    with pdfplumber.open(sample_doc_path(FS_DOC)) as pdf:
        text = pdf.pages[0].extract_text() or ""
    assert text.strip() == ""


def test_missing_ocr_binary_rejects_gracefully_not_crash(monkeypatch):
    """I bez tesseract-a instaliranog, ingest_document ne sme da baci exception — mora da vrati
    jasan razlog u quality_notes (SPEC.md 8.2 princip: ne pogađaj sadržaj).

    Namerno fiksira OCR_ENGINE na 'tesseract' bez obzira na ambijentalni .env (regresija
    2026-09-08: ovaj test je pokušavao pravi mrežni poziv i čekao pun timeout kad je neko lokalno
    promenio POC_OCR_ENGINE=vision u .env — testovi ne smeju zavisiti od tuđe .env konfiguracije)."""
    monkeypatch.setattr(document_ingestor, "OCR_ENGINE", "tesseract")
    doc = ingest_document(sample_doc_path(FS_DOC))
    if not TESSERACT_AVAILABLE:
        assert doc.quality_ok is False
        assert "tesseract" in (doc.quality_notes or "").lower()


@pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="tesseract-ocr nije instaliran na sistemu")
@pytest.mark.xfail(
    reason=(
        "Poznat, dokumentovan nalaz (evaluation/FINDINGS.md, 'OCR / Arabic scanned documents'): "
        "Tesseract-ov ara model ne čita pouzdano istočno-arapske (Indic) cifre koje realni "
        "egipatski dokumenti stvarno koriste u finansijskim tabelama — isti test sa zapadnim "
        "ciframa prolazi 100%, čime je promenljiva izolovana na sam sistem cifara, ne font/layout. "
        "Dokumenti su namerno ostavljeni sa autentičnim ciframa (ne Western workaround) da ovaj "
        "test ostane merilo dok se ne proveri PaddleOCR (proposal-ov pravi izbor motora)."
    ),
    strict=False,
)
def test_ocr_extracts_arabic_financial_statement(monkeypatch):
    monkeypatch.setattr(document_ingestor, "OCR_ENGINE", "tesseract")
    doc = ingest_document(sample_doc_path(FS_DOC))
    assert doc.quality_ok is True
    assert doc.pages[0].ocr_used is True
    assert "١٢٤٬٨٠٠٬٠٠٠" in doc.full_text()  # total assets, istočno-arapske cifre — mora preživeti OCR


@pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="tesseract-ocr nije instaliran na sistemu")
@pytest.mark.xfail(reason="Isti poznat nalaz kao test_ocr_extracts_arabic_financial_statement — vidi FINDINGS.md.", strict=False)
def test_ocr_extracts_arabic_loan_application_amounts(monkeypatch):
    """document_type klasifikacija NIJE ovde proverena namerno — empirijski nalaz (vidi
    evaluation/FINDINGS.md): naslovi/labele u arapskom OCR tekstu su dovoljno izobličeni da
    substring-based klasifikacija promaši (Tesseract povremeno pogrešno detektuje RTL smer na
    kraćim naslovnim linijama)."""
    monkeypatch.setattr(document_ingestor, "OCR_ENGINE", "tesseract")
    doc = ingest_document(sample_doc_path(LOAN_DOC))
    assert doc.quality_ok is True
    assert doc.pages[0].ocr_used is True
    full_text = doc.full_text()
    assert "٢٥٬٠٠٠٬٠٠٠" in full_text  # requested_facility_amount, istočno-arapske cifre
    assert "٤٢٬٠٠٠٬٠٠٠" in full_text  # collateral valuation, istočno-arapske cifre


def test_ocr_uses_vision_engine_when_configured(monkeypatch):
    """Mockovan Ollama vision poziv (bez pravog servera/modela) — proverava da
    document_ingestor ispravno rasterizuje stranicu, pozove Ollama /api/chat sa slikom, i
    iskoristi vraćen tekst kao OCR rezultat. Vidi evaluation/FINDINGS.md 'Vision-LLM alternative'
    za zašto je ova grana dodata (Tesseract/PaddleOCR ne čitaju pouzdano istočno-arapske cifre)."""
    monkeypatch.setattr(document_ingestor, "OCR_ENGINE", "vision")

    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {
        "message": {"content": "شركة دلتا النيل للأغذية ش.م.م\nإجمالي الأصول ١٢٤٬٨٠٠٬٠٠٠"}
    }

    with patch("requests.post", return_value=fake_response) as mock_post:
        doc = ingest_document(sample_doc_path(FS_DOC))

    assert mock_post.called
    _, kwargs = mock_post.call_args
    assert "images" in kwargs["json"]["messages"][0]  # slika stvarno poslata modelu
    assert doc.pages[0].ocr_used is True
    assert doc.quality_ok is True
    assert "١٢٤٬٨٠٠٬٠٠٠" in doc.full_text()


def test_ocr_vision_engine_http_error_surfaces_response_body(monkeypatch):
    """Regresija za bag nađen uživo (2026-09-08): kad Ollama vrati HTTP grešku (npr. 500 jer
    nema dovoljno memorije da učita model), poruka MORA da uključi telo odgovora — generičko
    'requests.HTTPError' bez detalja ne pomaže nikom da dijagnostikuje šta se stvarno desilo."""
    monkeypatch.setattr(document_ingestor, "OCR_ENGINE", "vision")

    fake_response = MagicMock()
    fake_response.ok = False
    fake_response.status_code = 500
    fake_response.json.return_value = {"error": "model requires more system memory than is available"}
    fake_response.text = '{"error": "model requires more system memory than is available"}'

    with patch("requests.post", return_value=fake_response):
        doc = document_ingestor.ingest_document(sample_doc_path(FS_DOC))

    assert doc.quality_ok is False
    assert "model requires more system memory" in (doc.quality_notes or "")
    assert "500" in (doc.quality_notes or "")


def test_ocr_vision_engine_unreachable_rejects_gracefully_not_crash(monkeypatch):
    """Ako Ollama vision server nije dostupan (npr. model još nije povučen), ingest_document i
    dalje ne sme da baci exception — ista disciplina kao za tesseract granu."""
    monkeypatch.setattr(document_ingestor, "OCR_ENGINE", "vision")

    with patch("requests.post", side_effect=ConnectionError("mock: server not reachable")):
        doc = ingest_document(sample_doc_path(FS_DOC))

    assert doc.quality_ok is False
    assert "vision ocr" in (doc.quality_notes or "").lower()
