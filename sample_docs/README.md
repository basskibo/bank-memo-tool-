# Test dokumenti (sintetički)

**Napomena:** SCB nije dostavio realne uzorke, a bankarski domen nije nam dobro poznat, pa su ova
četiri dokumenta **u potpunosti izmišljena** radi testiranja pipeline-a: fiktivne kompanije,
fiktivni brojevi, fiktivna banka ("National Bank"). Bilo kakva sličnost sa stvarnim entitetima je
slučajna. Generisana su skriptom [`generate_sample_docs.py`](generate_sample_docs.py) —
pokreni je ponovo ako želiš da izmeniš brojeve.

**Prioritet #1 posle inicijalnog POC-a:** zameniti ova dokumenta sa 2–3 realna (anonimizovana) SCB
dokumenta čim budu dostupna. Sintetika ne testira stvarnu varijabilnost formata, jezika ili
kvaliteta skena koje pipeline mora da izdrži u produkciji.

## Lista dokumenata

| Fajl | Šta predstavlja | Namena u testiranju |
|---|---|---|
| `acme_trading_financial_statements_fy2023.pdf` | Godišnji finansijski izveštaj (bilans stanja + bilans uspeha) fiktivne trgovinske kompanije, FY2023 | "Čist" dokument — osnovna ekstrakcija treba da radi skoro savršeno |
| `acme_trading_financial_statements_fy2024.pdf` | Isto, FY2024, iste kompanije | Drugi period — testira da li se ekstrakcija ponaša konzistentno na dva dokumenta istog formata |
| `acme_trading_loan_application.pdf` | Zahtev za kreditnu liniju iste kompanije — traženi iznos, kolateral, postojeće obaveze | Testira polja koja se ne nalaze u finansijskim izveštajima (`requested_facility_amount`, `collateral_offered`) |
| `beta_supplies_low_quality.pdf` | Namerno loš/nekonzistentan "finansijski sažetak" druge fiktivne kompanije | **Namerno pokvaren** — konfliktne vrednosti, nejasna valuta/jedinica, nedostajuće polje (net income). Testira da li agent ispravno eskalira umesto da nagađa (SPEC.md sekcija 4-5) |

Očekivane vrednosti (ground truth) za merenje tačnosti Financial Wizard-a su u
[`../evaluation/ground_truth.md`](../evaluation/ground_truth.md).
