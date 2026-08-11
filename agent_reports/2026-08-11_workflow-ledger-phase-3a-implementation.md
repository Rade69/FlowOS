---
flowos_report_version: 1
report_id: a5be979c-6df8-41d8-8372-9d54755d5a8d
agent: codex
model: gpt-5
session_id: unknown
report_type: implementation
work_status: completed
tasks:
  - unassigned
commits: []
created_at: 2026-08-11T19:21:10.9935089+02:00
---

# Workflow Ledger Phase 3A — implementation

## Datum

2026-08-11

## Agent / model / sesija

- Agent: Codex
- Model: gpt-5
- Sesija: unknown

## Scope

Implementiran je samo FlowOS Workflow Ledger Phase 3A:

- nova `workflow_ledger_events` tabela;
- novi `WorkflowLedgerEvent` ORM model;
- novi minimalni `WorkflowLedgerService`;
- prvi writer za `IMPLEMENTATION_COMPLETED`;
- authority cutover u `SessionCompletionService`;
- wiring iz `AgentReportIngestionService`;
- regression testovi za Ledger i SessionCompletion.

Nije implementirano:

- `TEST_RESULT`;
- review/finding/fix/user decision Ledger eventi;
- GUI;
- HTTP Ledger API;
- event-sourcing framework;
- queue/broker/reconciliation;
- YAML contract promjene;
- backfill starih reportova;
- izmjene `ReportService.set_verdict()` authority toka.

## Task contract / acceptance kriteriji

Implementacija prati analysis report:

`agent_reports/2026-08-11_workflow-ledger-phase-3a-analysis.md`

Acceptance kriteriji:

- SessionCompletion više ne smije automatski mijenjati `PlanItem.status` na osnovu commita, dirty files ili `verify.py PASS`;
- canonical ingested `AgentReport` sa `report_type=implementation` i `work_status=completed` proizvodi `IMPLEMENTATION_COMPLETED`;
- non-qualifying reporti ne proizvode event;
- jedan report može proizvesti više eventa, jedan po logičkom targetu;
- A-B-A segmenti za isti target daju jedan event sa svim linkovima u payloadu;
- idempotency je deterministički i DB-unique;
- `AgentReport`, binding linkovi i Ledger event nastaju u istoj DB transakciji;
- puna verifikacija mora proći.

## GitNexus impact ili ručni blast radius

GitNexus impact za `SessionCompletionService`:

- risk: LOW;
- direktni importer: `src/flowos/service/composition_root.py`;
- indirektno: `src/flowos/service/app.py`.

GitNexus `detect_changes` nakon implementacije:

- risk: MEDIUM;
- glavni pogođeni simbol: `SessionCompletionService.complete_session`;
- pogođeni flowovi uključuju `_complete → _run_git`, `_complete → _parse_porcelain_v2`, `_complete → Disconnect`, `_complete → Save`, `_complete → _derive_status`.

`AgentReportIngestionService` nije pronađen u GitNexus indeksu, pa je blast radius za njega provjeren ručno kroz:

- `composition_root.py` watcher callback;
- startup scan ingestion;
- `tests/integration/test_agent_report_ingestion.py`;
- `tests/integration/test_agent_report_v2.py`;
- novi `tests/integration/test_workflow_ledger_phase3a.py`.

## Reprodukcija prije izmjene

Prije Phase 3A, `SessionCompletionService.complete_session()` je:

- prebacivao `PlanItem` iz `IN_PROGRESS` u `IMPLEMENTED` na osnovu result commita ili dirty files;
- prebacivao `PlanItem` iz `IMPLEMENTED` u `VERIFIED` na osnovu `verify.py PASS`;
- emitovao `plan_progress.updated` iz completion toka.

To je bilo suprotno novom authority modelu: commit, dirty files i verify pass su činjenice, ali nisu workflow odluka.

## Šta je urađeno

### Nova Ledger tabela

Dodata je Alembic migracija:

`alembic/versions/b7c2e1d4a903_workflow_ledger_events.py`

Kreira tabelu:

`workflow_ledger_events`

Polja:

- `id` — `String(36)`, PK, UUID;
- `project_id` — `String(36)`, NOT NULL, FK `projects.id`, `ON DELETE CASCADE`;
- `event_type` — `String(80)`, NOT NULL;
- `session_id` — nullable FK `agent_sessions.id`, `ON DELETE SET NULL`;
- `task_id` — nullable FK `tasks.id`, `ON DELETE SET NULL`;
- `plan_item_id` — nullable FK `plan_items.id`, `ON DELETE SET NULL`;
- `source_kind` — `String(80)`, NOT NULL;
- `source_id` — `String(120)`, NOT NULL;
- `occurred_at` — timezone-aware `DateTime`, NOT NULL;
- `recorded_at` — timezone-aware `DateTime`, NOT NULL;
- `idempotency_key` — `String(300)`, NOT NULL, unique;
- `payload_json` — `Text`, NOT NULL, server default `{}`.

Indeksi:

- `(project_id, recorded_at)`;
- `(project_id, event_type, recorded_at)`;
- `(session_id, recorded_at)`;
- `(task_id, recorded_at)`;
- `(plan_item_id, recorded_at)`;
- `(source_kind, source_id)`;
- unique constraint na `idempotency_key`.

Nema DB CHECK-a koji zaključava buduću enum listu.

### Novi ORM model

Dodat je:

`src/flowos/service/services/infrastructure/persistence/workflow_ledger_models.py`

Model:

`WorkflowLedgerEvent`

Model je importovan u `alembic/env.py` da bude vidljiv Alembic metapodacima.

### Novi WorkflowLedgerService

Dodat je:

`src/flowos/service/services/workflow/ledger.py`

Minimalni contract:

- `append_implementation_completed_from_report(report_id)`;
- `list_for_project(project_id)`;
- `list_for_task(task_id)`.

Servis nema `update_event`, `delete_event` ili `replace_event`.

### IMPLEMENTATION_COMPLETED policy

Event nastaje samo ako DB `AgentReport` zadovoljava:

- `report_type == "implementation"`;
- `work_status == "completed"`;
- `source_report_id IS NOT NULL`;
- `source_path IS NOT NULL`;
- `source_content_sha256 IS NOT NULL`;
- `session_id` postoji;
- ima najmanje jedan `AgentReportBindingLink`;
- svaki link pokazuje na postojeći `SessionTaskBinding` iste sesije;
- binding se može deterministički pretvoriti u `task:<id>` ili `plan_item:<id>`.

No-op slučajevi:

- `analysis`;
- `review`;
- `fix`;
- `partial`;
- `blocked`;
- `tasks: [unassigned]`;
- `NEEDS_LINK`;
- legacy draft report bez source identity-ja i binding linkova.

### Multi-task i A-B-A grouping

Grouping pravilo:

- binding sa `task_id` daje target `task:<task_id>`;
- direct PlanItem binding daje target `plan_item:<plan_item_id>`;
- jedan event po logičkom targetu;
- A-B-A segmenti istog taska daju jedan event;
- payload sadrži sve relevantne `AgentReportBindingLink.id` i `SessionTaskBinding.id`, sortirane deterministički.

Za task event:

- ako postoji tačno jedan distinct `resolved_plan_item_id` snapshot, `event.plan_item_id` čuva taj snapshot;
- ako snapshot ne postoji, `event.plan_item_id = NULL`;
- ako postoji više različitih snapshotova, `event.plan_item_id = NULL`, a payload čuva sve snapshotove u `resolved_plan_item_ids`.

Live `Task.plan_item_id` se ne koristi kao historijski authority kada postoje `AgentReportBindingLink` snapshotovi.

### Idempotency

Tačan format:

```text
workflow-ledger:v1:IMPLEMENTATION_COMPLETED:agent_report:{AgentReport.id}:{target_kind}:{target_id}
```

Servis prvo traži postojeći event sa istim key-em i radi no-op ako postoji. DB unique constraint je dodatna zaštita od race-a.

### Transaction boundary

`AgentReportIngestionService.ingest_file()` sada poslije kreiranja `AgentReport` i svih `AgentReportBindingLink` redova poziva:

```python
WorkflowLedgerService(self._session).append_implementation_completed_from_report(report.id)
```

Caller i dalje radi završni commit. Zato qualifying ingestion transakcija sadrži:

- `AgentReport`;
- `AgentReportBindingLink`;
- `WorkflowLedgerEvent`.

Ako Ledger append padne, caller rollback uklanja report, linkove i evente. Watcher nije dobio workflow business pravila.

### Authority cutover u SessionCompletionService

Iz `SessionCompletionService.complete_session()` uklonjeno je:

- `IN_PROGRESS → IMPLEMENTED` na osnovu result commita, dirty files/Git promjene i conflict heuristike;
- `IMPLEMENTED → VERIFIED` na osnovu `verify.py PASS`;
- `plan_progress.updated` emit iz completion toka.

Zadržano je:

- `ended_at`;
- `exit_code`;
- `result_commit_sha`;
- zatvaranje aktivnog `SessionTaskBinding`;
- procesni `AgentSession.status`;
- Git state read;
- `VerificationService`;
- verification artefakt;
- `VERIFY_RESULT` `SessionEvent`;
- `verification.completed`;
- legacy draft `AgentReport`;
- `NO_COMMIT` conflict detection;
- project resume regeneracija;
- `session.completed`;
- `project.resume.updated`.

## Zašto je urađeno

Da FlowOS prestane tretirati procesne/Git/test činjenice kao workflow odluke.

Novi authority chain je:

```text
agent_reports/*.md
→ deterministic AgentReport ingestion
→ DB AgentReport + BindingLinks
→ WorkflowLedgerEvent
→ budući Workflow Ledger read/projection sloj
```

`IMPLEMENTATION_COMPLETED` je implementer claim, ne dokaz review-a, testova, verifikacije ili korisničkog prihvatanja.

## Kako je urađeno

Implementacija je urađena minimalno:

- nova DB tabela je generična za buduće evente, ali writer dozvoljava samo `IMPLEMENTATION_COMPLETED`;
- policy je u service sloju;
- watcher i startup scan ostaju samo caller-i istog ingestion servisa;
- nema HTTP/GUI površine;
- nema backfilla;
- nema LLM-a;
- nema frameworka.

## Izmijenjeni fajlovi i ponašanje

Izmijenjeni postojeći fajlovi:

- `alembic/env.py` — import novog ORM modela za Alembic metadata;
- `src/flowos/service/services/reports/ingestion.py` — nakon report/link flush-a poziva Workflow Ledger writer;
- `src/flowos/service/services/sessions/completion.py` — uklonjena automatska PlanItem status promocija i `plan_progress.updated` emit;
- `tests/unit/test_session_completion.py` — dodani regression testovi za novu authority semantiku.

Novi fajlovi:

- `alembic/versions/b7c2e1d4a903_workflow_ledger_events.py`;
- `src/flowos/service/services/infrastructure/persistence/workflow_ledger_models.py`;
- `src/flowos/service/services/workflow/__init__.py`;
- `src/flowos/service/services/workflow/ledger.py`;
- `tests/integration/test_workflow_ledger_phase3a.py`;
- `agent_reports/2026-08-11_workflow-ledger-phase-3a-implementation.md`.

Postojeći prethodni analysis report ostaje u working treeju:

- `agent_reports/2026-08-11_workflow-ledger-phase-3a-analysis.md`.

## Šta nije dirano

- `VerificationService` nije mijenjan;
- `ReportService.set_verdict()` nije mijenjan;
- AgentReport YAML parser/contract nije mijenjan;
- GUI nije mijenjan;
- HTTP rute nisu dodane;
- stari reporti nisu backfillovani;
- GitNexus tooling nije ručno mijenjan;
- commit nije napravljen.

## Verifikacija i stvarni rezultat

Pokrenuto:

```text
python -m pytest tests/integration/test_workflow_ledger_phase3a.py -v --tb=short
```

Rezultat:

```text
17 passed
```

Pokrenuto:

```text
python -m pytest tests/unit/test_session_completion.py tests/integration/test_agent_report_ingestion.py tests/integration/test_agent_report_v2.py tests/integration/test_session_task_bindings.py tests/unit/test_plan_progress.py tests/integration/test_plan_progress_api.py -v --tb=short
```

Rezultat:

```text
122 passed, 1 warning
```

Pokrenut ručni Alembic round-trip na privremenoj SQLite bazi:

```text
upgrade head
downgrade 4f2c9a7b8d11
upgrade head
```

Rezultat:

```text
PASS
```

Pokrenuto:

```text
python scripts/guard_architecture.py
```

Rezultat:

```text
FAIL — skripta prijavljuje postojeće service → websocket event_bus importe u više servisa.
```

Ovaj stricter guard nalaz nije proširen u ovom Phase 3A scope-u. Puni verify koristi `tests/architecture/` i prošao je.

Pokrenuto:

```text
python scripts/verify.py
```

Rezultat:

```text
[PASS] 1. Ruff format check
[PASS] 2. Ruff lint
[PASS] 3. mypy
[PASS] 4. Architecture boundaries
[PASS] 5. Unit tests
[PASS] 6. Migrations check
[PASS] 7. Alembic round-trip

Prošlo: 7/7
[PASS] VERIFIKACIJA PROŠLA
```

Test suite u verify:

```text
390 passed, 1 warning
```

## Nezavisna provjera

Nije urađena nezavisna provjera. Paket je spreman za independent review.

## Pronađeni problemi

Poznato ograničenje:

- `ReportService.set_verdict()` i dalje direktno vraća `PlanItem` u `IN_PROGRESS` za `NEEDS_WORK`/`REJECTED`.

To je namjerno ostavljeno van Phase 3A, po nalogu. To treba biti sljedeći authority-cutover kandidat za budući `USER_VALIDATION` ili `TASK_DECISION` Ledger event.

## Odbačene opcije

Opcija: dodati HTTP Ledger API.
Zašto odbačeno: Phase 3A može biti dokazan service/DB testovima; GUI/API čitanje nije potrebno.
Kada ponovo otvoriti: kada bude potreban read model za GUI ili Workflow Ledger pregled.

Opcija: emitovati Ledger iz watcher callback-a.
Zašto odbačeno: watcher ne smije nositi workflow business policy.
Kada ponovo otvoriti: ne preporučuje se; ingestion service je ispravan boundary.

Opcija: koristiti live `Task.plan_item_id` pri appendu.
Zašto odbačeno: to bi pokvarilo historijsku atribuciju ako se Task kasnije relinkuje.
Kada ponovo otvoriti: samo ako se uvede eksplicitni snapshot/backfill model koji dokazuje sigurnost.

Opcija: maskirati sve `IntegrityError` kao idempotency no-op.
Zašto odbačeno: nalog traži da se ne maskiraju druge DB greške.
Kada ponovo otvoriti: samo uz precizno constraint-name parsiranje i race testove.

## Konflikti/kontradiktorni izvori

Nema kontradikcije u implementacionom nalogu.

Postoji razlika između:

- `scripts/guard_architecture.py`, koji prijavljuje stare service → websocket import nalaze;
- `python scripts/verify.py`, gdje `tests/architecture/` prolazi.

Nisam proširio Phase 3A na refactor websocket event bus boundary-ja.

## Commitovi

Nema novih commitova.

## Rizici i ograničenja

- Nema backfill-a starih reportova, namjerno.
- Legacy completion draft reporti ne proizvode Ledger event, namjerno.
- `ReportService.set_verdict()` ostaje poznat authority-cutover dug.
- `WorkflowLedgerService` je backend-only writer bez API-ja; budući GUI će trebati read/projection sloj.
- `TEST_RESULT` nije implementiran, ali model ima `event_type/source_kind/source_id/payload_json` oblik koji ga može primiti bez nove osnovne arhitekture.

## Potreban follow-up

1. Independent review Phase 3A diff-a.
2. Nakon prihvatanja, poseban commit.
3. Sljedeća faza: definisati `TEST_RESULT` writer iz `VerificationService` artefakta ili cutover za `ReportService.set_verdict()` u `USER_VALIDATION`/`TASK_DECISION`.

## Potrebna korisnička potvrda

Potrebna je korisnička/review potvrda da je Phase 3A scope ispravan i da je `IMPLEMENTATION_COMPLETED` samo implementer claim, ne PlanItem status tranzicija.

READY FOR INDEPENDENT REVIEW
