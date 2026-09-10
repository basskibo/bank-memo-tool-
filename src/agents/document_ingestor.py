"""
Document Ingestor — SPEC.md 3.1.1


Direktna ekstrakcija teksta iz PDF-a (pdfplumber). Ako neka stranica nema izvlačiv text sloj
(skenirana slika — npr. arapski dokument koji je klijent fotokopirao/skenirao), ta stranica se
rasterizuje preko PyMuPDF i šalje na OCR — dva zamenljiva engine-a, birana preko `POC_OCR_ENGINE`
(SPEC.md 8):
  - "tesseract" (default): pytesseract, lang="ara+eng"
  - "vision": rasterizovana stranica se šalje vizuelnom LLM-u preko Ollama (OLLAMA_VISION_MODEL)
  - "mlx_vision": skenirana strana ide na mlx_vlm.server (MLX_VISION_BASE_URL, default :8081).
    Financial Wizard i dalje zove MLX_MODEL na MLX_BASE_URL (:8080). Oba procesa mogu da
    stoje u Mini 24 GB; inference je serijalizovan jednim lock-om.
  - "mlx_vision_extract" (FUSED): isti VL poziv i transkribuje stranu i vadi POC polja sa te
    strane (src/agents/vision_extractor.py). Financial Wizard onda preskače svoj LLM poziv i
    nema swap-a na 14B — bitno brže i tačnije (ekstrakcija čita sliku, ne šumoviti OCR tekst).

Ako OCR i dalje ne da dovoljno teksta (zaista nečitljiv/oštećen dokument, ili engine nije
dostupan), dokument se i dalje odbija sa razlogom — isto ponašanje kao proposal 8.2: ne pokušava
se pogađanje sadržaja kad ni OCR ne pomaže.
"""
import sys
import time
import uuid
from pathlib import Path
from typing import Callable

import pdfplumber
import pymupdf
import pytesseract
from PIL import Image

from src.config import (
    MLX_VISION_BASE_URL,
    MLX_VISION_MODEL,
    OCR_ENGINE,
    OLLAMA_BASE_URL,
    OLLAMA_VISION_MODEL,
    vision_fused_extract_enabled,
)
from src.llm_client import (
    MLX_HTTP_LOCK,
    OLLAMA_VISION_NUM_CTX,
    release_vision_model_for_extract,
)
from src.logging_setup import get_logger
from src.models.schemas import IngestedDocument, IngestedPage

log = get_logger("ingest")

MIN_CHARS_PER_PAGE_FOR_QUALITY = 30  # ispod ovoga smatramo da je ekstrakcija verovatno neuspešna
MIN_CHARS_TO_SKIP_OCR = 10  # ako pdfplumber izvuče makar ovoliko po strani, OCR se i ne pokušava
OCR_LANGS = "ara+eng"  # SPEC.md 8 — testiramo i engleski i arapski OCR u istom pozivu (Tesseract)
OCR_DPI = 300
VISION_OCR_TIMEOUT_SECONDS = 180
# Qwen2.5-VL uses dynamic resolution: more pixels → more visual tokens → slower prefill.
# 1920 keeps table/Indic digits readable without the 2560-px prefill cost on Mini.
VISION_OCR_MAX_DIM = 1920
VISION_OCR_NUM_CTX = OLLAMA_VISION_NUM_CTX
# A financial page is typically 400–800 tokens. 4096 let VL ramble for minutes at ~20 tok/s.
VISION_OCR_MAX_TOKENS = 1024

VISION_OCR_PROMPT = (
    "You are transcribing a scanned bank/financial document page for a credit-review pipeline. "
    "Transcribe ALL visible text on this page exactly as written, preserving reading order "
    "(right to left for Arabic sections, top to bottom).\n\n"
    "Rules:\n"
    "- Do NOT translate anything. Arabic stays Arabic, English stays English.\n"
    "- Do NOT convert numbers between digit scripts. Copy every digit exactly as shown, whether "
    "Eastern Arabic-Indic (١٢٣...) or Western (123...).\n"
    "- Do NOT summarize, explain, pad, or repeat lines.\n"
    "- For tables, output each row as plain text (label, then value), one row per line.\n"
    "- When the last visible line is transcribed, stop immediately. Output only the transcribed "
    "text, nothing else."
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


def _tesseract_missing_message() -> str:
    if sys.platform == "darwin":
        install = "brew install tesseract tesseract-lang"
    else:
        install = "sudo apt install tesseract-ocr tesseract-ocr-ara"
    return (
        "OCR pokušan ali tesseract nije instaliran na sistemu — "
        f"pokreni: {install}"
    )


def _ocr_page_tesseract(image: Image.Image) -> tuple[str, str | None]:
    try:
        return pytesseract.image_to_string(image, lang=OCR_LANGS), None
    except pytesseract.TesseractNotFoundError:
        return "", _tesseract_missing_message()
    except Exception as exc:
        return "", f"OCR (tesseract) nije uspeo: {exc}"


def _ocr_page_vision(
    image: Image.Image,
    page_number: int,
    *,
    keep_alive: str | int = "10m",
) -> tuple[str, str | None]:
    """OCR alternativa preko vizuelnog LLM-a (Ollama). Šalje rasterizovanu stranicu direktno
    modelu kao PNG umesto klasičnog OCR-a — vidi modul docstring i FINDINGS.md."""
    import base64
    import io

    import requests

    # OCR_DPI (300) je podešen za Tesseract; za vision svodimo na VISION_OCR_MAX_DIM (vidi
    # obrazloženje uz tu konstantu — veće = tačnije za Qwen2.5-VL, do granice VRAM-a).
    resized = image.copy()
    resized.thumbnail((VISION_OCR_MAX_DIM, VISION_OCR_MAX_DIM), Image.LANCZOS)

    buf = io.BytesIO()
    resized.save(buf, format="PNG")
    b64_image = base64.b64encode(buf.getvalue()).decode("ascii")

    log.info(
        "Vision OCR start page=%s model=%s keep_alive=%s",
        page_number,
        OLLAMA_VISION_MODEL,
        keep_alive,
    )
    started = time.monotonic()
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_VISION_MODEL,
                "messages": [{"role": "user", "content": VISION_OCR_PROMPT, "images": [b64_image]}],
                "stream": False,
                "keep_alive": keep_alive,
                "options": {
                    "num_ctx": VISION_OCR_NUM_CTX,
                    "temperature": 0,
                    "num_predict": VISION_OCR_MAX_TOKENS,
                },
            },
            timeout=VISION_OCR_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        log.exception(
            "Vision OCR failed page=%s model=%s (%.1fs)",
            page_number,
            OLLAMA_VISION_MODEL,
            time.monotonic() - started,
        )
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
        log.error(
            "Vision OCR HTTP %s page=%s model=%s (%.1fs): %s",
            resp.status_code,
            page_number,
            OLLAMA_VISION_MODEL,
            time.monotonic() - started,
            detail,
        )
        return "", (
            f"Vision OCR (Ollama '{OLLAMA_VISION_MODEL}' @ {OLLAMA_BASE_URL}) za stranu "
            f"{page_number} nije uspeo: HTTP {resp.status_code} — {detail}. Proveri da li je "
            f"model povučen na serveru ('ollama pull {OLLAMA_VISION_MODEL}') i da li server ima "
            "dovoljno memorije da ga učita."
        )

    text = (resp.json().get("message") or {}).get("content", "")
    elapsed = time.monotonic() - started
    if not text.strip():
        log.error("Vision OCR empty response page=%s (%.1fs)", page_number, elapsed)
        return "", f"Vision OCR za stranu {page_number} je vratio prazan odgovor."
    log.info("Vision OCR done page=%s (%.1fs, %s chars)", page_number, elapsed, len(text.strip()))
    return text, None


def _page_image_png_b64(image: Image.Image) -> str:
    import base64
    import io

    resized = image.copy()
    resized.thumbnail((VISION_OCR_MAX_DIM, VISION_OCR_MAX_DIM), Image.LANCZOS)
    buf = io.BytesIO()
    resized.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _ocr_page_mlx_vision(image: Image.Image, page_number: int) -> tuple[str, str | None]:
    """OCR via mlx_vlm.server OpenAI chat (same HTTP stack as mlx text extract)."""
    import requests

    b64_image = _page_image_png_b64(image)
    log.info(
        "MLX vision OCR start page=%s model=%s url=%s max_tokens=%s",
        page_number,
        MLX_VISION_MODEL,
        MLX_VISION_BASE_URL,
        VISION_OCR_MAX_TOKENS,
    )
    started = time.monotonic()
    try:
        with MLX_HTTP_LOCK:
            resp = requests.post(
                f"{MLX_VISION_BASE_URL}/v1/chat/completions",
                json={
                    "model": MLX_VISION_MODEL,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": VISION_OCR_PROMPT},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{b64_image}",
                                    },
                                },
                            ],
                        }
                    ],
                    "temperature": 0,
                    "max_tokens": VISION_OCR_MAX_TOKENS,
                    "stream": False,
                },
                timeout=VISION_OCR_TIMEOUT_SECONDS,
            )
    except Exception as exc:
        log.exception(
            "MLX vision OCR failed page=%s model=%s (%.1fs)",
            page_number,
            MLX_VISION_MODEL,
            time.monotonic() - started,
        )
        return "", (
            f"MLX vision OCR ('{MLX_VISION_MODEL}' @ {MLX_VISION_BASE_URL}) for page "
            f"{page_number} failed (network): {exc}. Start VL next to 14B (do not stop 14B):\n"
            f"  .venv/bin/python -m mlx_vlm server --model {MLX_VISION_MODEL} "
            f"--port 8081 --host 127.0.0.1"
        )

    if not resp.ok:
        try:
            detail = resp.json().get("error", resp.text)
        except ValueError:
            detail = resp.text
        if isinstance(detail, dict):
            detail = detail.get("message") or str(detail)
        log.error(
            "MLX vision OCR HTTP %s page=%s model=%s (%.1fs): %s",
            resp.status_code,
            page_number,
            MLX_VISION_MODEL,
            time.monotonic() - started,
            detail,
        )
        return "", (
            f"MLX vision OCR ('{MLX_VISION_MODEL}' @ {MLX_VISION_BASE_URL}) for page "
            f"{page_number} failed: HTTP {resp.status_code} — {detail}."
        )

    text = ((resp.json().get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    elapsed = time.monotonic() - started
    if not text.strip():
        log.error("MLX vision OCR empty response page=%s (%.1fs)", page_number, elapsed)
        return "", f"MLX vision OCR for page {page_number} returned an empty response."
    log.info(
        "MLX vision OCR done page=%s (%.1fs, %s chars)",
        page_number,
        elapsed,
        len(text.strip()),
    )
    return text, None


def ingest_document(
    file_path: str | Path,
    on_page_ocr: Callable[[int, int], None] | None = None,
    on_status: Callable[[str], None] | None = None,
) -> IngestedDocument:
    """`on_page_ocr(i, total)` se zove neposredno pre pokušaja OCR-a nad stranom `i` (od ukupno
    `total`) — jedini način da UI pokaže granularniji napredak dok traje spor CPU-only vision
    poziv, pošto sam ingest korak inače broji kao jedan neprozirni makro-korak (SPEC.md nema
    zahtev za ovo, čisto UX)."""
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    pages: list[IngestedPage] = []
    ocr_notes: list[str] = []
    ocr_doc: pymupdf.Document | None = None  # lenjo otvoren — samo ako neka strana zaista zatreba OCR
    warned_bad_engine = False  # upozori samo jednom po dokumentu, ne po strani
    fused = vision_fused_extract_enabled()
    fused_ran = False  # True tek kad je fused VL grana STVARNO obradila makar jednu skeniranu stranu
    fused_fields: list[dict] = []

    with pdfplumber.open(file_path) as pdf:
        total_pages = len(pdf.pages)
        page_texts = [(i, page.extract_text() or "") for i, page in enumerate(pdf.pages, start=1)]
        ocr_page_numbers = [
            i for i, text in page_texts if len(text.strip()) < MIN_CHARS_TO_SKIP_OCR
        ]
        attempted_vision = False
        log.info(
            "Ingest %s — %s page(s), OCR engine=%s, OCR pages=%s",
            file_path.name,
            total_pages,
            OCR_ENGINE,
            len(ocr_page_numbers),
        )
        if OCR_ENGINE in ("mlx_vision", "mlx_vision_extract") and ocr_page_numbers:
            from src.mlx_servers import ensure_mlx_vision

            ensure_mlx_vision(on_status=on_status)

        for (i, text), page in zip(page_texts, pdf.pages, strict=True):
            ocr_used = False
            if i in ocr_page_numbers:
                if on_page_ocr:
                    on_page_ocr(i, total_pages)
                if ocr_doc is None:
                    ocr_doc = pymupdf.open(file_path)
                try:
                    image = _rasterize_page(ocr_doc, i)
                except Exception as exc:
                    ocr_notes.append(f"Rasterizacija strane {i} nije uspela: {exc}")
                    image = None

                if image is not None:
                    known_engines = ("tesseract", "vision", "mlx_vision", "mlx_vision_extract")
                    if OCR_ENGINE not in known_engines and not warned_bad_engine:
                        warned_bad_engine = True
                        ocr_notes.append(
                            f"POC_OCR_ENGINE='{OCR_ENGINE}' nije prepoznat (očekuje se "
                            f"'tesseract', 'vision', 'mlx_vision' ili 'mlx_vision_extract') — "
                            f"tiho se koristi 'tesseract' kao fallback."
                        )
                    if OCR_ENGINE == "vision":
                        attempted_vision = True
                        ocr_text, ocr_error = _ocr_page_vision(image, i, keep_alive="10m")
                    elif OCR_ENGINE == "mlx_vision_extract":
                        from src.agents.vision_extractor import extract_page

                        ocr_text, page_fields, ocr_error = extract_page(
                            image, i, _classify_document_type("\n".join(p.text for p in pages)),
                        )
                        fused_ran = True
                        fused_fields.extend(page_fields)
                    elif OCR_ENGINE == "mlx_vision":
                        ocr_text, ocr_error = _ocr_page_mlx_vision(image, i)
                    else:
                        log.info("OCR page %s/%s engine=tesseract langs=%s", i, total_pages, OCR_LANGS)
                        ocr_text, ocr_error = _ocr_page_tesseract(image)
                    if ocr_error:
                        log.error("OCR page %s/%s failed: %s", i, total_pages, ocr_error)
                        ocr_notes.append(ocr_error)
                    if len(ocr_text.strip()) > len(text.strip()):
                        text = ocr_text
                        ocr_used = True
            pages.append(IngestedPage(page_number=i, text=text, source_file=file_path.name, ocr_used=ocr_used))

    if ocr_doc is not None:
        ocr_doc.close()
    if attempted_vision:
        release_vision_model_for_extract()

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
        quality_notes = (
            reason if not ocr_notes else reason + " " + " ".join(dict.fromkeys(ocr_notes))
        )
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
        # Fused engine already extracted the fields from the page images — Financial Wizard
        # consumes these instead of calling a text LLM. MUST stay None for a digital PDF that
        # never hit the fused VL branch (no scanned pages) — otherwise the normal text extract
        # is silently skipped and every field comes back empty.
        vision_prefetched_fields=(fused_fields if (fused and fused_ran) else None),
    )
