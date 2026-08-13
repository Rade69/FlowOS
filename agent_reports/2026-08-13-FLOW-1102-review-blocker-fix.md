---
flowos_report_version: 1
report_id: 7c9587ac-f644-49ed-99c1-5344a78bba87
agent: crush
model: deepseek-v4-pro
session_id: unknown
report_type: fix
work_status: completed
tasks:
  - FLOW-1102
commits: []
created_at: 2026-08-13T14:58:48+02:00
---

# FLOW-1102 — GUI API error path review blocker B1 fix

## Datum

2026-08-13

## Agent / model / sesija

- Agent: Crush
- Model: deepseek-v4-pro
- Sesija: interaktivna CLI

## ORIGINAL RUNTIME BUG

`GuiApiClient._handle_response()` je koristio:

```python
if callable(signal):
    signal(data)
elif signal:
    signal.emit(data)
```

PySide6 bound `SignalInstance` prijavljuje `callable(signal) == True`, ali
direktan poziv `signal(data)` baca:

```text
TypeError: native Qt signal instance '...' is not callable
```

Problem je bio prisutan u OBE grane: success i error.

## ENUM→INT FIX RETAINED

YES — `reply.error().value` je zadržan (prethodno prihvaćen FLOW-1102 fix).

## SIGNALINSTANCE DISPATCH FIX

PASS — uveden statički `_dispatch()` koji Qt signale prepoznaje i emituje kroz
`.emit()` PRE običnih Python callable-a:

```python
@staticmethod
def _dispatch(signal, callback, payload):
    if signal is not None and hasattr(signal, "emit"):
        signal.emit(payload)
    elif callable(signal):
        signal(payload)
    elif callback is not None:
        callback(payload)
```

Obe grane (`success` i `error`) sada koriste `_dispatch`.

## ERROR REAL-SIGNAL TEST

PASS

## SUCCESS REAL-SIGNAL TEST

PASS

## PLAIN CALLABLE COMPATIBILITY

PASS

## NO DUPLICATE ERROR EMIT

PASS

## TARGETED TESTS

`python -m pytest tests/gui/test_api_client_error_path.py -v` → **5 passed**

```
test_error_real_signal_no_typeerror PASSED
test_success_real_signal_no_typeerror PASSED
test_plain_callable_compatibility PASSED
test_error_no_duplicate_emission PASSED
test_no_secondary_typeerror_on_signalinstance PASSED
```

## scripts/verify.py

7/7 PASS

## FILES CHANGED

- `src/flowos/gui/services/client.py`
- `tests/gui/test_api_client_error_path.py`

## Self-check

Qt SignalInstance called directly as function anywhere in _handle_response? NO
Qt SignalInstance handled via .emit()? YES
enum→int .value fix retained? YES
success path covered with real signal? YES
error path covered with real signal? YES
API contract changed? NO
GuiApiClient redesigned? NO
DB touched? NO
verify.py 7/7? YES

---

READY FOR INDEPENDENT RE-REVIEW
