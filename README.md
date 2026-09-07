# Credit Memo Agent — POC

Pre bilo čega drugog, pročitaj:

1. **[SPEC.md](SPEC.md)** — šta se gradi, koji su kontrakti između delova, šta je namerno van
   obima i zašto. Izvor istine.
2. **[PLAN.md](PLAN.md)** — dan-po-dan plan rada i gate-ovi.

## Status

- ✅ Document Ingestor radi (testirano na sva 4 test dokumenta, `tests/test_document_ingestor.py`)
- ✅ LangGraph orkestracija (ingest → extract → validate) se kompajlira i radi
- ✅ Citation Validator implementiran (deterministički, bez LLM-a)
- ✅ `run_demo.py` — end-to-end demo skripta
- ✅ LLM provider je konfigurabilan: **Ollama** (lokalni/mrežni server) ili **Anthropic API**,
  isti kod za oba (`src/llm_client.py`) — SPEC.md sekcija 8 princip
- ⬜ Financial Wizard i Narrative Synthesizer (LLM pozivi) **nisu još pokrenuti do kraja sa
     stvarnim odgovorima** — to je sledeći korak, i to radiš ti (vidi ispod).
- ⬜ Review UI (Streamlit) je napisan, nije još ručno proveren u browseru.

## Kako pokrenuti (3 koraka)

**1. Setup (jednom):**
```bash
cd poc
python3 -m venv .venv          # preskoči ako .venv već postoji
.venv/bin/pip install -r requirements.txt
```

**2. Podesi LLM provider — lokalno, ne kroz chat:**
```bash
cp .env.example .env
```
Otvori `poc/.env` u editoru. Difolt je Ollama (koristi isti server kao drugi projekat):
```
POC_LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://mcs02.cmu:11434
OLLAMA_MODEL=qwen2.5:3b
```
Ako umesto toga želiš Anthropic API, promeni `POC_LLM_PROVIDER=api` i upiši pravi ključ u
`ANTHROPIC_API_KEY=` (ne ostavljaj placeholder `sk-ant-...` iz primera — to je bio uzrok prve
401 greške). `.env` je u `.gitignore` i neće se slučajno commit-ovati.

**Napomena o kvalitetu:** `qwen2.5:3b` je mali model — dobar za brzu proveru da li pipeline radi,
ali očekuj da JSON/citation disciplina bude manje pouzdana nego kod većih modela. Zbog toga
Financial Wizard i Narrative Synthesizer namerno pitaju model **po jedno polje / po jedna
sekcija odjednom** (~10 malih poziva po dokumentu za ekstrakciju), umesto jednog velikog poziva —
sporije, ali mnogo pouzdanije za slabije modele (vidi komentar na vrhu `financial_wizard.py`).
Ovo znači da jedan `run_demo.py` prolaz može potrajati par minuta. Ako izvučena polja i dalje
budu loša i posle ovoga, prva stvar za probati je veći model sa istog servera (`mistral:7b`,
`llama3.1:8b`, ako su povučeni) pre nego što se sumnja na pristup/prompt.

**3. Pokreni demo:**
```bash
.venv/bin/python run_demo.py
```

Ovo radi sledeće, uživo, u terminalu:
- pušta sva 4 test dokumenta kroz ceo pipeline (ingest → extract → validate),
- za svaki ispisuje tabelu izvučenih polja sa statusom (`confirmed` / `needs_review`) i poredi sa
  očekivanim vrednostima iz `evaluation/expected_values.py`,
- posebno proverava **kritičan slučaj**: da li se namerno pokvaren dokument
  (`beta_supplies_low_quality.pdf`) ispravno eskalira umesto da se pogrešno prihvati,
- na kraju generiše i ispisuje nacrt kreditnog memoranduma za najčistiji dokument (fy2023), sa
  guardrail proverom da li ijedna brojka u tekstu nema pokriće u izvornim podacima.

Ako nešto ne prođe kako se očekuje — to nije nužno bug, to je tačno ono što POC treba da otkrije
(vidi PLAN.md, "Izlazna odluka posle POC-a").

### Preporučeno: SCB Credit Memo Portal (interaktivni UI)

```bash
.venv/bin/streamlit run src/review/app.py
```
Otvara se u browseru na `http://localhost:8501` (ili preko `preview_start`/`.claude/launch.json`
u ovom radnom okruženju — konfiguracija `scb-credit-memo-portal` na portu 8765). Ovo je bank-
stilizovan portal koji najbliže liči na to kako bi stvarni credit officer koristio alat:

- **Drag-and-drop upload** proizvoljnog PDF dokumenta (ili izbor jednog od 4 test dokumenta iz
  `sample_docs/`).
- **Živ prikaz obrade** — dok pipeline radi, vidi se tačno koje polje/sekcija se trenutno
  obrađuje (`st.status()` sa live log-om), ne samo spinner bez konteksta.
- **Review korak** — polja koja zahtevaju pregled se prikazuju sa predloženom vrednošću, izvorom
  i mogućnošću ispravke/potvrde, isto kao i pre.
- **Generisanje i preuzimanje izveštaja** — posle generisanja memoranduma, dugme "Download report
  (PDF)" pravi kompletan PDF izveštaj (izvučena polja + nacrt memoranduma + guardrail nalaz) preko
  `reports/live_report.py`, na licu mesta, za taj konkretan upload.

Podržava više uploadovanih dokumenata odjednom — svaki dobija svoju karticu i obrađuje se
nezavisno (POC trenutno ne kombinuje više dokumenata u jedan memo — SPEC.md 3.1.2 podržava to za
Financial Wizard, ali orkestracija u `graph.py` još radi jedan-dokument-po-pozivu).

### Testovi (ne traže LLM provider)

```bash
.venv/bin/python -m pytest tests/ -v
```

**Regeneracija test dokumenata** (ako menjaš brojeve u njima):
```bash
.venv/bin/python sample_docs/generate_sample_docs.py
```

## Struktura projekta

```
poc/
├── SPEC.md                   # izvor istine — šta i kako
├── PLAN.md                   # dan-po-dan plan
├── run_demo.py                # ← pokreni ovo prvo
├── .env.example                # kopiraj u .env; bira Ollama ili Anthropic API
├── sample_docs/                # sintetička test PDF dokumenta + generator skripta
├── evaluation/
│   ├── ground_truth.md         # očekivane vrednosti, čitljivo (SPEC.md sekcija 5)
│   └── expected_values.py      # ista stvar, mašinski čitljivo — koristi je run_demo.py
├── src/
│   ├── models/schemas.py       # data contracts (IngestedDocument, ExtractedField, DraftMemo)
│   ├── agents/
│   │   ├── document_ingestor.py     # PDF → IngestedDocument (bez LLM-a)
│   │   ├── financial_wizard.py      # IngestedDocument → ExtractedField[] (LLM)
│   │   ├── citation_validator.py    # provera citata (bez LLM-a)
│   │   └── narrative_synthesizer.py # ExtractedField[] → DraftMemo (LLM) + guardrail provera
│   ├── orchestration/graph.py       # LangGraph wiring + apply_human_review()
│   ├── review/app.py                 # SCB Credit Memo Portal — Streamlit UI (upload, live log, report)
│   ├── llm_client.py                 # Ollama + Anthropic API wrapper (isti interfejs)
│   └── config.py                     # učitava .env, bira provider
├── reports/
│   ├── pdf_common.py                 # deljeni ReportLab stilovi/tabele
│   ├── generate_report.py            # snapshot izveštaj za Run 1 (evaluation/FINDINGS.md)
│   └── live_report.py                # PDF izveštaj za JEDAN stvaran upload, koristi ga portal
└── tests/
```

`../.claude/launch.json` (van `poc/`) sadrži `scb-credit-memo-portal` konfiguraciju za pokretanje
portala preko `preview_start` u ovom radnom okruženju, na portu 8765.

## Sledeći koraci (vidi PLAN.md)

1. Ti: podesi `poc/.env` (Ollama ili API), pokreni `run_demo.py`, pošalji mi/nama šta je
   ispisano (posebno da li je beta_supplies test prošao kao "OK" ili "KRITIČAN NALAZ").
2. Na osnovu toga dorađujemo prompt u `financial_wizard.py` ako nešto promašuje.
3. Probaj Streamlit UI uživo.
4. Popuni `evaluation/FINDINGS.md` (PLAN.md Dan 10) sa stvarnim rezultatima kad budemo imali
   više od jedne vožnje.
# bank-memo-tool-
