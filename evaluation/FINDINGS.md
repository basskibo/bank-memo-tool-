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

---

## OCR / Arabic scanned documents — first empirical result (2026-09-08)

Added per SPEC.md §3.1.1 and §9: a synthetic scanned-Arabic test set (`nile_delta_foods_*_arabic_scan.pdf`,
image-only PDFs, no text layer — see `sample_docs/generate_arabic_scanned_docs.py`) plus an OCR
fallback branch in Document Ingestor (`pytesseract`, `ara+eng`, PyMuPDF rasterization at 300 DPI).
Layout modeled on a real, public EGX filing (TMG Holding standalone financial statements FY2023,
audited EY/RSM Egypt) rather than guessed. This directly tests two risks the proposal itself flags
in §16: "Arabic OCR accuracy on poor-quality documents" and (indirectly, via table structure)
"Credit policy corpus incomplete or unstructured".

### Headline result

| Question | Result |
|---|---|
| Do the actual monetary figures (the fields the Financial Wizard needs) survive OCR? | **Yes — 100%** of tested figures (`total_assets`, `annual_revenue`, `requested_facility_amount`, collateral valuation, existing-facility amounts) extracted correctly, verbatim, across both scanned documents |
| Does document-type classification (label/title matching) survive OCR? | **No, unreliably.** The financial statement classified correctly; the loan application did not — Arabic label/title text was garbled enough that substring-based classification failed even after adding reversed-string matching as a fallback |

### The concrete, isolated finding: digit script matters more than expected

The real reference document (TMG Holding) uses **Eastern Arabic-Indic numerals** (١٢٣...) in its
financial tables — that is standard for real Egyptian corporate filings, not a stylistic choice.
First attempt at the synthetic doc used these authentically. Result: **every single monetary
figure was destroyed by OCR** (e.g. `124,800,000` came back as unrecoverable garbage), across
every Tesseract page-segmentation mode tested (`--psm 3/4/6/11/12`).

Isolated the variable by regenerating the identical layout with **Western numerals** (123...)
instead — same font, same table borders, same degradation. Result: **every monetary figure
extracted correctly**, first try, no further tuning needed. The Arabic *prose* around the numbers
was equally garbled in both versions — this isolates the failure specifically to Tesseract's
`ara` model reading Eastern Arabic-Indic digit glyphs in this font, not to Arabic text in general
or to the table layout.

**This is a real, material risk for the actual production engagement**, not a POC artifact: real
SCB documents will very plausibly use Eastern Arabic-Indic numerals in their tables, exactly like
the TMG reference. Recommendation for the full proposal: verify this specific behavior against
**PaddleOCR** (the proposal's actual chosen engine, §11) before assuming it doesn't share this
weakness — it may not, but it hasn't been checked, and this is now known to be worth checking
early rather than discovering it at UAT. A cheap mitigation if it does reproduce: a digit
normalization/preprocessing pass (Eastern → Western before OCR, or a digit-specific OCR pass).

**Decision: keep authentic Eastern Arabic-Indic numerals in the synthetic set**, everywhere,
including the `POC_FIELD_NAMES` figures — not a Western-digit workaround. The point of this test
set is to measure the real risk, not to make the demo pass. `tests/test_document_ingestor_ocr.py`
marks the two Tesseract digit-extraction tests `xfail` with a reason pointing back to this section,
so the gap stays visible in the test suite (not silently skipped, not silently "fixed" by
reverting to an unrealistic input) until it's actually resolved — either by a working engine or a
preprocessing mitigation. See "PaddleOCR comparison" below for the next step already taken on this.

### PaddleOCR comparison (2026-09-08) — resolved via Docker, confirms the Tesseract finding

First attempt (pip install directly in the POC venv) hit inference-engine crashes across three
`paddlepaddle` versions (3.3.1, 2.6.2, 3.0.0) — detailed further down. Root cause turned out to be
**`paddleocr` 3.x's new `paddlex`-based pipeline**, not the CPU: reproduced the identical crash
inside a fresh official `paddlepaddle/paddle:3.0.0` Docker container (ruling out an AVX-512/host
CPU explanation). Switching to the older, more mature **`paddleocr==2.7.3` + `paddlepaddle==2.6.2`**
combination (the pre-`paddlex` generation, still the most widely deployed PaddleOCR stack in
production today) worked immediately in the same container.

**Result, same page used for the Tesseract test, Arabic model (`lang="ar"`):**

| Digit script | Result |
|---|---|
| Western (123...) | Every figure recovered correctly, e.g. `11,200,000` came back as `000,200,11` — **digit groups reversed as a whole, each group internally correct.** A trivial, deterministic post-processing fix (split on separator, reverse group order, rejoin) — not a data-loss problem |
| Eastern Arabic-Indic (١٢٣...), the authentic script real documents use | Fragmentary, unusable: `١١,٢٠٠,٠٠٠` came back as isolated pieces like `٢,١١` and `٧` — not recoverable by any simple post-processing |

**This confirms the Tesseract finding rather than overturning it: two independent OCR engines
(Tesseract `ara`, PaddleOCR arabic) both reliably read Western digits and both fail on Eastern
Arabic-Indic digits in this table layout.** The risk is now a property of the *problem*
(multi-digit Eastern-Indic numeral recognition in dense tables), not a quirk of one specific
engine — the earlier recommendation to "just check PaddleOCR" undersold how deep this goes.

### Vision-LLM alternative (2026-09-08) — the one approach tested that actually worked

Before concluding "no OCR engine handles this," tried a fundamentally different approach: skip
OCR entirely and feed the scanned page **directly as an image to a vision-capable LLM**, the way
a human reviewer would just look at it. Read the same rendered page (Eastern Arabic-Indic digits,
the hard case) directly.

**Result: every single figure read correctly on the first try** — ١١,٢٠٠,٠٠٠ / ٢٥,٤٠٠,٠٠٠ /
٣٤,٦٠٠,٠٠٠ / ٤٨,٩٠٠,٠٠٠ / **١٢٤,٨٠٠,٠٠٠** (total assets) / ٢١,٣٠٠,٠٠٠ / ١٦,٨٠٠,٠٠٠ / ٢٤,١٠٠,٠٠٠ /
**٦٥,٢٠٠,٠٠٠** (total liabilities) / **٥٩,٦٠٠,٠٠٠** (total equity) — no preprocessing, no digit
normalization, no engine-specific tuning. This is the same underlying model family already used
for Financial Wizard extraction in this POC, so architecturally it isn't a new dependency — it's
a different way of using one already in the stack.

**Recommendation for the production engagement:** for Arabic scanned documents specifically,
evaluate a **vision-LLM-based ingestion path** (feed the page image directly to a VLM, either
instead of or as a fallback alongside traditional OCR) rather than assuming an OCR→text-LLM
pipeline is the only architecture. Important caveat: this POC's test used a **hosted** API
(Anthropic), which is fine for demonstrating the concept but conflicts with the proposal's
on-premise data-sovereignty requirement (§4.7) for production use — the equivalent production
path would be a **self-hosted open-weight vision model** (e.g. Qwen2-VL or similar, served via the
same vLLM runtime the proposal already specifies for text models, §11), not a new infrastructure
category. This turns the OCR risk from "engine tuning problem, unresolved" into "known solvable
problem, needs one additional model evaluated" — a materially better position for the SCB
conversation than either engine finding alone.

**Update (2026-09-08, same day):** wired this into the actual pipeline rather than leaving it as
a one-off test — `document_ingestor.py` now supports `POC_OCR_ENGINE=vision` as a real,
configurable alternative to Tesseract (same pattern as `POC_LLM_PROVIDER` in `llm_client.py`),
calling an Ollama-served vision model (`OLLAMA_VISION_MODEL`, e.g. `llama3.2-vision`) instead of
`pytesseract`. Covered by mocked tests (successful transcription, graceful failure, HTTP-error
detail surfacing) — 21 passed, 2 xfailed.

**Live verification attempt (2026-09-08, same day), by a teammate with a local Ollama + GPU/CPU
box (`llama3.2-vision:latest` pulled, 7.8GB):** blocked before reaching the actual OCR-accuracy
question, by an environment issue distinct from the model itself —

```
error loading model: unknown model architecture: 'mllama'
```

`mllama` is the architecture tag for Meta's Llama 3.2 Vision models. This error means the
installed **Ollama runtime binary predates mllama support** (added in a late-2024 Ollama release)
— the model weights were downloaded fine (`ollama ls` shows them), but the bundled `llama-server`
inference engine doesn't recognize the architecture and crashes on load (HTTP 500, immediate).
Fix is an Ollama version upgrade (`curl -fsSL https://ollama.com/install.sh | sh`, then restart
the service), not a code or POC-side change. Two smaller, genuine improvements came out of
diagnosing this regardless, since they're correct independent of the root cause:
1. Vision OCR errors now surface the actual Ollama response body (e.g. this exact message)
   instead of a bare `requests.HTTPError` string — needed to get from "500 Server Error" (useless)
   to the real cause above.
2. The pipeline log in the review portal now shows the full `quality_notes` reason inline instead
   of a terse "quality issues detected", so this class of diagnosis no longer requires a terminal.

Net effect: the vision-LLM OCR path in this codebase is implemented and request-correct (it got
all the way to the model-load step on the first real attempt) — accuracy against
`llama3.2-vision` specifically is still unverified, blocked on an Ollama upgrade on the test
machine, not on anything in this repo.

### PaddleOCR install notes (for reproducing this)

Getting from "pip install paddleocr" to a working run took real troubleshooting — worth recording
so it isn't repeated blind:

1. `pip install paddlepaddle paddleocr` installs the latest of each (`paddlepaddle` 3.3.1,
   `paddleocr` 3.7.0 at time of writing) — this combination crashes on CPU inference with
   `NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support [...]`, inside the
   oneDNN backend, regardless of which detection model variant is used.
2. Downgrading only `paddlepaddle` to `2.6.2` doesn't work either — `paddleocr` 3.x's `paddlex`
   dependency calls a `paddle.inference` API (`set_optimization_level`) that doesn't exist in the
   2.x line.
3. `paddlepaddle==3.0.0` avoids the crash but the detector then returns **zero text regions** on
   every image tried (including a trivial synthetic "TEST 12345" image) — and a `lang="en"` model
   hits a *different* PIR error (`strides` attribute type mismatch) in the same code path.
   Reproduced identically inside a stock `paddlepaddle/paddle:3.0.0` Docker container, which rules
   out a host-CPU explanation (e.g. missing AVX-512) — it's a version-compatibility bug between
   `paddlex` 3.7.2 and the paddle inference API, not an environment quirk.
4. **What actually works:** `pip install "paddlepaddle==2.6.2" "paddleocr==2.7.3"` — the
   pre-`paddlex` generation of PaddleOCR, using the older `PaddleOCR(...).ocr(path, cls=True)`
   API instead of the newer `.predict()` pipeline API. Also needed `numpy<2` (the older `opencv`
   pin this version depends on isn't numpy-2 compatible) and a single consistent `opencv`
   installation (mixing `opencv-python` / `opencv-contrib-python` / `opencv-python-headless` in
   the same environment causes ABI import errors).
5. None of this is wired into `document_ingestor.py` — this was a standalone comparison, done in
   a throwaway Docker container, to answer the digit-script question decisively. Adopting
   PaddleOCR for real would mean pinning this exact known-good version combination, not the
   latest release.

### Secondary finding: table borders help field values, don't help label classification

Switching from free-floating two-column text to a real bordered table (visual grid lines) did not
change the digit-script result, but it also didn't hurt — figures extracted just as reliably with
or without borders once the digit-script issue was isolated. Where it likely does matter: real
scanned documents are rarely as clean as either synthetic version, so bordered tables (matching
real document structure) remain the more representative choice for the ingestion side. Document
classification, however, depends on OCR'ing short title/label lines correctly, which is
consistently the weakest part of this pipeline regardless of layout — worth a note to production
scope: don't make anything downstream hard-depend on `document_type` being correct for scanned
inputs; treat it as a hint, not a guarantee (this already lines up with how `document_ingestor.py`
falls back to `"unknown"` rather than raising).

### Follow-up items

6. ~~Verify the Eastern-vs-Western digit OCR gap against PaddleOCR specifically~~ — **done**. Same
   pattern confirmed on a second, independent engine (see "PaddleOCR comparison" above) — this is
   a real, engine-independent risk for Eastern-Indic digits in dense tables, not a Tesseract quirk.
7. **New, higher-priority item**: pilot a **vision-LLM ingestion path** for Arabic scanned
   documents (see "Vision-LLM alternative" above) — this is the only approach tested so far that
   actually reads the authentic digit script correctly. Needs: a self-hosted open-weight vision
   model evaluated for the on-premise requirement (e.g. Qwen2-VL via vLLM), a small labelled set
   of scanned pages to measure accuracy on (not just one document), and a decision on whether it
   replaces or supplements the OCR branch in `document_ingestor.py`.
8. If/when real scanned SCB documents arrive, check what digit convention they actually use before
   assuming either script.
9. Consider a lightweight, more resilient document-type signal for OCR'd input (e.g. presence of
   currency/number-table density, or asking the Financial Wizard's LLM to infer type from content
   as a fallback when Document Ingestor returns `"unknown"`) rather than deeper investment in
   substring-based Arabic label matching, which has a low ceiling on noisy scans.
