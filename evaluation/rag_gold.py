"""
Gold question set for the RAG demo (SPEC.md §9).

Each entry: a query, the `doc_id` whose chunk should come back at rank 1, and a short phrase that
MUST appear in that top chunk (proves the retrieval landed on the right paragraph, not just the
right file). `chunk_id` is intentionally NOT asserted — it shifts if chunk sizes change; the
phrase check is the stable "did it hit the right passage" signal.

This is a hit/miss check on ~12 questions, NOT the proposal §9.3 "retrieval precision >= 90%"
KPI — the corpus is deliberately too small to be statistically meaningful (SPEC.md §9).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GoldQuery:
    query: str
    lang: str
    expect_doc_id: str
    expect_phrase: str  # must be a substring of the rank-1 chunk


GOLD: list[GoldQuery] = [
    # --- English ---
    GoldQuery("What is the maximum tenor for an SME working capital facility?", "en",
              "en_sme_lending", "maximum tenor of 36 months"),
    GoldQuery("How many years of audited financials are required above EGP 20 million?", "en",
              "en_sme_lending", "two years of audited financial statements"),
    GoldQuery("What is the loan-to-value limit for commercial real estate collateral?", "en",
              "en_collateral_ltv", "loan-to-value ratio is 70%"),
    GoldQuery("What coverage ratio is required for inventory pledged under a floating charge?", "en",
              "en_collateral_ltv", "coverage ratio of 1.5 times"),
    GoldQuery("What is the minimum debt service coverage ratio for a new term loan?", "en",
              "en_credit_risk_ratios", "debt service coverage ratio (DSCR) for a new term facility is 1.25"),
    GoldQuery("Which business activities is the bank prohibited from financing?", "en",
              "en_prohibited_activities", "gambling or betting"),
    GoldQuery("Is lending to agriculture and food processing allowed?", "en",
              "en_prohibited_activities", "agricultural and food-processing lending is permitted"),
    # --- Arabic ---
    GoldQuery("ما هي المدة القصوى لتسهيل رأس المال العامل للشركات الصغيرة والمتوسطة؟", "ar",
              "ar_sme_tenor", "أقصاها 36 شهراً"),
    GoldQuery("ما الحد الأقصى لنسبة التمويل إلى القيمة للعقارات التجارية؟", "ar",
              "ar_real_estate_ltv", "70% من"),
    GoldQuery("ما نسبة التغطية المطلوبة للمخزون المرهون برهن حيازي عائم؟", "ar",
              "ar_real_estate_ltv", "1.5 مرة"),
    GoldQuery("متى يُدرَج العميل على قائمة المتابعة؟", "ar",
              "ar_watchlist_restructuring", "قائمة المتابعة"),
    GoldQuery("هل يجوز إعادة هيكلة التسهيل دون موافقة لجنة الائتمان؟", "ar",
              "ar_watchlist_restructuring", "بموافقة لجنة الائتمان بالمركز الرئيسي"),
    GoldQuery("ما القطاعات التي تتطلب مراجعة بيئية واجتماعية قبل الموافقة؟", "ar",
              "ar_prohibited_sectors", "تقييماً للمخاطر البيئية والاجتماعية"),
]
