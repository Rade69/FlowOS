---
flowos_report_version: 1
report_id: b2643ffd-bd91-4eff-ba0c-a38cdf2c3865
agent: crush
model: deepseek-v4-pro
session_id: unknown
report_type: implementation
work_status: completed
tasks:
  - unassigned
commits: []
created_at: 2026-08-12T16:49:58+02:00
---

# Workflow Ledger Phase 3D — Authority Cutover implementacija

## Datum

2026-08-12

## Agent / model / sesija

- Agent: Crush
- Model: deepseek-v4-pro
- Sesija: interaktivna CLI

## Scope

Implementiran authority cutover: `ReportService.set_verdict()` → `TASK_DECISION`
Ledger event. Kreiran `WorkflowDecisionService` kao novi canonical authority za
korisničke workflow odluke.

Nije pravljena migracija. Nije menjan `WorkflowLedgerEvent` schema.
Nije implementiran findings parser ni Markdown body parser.

## Izmenjeni fajlovi

| Fajl | Izmena |
|------|--------|
| `src/flowos/service/services/workflow/decisions.py` | Novi fajl — `WorkflowDecisionService` |
| `src/flowos/service/services/reports/service.py` | `set_verdict()` delegira na `WorkflowDecisionService`; dodat `decision_id` parametar |
| `tests/integration/test_workflow_ledger_phase3d.py` | Novi fajl — 28 testova |
| `tests/unit/test_reports.py` | Dodat import `workflow_ledger_models` |

## TASK_DECISION semantika

`TASK_DECISION` znači: korisnik je doneo workflow odluku o dokazivo povezanom
work targetu. NE znači: REVIEW_COMPLETED, USER_VALIDATION, FINDING_DECIDED.

Nakon Phase 3D, `WorkflowLedgerEvent(TASK_DECISION)` je canonical history
korisničkih odluka. `AgentReport.user_verdict` i `verdict_audit_json` ostaju
compatibility projection.

## decision_id contract

- Caller može proslediti `decision_id` UUID — koristi se TAČNO taj ID
- Ako nije prosleđen — generiše se novi `uuid.uuid4()`
- Retry sa istim `decision_id` + isti verdict/notes → no-op (idempotent)
- Isti `decision_id` + drugačiji verdict → `ValueError` (conflict)

## Idempotency

Key format: `workflow-ledger:v1:TASK_DECISION:user_decision:{decision_id}:{target_kind}:{target_id}`

DB `UNIQUE(idempotency_key)` constraint štiti od duplikata.

## Source identity

- `source_kind = "user_decision"`
- `source_id = decision_id`

Report je context reference, ne source identity.

## Target grouping

Koristi isti `_build_target_groups()` kao Phase 3A/3C. Legacy fallback: tačno
1 `SessionTaskBinding` bez `AgentReportBindingLink`-ova.

## Verdict semantics

### ACCEPTED
- TASK_DECISION decision=ACCEPTED
- Compatibility projection update
- NE menja PlanItem status

### NEEDS_WORK
- TASK_DECISION decision=NEEDS_WORK
- IMPLEMENTED → IN_PROGRESS
- VERIFIED → IN_PROGRESS
- Za sve dokazive historical PlanItem targete

### REJECTED
- TASK_DECISION decision=REJECTED
- IMPLEMENTED → IN_PROGRESS
- VERIFIED → IN_PROGRESS
- Isti consequence kao NEEDS_WORK

## Unassigned

Report bez dokazivog targeta → compatibility projection update, 0 TASK_DECISION,
0 PlanItem mutacije.

## Compatibility projection

U okviru iste decision operacije: `user_verdict`, `user_notes`, `status=FINAL`,
`updated_at`, `verdict_audit_json` append.

## Transaction atomicity

Sve je u jednoj DB transakciji. Ako bilo koji consequence padne → rollback svega
(eventi, projection, audit, PlanItem reopen).

## Testovi (28)

## Coverage matrica

| Contract requirement | Test name | PASS |
|----------------------|-----------|------|
| ACCEPTED → TASK_DECISION | test_accepted_creates_task_decision | PASS |
| NEEDS_WORK IMPLEMENTED | test_needs_work_reopens_implemented | PASS |
| NEEDS_WORK VERIFIED | test_needs_work_reopens_verified | PASS |
| REJECTED IMPLEMENTED | test_rejected_reopens_implemented | PASS |
| REJECTED VERIFIED | test_rejected_reopens_verified | PASS |
| multi-target | test_two_targets_produce_two_events | PASS |
| A-B-A | test_aba_produces_one_event_per_logical_target | PASS |
| historical drift | test_historical_plan_item_drift | PASS |
| multiple snapshots | test_multiple_snapshots_null_plan_item_id | PASS |
| unassigned | test_unassigned_updates_compatibility_no_ledger_event | PASS |
| repeated decisions | test_needs_work_then_accepted_keeps_both | PASS |
| retry same decision_id | test_same_decision_id_retry_no_duplicate | PASS |
| conflict verdict | test_same_decision_id_different_verdict_raises | PASS |
| conflict notes | test_conflict_notes | PASS |
| conflict report | test_conflict_report | PASS |
| cross-project corruption | test_cross_project_corruption_zero_events | PASS |
| consequence rollback | test_consequence_failure_rollback | PASS |
| multi-target rollback | test_multi_target_partial_failure_rollback | PASS |
| legacy single binding | test_single_binding_legacy_creates_task_decision | PASS |
| legacy ambiguous binding | test_ambiguous_legacy_zero_events | PASS |
| no USER_VALIDATION | test_no_finding_decided_no_user_validation | PASS |
| no FINDING_DECIDED | test_no_finding_decided_no_user_validation | PASS |
| ACCEPTED no DONE/VERIFIED | test_accepted_no_done_no_verified | PASS |

## Regresije

| Test skup | Rezultat |
|-----------|----------|
| Phase 3A | 17 passed |
| Phase 3B | 19 passed |
| Phase 3C | 22 passed |
| AgentReport Ingestion | 26 passed |
| AgentReport v2 | 12 passed |
| Unit test_reports | 6 passed |
| **Ukupno regresije** | **102 passed** |

## verify.py

7/7 PASS

## Explicit non-goals

- Nije implementiran FINDING_DECIDED
- Nije implementiran FIX_COMPLETED
- Nije implementiran VERIFICATION_COMPLETED
- Nije implementiran USER_VALIDATION
- Nije pravljena migracija
- Nije menjan `WorkflowLedgerEvent` schema
- `ReportService.set_verdict()` signature je backward-kompatibilno proširen opcionim `decision_id` parametrom; postojeći pozivi bez `decision_id` ostaju kompatibilni.
- Nije implementiran findings parser
- Nije parsiran Markdown body

## Self-check

H1 — CLOSED
M2 — CLOSED
M5 — CLOSED

Phase 3D = 28 passed
Relevant regressions = 102 passed
scripts/verify.py = 7/7 PASS

Odstupanja od prompta: NONE

---

READY FOR FINAL CHECK
