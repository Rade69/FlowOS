---
report_type: fix
tasks:
  - unassigned
agent: codex
model: gpt-5
timestamp: 2026-08-10T17:45:19+02:00
branch: main
head_sha: 25ae36f1081a0435cd605afa38a6188c514ecded
status: GREEN_BASELINE
---

# FlowOS baseline stabilizacija

## Sažetak

BASELINE READY FOR ARCHITECTURAL MIGRATION

Postojeći FlowOS je doveden u provjerljivo stanje bez uvođenja nove arhitekture. `scripts/verify.py` sada prolazi 7/7, a kompletan `python -m pytest -q` prolazi sa 300 testova.

## Scope

U scope-u su bili dokazani model/contract bugovi iz naloga: `SessionService` plan item validacija, project timeline, `EvidenceService`, `ProjectStateService`, GUI import-plan tok, dupli `/health`, migration verify i verifikacioni/lint baseline. Nisu uvedeni `SessionTaskBinding`, Workflow Ledger, novi observer sistem, YAML parser, managed execution niti novi GUI koncept.

## Reprodukcija prije izmjene

Baseline prije izmjene:

- `git status --short --branch`: `main`, uz postojeću izmjenu `agent_reports/FLOWOS_CURRENT_STATE_AUDIT_2026-08-10.md`.
- `git rev-parse HEAD`: `25ae36f1081a0435cd605afa38a6188c514ecded`.
- `python scripts/verify.py`: FAIL, 2/7 PASS. Padovi: Ruff format, Ruff lint, mypy, architecture boundaries, migrations check. Unit/integration/contract testovi su tada prolazili 288 testova; Alembic round-trip na temp bazi je prolazio.
- Migration check je padao jer je `alembic upgrade head` išao na default lokalnu FlowOS bazu koja je već imala `projects`, dok je izolovani round-trip na praznoj temp bazi prolazio.

## Šta je urađeno

| Problem | Prije | Poslije | Test/dokaz |
|---|---|---|---|
| `SessionService → PlanItem` | `PlanItem.plan_id` ne postoji | Validacija ide `PlanItem.plan_phase_id → PlanPhase.plan_id → Plan.project_id` | `tests/integration/test_sessions_plan_item_api.py::test_create_session_accepts_valid_plan_item_id` |
| Project timeline | `/projects/{id}/timeline` filtrirao `SessionEvent.project_id` koji ne postoji | Timeline query ide preko `SessionEvent → AgentSession.project_id` u novom `ProjectTimelineService` | `test_timeline_filters_session_events_by_session_project` |
| `EvidenceService` ORM relacije | Koristio nepostojeći `plan_item.plan.phase` | Koristi stvarni `plan_item.phase.plan.project_id` i stabilnije report/conflict/criteria čitanje | `tests/unit/test_evidence.py` |
| `ProjectStateService` | Čitao `Worktree.git_status` i `ProjectWorkspaceState.is_dirty` | Koristi `Worktree.is_clean` i `ProjectWorkspaceState.last_known_status_porcelain` | `test_project_state_uses_existing_workspace_and_worktree_fields` |
| GUI import-plan shape | Import response se slao rendereru koji očekuje `plan-progress` | Nakon uspješnog POST-a GUI radi GET stvarnog plan-progress stanja | `tests/gui/test_plan_import_flow.py` |
| Dupli `/health` | Dvije iste rute u `system.py` | Ostavljena jedna kanonska ruta | `scripts/verify.py`, `test_health` |
| Migration check | `alembic upgrade head` udarao u korisničku lokalnu bazu | Verify koristi izolovanu temp SQLite bazu za migration check; round-trip ostaje zaseban | `scripts/verify.py` PASS 7/7 |
| Controller persistence import | `projects.py` i `system.py` uvozili persistence modele | Query logika premještena u servisni sloj (`ProjectTimelineService`, `SystemStateService`) | Architecture boundaries PASS |
| Reconciliation model mismatch | Korištena nepostojeća workspace/event polja | Mapirano na stvarne `ProjectWorkspaceState` i `ProjectReconciliationEvent` kolone | Ruff/mypy/verify PASS |

## Verifikacija

- `python -m pytest tests/integration/test_sessions_plan_item_api.py tests/integration/test_projects_tasks_api.py::TestProjectsAPI::test_timeline_filters_session_events_by_session_project tests/integration/test_projects_tasks_api.py::TestProjectsAPI::test_project_state_uses_existing_workspace_and_worktree_fields tests/unit/test_evidence.py tests/gui/test_plan_import_flow.py tests/architecture/ -q` → PASS, 18 passed.
- `ruff check src/ tests/ scripts/` → PASS.
- `python -m mypy src --explicit-package-bases` → PASS, 125 source files.
- `python scripts/verify.py` → PASS, 7/7.
- `python -m pytest -q` → PASS, 300 passed, 1 warning (`StarletteDeprecationWarning` iz dependency-ja).

## Šta nije dirano

Nisu implementirani `SessionTaskBinding`, `DecisionItem`, `ImplementationTask`, novi `WorkflowEvent`, Workflow Ledger, novi agent observer sistem, Claude/Codex/Pi/Crush telemetry adapteri, YAML `agent_reports` parser, nova reconciliation arhitektura, managed execution niti novi GUI koncept.

Nije napravljen commit, po nalogu.

## Pronađeni problemi

- PySide6 GUI tipovi imaju dosta dinamičkih `QLayoutItem`/Qt overload rubova. Za baseline je dodata lokalna mypy direktiva na postojeće GUI view fajlove, bez promjene runtime ponašanja.
- `ReconciliationService` je imao isti tip model mismatcha kao `ProjectStateService`: koristio je polja koja model više nema. Minimalno je usklađen sa stvarnim ORM modelima.
- Formatiranje je moralo obuhvatiti i fajlove koje je prethodni rad ostavio neformatirane, jer je to direktno blokiralo `scripts/verify.py`.

## Rizici / ograničenja

GitNexus je promjene označio kao CRITICAL zbog centralnog GUI `_handle_response` helpera. Promjena je aditivna: postojeći Qt Signal tok ostaje, a dodat je callable callback koji koristi import-plan refresh. Pokriveno je GUI regresionim testom.

Nove servisne klase su tanke i ciljane, ali `ProjectTimelineService` i `SystemStateService` treba ostaviti kao read-model servisni sloj, ne širiti ih u novu arhitekturu prije sljedeće faze.

## Potreban follow-up

Sljedeći arhitektonski korak može biti `SessionTaskBinding`, ali tek nakon pregleda ovog diffa i potvrde da je baseline prihvaćen.

## Potrebna korisnička potvrda

Potrebna je korisnička potvrda da je ovaj baseline prihvaćen i da smijemo u sljedećem koraku krenuti na arhitektonsku migraciju. Commit nije napravljen.

## Ljudsko usvajanje rezultata

Preporučeni ljudski review: pregledati diff za `GuiApiClient._handle_response`, `ReconciliationService`, `scripts/verify.py` i nove regresione testove. Ako review potvrdi scope, baseline se može commitovati kao jedna stabilizaciona cjelina.
