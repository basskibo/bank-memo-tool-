"""
Data contracts između capability-ja. Ovo je kod-ogledalo SPEC.md sekcije 3.1 —
ako menjaš nešto ovde, prvo izmeni SPEC.md pa onda ovo.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# Fiksan skup polja za POC — SPEC.md sekcija 6. Namerno se ne širi bez izmene spec-a.
POC_FIELD_NAMES: list[str] = [
    "company_name",
    "reporting_period",
    "total_assets",
    "total_liabilities",
    "total_equity",
    "annual_revenue",
    "net_income",
    "existing_bank_facilities",
    "requested_facility_amount",
    "collateral_offered",
]

CONFIDENCE_THRESHOLD = 0.7  # SPEC.md sekcija 4 — guardrail


class IngestedPage(BaseModel):
    page_number: int
    text: str
    source_file: str
    ocr_used: bool = False  # True ako je tekst dobijen OCR granom (SPEC.md 3.1.1), ne direktnom ekstrakcijom


class IngestedDocument(BaseModel):
    document_id: str
    source_file: str
    document_type: str  # "financial_statement" | "loan_application" | "unknown"
    pages: list[IngestedPage]
    quality_ok: bool
    quality_notes: str | None = None

    def full_text(self) -> str:
        return "\n\n".join(f"[PAGE {p.page_number}]\n{p.text}" for p in self.pages)


class ExtractedField(BaseModel):
    field_name: str
    value: str
    unit: str | None = None
    source_document_id: str
    source_page: int
    source_snippet: str
    confidence: float = Field(ge=0.0, le=1.0)
    status: Literal["confirmed", "needs_review"]
    validation_note: str | None = None


class MemoSection(BaseModel):
    title: str
    text: str
    cited_fields: list[str] = Field(default_factory=list)


class DraftMemo(BaseModel):
    client_name: str
    sections: list[MemoSection]
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    open_exceptions: list[str] = Field(default_factory=list)
    guardrail_violations: list[str] = Field(default_factory=list)
