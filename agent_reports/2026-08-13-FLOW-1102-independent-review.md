---
flowos_report_version: 1
report_id: db7fa91b-5325-425c-ab9c-e3b747e1c21b
agent: claude
model: claude-sonnet-5
session_id: unknown
report_type: review
work_status: completed
tasks:
  - FLOW-1102
commits: []
created_at: 2026-08-13T14:42:33+02:00
---

# FLOW-1102 — GUI API error path, independent review

## Scope

READ ONLY. Nije mijenjan kod, nisu mijenjani testovi, nije pravljen commit,
nije pushovano. Rad na FLOW-1103/1104/1105/1106 nije dirnut.

```
git status --short
 M src/flowos/gui/services/client.py
?? tests/gui/test_api_client_error_path.py
(plus nepovezani untracked docs/agent_reports fajlovi)
```
```
git diff --stat
 src/flowos/gui/services/client.py | 2 +-
```

**Nema izmjene van očekivanog scope-a.** Diff je doslovno jedna linija.

## 1. Scope

Potvrđeno — samo `client.py` (1 linija) i novi test fajl. Nema dirnutih
FLOW-1103/1104/1105/1106 fajlova niti DB/migracija.

## 2. Root cause — DJELIMIČNO TAČAN, NEDOVOLJAN

Pročitan stvaran kod `_handle_response()` (`client.py:120-145`) i
`error_occurred = Signal(int, str)` (linija 33).

**Provjerena tvrdnja implementation reporta** (`int(reply.error())` baca
`TypeError`, `.emit(enum, msg)` ne baca direktno nego tiho emituje `0` uz
Shiboken upozorenje) — **potvrđeno tačno, empirijski, na instaliranom PySide6
6.11.1**:

```
>>> int(QNetworkReply.NetworkError.ConnectionRefusedError)
TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NetworkError'

>>> emitter.error_occurred.emit(QNetworkReply.NetworkError.ConnectionRefusedError, "Connection refused")
Shiboken::Conversions::_pythonToCppCopy: Cannot copy-convert ... (NetworkError) to C++.
SLOT PRIMIO: code=0 (tip=int), msg='Connection refused'   ← POGREŠNA vrijednost (trebalo 1)
```

Ovo JE stvaran bug — `.value` fix (linija 138) ga ispravno rješava (potvrđeno:
`emit(enum.value, msg)` → slot prima `code=1`, ispravno).

**Ali ovo NIJE (ili nije jedini) originalno dijagnostikovan i runtime-potvrđen
problem.** Provjerena dva NEZAVISNA izvora, oba datirana PRIJE FLOW-1102
implementacije (13.08 popodne):

1. `agent_reports/2026-08-12-dogfooding-plan-pre-import-check.md:174-180`
   (analiza PRIJE implementacije, sa eksplicitnim dokazom):
   > "`GuiApiClient._handle_response()` u error grani emituje `error_occurred`,
   > ali zatim tretira `signal` kao callable ako `callable(signal)` vrati true
   > za Qt signal instancu. Runtime screenshot/capture je uhvatio
   > `TypeError: native Qt signal instance ... is not callable`."

2. `agent_reports/2026-08-12-flowos-current-gui-runtime-review.md:57,323`
   (nezavisan live GUI runtime review, sa stvarnim screenshotovima u
   `agent_reports/gui_runtime_2026-08-12/`):
   > "live GUI error path dodatno baca `TypeError` u
   > `GuiApiClient._handle_response`, jer na grešci pokušava pozvati Qt signal
   > kao funkciju." / "Service health | BROKEN | backend refused + GUI error
   > path TypeError"

Oba izvora opisuju **DRUGI, TEŽI bug**: `if callable(signal): signal(data)`
(linija 129/141) — `callable()` provjera je netačna za pravu Qt `SignalInstance`
(vraća `True`), pa se poziva `signal(data)` umjesto `signal.emit(data)`, što
baca `TypeError: native Qt signal instance '...' is not callable`.

**Potvrđeno mojim probe-om, direktno protiv TRENUTNOG (post-fix) koda, sa
POZIVOM TAČNO ONAKO KAKO PRODUKCIJSKI KOD STVARNO RADI** (`_get()`/`_post()`
prosljeđuju pravi `Signal`, ne `None`):

```python
client._handle_response(reply, client.health_received)   # tacno kao _get() radi
```
```
Pozivam _handle_response TACNO kao sto _get() stvarno radi: signal=client.health_received
!!! TypeError I DALJE POSTOJI (nakon FLOW-1102 fix-a): native Qt signal instance 'health_received' is not callable
error_occurred JE stigao prije crash-a? [(1, 'Connection refused')]
```

`self.error_occurred.emit(code, msg)` USPIJE (dokaz da JE `.value` fix
ispravan), ali ODMAH NAKON TOGA, `if callable(signal): signal({"error": msg})`
i dalje baca IDENTIČNU grešku kao prije FLOW-1102. Isti bug postoji i u SUCCESS
grani (linija 129), potvrđeno zasebnim probe-om — `_handle_response(reply,
client.health_received)` sa uspješnim odgovorom baca istu grešku prije nego što
`health_received` uopšte dobije podatke.

**Zašto je ovo bitno**: `callable(bound_qt_signal)` je `True` u PySide6 (probe:
`callable(c.sig) == True`, `type(c.sig) == SignalInstance`), ali direktan poziv
`c.sig(123)` baca tačno `TypeError: native Qt signal instance 'sig' is not
callable`. Od 13 javnih metoda `GuiApiClient`-a, 12 poziva `_get()`/`_post()`
koje UVIJEK prosljeđuju pravi `Signal` kao `signal` argument (npr.
`self._get("/health", self.health_received)`) — samo `delete_project()` koristi
`_delete()` koja prosljeđuje `signal=None`. To znači: **ovaj bug pogađa gotovo
SVAKI GET/POST poziv, na uspjehu I na grešci**, ne samo error granu.

**FLOW-1102 fix je ispravio realan, ali sporedan bug (enum→int silent
misconversion), dok je originalno dijagnostikovan, screenshot-potvrđen,
teži bug (`callable(signal)` crash na svakom GET/POST pozivu) ostao potpuno
nedirnut.**

**ROOT CAUSE = FIXES REQUIRED.**

## 3. Fix review

Sam `.value` fix (linija 138) je ispravan, minimalan, i ne radi ništa više od
potrebnog za bug koji rješava:

- ispravna numerička Qt network error vrijednost se čuva (`.value == 1` za
  `ConnectionRefusedError`, potvrđeno probe-om) — ✓
- nema dodatog broad exception suppression-a — ✓
- API contract nepromijenjen (`Signal(int, str)` isti) — ✓
- success grana nedirnuta (diff je samo u `else` grani) — ✓
- nema duplog emit-a uvedenog — ✓ (jedan `self.error_occurred.emit(...)` poziv,
  isto kao prije)
- error message payload ostaje smislen (`reply.errorString()` nepromijenjen) — ✓

Manja napomena: `if reply.error() is not None else -1` — `reply.error()` nikad
NE vraća `None` u praksi (Qt uvijek vraća validan enum, minimalno `NoError`) —
ovo je defanzivan kod za scenario koji se ne može desiti (blaga napomena, ne
funkcionalni bug — LOW).

**Fix koji JESTE isporučen radi tačno ono što tvrdi da radi — problem je što
ne rješava CIJEL originalno dijagnostikovan problem** (vidi Section 2).

## 4. PySide/Qt behavior — nezavisno reprodukovano

```
PySide6 verzija: 6.11.1
int(QNetworkReply.NetworkError.ConnectionRefusedError) → TypeError
QNetworkReply.NetworkError.ConnectionRefusedError.value → 1 (int)
Signal(int,str).emit(raw_enum, msg) → NE baca TypeError direktno, ali:
  - Shiboken upozorenje na stderr: "Cannot copy-convert ... (NetworkError) to C++"
  - slot prima code=0 (POGREŠNO, trebalo 1)
Signal(int,str).emit(raw_enum.value, msg) → slot prima code=1 (ISPRAVNO)
```

Sve potvrđeno živim izvršavanjem (QCoreApplication + stvaran `Signal`), ne samo
statičkim čitanjem koda.

## 5. Test quality — NEDOVOLJNO

Pročitan `tests/gui/test_api_client_error_path.py`. Sva četiri testa pozivaju:
```python
client._handle_response(reply, None)
```
sa `signal=None`. Ovo NIJE kako `_get()`/`_post()` stvarno pozivaju
`_handle_response()` u produkciji — `signal=None` je isključivo kalling
convention za `_delete()` (jedina metoda koja to radi). Kada je `signal=None`:
`callable(None)` je `False`, `elif signal:` je takođe `False` (None je falsy) —
cijeli `if callable(signal)/elif signal` blok se PRESKAČE u sva četiri testa.

**Testovi zato NIKAD ne izvršavaju granu koda koja sadrži originalno
dijagnostikovan, teži bug** (Section 2). Oni ispravno dokazuju da `error_occurred.
emit(code, msg)` sada radi (A — tačan int kod; C — smislena poruka; D — tačno
jedna emisija), ali B ("no secondary TypeError / Shiboken conversion issue")
je DOKAZAN SAMO za `.emit()` poziv, NE za cijeli `_handle_response()` poziv kroz
stvarni GET/POST put — jer `signal=None` put nikad ne stigne do koda koji baca
`TypeError: native Qt signal instance ... is not callable`.

**Testovi zaobilaze stvaran problematičan kod** — ne testiraju sintetički
signal umjesto pravog `GuiApiClient.error_occurred` (to JE pravi signal), nego
testiraju sa pogrešnim `signal` argumentom koji ne odgovara stvarnom pozivnom
obrascu 12 od 13 javnih metoda klase.

**TEST QUALITY = FIXES REQUIRED.**

## 6. Success path

Diff ne dira `if reply.error() == QNetworkReply.NetworkError.NoError:` granu
niti njen sadržaj — potvrđeno čitanjem. Ne postoji NIJEDAN postojeći test za
success granu `GuiApiClient`-a u cijelom repou (grep kroz `tests/` — jedini
fajl koji pominje `GuiApiClient` je novi FLOW-1102 test fajl) — pre-postojeći
gap, nije uveden ovim diff-om.

Napravljen sopstveni probe (poziv `_handle_response(reply, client.
health_received)` sa uspješnim JSON odgovorom, TAČNO kao `_get()` stvarno
poziva):
```
TypeError: native Qt signal instance 'health_received' is not callable
```
**Isti bug postoji i u success grani** — dokazuje da je problem iz Section 2
opštiji od samo "error path", pogađa i uspješne odgovore, kad se poziva kroz
stvaran `_get()`/`_post()` put.

**SUCCESS PATH = FIXES REQUIRED** (pre-postojeći, nedirnut ovim diff-om, ali
review eksplicitno traži da se provjeri i prijavi).

## 7. Regression

```
python -m pytest tests/gui/test_api_client_error_path.py -v --tb=short
4 passed in 0.09s
```
```
python scripts/verify.py
Prošlo: 7/7
[PASS] VERIFIKACIJA PROŠLA
```

Svi isporučeni testovi prolaze i `verify.py` je 7/7 — ali kao što je pokazano u
Section 5, to je zato što isporučeni testovi ne pokrivaju stvaran produkcijski
pozivni obrazac, ne zato što je bug stvarno riješen.

## 8. Findings

**BLOCKER**

- **B1** — `src/flowos/gui/services/client.py:129,141` (`if callable(signal):
  signal(data)` / `signal({"error": msg})`). `callable()` provjera netačno
  vraća `True` za pravu PySide6 `SignalInstance`, uzrokujući poziv `signal(...)`
  umjesto `signal.emit(...)`, što baca `TypeError: native Qt signal instance
  '...' is not callable`. **Dokaz**: probe protiv trenutnog (post-FLOW-1102)
  koda, pozivom `_handle_response()` tačno onako kako `_get()`/`_post()` stvarno
  pozivaju (sa pravim `Signal` argumentom) — greška se i dalje dešava, u obje
  grane (success i error). **Uticaj**: ovo je originalno dijagnostikovan,
  runtime-screenshot-potvrđen bug (`2026-08-12-dogfooding-plan-pre-import-
  check.md`, `2026-08-12-flowos-current-gui-runtime-review.md`) koji pogađa
  12 od 13 javnih `GuiApiClient` metoda — health check, projects, plan
  progress, resume, sessions, plan items, timeline, agents scan, worktrees,
  integration, cleanup. GUI ne može pouzdano primiti NIJEDAN uspješan ili
  neuspješan API odgovor kroz normalan put. **Minimalna ispravka**: zamijeniti
  `if callable(signal): signal(x) elif signal: signal.emit(x)` sa provjerom
  koja prvo prepoznaje pravi Qt signal (npr. `if hasattr(signal, "emit"):
  signal.emit(x) elif callable(signal): signal(x)`), ili koristiti
  `isinstance(signal, PySide6.QtCore.SignalInstance)` eksplicitno prije
  `callable()` provjere. Primijeniti izmjenu u OBJE grane (success i error).

**HIGH**

- **H1** — Implementation report (`2026-08-13-FLOW-1102-gui-api-error-path-
  fix.md`) naslovljava problem kao "GUI API error path TypeError" i tvrdi da je
  "ROOT CAUSE" pronađen i riješen, ali ne referencira niti provjerava dva
  postojeća, ranija dokumenta (`dogfooding-plan-pre-import-check.md`,
  `flowos-current-gui-runtime-review.md`) koja opisuju TAČNO drugačiji,
  screenshot-potvrđen mehanizam pod istim imenom problema. **Zašto je važno**:
  bez unakrsne provjere sa originalnom dijagnozom, implementator je popravio
  bug koji NIJE onaj koji je izvorno prijavljen kao "GUI API error path
  TypeError" — moguće zbog nezavisne reprodukcije (`int(reply.error())`
  scenario) koja JESTE realan bug, ali nije isti kao prijavljen. **Minimalna
  ispravka**: prije proglašavanja "ROOT CAUSE" utvrđenog, provjeriti da li
  postoji ranija dijagnoza/screenshot i da li se fix odnosi na TAJ TAČAN
  mehanizam.

**LOW**

- **L1** — `client.py:138`, `if reply.error() is not None else -1` — `reply.
  error()` nikad ne vraća `None` u praksi (Qt uvijek vraća validan
  `NetworkError` enum minimalno `NoError`); ovo je defanzivan kod za scenario
  koji se realno ne može desiti. Ne utiče na ispravnost, samo stilska napomena.

## 9. Finalni verdict

```
ROOT CAUSE:                     FIXES REQUIRED
FIX:                            FIXES REQUIRED (ispravan za svoj uzak scope, ali nedovoljan)
SIGNAL CONTRACT PRESERVED:      YES
ERROR CODE PRESERVED:           YES (za .emit() poziv; queue se ne stigne izvršiti do kraja u pravom GET/POST pozivu)
ERROR MESSAGE PRESERVED:        YES
NO DUPLICATE EMIT:              YES
SUCCESS PATH:                   FIXES REQUIRED (isti bug prisutan, van scope-a diff-a, ali stvaran)
TEST QUALITY:                   FIXES REQUIRED

scripts/verify.py: 7/7
```

**FLOW-1102 = FIXES REQUIRED**

Razlog: isporučeni fix je ISPRAVAN za bug koji adresira (enum→int
misconversion na `error_occurred.emit()`) — to nije sporno i potvrđeno je
probe-om. Ali originalno dijagnostikovan i dvostruko dokumentovan (analiza +
live GUI screenshot review, oba PRIJE implementacije) problem —
`callable(signal)` netačno tretira pravu Qt `SignalInstance` kao plain Python
callable, uzrokujući `TypeError: native Qt signal instance '...' is not
callable` na SVAKOM GET/POST pozivu (success i error) — ostaje potpuno
nedirnut. Ovo sam potvrdio direktnim, živim probe-om protiv trenutnog koda,
pozivajući `_handle_response()` tačno onako kako produkcijski `_get()`/`_post()`
stvarno pozivaju (sa pravim `Signal` argumentom, ne `None` kako to rade svi
isporučeni testovi). Isporučeni testovi ne mogu uhvatiti ovo jer koriste
`signal=None`, kalling convention koji odgovara samo `_delete()`, ne
preostalim 12 javnim metodama.

Potrebno prije prihvatanja:
1. Ispraviti `if callable(signal): signal(x) elif signal: signal.emit(x)`
   obrazac u OBJE grane `_handle_response()` da ispravno prepozna pravu Qt
   `SignalInstance` i pozove `.emit()`, ne direktan poziv.
2. Dodati test koji poziva `_handle_response()` sa PRAVIM `Signal` argumentom
   (npr. `client.health_received`), ne `None` — i za success i za error granu
   — da dokaže da GET/POST put stvarno radi.
3. Ažurirati implementation report da referencira i razriješi razliku između
   ova dva bug mehanizma.
