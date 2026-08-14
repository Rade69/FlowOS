---
flowos_report_version: 1
report_id: d2ca5d1f-e6c6-4c00-ada6-f1a8cb773c30
agent: crush
model: deepseek-v4-pro
session_id: unknown
report_type: implementation
work_status: completed
tasks:
  - FLOW-1104
commits: []
created_at: 2026-08-13T21:30:39+02:00
---

# FLOW-1104 — Stabilizacija PlanMarkdownParser import reporting-a

Datum: 2026-08-13
Agent: crush / deepseek-v4-pro
Sesija: unknown
Baseline: 3f22a4f101761918069e9e793aa3c3d6e1db6622

## Scope

Ispraviti dva deterministička buga u `PlanMarkdownParser` i pokriti ih
determinističkim regression testovima. Bez promene formata parsera, bez
AI/LLM zaključivanja, bez izmena GUI/API/baze/dogfooding plana.

## Task contract / acceptance kriteriji

- BUG A: validan `#### FLOW-...` heading više se ne prijavljuje kao `unclear_section`.
- BUG B: numerisani kriterijum čuva inline-code backtick-ove.
- Neprepoznat `## ` (LEVEL-2) heading i dalje se prijavljuje kao unclear.
- Parser format, dependency/risk/DOKAZ/OUT_OF_SCOPE/DRAFT semantika nepromenjeni.
- Dogfooding direktni parse: `phases=5`, `unclear=0`.
- `scripts/verify.py` prolazi 7/7.

## GitNexus impact

Pre izmene pokrenut `npx gitnexus status` (indeks bio stale) i `npx gitnexus analyze`.
Pogođen simbol: `PlanMarkdownParser.parse` i `PlanMarkdownParser._extract_criteria`.
Ručni blast radius: pozivaoci su `PlanImportService.import_plan` (preko
`_parse_with_phases`) i unit testovi `tests/unit/test_plan_import.py`. Rizik
ocenjen kao NIZAK (lokalna parserska logika, bez uticaja na bazu/migracije/API).

## Reprodukcija pre izmene

Direktan `PlanMarkdownParser().parse()` na dogfooding planu v1 vraćao je
`unclear_sections = 20` (svih 20 validnih `#### FLOW-...` stavki pogrešno
prijavljeno). Na `-v2.md` (22 stavke) originalni parser vraćao je `unclear = 22`.

## BUG A ROOT CAUSE

`parse()` je klasifikovao nejasnoće tekstualnim prefiks testom:

```python
heading and heading.startswith("##") and not self.PHASE_HEADING.match(heading)
```

Validan `#### FLOW-...` heading takođe počinje sa `"##"`, pa je svaki validan
FLOW item pogrešno prijavljivan kao `unclear_section`.

## BUG A FIX

Koristiti strukturni nivo sekcije koji parser već beleži (`section["level"]`):

```python
heading and section["level"] == 2 and not self.PHASE_HEADING.match(heading)
```

Samo neprepoznati LEVEL-2 (`## `) heading može biti nejasna top-level sekcija.

## BUG B ROOT CAUSE

Numerisani cleanup je imao semantiku:

```python
re.sub(r"^\d+\.\s*`?\s*", "", stripped).strip("`; ")
```

Regex je uklanjao vodeći backtick, a `.strip("`; ")` je uklanjao trailing
backtick i interpunkciju. Kriterijum koji počinje inline kodom gubio je
oba backtick-a.

## BUG B FIX

```python
re.sub(r"^\d+\.\s*", "", stripped).strip()
```

Uklanja se SAMO Markdown list prefiks (`<broj>.` + whitespace). Backtick-ovi,
navodnici, zagrade, interpunkcija i event/status nazivi ostaju netaknuti.

## Šta je urađeno / kako

- `src/flowos/service/services/plan_import.py:117` — BUG A fix (level 2 umesto `startswith("##")`).
- `src/flowos/service/services/plan_import.py:317` — BUG B fix (samo `^\d+\.\s*`, bez `\`?` i bez `.strip("`; ")`).
- `tests/unit/test_plan_import.py` — dodati regression testovi `TestFlow1104ParserReporting`
  i `TestFlow1104InlineCode` (5 novih testova).

## Izmijenjeni fajlovi

- `src/flowos/service/services/plan_import.py`
- `tests/unit/test_plan_import.py`

## Validacioni nalazi

VALID FLOW H4 REPORTED UNCLEAR: NO
UNKNOWN H2 STILL REPORTED: YES
INLINE CODE PRESERVED: PASS
DIRECT/SERVICE CONSISTENCY: PASS

## DOGFOODING DIRECT PARSE

Na `docs/FlowOS-plan-faze-11-15-dogfooding-v2.md` (naveden u zadatku):

```text
phases=5
items=22
criteria=157
dependencies=23
unclear=0
```

Na `docs/FlowOS-plan-faze-11-15-dogfooding.md` (v1, bez `-v2`):

```text
phases=5
items=20
criteria=141
dependencies=20
unclear=0
```

## Konflikti / divergencija (pre-existing, nije uzrokovana FLOW-1104)

Pre-import evidence (`items=20`, `criteria=141`, `dependencies=20`,
`unclear=20`) tačno odgovara fajlu `FlowOS-plan-faze-11-15-dogfooding.md`
(v1, 20 FLOW stavki), a NE `-v2.md` (22 FLOW stavke). `-v2.md` ima 22 stavke,
157 kriterijuma i 23 zavisnosti. Ovo je nevezana divergencija verzija plana;
FLOW-1104 je ne menja i ne širi scope na nju.

Dokaz da fix NE menja item/dependency counts (original HEAD parser vs trenutni
parser na `-v2.md`):

```text
phases: orig=5 curr=5
items: orig=22 curr=22
criteria: orig=157 curr=157
dependencies: orig=23 curr=23
unclear: orig=22 curr=0
```

Fix menja ISKLJUČIVO `unclear` (22→0 na `-v2.md`, odnosno 20→0 na `-v1.md`).

## DIRECT/SERVICE CONSISTENCY

`PlanMarkdownParser.parse()` vs `PlanImportService._parse_with_phases()` na
istom `-v2.md` ulazu: title, phases, items, criteria, dependencies i unclear
se u potpunosti poklapaju; `desc_mismatch=0` (0 od 157 kriterijum opisa se razlikuje).

## Verifikacija

TARGETED TESTS (`pytest tests/unit/test_plan_import.py`):

```text
22 passed in 2.35s
```

`scripts/verify.py`:

```text
[PASS] 1. Ruff format check
[PASS] 2. Ruff lint
[PASS] 3. mypy
[PASS] 4. Architecture boundaries
[PASS] 5. Unit tests        (477 passed)
[PASS] 6. Migrations check
[PASS] 7. Alembic round-trip
Prošlo: 7/7
```

## Šta nije dirano

- FLOW-1105 (GUI/backend markdown vs markdown_text)
- FLOW-1106 (actual plan import)
- GUI / kontroleri / shared API contracts
- DB modeli / migracije
- plan activation / AI-LLM parsing
- dogfooding plan Markdown

## Commitovi

Nijedan (zabranjeno promptom — "Do NOT commit", "Do NOT push").

## Rizici i ograničenja

Nema. Izmene su lokalne u parseru, pokrivene determinističkim testovima.

## Potreban follow-up

Nezavisna review FLOW-1104. Divergencija verzija dogfooding plana (v1 vs v2)
je zasebna stvar koja nije u scope-u FLOW-1104.

## Potrebna korisnička potvrda

Nema za samu ispravku. Integracija/commit po korisničkom zahtevu.

## Odstupanja od prompta

NONE
