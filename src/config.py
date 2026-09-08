"""Konfiguracija POC-a — vidi SPEC.md sekcija 8 (tech stack) za obrazloženje izbora."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Učitaj poc/.env ako postoji (nikad se ne commit-uje — vidi .gitignore).
# Ovo znači: API ključ se podešava lokalno u fajlu, ne kroz shell export ili chat.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# LLM provider — "ollama" (lokalni/mrežni Ollama server) ili "api" (Anthropic).
# Ovo je konfigurabilno tačno kako SPEC.md sekcija 8 predviđa — isti interfejs (complete_json)
# za oba, pozivaoci (financial_wizard.py, narrative_synthesizer.py) ne znaju koji se koristi.
LLM_PROVIDER = os.environ.get("POC_LLM_PROVIDER", "api").strip().lower()

# --- provider: ollama ---
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")

# --- provider: api (Anthropic) ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
LLM_MODEL = os.environ.get("POC_LLM_MODEL", "claude-haiku-4-5-20251001")

# OCR engine za stranice bez izvlačivog text sloja (SPEC.md 3.1.1) — "tesseract" (default,
# pytesseract) ili "vision" (rasterizovana stranica se šalje vizuelnom LLM-u preko Ollama umesto
# klasičnom OCR-u — vidi evaluation/FINDINGS.md "Vision-LLM alternative" za zašto).
OCR_ENGINE = os.environ.get("POC_OCR_ENGINE", "tesseract").strip().lower()
OLLAMA_VISION_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "llama3.2-vision")

SAMPLE_DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "sample_docs")


def sample_doc_path(filename: str) -> Path:
    """Resolve a sample PDF by filename (searches company subfolders under sample_docs/)."""
    root = Path(SAMPLE_DOCS_DIR)
    direct = root / filename
    if direct.is_file():
        return direct
    matches = sorted(root.glob(f"**/{filename}"))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise FileNotFoundError(f"Ambiguous sample doc: {filename}")
    raise FileNotFoundError(f"Sample doc not found: {filename}")


def iter_sample_docs() -> list[Path]:
    """All sample PDFs, sorted by company folder then filename."""
    return sorted(Path(SAMPLE_DOCS_DIR).glob("**/*.pdf"))
