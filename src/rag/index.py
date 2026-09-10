"""
Vector index over the policy chunks. Two interchangeable stores, one `.query()` contract:

* ChromaPolicyIndex — local **persistent** DB on disk (`RAG_CHROMA_DIR`, default data/rag_chroma/).
  Survives restarts; re-embeds only when the corpus text changes (tracked by a hash manifest).
  This is the SPEC §8 "Chroma/FAISS" choice. `pip install chromadb`.
* PolicyIndex — numpy matrix rebuilt each process. Zero extra deps, fine for 24 chunks.

Pick with `RAG_STORE=chroma` (default) or `RAG_STORE=memory`. Embeddings come from the same
sentence-transformers model (`RAG_EMBED_MODEL`) in both cases, so results match.
"""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

from src.config import RAG_CHROMA_DIR, RAG_EMBED_MODEL, RAG_STORE, RAG_TOP_K
from src.logging_setup import get_logger
from src.rag.corpus import build_chunks
from src.rag.schemas import PolicyChunk, RetrievedChunk

log = get_logger("rag")

_LOCK = threading.Lock()
_INDEX = None  # ChromaPolicyIndex | PolicyIndex | None
_MODEL = None
_MODEL_LOCK = threading.Lock()


class RagNotAvailable(RuntimeError):
    pass


def _embedder():
    """Shared lazy sentence-transformers model — loaded once per process."""
    global _MODEL
    if _MODEL is None:
        with _MODEL_LOCK:
            if _MODEL is None:
                try:
                    from sentence_transformers import SentenceTransformer
                except ImportError as exc:  # pragma: no cover
                    raise RagNotAvailable(
                        "RAG needs sentence-transformers: .venv/bin/pip install sentence-transformers"
                    ) from exc
                log.info("Loading embedding model %s", RAG_EMBED_MODEL)
                _MODEL = SentenceTransformer(RAG_EMBED_MODEL, device="cpu")
    return _MODEL


def _encode(texts: list[str]):
    import numpy as np

    vecs = _embedder().encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(vecs, dtype="float32")


def _corpus_fingerprint(chunks: list[PolicyChunk]) -> str:
    h = hashlib.sha256()
    h.update(RAG_EMBED_MODEL.encode())
    for c in chunks:
        h.update(f"{c.chunk_id}\x1f{c.text}\n".encode())
    return h.hexdigest()


# --------------------------------------------------------------------------- memory


class PolicyIndex:
    kind = "memory"

    def __init__(self, chunks: list[PolicyChunk]) -> None:
        if not chunks:
            raise RagNotAvailable("Policy corpus is empty — nothing to index.")
        import numpy as np

        self._np = np
        self.chunks = chunks
        log.info("Embedding %s policy chunks (in-memory)", len(chunks))
        self.matrix = _encode([c.text for c in chunks])

    def query(self, text: str, k: int = RAG_TOP_K) -> list[RetrievedChunk]:
        if not text.strip():
            return []
        q = _encode([text])[0]
        scores = self.matrix @ q
        order = self._np.argsort(-scores)[: max(1, k)]
        return [
            RetrievedChunk(
                doc_id=self.chunks[int(i)].doc_id, chunk_id=self.chunks[int(i)].chunk_id,
                lang=self.chunks[int(i)].lang, text=self.chunks[int(i)].text,
                score=round(float(scores[int(i)]), 4),
            )
            for i in order
        ]


# --------------------------------------------------------------------------- chroma


class ChromaPolicyIndex:
    kind = "chroma"
    COLLECTION = "policy"

    def __init__(self, chunks: list[PolicyChunk], persist_dir: str | Path = RAG_CHROMA_DIR) -> None:
        if not chunks:
            raise RagNotAvailable("Policy corpus is empty — nothing to index.")
        try:
            import chromadb
        except ImportError as exc:  # pragma: no cover
            raise RagNotAvailable(
                "RAG_STORE=chroma needs chromadb: .venv/bin/pip install chromadb "
                "(or set RAG_STORE=memory)"
            ) from exc

        self.dir = Path(persist_dir).resolve()
        self.dir.mkdir(parents=True, exist_ok=True)
        self._manifest = self.dir / "manifest.json"
        self.client = chromadb.PersistentClient(path=str(self.dir))
        self.collection = self.client.get_or_create_collection(
            self.COLLECTION, metadata={"hnsw:space": "cosine"}
        )

        fp = _corpus_fingerprint(chunks)
        if self._current_fingerprint() != fp or self.collection.count() != len(chunks):
            self._rebuild(chunks, fp)
        else:
            log.info("Chroma policy index up to date (%s chunks, %s)", len(chunks), self.dir)

    def _current_fingerprint(self) -> str | None:
        try:
            return json.loads(self._manifest.read_text())["fingerprint"]
        except (OSError, ValueError, KeyError):
            return None

    def _rebuild(self, chunks: list[PolicyChunk], fp: str) -> None:
        log.info("(Re)building Chroma policy index → %s (%s chunks)", self.dir, len(chunks))
        # clean slate — the corpus is tiny
        try:
            self.client.delete_collection(self.COLLECTION)
        except Exception:  # noqa: BLE001
            pass
        self.collection = self.client.get_or_create_collection(
            self.COLLECTION, metadata={"hnsw:space": "cosine"}
        )
        embeddings = _encode([c.text for c in chunks]).tolist()
        self.collection.add(
            ids=[c.chunk_id for c in chunks],
            documents=[c.text for c in chunks],
            embeddings=embeddings,
            metadatas=[
                {"doc_id": c.doc_id, "lang": c.lang,
                 "char_start": c.char_start, "char_end": c.char_end}
                for c in chunks
            ],
        )
        self._manifest.write_text(json.dumps(
            {"fingerprint": fp, "model": RAG_EMBED_MODEL, "n_chunks": len(chunks)}, indent=2
        ))

    def query(self, text: str, k: int = RAG_TOP_K) -> list[RetrievedChunk]:
        if not text.strip():
            return []
        res = self.collection.query(
            query_embeddings=_encode([text]).tolist(),
            n_results=max(1, k),
            include=["documents", "metadatas", "distances"],
        )
        out: list[RetrievedChunk] = []
        ids = res["ids"][0]
        for cid, doc, meta, dist in zip(
            ids, res["documents"][0], res["metadatas"][0], res["distances"][0]
        ):
            out.append(RetrievedChunk(
                doc_id=meta.get("doc_id", cid.split("#")[0]),
                chunk_id=cid, lang=meta.get("lang", "en"), text=doc,
                score=round(1.0 - float(dist), 4),  # cosine distance → similarity
            ))
        return out


# --------------------------------------------------------------------------- factory


def build_index(store: str | None = None):
    store = (store or RAG_STORE).strip().lower()
    chunks = build_chunks()
    if store == "memory":
        return PolicyIndex(chunks)
    try:
        return ChromaPolicyIndex(chunks)
    except RagNotAvailable as exc:
        log.warning("%s — falling back to in-memory store", exc)
        return PolicyIndex(chunks)


def get_index():
    """Lazy singleton — build once per process."""
    global _INDEX
    if _INDEX is None:
        with _LOCK:
            if _INDEX is None:
                _INDEX = build_index()
    return _INDEX


def reset_index() -> None:
    global _INDEX
    with _LOCK:
        _INDEX = None
