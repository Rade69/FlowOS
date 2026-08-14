---
flowos_report_version: 1
report_id: 82374520-d0d3-4204-bdf2-9eee0d3ebdb7
agent: claude
model: claude-sonnet-5
session_id: unknown
report_type: review
work_status: completed
tasks:
  - FLOW-1104
commits: []
created_at: 2026-08-14T08:37:57+02:00
---

# FLOW-1104 — PlanMarkdownParser reporting fix, independent review

## Scope

READ ONLY. Nije mijenjan kod, nisu mijenjani testovi, nije mijenjan plan
Markdown, nije pravljen commit, nije pushovano. FLOW-1105/1106 nisu dirnuti.

## 1. Scope / diff

```
git status --short
 M src/flowos/service/services/plan_import.py
 M tests/unit/test_plan_import.py
(plus nepovezani untracked docs/agent_reports fajlovi)
```
```
git diff --stat
 src/flowos/service/services/plan_import.py |   6 +-
 tests/unit/test_plan_import.py             | 116 +++++++++++++++++++++
```

Diff na produkcijskom fajlu je tačno DVA reda promijenjena (jedan za Bug A,
jedan za Bug B), plus komentar. Nema izmjene van očekivanog scope-a.

## 2-3. Bug A — root cause i fix

**Stari kod**: `heading.startswith("##")`. Pošto `"#### FLOW-1104 — ...".
startswith("##")` vraća `True` (string doslovno počinje sa dva `#` znaka, bez
obzira što ih ima još dva iza) — svaki `####` (level-4 FLOW) heading je
LAŽNO ulazio u isti test kao pravi `##` (level-2) heading, i pošto ne
odgovara `PHASE_HEADING` regex-u (koji zahtijeva `^##\s+Faza`), bio je
pogrešno dodavan u `unclear_sections`.

**Novi kod**: `section["level"] == 2`. Potvrđeno čitanjem `_split_into_
sections()` (`plan_import.py:145-199`) — `level` je STRUKTURALNO polje:
`current_level = 2` samo kad linija počinje sa `"## "` i NE počinje sa
`"### "`; `current_level = 4` samo kad počinje sa `"#### "` i NE počinje sa
`"##### "`. Ovo je prava strukturna klasifikacija, ne string-prefix trik.

**Nezavisno potvrđeno probe-om** (markdown sa nepoznatom H2 sekcijom +
validnim `FLOW-001`/`FLOW-002A` H4 stavkama):
```
items u fazi 1: ['FLOW-001', 'FLOW-002A']
unclear_sections: ['## Nepoznata sekcija bez Faza prefiksa']
```
Tačno jedan unclear entry (nepoznat H2), nijedan FLOW H4 nije lažno prijavljen.

**BUG A ROOT CAUSE = CONFIRMED. BUG A FIX = ACCEPT.**

## 4-5. Bug B — root cause i fix

**Stari kod**: `re.sub(r"^\d+\.\s*`?\s*", "", stripped).strip("`; ")`. Regex
ima OPCIONI `` `? `` koji može progutati OTVARAJUĆI backtick odmah nakon `"1. "`;
`.strip("`; ")` na kraju briše bilo koji od znakova `` ` ``, `;`, razmak sa OBA
kraja rezultata — asimetrična, ranjiva korupcija (otvarajući backtick
konzumiran regex-om, zatvarajući backtick ranjiv na strip ako se nalazi na
samom kraju stringa).

**Novi kod**: `re.sub(r"^\d+\.\s*", "", stripped).strip()`. Regex uklanja
ISKLJUČIVO broj + tačku + whitespace. `.strip()` bez argumenata uklanja SAMO
plain whitespace, ne backtick/tačka-zarez.

**Nezavisno testirano svih 6 traženih primjera, sa TAČNIM string poređenjem
(ne substring)**:
```
REQ-01: '`IMPLEMENTATION_COMPLETED` prikazati kao zavrsenu implementaciju.'
REQ-02: '`TEST_RESULT` prikazati rezultat.'
REQ-03: 'Akcija `Prihvati rezultat` mapira se na TASK_DECISION.'
REQ-04: '"Quoted value" ostaje quoted.'
REQ-05: '[Bracketed] ostaje bracketed.'
REQ-06: 'Trailing punctuation ostaje nepromijenjena!'
Poklapanje tacno? True
```
Svi backtick-ovi (otvarajući i zatvarajući), navodnici, uglaste zagrade i
trailing interpunkcija su tačno sačuvani, karakter po karakter.

**BUG B ROOT CAUSE = CONFIRMED. INLINE CODE PRESERVATION = ACCEPT. PUNCTUATION
PRESERVED = YES.**

## 6. Parser contract preservation

Diff sadrži TAČNO dva izmijenjena reda (plus komentar) u `plan_import.py`.
`PHASE_HEADING`, `ITEM_HEADING`, `RISK_PATTERN`, `DEPENDS_PATTERN`,
`FLOW_REF_PATTERN` regex konstante nisu u diff-u — nepromijenjene. `_extract_
risk`, `_extract_dependencies`, DOKAZ/OUT_OF_SCOPE ekstrakcija, DRAFT import
tok (`PlanImportService.import_plan`) — sve nepromijenjeno. Nema novog
AI/LLM importa, nema fuzzy heading logike, nema API/DB šema izmjene.

**PARSER CONTRACT PRESERVED = YES.**

## 7. Test quality

**Bug A testovi** (`TestFlow1104ParserReporting`, 3 testa) — koriste TAČNU
equality provjeru: `assert result.unclear_sections == []` i `assert result.
unclear_sections == ["## Nepoznata sekcija"]` — ne substring, pravi exact-match
na cijelu listu. Solidno.

**Bug B testovi** (`TestFlow1104InlineCode`, 2 testa) — **slabiji**:
- `test_inline_code_backticks_preserved`: `assert any("`IMPLEMENTATION_
  COMPLETED`" in d for d in descriptions)` — ovo je SAMO substring provjera
  (`in`), ne provjerava CIJEL opis kriterijuma karakter-po-karakter. Ne bi
  uhvatila regresiju koja bi npr. odsjekla trailing sadržaj ili uvela dodatni
  whitespace bilo gdje van tog konkretnog tokena.
- `test_inline_code_first_criterion_exact`: `.startswith("`IMPLEMENTATION_
  COMPLETED`")` — bolje, provjerava tačno ranjivo mjesto (otvarajući
  backtick), ali i dalje ne provjerava PUN string do kraja (trailing
  interpunkcija, navodnici, zagrade — moji dodatni primjeri iz Section 4-5 —
  nisu pokriveni nijednim isporučenim testom).

Nijedan isporučeni test ne provjerava PUNU, tačnu vrijednost opisa
kriterijuma sa `==` uključujući i otvarajući i zatvarajući backtick i
trailing tekst. Ovo tačno odgovara upozorenju iz zahtjeva: "Ako testovi samo
tvrde loose substrings: prijavi slabost." Stvarno ponašanje JE ispravno
(dokazano mojim probe-om, Section 4-5), ali isporučeni testovi to ne
dokazuju sa istom strogošću.

**TEST QUALITY = FIXES REQUIRED** (Bug B dio; Bug A dio je solidan).

## 8-9. Dogfooding v1/v2 probe

Direktno parsirano (READ ONLY, `PlanMarkdownParser().parse()`):

```
docs/FlowOS-plan-faze-11-15-dogfooding.md:
  phases=5 items=20 criteria=141 dependencies=20 unclear=0

docs/FlowOS-plan-faze-11-15-dogfooding-v2.md:
  phases=5 items=22 criteria=157 dependencies=23 unclear=0
```

Oba se poklapaju TAČNO sa prijavljenim brojevima.

**Poređenje sa pre-FLOW-1104 ponašanjem** (rekonstruisan stari `unclear`-
collection kod, `heading.startswith("##")`, pokrenut na ISTOM trenutnom
sadržaju oba fajla):

```
v1: STARO unclear=20 → NOVO unclear=0   (items/phases/dependencies IDENTIČNI)
v2: STARO unclear=22 → NOVO unclear=0   (items/phases/dependencies IDENTIČNI)
```

`items`, `phases`, `dependencies`, `criteria` su IDENTIČNI prije i poslije
fixa za OBA fajla — SAMO `unclear` broj se mijenja. Ovo dokazuje da razlika
između v1 (20 stavki/141 kriterijum/20 zavisnosti) i v2 (22/157/23) postoji
ISKLJUČIVO zbog stvarnog sadržaja dva različita dokumenta — nije uzrokovana
FLOW-1104 izmjenom koda.

**DOGFOODING V1 = phases=5, items=20, criteria=141, dependencies=20,
unclear=0. DOGFOODING V2 = phases=5, items=22, criteria=157, dependencies=23,
unclear=0. V1/V2 DIVERGENCE = PRE-EXISTING.**

## 10. Direct parser vs service — **MATERIJALAN NALAZ**

`PlanImportService.import_plan()` (stvaran put koji GUI/API koristi) NE
poziva `PlanMarkdownParser.parse()` direktno — koristi zaseban statički metod
`_parse_with_phases()` (`plan_import.py:517-533`):
```python
@staticmethod
def _parse_with_phases(parser, markdown):
    lines = markdown.split("\n")
    title = parser._extract_title(lines)
    sections = parser._split_into_sections(lines)
    phases = parser._parse_phase_sections(sections)
    result = ImportResult(title=title, phases=phases)
    result.stats = {..., "unclear": len(result.unclear_sections)}
    return result
```
Ovaj metod **nikad ne izvršava petlju koja sakuplja `unclear_sections`** —
`result.unclear_sections` ostaje na default vrijednosti (`[]`, iz `field(
default_factory=list)`), i `stats["unclear"]` je UVIJEK `0`, bez obzira na
stvaran sadržaj markdown-a.

**Nezavisno potvrđeno probe-om** (isti markdown, dva puta parsiran — direktno
i preko stvarnog `PlanImportService.import_plan()` sa in-memory SQLite bazom):
```
DIREKTAN PlanMarkdownParser.parse():      unclear_sections: ['## Nepoznata sekcija']
SERVISNI PUT PlanImportService.import_plan(): unclear_sections: []
Slazu li se? False
```

**Ovo je pre-postojeći strukturni gap** — `_parse_with_phases()` nije diran
ovim diff-om (nije u diff hunkovima), pa FLOW-1104 nije ovo UZROKOVAO. Ali je
DIREKTNO relevantno za prihvatanje ovog reviewa, jer:

1. Zahtjev eksplicitno traži poređenje `PlanMarkdownParser.parse()` i
   `PlanImportService` puta na "unclear reporting" — divergencija postoji, i
   nije samo formatiranje/redoslijed, nego POTPUNO odsustvo funkcionalnosti
   na servisnoj strani.
2. **Praktična posljedica**: korisnik koji uveze bilo koji od dva dogfooding
   plana kroz stvaran GUI "Uvezi plan" tok ili `/projects/{id}/import-plan`
   API rutu (koji koriste `PlanImportService`, ne `PlanMarkdownParser.parse()`
   direktno) NIKAD neće vidjeti `unclear_sections` upozorenje — ni prije ni
   poslije FLOW-1104 fix-a. Cijela svrha Bug A popravke (ispravno prijavljivanje
   umjesto lažnih 20/22 unclear stavki) je NEVIDLJIVA na stvarnom import putu
   koji korisnik zaista koristi — vidljiva je samo kad se `PlanMarkdownParser.
   parse()` pozove direktno (npr. u testovima).

Criteria/dependencies parsing (Bug B) NIJE pogođen ovom divergencijom — i
`parse()` i `_parse_with_phases()` pozivaju ISTI dijeljeni `_parse_phase_
sections()`/`_parse_item()`/`_extract_criteria()` lanac, pa Bug B fix VAŽI
identično na oba puta (potvrđeno istim probe-om — kriterijumi se poklapaju).

**DIRECT/SERVICE CONSISTENCY = FIXES REQUIRED.**

## 11. Regression

```
python -m pytest tests/unit/test_plan_import.py -v --tb=short
22 passed in 0.51s
```
```
python -m pytest tests/gui/test_plan_import_flow.py -v --tb=short
1 passed
```
```
python scripts/verify.py
Prošlo: 7/7
[PASS] VERIFIKACIJA PROŠLA
```

## 12. Findings

Nema BLOCKER nalaza.

**HIGH**

- **H1** — `src/flowos/service/services/plan_import.py:517-533`
  (`PlanImportService._parse_with_phases`). Servisni put koji GUI/API stvarno
  koristi za import plana nikad ne računa `unclear_sections` — `stats.
  unclear` je uvijek `0`, nezavisno od stvarnog sadržaja markdown-a i
  nezavisno od FLOW-1104 fix-a. **Dokaz**: probe koji poredi `PlanMarkdownParser.
  parse()` (vraća `['## Nepoznata sekcija']`) naspram `PlanImportService.
  import_plan()` na istom ulazu (vraća `[]`). **Uticaj**: praktična vrijednost
  Bug A popravke je nevidljiva na stvarnom import putu; korisnik nikad ne
  dobija upozorenje o nejasnim sekcijama kroz GUI/API, samo kroz direktan
  poziv parsera (testovi). Pre-postojeći gap, nije uzrokovan ovim diff-om, ali
  materijalno relevantan za kompletnost FLOW-1104 kao "stabilize... reporting"
  zadatka. **Minimalna ispravka**: `_parse_with_phases()` treba ili pozvati
  `parser.parse(markdown)` direktno (ako assembly razlike nisu suštinske), ili
  dodati identičnu unclear-collection petlju kakva postoji u `parse()`.

**MEDIUM**

- **M1** — `tests/unit/test_plan_import.py`, `TestFlow1104InlineCode` (2
  testa). Bug B testovi koriste substring (`in`) i `.startswith()` provjere
  umjesto pune `==` jednakosti opisa kriterijuma. Stvarno ponašanje je
  dokazano ispravno (Section 4-5, moj probe), ali isporučeni testovi ne bi
  uhvatili regresiju koja korumpira dio opisa van specifično provjerenog
  tokena (npr. trailing navodnici/zagrade/interpunkcija). **Minimalna
  ispravka**: dodati test koji provjerava `desc == "tačan_očekivan_string"`
  za kriterijum sa navodnicima, uglastim zagradama i trailing interpunkcijom
  (kao moji probe primjeri 4-6).

**LOW**

- **L1** — Malformisan/neprepoznat `#### ` heading (ne poklapa se sa
  `ITEM_HEADING`) se sada tiho ignoriše u `_parse_phase_sections()` — ne
  pojavljuje se nigdje (ni kao stavka, ni kao unclear). Prije FLOW-1104 fix-a,
  isti slučaj je (kao SPOREDNI efekat iste greške koja je lažno flagovala
  VALIDNE FLOW stavke) bio hvatan u `unclear_sections`. Ovo nije regresija u
  namjeravanom ponašanju (docstring uvijek opisuje "unclear" kao specifično za
  neprepoznat H2, ne H4), i `_parse_phase_sections()` nije diran ovim diff-om.
  Informativna napomena, ne blokira.

## 13. Finalni verdict

```
BUG A ROOT CAUSE:                CONFIRMED
BUG A FIX:                       ACCEPT
UNKNOWN H2 STILL REPORTED:       YES
VALID FLOW H4 FALSE UNCLEAR:     CLOSED
BUG B ROOT CAUSE:                CONFIRMED
INLINE CODE PRESERVATION:        ACCEPT
PUNCTUATION PRESERVED:           YES
PARSER CONTRACT PRESERVED:       YES

DOGFOODING V1: phases=5 items=20 criteria=141 dependencies=20 unclear=0
DOGFOODING V2: phases=5 items=22 criteria=157 dependencies=23 unclear=0
V1/V2 DIVERGENCE: PRE-EXISTING

DIRECT/SERVICE CONSISTENCY:      FIXES REQUIRED
TEST QUALITY:                    FIXES REQUIRED

scripts/verify.py: 7/7
```

**FLOW-1104 = FIXES REQUIRED**

Razlog: oba prijavljena bug fix-a (A i B) su ispravna, potvrđena i nezavisno
dokazana probe-ovima sa tačnim string poređenjem — ovo NIJE sporno. V1/v2
divergencija je ispravno izvan scope-a, potvrđeno pre-postojeća. Ali review je
otkrio dva materijalna nedostatka koja review zahtjev eksplicitno traži da se
provjere: (1) stvaran servisni import put (`PlanImportService`, ono što GUI/
API zaista koriste) nikad ne računa `unclear_sections`, čime je praktična
vrijednost Bug A popravke nevidljiva korisniku na stvarnom putu — ovo je
pre-postojeći gap, ali materijalno potkopava svrhu "reporting fix" zadatka;
(2) Bug B testovi koriste substring/`.startswith()` umjesto pune `==`
provjere, što je slabija zaštita od buduće regresije nego što bi trebalo biti
za string-manipulacioni bugfix ove vrste.

Kod za same regex/level izmjene je ispravan i minimalan — problem nije u
onome što je izmijenjeno, nego u obimu onoga što NIJE pokriveno (servisni put)
i strogosti testova koji dokazuju popravku.
