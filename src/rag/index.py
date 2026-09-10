"""
In-memory vector index over the policy chunks.

Store is a numpy matrix + a parallel list of PolicyChunk metadata — the FAISS-equivalent minimum
(SPEC.md §8 sanctions "Chroma/FAISS in-memory"). Swap this class for a Chroma collection in
production; `retrieve()` does not change.

The embedding model is a small multilingual sentence encoder (config.RAG_EMBED_MODEL) run on CPU.
First call downloads ~470 MB and takes a few seconds; after that, indexing the whole corpus is
well under a second and a query is instant.
"""
from __future__ import annotations

import threading

from src.config import RAG_EMBED_MODEL, RAG_TOP_K
from src.logging_setup import get_logger
from src.rag.corpus import build_chunks
from src.rag.schemas import PolicyChunk, RetrievedChunk

log = get_logger("rag")

_LOCK = threading.Lock()
_INDEX: "PolicyIndex | None" = None


class RagNotAvailable(RuntimeError):
    pass


class PolicyIndex:
    def __init__(self, chunks: list[PolicyChunk], model_name: str = RAG_EMBED_MODEL) -> None:
        if not chunks:
            raise RagNotAvailable("Policy corpus is empty — nothing to index.")
        try:
            import numpy as np
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - env guard
            raise RagNotAvailable(
                "RAG demo needs sentence-transformers + numpy: "
                ".venv/bin/pip install sentence-transformers"
            ) from exc

        self._np = np
        self.chunks = chunks
        log.info("Loading embedding model %s", model_name)
        self.model = SentenceTransformer(model_name, device="cpu")
        log.info("Embedding %s policy chunks", len(chunks))
        mat = self.model.encode(
            [c.text for c in chunks], normalize_embeddings=True, show_progress_bar=False,
        )
        self.matrix = np.asarray(mat, dtype="float32")  # (n_chunks, dim), unit-norm rows

    def query(self, text: str, k: int = RAG_TOP_K) -> list[RetrievedChunk]:
        if not text.strip():
            return []
        q = self.model.encode([text], normalize_embeddings=True, show_progress_bar=False)
        q = self._np.asarray(q, dtype="float32")[0]
        scores = self.matrix @ q  # cosine, both sides unit-norm
        order = self._np.argsort(-scores)[: max(1, k)]
        out: list[RetrievedChunk] = []
        for i in order:
            c = self.chunks[int(i)]
            out.append(RetrievedChunk(
                doc_id=c.doc_id, chunk_id=c.chunk_id, lang=c.lang, text=c.text,
                score=round(float(scores[int(i)]), 4),
            ))
        return out


def get_index() -> PolicyIndex:
    """Lazy singleton — build once per process."""
    global _INDEX
    if _INDEX is None:
        with _LOCK:
            if _INDEX is None:
                _INDEX = PolicyIndex(build_chunks())
    return _INDEX


def reset_index() -> None:
    global _INDEX
    with _LOCK:
        _INDEX = None
