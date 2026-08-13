---
flowos_report_version: 1
report_id: fd450bae-6267-4386-aebe-8111dbe4a2b4
agent: crush
model: deepseek-v4-pro
session_id: unknown
report_type: implementation
work_status: completed
tasks:
  - FLOW-1103
commits: []
created_at: 2026-08-13T15:39:20+02:00
---

# FLOW-1103 — supported LIVE launch

## Datum

2026-08-13

## Agent / model / sesija

- Agent: Crush
- Model: deepseek-v4-pro
- Sesija: interaktivna CLI

## CURRENT LIVE PROBLEM

- `_ensure_service_running()` je koristila hardcoded `flowos-service.exe` i
  nije vraćala port.
- `_get_service_port()` je vraćala fallback `9100` ako descriptor ne postoji.
- `create_gui` je pozivao `_ensure_service_running()` pa `_get_service_port()`
  odvojeno — čitajući potencijalno stale port (9100) umesto stvarnog porta
  novo-pokrenutog servisa.
- Greške pri pokretanju su gutane (`except FileNotFoundError: pass`,
  `except Exception: pass`) — LIVE GUI bi se tiho otvorio bez konekcije.

## CANONICAL LIVE COMMAND

```text
flowos-gui --live
```

## SERVICE LAUNCH METHOD

```text
sys.executable -m flowos.service.app
```

Bez `shell=True`. Bez `flowos-service.exe`. Bez platformskog launcher-a.

## PORT AUTHORITY

Runtime descriptor `service.json` je autoritativan izvor porta.

## Novi `ensure_service_running() -> int`

1. Čita descriptor port; ako je `/health` zdrav, vraća taj port (reuse).
2. Inače pokreće servis kroz trenutni Python environment.
3. Čeka da servis upiše descriptor i postane zdrav (bounded 30s).
4. Vraća potvrđeni port iz descriptor-a.
5. Ako servis izađe ili ne postane zdrav → `ServiceStartupError`.

## EXISTING SERVICE REUSE

PASS

## NEW SERVICE START

PASS

## DYNAMIC PORT

PASS (test dokazuje port 9105, ne fallback 9100)

## VISIBLE STARTUP FAILURE

PASS (`ServiceStartupError` sa jasnom porukom)

## MOCK MODE UNCHANGED

PASS (plain `flowos-gui` ne pokreće backend)

## SERVICE SURVIVES NORMAL GUI CLOSE

PASS (nema auto-terminacije servisa pri zatvaranju GUI-ja)

## TARGETED TESTS

`python -m pytest tests/gui/test_live_launch.py -v` → **5 passed**

```
test_existing_healthy_service_reused PASSED
test_new_service_dynamic_port PASSED
test_startup_failure_raises PASSED
test_startup_timeout_raises PASSED
test_mock_mode_does_not_launch_backend PASSED
```

## scripts/verify.py

7/7 PASS

## FILES CHANGED

- `src/flowos/gui/composition_root.py`
- `tests/gui/test_live_launch.py`

## OUT OF SCOPE LEFT UNTOUCHED

- FLOW-1104
- FLOW-1105
- FLOW-1106
- Plan import
- DB/migrations
- Task UI
- Ledger GUI

## Self-check

hardcoded flowos-service.exe dependency remains? NO
new service assumes port 9100? NO
startup failures silently swallowed? NO
actual descriptor port used? YES
healthy existing service reused? YES
plain flowos-gui remains MOCK? YES
normal GUI close kills service? NO
DB repair added? NO
API contract changed? NO
verify.py 7/7? YES

---

READY FOR INDEPENDENT REVIEW
