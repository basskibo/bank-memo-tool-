"""
Generiše sintetička test PDF dokumenta za POC (fiktivne kompanije, izmišljeni brojevi).

Format je modelovan po praksi egipatskih banaka (CBE, komercijalni registar, EGP, CAP pozicija,
revizija kod FRA-registrovanog revizora). SCB = Suez Canal Bank (fiktivni odnos u test podacima).

Pokretanje:
    .venv/bin/python sample_docs/generate_sample_docs.py          # svi setovi
    .venv/bin/python sample_docs/generate_sample_docs.py --set acme   # jedan set

Svaka firma se generiše u svoj podfolder: sample_docs/<company_slug>/
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT_DIR = Path(__file__).parent
styles = getSampleStyleSheet()
h1 = styles["Title"]
h2 = ParagraphStyle("h2", parent=styles["Heading2"], spaceBefore=14, spaceAfter=6)
body = styles["Normal"]
small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, textColor=colors.grey)
arabic_sub = ParagraphStyle("arabic_sub", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#444444"))

TABLE_STYLE = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
])

FORM_STYLE = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8b0000")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
])


@dataclass
class FinancialYear:
    year: int
    total_assets: str
    total_liabilities: str
    total_equity: str
    annual_revenue: str
    net_income: str
    cash: str
    receivables: str
    inventory: str
    ppe: str
    payables: str
    short_term_debt: str
    long_term_debt: str
    cogs: str
    opex: str
    interest: str
    facilities_note: str


@dataclass
class CompanyCase:
    slug: str
    legal_name: str
    arabic_name: str
    cr_number: str
    tax_card: str
    industry: str
    governorate: str
    years_in_operation: int
    bank_relationship_since: int
    auditor: str
    currency_label: str = "EGP"
    currency_note: str = "(All amounts in Egyptian Pounds — EGP unless otherwise stated.)"
    financial_years: list[FinancialYear] = field(default_factory=list)
    loan_amount: str = ""
    loan_type: str = ""
    loan_purpose: str = ""
    collateral: str = ""
    existing_facilities_declared: str = ""
    low_quality: bool = False
    low_quality_sections: list[tuple[str, str]] | None = None


def build(company_slug: str, filename: str, story: list):
    out_dir = OUT_DIR / company_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
    )
    doc.build(story)
    print(f"Generated {company_slug}/{filename}")


def _table(data: list[list[str]], col_widths: list[float], style: TableStyle = TABLE_STYLE) -> Table:
    t = Table(data, colWidths=col_widths)
    t.setStyle(style)
    return t


def _egyptian_financial_header(case: CompanyCase, fy: FinancialYear) -> list:
    story = []
    story.append(Paragraph(case.legal_name, h1))
    story.append(Paragraph(case.arabic_name, arabic_sub))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Annual Financial Statements — Fiscal Year {fy.year} "
        f"(year ended 31 December {fy.year})",
        styles["Heading3"],
    ))
    story.append(Paragraph(
        "Prepared in accordance with Egyptian Accounting Standards (EAS) and IFRS. "
        f"Audited by {case.auditor}, registered with the Financial Regulatory Authority (FRA).",
        small,
    ))
    story.append(Paragraph(case.currency_note, small))
    story.append(Paragraph(
        f"Commercial Register No.: {case.cr_number} | Tax Card: {case.tax_card} | "
        f"Registered office: {case.governorate}, Arab Republic of Egypt",
        small,
    ))
    story.append(Paragraph("(Synthetic test document — not a real company.)", small))
    story.append(Spacer(1, 14))
    return story


def generate_financial_statement(case: CompanyCase, fy: FinancialYear) -> None:
    story = _egyptian_financial_header(case, fy)

    story.append(Paragraph("Statement of Financial Position as at 31 December " + str(fy.year), h2))
    bs_data = [
        ["Line Item", f"Amount ({case.currency_label})"],
        ["Cash and cash equivalents", fy.cash],
        ["Trade and other receivables", fy.receivables],
        ["Inventories", fy.inventory],
        ["Property, plant and equipment (net)", fy.ppe],
        ["Total Assets", fy.total_assets],
        ["Trade and other payables", fy.payables],
        ["Short-term bank borrowings", fy.short_term_debt],
        ["Long-term borrowings", fy.long_term_debt],
        ["Total Liabilities", fy.total_liabilities],
        ["Total Equity", fy.total_equity],
    ]
    story.append(_table(bs_data, [10 * cm, 5 * cm]))
    story.append(Spacer(1, 14))

    story.append(Paragraph(f"Statement of Profit or Loss — Year Ended 31 December {fy.year}", h2))
    is_data = [
        ["Line Item", f"Amount ({case.currency_label})"],
        ["Revenue", fy.annual_revenue],
        ["Cost of sales", fy.cogs],
        ["Gross profit", _subtract_display(fy.annual_revenue, fy.cogs)],
        ["Operating expenses", fy.opex],
        ["Operating profit", _operating_profit(fy)],
        ["Finance costs", fy.interest],
        ["Net profit for the year", fy.net_income],
    ]
    story.append(_table(is_data, [10 * cm, 5 * cm]))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Note 12 — Bank Borrowings and Credit Facilities", h2))
    story.append(Paragraph(fy.facilities_note, body))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Note: Total banking exposure is reported to the Central Bank of Egypt (CBE) under the "
        "Credit Aggregate Position (CAP) framework. Figures above reflect facilities outstanding "
        "as at the reporting date.",
        small,
    ))

    build(case.slug, f"{case.slug}_financial_statements_fy{fy.year}.pdf", story)


def _parse_amount(s: str) -> int:
    return int(s.replace(",", ""))


def _subtract_display(revenue: str, cogs: str) -> str:
    val = _parse_amount(revenue) - _parse_amount(cogs)
    return f"{val:,}"


def _operating_profit(fy: FinancialYear) -> str:
    rev = _parse_amount(fy.annual_revenue)
    cogs = _parse_amount(fy.cogs)
    opex = _parse_amount(fy.opex)
    return f"{rev - cogs - opex:,}"


def generate_loan_application(case: CompanyCase) -> None:
    story = []
    story.append(Paragraph("Corporate Credit Facility Application", h1))
    story.append(Paragraph("Suez Canal Bank — Corporate Banking Division", styles["Heading3"]))
    story.append(Paragraph(
        "Form CBG-CR-01 (rev. 2023) | Internal use — Credit Committee review",
        small,
    ))
    story.append(Paragraph("(Synthetic test document — not a real company or bank.)", small))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Section A — Applicant Information", h2))
    app_data = [
        ["Field", "Details"],
        ["Legal name", case.legal_name],
        ["Arabic name", case.arabic_name],
        ["Commercial Register No.", case.cr_number],
        ["Tax Card No.", case.tax_card],
        ["Industry / activity", case.industry],
        ["Registered governorate", case.governorate],
        ["Years in operation", str(case.years_in_operation)],
        ["Relationship with Suez Canal Bank since", str(case.bank_relationship_since)],
    ]
    story.append(_table(app_data, [6 * cm, 9 * cm], FORM_STYLE))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Section B — Facility Requested", h2))
    req_data = [
        ["Field", "Details"],
        ["Requested facility amount", case.loan_amount],
        ["Facility type", case.loan_type],
        ["Purpose / use of proceeds", case.loan_purpose],
        ["Proposed drawdown", "Single drawdown within 90 days of approval"],
        ["Repayment source", "Operating cash flows and existing contract backlog"],
    ]
    story.append(_table(req_data, [6 * cm, 9 * cm], FORM_STYLE))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Section C — Collateral & Security", h2))
    story.append(Paragraph(case.collateral, body))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Section D — Existing Banking Relationships (as declared by applicant)", h2))
    story.append(Paragraph(case.existing_facilities_declared, body))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Applicant confirms that a current CBE Credit Aggregate Position (CAP) report has been "
        "obtained and is attached. No undisclosed facilities are held with other licensed banks.",
        body,
    ))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Section E — Executive Summary", h2))
    story.append(Paragraph(
        f"{case.legal_name} operates in {case.industry.lower()} and has maintained a banking "
        f"relationship with Suez Canal Bank since {case.bank_relationship_since}. The requested "
        f"facility of {case.loan_amount} will support {case.loan_purpose.lower()}. "
        "Management represents that audited financial statements for the last two fiscal years "
        "are enclosed and that all information provided is complete and accurate.",
        body,
    ))

    build(case.slug, f"{case.slug}_loan_application.pdf", story)


def generate_low_quality(case: CompanyCase) -> None:
    story = []
    story.append(Paragraph(f"{case.legal_name} — Internal Financial Summary", h1))
    story.append(Paragraph(
        "(Synthetic test document, intentionally degraded to test escalation behaviour.)",
        small,
    ))
    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "Management summary prepared internally for credit review. Unaudited draft; figures may "
        "differ from statutory accounts. Some sections use inconsistent units or omit required "
        "fields (kept intentionally for POC testing).",
        body,
    ))
    story.append(Spacer(1, 12))

    for title, text in case.low_quality_sections or []:
        story.append(Paragraph(title, h2))
        story.append(Paragraph(text, body))
        story.append(Spacer(1, 12))

    story.append(Paragraph(
        "Note for POC: this document deliberately contains conflicting figures, currency/unit "
        "ambiguity, and missing required fields. Expected agent behaviour: flag as needs_review, "
        "do not guess a resolved value.",
        small,
    ))
    build(case.slug, f"{case.slug}_low_quality.pdf", story)


# ---------------------------------------------------------------------------
# Legacy set (Acme / Beta) — kept for backward compatibility with existing tests
# ---------------------------------------------------------------------------

def generate_legacy_acme() -> None:
    """Original USD-based Acme set used by unit tests and run_demo.py."""
    legacy_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b2b2b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])

    # FY2023
    story = []
    story.append(Paragraph("Acme Trading LLC", h1))
    story.append(Paragraph("Annual Financial Statements — Fiscal Year 2023 (ended 31 December 2023)", styles["Heading3"]))
    story.append(Paragraph("(All figures in USD unless otherwise stated. Synthetic test document — not a real company.)", small))
    story.append(Spacer(1, 16))
    story.append(Paragraph("Balance Sheet as of 31 December 2023", h2))
    bs_data = [
        ["Line Item", "Amount (USD)"],
        ["Cash and cash equivalents", "1,850,000"],
        ["Accounts receivable", "3,200,000"],
        ["Inventory", "4,100,000"],
        ["Property, plant & equipment", "3,300,000"],
        ["Total Assets", "12,450,000"],
        ["Accounts payable", "2,900,000"],
        ["Short-term bank facilities", "1,800,000"],
        ["Long-term debt", "2,500,000"],
        ["Total Liabilities", "7,200,000"],
        ["Total Equity", "5,250,000"],
    ]
    t = Table(bs_data, colWidths=[10 * cm, 5 * cm])
    t.setStyle(legacy_style)
    story.append(t)
    story.append(Spacer(1, 16))
    story.append(Paragraph("Income Statement — Year Ended 31 December 2023", h2))
    is_data = [
        ["Line Item", "Amount (USD)"],
        ["Annual Revenue", "18,300,000"],
        ["Cost of Goods Sold", "13,100,000"],
        ["Gross Profit", "5,200,000"],
        ["Operating Expenses", "3,600,000"],
        ["Operating Income", "1,600,000"],
        ["Interest Expense", "310,000"],
        ["Net Income", "1,120,000"],
    ]
    t2 = Table(is_data, colWidths=[10 * cm, 5 * cm])
    t2.setStyle(legacy_style)
    story.append(t2)
    story.append(Spacer(1, 16))
    story.append(Paragraph("Notes on Existing Bank Facilities", h2))
    story.append(Paragraph(
        "Acme Trading LLC maintains an existing overdraft facility of USD 500,000 with National "
        "Bank, utilized at approximately 60% as of the statement date. No other outstanding "
        "credit facilities were held as of 31 December 2023.", body
    ))
    build("acme_trading", "acme_trading_financial_statements_fy2023.pdf", story)

    # FY2024
    story = []
    story.append(Paragraph("Acme Trading LLC", h1))
    story.append(Paragraph("Annual Financial Statements — Fiscal Year 2024 (ended 31 December 2024)", styles["Heading3"]))
    story.append(Paragraph("(All figures in USD unless otherwise stated. Synthetic test document — not a real company.)", small))
    story.append(Spacer(1, 16))
    story.append(Paragraph("Balance Sheet as of 31 December 2024", h2))
    bs_data = [
        ["Line Item", "Amount (USD)"],
        ["Cash and cash equivalents", "2,050,000"],
        ["Accounts receivable", "3,650,000"],
        ["Inventory", "4,700,000"],
        ["Property, plant & equipment", "3,700,000"],
        ["Total Assets", "14,100,000"],
        ["Accounts payable", "3,150,000"],
        ["Short-term bank facilities", "2,100,000"],
        ["Long-term debt", "2,800,000"],
        ["Total Liabilities", "8,050,000"],
        ["Total Equity", "6,050,000"],
    ]
    t = Table(bs_data, colWidths=[10 * cm, 5 * cm])
    t.setStyle(legacy_style)
    story.append(t)
    story.append(Spacer(1, 16))
    story.append(Paragraph("Income Statement — Year Ended 31 December 2024", h2))
    is_data = [
        ["Line Item", "Amount (USD)"],
        ["Annual Revenue", "21,750,000"],
        ["Cost of Goods Sold", "15,400,000"],
        ["Gross Profit", "6,350,000"],
        ["Operating Expenses", "4,150,000"],
        ["Operating Income", "2,200,000"],
        ["Interest Expense", "380,000"],
        ["Net Income", "1,540,000"],
    ]
    t2 = Table(is_data, colWidths=[10 * cm, 5 * cm])
    t2.setStyle(legacy_style)
    story.append(t2)
    story.append(Spacer(1, 16))
    story.append(Paragraph("Notes on Existing Bank Facilities", h2))
    story.append(Paragraph(
        "Acme Trading LLC continues to hold an overdraft facility of USD 500,000 with National Bank "
        "(unchanged from the prior year). In Q2 2024, the company opened an additional trade finance "
        "line of USD 300,000 with the same institution to support seasonal import cycles.", body
    ))
    build("acme_trading", "acme_trading_financial_statements_fy2024.pdf", story)

    # Loan application
    story = []
    story.append(Paragraph("Credit Facility Application", h1))
    story.append(Paragraph("Applicant: Acme Trading LLC", styles["Heading3"]))
    story.append(Paragraph("(Synthetic test document — not a real company or bank.)", small))
    story.append(Spacer(1, 16))
    story.append(Paragraph("Applicant Details", h2))
    app_data = [
        ["Field", "Value"],
        ["Legal name", "Acme Trading LLC"],
        ["Registration number", "SC-2011-004521"],
        ["Industry", "Import / Export Trading — Consumer Goods"],
        ["Years in operation", "13"],
        ["Relationship with bank since", "2016"],
    ]
    t = Table(app_data, colWidths=[6 * cm, 9 * cm])
    t.setStyle(legacy_style)
    story.append(t)
    story.append(Spacer(1, 16))
    story.append(Paragraph("Facility Requested", h2))
    req_data = [
        ["Field", "Value"],
        ["Requested facility amount", "USD 2,000,000"],
        ["Facility type", "Term Loan — 5 years"],
        ["Purpose", "Warehouse expansion and working capital support"],
        ["Proposed drawdown", "Single drawdown, Q1 following approval"],
    ]
    t2 = Table(req_data, colWidths=[6 * cm, 9 * cm])
    t2.setStyle(legacy_style)
    story.append(t2)
    story.append(Spacer(1, 16))
    story.append(Paragraph("Collateral Offered", h2))
    story.append(Paragraph(
        "The applicant offers as collateral: (1) a commercial warehouse property located in the "
        "Free Zone, independently valued at USD 3,200,000 as of March 2025; and (2) a personal "
        "guarantee from the majority shareholder, Mr. Karim El-Sayed, covering the full facility "
        "amount.", body
    ))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Existing Bank Facilities (as declared by applicant)", h2))
    story.append(Paragraph(
        "USD 500,000 overdraft facility with National Bank (utilized ~60%), and a USD 300,000 trade "
        "finance line opened in Q2 2024 with the same institution. No facilities are held with other "
        "banks.", body
    ))
    build("acme_trading", "acme_trading_loan_application.pdf", story)

    # Beta low quality
    story = []
    story.append(Paragraph("Beta Supplies Co. — Financial Summary", h1))
    story.append(Paragraph("(Synthetic test document, intentionally degraded to test escalation behaviour.)", small))
    story.append(Spacer(1, 16))
    story.append(Paragraph(
        "Beta Supplies Co figures for the period are summarized below. Statement prepared internally, "
        "unaudited; some figures reported inconsistently between sections (kept intentionally for POC "
        "testing of conflict/ambiguity handling).", body
    ))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Summary Figures (Section A)", h2))
    story.append(Paragraph(
        "Total assets approx. 6,400 (thousands). Revenue for the year was about 9.1M. Figures are "
        "management estimates pending final audit sign-off.", body
    ))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Summary Figures (Section B — later in same document)", h2))
    story.append(Paragraph(
        "Total assets: 7,150,000. Currency not stated in this section. Net income line was omitted "
        "from this draft and will be provided in a follow-up submission. Existing facilities: "
        "'various, details with relationship manager'.", body
    ))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Note for POC: this document deliberately contains (a) a currency/unit ambiguity ('6,400' "
        "thousands vs '9.1M' vs '7,150,000' unqualified), (b) a conflicting total-assets figure "
        "between two sections, and (c) a missing required field (net income). Expected agent "
        "behaviour per SPEC.md: flag all of these as needs_review, do not guess a resolved value.",
        small
    ))
    build("beta_supplies", "beta_supplies_low_quality.pdf", story)


# ---------------------------------------------------------------------------
# Egyptian-style company sets
# ---------------------------------------------------------------------------

EGYPTIAN_CASES: list[CompanyCase] = [
    CompanyCase(
        slug="nile_delta_foods",
        legal_name="Nile Delta Foods S.A.E.",
        arabic_name="شركة دلتا النيل للأغذية ش.م.م",
        cr_number="CR 184729 (Cairo — GAFI)",
        tax_card="Tax Card 547-891-203",
        industry="Food Processing & Distribution",
        governorate="6th of October City, Giza",
        years_in_operation=18,
        bank_relationship_since=2014,
        auditor="Hassan Allam & Partners (Certified Public Accountants)",
        financial_years=[
            FinancialYear(
                year=2023,
                cash="8,420,000", receivables="22,150,000", inventory="31,800,000", ppe="45,600,000",
                total_assets="112,400,000", payables="18,900,000", short_term_debt="14,200,000",
                long_term_debt="22,500,000", total_liabilities="58,600,000", total_equity="53,800,000",
                annual_revenue="186,500,000", cogs="128,400,000", opex="38,200,000", interest="4,800,000",
                net_income="12,100,000",
                facilities_note=(
                    "The Group holds an EGP 15,000,000 revolving working-capital facility with "
                    "Suez Canal Bank (utilized at 72% as at 31 December 2023) and an EGP 8,000,000 "
                    "letter-of-credit line with National Bank of Egypt for raw-material imports."
                ),
            ),
            FinancialYear(
                year=2024,
                cash="11,200,000", receivables="25,400,000", inventory="34,600,000", ppe="48,900,000",
                total_assets="124,800,000", payables="21,300,000", short_term_debt="16,800,000",
                long_term_debt="24,100,000", total_liabilities="65,200,000", total_equity="59,600,000",
                annual_revenue="208,300,000", cogs="141,600,000", opex="42,500,000", interest="5,400,000",
                net_income="15,800,000",
                facilities_note=(
                    "Suez Canal Bank working-capital facility increased to EGP 18,000,000 in Q2 2024 "
                    "(utilized at 65%). NBE LC line unchanged at EGP 8,000,000. New EGP 5,000,000 "
                    "equipment finance line with Banque Misr signed in Q4 2024 for production line upgrade."
                ),
            ),
        ],
        loan_amount="EGP 25,000,000",
        loan_type="Term Loan — 7 years, quarterly amortisation",
        loan_purpose="Expansion of cold-storage capacity at 6th of October plant and seasonal working capital",
        collateral=(
            "First-ranking mortgage over production facility at Plot 14, Industrial Zone, 6th of October "
            "(independent valuation EGP 42,000,000 by CBE-registered valuer El Masreya, dated January 2025); "
            "assignment of receivables from top-3 retail customers; corporate guarantee from parent "
            "Nile Delta Holdings S.A.E.; personal guarantee of Mr. Ahmed Hassan Farouk (Managing Director)."
        ),
        existing_facilities_declared=(
            "EGP 18,000,000 working-capital facility with Suez Canal Bank (~65% utilized); "
            "EGP 8,000,000 LC line with National Bank of Egypt; EGP 5,000,000 equipment finance "
            "with Banque Misr (Q4 2024). CAP report dated February 2025 attached."
        ),
    ),
    CompanyCase(
        slug="alex_maritime",
        legal_name="Alexandria Maritime Services S.A.E.",
        arabic_name="شركة الإسكندرية للخدمات البحرية ش.م.م",
        cr_number="CR 90234 (Alexandria — GAFI)",
        tax_card="Tax Card 312-445-678",
        industry="Shipping Agency & Port Logistics",
        governorate="Alexandria",
        years_in_operation=22,
        bank_relationship_since=2010,
        auditor="BDO Egypt (Member of BDO International)",
        financial_years=[
            FinancialYear(
                year=2023,
                cash="15,600,000", receivables="38,400,000", inventory="2,100,000", ppe="28,700,000",
                total_assets="89,200,000", payables="24,500,000", short_term_debt="19,800,000",
                long_term_debt="8,400,000", total_liabilities="54,700,000", total_equity="34,500,000",
                annual_revenue="142,800,000", cogs="96,200,000", opex="32,100,000", interest="3,200,000",
                net_income="9,300,000",
                facilities_note=(
                    "Overdraft facility of EGP 12,000,000 with Suez Canal Bank (Alexandria branch), "
                    "utilized at 55%. Trade finance limit of EGP 20,000,000 with Commercial International "
                    "Bank (CIB) for import LC backing, partially drawn."
                ),
            ),
            FinancialYear(
                year=2024,
                cash="18,900,000", receivables="41,200,000", inventory="2,400,000", ppe="30,100,000",
                total_assets="96,500,000", payables="26,800,000", short_term_debt="21,500,000",
                long_term_debt="9,200,000", total_liabilities="59,500,000", total_equity="37,000,000",
                annual_revenue="158,600,000", cogs="105,400,000", opex="35,800,000", interest="3,600,000",
                net_income="11,200,000",
                facilities_note=(
                    "SCB overdraft unchanged at EGP 12,000,000 (utilization 48%). CIB trade finance "
                    "limit increased to EGP 25,000,000 in Q1 2024. No new long-term facilities during the year."
                ),
            ),
        ],
        loan_amount="EGP 18,000,000",
        loan_type="Revolving Credit Facility — 3 years, annual review",
        loan_purpose="Fleet maintenance, bunkering advances, and port-handling equipment lease deposits",
        collateral=(
            "Pledge of three vessel agency contracts with Mediterranean Shipping Co.; first-ranking "
            "charge over office and warehouse at Port of Alexandria, Block 7 (valued EGP 22,000,000); "
            "standby LC from parent Alexandria Group Holdings."
        ),
        existing_facilities_declared=(
            "EGP 12,000,000 overdraft with Suez Canal Bank (~48% utilized); EGP 25,000,000 trade "
            "finance limit with CIB. No facilities with other banks beyond CAP declaration."
        ),
    ),
    CompanyCase(
        slug="delta_construction",
        legal_name="Delta Construction & Contracting LLC",
        arabic_name="شركة دلتا للمقاولات والتشييد ذ.م.م",
        cr_number="CR 556781 (Cairo — GAFI)",
        tax_card="Tax Card 678-234-901",
        industry="General Contracting — Infrastructure & Real Estate",
        governorate="New Cairo, Cairo Governorate",
        years_in_operation=11,
        bank_relationship_since=2018,
        auditor="PricewaterhouseCoopers (PwC Egypt)",
        financial_years=[
            FinancialYear(
                year=2023,
                cash="22,400,000", receivables="68,500,000", inventory="12,300,000", ppe="18,900,000",
                total_assets="128,600,000", payables="45,200,000", short_term_debt="32,100,000",
                long_term_debt="15,800,000", total_liabilities="95,100,000", total_equity="33,500,000",
                annual_revenue="245,000,000", cogs="198,400,000", opex="28,600,000", interest="6,900,000",
                net_income="8,100,000",
                facilities_note=(
                    "Project finance facility of EGP 40,000,000 with Suez Canal Bank for New Capital "
                    "housing project (drawn EGP 28,500,000). EGP 10,000,000 bid-bond line with QNB Alahli."
                ),
            ),
            FinancialYear(
                year=2024,
                cash="19,800,000", receivables="74,200,000", inventory="14,600,000", ppe="20,400,000",
                total_assets="135,400,000", payables="48,900,000", short_term_debt="35,600,000",
                long_term_debt="18,200,000", total_liabilities="104,700,000", total_equity="30,700,000",
                annual_revenue="268,400,000", cogs="216,800,000", opex="31,200,000", interest="8,200,000",
                net_income="6,400,000",
                facilities_note=(
                    "SCB project finance drawn to EGP 35,000,000. Additional EGP 15,000,000 performance "
                    "bond facility with Suez Canal Bank opened Q3 2024 for Ministry of Housing contract."
                ),
            ),
        ],
        loan_amount="EGP 35,000,000",
        loan_type="Project Finance Term Loan — 5 years, milestone-linked disbursement",
        loan_purpose="Completion of Phase 2 residential blocks in New Administrative Capital (NAC) project",
        collateral=(
            "Assignment of receivables under Ministry of Housing contract MH-2023-NAC-4412; "
            "mortgage over equipment fleet (valued EGP 28,000,000); retention account with Suez Canal Bank."
        ),
        existing_facilities_declared=(
            "EGP 35,000,000 project finance + EGP 15,000,000 performance bond line with Suez Canal Bank; "
            "EGP 10,000,000 bid-bond line with QNB Alahli. CAP report attached."
        ),
    ),
    CompanyCase(
        slug="misr_pharma",
        legal_name="Misr Pharma Distribution S.A.E.",
        arabic_name="شركة مصر لتجارة الأدوية ش.م.م",
        cr_number="CR 334512 (Cairo — GAFI)",
        tax_card="Tax Card 891-567-234",
        industry="Pharmaceutical Wholesale & Distribution",
        governorate="Nasr City, Cairo",
        years_in_operation=15,
        bank_relationship_since=2016,
        auditor="KPMG Egypt",
        financial_years=[
            FinancialYear(
                year=2023,
                cash="6,800,000", receivables="41,500,000", inventory="52,300,000", ppe="14,200,000",
                total_assets="118,900,000", payables="38,600,000", short_term_debt="28,400,000",
                long_term_debt="6,500,000", total_liabilities="76,500,000", total_equity="42,400,000",
                annual_revenue="312,600,000", cogs="268,400,000", opex="28,900,000", interest="5,100,000",
                net_income="7,200,000",
                facilities_note=(
                    "Inventory financing line EGP 30,000,000 with Suez Canal Bank (utilized 81%). "
                    "EGP 5,000,000 overdraft with Arab African International Bank for payroll cycles."
                ),
            ),
            FinancialYear(
                year=2024,
                cash="8,100,000", receivables="44,800,000", inventory="56,700,000", ppe="15,600,000",
                total_assets="129,400,000", payables="41,200,000", short_term_debt="31,500,000",
                long_term_debt="7,800,000", total_liabilities="83,500,000", total_equity="45,900,000",
                annual_revenue="341,200,000", cogs="291,800,000", opex="31,400,000", interest="5,800,000",
                net_income="9,600,000",
                facilities_note=(
                    "SCB inventory line increased to EGP 35,000,000 (utilized 76%). AAIB overdraft "
                    "repaid and closed in Q2 2024. No new external facilities."
                ),
            ),
        ],
        loan_amount="EGP 20,000,000",
        loan_type="Inventory Financing Facility — 2 years, revolving",
        loan_purpose="Stocking of imported oncology and chronic-disease medications ahead of MOH tender season",
        collateral=(
            "Floating charge over pharmaceutical inventory (minimum coverage ratio 1.5x); "
            "warehouse at Plot 22, Industrial Zone, 10th of Ramadan (valued EGP 18,000,000); "
            "personal guarantees of Dr. Yasmine El-Masry (CEO) and Mr. Tarek Abdel Rahman (CFO)."
        ),
        existing_facilities_declared=(
            "EGP 35,000,000 inventory financing with Suez Canal Bank (~76% utilized). "
            "No other banking facilities as per CAP February 2025."
        ),
    ),
    CompanyCase(
        slug="cairo_textile",
        legal_name="Cairo Textile Exports S.A.E.",
        arabic_name="شركة القاهرة لتصدير المنسوجات ش.م.م",
        cr_number="CR 778901 (Alexandria Free Zone — GAFI)",
        tax_card="Tax Card 445-123-789",
        industry="Textile Manufacturing & Export",
        governorate="Alexandria Free Zone",
        years_in_operation=25,
        bank_relationship_since=2008,
        auditor="Ernst & Young (EY Egypt)",
        financial_years=[
            FinancialYear(
                year=2023,
                cash="4,200,000", receivables="28,600,000", inventory="19,400,000", ppe="38,200,000",
                total_assets="92,800,000", payables="16,800,000", short_term_debt="22,400,000",
                long_term_debt="12,600,000", total_liabilities="52,800,000", total_equity="40,000,000",
                annual_revenue="156,400,000", cogs="118,200,000", opex="24,800,000", interest="4,400,000",
                net_income="6,800,000",
                facilities_note=(
                    "Pre-shipment export finance EGP 18,000,000 with Suez Canal Bank (utilized 60%). "
                    "EGP 12,000,000 term loan with Export Development Bank of Egypt (EDBE) for machinery."
                ),
            ),
            FinancialYear(
                year=2024,
                cash="5,800,000", receivables="31,200,000", inventory="21,600,000", ppe="39,800,000",
                total_assets="100,400,000", payables="18,400,000", short_term_debt="24,100,000",
                long_term_debt="13,200,000", total_liabilities="57,700,000", total_equity="42,700,000",
                annual_revenue="172,900,000", cogs="129,600,000", opex="27,200,000", interest="4,900,000",
                net_income="8,500,000",
                facilities_note=(
                    "SCB pre-shipment facility increased to EGP 22,000,000. EDBE term loan balance "
                    "reduced to EGP 10,800,000 following scheduled repayments."
                ),
            ),
        ],
        loan_amount="EGP 15,000,000",
        loan_type="Export Pre-Shipment Finance — 180-day revolving",
        loan_purpose="Purchase of raw cotton and dyes for EU export orders (FW 2025/26 season)",
        collateral=(
            "Export receivables assignment (buyers: H&M, C&A, Inditex subsidiaries); "
            "machinery lien on spinning and weaving lines (valued EGP 35,000,000); "
            "Export Insurance Policy from Export Credit Guarantee Company of Egypt (ECGE)."
        ),
        existing_facilities_declared=(
            "EGP 22,000,000 pre-shipment finance with Suez Canal Bank; EGP 10,800,000 term loan "
            "balance with EDBE. CAP report attached."
        ),
    ),
    CompanyCase(
        slug="sinai_agro",
        legal_name="Sinai Agro-Industrial Co. S.A.E.",
        arabic_name="شركة سيناء للصناعات الزراعية ش.م.م",
        cr_number="CR 112890 (Ismailia — GAFI)",
        tax_card="Tax Card 234-678-345",
        industry="Agricultural Processing — Olive Oil & Packaged Foods",
        governorate="Ismailia",
        years_in_operation=9,
        bank_relationship_since=2019,
        auditor="El Nile Audit Office (FRA registered)",
        low_quality=True,
        low_quality_sections=[
            (
                "Section A — Management Estimates (draft)",
                "Total assets approx. 4,850 (thousands). Revenue for FY was about 62M. "
                "Figures are management estimates pending final audit sign-off by external auditor.",
            ),
            (
                "Section B — Summary attached later in same file",
                "Total assets: 5,420,000. Currency not stated in this section. Net income line was "
                "omitted from this draft and will be provided in a follow-up submission. Existing "
                "facilities: 'see relationship manager at branch'.",
            ),
            (
                "Section C — Working Capital Note",
                "Seasonal inventory build expected Q3. Bank lines 'renewed recently' but amounts "
                "not specified in this internal memo.",
            ),
        ],
    ),
]


def generate_company_set(case: CompanyCase) -> None:
    if case.low_quality:
        generate_low_quality(case)
        return
    for fy in case.financial_years:
        generate_financial_statement(case, fy)
    generate_loan_application(case)


def generate_all(selected: list[str] | None = None) -> None:
    if selected is None or "acme" in selected or "legacy" in selected:
        generate_legacy_acme()
    slugs = {c.slug for c in EGYPTIAN_CASES}
    for case in EGYPTIAN_CASES:
        if selected is not None and case.slug not in selected and "all" not in selected:
            continue
        generate_company_set(case)
    if selected is not None:
        unknown = set(selected) - slugs - {"acme", "legacy", "all"}
        if unknown:
            print(f"Warning: unknown set(s): {', '.join(sorted(unknown))}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic test PDF documents.")
    parser.add_argument(
        "--set", action="append", dest="sets",
        help="Generate only specified set(s): acme, nile_delta_foods, alex_maritime, "
             "delta_construction, misr_pharma, cairo_textile, sinai_agro, or 'all' (default: all)",
    )
    args = parser.parse_args()
    generate_all(args.sets)
    print(f"\nAll requested documents generated in {OUT_DIR}")


if __name__ == "__main__":
    main()
