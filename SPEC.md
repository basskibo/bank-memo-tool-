# SPEC — Credit Memo Agent POC (SCB)

> **Status:** Living spec. Ovo je izvor istine za POC — svaka odluka o tome šta se gradi i kako
> treba prvo da bude ovde, pa tek onda u kodu. Ako nešto nije u ovom dokumentu, nije u obimu POC-a.
>
> **Odnos prema proposal-u:** Ovaj spec je izveden iz `SCB Credit Memo Tool - Proposal by Xenon7.pdf`
> (pun 10-nedeljni/9-ljudi angažman). POC namerno seče obim da dokaže rizičnu pretpostavku
> (kvalitet ekstrakcije i citiranja na realnim dokumentima) pre nego što se pravi pun sistem.
> Svako odstupanje od proposal-a je eksplicitno označeno i obrazloženo — ništa se ne skida "ćutke".

---

## 1. Cilj POC-a

Dokazati, na malom skupu dokumenata, da agent može:

1. da pročita finansijski/kreditni dokument (PDF),
2. da izvuče ključne finansijske vrednosti,
3. da svaku izvučenu vrednost veže za tačan izvor (dokument, stranica, pasus/snippet),
4. da od tih vrednosti sastavi nacrt kreditnog memoranduma,
5. da čovek može da pregleda, ispravi ili odobri taj nacrt pre finalizacije.

**Ne dokazuje se u POC-u:** tačnost na skali, performanse pod opterećenjem, potpuna platforma,
Risk Agent, ni bilo šta iz punog proposal-a van ove tanke vertikale. Cilj je odgovoriti na jedno
pitanje: *da li osnovni pristup (extraction → citation → narrative) radi na dokumentima sličnim
onima koje SCB stvarno ima* — pre nego što se ugovorno obeća KPI iz proposal-a (sekcija 9.1).

---

## 2. Obim POC-a naspram punog proposal-a

| Proposal (puna verzija) | POC | Zašto |
|---|---|---|
| Credit Memo Agent + Risk Agent | **Samo Credit Memo Agent** | Risk Agent konzumira gotovu, odobrenu evidence bazu iz Credit Memo Agenta (proposal 3.3) — nema smisla graditi drugi agent pre nego što prvi radi |
| 6 capability (Document Ingestor, Financial Wizard, Citation Validator, Conflict Resolver, Narrative Synthesizer, Industry Scanner) | **4 capability**: Document Ingestor, Financial Wizard, Citation Validator, Narrative Synthesizer | Conflict Resolver treba više dokumenata po slučaju da bi imao šta da poredi; Industry Scanner zavisi od eksternih data feed-ova koje SCB nije obezbedio (proposal 14 — out of scope i u punoj verziji) |
| Bilingual EN/AR memo | **Samo engleski** | Arapski dodaje OCR/LLM kompleksnost i bilingual-consistency proveru; testira se odvojeno kad osnovni pipeline radi |
| Pun platform layer (orkestracija, guardrails, human-in-loop, audit, observability, RAG, responsible AI — proposal sekcija 4) | **Minimalni podskup**: osnovna orkestracija (LangGraph), osnovni guardrails, prost review UI, prost log kao audit trag | Prometheus/Grafana/Instana/Keycloak/OpenShift su operativna infrastruktura — vredna tek kad ima šta da se posmatra u produkciji |
| RAG nad credit policy + istorijskim dokumentima | **Izostavljeno** (ili minimalni demo ako SCB da uzorak policy dokumenta) | RAG je ulaz za Risk Agent (Policy Monitor), koji nije u POC obimu |
| Fine-tuning, AIOps pipeline, performance/penetration testing | **Izostavljeno** | Prerano — proposal sekcija 6 i 7 eksplicitno kažu da ovo dolazi posle osnovnog pipeline-a |
| Angular frontend | **Prost review UI** (npr. Streamlit ili slična brza alatka) | Frontend izbor iz proposal-a (11) je produkcioni commitment prema SCB inženjeringu; POC ne menja tu odluku, samo je ne implementira dok se pristup ne dokaže |
| Tim: 9 ljudi, 10 nedelja | **2–3 osobe, 2–3 nedelje** | Vidi PLAN.md |

**Ništa iz ove tabele nije trajna odluka o produkciji.** POC ne obavezuje ni na tech stack ni na
KPI brojeve — proizvodi dokaz i podatke na osnovu kojih se puna ponuda dorađuje.

---

## 3. Agent u obimu: Credit Memo Agent (POC verzija)

Vlasnik: sastavlja nacrt kreditnog memoranduma iz jednog ili više ulaznih dokumenata jednog
klijenta. Odlučuje šta je izvučeno pouzdano, a šta ide na ljudski pregled kao izuzetak.

### 3.1 Capabilities i data contracts

Svaka capability ima jasan ulaz/izlaz (contract) — to je namerno, isto kao u proposal-u (3.4:
"agents communicate through typed contracts"), da bi kasnije Risk Agent mogao da se doda bez
menjanja postojećeg koda.

#### 3.1.1 Document Ingestor

| | |
|---|---|
| **Ulaz** | Sirov fajl (PDF, eventualno slika/scan) |
| **Izlaz** | `IngestedDocument`: lista stranica, za svaku stranicu ekstraktovan tekst (+ layout/blokovi ako je dostupno), tip dokumenta (klasifikacija), quality flag |
| **Ponašanje** | Ako je dokument nečitljiv/nizak kvalitet → odbija se sa razlogom (ne pokušava OCR na neupotrebljivom ulazu — isto pravilo kao proposal 8.2) |
| **POC pojednostavljenje** | Bez punog OCR-a (PaddleOCR) ako test dokumenti nisu skenirani — direktna ekstrakcija teksta iz PDF-a (pdfplumber/PyMuPDF). OCR grana se dodaje kad/ako testiramo skenirane dokumente. |

```python
class IngestedPage(BaseModel):
    page_number: int
    text: str
    source_file: str

class IngestedDocument(BaseModel):
    document_id: str
    source_file: str
    document_type: str          # npr. "financial_statement", "loan_application"
    pages: list[IngestedPage]
    quality_ok: bool
    quality_notes: str | None
```

#### 3.1.2 Financial Wizard

| | |
|---|---|
| **Ulaz** | `IngestedDocument` (jedan ili više) |
| **Izlaz** | Lista `ExtractedField` — svaka izvučena vrednost sa referencom na tačnu stranicu i snippet teksta iz kog je izvučena |
| **Obim polja za POC** | Mali, fiksan skup (vidi sekciju 6 — Test skup polja), ne "svi mogući finansijski pojmovi" |
| **Ponašanje** | Ne piše vrednost bez izvora. Nejasna/kontradiktorna vrednost → status `needs_review`, ne nagađa. |

```python
class ExtractedField(BaseModel):
    field_name: str              # npr. "total_assets", "annual_revenue"
    value: str
    unit: str | None
    source_document_id: str
    source_page: int
    source_snippet: str          # tačan citat iz teksta koji potkrepljuje vrednost
    confidence: float            # 0-1
    status: Literal["confirmed", "needs_review"]
    validation_note: str | None  # popunjava Citation Validator kad menja status (razlog)
```

#### 3.1.3 Citation Validator

| | |
|---|---|
| **Ulaz** | Lista `ExtractedField` |
| **Izlaz** | Ista lista, sa dodatnom proverom: da li `source_snippet` zaista postoji na `source_page` u originalnom dokumentu |
| **Ponašanje** | Ako se snippet ne može pronaći/potvrditi u izvoru → polje ide na `needs_review`, nikad se ne prosleđuje dalje kao potvrđeno. Ovo je direktna implementacija proposal principa "nothing is asserted without evidence" (3.1). |

#### 3.1.4 Narrative Synthesizer

| | |
|---|---|
| **Ulaz** | Lista potvrđenih `ExtractedField` (status `confirmed`, posle ljudskog pregleda izuzetaka) |
| **Izlaz** | `DraftMemo`: tekst memoranduma na engleskom, po sekcijama, sa citatom pored svake tvrdnje koja koristi izvučenu vrednost |
| **Ponašanje** | Ne sme uneti nijednu brojku koja nije u ulaznoj listi potvrđenih polja. Ako podatak nedostaje za standardnu sekciju memoranduma, eksplicitno piše "podatak nije dostupan", ne izmišlja. |

```python
class MemoSection(BaseModel):
    title: str
    text: str
    cited_fields: list[str]      # field_name referenced in this section

class DraftMemo(BaseModel):
    client_name: str
    sections: list[MemoSection]
    generated_at: datetime
    open_exceptions: list[str]   # polja koja čekaju ljudski review
```

### 3.2 Redosled izvršavanja (POC orkestracija)

```
raw file(s)
    │
    ▼
Document Ingestor  ──► IngestedDocument[]
    │
    ▼
Financial Wizard    ──► ExtractedField[]  (confirmed | needs_review)
    │
    ▼
Citation Validator  ──► ExtractedField[]  (potvrđeni citati; needs_review ostaje otvoren)
    │
    ▼
[HUMAN REVIEW]  ── čovek potvrđuje/ispravlja needs_review stavke ──►  ExtractedField[] (sve confirmed)
    │
    ▼
Narrative Synthesizer ──► DraftMemo
    │
    ▼
[HUMAN REVIEW]  ── čovek odobrava finalni memo ──► gotovo
```

Implementirano kao LangGraph graf sa čvorovima 1:1 prema capability-jima iznad, plus dva
"interrupt" čvora za ljudski review (proposal 4.4 princip: "no memo is issued without an
authorized reviewer approving it" — u POC-u pojednostavljeno na CLI/UI potvrdu, bez punog
role-based approval flow-a).

---

## 4. Guardrails (POC podskup)

Iz punog proposal seta (4.3) implementira se samo ono što se aktivno testira u ovoj vertikali:

| Guardrail | POC implementacija |
|---|---|
| Input validacija | Tip fajla (PDF) i veličina; odbijanje ako nije čitljiv tekst/OCR neupotrebljiv |
| Mandatory citation | `Narrative Synthesizer` odbija da generiše rečenicu sa brojkom bez `source_page`/`source_snippet` |
| Confidence threshold | Polja ispod praga (podesivo, početno 0.7) idu na `needs_review`, ne u memo direktno |
| Scope boundary | Agent radi samo nad poljima iz fiksnog skupa (sekcija 6) — ne "izmišlja" nova polja van liste |

Van obima POC-a: prompt injection screening, PII handling rules, token/cost ceilings, loop
protection — relevantni za produkciju, ne za dokazivanje pristupa.

---

## 5. Acceptance kriterijumi za POC

**Važno:** ovo NISU brojevi iz proposal sekcije 9.1 (95%/98%/100%...). Na 5-10 test dokumenata ti
brojevi nisu statistički smisleni — jedna greška na 10 polja je već "10% grešaka". POC koristi
**dijagnostičke, ne ugovorne** kriterijume:

| Pitanje | Kako se meri |
|---|---|
| Da li se tekst uopšte čisto izvlači iz test dokumenata? | Ručna provera ekstraktovanog teksta naspram originala, po dokumentu |
| Da li Financial Wizard nalazi tačan skup polja definisan u sekciji 6? | Broj polja tačno izvučenih / ukupan broj definisanih polja, po dokumentu — izveštava se kao razlomak (npr. "9/10"), ne kao %-KPI |
| Da li je svaki citat proverljiv (snippet zaista postoji na navedenoj stranici)? | 100% na nivou POC-a — ako ovo ne prolazi, citation pristup ne radi i to je najvažniji signal iz čitavog POC-a |
| Da li generisani memo sadrži ijednu brojku bez citata? | 0 dozvoljeno — direktna provera guardrail-a iz sekcije 4 |
| Da li ljudski reviewer smatra nacrt memoranduma upotrebljivim kao polazna tačka? | Kvalitativna ocena (da/ne/uz izmene), ne broj |

Rezultat POC-a je **izveštaj sa ovim nalazima**, koji onda informiše da li se KPI brojevi iz
proposal-a mogu realno obećati SCB-u, i pod kojim uslovima (kvalitet dokumenata, obim polja, itd.)
— ovo direktno hrani "Relaksacija" diskusiju iz internog pregovaračkog dokumenta.

---

## 6. Test skup polja (Financial Wizard — POC obim)

Namerno mali i standardan skup, prisutan u većini finansijskih izveštaja bez obzira na
jurisdikciju:

1. `company_name`
2. `reporting_period` (npr. "FY2024")
3. `total_assets`
4. `total_liabilities`
5. `total_equity`
6. `annual_revenue`
7. `net_income`
8. `existing_bank_facilities` (postojeći krediti/limiti, ako su navedeni)
9. `requested_facility_amount` (iz loan application dokumenta)
10. `collateral_offered` (ako je navedeno)

Ovih 10 polja su ono naspram čega se meri sekcija 5. Lista se svesno ne širi dok POC ne pokaže da
osnovni pristup radi.

---

## 7. Test dokumenti

Pošto SCB nije dostavio realne primere, a bankarski domen nije poznat timu, POC koristi
**sintetička dokumenta** za fiktivnu kompaniju — vidi `sample_docs/README.md` za listu, sadržaj i
eksplicitnu napomenu da su izmišljena. Struktura dokumenata (koja polja postoje, kako izgleda
bilans stanja, šta je "loan application") je modelovana po standardnoj bankarskoj praksi, ali
**čim SCB da bar 2-3 realna (anonimizovana) primera, sintetička dokumenta se zamenjuju** — to je
najvažniji sledeći korak posle inicijalnog POC-a, jer sintetička dokumenta ne mogu testirati
stvarnu varijabilnost (format SCB-a, arapski OCR, loš skener kvalitet, itd.).

---

## 8. Tech stack za POC

| Sloj | Puna produkcija (proposal 11) | POC |
|---|---|---|
| Orkestracija | LangGraph | **LangGraph** (isto — ovo se ionako testira) |
| Document parsing | PaddleOCR + pdfplumber/PyMuPDF | **pdfplumber/PyMuPDF** (OCR grana dodaje se samo ako testiramo skenove) |
| LLM runtime | vLLM (prod) / Ollama (dev) | **Konfigurabilno preko `POC_LLM_PROVIDER`** — Ollama (mrežni server, npr. `qwen2.5:3b`) ili Anthropic API, isti `complete_json()` interfejs za oba (`src/llm_client.py`) |
| Baza/storage | Oracle, Nutanix Object Store | **Lokalni fajlovi / SQLite** za POC |
| Review UI | Angular | **Streamlit ili ekvivalent** (brzo, jednokratno) |
| Auth, monitoring, CI/CD | Keycloak, Prometheus/Grafana/Instana, OpenShift | **Izostavljeno** |

Ovo su POC-only izbori radi brzine — ne menjaju agreed tech stack iz proposal sekcije 11 za punu
produkciju.

---

## 9. Eksplicitno van obima POC-a

Pored svega već pomenutog: Risk Agent, RAG, fine-tuning, bilingual (AR), Conflict Resolver,
Industry Scanner, AIOps pipeline, performance/security testing, bilo kakva integracija sa SCB
sistemima. Sve ovo ostaje u punom proposal-u i gradi se tek posle POC faze, po planu iz PLAN.md i
punog proposal-a (sekcija 12).

---

## 10. Kako se ovaj dokument koristi

- Svaka nova capability, polje, guardrail ili acceptance kriterijum se **prvo dodaje ovde**, pa
  tek onda u kod.
- Ako neki zahtev iz razgovora nije pokriven ovim dokumentom, tretira se kao promena obima i
  eksplicitno se dodaje/odbija ovde — ne implementira se "u prolazu".
- Ovaj spec se ažurira kad se POC nalazi promene planove (npr. ako se pokaže da citation
  validacija ne radi dobro, to menja i acceptance kriterijume i sledeće korake).
