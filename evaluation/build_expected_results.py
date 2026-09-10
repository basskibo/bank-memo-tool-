"""
Generate evaluation/EXPECTED_RESULTS.md — the per-document answer key for every sample PDF.

Ground truth comes straight from sample_docs/generate_sample_docs.py (that data IS what the PDFs
are rendered from) plus generate_arabic_scanned_docs.py for the *_arabic_scan.pdf set. Regenerate
after changing either generator:

    .venv/bin/python evaluation/build_expected_results.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sample_docs"))

import generate_sample_docs as gen  # noqa: E402

OUT = Path(__file__).resolve().parent / "EXPECTED_RESULTS.md"

POC_FIELDS = [
    "company_name", "reporting_period", "total_assets", "total_liabilities", "total_equity",
    "annual_revenue", "net_income", "existing_bank_facilities", "requested_facility_amount",
    "collateral_offered",
]

# Arabic-scan answer key (numbers copied from generate_arabic_scanned_docs.py; those files use a
# DIFFERENT synthetic company for nile_delta and the same numbers as EGYPTIAN_CASES for misr_pharma).
ARABIC_SCANS = {
    "nile_delta_foods/nile_delta_foods_financial_statements_fy2024_arabic_scan.pdf": {
        "company_name": "شركة دلتا النيل للأغذية ش.م.م (Nile Delta Foods S.A.E.)",
        "reporting_period": "السنة المنتهية في 31 ديسمبر 2024 (FY2024)",
        "total_assets": "124,800,000", "total_liabilities": "65,200,000", "total_equity": "59,600,000",
        "annual_revenue": "208,300,000", "net_income": "15,800,000",
        "existing_bank_facilities": (
            "تسهيل تشغيلي متجدد من بنك قناة السويس ارتفع إلى 18,000,000 جنيه (استخدام 65٪)؛ "
            "خط اعتماد مستندي لدى البنك الأهلي المصري 8,000,000 جنيه؛ خط تمويل معدات جديد 5,000,000 جنيه"
        ),
        "requested_facility_amount": "n/a (financial statement)",
        "collateral_offered": "n/a (financial statement)",
    },
    "nile_delta_foods/nile_delta_foods_loan_application_arabic_scan.pdf": {
        "company_name": "شركة دلتا النيل للأغذية ش.م.م (Nile Delta Foods S.A.E.)",
        "reporting_period": "n/a (loan application form)",
        "total_assets": "n/a", "total_liabilities": "n/a", "total_equity": "n/a",
        "annual_revenue": "n/a", "net_income": "n/a",
        "existing_bank_facilities": (
            "تسهيل تشغيلي بنك قناة السويس 18,000,000 (استخدام 65٪)؛ اعتماد مستندي البنك الأهلي المصري "
            "8,000,000؛ تمويل معدات بنك مصر 5,000,000 (الربع الرابع 2024)"
        ),
        "requested_facility_amount": "25,000,000 (EGP / جنيه مصري)",
        "collateral_offered": (
            "رهن عقاري من الدرجة الأولى على منشأة الإنتاج (تقييم مستقل 42,000,000 جنيه)"
        ),
    },
    "misr_pharma/misr_pharma_financial_statements_fy2024_arabic_scan.pdf": {
        "company_name": "شركة مصر لتجارة الأدوية ش.م.م (Misr Pharma Distribution S.A.E.)",
        "reporting_period": "السنة المنتهية في 31 ديسمبر 2024 (FY2024), مع أرقام مقارنة 2023",
        "total_assets": "129,400,000  (2023: 118,900,000)",
        "total_liabilities": "83,500,000  (2023: 76,500,000)",
        "total_equity": "45,900,000  (2023: 42,400,000)",
        "annual_revenue": "341,200,000  (2023: 312,600,000)",
        "net_income": "9,600,000  (2023: 7,200,000)",
        "existing_bank_facilities": (
            "خط تمويل مخزون بنك قناة السويس ارتفع إلى 35,000,000 (استخدام 76٪). "
            "سحب على المكشوف AAIB سُدّد وأُغلق في الربع الثاني 2024. لا تسهيلات خارجية جديدة."
        ),
        "requested_facility_amount": "n/a (financial statement)",
        "collateral_offered": "n/a (financial statement)",
    },
    "misr_pharma/misr_pharma_loan_application_arabic_scan.pdf": {
        "company_name": "شركة مصر لتجارة الأدوية ش.م.م (Misr Pharma Distribution S.A.E.)",
        "reporting_period": "n/a (loan application form)",
        "total_assets": "n/a", "total_liabilities": "n/a", "total_equity": "n/a",
        "annual_revenue": "n/a", "net_income": "n/a",
        "existing_bank_facilities": "35,000,000 تمويل مخزون بنك قناة السويس (استخدام 76٪)",
        "requested_facility_amount": "20,000,000 (EGP)",
        "collateral_offered": "رهن حيازي على مخزون الأدوية + مستودع (تقييم 18,000,000 جنيه)",
    },
}


def _fy_label(year: int) -> str:
    return f"FY{year} — year ended 31 December {year}"


def _clean_fs(case: gen.CompanyCase, fy: gen.FinancialYear) -> dict[str, str]:
    return {
        "company_name": case.legal_name,
        "reporting_period": _fy_label(fy.year),
        "total_assets": fy.total_assets,
        "total_liabilities": fy.total_liabilities,
        "total_equity": fy.total_equity,
        "annual_revenue": fy.annual_revenue,
        "net_income": fy.net_income,
        "existing_bank_facilities": (fy.facilities_note or "").strip() or "—",
        "requested_facility_amount": "n/a — not a loan application (do NOT extract)",
        "collateral_offered": "n/a — not a loan application (do NOT extract)",
    }


def _clean_loan(case: gen.CompanyCase) -> dict[str, str]:
    return {
        "company_name": case.legal_name,
        "reporting_period": "n/a — loan application form has no accounting period → expect needs_review",
        "total_assets": "n/a", "total_liabilities": "n/a", "total_equity": "n/a",
        "annual_revenue": "n/a", "net_income": "n/a",
        "existing_bank_facilities": case.existing_facilities_declared.strip() or "—",
        "requested_facility_amount": case.loan_amount.strip() or "—",
        "collateral_offered": case.collateral.strip() or "—",
    }


def _low_quality(case: gen.CompanyCase) -> dict[str, str]:
    return {f: "INTENTIONALLY DEGRADED — every field must come back `needs_review`, never `confirmed`"
            for f in POC_FIELDS}


_ABSENT = "— not extracted (field does not apply to this document type)"

# Which fields a correctly-working pipeline should CONFIRM vs flag vs not extract at all.
_FS_CONFIRM = {
    "company_name", "reporting_period", "total_assets", "total_liabilities", "total_equity",
    "annual_revenue", "net_income", "existing_bank_facilities",
}
_LOAN_CONFIRM = {"company_name", "existing_bank_facilities", "requested_facility_amount", "collateral_offered"}


def _status(doc_kind: str, field: str) -> str:
    if doc_kind == "low_quality":
        return "needs_review (never confirmed)"
    if doc_kind == "financial_statement":
        if field in _FS_CONFIRM:
            return "confirmed"
        return _ABSENT
    if doc_kind == "loan_application":
        if field == "reporting_period":
            return "needs_review (no accounting period on a loan form)"
        if field in _LOAN_CONFIRM:
            return "confirmed"
        return _ABSENT
    if doc_kind == "arabic_scan_fs":
        if field in _FS_CONFIRM:
            return "needs_review OK (confirmed also a pass if value is right — OCR citations rarely verbatim)"
        return _ABSENT
    if doc_kind == "arabic_scan_loan":
        if field == "reporting_period":
            return "needs_review"
        if field in _LOAN_CONFIRM:
            return "needs_review OK (confirmed also a pass if value is right)"
        return _ABSENT
    return "—"


def _doc_table(title: str, path: str, values: dict[str, str], doc_kind: str, notes: str = "") -> str:
    rows = "\n".join(
        f"| `{f}` | {values.get(f, '—').replace(chr(10), ' ')} | {_status(doc_kind, f)} |"
        for f in POC_FIELDS
    )
    block = [f"### `{path}`", "", f"**{title}**", ""]
    if notes:
        block += [f"> {notes}", ""]
    block += ["| Field | Expected value | Expected status (a working pipeline) |",
              "|---|---|---|", rows, ""]
    return "\n".join(block)


def main() -> None:
    parts: list[str] = [
        "# Expected results — sample document answer key",
        "",
        "Auto-generated by `evaluation/build_expected_results.py` from the document generators. "
        "Do not hand-edit — regenerate.",
        "",
        "**How to read a `needs_review` in the portal:** a correct VALUE that is flagged only "
        "because the citation snippet is not verbatim on the page (common with local OCR/7B) is "
        "still a PASS. A wrong value, a missing field, or a `confirmed` on a degraded document is "
        "a FAIL.",
        "",
        "`existing_bank_facilities` on a financial statement = the bank-facilities note (narrative, "
        "may list several facilities). On a loan application = the applicant's declared facilities. "
        "`collateral_offered` is always free text, never a bare number.",
        "",
        "---",
        "",
    ]

    for case in gen.EGYPTIAN_CASES:
        parts.append(f"## {case.legal_name} (`{case.slug}`)\n")
        if case.low_quality:
            parts.append(_doc_table(
                "Intentionally low-quality internal summary", f"{case.slug}/{case.slug}_low_quality.pdf",
                _low_quality(case), "low_quality",
                notes="Guardrail test — the pipeline must refuse to confirm anything here.",
            ))
            continue
        for fy in case.financial_years:
            parts.append(_doc_table(
                f"Financial statements {fy.year}",
                f"{case.slug}/{case.slug}_financial_statements_fy{fy.year}.pdf",
                _clean_fs(case, fy), "financial_statement",
            ))
        parts.append(_doc_table(
            "Loan / credit facility application",
            f"{case.slug}/{case.slug}_loan_application.pdf",
            _clean_loan(case), "loan_application",
        ))

    parts.append("## Legacy Acme Trading set (`acme_trading`)\n")
    parts.append(
        "The 4 `acme_trading/*` PDFs predate the Egyptian set. Their answer key lives in "
        "`evaluation/expected_values.py` (status-level). Values: USD, and the numbers are in that "
        "file's git history — regenerate with `generate_sample_docs.generate_legacy_acme()` if the "
        "PDFs are rebuilt.\n"
    )

    parts.append("---\n\n## Arabic scanned documents (`*_arabic_scan.pdf`)\n")
    parts.append(
        "Scanned-image PDFs with Eastern Arabic-Indic numerals. OCR path "
        "(`POC_OCR_ENGINE=mlx_vision_extract` or `mlx_vision`). Values normalised to Western "
        "digits below; the model may keep Arabic-Indic in the transcription.\n"
    )
    for path, values in ARABIC_SCANS.items():
        kind = "arabic_scan_loan" if "loan_application" in path else "arabic_scan_fs"
        parts.append(_doc_table(path.split("/")[-1], path, values, kind))

    OUT.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(parts)} blocks)")


if __name__ == "__main__":
    main()
