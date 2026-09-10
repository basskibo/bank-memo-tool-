"""
RAG demo hit/miss sweep (SPEC.md §9). Prints a table and writes evaluation/rag_results.json.

    .venv/bin/python evaluation/run_rag_eval.py

PASS for a query = the expected doc_id is at rank 1 AND the expected phrase is in that chunk.
"doc-hit" = expected doc_id appears anywhere in the top-k (softer signal).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.table import Table

from evaluation.rag_gold import GOLD
from src.config import RAG_TOP_K
from src.rag import retrieve

console = Console()


def main() -> None:
    t0 = time.monotonic()
    console.print(f"[dim]Building index + running {len(GOLD)} gold queries (top-{RAG_TOP_K})…[/dim]")

    table = Table(show_lines=False)
    for col in ("Lang", "Query", "Expected doc", "Rank-1 doc", "Phrase?", "Result"):
        table.add_column(col, overflow="fold")

    results = []
    rank1_ok = doc_hit = 0
    for g in GOLD:
        hits = retrieve(g.query, k=RAG_TOP_K)
        top = hits[0] if hits else None
        top_doc = top.doc_id if top else "—"
        phrase_in_top = bool(top and g.expect_phrase in top.text)
        r1 = top_doc == g.expect_doc_id
        dh = any(h.doc_id == g.expect_doc_id for h in hits)
        passed = r1 and phrase_in_top
        rank1_ok += r1
        doc_hit += dh
        table.add_row(
            g.lang, g.query[:60], g.expect_doc_id, top_doc,
            "✓" if phrase_in_top else "✗",
            "[green]PASS[/green]" if passed else ("[yellow]doc-hit[/yellow]" if dh else "[red]MISS[/red]"),
        )
        results.append({
            "query": g.query, "lang": g.lang, "expect_doc_id": g.expect_doc_id,
            "rank1_doc": top_doc, "rank1_correct": r1, "phrase_in_top": phrase_in_top,
            "doc_in_topk": dh, "passed": passed,
            "topk": [h.model_dump() for h in hits],
        })

    console.print(table)
    n = len(GOLD)
    console.print(
        f"\n[bold]{rank1_ok}/{n}[/bold] rank-1 correct · "
        f"[bold]{doc_hit}/{n}[/bold] expected doc in top-{RAG_TOP_K} · "
        f"{time.monotonic() - t0:.1f}s"
    )
    out = Path(__file__).parent / "rag_results.json"
    out.write_text(json.dumps({
        "top_k": RAG_TOP_K, "n": n, "rank1_correct": rank1_ok, "doc_in_topk": doc_hit,
        "results": results,
    }, ensure_ascii=False, indent=2))
    console.print(f"[dim]Written to {out}[/dim]")


if __name__ == "__main__":
    main()
