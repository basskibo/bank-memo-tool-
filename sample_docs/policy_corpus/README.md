# Synthetic credit-policy corpus (RAG demo — SPEC.md §9)

These are **fictional** policy snippets written for the POC. They are **not** Suez Canal Bank
policy and must never be treated as real. Each `.md` file is one short "policy" document; the
RAG demo chunks them, embeds the chunks, and retrieves the top-k for a query with a citation
(`doc_id` + `chunk_id`).

- `en_*.md` — English policy documents
- `ar_*.md` — Arabic policy documents (Modern Standard Arabic)

`evaluation/rag_gold.py` holds the gold question → expected `doc_id` set used by
`tests/test_rag_retrieval.py` and `evaluation/run_rag_eval.py`.
