# How the app works — flow

Companion to `SPEC.md` (what each capability must do) and `PLAN.md` (schedule). This file is the
runtime picture: what runs when, and where each module sits.

---

## 1. Top level

```mermaid
flowchart TD
    U([Reviewer]) -->|"upload PDF / pick sample"| PORTAL["Streamlit portal - src/review/app.py"]
    PORTAL -->|"Process this document"| BG["background thread - process_run_data()"]
    BG --> GRAPH["Extraction pipeline - src/orchestration/graph.py - LangGraph: ingest, extract, validate"]
    GRAPH --> RESULT["list of ExtractedField - value, unit, source_page, source_snippet, confidence, status = confirmed or needs_review"]
    RESULT --> REVIEW["Review UI - confirmed table + Needs review cards"]
    REVIEW -->|"reviewer corrects and ticks Confirm"| APPLY["apply_human_review()"]
    APPLY --> MEMO["Generate report - synthesize_memo() uses confirmed fields ONLY"]
    MEMO --> PDF["PDF report - reports/live_report.py"]

    RESULT -.->|"read-only, optional"| RAG["Policy check RAG - src/rag/policy_check.py"]
    PORTAL -.->|"free query, sidebar"| RAGD["Policy lookup RAG demo - src/rag/retrieve.py"]

    classDef rag fill:#eef7ee,stroke:#5a9,stroke-dasharray:4 3;
    class RAG,RAGD rag;
```

The two RAG boxes are **dashed** on purpose: they never touch a field or the memo (SPEC §9 —
isolated demo). Everything solid is the credit-memo pipeline.

---

## 2. The pipeline — `ingest → extract → validate`

LangGraph runs three nodes in order. Any node can write `error` to state and the rest is skipped.

```mermaid
flowchart TD
    START([run_extraction]) --> ING

    subgraph ING["node_ingest - document_ingestor.ingest_document()"]
        P1["pdfplumber: extract text layer per page"] --> P2{"page has under 10 chars?"}
        P2 -->|no| KEEP["keep text layer"]
        P2 -->|"yes - scanned page"| OCR{"POC_OCR_ENGINE"}
        OCR -->|tesseract| T["pytesseract ara+eng"]
        OCR -->|vision| OLL["Ollama VL"]
        OCR -->|mlx_vision| MV["mlx_vlm server - transcription only"]
        OCR -->|"mlx_vision_extract - FUSED"| MVE["vision_extractor.extract_page() - VL transcribes AND extracts fields - sets document.vision_prefetched_fields"]
        T --> CLS
        OLL --> CLS
        MV --> CLS
        KEEP --> CLS
        MVE --> CLS
        CLS["classify: financial_statement / loan_application / unknown"] --> Q{"avg chars per page >= 30 ?"}
        Q -->|no| REJECT["quality_ok = False - Wizard will not guess"]
        Q -->|yes| DOC["IngestedDocument"]
    end

    ING --> EXT

    subgraph EXT["node_extract - financial_wizard.extract_fields()"]
        E0{"vision_prefetched_fields present?"}
        E0 -->|"yes - fused engine already did it"| PRE["_fields_from_prefetched() - guardrails only, NO LLM call"]
        E0 -->|no| E1{"provider = api?"}
        E1 -->|yes| BATCH["one batched JSON call"]
        E1 -->|"no - mlx or ollama"| PF["per-field loop - narrative fields get a wider prompt - empty core field gets 1 blunt retry"]
        BATCH --> LLM["complete_json() - llm_client.py"]
        PF --> LLM
        LLM -->|mlx| MLXS["mlx_lm / mlx_vlm server"]
        LLM -->|ollama| OLS["Ollama"]
        LLM -->|api| ANT["Anthropic API"]
        PRE --> GD["guardrail: confidence under 0.7 becomes needs_review"]
        LLM --> GD
    end

    EXT --> VAL

    subgraph VAL["node_validate - citation_validator.validate_citations()"]
        V1["for each field: is source_snippet VERBATIM on the cited page?"]
        V1 -->|yes| OKF["stays confirmed"]
        V1 -->|"no or empty"| NR["becomes needs_review - possible hallucinated citation"]
    end

    VAL --> OUT([list of ExtractedField to portal])
```

Key rules:
- **`quality_ok = False`** (unreadable / degraded doc) → Financial Wizard returns nothing. The
  pipeline refuses to guess (SPEC §8.2).
- **Citation Validator is deterministic** — no LLM. A correct value whose snippet is not
  verbatim on the page still gets flagged `needs_review`. That is the safety net, not a bug.
- **The memo uses `confirmed` fields only.** A `needs_review` field is excluded until a human
  ticks *Confirm*.

---

## 3. MLX model management (when `POC_LLM_PROVIDER=mlx`)

The Mini (24 GB) holds **one** model at a time. `src/mlx_servers.py` swaps them.

```mermaid
flowchart LR
    ING2["ingest: scanned pages need OCR"] -->|ensure_mlx_vision| VL["VL 7B on port 8081"]
    EXT2["extract: text model needed"] -->|ensure_mlx_text| TXT["text 7B on port 8080"]
    VL -.->|"reap strays + free memory - _settle_after_unload"| TXT
    TXT -.-> VL
    NOTE["FUSED engine mlx_vision_extract skips the swap entirely - VL does OCR + extract, so node_extract has nothing to call"]
```

- Every swap first **reaps orphan `mlx_lm` / `mlx_vlm` servers** and waits for freed memory.
- On a dropped connection mid-generation (OOM), `_complete_json_mlx` restarts the server once
  and retries, then gives a plain "out of memory — close other apps" message.

---

## 4. RAG — isolated policy lookup (SPEC §9)

Not a pipeline node. Built once per process (lazy), then instant.

```mermaid
flowchart TD
    C["sample_docs/policy_corpus/*.md - 8 synthetic policies, 4 EN + 4 AR"] --> CH["chunk.py - fixed window + overlap - EN 450/90, AR 350/70"]
    CH --> EMB["index.py - sentence-transformers paraphrase-multilingual-MiniLM-L12-v2 - 25 chunks x 384-dim, unit-norm"]
    EMB --> IDX[("in-memory numpy matrix + metadata list - swap for Chroma in prod")]

    Q1["sidebar: free query"] --> RET
    Q2["per-doc: policy_check.py builds queries FROM extracted fields - amount, collateral, existing facilities, activity"] --> RET
    RET["retrieve(query, k=3)"] --> IDX
    IDX --> HITS["top-k RetrievedChunk - text, doc_id, chunk_id, lang, score - each carries a citation"]
    HITS --> SHOW["shown in portal - a pointer for the reviewer, NOT a compliance decision, NOT in the memo"]
```

Gold check: `evaluation/run_rag_eval.py` — 13 questions (7 EN, 6 AR) → **13/13 land on the
right passage**. Not the proposal §9.3 KPI (corpus is deliberately tiny).

---

## 5. Module map

| Path | Role |
|------|------|
| `src/review/app.py` | Streamlit portal — queue, live pipeline log, review UI, report button, RAG panels |
| `src/orchestration/graph.py` | LangGraph wiring: `ingest → extract → validate`, `run_extraction()` |
| `src/agents/document_ingestor.py` | PDF text + OCR branch (tesseract / vision / mlx_vision / fused), classify, quality gate |
| `src/agents/vision_extractor.py` | Fused VL engine — one call per scanned page: transcribe **and** extract fields |
| `src/agents/financial_wizard.py` | Field extraction — per-field / batch, narrative-field prompts, prefetched-field path |
| `src/agents/citation_validator.py` | Deterministic: is each snippet verbatim on its cited page? |
| `src/agents/narrative_synthesizer.py` | Draft memo from **confirmed** fields + citation guardrail |
| `src/llm_client.py` | One `complete_json()` over three providers (mlx / ollama / api) + JSON repair |
| `src/mlx_servers.py` | Start/stop/reap mlx servers, one model resident at a time |
| `src/rag/` | `chunk` · `corpus` · `index` · `retrieve` · `policy_check` — isolated |
| `reports/live_report.py` | PDF report (single + batch) |
| `evaluation/` | `run_full_sweep.py` (field status), `run_rag_eval.py` (retrieval), `EXPECTED_RESULTS.md` (answer key) |
