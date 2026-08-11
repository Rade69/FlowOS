---
flowos_report_version: 1
agent: codex
model: gpt-5
session_id: unknown
report_type: fix
work_status: completed
tasks:
  - unassigned
commits: []
created_at: 2026-08-11T13:43:38.5449156+02:00
---

# AgentReport v2 — Phase 1 — review popravke

## Scope

Ovaj report dokumentuje samo popravke obaveznih F1–F5 nalaza iz nezavisnog review-a. Nije napravljen commit.

## F1 — historijski PlanItem snapshot

`AgentReportBindingLink` sada ima nullable `resolved_plan_item_id`, FK na `plan_items.id` sa `ON DELETE RESTRICT`.

Vrijednost je snapshot deterministički razriješenog PlanItem-a pri `link_report_to_binding()` pozivu:

- direktni `binding.plan_item_id` se kopira;
- za `binding.task_id` snapshotuje se tadašnji `Task.plan_item_id`;
- UNASSIGNED ili Task bez PlanItem-a ostavlja `NULL`.

Eksplicitno linkovani reporti pri verdictu koriste samo `resolved_plan_item_id`; više se ne čita živi `Task.plan_item_id`. Time kasnija promjena Task targeta ne može preusmjeriti stari report na pogrešan PlanItem.

Dodani test mijenja `Task.plan_item_id` sa A na B kroz stvarni `TaskService.update_task()` nakon linkovanja. `NEEDS_WORK` vraća A u `IN_PROGRESS`, a B ostaje `IMPLEMENTED`.

## F2 — zatvorena javna state machine

Globalna `ALLOWED_TRANSITIONS` matrica je vraćena na strogo stanje: generički pozivaoci ne mogu `IMPLEMENTED/VERIFIED → IN_PROGRESS`.

`PlanProgressService.validate_transition()` ima keyword-only `allow_verdict_reopen=False`. On dopušta isključivo ta dva reopen prelaza kada je eksplicitno `True`; ne otvara druge nedozvoljene prelaze. Samo `ReportService._reopen_plan_item()` ga koristi. Centralni audit, timestamp, WebSocket i refresh tok ostaju u istom `PlanProgressService` putu.

Dodani su testovi da običan servisni poziv i HTTP `POST /plan-items/{id}/start` vraćaju zabranu/409 za `IMPLEMENTED` i `VERIFIED`, dok report-verdict tok uspješno reopenuje oba statusa uz valjan link.

## F5 — DB integritet `work_status`

`AgentReport` metadata i Alembic migracija sada sadrže CHECK:

```sql
work_status IS NULL OR work_status IN ('completed', 'partial', 'blocked')
```

`report_type` nema CHECK constraint, jer njegova taksonomija nije zaključana. Aplikativna `ReportService` validacija ostaje aktivna. Test direktnim ORM insertom potvrđuje da DB odbija nevažeći `work_status` i kada se servis zaobiđe.

## Legacy ponašanje i ograničenja

Legacy report bez linka koristi fallback samo kada sesija ima tačno jedan relevantni binding sa direktnim `plan_item_id`.

Legacy TASK binding nema snapshot `resolved_plan_item_id`; za njega se ne radi živi lookup mutabilnog `Task.plan_item_id`, nego fail-safe warning i bez reopenovanja. Time legacy fallback nije predstavljen kao historijska garancija koju nema.

`link_report_to_binding()` i dalje nije ožičen u produkcioni tok, što je namjerno Phase-1 ograničenje: fail-safe je bolji od pogrešne atribucije.

## Timestamp ranijeg reporta

Prethodni `agent_reports/2026-08-11_agent-report-v2-phase-1.md` ima `created_at: 2026-08-11T00:00:00+02:00`. Taj ponoćni placeholder je nepouzdan metadata zapis i ne smije se koristiti kao autoritativno vrijeme događaja. Ovaj report koristi stvarno vrijeme pisanja iz lokalnog sistema.

## Verifikacija

- `python -m pytest tests/integration/test_agent_report_v2.py tests/unit/test_reports.py tests/unit/test_plan_progress.py tests/integration/test_plan_progress_api.py -v --tb=short` → PASS, 70 passed, 1 dependency warning.
- `python scripts/verify.py` → PASS, 7/7; širi suite 331 passed, 1 dependency warning.
- Alembic upgrade na praznoj SQLite bazi → PASS.
- Alembic upgrade/downgrade/upgrade round-trip → PASS.

## Namjerno van scope-a

Workflow Ledger, YAML/Markdown ingestion, watcher, hash/dedupe, report-binding HTTP endpoint, `SessionCompletionService` ožičavanje i `EvidenceService` migracija nisu implementirani.

## Commitovi

Nema. Rad je ostavljen necommitovan prema nalogu.

## Verdict

READY FOR RE-REVIEW
