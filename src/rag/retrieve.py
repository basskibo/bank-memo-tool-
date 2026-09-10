"""The one public entry point: query in, cited chunks out."""
from __future__ import annotations

from src.config import RAG_TOP_K
from src.rag.index import get_index
from src.rag.schemas import RetrievedChunk


def retrieve(query: str, k: int = RAG_TOP_K) -> list[RetrievedChunk]:
    """Top-k policy chunks for `query` (EN or AR), each carrying its doc_id + chunk_id citation.

    Isolated demo (SPEC.md §9) — callers must not feed the result into field extraction or the
    memo. In production the same signature is served by the Risk Agent's Policy Monitor over the
    real corpus.
    """
    return get_index().query(query, k=k)


def retrieve_dicts(query: str, k: int = RAG_TOP_K) -> list[dict]:
    """Plain-dict form for the Streamlit demo / JSON output."""
    return [h.model_dump() for h in retrieve(query, k=k)]
