---
task_id: FLOW-1158
risk: MEDIUM
implementer: TBD
reviewers: [Claude]
status: "OPEN — task contract napisan prije koda"
created_at: 2026-08-28
depends_on: []
blocks: []
coupled_with: [FLOW-1156]
---

# FLOW-1158 — Uklanjanje services→controllers zavisnosti (event_bus)

## 1. Kontekst

Potvrđeno pokretanjem `python scripts/guard_architecture.py` nad `34cacdb`
(identično na `b83f197` — pre-postojeći dug, ne regresija FLOW-1157):

```text
[FAIL] 9 arhitektonskih prekršaja — svi isti obrazac:
zabranjen import 'flowos.service.controllers.websocket.events' → pripada 'flowos.service.controllers'
```

Tačne lokacije (`from flowos.service.controllers.websocket.events import event_bus`):

```text
src/flowos/service/services/plan_progress.py:461
src/flowos/service/services/reconciliation/service.py:160
src/flowos/service/services/worktrees/manager.py:63
src/flowos/service/services/sessions/service.py:142
src/flowos/service/services/sessions/completion.py:136
src/flowos/service/services/sessions/completion.py:225
src/flowos/service/services/sessions/completion.py:265
src/flowos/service/services/conflicts/service.py:531
src/flowos/service/services/conflicts/service.py:566
```

Granica arhitekture je `View → Controller → Services`: Controller smije
zvati Service, ne obrnuto. Ovih devet mjesta krši smjer — Service uvozi iz
Controller paketa da bi emitovao WebSocket notifikaciju.

`event_bus` je modul-nivo singleton klase `EventBus`
(`src/flowos/service/controllers/websocket/events.py:1–82`). Sama klasa
nema zavisnost od HTTP-a, rutiranja ni FastAPI kontrolera — radi čisti
pub/sub sa `asyncio` i WebSocket konekcijama. Njeno mjesto u
`controllers/websocket/` je istorijska slučajnost, ne arhitektonska
nužnost. Jedini stvarni Controller-specifičan dio istog fajla je
`ws_endpoint()` i `_is_authorized()` (`:88+`), koji ostaju gdje jesu.

Dodatni pozivalac van services sloja:

```text
src/flowos/service/composition_root.py:31   import ws_endpoint
src/flowos/service/composition_root.py:435  import event_bus  (za bind_loop)
```

Composition root je wiring/DI root — legitiman pozivalac oba sloja, ne
mijenja se ovim taskom.

## 2. Cilj

`EventBus` postaje dio infrastructure sloja, koji i Services i Controllers
smiju importovati. Devet importa u `services/*` prestaje ići kroz
`controllers.websocket.events`. Guard prijavljuje nula prekršaja za ovaj
obrazac.

## 3. Traženo rješenje

### 3.1 Premjestiti EventBus

Novi fajl: `src/flowos/service/services/infrastructure/events.py`

Sadrži klasu `EventBus` i modul-nivo `event_bus = EventBus()`, premješteno
doslovno iz `websocket/events.py:1–82` (import, `EventBus` klasa, `emit`,
`emit_sync`, `bind_loop`, `connect`, `disconnect`, globalna instanca).

### 3.2 `websocket/events.py` re-eksportuje

```python
from flowos.service.services.infrastructure.events import EventBus, event_bus

__all__ = ["EventBus", "event_bus", "ws_endpoint"]
```

`ws_endpoint()` i `_is_authorized()` ostaju u ovom fajlu nepromijenjeni —
oni su stvarno Controller-nivo (FastAPI WebSocket ruta, auth provjera).

Re-export postoji da `composition_root.py:31,435` ne mora mijenjati ništa
u ovom tasku — DI root i dalje importuje iz `controllers.websocket.events`
i dobija identičan objekat.

### 3.3 Promijeniti devet importa

U svih šest fajlova iz sekcije 1, zamijeniti:

```python
from flowos.service.controllers.websocket.events import event_bus
```

sa:

```python
from flowos.service.services.infrastructure.events import event_bus
```

Ništa drugo u tim fajlovima se ne dira — poziv je i dalje
`event_bus.emit_sync(...)` ili `event_bus.emit(...)`, isti objekat, isti
API.

## 4. Acceptance

```text
[ ] src/flowos/service/services/infrastructure/events.py postoji sa EventBus
[ ] websocket/events.py importuje EventBus/event_bus odatle, ne definiše je
[ ] websocket/events.py i dalje izlaže ws_endpoint bez izmjene ponašanja
[ ] svih devet mjesta iz sekcije 1 importuje iz infrastructure.events
[ ] composition_root.py:31,435 nepromijenjen i dalje radi (re-export)
[ ] python scripts/guard_architecture.py → 0 prekršaja
[ ] pytest tests/architecture/ -q → PASS
[ ] pytest tests/unit tests/integration -q → PASS, posebna pažnja na
    testove koji mock-uju ili importuju event_bus direktno
[ ] python scripts/verify.py → PASS, svi koraci
[ ] ruff check . → clean
[ ] mypy src → clean
[ ] grep -rn "from flowos.service.controllers.websocket.events import event_bus" src
    → 0 pogodaka van websocket/events.py samog re-eksporta i
    composition_root.py
```

### 4.1 Adversarni dokaz

Ovaj task ne mijenja PUT izvršavanja (`event_bus.emit_sync(...)` poziv je
identičan, mijenja se samo odakle se objekat uvozi), pa striktno gledano
FLOW-1305 se ne primjenjuje. Ipak, jer je greška klase „radi u testu, ne
radi u runtime-u zbog lijenog importa", obavezna provjera:

```text
1. Pokrenuti servis (scripts/run_service.py) lokalno
2. Okinuti bar jedan event (npr. import plana → plan_progress.updated)
3. Potvrditi da GUI klijent prima WebSocket poruku kao i prije izmjene
4. Doslovan log/output ide u izvještaj
```

Testovi koji mock-uju `event_bus` importom iz starog mjesta moraju biti
pronađeni i ažurirani — pretraga `grep -rn "controllers.websocket.events" tests`
prije zaključivanja da je gotovo.

## 5. Allowed / Forbidden paths

**Allowed:**

```text
src/flowos/service/services/infrastructure/events.py   (novi fajl)
src/flowos/service/controllers/websocket/events.py
src/flowos/service/services/plan_progress.py
src/flowos/service/services/reconciliation/service.py
src/flowos/service/services/worktrees/manager.py
src/flowos/service/services/sessions/service.py
src/flowos/service/services/sessions/completion.py
src/flowos/service/services/conflicts/service.py
tests/**   (samo importi event_bus, ne nova test logika van scope-a)
```

**Forbidden:**

```text
src/flowos/gui/**              — nema veze sa ovim taskom
src/flowos/service/composition_root.py   — ostaje netaknut (re-export ga pokriva)
scripts/guard_architecture.py  — FLOW-1156, ne ovaj task
scripts/verify.py
```

Ako se otkrije da neki od šest fajlova ima dodatne importe iz
`controllers/` van `event_bus` (nepotvrđeno, nije provjereno), to je
`OUT_OF_SCOPE_FINDING` — ne širiti scope bez novog taska.

## 6. Review

**Reviewer: Claude.**

Fokus:

```text
1. Da li je EventBus premještena doslovno ili je logika suptilno promijenjena
2. Da li ws_endpoint i dalje radi identično — pokrenuti servis, ne samo čitati diff
3. Da li je re-export potpun (ništa što composition_root koristi nije nestalo)
4. Da li grep za stari import path pokazuje 0 pogodaka van dozvoljenih mjesta
5. Da li su testovi koji importuju event_bus i dalje zeleni
```

Verdict blok:

```yaml
verdict: PASS|PASS_WITH_NOTES|REJECT
scope: PASS|REJECT
acceptance: PASS|REJECT
architecture: PASS|REJECT
security: PASS|REJECT
blocking_findings:
  - <kod>: <opis>
```

## 7. Koordinacija

```text
grana:      task/FLOW-1158-eventbus-relocation
baseline:   34cacdb ili noviji main — navesti u izvještaju
zavisnosti: nema
coupled:    FLOW-1156 — guard ne postaje blokirajući dok oba nisu gotova
```

Implementer ne commituje i ne pušuje sam. Poslije mergea: post-merge gate
na glavnoj grani (`pytest -q`, `ruff check .`, `mypy src`,
`python scripts/verify.py`, `python scripts/guard_architecture.py` —
ovaj put i guard, jer je upravo on mjera uspjeha ovog taska).

## 8. Izvještaj implementera

```text
agent_reports/<YYYY-MM-DD>-FLOW-1158-<implementer>-eventbus-relocation.md
```

Sadrži: baseline SHA, listu stvarno promijenjenih fajlova, doslovan output
svih komandi iz sekcije 4, dokaz iz 4.1 (log stvarno pokrenutog servisa),
svaki `OUT_OF_SCOPE_FINDING`.
