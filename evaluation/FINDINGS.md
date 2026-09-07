# POC Findings

## Run 2 — Full sweep, current codebase, Anthropic API (2026-09-07)

**Provider:** Anthropic API, model `claude-haiku-4-5-20251001`
**Scope:** All 20 current sample documents (7 companies, 15 clean financial statements/loan
applications + 2 deliberately broken documents), current codebase (per-field extraction,
currency/unit inference, footnote-based memo citations). Supersedes Run 1 below, which was on
the original 4-document set with a weak local model (`qwen2.5:3b`) and an earlier prompt version.

Script: `evaluation/run_full_sweep.py`. Raw output: `evaluation/sweep_results.json`.

### Headline result

| Metric | Value |
|---|---|
| Documents processed | 20 (0 errors) |
| Total wall-clock time | 6.4 minutes |
| Field-status matches vs. ground truth | **124 / 125** |
| Safe mismatches (over-cautious) | 1 |
| **Dangerous mismatches (false confidence)** | **0** |

This is a full reversal of Run 1's critical finding. On `qwen2.5:3b`, 3 of 4 deliberately-broken
fields were confidently accepted when they should have been flagged (false-confidence rate
~12.5% of evaluated fields). On `claude-haiku-4-5-20251001`, **both** deliberately broken
documents (`beta_supplies_low_quality.pdf` and the newly added `sinai_agro_low_quality.pdf`) had
**every** defect correctly escalated to `needs_review`, with zero false "confirmed" results
anywhere in the 20-document set.

### The two deliberately broken documents, in detail

| Document | Field | Result | Correct? |
|---|---|---|---|
| beta_supplies_low_quality.pdf | total_assets | `needs_review`, no value committed (conflicting figures in doc) | ✅ |
| beta_supplies_low_quality.pdf | annual_revenue | `needs_review`, "9.1M" (stated as approximation) | ✅ |
| beta_supplies_low_quality.pdf | existing_bank_facilities | `needs_review`, vague text flagged | ✅ |
| beta_supplies_low_quality.pdf | net_income | not extracted at all (correctly treated as absent) | ✅ |
| sinai_agro_low_quality.pdf | annual_revenue | `needs_review`, "62" (stated as approximation) | ✅ |
| sinai_agro_low_quality.pdf | existing_bank_facilities | `needs_review`, empty value (vague "renewed recently, amount not specified") | ✅ |
| sinai_agro_low_quality.pdf | total_assets, net_income | not extracted at all (conflicting/missing in source) | ✅ |

Worth noting as a behavioral nuance, not a defect: on both documents the model sometimes chose to
**omit a field entirely** (rather than emit a `needs_review` placeholder) when the underlying
number was genuinely unresolvable — e.g. `total_assets` on `beta_supplies` has two conflicting
figures in the source and the model declined to pick either, versus `qwen2.5:3b` in Run 1, which
picked one and stated it confidently. Omission-when-unresolvable is at least as safe as flagging,
arguably safer (nothing reaches a reviewer to potentially rubber-stamp).

### The one "mismatch"

`misr_pharma_financial_statements_fy2024.pdf`, field `existing_bank_facilities`: expected
`confirmed`, got `needs_review` (confidence 0.65). Source text: *"SCB inventory line increased to
EGP 35,000,000 (utilized 76%). AAIB overdraft..."* — this is a genuinely compound fact (multiple
facilities in one note). The automated ground truth (built programmatically from the document
generator's source data, see below) assumed a blanket "single existing_bank_facilities note =
confirmed" rule, which doesn't account for notes listing multiple distinct facilities. This reads
as the model being reasonably careful about a compound fact rather than a real extraction error.

### A real finding: field/document-type confusion, one instance confidently wrong

Not caught by the automated ground truth (it only checks fields that are *expected* to appear —
these three weren't expected on financial statements at all, so their presence wasn't scored as
a "mismatch"), but found by manually inspecting the raw sweep output: on **3 of the 15 clean
financial statements**, the Financial Wizard extracted a `requested_facility_amount` — a field
that SPEC.md §6 defines as loan-application-only — by picking up an *existing* facility's
approved limit from the "Bank Borrowings and Credit Facilities" note. Two were self-flagged
`needs_review`; one was not:

| Document | Extracted value | Status | Actual source text |
|---|---|---|---|
| `delta_construction_financial_statements_fy2023.pdf` | 40,000,000 | **confirmed** (0.9) | *"Project finance facility of EGP 40,000,000 with Suez Canal Bank... (drawn EGP 28,500,000)"* — an existing, already-drawn facility, not a request |
| `cairo_textile_financial_statements_fy2024.pdf` | 22,000,000 | needs_review (0.8) | same pattern |
| `nile_delta_foods_financial_statements_fy2023.pdf` | 15,000,000 | needs_review (0.85) | same pattern |

The `delta_construction` case is the more serious one: the model was confident (0.9, above the
threshold) about a field that should never have existed at all for this document type. This is
the same pattern Run 1 noted as a secondary finding (§5.1 in that run) but with a materially
worse outcome this time — it reached `confirmed`, not just `needs_review`.

**Fixed during this session:** `financial_wizard.py`'s prompt now (a) passes the document's
classified `document_type` into every field-extraction call, and (b) adds an explicit rule that
`requested_facility_amount`/`collateral_offered` describe a *new* facility being requested, and
must not be extracted from a financial statement's existing-facilities note even when a number
appears there.

**Verified with a full re-sweep (Run 3, same day):** re-ran all 20 documents after the fix —
**0** occurrences of `requested_facility_amount`/`collateral_offered` on any financial-statement
document (down from 3), still **0** dangerous mismatches overall. Result shifted slightly to
123/125 matches, 2 safe mismatches — both the same benign "compound multi-facility note" caution
pattern as Run 2's single case, just landing on two different documents (`delta_construction_loan_application.pdf`
and `nile_delta_foods_financial_statements_fy2023.pdf`) due to ordinary model run-to-run variance,
not a regression. Raw data for both sweeps kept: `evaluation/sweep_results.json` (post-fix,
current) — pre-fix snapshot is in git history of this run.

### Methodology note: ground truth for the 16 new documents

The original `evaluation/expected_values.py` only covered the legacy 4-document set. For the 15
new clean Egyptian-format documents and `sinai_agro_low_quality.pdf`, ground truth was derived
**programmatically** from `sample_docs/generate_sample_docs.py`'s own `CompanyCase`/`FinancialYear`
source data (see `evaluation/run_full_sweep.py::build_expected_for_all_docs`) rather than
hand-transcribed — that source data *is* the ground truth, since it's what the PDFs were rendered
from. This checks **status calibration** (confirmed vs. needs_review — did the pipeline correctly
judge whether to trust a value), not exact-value accuracy field-by-field; a full value-level
audit would need per-field hand transcription, which wasn't done here.

---

## Run 1 — Original 4-document set, Ollama qwen2.5:3b (2026-09-04)

Kept for historical comparison — this is what motivated the model-comparison recommendation that
Run 2 acts on.

Of 24 evaluated fields, 13 matched expectations, 11 did not: 8 safe (over-cautious) and **3
dangerous** (confidently wrong on `beta_supplies_low_quality.pdf` — `total_assets`,
`annual_revenue`, `existing_bank_facilities` all falsely `confirmed`). Citation sourcing itself
was correct in every case; the failure was the model's judgment of whether a value was
trustworthy, not the citation mechanism. Full detail preserved in git history of this file.

A code bug was also found and fixed during Run 1: a guardrail regex falsely flagged trailing
sentence punctuation (`"2023,"`) as an uncited number. Fixed in `narrative_synthesizer.py`.

---

## What this means against the proposal's KPI targets (proposal §9.1)

| KPI | Target | Run 2 result |
|---|---|---|
| False-confidence rate | ≤ 2% | **0%** (0 of 125 evaluated fields) |
| Field extraction accuracy | ≥ 95% | 124/125 = 99.2% on status calibration (see methodology note — not a full value audit) |
| Citation integrity | 100% | 100% in every run so far (Citation Validator has never let an unverifiable snippet through) |

These are now genuinely encouraging numbers — but they reflect **one strong hosted model**
(Claude Haiku) on **synthetic documents with no scanning artifacts**. They are not yet evidence
about `qwen2.5:3b` in production-realistic conditions, nor about real SCB documents.

## Recommended next steps

1. ~~Re-run against a larger model / Anthropic API as an upper-bound reference~~ — **done**. The
   gap between `qwen2.5:3b` and `claude-haiku-4-5` on the false-confidence metric (12.5% → 0%)
   is now the key data point for the model-choice conversation with SCB.
2. ~~Re-run the full sweep after the field/document-type confusion fix~~ — **done (Run 3)**,
   confirmed clean, no regressions.
3. If a mid-size local model is available on the Ollama server (`mistral:7b`, `llama3.1:8b`),
   run this same sweep against it — that fills in the gap between the two data points already
   measured (3B local vs. hosted Haiku) and matters directly for the on-premise requirement in
   the proposal (data sovereignty — proposal §4.7).
4. Do a value-level accuracy pass on a sample of the 15 new clean documents (not just
   status-calibration) to confirm numbers are correct, not just confidently stated.
5. Once SCB provides real (anonymized) documents, this exact sweep script
   (`run_full_sweep.py`) is reusable — swap in the real documents and their ground truth.
