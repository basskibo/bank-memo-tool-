"""
Full measurement sweep across ALL current sample documents (PLAN.md Dan 5 + Dan 9, redone at
current scale — the old run_demo.py only covers the original 4-document legacy set).

Ground truth for the 15 Egyptian clean documents + sinai_agro is derived programmatically from
sample_docs/generate_sample_docs.py's CompanyCase/FinancialYear source data, rather than
hand-transcribed, since that data IS the ground truth (it's what the PDFs were generated from).
Legacy 4-document ground truth still comes from evaluation/expected_values.py.

This checks STATUS (confirmed vs needs_review), not exact values — i.e. "did the pipeline
correctly judge whether to trust this field", which is the question PLAN.md's exit criteria
actually care about. Exact-value spot checks are done separately/manually.

Run: .venv/bin/python evaluation/run_full_sweep.py
Output: prints a live report AND writes evaluation/sweep_results.json for FINDINGS.md to consume.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sample_docs"))

from rich.console import Console
from rich.table import Table

import generate_sample_docs as gen  # noqa: E402  (sample_docs/ added to path above)
from evaluation.expected_values import EXPECTED as LEGACY_EXPECTED
from src.config import SAMPLE_DOCS_DIR, iter_sample_docs
from src.llm_client import LLMNotConfigured, active_provider_summary, check_provider_ready
from src.orchestration.graph import run_extraction

console = Console()

CLEAN_STATEMENT_STATUS = {
    "company_name": "confirmed",
    "reporting_period": "confirmed",
    "total_assets": "confirmed",
    "total_liabilities": "confirmed",
    "total_equity": "confirmed",
    "annual_revenue": "confirmed",
    "net_income": "confirmed",
    "existing_bank_facilities": "confirmed",
}
LOAN_APPLICATION_STATUS = {
    "company_name": "confirmed",
    # Loan application forme (CBG-CR-01) nemaju računovodstveni reporting period — nema "year
    # ended", samo "Form rev. 2023". Pipeline NE sme da potvrdi period kog nema u dokumentu;
    # očekujemo needs_review. Ako model vrati confirmed, to je dangerous mismatch (false confidence).
    "reporting_period": "needs_review",
    "existing_bank_facilities": "confirmed",
    "requested_facility_amount": "confirmed",
    "collateral_offered": "confirmed",
}
LOW_QUALITY_STATUS = {
    "total_assets": "needs_review",
    "annual_revenue": "needs_review",
    "net_income": "needs_review",
    "existing_bank_facilities": "needs_review",
}


def build_expected_for_all_docs() -> dict[str, dict[str, str]]:
    """Programmatic ground truth for the 20 current sample docs, keyed by relative path."""
    expected: dict[str, dict[str, str]] = {}

    for case in gen.EGYPTIAN_CASES:
        if case.low_quality:
            expected[f"{case.slug}/{case.slug}_low_quality.pdf"] = dict(LOW_QUALITY_STATUS)
            continue
        for fy in case.financial_years:
            expected[f"{case.slug}/{case.slug}_financial_statements_fy{fy.year}.pdf"] = (
                dict(CLEAN_STATEMENT_STATUS)
            )
        expected[f"{case.slug}/{case.slug}_loan_application.pdf"] = dict(LOAN_APPLICATION_STATUS)

    # Legacy 4-doc set keeps using the hand-written expected_values.py (unchanged, still valid).
    # Those files now live under sample_docs/<slug>/ subfolders too, same as the Egyptian sets.
    for filename, status_map in LEGACY_EXPECTED.items():
        slug = "beta_supplies" if filename.startswith("beta_supplies") else "acme_trading"
        expected[f"{slug}/{filename}"] = status_map

    return expected


def relative_name(path: Path) -> str:
    try:
        return str(path.relative_to(SAMPLE_DOCS_DIR))
    except ValueError:
        return path.name


def run_one(path: Path, expected: dict[str, str]) -> dict:
    name = relative_name(path)
    console.rule(f"[bold]{name}")
    start = time.monotonic()

    def progress_cb(field_name: str, i: int, total: int) -> None:
        elapsed = time.monotonic() - start
        status.update(f"[cyan]{i}/{total}: {field_name}[/cyan] [dim]({elapsed:.0f}s)[/dim]")

    with console.status("[cyan]Starting...[/cyan]", spinner="dots") as status:
        result = run_extraction(str(path), on_progress=progress_cb)

    elapsed = time.monotonic() - start
    if result.get("error"):
        console.print(f"[red]Error: {result['error']}[/red]")
        return {"file": name, "error": result["error"], "elapsed_s": round(elapsed, 1)}

    fields = result["fields"]
    table = Table(show_lines=False)
    for col in ("Field", "Status", "Expected", "Match"):
        table.add_column(col)

    field_results = []
    safe_mismatches = 0
    dangerous_mismatches = 0
    matches = 0
    for f in fields:
        exp = expected.get(f.field_name)
        if exp is None:
            match = "-"
        elif exp == f.status:
            match = "[green]OK[/green]"
            matches += 1
        else:
            match = "[bold red]MISMATCH[/bold red]"
            if exp == "needs_review" and f.status == "confirmed":
                dangerous_mismatches += 1
            else:
                safe_mismatches += 1
        style = "green" if f.status == "confirmed" else "yellow"
        table.add_row(f.field_name, f"[{style}]{f.status}[/{style}]", exp or "-", match)
        field_results.append({
            "field_name": f.field_name, "value": f.value, "status": f.status,
            "confidence": f.confidence, "expected": exp,
        })

    console.print(table)
    console.print(f"[dim]{elapsed:.1f}s — {matches} OK, {safe_mismatches} safe mismatch, "
                  f"{dangerous_mismatches} DANGEROUS mismatch[/dim]")

    return {
        "file": name, "elapsed_s": round(elapsed, 1), "fields": field_results,
        "matches": matches, "safe_mismatches": safe_mismatches,
        "dangerous_mismatches": dangerous_mismatches,
    }


def main() -> None:
    try:
        check_provider_ready()
    except LLMNotConfigured as exc:
        console.print(f"[bold red]{exc}[/bold red]")
        sys.exit(1)
    console.print(f"[dim]Provider: {active_provider_summary()}[/dim]\n")

    expected_all = build_expected_for_all_docs()
    docs = iter_sample_docs()
    console.print(f"[bold]Running full sweep on {len(docs)} documents...[/bold]\n")

    results = []
    sweep_start = time.monotonic()
    for path in docs:
        name = relative_name(path)
        exp = expected_all.get(name, {})
        results.append(run_one(path, exp))

    total_elapsed = time.monotonic() - sweep_start

    console.rule("[bold]SUMMARY")
    total_matches = sum(r.get("matches", 0) for r in results)
    total_safe = sum(r.get("safe_mismatches", 0) for r in results)
    total_dangerous = sum(r.get("dangerous_mismatches", 0) for r in results)
    errors = [r for r in results if "error" in r]

    console.print(f"Documents processed: {len(results)} ({len(errors)} errors)")
    console.print(f"Total time: {total_elapsed / 60:.1f} min")
    console.print(f"[green]Matches: {total_matches}[/green]  "
                  f"[yellow]Safe mismatches (over-caution): {total_safe}[/yellow]  "
                  f"[bold red]Dangerous mismatches (false confidence): {total_dangerous}[/bold red]")

    if total_dangerous:
        console.print("\n[bold red]Dangerous mismatches by document:[/bold red]")
        for r in results:
            bad = [f for f in r.get("fields", [])
                   if f["expected"] == "needs_review" and f["status"] == "confirmed"]
            if bad:
                console.print(f"  {r['file']}: {[f['field_name'] for f in bad]}")

    out_path = Path(__file__).parent / "sweep_results.json"
    out_path.write_text(json.dumps({
        "provider": active_provider_summary(),
        "total_elapsed_s": round(total_elapsed, 1),
        "total_matches": total_matches,
        "total_safe_mismatches": total_safe,
        "total_dangerous_mismatches": total_dangerous,
        "results": results,
    }, indent=2))
    console.print(f"\n[dim]Full results written to {out_path}[/dim]")


if __name__ == "__main__":
    main()
