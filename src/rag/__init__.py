"""
RAG — minimal, isolated policy-lookup demo (SPEC.md §9).

NOT part of the ingest → extract → validate graph. Does not touch extracted fields or the memo.
The point is only to answer: does dumb fixed-size chunking + a small multilingual embedding +
cosine retrieval actually return the RIGHT policy paragraph for a query (EN or AR), with a
citation? Same "nothing without evidence" discipline as the Citation Validator.

Public contract:
    from src.rag import retrieve
    hits = retrieve("What is the maximum SME tenor?", k=3)
    # -> list[RetrievedChunk]: {text, doc_id, chunk_id, lang, score}

Swap `PolicyIndex`'s numpy store for Chroma/OpenSearch later; the contract stays.
"""
from src.rag.retrieve import retrieve
from src.rag.schemas import PolicyChunk, RetrievedChunk

__all__ = ["retrieve", "RetrievedChunk", "PolicyChunk"]
