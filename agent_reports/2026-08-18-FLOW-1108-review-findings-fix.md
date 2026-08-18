---
flowos_report_version: 1
report_id: ddb9ecca-ee4b-47ca-a209-5ef9cab95c7e
agent: crush
model: deepseek-v4-pro
session_id: unknown
report_type: implementation
work_status: completed
tasks:
  - FLOW-1108
commits: []
created_at: 2026-08-18T15:39:46+02:00
---

# FLOW-1108 — Zaštita lokalnih FlowOS podataka

Datum: 2026-08-18
Agent: crush / deepseek-v4-pro
Baseline: d059ffc8ed4c9e0367776ee1f50a24bf1850b95a

## REV-1108-H1: CLOSED

Zatvoren jedan materijalni acceptance nalaz iz nezavisnog adversarial review-a
(`agent_reports/2026-08-14-FLOW-1108-independent-security-review.md`, §19/§24).
Prethodno prihvaćeni FLOW-1108 mehanizam ACL hardening-a NIJE redizajniran —
samo je zatvoren maskirani-failure put u `_run_icacls()`.

## ROOT CAUSE

`dir_security.py::_run_icacls()` je provjeravao ISKLJUČIVO `result.returncode != 0`.
Međutim `icacls` sa `/C` (continue-on-error) vraća exit code 0 ČAK I KAD je 100%
ciljanih objekata neuspješno obrađeno — stvarni neuspjeh se prijavljuje isključivo
tekstualno u `stdout` kao `Failed processing N files`. Posljedica: `ensure_private_directory`
i `harden_existing_directory` su mogli tiho "uspjeti" bez ijedne stvarne ACL izmjene,
što je narušavalo fail-closed garanciju za runtime bearer token i sve ostale
zaštićene direktorijume.

## FIX

U `_run_icacls()`, uz postojeću `returncode != 0` provjeru, dodat parsiranje
numeričkog processing-summary signala:

```python
_FAILED_PROCESSING_RE = re.compile(r"Failed processing (\d+) files")

failed_match = _FAILED_PROCESSING_RE.search(result.stdout)
if failed_match and int(failed_match.group(1)) > 0:
    raise DirectoryHardeningError(...)
```

Bilo koji `N > 0` → hard failure, NEZAVISNO od exit code-a. Parsira se SAMO numerički
signal, bez oslanjanja na lokalizovane deskriptivne poruke ("Access is denied",
"The system cannot find the path specified").

## ICACLS /C STRATEGY

Odabrana Opcija A (najmanja sigurna korekcija): `/C` ostaje na OBA poziva
(`dir_cmd` single-target i `children_cmd` traversal), a `_run_icacls()` sada
detektuje `Failed processing N files` za `N > 0`. Nije mijenjana struktura komandi.

## Validacioni nalazi

MASKED FAILURE DETECTION: PASS
RUNTIME TOKEN FAIL-CLOSED: PASS
BACKUP FAIL-CLOSED: PASS
REAL WINDOWS FAIL-CLOSED PROBE: PASS

Stvarna Windows proba (TEMP direktorijum, nepostojeći path, čistićenje izvršeno):

```text
RAW icacls returncode: 0
RAW icacls stdout: 'Successfully processed 0 files; Failed processing 1 files'
FLOWOS PRIMITIVE: DirectoryHardeningError (PASS)
```

## ACL TARGETED TESTS

```text
python -m pytest tests/unit/test_dir_security.py -v --tb=short
→ 31 passed, 1 warning
```

## FLOW-1107 REGRESSION

```text
python -m pytest tests/integration/test_service_runtime.py tests/gui/test_live_launch.py \
  tests/gui/test_api_client_auth.py tests/integration/test_composition_root.py \
  tests/integration/test_websocket_auth.py -v --tb=short
→ 55 passed, 1 warning
```

## scripts/verify.py

```text
[PASS] 1. Ruff format check
[PASS] 2. Ruff lint
[PASS] 3. mypy
[PASS] 4. Architecture boundaries
[PASS] 5. Unit tests
[PASS] 6. Migrations check
[PASS] 7. Alembic round-trip
Prošlo: 7/7
```

## FILES CHANGED

- `src/flowos/service/services/infrastructure/dir_security.py`
- `tests/unit/test_dir_security.py`

## UNRELATED FILES CHANGED

NO

## Self-attack potvrda

- returncode=0 + "Failed processing 1" → RAISES
- returncode=0 + "Failed processing 2+" → RAISES
- returncode=0 + "Failed processing 0" → SUCCEEDS
- returncode!=0 → RAISES
- runtime token nakon maskiranog ACL failure → NOT WRITTEN (service.json ni .tmp)
- backup sadržaj nakon maskiranog ACL failure → NOT WRITTEN
- postojeći fajlovi ostaju čitljivi/upisivi → YES
- novi fajlovi i dalje nasljeđuju privatni ACL → YES
- junction cilj ostaje netaknut → YES
- repo/worktree path ne može biti hardenovan → YES

## Odstupanja od prompta

NONE

FLOW-1108 — Zaštita lokalnih FlowOS podataka = READY FOR FOCUSED RE-REVIEW
