"""
Turn a document's extracted fields into policy-lookup queries and run them (SPEC.md §9 demo,
applied to real extraction output).

This is the seam a production Risk Agent / Policy Monitor would use — but here it is READ-ONLY:
it never changes an ExtractedField, never writes to the memo, and a retrieved passage is a
pointer for a human reviewer, not a compliance verdict. It is opt-in in the portal.
"""
from __future__ import annotations

from pydantic import BaseModel

from src.config import RAG_TOP_K
from src.models.schemas import ExtractedField
from src.rag.retrieve import retrieve
from src.rag.schemas import RetrievedChunk


class PolicyCheckItem(BaseModel):
    topic: str
    query: str
    hits: list[RetrievedChunk]


def _by_name(fields: list[ExtractedField]) -> dict[str, ExtractedField]:
    return {f.field_name: f for f in fields}


def build_policy_queries(
    fields: list[ExtractedField], document_type: str
) -> list[tuple[str, str]]:
    """(topic, query) pairs seeded with whatever the pipeline actually extracted."""
    f = _by_name(fields)
    company = f["company_name"].value if "company_name" in f else "the applicant"
    queries: list[tuple[str, str]] = []

    if document_type == "loan_application":
        amount = f.get("requested_facility_amount")
        if amount:
            unit = f" {amount.unit}" if amount.unit else ""
            queries.append((
                "Facility limits & tenor",
                f"A facility of {amount.value}{unit} is requested. What are the tenor limits, "
                f"single-obligor limit and audited-financials requirement?",
            ))
        collateral = f.get("collateral_offered")
        if collateral:
            queries.append((
                "Collateral & LTV",
                f"Collateral offered: {collateral.value[:300]}. What loan-to-value and coverage "
                f"ratios apply to this type of collateral?",
            ))

    if document_type == "financial_statement":
        queries.append((
            "Credit-risk ratio thresholds",
            "What are the minimum DSCR, leverage, current ratio and interest coverage thresholds "
            "for a term facility?",
        ))

    existing = f.get("existing_bank_facilities")
    if existing:
        queries.append((
            "Existing facilities & concentration",
            f"Existing bank facilities: {existing.value[:300]}. What single-obligor and "
            f"concentration limits apply?",
        ))

    queries.append((
        "Prohibited / restricted activity",
        f"Is the business of {company} a prohibited or restricted activity for credit?",
    ))
    return queries


def run_policy_check(
    fields: list[ExtractedField], document_type: str, k: int = RAG_TOP_K
) -> list[PolicyCheckItem]:
    out: list[PolicyCheckItem] = []
    for topic, query in build_policy_queries(fields, document_type):
        out.append(PolicyCheckItem(topic=topic, query=query, hits=retrieve(query, k=k)))
    return out
