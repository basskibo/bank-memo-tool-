"""
Shared ReportLab building blocks for PDF reports (styles, table formatting, callout boxes).
Used by generate_report.py (Run 1 snapshot) and live_report.py (per-upload portal report) so
both look consistent without duplicating style code.
"""
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Table, TableStyle

styles = getSampleStyleSheet()

title_style = styles["Title"]
subtitle_style = ParagraphStyle("subtitle", parent=styles["Normal"], fontSize=11,
                                  textColor=colors.grey, spaceAfter=20)
h1 = ParagraphStyle("h1", parent=styles["Heading1"], spaceBefore=18, spaceAfter=8,
                     textColor=colors.HexColor("#1a1a1a"))
h2 = ParagraphStyle("h2", parent=styles["Heading2"], spaceBefore=12, spaceAfter=6,
                     textColor=colors.HexColor("#2b2b2b"))
body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10, leading=14, spaceAfter=8)
small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, textColor=colors.grey)
callout_text = ParagraphStyle("callout", parent=styles["Normal"], fontSize=10, leading=14,
                                textColor=colors.HexColor("#7a1f1f"))
cell_text = ParagraphStyle("cell", parent=styles["Normal"], fontSize=8, leading=10)

TABLE_STYLE = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b2b2b")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
    ("FONTSIZE", (0, 0), (-1, -1), 8),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
])


def status_color(status: str) -> colors.Color:
    return colors.HexColor("#1a7a3c") if status == "confirmed" else colors.HexColor("#a86a00")


def match_color(match: str) -> colors.Color:
    if match == "OK":
        return colors.HexColor("#1a7a3c")
    if match == "MISMATCH":
        return colors.HexColor("#b02a2a")
    return colors.grey


def callout_box(text: str, border_color=colors.HexColor("#b02a2a"),
                 bg_color=colors.HexColor("#fdecec")) -> Table:
    t = Table([[Paragraph(text, callout_text)]], colWidths=[17 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg_color),
        ("BOX", (0, 0), (-1, -1), 1.2, border_color),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    return t


def field_result_table(rows: list[dict]) -> Table:
    """rows: list of {"field", "value", "page", "status", "expected", "match"}."""
    header = ["Field", "Value", "Pg", "Status", "Expected", "Match"]
    data = [header]
    for r in rows:
        # Value can be arbitrarily long (e.g. a full sentence extracted from a document) — wrap it
        # in a Paragraph so ReportLab wraps it across lines instead of overflowing into the next
        # column. Plain strings in Table cells do NOT wrap on their own.
        data.append([r["field"], Paragraph(str(r["value"]), cell_text), str(r["page"]),
                     r["status"], r["expected"], r["match"]])

    t = Table(data, colWidths=[4.2 * cm, 5.3 * cm, 1 * cm, 2.3 * cm, 2.3 * cm, 2 * cm])
    style_cmds = list(TABLE_STYLE.getCommands())
    for i, r in enumerate(rows, start=1):
        style_cmds.append(("TEXTCOLOR", (3, i), (3, i), status_color(r["status"])))
        style_cmds.append(("TEXTCOLOR", (5, i), (5, i), match_color(r["match"])))
        style_cmds.append(("FONTNAME", (5, i), (5, i), "Helvetica-Bold"))
    t.setStyle(TableStyle(style_cmds))
    return t
