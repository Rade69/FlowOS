---
task_id: FLOW-1105
title: Tipizovani Plan Import API contract
phase: foundation
risk: MEDIUM
coordinator: ChatGPT
implementer: Pi
reviewers:
  - independent reviewer TBD
status: IMPLEMENTING
created_at: 2026-09-03
dependencies:
  - FLOW-1110
gitnexus_required: true
adversarial_required: true
baseline_sha: 5de0ee0f3f405fa3ca4081ed1bdb9e81ffd4c1fe
branch: task/FLOW-1105-plan-import-contract
worktree: ../FlowOS-worktrees/FLOW-1105-plan-import-contract
allowed_paths:
  - src/flowos/service/controllers/http/plan_progress.py
  - tests/integration/test_plan_progress_api.py
  - agent_reports/FLOW-1105-task-contract.md
  - agent_reports/2026-09-03-FLOW-1105-pi.md
forbidden_paths:
  - GUI implementation files
  - database models
  - migrations
  - parser/import business logic
  - unrelated services
  - worktree/session/evidence subsystems
---

# FLOW-1105 — Task Contract

## Objective

Ojačati HTTP request contract `/projects/{project_id}/import-plan` tako da endpoint
više ne prima raw `dict`, nego eksplicitni Pydantic request model. Task NE uvodi novu
funkcionalnost i NE mijenja business semantics Plan Importa.

## Why now

Plan Import endpoint trenutno ručno izvlači `markdown_text` iz raw `dict` i time
gubi transportnu validaciju (missing field i pogrešan tip prolaze do ručnog koda).
Shared contracts modul već definiše `PlanImportRequest` model, ali endpoint ga ne
koristi. Tipizacija boundary-ja uklanja tu neusklađenost.

## Potvrđene pre-change facts

- **Stvarni endpoint:** `POST /projects/{project_id}/import-plan` u
  `src/flowos/service/controllers/http/plan_progress.py:179`.
- **Stara endpoint signature:** `def import_plan(project_id: str, body: dict, session=Depends(get_session))`.
- **Stari extraction:** `markdown = body.get("markdown_text", "")` + ručni
  `if not markdown.strip(): raise HTTPException(400, ...)`.
- **Service poziv (nepromijenjen):** `PlanProgressService(session).import_plan(project_id, markdown)`
  — ne prosljeđuje `source_artifact_id`.
- **Postojeći request model:** `PlanImportRequest` u
  `src/flowos/shared/contracts/plan_progress.py:150`:
  `markdown_text: str`, `source_artifact_id: str | None = None`.
- **GUI payload (P3):** `src/flowos/gui/services/client.py:113` šalje
  `{"markdown_text": markdown_text}`. Docstring navodi "canonical PlanImportRequest polje".
- **Postojeći endpoint/API testovi:** `tests/integration/test_plan_progress_api.py`
  (`TestPlanImportApi`), uključujući valid import (200), prazan `markdown_text` (400),
  activate.
- **Response contract (nepromijenjen):** `{plan_id, phases, items, criteria,
  dependencies, unclear_count, unclear_sections}` (vidi
  `PlanProgressService.import_plan` u `src/flowos/service/services/plan_progress.py:406`).

Pretpostavke P1–P4 su potvrđene read-only preflightom (`rg` + čitanje fajlova).

## GitNexus evidence

GITNEXUS_PRE = UNKNOWN. MCP alati nisu dostupni u pi okruženju ovog worktree-ja,
a sibling worktree/index binding daje nepouzdane rezultate. Ručna kompenzacija
(`rg`/`git grep`) urađena umjesto toga:

- `import-plan` endpoint definisan samo u `src/flowos/service/controllers/http/plan_progress.py`.
- Pozivaoci rute: GUI `client.py` (`import_plan`) i integracijski testovi
  `test_plan_progress_api.py`. Nema drugih HTTP callers.
- `markdown_text` referenciran u GUI client-u, controlleru, shared contracts modelu
  i testovima — bez neočekivanih potrošača.
- `PlanImportRequest` trenutno nije nigdje instanciran (samo definicija).

Blast radius: jedan endpoint + jedan pozivalac (GUI client, payload već kompatibilan)
+ postojeći test modul. Rizik MEDIUM zbog javnog API contracta, ne zbog širine.

## Exact allowed/forbidden scope

Allowed:
- `src/flowos/service/controllers/http/plan_progress.py` — samo `import_plan` endpoint
  i import `PlanImportRequest`.
- `tests/integration/test_plan_progress_api.py` — dodati contract testove T1–T4.
- `agent_reports/FLOW-1105-task-contract.md`
- `agent_reports/2026-09-03-FLOW-1105-pi.md`

Forbidden (nepromijenjeno): GUI, DB modeli, migracije, parser/import business logic,
drugi services, worktree/session/evidence, README, planovi, AGENTS.md, CLAUDE.md.

## Acceptance criteria

1. Endpoint koristi `PlanImportRequest` umjesto `body: dict`.
2. Missing `markdown_text` → HTTP 422 na FastAPI/Pydantic boundary-ju; downstream
   (import service/parser) se ne izvršava.
3. Pogrešan tip `markdown_text` → HTTP 422.
4. Valid request i response ostaju identični (route URL, method, response body).
5. Prazan `markdown_text` (`""`) i dalje → HTTP 400 (business pravilo, NIJE
   transportna validacija).
6. `source_artifact_id` se NE prosljeđuje u service (zadržano postojeće ponašanje).
7. Adversarial proof: mutacija nazad na raw-dict mora oboriti T2; typed mora PASS.

## Verification

- `python -m pytest tests/integration/test_plan_progress_api.py -q` (targeted).
- `python -m ruff check src/flowos/service/controllers/http/plan_progress.py tests/integration/test_plan_progress_api.py`
- `python -m ruff format --check ...`
- `python scripts/guard_architecture.py`
- `python scripts/verify.py` (full gate).

## Adversarial strategy

T2 (`{}` → 422, downstream ne pozvan) je boundary dokaz. Privremeno vratiti endpoint
na raw-dict semantiku, pokrenuti T2 (mora FAIL — raw dict vraća 400 jer default-uje
`markdown_text` na `""`), zatim vratiti typed implementaciju i ponovo pokrenuti T2
(mora PASS). Mutacija se NE commit-uje.

## Rollback

Vratiti `src/flowos/service/controllers/http/plan_progress.py` na baseline verziju
(`body: dict`) i ukloniti dodane testove. Bez DB/schema promjena.

## Stop conditions

- origin/main nije `5de0ee0f3f405fa3ca4081ed1bdb9e81ffd4c1fe`.
- Endpoint više ne koristi raw dict (task assumption nevalidna).
- GUI ne šalje `markdown_text`.
- Tipizovani request već postoji u endpointu.
- Zahtijeva promjenu GUI/parser/service/DB/response contracta.
- T2 ne dokazuje 422 boundary ili adversarial mutacija ne obara T2.
- Changed file izađe iz allowed_paths.
- Full verify ne prolazi.
- Push bi zahtijevao force.
