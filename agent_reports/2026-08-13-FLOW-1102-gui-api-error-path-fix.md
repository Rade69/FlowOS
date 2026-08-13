---
flowos_report_version: 1
report_id: 3a2e8e56-b15b-4a46-ab66-1d74012b5ba5
agent: crush
model: deepseek-v4-pro
session_id: unknown
report_type: implementation
work_status: completed
tasks:
  - FLOW-1102
commits: []
created_at: 2026-08-13T14:30:47+02:00
---

# FLOW-1102 — GUI API error path TypeError fix

## Datum

2026-08-13

## Agent / model / sesija

- Agent: Crush
- Model: deepseek-v4-pro
- Sesija: interaktivna CLI

## ROOT CAUSE

`GuiApiClient.error_occurred` je deklarisan kao `Signal(int, str)`, ali
`_handle_response()` u error grani emituje `code = reply.error()` — što je
`QNetworkReply.NetworkError` enum, NE `int`.

PySide6 (Shiboken) ne može da konvertuje `NetworkError` enum u `int` C++ tip
za signal parametar. Posledica:

- `int(reply.error())` baca `TypeError: int() argument must be a string, a
  bytes-like object or a real number, not 'NetworkError'`
- `signal.emit(enum, msg)` ne baca direktno, ali emituje `0` umesto stvarne
  enum vrednosti i loguje Shiboken `Cannot copy-convert ... (NetworkError) to C++`

Tačna mismatch lokacija:

```text
signal deklaracija: error_occurred = Signal(int, str)
emit poziv:         self.error_occurred.emit(reply.error(), msg)   # enum umesto int
```

## REPRODUCTION

Izolovana reprodukcija u Pythonu:

```python
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtCore import QObject, Signal

class C(QObject):
    err = Signal(int, str)

c = C()
c.err.connect(lambda code, msg: print(code, msg))
e = QNetworkReply.NetworkError.ConnectionRefusedError
c.err.emit(e, "msg")
# → prima 0 (umesto 1) + Shiboken "Cannot copy-convert NetworkError to C++"
```

`int(QNetworkReply.NetworkError.ConnectionRefusedError)` baca `TypeError`.

## FIX

Minimalna izmena u `_handle_response()` error grani:

```python
code = reply.error().value if reply.error() is not None else -1
```

`.value` vraća `int` (npr. `ConnectionRefusedError.value == 1`), čime signal
dobija ispravan `int` bez Shiboken konverzione greške ili TypeError-a.

## ERROR PATH

PASS

## SUCCESS PATH

PASS (nepromijenjen — success grana ne dira `reply.error()`)

## TARGETED TESTS

`python -m pytest tests/gui/test_api_client_error_path.py -v` → **4 passed**

```
test_network_error_emits_int_code_without_typeerror PASSED
test_network_error_no_secondary_typeerror PASSED
test_error_surfaces_to_receiver_payload PASSED
test_no_duplicate_error_emission PASSED
```

## scripts/verify.py

7/7 PASS

## FILES CHANGED

- `src/flowos/gui/services/client.py`
- `tests/gui/test_api_client_error_path.py`

## OUT OF SCOPE LEFT UNTOUCHED

- FLOW-1103
- FLOW-1104
- FLOW-1105
- FLOW-1106
- DB/migrations
- Task UI
- Ledger GUI

## Self-check

API contract changed? NO
GuiApiClient redesigned? NO
broad exception suppression added? NO
DB touched? NO
unrelated GUI work added? NO
verify.py 7/7? YES

---

READY FOR INDEPENDENT REVIEW
