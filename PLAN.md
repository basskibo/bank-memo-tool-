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
| Dan 5 | Merenje: pokreni ceo pipeline (Ingestor→Wizard→Validator) na svih 5-10 test dokumenata, ručno oceni rezultate naspram sekcije 5 SPEC-a (dijagnostički kriterijumi) | Prva verzija nalaza: koliko polja tačno, koliko citata validno |

**Gate na kraju nedelje 1:** da li Financial Wizard uopšte pogađa realan broj polja (npr. bar
6-7/10)? Ako ne — nedelja 2 počinje popravkom prompta/pristupa pre nego što se gradi UI i
Narrative Synthesizer na lošim podacima.

---

## Nedelja 2 — Review, memo, end-to-end demo

**Cilj nedelje:** čovek može da pregleda izuzetke i dobije čitljiv nacrt memoranduma.

| Dan | Fokus | Deliverable |
|---|---|---|
| Dan 6 | Prost review UI (Streamlit): prikaz `needs_review` polja sa snippet/stranicom, dugme potvrdi/ispravi | Reviewer može ručno da reši sve otvorene izuzetke |
| Dan 7 | Narrative Synthesizer — generisanje `DraftMemo` iz potvrđenih polja, po sekcijama, sa citatom uz svaku brojku | Nacrt memoranduma se generiše, čitljiv je |
| Dan 8 | Guardrail provera: da li ijedna brojka u memou nema citat (mora biti 0); popravka ako ima | Memo prolazi guardrail proveru iz SPEC sekcije 4 |
| Dan 9 | End-to-end vožnja na svim test dokumentima, uključujući i namerno "loš" dokument (nizak kvalitet/nedostajuća polja) da se vidi da li sistem to ispravno eskalira umesto da nagađa | Kompletan run-log za sve test slučajeve |
| Dan 10 | Izveštaj o nalazima: šta radi, šta ne, koji su realni brojevi (ne KPI-obećanja, nego "ovo smo izmerili") | `FINDINGS.md` — ulaz za odluku o punom angažmanu |

**Gate na kraju nedelje 2:** POC je demonstrabilan SCB-u — end-to-end vožnja uživo na test
dokumentima, sa jasnim "evo šta radi pouzdano, evo šta zahteva dalji rad".

---

## Nedelja 3 (opciono, bafer) — Polish i realni dokumenti

Aktivira se samo ako: (a) nedelja 1-2 pokažu ozbiljne probleme koje vredi ispraviti pre
prezentacije, ili (b) SCB u međuvremenu dostavi realne dokumente pa ih vredi odmah testirati.

- Zamena/dodavanje realnih (anonimizovanih) SCB dokumenata u test skup
- Ponovno merenje nalaza na realnim podacima
- Priprema kratke prezentacije/demo skripte za SCB stakeholder-e

---

## Šta POC NE pokušava da reši (podsetnik iz SPEC-a)

Ne gradimo Risk Agent, RAG, bilingual, fine-tuning, punu platformu. Ako se tokom rada pojavi
iskušenje da se nešto od ovoga "brzo doda" — ne radi se dok se prvo ne doda u SPEC.md sa
obrazloženjem. Ovo je namerna disciplina protiv scope creep-a, ista logika kao u internoj
pregovaračkoj tabeli (nedefinisan plafon = beskonačan posao).

---

## Izlazna odluka posle POC-a

`FINDINGS.md` (dan 10) treba da odgovori na tri pitanja koja direktno hrane odluku o punom
angažmanu i pregovorima sa SCB:

1. **Da li je extraction+citation pristup fundamentalno ispravan?** (da/ne/uz uslove)
2. **Koji KPI brojevi iz proposal sekcije 9.1 su realni**, na osnovu onoga što je izmereno — i pod
   kojim uslovima (kvalitet dokumenata, obim polja definisan u SPEC 6 vs. širi obim)
3. **Šta nedostaje da POC postane produkcioni scope** (najverovatnije: realni SCB dokumenti, širi
   skup polja, OCR grana za skenove, Conflict Resolver, RAG, Risk Agent)
