"""
End-to-end demo: pokreni pipeline (ingest -> extract -> validate) na sva 4 test dokumenta,
uporedi rezultate sa evaluation/expected_values.py, i na kraju generiši nacrt memoranduma za
"čist" dokument (fy2023) da se vidi ceo lanac do finalnog teksta.

Pokretanje:
    .venv/bin/python run_demo.py

Provider (Ollama ili Anthropic API) se bira preko POC_LLM_PROVIDER u .env — vidi .env.example.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from evaluation.expected_values import EXPECTED
from src.agents.narrative_synthesizer import synthesize_memo
from src.config import sample_doc_path
from src.llm_client import LLMNotConfigured, active_provider_summary, check_provider_ready
from src.orchestration.graph import run_extraction

console = Console()

SAMPLE_FILES = [
    "acme_trading_financial_statements_fy2023.pdf",
    "acme_trading_financial_statements_fy2024.pdf",
    "acme_trading_loan_application.pdf",
    "beta_supplies_low_quality.pdf",
]


def check_api_key() -> None:
    try:
        check_provider_ready()
    except LLMNotConfigured as exc:
        console.print(f"\n[bold red]{exc}[/bold red]\n\n"
                       "Podesi poc/.env (vidi .env.example) i pokreni ponovo: "
                       "[cyan].venv/bin/python run_demo.py[/cyan]\n")
        sys.exit(1)
    console.print(f"[dim]Provider: {active_provider_summary()}[/dim]\n")


def run_one_document(filename: str) -> dict | None:
    console.rule(f"[bold]{filename}")
    start = time.monotonic()

    def progress_cb(field_name: str, i: int, total: int) -> None:
        elapsed = time.monotonic() - start
        status.update(f"[cyan]Ekstrakcija polja {i}/{total}: {field_name}[/cyan] "
                       f"[dim]({elapsed:.0f}s proteklo)[/dim]")

    with console.status("[cyan]Ucitavam i parsiram dokument...[/cyan]", spinner="dots") as status:
        result = run_extraction(str(sample_doc_path(filename)), on_progress=progress_cb)

    console.print(f"[dim]Gotovo za {time.monotonic() - start:.1f}s[/dim]")

    if result.get("error"):
        console.print(f"[red]Greška pri ingest-u: {result['error']}[/red]")
        return None

    fields = result["fields"]
    expected = EXPECTED.get(filename, {})

    table = Table(show_lines=False)
    table.add_column("Polje")
    table.add_column("Vrednost")
    table.add_column("Str.")
    table.add_column("Status")
    table.add_column("Očekivano")
    table.add_column("Match?")

    mismatches = []
    for f in fields:
        expected_status = expected.get(f.field_name)
        if expected_status is None:
            match = "—"
        elif expected_status == f.status:
            match = "[green]OK[/green]"
        else:
            match = "[bold red]MISMATCH[/bold red]"
            mismatches.append((f.field_name, expected_status, f.status))

        status_style = "green" if f.status == "confirmed" else "yellow"
        table.add_row(
            f.field_name,
            f.value[:40],
            str(f.source_page),
            f"[{status_style}]{f.status}[/{status_style}]",
            expected_status or "-",
            match,
        )

    console.print(table)

    found_names = {f.field_name for f in fields}
    missing_expected = set(expected) - found_names
    if missing_expected:
        console.print(f"[yellow]Napomena: ova polja se očekuju ali nisu uopšte izvučena: "
                       f"{sorted(missing_expected)}[/yellow]")

    if filename == "beta_supplies_low_quality.pdf":
        wrongly_confirmed = [
            f for f in fields
            if expected.get(f.field_name) == "needs_review" and f.status == "confirmed"
        ]
        if wrongly_confirmed:
            console.print(
                f"[bold red]KRITIČAN NALAZ: {[f.field_name for f in wrongly_confirmed]} je "
                f"trebalo da bude needs_review (dokument je namerno pokvaren), a pipeline ga je "
                f"prihvatio kao confirmed. Guardrail ne radi kako treba — vidi SPEC.md sekcija 5."
                f"[/bold red]"
            )
        else:
            console.print("[bold green]OK — svi sporni podaci u beta_supplies su ispravno "
                           "eskalirani na needs_review, nijedan nije lažno prihvaćen.[/bold green]")

    return {"filename": filename, "fields": fields, "mismatches": mismatches}


def main():
    check_api_key()

    all_results = []
    try:
        for filename in SAMPLE_FILES:
            r = run_one_document(filename)
            if r:
                all_results.append(r)
    except LLMNotConfigured as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)

    console.rule("[bold]Nacrt memoranduma (na osnovu fy2023 — očekivano najčistiji dokument)")
    fy2023 = next((r for r in all_results if r["filename"].endswith("fy2023.pdf")), None)
    if fy2023:
        confirmed = [f for f in fy2023["fields"] if f.status == "confirmed"]
        open_exceptions = [f.field_name for f in fy2023["fields"] if f.status == "needs_review"]
        if confirmed:
            def memo_progress_cb(title: str, i: int, total: int) -> None:
                status.update(f"[cyan]Pišem sekciju {i}/{total}: {title}[/cyan]")

            with console.status("[cyan]Pišem nacrt memoranduma...[/cyan]", spinner="dots") as status:
                memo = synthesize_memo("Acme Trading LLC", confirmed, open_exceptions,
                                        on_progress=memo_progress_cb)
            if memo.guardrail_violations:
                console.print("[bold red]GUARDRAIL VIOLATION — memo sadrži necitiranu "
                               "brojku:[/bold red]")
                for v in memo.guardrail_violations:
                    console.print(f"  - {v}")
            for section in memo.sections:
                console.print(Markdown(f"### {section.title}\n\n{section.text}"))
            if memo.open_exceptions:
                console.print(f"[yellow]Otvoreni izuzeci (nisu u memou): "
                               f"{memo.open_exceptions}[/yellow]")
        else:
            console.print("[yellow]Nema potvrđenih polja, memo se ne generiše.[/yellow]")

    console.rule("[bold]Rezime")
    total_mismatches = sum(len(r["mismatches"]) for r in all_results)
    if total_mismatches == 0:
        console.print("[bold green]Svi rezultati odgovaraju očekivanjima iz "
                       "evaluation/expected_values.py.[/bold green]")
    else:
        console.print(f"[bold yellow]{total_mismatches} neslaganja sa očekivanim vrednostima — "
                       f"vidi tabele iznad. Ovo je normalno za prvu vožnju, ne mora značiti bug; "
                       f"upiši nalaze u evaluation/FINDINGS.md (PLAN.md Dan 10).[/bold yellow]")


if __name__ == "__main__":
    main()
