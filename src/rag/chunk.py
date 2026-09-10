"""
Deliberately dumb fixed-size chunking with overlap (SPEC.md §9 / proposal §5).

NOT semantic / LLM chunking — the whole point is that it is simple and measurable. EN and AR
get different window sizes because Arabic carries more meaning per character (proposal §5 asks
for language-specific chunking).
"""
from __future__ import annotations

import re

from src.config import (
    RAG_CHUNK_CHARS_AR,
    RAG_CHUNK_CHARS_EN,
    RAG_CHUNK_OVERLAP_AR,
    RAG_CHUNK_OVERLAP_EN,
)
from src.rag.schemas import Lang, PolicyChunk

_ARABIC = re.compile(r"[؀-ۿ]")
_WS = re.compile(r"\s+")


def detect_lang(text: str) -> Lang:
    """>=15% Arabic-script characters (of non-space chars) → 'ar', else 'en'."""
    stripped = re.sub(r"\s", "", text)
    if not stripped:
        return "en"
    arabic = len(_ARABIC.findall(stripped))
    return "ar" if arabic / len(stripped) >= 0.15 else "en"


def _window(lang: Lang) -> tuple[int, int]:
    if lang == "ar":
        return RAG_CHUNK_CHARS_AR, RAG_CHUNK_OVERLAP_AR
    return RAG_CHUNK_CHARS_EN, RAG_CHUNK_OVERLAP_EN


def _normalize(text: str) -> str:
    # A chunk is a retrieval unit, not a formatted page — collapse ALL whitespace to single
    # spaces so a rule that wraps across a line still matches and embeds cleanly.
    return _WS.sub(" ", text).strip()


def chunk_document(doc_id: str, raw_text: str, lang: Lang | None = None) -> list[PolicyChunk]:
    text = _normalize(raw_text)
    lang = lang or detect_lang(text)
    size, overlap = _window(lang)
    step = max(1, size - overlap)

    chunks: list[PolicyChunk] = []
    n = len(text)
    start = 0
    idx = 0
    while start < n:
        end = min(n, start + size)
        # don't cut mid-word: back up to the last whitespace if we're not at the end
        if end < n:
            back = text.rfind(" ", start + step // 2, end)
            if back != -1:
                end = back
        piece = text[start:end].strip()
        if piece:
            chunks.append(PolicyChunk(
                doc_id=doc_id, chunk_id=f"{doc_id}#{idx}", lang=lang,
                text=piece, char_start=start, char_end=end,
            ))
            idx += 1
        if end >= n:
            break
        start = end - overlap if end - overlap > start else end
    return chunks
