---
flowos_report_version: 1
report_id: 12e1af64-5ff9-406d-94f9-5857b6e628fc
agent: codex
model: gpt-5
session_id: unknown
report_type: fix
work_status: completed
tasks:
  - unassigned
commits: []
created_at: 2026-08-11T17:10:54+02:00
---

# AgentReport v2 - Phase 2 review fixes

## Scope

Popravljeni su samo nalazi iz formalnog independent review-a za AgentReport v2 Phase 2 ingestion. Nije pravljen commit. Nije mijenjana arhitektura ingestiona, nije dodat novi dedupe sistem, nije diran Workflow Ledger, SessionCompletionService, EvidenceService, AGENTS.md ni CLAUDE.md.

## F1 - source_path race

Race je zatvoren DB-level zastitom: `AgentReport.source_path` sada ima UNIQUE index u ORM metadata i u postojeceoj necommitovanoj migraciji `4f2c9a7b8d11_agent_report_source_identity.py`.

Izabran je obicni UNIQUE index, jer trenutna SQLite semantika dozvoljava vise `NULL` vrijednosti u UNIQUE indexu. Time legacy i session-completion reportovi sa `source_path = NULL` i dalje mogu postojati u vise redova, dok non-null Markdown artifact path moze pripadati samo jednom source reportu.

Postojeca aplikativna `_check_identity()` provjera je zadrzana kao prva linija odbrane. DB constraint je zadnja zastita od TOCTOU race-a.

## Graceful concurrency rezultat

`AgentReportIngestionService` sada usko hvata samo `IntegrityError` koji dolazi iz source identity UNIQUE sudara nad:

- `agent_reports.source_report_id`
- `agent_reports.source_path`
- pripadajucim index imenima

Takav sudar se vraca kao `IMMUTABLE_CONFLICT`. Ostali `IntegrityError` slucajevi se ne gutaju i nastavljaju da se propagiraju.

## Concurrency regression test

Dodat je stvarni regression test sa dvije odvojene SQLAlchemy sesije/transakcije:

- T1 i T2 oba izvrse identity pre-check dok je isti `source_path` slobodan
- T1 zatim upise prvi report
- T2 pokusa upisati drugi `source_report_id` na isti `source_path`
- DB UNIQUE constraint odbija T2
- konacno postoji tacno jedan `AgentReport` red za taj `source_path`

Dodat je i test da ingestion boundary stvarni source_path UNIQUE violation pretvara u `IMMUTABLE_CONFLICT`, bez drugog DB reda.

## YAML injection regression test

Dodat je test za unsafe PyYAML tag payload:

```yaml
agent: !!python/object/apply:os.system ["echo SHOULD_NOT_RUN"]
```

Parser/Ingestion rezultat je `INVALID`, `os.system` nije pozvan i ne nastaje `AgentReport` DB red.

## Ostalo Phase 2 ponašanje

Nije mijenjano prihvaceno ponasanje:

- `source_report_id` ostaje unique identity
- isti ID/path/hash ostaje `ALREADY_INGESTED`
- isti ID/path/drugi hash ostaje `IMMUTABLE_CONFLICT`
- isti ID/drugi path ostaje `IMMUTABLE_CONFLICT`
- drugi ID/isti path ostaje `IMMUTABLE_CONFLICT`
- `session_id: unknown` ostaje `NEEDS_LINK` bez DB reporta
- exact binding resolution ostaje bez fuzzy/current-pointer fallbacka
- `tasks: [unassigned]` ostaje session-scoped report bez binding linkova
- startup scan i postojeci watcher hook ostaju isti
- `FileActivity` se i dalje commit-a prije ingestion pokusaja
- immutable report se ne prepisuje

## Verifikacija

Pokrenuto:

```text
python -m pytest tests/unit/test_agent_report_front_matter.py tests/integration/test_agent_report_ingestion.py -v --tb=short
```

Rezultat:

```text
39 passed
```

Pokrenuto:

```text
python -m pytest tests/integration/test_agent_report_v2.py tests/unit/test_reports.py tests/integration/test_session_task_bindings.py tests/integration/test_watcher_activity.py tests/unit/test_session_completion.py -q
```

Rezultat:

```text
51 passed, 1 warning
```

Pokrenuto:

```text
python scripts/verify.py
```

Rezultat:

```text
PASS 7/7
370 passed, 1 warning
Ruff format PASS
Ruff lint PASS
mypy PASS
architecture boundaries PASS
migrations check PASS
Alembic round-trip PASS
```

## Van scope-a

Namjerno nije implementirano:

- Workflow Ledger
- Verification Ledger
- novi watcher
- novi dedupe subsystem
- pending/report tabela
- HTTP ingestion endpoint
- SessionCompletionService wiring
- EvidenceService rewrite
- LLM parsing
- fuzzy matching
- custom report folder konfiguracija
- managed worktree watcher redesign

READY FOR RE-REVIEW
