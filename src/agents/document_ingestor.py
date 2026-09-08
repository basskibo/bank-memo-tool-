"""
Document Ingestor — SPEC.md 3.1.1

Direktna ekstrakcija teksta iz PDF-a (pdfplumber). Ako neka stranica nema izvlačiv text sloj
(skenirana slika — npr. arapski dokument koji je klijent fotokopirao/skenirao), ta stranica se
rasterizuje preko PyMuPDF i šalje na OCR — dva zamenljiva engine-a, birana preko `POC_OCR_ENGINE`
(SPEC.md 8):
  - "tesseract" (default): pytesseract, lang="ara+eng"
  - "vision": rasterizovana stranica se šalje vizuelnom LLM-u preko Ollama (OLLAMA_VISION_MODEL,
    npr. "llama3.2-vision") umesto klasičnom OCR-u. Dodato posle empirijskog nalaza
    (evaluation/FINDINGS.md, "Vision-LLM alternative") da ni Tesseract ni PaddleOCR ne čitaju
    pouzdano istočno-arapske (Indic) cifre koje realni egipatski dokumenti stvarno koriste, dok
    vizuelni LLM istu stranu čita tačno.

Ako OCR i dalje ne da dovoljno teksta (zaista nečitljiv/oštećen dokument, ili engine nije
dostupan), dokument se i dalje odbija sa razlogom — isto ponašanje kao proposal 8.2: ne pokušava
se pogađanje sadržaja kad ni OCR ne pomaže.
"""
import uuid
from pathlib import Path

import pdfplumber
import pymupdf
import pytesseract
from PIL import Image

from src.config import OCR_ENGINE, OLLAMA_BASE_URL, OLLAMA_VISION_MODEL
from src.models.schemas import IngestedDocument, IngestedPage

MIN_CHARS_PER_PAGE_FOR_QUALITY = 30  # ispod ovoga smatramo da je ekstrakcija verovatno neuspešna
MIN_CHARS_TO_SKIP_OCR = 10  # ako pdfplumber izvuče makar ovoliko po strani, OCR se i ne pokušava
OCR_LANGS = "ara+eng"  # SPEC.md 8 — testiramo i engleski i arapski OCR u istom pozivu (Tesseract)
OCR_DPI = 300
VISION_OCR_TIMEOUT_SECONDS = 300  # vizuelni modeli su sporiji od teksualnih, posebno na CPU-u

VISION_OCR_PROMPT = (
    "You are transcribing a scanned bank/financial document page for a credit-review pipeline. "
    "Transcribe ALL visible text on this page exactly as written, preserving reading order "
    "(right to left for Arabic sections, top to bottom).\n\n"
    "Rules:\n"
    "- Do NOT translate anything. Arabic stays Arabic, English stays English.\n"
    "- Do NOT convert numbers between digit scripts. Copy every digit exactly as shown, whether "
    "Eastern Arabic-Indic (١٢٣...) or Western (123...).\n"
    "- Do NOT summarize, explain, or add commentary of your own.\n"
    "- For tables, output each row as plain text (label, then value), one row per line.\n"
    "- Output only the transcribed text, nothing else."
)

FINANCIAL_STATEMENT_MARKERS = [
    "balance sheet", "income statement",
    "قائمة المركز المالي", "قائمة الدخل",
]
LOAN_APPLICATION_MARKERS = [
    "facility application", "requested facility", "collateral offered",
    "طلب تسهيل ائتماني", "التسهيل المطلوب", "الضمانات المقدمة", "تسهيل ائتماني",
]


def _contains_marker(text: str, marker: str) -> bool:
    """Substring check, plus the character-reversed form of the marker — Tesseract occasionally
    misdetects Arabic (RTL) line direction and emits the line in reversed character order. This
    is a known Tesseract limitation on noisy/degraded Arabic scans, not specific to our synthetic
    set (SPEC.md 3.1.1 OCR grana)."""
    return marker in text or marker[::-1] in text


def _classify_document_type(full_text: str) -> str:
    lowered = full_text.lower()
    if any(_contains_marker(lowered, marker.lower()) for marker in LOAN_APPLICATION_MARKERS):
        return "loan_application"
    if any(_contains_marker(lowered, marker.lower()) for marker in FINANCIAL_STATEMENT_MARKERS):
        return "financial_statement"
    return "unknown"


def _rasterize_page(doc: pymupdf.Document, page_number: int) -> Image.Image:
    pix = doc[page_number - 1].get_pixmap(dpi=OCR_DPI)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def _ocr_page_tesseract(image: Image.Image) -> tuple[str, str | None]:
    try:
        return pytesseract.image_to_string(image, lang=OCR_LANGS), None
    except pytesseract.TesseractNotFoundError:
        return "", (
            "OCR pokušan ali tesseract-ocr nije instaliran na sistemu — "
            "pokreni: sudo apt install tesseract-ocr tesseract-ocr-ara"
        )
    except Exception as exc:
        return "", f"OCR (tesseract) nije uspeo: {exc}"


def _ocr_page_vision(image: Image.Image, page_number: int) -> tuple[str, str | None]:
    """OCR alternativa preko vizuelnog LLM-a (Ollama). Šalje rasterizovanu stranicu direktno
    modelu kao PNG umesto klasičnog OCR-a — vidi modul docstring i FINDINGS.md."""
    import base64
    import io

    import requests

    # OCR_DPI (300) je podešen za Tesseract; vizuelni modeli interno svode sliku na sopstvenu
    # fiksnu rezoluciju bez obzira na ulaz, pa slanje pune 300 DPI slike samo troši propusni opseg
    # i memoriju servera bez ikakve koristi za tačnost — smanji na razumnu maksimalnu dimenziju.
    resized = image.copy()
    resized.thumbnail((1600, 1600), Image.LANCZOS)

    buf = io.BytesIO()
    resized.save(buf, format="PNG")
    b64_image = base64.b64encode(buf.getvalue()).decode("ascii")

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_VISION_MODEL,
                "messages": [{"role": "user", "content": VISION_OCR_PROMPT, "images": [b64_image]}],
                "stream": False,
            },
            timeout=VISION_OCR_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        return "", (
            f"Vision OCR (Ollama '{OLLAMA_VISION_MODEL}' @ {OLLAMA_BASE_URL}) za stranu "
            f"{page_number} nije uspeo (mrežna greška): {exc}. Proveri da li je server dostupan "
            f"i da li je OLLAMA_BASE_URL tačan u poc/.env."
        )

    if not resp.ok:
        # Ollama-ov error body obično objasni PRAVI razlog (npr. nedovoljno RAM-a za model) —
        # requests.HTTPError.__str__() ga ne uključuje, pa ga ovde eksplicitno pridodajemo.
        try:
            detail = resp.json().get("error", resp.text)
        except ValueError:
            detail = resp.text
        return "", (
            f"Vision OCR (Ollama '{OLLAMA_VISION_MODEL}' @ {OLLAMA_BASE_URL}) za stranu "
            f"{page_number} nije uspeo: HTTP {resp.status_code} — {detail}. Proveri da li je "
            f"model povučen na serveru ('ollama pull {OLLAMA_VISION_MODEL}') i da li server ima "
            "dovoljno memorije da ga učita."
        )

    text = (resp.json().get("message") or {}).get("content", "")
    if not text.strip():
        return "", f"Vision OCR za stranu {page_number} je vratio prazan odgovor."
    return text, None


def ingest_document(file_path: str | Path) -> IngestedDocument:
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    pages: list[IngestedPage] = []
    ocr_notes: list[str] = []
    ocr_doc: pymupdf.Document | None = None  # lenjo otvoren — samo ako neka strana zaista zatreba OCR
    warned_bad_engine = False  # upozori samo jednom po dokumentu, ne po strani

    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            ocr_used = False
            if len(text.strip()) < MIN_CHARS_TO_SKIP_OCR:
                if ocr_doc is None:
                    ocr_doc = pymupdf.open(file_path)
                try:
                    image = _rasterize_page(ocr_doc, i)
                except Exception as exc:
                    ocr_notes.append(f"Rasterizacija strane {i} nije uspela: {exc}")
                    image = None

                if image is not None:
                    if OCR_ENGINE not in ("tesseract", "vision") and not warned_bad_engine:
                        warned_bad_engine = True
                        ocr_notes.append(
                            f"POC_OCR_ENGINE='{OCR_ENGINE}' nije prepoznat (očekuje se tačno "
                            f"'tesseract' ili 'vision') — tiho se koristi 'tesseract' kao "
                            f"fallback. Ako si hteo vision model, postavi POC_OCR_ENGINE=vision "
                            f"i OLLAMA_VISION_MODEL={OCR_ENGINE}."
                        )
                    if OCR_ENGINE == "vision":
                        ocr_text, ocr_error = _ocr_page_vision(image, i)
                    else:
                        ocr_text, ocr_error = _ocr_page_tesseract(image)
                    if ocr_error:
                        ocr_notes.append(ocr_error)
                    if len(ocr_text.strip()) > len(text.strip()):
                        text = ocr_text
                        ocr_used = True
            pages.append(IngestedPage(page_number=i, text=text, source_file=file_path.name, ocr_used=ocr_used))

    if ocr_doc is not None:
        ocr_doc.close()

    full_text = "\n".join(p.text for p in pages)
    avg_chars = (len(full_text) / len(pages)) if pages else 0
    any_ocr = any(p.ocr_used for p in pages)

    quality_ok = avg_chars >= MIN_CHARS_PER_PAGE_FOR_QUALITY
    quality_notes = None
    if not quality_ok:
        reason = (
            f"Prosečno {avg_chars:.0f} karaktera po strani nakon "
            f"{'OCR pokušaja' if any_ocr or ocr_notes else 'direktne ekstrakcije'} "
            f"(engine: {OCR_ENGINE}) — dokument je i dalje verovatno nečitljiv ili oštećen. "
            "Dokument se odbija umesto da se nagađa sadržaj (SPEC.md 8.2 princip)."
        )
        quality_notes = reason if not ocr_notes else reason + " " + " ".join(ocr_notes)
    elif any_ocr:
        n = sum(1 for p in pages if p.ocr_used)
        quality_notes = f"OCR (engine: {OCR_ENGINE}) korišćen za {n} od {len(pages)} strana(e)."

    return IngestedDocument(
        document_id=str(uuid.uuid4()),
        source_file=file_path.name,
        document_type=_classify_document_type(full_text),
        pages=pages,
        quality_ok=quality_ok,
        quality_notes=quality_notes,
    )
