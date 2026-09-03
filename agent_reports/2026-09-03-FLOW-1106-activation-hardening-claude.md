---
flowos_report_version: 1
report_id: 5e8c1a4f-9b26-4d73-8f10-2c6a9e4b1106
agent: claude
model: claude-sonnet-5
session_id: unknown
report_type: implementation
work_status: completed
tasks:
  - FLOW-1106
commits: []
created_at: 2026-09-03T00:00:00+02:00
---

# FLOW-1106 — Activation hardening (handoff from Codex)

## Handoff state

Preuzeto od Codexa nakon što je iscrpio context/token limit. Read-only
rekonstrukcija prije bilo kakve izmjene:

- `git status --short --branch` → `task/FLOW-1106-activation-hardening...origin/main`,
  9 modifikovanih + 2 nova fajla, sve nekomitovano.
- `git fetch --all --prune` → bez novih refova; `git branch -vv` potvrđuje da
  `task/FLOW-1106-activation-hardening` sjedi tačno na istom commitu kao
  trenutni `origin/main` (`8416d27`) — grana je već svježa, nije potrebno
  rebase-ovati niti praviti novu granu.
- `git reflog show main` potvrđuje da nijedan raniji rad (uključujući moj
  FLOW-1156/1157/1158 commit iz prethodne sesije) nije izgubljen — sve je i
  dalje predak trenutnog `origin/main` (`git merge-base --is-ancestor` = YES).
- Nema postojećeg `agent_report`-a za activation-hardening dio (postoji samo
  `2026-09-03-FLOW-1106-F1-pi.md`, koji pokriva DRUGI, već mergovan
  sub-task — GUI status label fix, nevezan za ovaj rad).
- Codex-ov rad je pročitan u cijelosti (diff + novi fajlovi) prije bilo kakve
  izmjene, kako handoff zahtijeva.

**Reused:** kompletan Codex-ov rad — ORM partial UNIQUE index, Alembic
migracija, schema_repair self-heal, `activate_plan()` atomic redosled,
`ProjectResumeService.regenerate` reuse, `WorkflowLedgerService.append_plan_activated`,
i novi `tests/integration/test_plan_activation_contract.py` (11 testova, T1-T12
osim T2 koji je stopljen u T3-test).

**Discarded:** ništa. Codex-ov rad je bio arhitektonski ispravan i potpun za
scope koji je pokrivao.

**Reason:** Nakon punog pregleda koda i pokretanja testova, Codex-ov
implementacioni pristup je zdrav — DB-level partial unique index +
service-level deterministic supersede + postojeći canonical audit/resume
mehanizmi, tačno kako §5/§7/§8 handoff-a traže. Nije bilo razloga za
ponovno pisanje.

**Baseline:** `8416d27` (= trenutni `origin/main`, potvrđeno fresh fetch-om).

**Branch:** `task/FLOW-1106-activation-hardening` (nastavljena, ne nova).

**Implementation HEAD:** nekomitovano do kraja ove sesije — vidi "Commitovi"
niže za tačan SHA nakon commita.

## Šta sam DODAO preko Codex-ovog rada

Codex-ov diff je bio nepotpun u tačno jednoj stvari: novi partial UNIQUE
index (`project_id WHERE status='ACTIVE'`) je ispravno primoran na DB nivou,
ali **nije provjeren protiv cijelog test suite-a** — samo protiv ledger
Phase3A-3D fajlova (koje je Codex i popravio istim obrascem). Pun
`python scripts/verify.py` je otkrio **8 dodatnih failing testova** u TRI
fajla koje Codex nije dirao: `test_agent_report_ingestion.py` (2),
`test_agent_report_v2.py` (5), `test_session_task_bindings.py` (1) — svi sa
istim uzrokom: `_plan_item()` test-helper je kreirao drugi `Plan(status="ACTIVE")`
za isti projekat, što novi index sada ispravno odbija
(`sqlite3.IntegrityError: UNIQUE constraint failed: plans.project_id`).

Popravio sam sve tri po IDENTIČNOM obrascu koji je Codex već uspostavio u
Phase3A-3D fajlovima (potraži postojeći ACTIVE plan za projekat prije
kreiranja novog):

```python
plan = (
    db.query(Plan)
    .filter(Plan.project_id == project.id, Plan.status == "ACTIVE")
    .one_or_none()
)
if plan is None:
    plan = Plan(id=f"plan-{key}", project_id=project.id, title=key, status="ACTIVE")
```

Provjerio sam grep-om (`Plan(` + `status="ACTIVE"`) SVE preostale fajlove sa
istim obrascem (14 ukupno) i potvrdio pokretanjem da preostalih 6
(`test_project_resume_api.py`, `test_sessions_plan_item_api.py`,
`test_evidence.py`, `test_plan_progress.py`, `test_project_resume.py`,
`test_session_completion.py`) nemaju problem — svaki kreira samo JEDAN
ACTIVE plan po projektu, pa nova constraint ne smeta. Drugi pogodak u
`test_session_task_bindings.py:411` (`test_plan_item_fk_is_also_restricted`)
je namjerno ostavljen netaknut — koristi svjež, poseban projekat unutar tog
testa, nije duplikat.

Takođe pokrenuo `ruff format` — 7 fajlova (uključujući Codex-ove, koje nije
stigao formatirati) je trebalo reformat; sve primijenjeno, `ruff check`/`mypy`
ostaju čisti.

## CHANGED FILES

```text
M  src/flowos/service/services/infrastructure/persistence/plan_models.py     (Codex)
M  src/flowos/service/services/infrastructure/persistence/schema_repair.py   (Codex)
M  src/flowos/service/services/plan_progress.py                             (Codex)
M  src/flowos/service/services/workflow/ledger.py                           (Codex)
M  tests/integration/test_workflow_ledger_phase3a.py                        (Codex)
M  tests/integration/test_workflow_ledger_phase3b.py                        (Codex)
M  tests/integration/test_workflow_ledger_phase3c.py                        (Codex)
M  tests/integration/test_workflow_ledger_phase3d.py                        (Codex)
M  tests/unit/test_schema_repair.py                                         (Codex)
A  alembic/versions/c83f1a2d4e67_one_active_plan_per_project.py             (Codex)
A  tests/integration/test_plan_activation_contract.py                       (Codex)
M  tests/integration/test_agent_report_ingestion.py                        (Claude — fixture fix)
M  tests/integration/test_agent_report_v2.py                               (Claude — fixture fix)
M  tests/integration/test_session_task_bindings.py                         (Claude — fixture fix)
```

## Arhitektonska analiza implementacije

### ACTIVE uniqueness — DB + service nivo

- `Plan.__table_args__` dobija `Index("uq_plans_one_active_per_project",
  "project_id", unique=True, sqlite_where=text("status = 'ACTIVE'"))` —
  partial UNIQUE index, ORM-level definicija za `create_all()`-bazirane
  test baze.
- Alembic migracija `c83f1a2d4e67` dodaje isti index za realne
  deployovane baze — `upgrade()` će PUCATI (`IntegrityError`) ako postojeći
  podaci već imaju duplikate, umjesto tihog gubitka podataka.
- `schema_repair.py` dobija `_ensure_plan_active_index` (idempotentan
  `CREATE UNIQUE INDEX IF NOT EXISTS ... WHERE status = 'ACTIVE'`) i
  `_plan_active_index_valid` (provjerava shape + WHERE uslov) za
  dev/legacy baze van čistog Alembic toka — isti trostruki obrazac
  (ORM/migracija/self-heal) koji već postoji za `workflow_ledger_events`
  idempotency unique constraint.
- **Sigurno ponašanje za postojeće duplikate**: dokazano DVA različita,
  namjerno različita ponašanja za dva različita puta —
  - `repair_database()` (startup/maintenance) **odbija** (fail-closed,
    `IntegrityError`, nula promjena podataka) — dokazano testom
    `test_previous_head_duplicate_active_plans_abort_repair_without_data_change`.
  - `activate_plan()` (runtime, eksplicitna korisnička akcija) **deterministički
    superseduje SVE prethodne ACTIVE** (ne samo `.first()`) — dokazano T9.
  Ovo nije nekonzistentnost — repair je pasivna infrastrukturna operacija
  koja ne smije nagađati o ambiguoznom istorijskom stanju; activate je
  eksplicitna, namjerna akcija u trenutku kad korisnik bira NOVI ACTIVE plan.

### Atomicity i redoslijed

`activate_plan()`: (1) query SVI previous ACTIVE (ne `.first()`) → (2) svi →
SUPERSEDED → (3) **flush** → (4) target → ACTIVE → (5) **flush** → (6)
`ProjectResumeService.regenerate()` (postojeći canonical mehanizam, ne
direktan column write) → (7) `WorkflowLedgerService.append_plan_activated()`
(postojeća append-only Ledger infrastruktura, idempotentan preko
`idempotency_key=f"plan-activated:{plan_id}"`) → (8) invariant re-query
(`active_count == 1`, inače `RuntimeError`).

Redoslijed flush-eva (superseduj PA flush, PA aktiviraj PA flush) je
namjerno — sprečava trenutno kršenje partial unique indexa unutar iste
transakcije. Transakcijska granica je FastAPI `get_session` dependency
(`yield session; session.commit()` / `except: session.rollback(); raise`) —
svaki exception iz `activate_plan()` (uključujući invariant `RuntimeError`)
propagira do rollback-a. Cijela operacija je JEDNA DB transakcija.

## ADVERSARIAL MUTATION TESTS — sopstveno pokrenuto

Sve tri mutacije rađene direktno na `src/flowos/service/services/plan_progress.py`,
svaka: izmjena → ciljani test FAIL (doslovan output ispod) → vraćeno na
Codex-ov originalni kod → potvrđen PASS. Nijedna mutacija nije komitovana.

**Mutacija A — vraćen `.first()`-ekvivalentno ponašanje** (samo prvi od
prethodnih ACTIVE se superseduje):

```
FAILED test_t9_legacy_multiple_active_plans_are_all_superseded
RuntimeError: Plan activation invariant nije zadovoljen za projekat ...
```

Uhvaćeno invariant re-query provjerom (dodatni sloj odbrane iako je index
u tom testu namjerno isključen da bi se testirao stariji-legacy scenario).

**Mutacija B — uklonjen `ProjectResumeService(...).regenerate(...)` poziv:**

```
FAILED test_t1_t3_t4_t5_activate_without_previous_active
AssertionError: assert None == '462f1dd6-541e-459e-ba9a-e998406682e1'
```

**Mutacija C — uklonjen `WorkflowLedgerService(...).append_plan_activated(...)` poziv:**

```
FAILED test_t1_t3_t4_t5_activate_without_previous_active
assert 0 == 1  (0 = len([]) audit eventova)
```

Poslije svake mutacije: `git diff --stat` na `plan_progress.py` potvrđen
identičan originalnom Codex-ovom diffu (31 insertions/5 deletions) —
fajl je bajt-identičan.

## TARGETED TESTS

```
$ python -m pytest tests/integration/test_plan_activation_contract.py -v
11 passed in 15.46s
```

## Šira regresija (§12 relevant plan-progress/service test scope)

```
$ python -m pytest tests/unit/test_schema_repair.py \
    tests/integration/test_workflow_ledger_phase3a.py \
    tests/integration/test_workflow_ledger_phase3b.py \
    tests/integration/test_workflow_ledger_phase3c.py \
    tests/integration/test_workflow_ledger_phase3d.py \
    tests/integration/test_plan_progress_api.py -q
121 passed in 30.84s

$ python -m pytest tests/integration/test_agent_report_ingestion.py \
    tests/integration/test_agent_report_v2.py \
    tests/integration/test_session_task_bindings.py -q     # nakon mog fixa
60 passed in 27.90s

$ python -m pytest tests/integration/test_project_resume_api.py \
    tests/integration/test_sessions_plan_item_api.py tests/unit/test_evidence.py \
    tests/unit/test_plan_progress.py tests/unit/test_project_resume.py \
    tests/unit/test_session_completion.py -q     # potvrda da NISU pogodjeni
67 passed in 5.27s
```

## FULL VERIFY

Prvi pokušaj (prije mojih dodatnih fixeva): **6/8** — `1. Ruff format check`
i `6. Unit tests` (8 failed, svi u tri fajla gore navedena) su pali.

Poslije `ruff format` + tri fixture fixa:

```
$ python scripts/verify.py
[PASS] 1. Ruff format check
[PASS] 2. Ruff lint
[PASS] 3. mypy
[PASS] 4. Architecture guard
[PASS] 5. Architecture boundaries
[PASS] 6. Unit tests
[PASS] 7. Migrations check
[PASS] 8. Alembic round-trip
Prošlo: 8/8
[PASS] VERIFIKACIJA PROŠLA
```

Nije bilo potrebe gasiti Windows mutex — servis nije bio pokrenut tokom
verifikacije.

## GITNEXUS

**PRE:** `mcp__gitnexus__impact(target="activate_plan", direction="upstream")`
vratio `impactedCount: 0, risk: LOW` za `PlanProgressService.activate_plan` —
ovo je **netačno/stale** (indeks je zastario od ranije u sesiji, potvrđeno
manuelnim grep-om koji nalazi tačno jednog pozivaoca:
`controllers/http/plan_progress.py:190`). Manuelni blast radius: 1 direktan
pozivalac (HTTP ruta), poznat i ograničen.

**POST:** `mcp__gitnexus__detect_changes(scope="unstaged")` → `risk_level:
critical`, 61 "touched" simbola u 12 fajlova. Ovo je koarsni artefakt mape
(cijela `WorkflowLedgerService` klasa i njene postojeće metode označene kao
"touched" iako je diff dodao samo JEDNU novu metodu — potvrđeno da nijedna
postojeća metoda u `ledger.py` nije izmijenjena, `git diff` pokazuje čisto
aditivan blok). Stvarni affected_processes su `repair_database` i srodni
schema-repair pomoćnici (očekivano — to je dijeljena infrastruktura koju
svaki DB lifecycle put prolazi) i `_emit_and_refresh`/`_build_target_groups`
(dijeljeni plan-progress/ledger internals). Nijedan flagovan proces nije
iznenađujuć s obzirom na fajlove koji su dirani; ručna targeted+regression
test pokrivenost iznad je pouzdaniji dokaz od ovog coarse-grained signala.

## NOT VERIFIED

- Live GUI protiv stvarno pokrenutog `flowos-service.exe` (samo test-suite
  i live uvicorn TestClient, ne ručni klik kroz GUI "Aktiviraj plan" dugme).
- Ponašanje pod stvarnom konkurentnošću (dvije istovremene HTTP aktivacije
  za isti projekat) — partial unique index bi trebao spriječiti drugu na DB
  nivou, ali nije eksplicitno testirano sa stvarnim paralelnim thread-ovima/
  procesima (samo sekvencijalni T6 re-activation test).
- Da li postoji STVARNA produkcijska/dev baza sa već postojećim duplikat
  ACTIVE planovima koja bi migraciju učinila blokirajućom — nije provjereno
  jer nemam pristup takvoj bazi u ovoj sesiji; `verify.py` migracioni korak
  koristi svježu privremenu bazu.

## OUT_OF_SCOPE_FINDINGS

Nema. Sve izmjene su unutar activation-hardening scope-a definisanog
handoff-om (§4-§9) plus neophodan fixture-fix da postojeći testovi ne
puknu zbog nove DB constraint-e — to nije scope creep, to je direktna
posljedica implementacije koju handoff traži.

## Odbačene opcije

- Presjeći umjesto proširiti test-fixture fix — odbačeno, isti obrazac kao
  Codex-ov postojeći fix održava konzistentnost stila kroz test suite.
- Ne diranje trećeg pogotka u `test_session_task_bindings.py:411` — svjesno
  odbačeno jer taj test koristi svjež projekat bez postojećeg ACTIVE plana;
  diranje bi bilo nepotrebna izmjena van scope-a.

## Nezavisna provjera

`INDEPENDENT REVIEW: NOT AVAILABLE` — Crush nije dostupan kao odvojen
agent/sesija u ovom okruženju (`ListAgents` ne vraća Crush; samo offline
Remote Control peer sesije nevezane za ovaj task). Sopstvena adversarna
verifikacija iznad (mutacije, pun test suite, verify.py 8/8) NIJE
predstavljena kao independent review — to je implementer/arhitekta-nivo
samo-provjera, isti standard koji je primijenjen na FLOW-1156 ranije u ovoj
sesiji iz istog razloga.

## Commitovi

Commitovano na `task/FLOW-1106-activation-hardening` (ne `main`) nakon
pisanja ovog izvještaja — vidi git log za tačan SHA. Nije mergovano, nije
force-pushovano, `main` nije diran.
