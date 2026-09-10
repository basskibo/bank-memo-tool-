"""Load the synthetic policy corpus from sample_docs/policy_corpus/*.md."""
from __future__ import annotations

from pathlib import Path

from src.config import POLICY_CORPUS_DIR
from src.rag.chunk import chunk_document, detect_lang
from src.rag.schemas import PolicyChunk


def _lang_from_name(stem: str, text: str) -> str:
    if stem.startswith("en_"):
        return "en"
    if stem.startswith("ar_"):
        return "ar"
    return detect_lang(text)


def load_corpus(corpus_dir: str | Path | None = None) -> list[tuple[str, str, str]]:
    """Returns [(doc_id, lang, raw_text)] for every .md file except README."""
    root = Path(corpus_dir or POLICY_CORPUS_DIR)
    docs: list[tuple[str, str, str]] = []
    for path in sorted(root.glob("*.md")):
        if path.stem.lower() == "readme":
            continue
        text = path.read_text(encoding="utf-8")
        docs.append((path.stem, _lang_from_name(path.stem, text), text))
    return docs


def build_chunks(corpus_dir: str | Path | None = None) -> list[PolicyChunk]:
    chunks: list[PolicyChunk] = []
    for doc_id, lang, text in load_corpus(corpus_dir):
        chunks.extend(chunk_document(doc_id, text, lang))
    return chunks
