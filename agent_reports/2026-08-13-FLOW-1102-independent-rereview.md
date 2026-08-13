---
flowos_report_version: 1
report_id: 1aa64e5e-2b34-4ad7-8146-e2853f2905b2
agent: claude
model: claude-sonnet-5
session_id: unknown
report_type: review
work_status: completed
tasks:
  - FLOW-1102
commits: []
created_at: 2026-08-13T15:20:45+02:00
---

# FLOW-1102 — Focused re-review B1 (SignalInstance) popravke

## Scope

READ ONLY. Nije mijenjan kod, nisu mijenjani testovi, nije pravljen commit,
nije pushovano. FLOW-1103/1104/1105/1106 nisu dirnuti. Fokusiran re-review
isključivo B1 nalaza iz `agent_reports/2026-08-13-FLOW-1102-independent-
review.md`.

## 8. Scope / diff

```
git diff --stat
 src/flowos/gui/services/client.py | 30 +++++++++++++++++++-----------
```

Diff sada obuhvata i prethodni enum→int fix i novi `_dispatch()` helper —
oboje u istom, jedinom očekivanom fajlu. `tests/gui/test_api_client_error_
path.py` je ažuriran (untracked, kao i prije). Nema izmjene van
`client.py`/test fajla. Nepovezani untracked docs/reports fajlovi ostaju
netaknuti.

**Nema scope deviation.**

## 1. Verifikacija prethodnog B1

Pročitan trenutni `_handle_response()` i novi `_dispatch()`
(`client.py:120-153`):

```python
def _handle_response(self, reply, signal, callback=None):
    if reply.error() == QNetworkReply.NetworkError.NoError:
        try:
            data = json.loads(reply.readAll().data().decode())
            self._dispatch(signal, callback, data)
        except json.JSONDecodeError:
            self.error_occurred.emit(-1, "Neispravan JSON odgovor")
    else:
        code = reply.error().value if reply.error() is not None else -1
        msg = reply.errorString()
        self.error_occurred.emit(code, msg)
        self._dispatch(signal, callback, {"error": msg})
    reply.deleteLater()

@staticmethod
def _dispatch(signal, callback, payload):
    if signal is not None and hasattr(signal, "emit"):
        signal.emit(payload)
    elif callable(signal):
        signal(payload)
    elif callback is not None:
        callback(payload)
```

Direktan poziv `signal(payload)` na Qt `SignalInstance` **više se nigdje ne
dešava** — `_dispatch()` prvo provjerava `hasattr(signal, "emit")`, što je
`True` isključivo za pravu Qt `SignalInstance`, PRIJE `callable()` provjere.
Potvrđeno izolovanim probe-om:

```
hasattr(bound_qt_signal, "emit"): True
callable(bound_qt_signal): True
hasattr(plain_lambda, "emit"): False
```

`hasattr(signal, "emit")` ispravno razdvaja Qt signal (ide na `.emit()`) od
plain Python callable-a (ide na `callable()` granu) — obrnut redoslijed od
starog, pokvarenog koda koji je prvo provjeravao `callable()` (netačno True i
za Qt signal) i zato pokušavao direktan poziv.

Primijenjeno identično u OBJE grane (success linija 129, error linija 136) —
jedna dispatch putanja za oboje, nema duplirane/razdvojene logike koja bi
mogla drift-ovati.

**B1 SIGNALINSTANCE BUG = CLOSED.**

## 2. Review `_dispatch` implementacije

- **Ispravna**: `hasattr(signal, "emit")` provjera prije `callable()` je tačno
  ispravan redoslijed za razlikovanje Qt `SignalInstance` od plain callable-a
  (potvrđeno probe-om gore).
- **Minimalna**: jedna nova statička metoda, tri grane, zamjenjuje identičan
  ponovljeni blok koji je prije postojao dva puta (success i error granu) —
  ovo je i DRY poboljšanje, ne samo bugfix.
- **Kompatibilna sa postojećim callerima**: provjereni svi pozivaoci
  `_handle_response()`:
  - `_get()` (`client.py:96-102`) — prosljeđuje pravi `Signal` kao `signal`,
    `callback` nije prosljeđen (default `None`) → `_dispatch` ide na
    `signal.emit()`. 11 od 13 javnih metoda ide ovim putem
    (`check_health`, `get_projects`, `get_plan_progress`, `get_resume`,
    `get_active_sessions`, `get_plan_item`, `get_timeline`, `scan_agents`,
    `fetch_worktrees`).
  - `_post()` (`client.py:104-111`) — isto, pravi `Signal`
    (`create_project`, `regenerate_resume`, `prepare_integration`,
    `cleanup_worktree`).
  - `_delete()` (`client.py:113-118`) — prosljeđuje `signal=None,
    callback=callback` (plain lambda) → `_dispatch` preskače prvu granu
    (`signal is not None` je `False`), preskače `callable(None)` (`False`),
    ide na `callback(payload)`. Jedina metoda ovog obrasca:
    `delete_project()`.
- **Bez neželjene dvostruke isporuke**: `_dispatch()` je strogi if/elif/elif
  lanac — tačno jedna grana se izvršava po pozivu. Dvostruka NAMJERNA
  notifikacija (`error_occurred.emit()` PLUS `_dispatch()` na request-specifični
  signal) je isti obrazac koji je postojao i prije ovog fixa (dva različita
  signala za dvije različite svrhe: globalni error handler + per-request UI
  update) — nije novo ponašanje uvedeno ovim diff-om.

**Nisam se oslonio samo na implementation/fix report — potvrđeno direktnim
čitanjem koda i probe-ovima.**

## 3. Enum→int fix

```python
code = reply.error().value if reply.error() is not None else -1
```

I dalje prisutan, nepromijenjen od prethodnog reviewa. `error_occurred`
signature ostaje `Signal(int, str)` (`client.py:33`, nepromijenjeno). API
contract nepromijenjen.

## 4. Error production pattern — nezavisno provjereno

Ponovljen TAČAN probe iz prethodnog (BLOCKER) reviewa, protiv trenutnog koda:

```python
client._handle_response(reply, client.health_received)   # tacno kao _get()
```
```
Pozivam _handle_response TACNO kao sto _get() stvarno radi: signal=client.health_received
OK, nema greske. error_occurred primio: [(1, 'Connection refused')], health_received primio: [{'error': 'Connection refused'}]
```

- Nema `TypeError` ✓
- `error_occurred` emituje tačno jednom, `code=1` (tačan int za
  `ConnectionRefusedError`) ✓
- Poruka očuvana (`'Connection refused'`) ✓
- `health_received` prima tačno jednom `{"error": "Connection refused"}` ✓

**ERROR REAL-SIGNAL PATH = ACCEPT.**

## 5. Success production pattern — nezavisno provjereno

Ponovljen probe iz prethodnog reviewa (uspješan JSON odgovor):

```
health_received primio: [{'status': 'ok', 'uptime': 12.3}]
error_occurred primio (ocekivano prazno): []
Success path OK? True
```

- Nema `TypeError` ✓
- `health_received` emituje tačno jednom, ispravan dekodiran payload ✓
- `error_occurred` emituje nula puta ✓

**SUCCESS REAL-SIGNAL PATH = ACCEPT.**

## 6. Test quality

Pročitan ažuriran `tests/gui/test_api_client_error_path.py` (5 testova, gore sa
4):

- `test_error_real_signal_no_typeerror` — `client._handle_response(reply,
  client.health_received)`, PRAVI bound signal, error put. Provjerava
  `error_occurred` (tačan int, poruka) I `health_received` ({"error": msg}
  payload, tačno jednom).
- `test_success_real_signal_no_typeerror` — isto, success put, PRAVI bound
  signal, provjerava dekodiran payload i da `error_occurred` NE emituje.
- `test_plain_callable_compatibility` — `_handle_response(reply, None,
  lambda...)` — `_delete()`-stil calling convention, potvrđuje da plain
  callable i dalje radi.
- `test_error_no_duplicate_emission` — tačno 1+1 emisija na grešku.
- `test_no_secondary_typeerror_on_signalinstance` — eksplicitan regresioni
  test sa komentarom koji imenuje TAČNO stari bug ("Ako bi _dispatch koristio
  callable(signal) prvi, ovo bi puklo").

Svi testovi sada koriste PRAVI `client.health_received` (stvaran, deklarisan
Qt signal na klasi), ne `signal=None` kao prije. `_FakeReply.readAll()` sada
vraća pravi `QByteArray` (ne sirovi `bytes`), što tačnije replicira stvaran
`QNetworkReply` interfejs koji `_handle_response()` očekuje
(`reply.readAll().data().decode()`).

Pokrivenost naspram traženih A-F:
- A) SignalInstance error put — ✓ (`test_error_real_signal_no_typeerror`)
- B) SignalInstance success put — ✓ (`test_success_real_signal_no_typeerror`)
- C) tačan int network error kod — ✓ (oba testa)
- D) smislen error payload — ✓ (`msg`, `{"error": msg}`)
- E) nema duple error emisije — ✓ (`test_error_no_duplicate_emission`)
- F) plain Python callable kompatibilnost — ✓ (`test_plain_callable_
  compatibility`)

**Testovi više NE zaobilaze stvaran produkcijski dispatch — koriste tačan
`_get()`/`_post()` calling obrazac (pravi Signal) za sve nove asercije.**

**TEST QUALITY = ACCEPT.**

## 7. Regression

```
python -m pytest tests/gui/test_api_client_error_path.py -v --tb=short
5 passed in 0.07s
```
```
python scripts/verify.py
Prošlo: 7/7
[PASS] VERIFIKACIJA PROŠLA
```

Nema drugih postojećih testova koji referenciraju `GuiApiClient` u repou
(provjereno grep-om) — svježe potvrđeno, nepromijenjeno stanje od prethodnog
reviewa.

## 9. Findings

Nema novih BLOCKER/HIGH nalaza. Prethodni B1 (BLOCKER) je zatvoren sa dokazima
u sekcijama 1 i 4-5. Prethodni H1 (implementation report nije unakrsno
provjerio raniju dijagnozu) i L1 (`is not None` defanzivan kod za scenario koji
se ne dešava) nisu ponovo otvarani — L1 ostaje kao trivijalna stilska napomena,
H1 je bespredmetan sada kad je stvaran problem zatvoren.

**LOW**

- **L1 (ponovljeno, nepogoršano)** — `client.py:133`, `if reply.error() is not
  None else -1` — i dalje defanzivan kod za scenario koji se u praksi ne
  dešava (Qt `reply.error()` nikad ne vraća `None`). Nije uticaj na
  ispravnost, ne blokira prihvatanje.

## 10. Finalni verdict

```
B1 SIGNALINSTANCE BUG:              CLOSED
ENUM→INT FIX:                        ACCEPT
ERROR REAL-SIGNAL PATH:              ACCEPT
SUCCESS REAL-SIGNAL PATH:            ACCEPT
PLAIN CALLABLE COMPATIBILITY:        ACCEPT
NO DUPLICATE DELIVERY:               YES
TEST QUALITY:                        ACCEPT
API CONTRACT PRESERVED:              YES

scripts/verify.py: 7/7
```

**FLOW-1102 = ACCEPT**

Oba bug mehanizma (enum→int misconversion na `error_occurred.emit()`, i
`callable(signal)` netačno prepoznavanje Qt `SignalInstance` kao plain
callable) su sada dokazano zatvorena — ne samo isporučenim testovima, nego i
mojim nezavisnim probe-ovima koji direktno repliciraju tačan produkcijski
`_get()`/`_post()` pozivni obrazac (pravi `Signal`, ne `None`), isti obrazac
koji je u prethodnom reviewu dokazao da bug i dalje postoji. Success i error
putevi oba rade bez `TypeError`-a, sa tačnim int kodovima, smislenim porukama i
bez duple isporuke.
