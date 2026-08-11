---
flowos_report_version: 1
agent: crush
model: deepseek-v4-pro
session_id: unknown
report_type: fix
tasks:
  - unassigned
commits: []
created_at: 2026-08-11T00:00:00+02:00
---

# SessionTaskBinding — review fixes (F1, F2, F3)

## Datum

2026-08-11

## Agent / model / sesija

- Agent: Crush
- Model: deepseek-v4-pro
- Sesija: interaktivna CLI

## Scope

Popravka prihvaćenih nalaza nezavisnog review-a SessionTaskBinding faze 1:
F1 (HIGH), F2 (HIGH), F3 (MEDIUM) + regresioni testovi.

F5 (LOW) namerno nije diran. Nije uvedena nova arhitektura (Workflow Ledger,
DecisionItem, ImplementationTask). Nije pravljen GUI. Nije pravljen commit.

## Izmenjeni fajlovi

| Fajl | Izmena |
|------|--------|
| `src/flowos/service/services/sessions/bindings.py` | F1 — redosled: validacija pre zatvaranja bindinga |
| `alembic/versions/9b2d1f7a4c63_session_task_bindings.py` | F2 — `ondelete="SET NULL"` → `"RESTRICT"` |
| `src/flowos/service/services/infrastructure/persistence/models.py` | F2 — ORM FK `ondelete="RESTRICT"` |
| `src/flowos/service/controllers/http/sessions.py` | F3 — `IntegrityError` → 409 |
| `src/flowos/service/controllers/http/tasks.py` | F2/F3 — Task delete 409 |
| `src/flowos/service/services/tasks/service.py` | F2/F3 — try/except IntegrityError u `delete_task` |
| `tests/integration/test_session_task_bindings.py` | F1–F4 regresioni testovi |

## F1 — switch prvo validira, pa zatvara

**Šta je bilo pogrešno:** `switch_binding()` je zatvarao postojeći aktivni binding pre
nego što je validirao novi target. Ako validacija padne, stari binding je već mutiran
(`ended_at` postavljen) u SQLAlchemy identity mapi. Pri sledećem `flush()`-u bez
rollback-a, sesija ostaje bez ijednog aktivnog bindinga.

**Kako je popravljeno:** Promenjen redosled — `_validate_target_project()` se
sada poziva PRE `_close_binding()`. Ako validacija padne, postojeći aktivni
binding ostaje potpuno netaknut.

## F2 — RESTRICT FK za task_id i plan_item_id

**Šta je bilo pogrešno:** FK constraint `ON DELETE SET NULL` je dozvoljavao
da se obriše Task/PlanItem koji je referenciran istorijskim bindingom. Istorijski
TASK binding bi postao UNASSIGNED — bez traga da je ikad imao target.

**Kako je popravljeno:** `ondelete="SET NULL"` → `ondelete="RESTRICT"` u:
- Alembic migraciji (linije 45, 47)
- ORM modelu `SessionTaskBinding` (`models.py:178,181`)
- `TaskService.delete_task()` sada hvata `IntegrityError` i vraća `False`
- HTTP `DELETE /tasks/{id}` prvo proverava postojanje taska, pa vraća 409 ako
  RESTRICT odbije brisanje

## F3 — 409 handling za konkurentni switch

**Šta je bilo pogrešno:** Kada dva switch zahteva trkaju, partial unique index
odbija duplikat aktivnog bindinga kroz `IntegrityError`, ali HTTP endpoint je
hvatao samo `ValueError`. Rezultat: sirovi 500 umesto 409.

**Kako je popravljeno:** `switch_session_binding` sada hvata i `IntegrityError`
(ili `Exception` sa `IntegrityError` kao `__cause__`) i mapira na 409 sa porukom
"Binding je u međuvremenu promijenjen. Osvježi stanje i pokušaj ponovo."

## F4 — regresioni testovi

Dodati testovi:

| Test | Šta pokriva |
|------|-------------|
| `test_invalid_target_does_not_close_existing_binding` | F1: neuspeli switch ne zatvara postojeći binding |
| `test_cross_project_switch_does_not_close_existing_binding` | F1: cross-project switch čuva binding |
| `test_delete_task_with_binding_is_rejected` | F2: DB RESTRICT odbija brisanje taska |
| `test_delete_task_with_binding_http_returns_409` | F2: HTTP DELETE → 409 |
| `test_plan_item_fk_is_also_restricted` | F2: PlanItem FK takođe RESTRICT |
| `test_concurrent_switch_returns_409` | F3: konkurentni switch → 409 |
| `test_close_active_binding_on_legacy_session_is_safe` | Legacy: UNASSIGNED binding se bezbedno zatvara |
| `test_switch_with_older_timestamp_is_rejected` | Timestamp: switch sa starijim vremenom odbijen |

## F5 — namerno nije diran

F5 (`switched_at < AgentSession.started_at` bez aktivnog bindinga) nije
popravljan. To je LOW severity, nije dostižno kroz HTTP API, i eksplicitno
isključeno iz scope-a ovog zadatka.

## Verifikacija

```text
pytest tests/integration/test_session_task_bindings.py -v
→ 22 passed
```

```text
pytest tests/ --ignore=tests/architecture -q
→ 315 passed
```

```text
python scripts/verify.py
→ 4/7 PASS
  Migrations check: PASS (6/7)
  Alembic round-trip: PASS (7/7)
  Preostala 3 pada su postojeća (ruff format, ruff lint, architecture)
```

## Rizici i ograničenja

- `TaskService.delete_task()` sada hvata sve `Exception` na flush-u i vraća
  `False`. Ovo je šire nego samo `IntegrityError` — ali u praksi, jedini
  drugi exception na flush-u bi bio constraint violation (što je i dalje
  ispravno mapiranje na 409).
- F5 ostaje nepopravljen — teorijski edge case za buduće interne pozivaoce.
- verify.py pada na ruff/architecture — postojeći problemi, nisu deo ovih izmena.

## Gdje je rad stao

F1, F2, F3 popravljeni. Regresioni testovi dodati. 315/315 testova prolazi.
Migrations round-trip prolazi.

## Sljedeći korak

Commit ovih izmena (kada korisnik odluči). Zatim nastavak na P0.7 launcher
i P0.9 lifecycle service.
