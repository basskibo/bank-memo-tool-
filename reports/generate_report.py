"""
Builds the POC results/findings PDF report from the data observed in Run 1
(evaluation/FINDINGS.md is the narrative source of truth this mirrors).

Run: .venv/bin/python reports/generate_report.py
Output: reports/POC_Findings_Report.pdf
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from reports.pdf_common import (
    body,
    callout_box,
    field_result_table,
    h1,
    h2,
    small,
    subtitle_style,
    title_style,
)

OUT_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Data observed in Run 1 (2026-09-04) — mirrors evaluation/FINDINGS.md.
# Keep in sync manually with FINDINGS.md and expected_values.py if re-generating after a new run.
# ---------------------------------------------------------------------------
FY2023 = [
    {"field": "company_name", "value": "Acme Trading LLC", "page": 1, "status": "confirmed", "expected": "confirmed", "match": "OK"},
    {"field": "reporting_period", "value": "31 December 2023", "page": 1, "status": "confirmed", "expected": "confirmed", "match": "OK"},
    {"field": "total_assets", "value": "12,450,000", "page": 1, "status": "confirmed", "expected": "confirmed", "match": "OK"},
    {"field": "total_liabilities", "value": "7,200,000", "page": 1, "status": "confirmed", "expected": "confirmed", "match": "OK"},
    {"field": "total_equity", "value": "5,250,000", "page": 1, "status": "confirmed", "expected": "confirmed", "match": "OK"},
    {"field": "annual_revenue", "value": "18,300,000", "page": 1, "status": "confirmed", "expected": "confirmed", "match": "OK"},
    {"field": "net_income", "value": "1,120,000", "page": 2, "status": "needs_review", "expected": "confirmed", "match": "MISMATCH"},
    {"field": "existing_bank_facilities", "value": "USD 500,000", "page": 4, "status": "needs_review", "expected": "confirmed", "match": "MISMATCH"},
    {"field": "requested_facility_amount", "value": "1,800,000", "page": 1, "status": "needs_review", "expected": "n/a", "match": "-"},
    {"field": "collateral_offered", "value": "(empty)", "page": 1, "status": "needs_review", "expected": "n/a", "match": "-"},
]

FY2024 = [
    {"field": "company_name", "value": "Acme Trading LLC", "page": 1, "status": "confirmed", "expected": "confirmed", "match": "OK"},
    {"field": "reporting_period", "value": "31 December 2024", "page": 1, "status": "confirmed", "expected": "confirmed", "match": "OK"},
    {"field": "total_assets", "value": "14,100,000", "page": 1, "status": "confirmed", "expected": "confirmed", "match": "OK"},
    {"field": "total_liabilities", "value": "8,050,000", "page": 1, "status": "confirmed", "expected": "confirmed", "match": "OK"},
    {"field": "total_equity", "value": "6,050,000", "page": 1, "status": "confirmed", "expected": "confirmed", "match": "OK"},
    {"field": "annual_revenue", "value": "21,750,000", "page": 1, "status": "needs_review", "expected": "confirmed", "match": "MISMATCH"},
    {"field": "net_income", "value": "1,540,000", "page": 2, "status": "needs_review", "expected": "confirmed", "match": "MISMATCH"},
    {"field": "existing_bank_facilities", "value": "USD 500,000", "page": 1, "status": "needs_review", "expected": "confirmed", "match": "MISMATCH"},
    {"field": "requested_facility_amount", "value": "500,000", "page": 1, "status": "needs_review", "expected": "n/a", "match": "-"},
    {"field": "collateral_offered", "value": "(empty)", "page": 1, "status": "needs_review", "expected": "n/a", "match": "-"},
]

LOAN_APP = [
    {"field": "company_name", "value": "Acme Trading LLC", "page": 1, "status": "needs_review", "expected": "confirmed", "match": "MISMATCH"},
    {"field": "total_assets", "value": "(empty)", "page": 1, "status": "needs_review", "expected": "n/a", "match": "-"},
    {"field": "total_equity", "value": "(empty)", "page": 1, "status": "needs_review", "expected": "n/a", "match": "-"},
    {"field": "annual_revenue", "value": "(empty)", "page": 1, "status": "needs_review", "expected": "n/a", "match": "-"},
    {"field": "net_income", "value": "(empty)", "page": 1, "status": "needs_review", "expected": "n/a", "match": "-"},
    {"field": "existing_bank_facilities", "value": "USD 500,000 overdraft...", "page": 1, "status": "confirmed", "expected": "confirmed", "match": "OK"},
    {"field": "requested_facility_amount", "value": "USD 2,000,000", "page": 1, "status": "needs_review", "expected": "confirmed", "match": "MISMATCH"},
    {"field": "collateral_offered", "value": "USD 3,200,000", "page": 3, "status": "needs_review", "expected": "confirmed", "match": "MISMATCH"},
]

BETA_SUPPLIES = [
    {"field": "company_name", "value": "Beta Supplies Co.", "page": 1, "status": "confirmed", "expected": "n/a", "match": "-"},
    {"field": "reporting_period", "value": "(none)", "page": 1, "status": "needs_review", "expected": "n/a", "match": "-"},
    {"field": "total_assets", "value": "7,150,000", "page": 1, "status": "confirmed", "expected": "needs_review", "match": "MISMATCH"},
    {"field": "total_liabilities", "value": "(empty)", "page": 1, "status": "needs_review", "expected": "n/a", "match": "-"},
    {"field": "total_equity", "value": "(empty)", "page": 1, "status": "needs_review", "expected": "n/a", "match": "-"},
    {"field": "annual_revenue", "value": "9.1M", "page": 1, "status": "confirmed", "expected": "needs_review", "match": "MISMATCH"},
    {"field": "net_income", "value": "(none)", "page": 1, "status": "needs_review", "expected": "needs_review", "match": "OK"},
    {"field": "existing_bank_facilities", "value": "various", "page": 1, "status": "confirmed", "expected": "needs_review", "match": "MISMATCH"},
    {"field": "requested_facility_amount", "value": "(none)", "page": 1, "status": "needs_review", "expected": "n/a", "match": "-"},
    {"field": "collateral_offered", "value": "(empty)", "page": 1, "status": "needs_review", "expected": "n/a", "match": "-"},
]


def build():
    doc = SimpleDocTemplate(
        str(OUT_DIR / "POC_Findings_Report.pdf"), pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
    )
    story = []

    # --- Title page -----------------------------------------------------
    story.append(Spacer(1, 3 * cm))
    story.append(Paragraph("Credit Memo Agent — POC", title_style))
    story.append(Paragraph("Results &amp; Findings Report — Run 1", subtitle_style))
    story.append(Spacer(1, 0.5 * cm))
    meta = [
        ["Date", "2026-09-04"],
        ["Scope", "First complete end-to-end run across all 4 synthetic test documents"],
        ["Provider / Model", "Ollama — qwen2.5:3b @ mcs02.cmu:11434"],
        ["Reference documents", "SPEC.md, PLAN.md, evaluation/ground_truth.md, evaluation/FINDINGS.md"],
    ]
    mt = Table(meta, colWidths=[4 * cm, 12 * cm])
    mt.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(mt)
    story.append(Spacer(1, 1 * cm))

    story.append(callout_box(
        "<b>Headline:</b> the pipeline ran end-to-end without crashing across all 4 documents. "
        "Of 24 fields with a defined expected outcome, 13 matched and 11 did not — but only 3 of "
        "those 11 are dangerous (a value confidently accepted when it should have been flagged), "
        "and all 3 occurred on the one document deliberately built to be ambiguous. "
        "See Section 3.",
        border_color=colors.HexColor("#7a1f1f"), bg_color=colors.HexColor("#fdecec"),
    ))
    story.append(PageBreak())

    # --- Section 1: Executive summary -----------------------------------
    story.append(Paragraph("1. Executive Summary", h1))
    story.append(Paragraph(
        "This report captures the first full run of the Credit Memo Agent proof-of-concept "
        "against four synthetic test documents, using a small local model (qwen2.5:3b) served "
        "over an existing Ollama endpoint. The purpose of this run was not to validate production "
        "KPI targets — it was to answer one specific question defined in SPEC.md: does the "
        "extraction -&gt; citation -&gt; escalation approach work at all, and does it correctly recognize "
        "when NOT to trust a value.", body
    ))
    story.append(Paragraph(
        "The answer is qualified: the architecture holds (every extracted value carried a real, "
        "verifiable citation in every case observed), but the specific model tested here does not "
        "reliably judge when a value is untrustworthy. On the one document built with deliberate "
        "conflicts and ambiguity, it confidently accepted 3 of 4 problematic fields instead of "
        "escalating them for human review. This is precisely the failure mode the POC exists to "
        "catch before any KPI commitment is made to a client.", body
    ))
    story.append(Paragraph(
        "The other 8 mismatches were in the safe direction (over-caution — a correct value flagged "
        "for review it didn't strictly need), which costs reviewer time but does not risk a wrong "
        "memo. Full breakdown in Section 3 and Section 4.", body
    ))

    # --- Section 2: What was tested --------------------------------------
    story.append(Paragraph("2. What Was Tested", h1))
    story.append(Paragraph(
        "Four synthetic PDF documents (no real company data — see sample_docs/README.md), covering "
        "a clean financial statement for two periods, a loan/facility application, and one "
        "document deliberately built with conflicting figures, an unstated currency ambiguity, "
        "and a missing required field. Each document was pushed through the full pipeline: "
        "Document Ingestor -&gt; Financial Wizard (per-field LLM extraction) -&gt; Citation Validator "
        "(deterministic snippet check). See SPEC.md Section 3 for what each capability owns.", body
    ))

    # --- Section 3: Results by document -----------------------------------
    story.append(Paragraph("3. Results by Document", h1))

    story.append(Paragraph("3.1 acme_trading_financial_statements_fy2023.pdf (clean document)", h2))
    story.append(field_result_table(FY2023))
    story.append(Spacer(1, 10))

    story.append(Paragraph("3.2 acme_trading_financial_statements_fy2024.pdf (clean document)", h2))
    story.append(field_result_table(FY2024))
    story.append(Spacer(1, 10))

    story.append(Paragraph("3.3 acme_trading_loan_application.pdf", h2))
    story.append(Paragraph(
        "Two fields (reporting_period, total_liabilities) were skipped by the pipeline's defensive "
        "parsing because the model's response was missing a required key — handled gracefully, "
        "not a crash, but noted here for completeness.", small
    ))
    story.append(field_result_table(LOAN_APP))
    story.append(Spacer(1, 10))

    story.append(Paragraph("3.4 beta_supplies_low_quality.pdf — deliberately broken document", h2))
    story.append(field_result_table(BETA_SUPPLIES))
    story.append(PageBreak())

    # --- Section 4: Critical finding ---------------------------------------
    story.append(Paragraph("4. Critical Finding — Guardrail Does Not Hold on qwen2.5:3b", h1))
    story.append(callout_box(
        "<b>total_assets</b>, <b>annual_revenue</b>, and <b>existing_bank_facilities</b> were all "
        "confidently marked <b>confirmed</b> on beta_supplies_low_quality.pdf, despite the document "
        "containing (by design) a conflicting figure, a stated approximation, and a vague "
        "description respectively. Each should have been <b>needs_review</b>.",
    ))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "This is not a citation-sourcing problem — every one of those three fields carried a real, "
        "verbatim snippet pulled from the actual document text, so the Citation Validator "
        "(a deterministic check, no LLM involved) passed them correctly. The failure is in "
        "content judgment: the model did not recognize that the value it found was unreliable. "
        "That judgment is the entire point of the confidence/status field in the SPEC.md contract "
        "— without it, a human reviewer has no signal telling them which values need a second look.", body
    ))
    story.append(Paragraph(
        "The one field on this document handled correctly was net_income — the model correctly "
        "recognized the value was absent from the document (stated as 'will be provided later') "
        "rather than inventing one, and flagged it for review.", body
    ))

    # --- Section 5: Secondary findings ---------------------------------------
    story.append(Paragraph("5. Secondary Findings", h1))
    story.append(Paragraph("5.1 Field / document-type confusion", h2))
    story.append(Paragraph(
        "On both clean financial statements, the model returned a value for "
        "requested_facility_amount — a field that only applies to loan-application documents per "
        "SPEC.md Section 6 — by mistakenly reusing an unrelated balance-sheet line "
        "('short-term bank facilities'). Both were correctly downgraded to needs_review by the "
        "confidence guardrail, so nothing false reached 'confirmed', but a reviewer still has to "
        "spend time dismissing a field that should not have been generated at all.", body
    ))
    story.append(Paragraph("5.2 Over-caution on unambiguous values", h2))
    story.append(Paragraph(
        "8 of the 11 mismatches are fields stated clearly and once in the source text, yet still "
        "returned with confidence below the 0.7 threshold and routed to needs_review. This is the "
        "safe failure direction, but if it holds at scale it would push most memo fields into the "
        "review queue regardless of document quality, undermining the proposal's 'under 20 "
        "minutes to draft' target (proposal Section 9.1).", body
    ))

    # --- Section 6: Fixed during this run ---------------------------------------
    story.append(Paragraph("6. Known Issue Found and Fixed During This Run", h1))
    story.append(Paragraph(
        "A false positive was found in the memo-generation guardrail itself (a code defect, not a "
        "model finding): the regex comparing numbers written in the generated memo against numbers "
        "present in confirmed fields captured trailing sentence punctuation (e.g. '2023,') as part "
        "of the number, so it failed to match the clean '2023' value and incorrectly flagged every "
        "section of the fy2023 memo as a guardrail violation. This has been fixed in "
        "narrative_synthesizer.py. Noted here so a future run's clean guardrail result isn't read "
        "as a change in model behaviour.", body
    ))

    # --- Section 7: KPI comparison ---------------------------------------
    story.append(Paragraph("7. Comparison Against Proposal KPI Targets", h1))
    story.append(Paragraph(
        "The full Xenon7 proposal (Section 9.1) targets field extraction accuracy of at least 95%, "
        "critical-field accuracy of at least 98%, and a false-confidence rate no higher than 2%. "
        "This run's raw match rate (13/24, about 54%) sits far below that, but is not a fair "
        "comparison yet — this was a stress test of a 3B-parameter model with a fixed per-field "
        "prompting strategy, not a tuned production configuration. The number that IS a fair early "
        "read: the false-confidence proxy from this run (3 of 24 fields evaluated, about 12.5%) is "
        "well above the proposal's 2% ceiling, and is the single most important number to re-check "
        "against a larger model before any KPI commitment is finalized.", body
    ))

    # --- Section 8: Recommendations ---------------------------------------
    story.append(Paragraph("8. Recommended Next Steps", h1))
    steps = [
        "Re-run against a larger model on the same Ollama server (mistral:7b or llama3.1:8b, if "
        "available) and compare the false-confidence rate directly against this baseline.",
        "If no larger local model is available, run the same evaluation via the Anthropic API path "
        "(POC_LLM_PROVIDER=api) as an upper-bound reference point.",
        "Strengthen the 'field does not apply to this document' instruction in financial_wizard.py "
        "— see finding 5.1.",
        "Do not loosen the confidence threshold to reduce over-caution mismatches (5.2) — that is "
        "the safe failure mode. Any tuning should target the critical finding (Section 4) without "
        "touching this one.",
        "Once a model clears the critical finding (no confident wrong answers on the deliberately "
        "broken test document), this POC has answered its core question and the team can move to "
        "PLAN.md Stage 2 planning with real numbers instead of proposal assumptions.",
    ]
    for i, s in enumerate(steps, start=1):
        story.append(Paragraph(f"{i}. {s}", body))

    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "Full narrative version of this report: evaluation/FINDINGS.md. Underlying data: "
        "evaluation/expected_values.py, evaluation/ground_truth.md.", small
    ))

    doc.build(story)
    print(f"Generated {OUT_DIR / 'POC_Findings_Report.pdf'}")


if __name__ == "__main__":
    build()
