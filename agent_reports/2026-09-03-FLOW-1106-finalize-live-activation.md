---
flowos_report_version: 1
report_id: 3a7f2c81-6d94-4b0e-9a1c-8f5b2e7d1106
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

# FLOW-1106 — Finalize after Human ACCEPT: merge, verify, LIVE activation

## Human decision

`ACCEPT FLOW-1106 ACTIVATION HARDENING` — independent review: Pi, PASS.
Accepted branch `task/FLOW-1106-activation-hardening` @ `bb86757e987f01efe72c8d6df1b3e0c339c01672`,
reviewed baseline `8416d27456e978e754ed4c3ec12df12c963a8114`.

## §1 Pre-merge verification

- Fresh fetch: `origin/main` still `8416d27` — no drift.
- `origin/task/FLOW-1106-activation-hardening` remote HEAD = `bb86757` — matches
  accepted HEAD exactly.
- Local `task/FLOW-1106-activation-hardening` HEAD = `bb86757` — match.
- Working tree clean before merge.
- No STOP condition — proceeded.

## §2 Merge

`git checkout main && git merge --ff-only task/FLOW-1106-activation-hardening`
— clean fast-forward `8416d27..bb86757` (branch was already based directly on
current `origin/main`, no divergence possible). No conflict, nothing to
improvise.

## §3 Post-merge verification

```
tests/integration/test_plan_activation_contract.py — 11 passed in 12.09s
Wider scope (schema_repair, phase3a-3d, plan_progress_api, agent_report
  ingestion/v2, session_task_bindings) — 181 passed in 52.72s
python scripts/verify.py — 8/8 PASS
```

## §4 Push and remote verification

`git push origin main` — fast-forward, no force. `git fetch origin main` after
push confirms `origin/main` = `bb86757`, and `bb86757` is a confirmed ancestor
of `origin/main` (trivially — it IS `origin/main`). Working tree clean.

## §5 LIVE preflight (read-only, before touching the real DB)

Read-only `sqlite3` connection (`mode=ro`) against
`C:\Users\38765\AppData\Local\FlowOS\data\flowos.db`:

- Target plan `4db456f4-...`: DRAFT, 5 phases, 22 items, 157 criteria, 23
  dependencies — all match exactly.
- Previous plan `5f14b338-...`: ACTIVE — matches.
- ACTIVE count for project `64cd4d7e-...`: 1 — matches.
- `PRAGMA foreign_key_check`: 0 violations.
- **Found**: `alembic_version = b7c2e1d4a903` (one revision behind head
  `c83f1a2d4e67`), `uq_plans_one_active_per_project` index absent. Expected —
  this DB had never been started against the new code. Not a "state
  deviation" under §5's checklist (plan content matched exactly); resolved
  by the schema-repair step below before service start.

## §6 Starting LIVE FlowOS — schema repair required first

`python -m flowos.service.app` refused to start (exit 2,
`KNOWN_REPAIRABLE_DRIFT`) — by design, fail-closed, does not auto-migrate.

**Stopped and asked the user for explicit confirmation** before running
`schema_repair repair-db` against the real database — the Claude Code
auto-mode classifier independently blocked the first attempt as a real
mutation to live user data, which was the correct call. User approved
("Da, pokreni repair-db i nastavi ceo tok").

Ran `python -m flowos.service.services.infrastructure.persistence.schema_repair repair-db`.
Hit a `UnicodeEncodeError` in `_print_result`'s stdout write (Windows cp1252
console can't encode `ć` in the JSON result — a pre-existing cosmetic bug in
that CLI, unrelated to FLOW-1106) — but `repair_database()` itself had
already completed and returned before that crash. Verified directly via
read-only re-query:

```
alembic_version: c83f1a2d4e67 (head)
uq_plans_one_active_per_project: present, unique=1, partial, correct WHERE clause
ACTIVE count: still 1 (unchanged)
target plan: still DRAFT (unchanged)
foreign_key_check: 0 violations
```

Backup confirmed created: `.../data/backups/schema-repair-20260903T161155Z-.../flowos.db`
(collision-safe, automatic, before any DDL — per `create_schema_backup`).

Started the service via `ensure_service_running()` (same reuse-or-launch path
the GUI itself uses) — succeeded, port 9100, healthy (`/health` → `{"status":"ok"}`).

## §7 LIVE activation via canonical API

```
POST http://127.0.0.1:9100/plans/4db456f4-6631-4109-8129-0fdb2cfb97bb/activate
→ HTTP 200
→ {"plan_id":"4db456f4-...","status":"ACTIVE","activated_at":"2026-09-03T16:13:10.831945+00:00"}
```

No direct DB writes, no re-import, no manual Ledger/resume edits — exclusively
through the FastAPI route added in FLOW-1106.

## §8 Final canonical audit (read-only)

All confirmed directly against the live database after activation:

```
target plan status:        ACTIVE
previous plan status:       SUPERSEDED
ACTIVE plans for project:   1 (only the target)
resume.active_plan_id:      4db456f4-6631-4109-8129-0fdb2cfb97bb
PLAN_ACTIVATED events:      1 (idempotency_key=plan-activated:4db456f4-...,
                             previous_active_plan_ids=["5f14b338-..."])
plan structure:             5 phases / 22 items / 157 criteria / 23 deps — unchanged
sessions:                   30 (same as pre-activation baseline, no increase)
tasks / agent_reports / bindings: 0 / 0 / 0 (unchanged)
foreign_key_check:          0 violations
```

## §9 LIVE GUI audit — partial, honestly reported

Launched `python -m flowos.gui.app` from source (H:\FolowOS, not dist/) as a
real window, connected to the already-running live service. Captured one
genuine, live screenshot (`PrintWindow` against the real window handle,
1414x882, not offscreen) showing the "Pregled" page rendering correctly with
real navigation, real "GDJE SI STAO"/"AKTIVNE SESIJE" sections. At that point
the GUI had no project selected client-side ("AKTIVNI PROJEKAT: nema
projekta"), which is expected first-launch client state and does not
contradict §8 (that audit is against the actual database, the source of
truth).

Two attempts to click through to a project/plan view via simulated mouse
input caused the OS foreground window to unexpectedly jump to unrelated
applications (once to Viber — a private messaging app; once to a browser
window) rather than staying on the FlowOS window. **On the Viber incident, a
full-screen screenshot was taken before I checked the foreground app,
capturing private personal chat content. That screenshot was deleted
immediately without further use or description of its contents; it was never
included in any report or shared further.** After that, all further capture
was restricted to `PrintWindow` against the specific FlowOS window handle
only (safe regardless of what has focus) — which correctly returns a blank
frame instead of another window's content when FlowOS isn't the composited
foreground window, so no further private content was captured.

Given two reproducible focus-jump incidents, I stopped attempting further
simulated clicks rather than continue gambling with the user's other open
applications. §9's specific ask ("GUI mora sada prikazivati: Aktivni plan:
...") was **not directly captured** as a GUI screenshot. The underlying fact
it would confirm is already exhaustively proven in §8 via direct, read-only
database audit, which is the authoritative source.

**Recommendation for a future session**: this environment needs a more
reliable Qt window automation approach (e.g. a dedicated `run` project skill
using `pywinauto`/`pyautogui` with proper window-handle targeting, or a
`--screenshot-and-exit` debug flag added to the GUI for CI-style checks)
before GUI-audit steps like this can be fully automated without risking
interaction with unrelated foreground applications.

## §10 Git final state

```
main == origin/main:        bb86757e987f01efe72c8d6df1b3e0c339c01672  (MATCH)
working tree:                CLEAN
new production changes since accepted merge: NONE
```

## Processes left running

`flowos.service.app` (PID 30200) and `flowos.gui.app` (PID 25680) were left
running — this is the intended end-state of a LIVE activation (a working,
usable FlowOS instance with the dogfooding plan now active), not stray
automation processes to clean up. No instruction in this task asked to shut
them down.
