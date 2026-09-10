"""Konfiguracija POC-a — vidi SPEC.md sekcija 8 (tech stack) za obrazloženje izbora."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Učitaj poc/.env ako postoji (nikad se ne commit-uje — vidi .gitignore).
# Ovo znači: API ključ se podešava lokalno u fajlu, ne kroz shell export ili chat.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# LLM provider — "mlx" (mlx_lm.server OpenAI HTTP), "ollama", ili "api" (Anthropic).
# Isti complete_json() interfejs; pozivaoci ne znaju koji je aktivan.
LLM_PROVIDER = os.environ.get("POC_LLM_PROVIDER", "api").strip().lower()

# Extract strategy: "auto" = one LLM call for mlx/api (14B+ can return a JSON array),
# per-field for ollama (small models drop fields). Override with 1/0.
_EXTRACT_BATCH_RAW = os.environ.get("POC_EXTRACT_BATCH", "auto").strip().lower()


def extract_batch_enabled() -> bool:
    if _EXTRACT_BATCH_RAW in {"1", "true", "yes", "on", "batch"}:
        return True
    if _EXTRACT_BATCH_RAW in {"0", "false", "no", "off", "per_field"}:
        return False
    # Local models (mlx 7B, ollama) return a sparse/truncated array for a 10-field batch and
    # then fall back to per-field anyway — the batch attempt is just a wasted call. Only the
    # hosted API is reliable enough to do it in one shot.
    return LLM_PROVIDER == "api"

# --- provider: mlx (Apple Silicon, HTTP to mlx_lm.server / mlx_vlm.server — no import mlx in workers) ---
# Two processes, two ports. Native-text extract hits 14B; scanned pages hit VL.
# 14B-4bit (~8 GB) + VL-7B-4bit (~4.5 GB) can both be resident, but Mini is faster
# if only one is loaded. POC_MLX_AUTOSWAP=1 (default) starts the model the pipeline
# needs and stops the other.
def mlx_autoswap_enabled() -> bool:
    if LLM_PROVIDER != "mlx":
        return False
    raw = os.environ.get("POC_MLX_AUTOSWAP", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


MLX_BASE_URL = os.environ.get("MLX_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
MLX_MODEL = os.environ.get(
    "MLX_MODEL",
    "mlx-community/Qwen2.5-7B-Instruct-4bit",
)
MLX_VISION_BASE_URL = os.environ.get("MLX_VISION_BASE_URL", "http://127.0.0.1:8081").rstrip("/")
MLX_VISION_MODEL = os.environ.get(
    "MLX_VISION_MODEL",
    "mlx-community/Qwen2.5-VL-7B-Instruct-4bit",
)

# --- provider: ollama ---
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

# Kad je OCR_ENGINE=vision, Financial Wizard koristi ISTI OLLAMA_VISION_MODEL (text-only chat)
# umesto da menja na OLLAMA_MODEL — to je ono što je na Mini ostavljalo GPU na Stopping....
# OLLAMA_FORCE_VISION_UNLOAD=1 je opciono: jedan keep_alive=0 posle OCR-a, bez /api/ps petlje.
OLLAMA_FORCE_VISION_UNLOAD = os.environ.get("OLLAMA_FORCE_VISION_UNLOAD", "").strip() == "1"

# --- provider: api (Anthropic) ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
LLM_MODEL = os.environ.get("POC_LLM_MODEL", "claude-haiku-4-5-20251001")

# OCR engine za stranice bez izvlačivog text sloja (SPEC.md 3.1.1):
#   "tesseract" (default, pytesseract)
#   "vision" (Ollama VL — FINDINGS.md; na Mini često Stopping... pored mlx_lm)
#   "mlx_vision" (mlx_vlm.server on MLX_VISION_BASE_URL; extract stays on MLX_MODEL)
#   "mlx_vision_extract" (FUSED — VL i transkribuje i vadi polja u jednom pozivu po strani;
#      Financial Wizard preskače LLM poziv, nema swap-a na 14B. Vidi src/agents/vision_extractor.py)
OCR_ENGINE = os.environ.get("POC_OCR_ENGINE", "tesseract").strip().lower()


def vision_fused_extract_enabled() -> bool:
    """True kad OCR i field-extract idu u istom VL pozivu po strani (mlx_vision_extract)."""
    return OCR_ENGINE == "mlx_vision_extract"
# Preporučeni vision model: qwen2.5vl:7b. Benchmark (evaluation/FINDINGS.md) na skeniranom
# arapskom finansijskom izveštaju: 7B čita tabele i istočno-arapske cifre pouzdano (~18/20 po
# strani), dok qwen2.5vl:3b upada u petlju ponavljanja, llama3.2-vision (arh. "mllama") NE radi
# na Ollama llama.cpp backendu, a minicpm-v / glm-ocr haluciniraju na ovom gradivu.
OLLAMA_VISION_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")

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
