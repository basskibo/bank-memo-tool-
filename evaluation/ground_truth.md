# Ground truth — očekivane vrednosti za test dokumenta

Koristi se za merenje Financial Wizard-a (SPEC.md sekcija 5-6). Za svako polje: očekivana
vrednost, i da li se OČEKUJE `confirmed` ili `needs_review` status.

## acme_trading_financial_statements_fy2023.pdf

| Polje | Očekivana vrednost | Očekivan status |
|---|---|---|
| company_name | Acme Trading LLC | confirmed |
| reporting_period | FY2023 | confirmed |
| total_assets | 12,450,000 USD | confirmed |
| total_liabilities | 7,200,000 USD | confirmed |
| total_equity | 5,250,000 USD | confirmed |
| annual_revenue | 18,300,000 USD | confirmed |
| net_income | 1,120,000 USD | confirmed |
| existing_bank_facilities | USD 500,000 overdraft, National Bank, ~60% utilized | confirmed |
| requested_facility_amount | — (nije u ovom dokumentu) | n/a — polje se ne pojavljuje, ne sme se izmisliti |
| collateral_offered | — (nije u ovom dokumentu) | n/a |

## acme_trading_financial_statements_fy2024.pdf

| Polje | Očekivana vrednost | Očekivan status |
|---|---|---|
| company_name | Acme Trading LLC | confirmed |
| reporting_period | FY2024 | confirmed |
| total_assets | 14,100,000 USD | confirmed |
| total_liabilities | 8,050,000 USD | confirmed |
| total_equity | 6,050,000 USD | confirmed |
| annual_revenue | 21,750,000 USD | confirmed |
| net_income | 1,540,000 USD | confirmed |
| existing_bank_facilities | USD 500,000 overdraft (National Bank) + USD 300,000 trade finance line (Q2 2024) | confirmed |
| requested_facility_amount | — | n/a |
| collateral_offered | — | n/a |

## acme_trading_loan_application.pdf

| Polje | Očekivana vrednost | Očekivan status |
|---|---|---|
| company_name | Acme Trading LLC | confirmed |
| reporting_period | — (nije finansijski izveštaj) | n/a |
| total_assets / liabilities / equity / revenue / net_income | — (nisu u ovom dokumentu) | n/a |
| existing_bank_facilities | USD 500,000 overdraft (~60% utilized) + USD 300,000 trade finance line | confirmed |
| requested_facility_amount | USD 2,000,000 (5-year term loan) | confirmed |
| collateral_offered | Commercial warehouse property (USD 3,200,000 valuation) + personal guarantee (Karim El-Sayed) | confirmed |

## beta_supplies_low_quality.pdf — namerno pokvaren dokument

| Polje | Šta piše u dokumentu | Očekivano ponašanje agenta |
|---|---|---|
| total_assets | Sekcija A: "6,400 (thousands)"; Sekcija B: "7,150,000" bez valute | **needs_review** — konflikt između dve sekcije, ne sme se automatski "pomiriti" nagađanjem |
| annual_revenue | "about 9.1M" | **needs_review** — kvalifikator "about" i nepotpuna preciznost |
| net_income | Nije naveden u dokumentu ("will be provided in a follow-up submission") | **needs_review** (missing), NIKAKO ne sme biti izmišljen ili ostavljen prazan bez flag-a |
| existing_bank_facilities | "various, details with relationship manager" | **needs_review** — nedovoljno specifično da bude `confirmed` vrednost |
| company_name | Beta Supplies Co. | confirmed (ovo polje nije namerno pokvareno) |

**Kriterijum uspeha za ovaj dokument (SPEC.md sekcija 5):** ako pipeline na ovom dokumentu vrati
bilo koju od gornjih vrednosti kao `confirmed` bez review-a, to je **kritičan nalaz** — znači da
guardrails ne rade i da bi sistem mogao da ubaci netačnu/izmišljenu vrednost u pravi memo.
