# PLAN — Credit Memo Agent POC

Prati [SPEC.md](SPEC.md) — ako nešto ovde nije jasno definisano, referenca je uvek spec, ne ovaj
plan. Plan je operativan (šta se radi kog dana), spec je normativan (šta se gradi i kako).

**Tim:** 2–3 osobe (1 backend/agent developer, 1 koji pokriva orkestraciju+review UI, opciono 1 za
test dokumenta/evaluaciju — može biti ista osoba kao developer ako je tim od 2).
**Trajanje:** 2 nedelje core rad + 3. nedelja kao bafer/nalazi-izveštaj (ne mora biti puna nedelja).

---

## Nedelja 0 (pre starta) — Preduslovi

Ovo mora biti spremno pre Dana 1, inače se prva nedelja gubi na čekanje:

- [ ] Python okruženje, repo, `requirements.txt` (vidi kod skelet)
- [ ] Pristup LLM-u (API ključ ili lokalni model) — odluka pre starta, ne tokom
- [ ] Sintetička test dokumenta gotova (sekcija 7 u SPEC-u) — **ovo radimo mi u ovoj sesiji**, ne
      čeka se SCB
- [ ] Ako SCB u međuvremenu pošalje 2-3 realna (anonimizovana) dokumenta — ubaciti ih čim stignu,
      to je najveći mogući skok u kvalitetu nalaza POC-a

---

## Nedelja 1 — Pipeline do potvrđenih polja

**Cilj nedelje:** dokument uđe kao PDF, izađe kao lista tačno izvučenih i citiranih polja.

| Dan | Fokus | Deliverable |
|---|---|---|
| Dan 1 | Setup projekta, schemas (`IngestedDocument`, `ExtractedField`), LangGraph skeleton sa stub čvorovima koji samo prosleđuju podatke | Prazan end-to-end graf koji se pokreće bez greške |
| Dan 2 | Document Ingestor — realna implementacija (pdfplumber/PyMuPDF ekstrakcija, quality check, klasifikacija tipa dokumenta) | Ingestor radi nad 2-3 test PDF-a, tekst se čisto izvlači |
| Dan 3 | Financial Wizard v1 — LLM poziv koji izvlači 10 polja iz sekcije 6 SPEC-a, sa `source_page`/`source_snippet` | Polja se izvlače iz test dokumenata (možda još nisu savršena) |
| Dan 4 | Citation Validator — provera da snippet zaista postoji na navedenoj strani; routing na `confirmed`/`needs_review` | Lažni/netačni citati se hvataju i označavaju |
| Dan 5 | ✅ **Gotovo** (2026-09-07, Run 2) — pun pipeline pokrenut na **svih 20** trenutnih test dokumenata (ne 5-10, korpus je u međuvremenu narastao), rezultati u `evaluation/FINDINGS.md` | 124/125 polja status-kalibrisano tačno, 0 opasnih grešaka, `evaluation/sweep_results.json` |

**Gate na kraju nedelje 1:** da li Financial Wizard uopšte pogađa realan broj polja (npr. bar
6-7/10)? ✅ **Prošao, i to daleko iznad praga** — sa Anthropic API (`claude-haiku-4-5`) pipeline
pogađa 124/125 (99.2%) status-kalibracije na 20 dokumenata. Sa lokalnim `qwen2.5:3b` (Run 1)
prag je i dalje prošao (6-8/10) ali sa slabijom kalibracijom (12.5% opasnih grešaka).

---

## Nedelja 2 — Review, memo, end-to-end demo

**Cilj nedelje:** čovek može da pregleda izuzetke i dobije čitljiv nacrt memoranduma.

| Dan | Fokus | Deliverable |
|---|---|---|
| Dan 6 | Prost review UI (Streamlit): prikaz `needs_review` polja sa snippet/stranicom, dugme potvrdi/ispravi | Reviewer može ručno da reši sve otvorene izuzetke |
| Dan 7 | Narrative Synthesizer — generisanje `DraftMemo` iz potvrđenih polja, po sekcijama, sa citatom uz svaku brojku | Nacrt memoranduma se generiše, čitljiv je |
| Dan 8 | Guardrail provera: da li ijedna brojka u memou nema citat (mora biti 0); popravka ako ima | Memo prolazi guardrail proveru iz SPEC sekcije 4 |
| Dan 9 | ✅ **Gotovo** (2026-09-07, Run 2) — end-to-end na svih 20 dokumenata uključujući **oba** namerno loša (`beta_supplies`, `sinai_agro`) | Oba lošа dokumenta ispravno eskalirala 100% svojih namernih grešaka, 0 lažno prihvaćeno |
| Dan 10 | ✅ **Gotovo** — osvežen `FINDINGS.md` sa Run 2 podacima, uporedbom naspram Run 1, i novim nalazom (field/document-type confusion) koji je odmah i popravljen | `evaluation/FINDINGS.md` (Run 1 + Run 2) |

**Gate na kraju nedelje 2:** POC je demonstrabilan SCB-u — end-to-end vožnja uživo na test
dokumentima, sa jasnim "evo šta radi pouzdano, evo šta zahteva dalji rad". ✅ **Prošao** — portal
(drag-and-drop, live log, batch obrada, review, PDF report) radi na svih 20 dokumenata, i imamo
dokumentovane, ponovljive brojeve umesto utiska.

---

## Nedelja 3 — OCR + RAG (nova stavka, dodata posle inicijalnog POC-a)

Originalni 2-nedeljni POC (Nedelja 1-2 gore) je završen i oba gate-a su prošla. Sledeće dve stavke
nisu bile u originalnom obimu, ali su dodate jer direktno testiraju dva rizika koja proposal sam
navodi (§16 risk tabela): "Arabic OCR accuracy on poor-quality documents" i "Credit policy corpus
incomplete or unstructured". Vidi SPEC.md sekcije 3.1.1 i 9 za pun kontekst i obrazloženje.

| Dan | Fokus | Deliverable | Status |
|---|---|---|---|
| Dan 11 | OCR grana za skenirane/arapske dokumente — sintetički skenirani arapski test set modelovan po realnom EGX dokumentu, sa **autentičnim istočno-arapskim ciframa** (`sample_docs/generate_arabic_scanned_docs.py`) + OCR fallback u Document Ingestor-u (`pytesseract`, lang `ara+eng`, rasterizacija preko PyMuPDF) | ✅ **Implementirano i verifikovano end-to-end** (2026-09-08) — pun test suite (16 passed, 2 xfailed — namerno, dokumentovan nalaz). **Ključni nalaz:** Tesseract-ov `ara` model ne čita pouzdano istočno-arapske (Indic) cifre koje realni egipatski dokumenti stvarno koriste u finansijskim tabelama (izolovano od fonta/layout-a — isti test sa zapadnim ciframa prolazi 100%). **PaddleOCR provereno preko Docker-a (starija `paddleocr==2.7.3`/`paddlepaddle==2.6.2` kombinacija — novija 3.x kombinacija ima svoj bag, dokumentovano) — potvrđuje isti obrazac: zapadne cifre čita, istočno-arapske ne.** Dva nezavisna OCR engine-a, ista mana — rizik je stvaran, ne specifičan za jedan alat. **Najbolji nalaz dana:** vision-LLM (ista porodica modela već korišćena za Financial Wizard) čita identičnu sliku sa 100% tačnošću, bez OCR-a uopšte — najjača kandidat-preporuka za produkciju (self-hosted vizuelni model, npr. Qwen2-VL preko vLLM, u skladu sa proposal §11). Pun nalaz i preporuke: `evaluation/FINDINGS.md` "OCR / Arabic scanned documents" |
| Dan 11b | Vision-LLM OCR engine ugrađen u Document Ingestor kao ravnopravna alternativa Tesseract-u, birana preko `POC_OCR_ENGINE=vision` (`OLLAMA_VISION_MODEL`, npr. `llama3.2-vision` preko mrežnog Ollama servera) | ✅ **Implementirano** (2026-09-08) — `document_ingestor.py` rasterizuje stranicu i šalje je modelu preko Ollama `/api/chat` (isti obrazac kao `POC_LLM_PROVIDER` u `llm_client.py`). Mockovani testovi (2 nova, i uspeh i graceful fallback bez servera) prolaze — 16 passed, 2 xfailed. **Živa verifikacija sa pravim `llama3.2-vision` modelom čeka korisnika** — ovaj dev environment ne može da dosegne mrežni Ollama server (`mcs02.cmu`) sa kog se model povlači, pa krajnja tačnost nije potvrđena van mock-a |
| Dan 12 | RAG minimalni demo — chunking + embedding + retrieval nad malim sintetičkim policy korpusom (EN + AR), sa citatom uz svaki vraćeni pasus (SPEC.md sekcija 9) | ⏳ **Planirano, sledeće** |
| Dan 13 | Vision-LLM OCR — živa verifikacija i izbor modela na lokalnom Ollama-u (M4/24 GB), pošto `mcs02.cmu` više nije dostupan i `llama3.2-vision` (`mllama`) uopšte ne radi na aktuelnom Ollama buildu | ✅ **Verifikovano i podešeno** (2026-09-09) — benchmark 7 vision modela na skeniranom arapskom FS (`sample_docs/misr_pharma/..._fy2024_arabic_scan.pdf`), ground truth iz `generate_sample_docs.py`. **Nalaz:** `qwen2.5vl:7b`, cela strana kao jedna slika @ 2560 px + `num_ctx` 12288 → ~18/20 tačnih brojeva po strani za 60–90 s/str. `qwen2.5vl:3b` i `gemma3:12b` upadaju u petlju ponavljanja; `minicpm-v:8b` i `glm-ocr` haluciniraju; `qwen3-vl:8b` vraća prazan izlaz (thinking pojede budžet). Tiling strane smanjuje tačnost. **Druga greška, nezavisna:** oba arapska skena su padala na JSON ekstrakciji (`Expecting ',' delimiter`) — ne na OCR-u — jer `qwen2.5:3b` + Ollama default `num_ctx` 4096 iseku dug šumovit OCR ulaz i vrate odsečen JSON. Fix: `OLLAMA_MODEL=qwen2.5:7b` + `num_ctx` 16384 na text-extract pozivu. Izmene: `config.py`, `document_ingestor.py`, `llm_client.py`, `.env`. Pun benchmark: `evaluation/FINDINGS.md` "Vision-LLM benchmark (lokalni Ollama)" |

| Dan 14 | MLX runtime (bez Ollame) + **fused VL OCR+extract** — `mlx_lm.server`/`mlx_vlm.server` sa autoswap-om (`src/mlx_servers.py`), i `POC_OCR_ENGINE=mlx_vision_extract`: VL po skeniranoj strani i transkribuje i vadi polja u 2 fokusirana poziva, bez swap-a na 14B, Financial Wizard preskače LLM poziv (`src/agents/vision_extractor.py`, `_fields_from_prefetched`) | 🟡 **Izgrađeno i testirano** (2026-09-10) — 85 testova prolazi (+10 novih). Arhitektura radi end-to-end (394 s / 3 strane, sva polja, bez swap-a). **Tačnost brojeva sa MLX 4-bit VL-7B i dalje slaba** — u Naskh fontu je istočno-arapska nula `٠` tačka gotovo identična `٬` separatoru i skeniranom šumu (`٤٥٬٩٠٠٬٠٠٠` ≈ `٤٥٬٩··٬···`). Sledeći korak: MLX VL-7B **8-bit** ili re-baseline Ollama `qwen2.5vl:7b` na regenerisanom (realistično renderovanom) arapskom setu. Detalji: `evaluation/FINDINGS.md` "Fused VL pass". Uz to: `MLX_HTTP_LOCK` dobio 90 s acquire-timeout (zaglavljeni holder više ne blokira pipeline), test hygiene u `tests/conftest.py` |

**Zašto sada:** proposal sam identifikuje ova dva kao top rizike (§16), a POC-ov princip je da se
rizične pretpostavke dokazuju rano i izolovano (SPEC.md sekcija 1) — isti pristup kao originalni
Dan 1-10, samo primenjen na dve nove, eksplicitno odobrene stavke obima.

---

## Backlog — Robusnost obrade (radi se kad se rasteretiti posao)

Ne menja arhitekturu. Trenutni „Process all pending" radi sinhrono, sekvencijalno, u Streamlit
UI threadu — ako padne na 3. strani 4. dokumenta gubi se sav progres, a UI je zamrznut dok traje.
Za POC na jednoj mašini sekvencijalna obrada ostaje ispravan izbor (Ollama svejedno drži jedan
model i serijalizuje pozive; paralelni vision pozivi ruše server — potvrđeno 2026-09-09). Dodaje
se samo otpornost, ne konkurentnost:

| Stavka | Deliverable | Procena | Status |
|---|---|---|---|
| Red u SQLite | Tabela `jobs(doc_id, status, attempts, last_error, updated_at)` sa `pending/running/done/failed`; obrada u jednom background thread-u, Streamlit samo čita i osvežava | ~0.5 dana | ⏳ backlog |
| Retry sa backoff | Na `ConnectionError` / HTTP 5xx od Ollama-e (server povremeno restartuje, posebno posle vision poziva) — 2–3 pokušaja sa pauzom, pa `failed` sa razlogom | ~0.25 dana | ⏳ backlog |
| Per-page checkpoint | OCR tekst se snima po strani čim stigne; restart obrade kreće od prve neurađene strane, ne od nule (bitno jer je vision ~60–90 s/str) | ~0.25 dana | ⏳ backlog |
| Health-check | Provera `/api/version` pre svakog posla; ako je Ollama pao, jasna poruka (ili auto `ollama serve`) umesto polovične obrade | ~0.25 dana | ⏳ backlog |

**Van obima za sada** (tek ako POC pređe u pravi sistem): RQ/Celery worker-i, druga Ollama
instanca ili API za text-extract radi paralelizacije na nivou dokumenata. Na jednom Mac Mini +
jedan Ollama, sekvencijalno je i najbrže i najsigurnije.

---

## Nedelja 4 (opciono, bafer) — Polish i realni dokumenti

Aktivira se samo ako: (a) nedelja 1-2 pokažu ozbiljne probleme koje vredi ispraviti pre
prezentacije, ili (b) SCB u međuvremenu dostavi realne dokumente pa ih vredi odmah testirati.

- Zamena/dodavanje realnih (anonimizovanih) SCB dokumenata u test skup
- Ponovno merenje nalaza na realnim podacima
- Priprema kratke prezentacije/demo skripte za SCB stakeholder-e

---

## Šta POC NE pokušava da reši (podsetnik iz SPEC-a)

Ne gradimo Risk Agent, fine-tuning, bilingual memo **izlaz** (AR), punu platformu, ni produkcionu
OCR/RAG infrastrukturu. Minimalni OCR i RAG demo (Nedelja 3 gore, SPEC.md sekcije 3.1.1 i 9) su
namerni izuzeci od ovog pravila — dodati u obim jer direktno testiraju proposal-ove sopstvene top
rizike (§16), ne scope creep. Ako se tokom rada pojavi iskušenje da se doda bilo šta drugo van
onoga što je već u SPEC.md — ne radi se dok se prvo ne doda tamo sa obrazloženjem. Ista disciplina
kao u internoj pregovaračkoj tabeli (nedefinisan plafon = beskonačan posao).

---

## Izlazna odluka posle POC-a

`FINDINGS.md` (dan 10) treba da odgovori na tri pitanja koja direktno hrane odluku o punom
angažmanu i pregovorima sa SCB:

1. **Da li je extraction+citation pristup fundamentalno ispravan?** (da/ne/uz uslove)
2. **Koji KPI brojevi iz proposal sekcije 9.1 su realni**, na osnovu onoga što je izmereno — i pod
   kojim uslovima (kvalitet dokumenata, obim polja definisan u SPEC 6 vs. širi obim)
3. **Šta nedostaje da POC postane produkcioni scope** (najverovatnije: realni SCB dokumenti, širi
   skup polja, produkciona OCR infrastruktura — PaddleOCR umesto POC-ovog pytesseract, pravi
   Policy Monitor/RAG na stvarnom SCB policy korpusu umesto POC-ovog sintetičkog, Conflict
   Resolver, Risk Agent)
