# Test dokumenti (sintetički)

**Napomena:** SCB nije dostavio realne uzorke. Dokumenti su **u potpunosti izmišljeni** radi
testiranja pipeline-a: fiktivne kompanije, fiktivni brojevi, fiktivne banke. Bilo kakva sličnost
sa stvarnim entitetima je slučajna.

Format novih setova modelovan je po praksi **egipatskih banaka** (CBE, GAFI komercijalni registar,
EGP valuta, CAP pozicija, FRA-registrovan revizor, SCB — Suez Canal Bank kao odnosna banka u
fiktivnim podacima). Stari Acme/Beta set ostaje za backward compatibility sa postojećim testovima.

## Struktura foldera

Svaka firma ima svoj podfolder:

```
sample_docs/
├── generate_sample_docs.py
├── acme_trading/
│   ├── acme_trading_financial_statements_fy2023.pdf
│   ├── acme_trading_financial_statements_fy2024.pdf
│   └── acme_trading_loan_application.pdf
├── beta_supplies/
│   └── beta_supplies_low_quality.pdf
├── nile_delta_foods/
│   └── ...
├── alex_maritime/
├── delta_construction/
├── misr_pharma/
├── cairo_textile/
└── sinai_agro/
    └── sinai_agro_low_quality.pdf
```

Generisana su skriptom [`generate_sample_docs.py`](generate_sample_docs.py):

```bash
.venv/bin/python sample_docs/generate_sample_docs.py              # svi setovi
.venv/bin/python sample_docs/generate_sample_docs.py --set nile_delta_foods   # jedan set
```

**Prioritet #1 posle inicijalnog POC-a:** zameniti ova dokumenta sa 2–3 realna (anonimizovana) SCB
dokumenta čim budu dostupna.

---

## Set 1 — Acme / Beta (legacy, koristi se u testovima)

| Fajl | Šta predstavlja | Namena |
|---|---|---|
| `acme_trading/...fy2023.pdf` | Godišnji finansijski izveštaj (USD), FY2023 | "Čist" dokument — osnovna ekstrakcija |
| `acme_trading/...fy2024.pdf` | Isto, FY2024 | Drugi period, isti format |
| `acme_trading/...loan_application.pdf` | Zahtev za kreditnu liniju | Polja: requested amount, collateral, existing facilities |
| `beta_supplies/...low_quality.pdf` | Namerno loš sažetak | Eskalacija — konflikti, nejasna valuta, missing fields |

Ground truth: [`../evaluation/ground_truth.md`](../evaluation/ground_truth.md)

---

## Setovi 2–7 — Egipatske firme

| Folder | Kompanija | Industrija |
|---|---|---|
| `nile_delta_foods/` | Nile Delta Foods S.A.E. | Prehrambena industrija |
| `alex_maritime/` | Alexandria Maritime Services S.A.E. | Brodarstvo / logistika |
| `delta_construction/` | Delta Construction & Contracting LLC | Građevinarstvo |
| `misr_pharma/` | Misr Pharma Distribution S.A.E. | Farmaceutska distribucija |
| `cairo_textile/` | Cairo Textile Exports S.A.E. | Tekstil / export |
| `sinai_agro/` | Sinai Agro-Industrial Co. S.A.E. | Loš kvalitet — test eskalacije |

Svaka “čista” firma ima: FY2023 + FY2024 finansijske izveštaje + loan application (3 PDF-a).

**Ukupno: 20 PDF dokumenata u 7 foldera.**
