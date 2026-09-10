"""Data contracts for the RAG demo. Kept tiny on purpose."""
from __future__ import annotations

from pydantic import BaseModel, Field

Lang = str  # "en" | "ar"


class PolicyChunk(BaseModel):
    doc_id: str          # source file stem, e.g. "en_sme_lending"
    chunk_id: str        # f"{doc_id}#{n}"
    lang: Lang
    text: str
    char_start: int      # offset in the source document (for a precise citation)
    char_end: int


class RetrievedChunk(BaseModel):
    doc_id: str
    chunk_id: str
    lang: Lang
    text: str
    score: float = Field(ge=-1.0, le=1.0)  # cosine similarity

    def citation(self) -> str:
        return f"{self.doc_id} · {self.chunk_id}"
