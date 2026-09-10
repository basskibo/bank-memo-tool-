"""
Python verzija ground_truth.md — koristi je run_demo.py za automatsko poređenje.
Ako menjaš očekivane vrednosti, izmeni OBA fajla (ovaj i ground_truth.md) da ostanu u skladu.
"""

# filename -> {field_name: expected_status}. "n/a" znači "polje se ne pojavljuje u dokumentu,
# ne sme biti izmišljeno" — proverava se posebno (odsustvo, ne pogrešan status).
EXPECTED: dict[str, dict[str, str]] = {
    "acme_trading_financial_statements_fy2023.pdf": {
        "company_name": "confirmed",
        "reporting_period": "confirmed",
        "total_assets": "confirmed",
        "total_liabilities": "confirmed",
        "total_equity": "confirmed",
        "annual_revenue": "confirmed",
        "net_income": "confirmed",
        "existing_bank_facilities": "confirmed",
    },
    "acme_trading_financial_statements_fy2024.pdf": {
        "company_name": "confirmed",
        "reporting_period": "confirmed",
        "total_assets": "confirmed",
        "total_liabilities": "confirmed",
        "total_equity": "confirmed",
        "annual_revenue": "confirmed",
        "net_income": "confirmed",
        "existing_bank_facilities": "confirmed",
    },
    "acme_trading_loan_application.pdf": {
        "company_name": "confirmed",
        # Loan application forma nema računovodstveni reporting period ("year ended") — pipeline
        # ne sme da ga potvrdi. needs_review je ispravno; confirmed = false confidence.
        "reporting_period": "needs_review",
        "existing_bank_facilities": "confirmed",
        "requested_facility_amount": "confirmed",
        "collateral_offered": "confirmed",
    },
    "beta_supplies_low_quality.pdf": {
        # Namerno pokvaren dokument — SVE ovo MORA biti needs_review, ne confirmed.
        # Ako pipeline ovde vrati "confirmed", to je kritičan guardrail nalaz (SPEC.md sekcija 5).
        "total_assets": "needs_review",
        "annual_revenue": "needs_review",
        "net_income": "needs_review",
        "existing_bank_facilities": "needs_review",
    },
}
