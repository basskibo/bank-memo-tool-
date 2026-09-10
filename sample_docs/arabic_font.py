"""Noto Naskh Arabic + reshape/bidi for sample PDF generators.

ReportLab's built-in Helvetica has no Arabic glyphs, so logical-order Arabic is drawn as
.notdef boxes (tofu). PIL on the scanned-doc generator needs the same font plus contextual
reshaping. Fonts live in sample_docs/fonts/ (SIL Open Font License).
"""
from __future__ import annotations

from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display

FONTS_DIR = Path(__file__).resolve().parent / "fonts"
REGULAR_TTF = FONTS_DIR / "NotoNaskhArabic-Regular.ttf"
BOLD_TTF = FONTS_DIR / "NotoNaskhArabic-Bold.ttf"
ARABIC_FONT_NAME = "NotoNaskhArabic"
ARABIC_FONT_BOLD_NAME = "NotoNaskhArabic-Bold"

_registered = False


def shape_arabic(text: str) -> str:
    """Contextual letter forms + visual RTL order for LTR canvas APIs (ReportLab, PIL)."""
    if not text:
        return text
    return get_display(arabic_reshaper.reshape(text))


def require_regular() -> Path:
    if not REGULAR_TTF.is_file():
        raise FileNotFoundError(
            f"Missing Arabic font {REGULAR_TTF}. Place Noto Naskh Arabic Regular.ttf in "
            "sample_docs/fonts/ (SIL OFL)."
        )
    return REGULAR_TTF


def require_bold() -> Path:
    if BOLD_TTF.is_file():
        return BOLD_TTF
    return require_regular()


def register_reportlab_arabic_font() -> str:
    """Embed Noto Naskh Arabic so ReportLab can draw real glyphs instead of .notdef boxes."""
    global _registered
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if not _registered:
        pdfmetrics.registerFont(TTFont(ARABIC_FONT_NAME, str(require_regular())))
        pdfmetrics.registerFont(TTFont(ARABIC_FONT_BOLD_NAME, str(require_bold())))
        _registered = True
    return ARABIC_FONT_NAME
