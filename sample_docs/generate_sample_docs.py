"""
Generiše sintetička test PDF dokumenta za POC (fiktivne kompanije, izmišljeni brojevi).
Pokretanje: .venv/bin/python sample_docs/generate_sample_docs.py
"""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)

OUT_DIR = Path(__file__).parent
styles = getSampleStyleSheet()
h1 = styles["Title"]
h2 = ParagraphStyle("h2", parent=styles["Heading2"], spaceBefore=14, spaceAfter=6)
body = styles["Normal"]
small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, textColor=colors.grey)

TABLE_STYLE = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b2b2b")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
])


def build(filename: str, story: list):
    doc = SimpleDocTemplate(
        str(OUT_DIR / filename), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
    )
    doc.build(story)
    print(f"Generated {filename}")


# ---------------------------------------------------------------------------
# 1. Acme Trading LLC — Financial Statements FY2023
# ---------------------------------------------------------------------------
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
t.setStyle(TABLE_STYLE)
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
t2.setStyle(TABLE_STYLE)
story.append(t2)
story.append(Spacer(1, 16))

story.append(Paragraph("Notes on Existing Bank Facilities", h2))
story.append(Paragraph(
    "Acme Trading LLC maintains an existing overdraft facility of USD 500,000 with National "
    "Bank, utilized at approximately 60% as of the statement date. No other outstanding "
    "credit facilities were held as of 31 December 2023.", body
))
build("acme_trading_financial_statements_fy2023.pdf", story)


# ---------------------------------------------------------------------------
# 2. Acme Trading LLC — Financial Statements FY2024
# ---------------------------------------------------------------------------
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
t.setStyle(TABLE_STYLE)
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
t2.setStyle(TABLE_STYLE)
story.append(t2)
story.append(Spacer(1, 16))

story.append(Paragraph("Notes on Existing Bank Facilities", h2))
story.append(Paragraph(
    "Acme Trading LLC continues to hold an overdraft facility of USD 500,000 with National Bank "
    "(unchanged from the prior year). In Q2 2024, the company opened an additional trade finance "
    "line of USD 300,000 with the same institution to support seasonal import cycles.", body
))
build("acme_trading_financial_statements_fy2024.pdf", story)


# ---------------------------------------------------------------------------
# 3. Acme Trading LLC — Loan / Facility Application
# ---------------------------------------------------------------------------
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
t.setStyle(TABLE_STYLE)
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
t2.setStyle(TABLE_STYLE)
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
build("acme_trading_loan_application.pdf", story)


# ---------------------------------------------------------------------------
# 4. Beta Supplies Co. — deliberately low-quality / ambiguous document
#    (za testiranje da agent eskalira umesto da nagađa)
# ---------------------------------------------------------------------------
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
build("beta_supplies_low_quality.pdf", story)

print("\nAll sample documents generated in", OUT_DIR)
