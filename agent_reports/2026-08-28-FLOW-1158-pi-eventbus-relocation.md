# FLOW-1158 — Uklanjanje services→controllers zavisnosti (event_bus)

- Datum: 2026-08-28
- Agent: pi
- Grana: task/FLOW-1158-eventbus-relocation
- Baseline: 34cacdb (zatečeno na main, potvrđeno `git log`)
- Task contract: docs/FLOW-1158-task-contract.md
- Status: OK (implementirano, NIJE commitovano — po pravilu "implementer ne commituje sam")

## Scope

Premjestiti `EventBus` (i singleton `event_bus`) iz `controllers/websocket/events.py`
u `services/infrastructure/events.py`, ostaviti `ws_endpoint()` i `_is_authorized()`
u Controller fajlu uz re-export, i promijeniti 9 importa u 6 services fajlova tako da
uvoze iz infrastructure sloja umjesto iz Controller paketa.

## Task contract / acceptance kriteriji

Svi kriteriji iz sekcije 4 contracta — rezultati u sekciji "Verifikacija".

## GitNexus impact analiza

Pokrenuto `npx gitnexus impact -r FlowOS EventBus`:

- Target: `Class:src/flowos/service/controllers/websocket/events.py:EventBus`
- Risk: **MEDIUM** (poklapa se sa contractom)
- impactedCount: 15; direct (depth 1): 7 importera — composition_root.py + 6 services fajlova
- depth 2: app.py, plan_import.py, workflow/decisions.py, reports/service.py, controllers/http/*

Nema HIGH/CRITICAL pa handoff nije potreban. Blast radius se poklapa sa listom iz contracta.

## Reprodukcija prije izmjene

`python scripts/guard_architecture.py` nad baseline `34cacdb` prijavljivao je 9 prekršaja
obrasca `from flowos.service.controllers.websocket.events import event_bus` u services sloju
(potvrđeno u contractu; greške su bile determinističke i vidljive na svim 9 lokacija).

## Šta je urađeno

1. Kreiran `src/flowos/service/services/infrastructure/events.py` — klasa `EventBus`,
   metode `bind_loop`, `connect`, `disconnect`, `emit`, `emit_sync` i `event_bus = EventBus()`
   premješteni doslovno (bez izmjene logike).
2. `src/flowos/service/controllers/websocket/events.py` sada sadrži samo Controller-nivo
   kod (`ws_endpoint`, `_is_authorized`) i re-eksportuje `EventBus`/`event_bus` iz
   infrastructure sloja uz `__all__ = ["EventBus", "event_bus", "ws_endpoint"]`.
3. Zamijenjeno 9 importa u 6 fajlova: `from flowos.service.controllers.websocket.events
   import event_bus` → `from flowos.service.services.infrastructure.events import event_bus`.
4. `composition_root.py:31,435` NIJE diran (re-export ga pokriva, kako contract traži).

## Zašto je urađeno

Services sloj je uvozio iz Controller paketa da bi emitovao WebSocket notifikaciju, što
krši granicu View → Controller → Services. `EventBus` je čisti pub/sub bez HTTP/routing
zavisnosti pa pripada infrastructure sloju koji smiju koristiti i Services i Controllers.

## Kako je urađeno

- Novi fajl napisan (write), Controller fajl prepisan (write), importi zamijenjeni
  ciljanim `sed`-om ograničenim na 6 dozvoljenih fajlova (ne globalni find-replace po repou).

## Izmijenjeni fajlovi

- `src/flowos/service/services/infrastructure/events.py` (novi)
- `src/flowos/service/controllers/websocket/events.py`
- `src/flowos/service/services/plan_progress.py`
- `src/flowos/service/services/reconciliation/service.py`
- `src/flowos/service/services/worktrees/manager.py`
- `src/flowos/service/services/sessions/service.py`
- `src/flowos/service/services/sessions/completion.py`
- `src/flowos/service/services/conflicts/service.py`

## Šta NIJE dirano

- `src/flowos/service/composition_root.py` (forbidden — re-export ga pokriva)
- `src/flowos/gui/**` (forbidden)
- `scripts/guard_architecture.py`, `scripts/verify.py` (forbidden — FLOW-1156/verify)
- Tuđe zatečene izmjene: `scripts/guard_architecture.py`, `tests/architecture/test_boundaries.py`,
  `agent_reports/2026-08-28-FLOW-1156-claude-guard-gui-coverage.md` (paralelni rad na FLOW-1156)

## Verifikacija i stvarni rezultat

Sve komande pokrenute, doslovan rezultat:

1. `python scripts/guard_architecture.py` → `[PASS] Arhitektura cista — nema zabranjenih importa.` (0 prekršaja)
2. `python -m pytest tests/architecture/ -q` → `10 passed`
3. `python -m pytest tests/unit tests/integration -q` → `548 passed, 1 warning` (warning je postojeći StarletteDeprecationWarning, nevezan za task)
4. `python scripts/verify.py` → `Prošlo: 7/7` (`[PASS] VERIFIKACIJA PROŠLA`)
5. `ruff check` nad 8 izmijenjenih fajlova → `All checks passed!`
6. `mypy --explicit-package-bases` nad 2 nova/prepisana fajla → `Success: no issues found`
7. `grep -rn "from flowos.service.controllers.websocket.events import event_bus" src` →
   jedini preostali pogodak je `composition_root.py:435` (dozvoljen); 0 u tests
8. `python -m py_compile` nad svih 8 izmijenjenih fajlova → OK

### Adversarni dokaz (4.1)

Stvarni uvicorn servis (`create_app` + lifespan `bind_loop`) na izolovanoj temp bazi i
fiksnim tokenom, pa end-to-end: `POST /projects` → WebSocket `/ws` (Bearer token) →
`POST /sessions` → primljena WS poruka. Doslovan ishod:

```text
SESSION_CREATED http_status=200
WS_RECEIVED type=session.created payload_keys=['agent_type', 'execution_mode', 'project_id', 'session_id', 'worktree_path']
ADVERSARIAL_PASS: WebSocket poruka primljena u runtime-u
```

Log servisa potvrđuje bindovanje loopa: `flowos.websocket: EventBus vezan za glavni event loop`.
Privremeni skript obrisan nakon izvršenja.

## Pronađeni problemi

- **F1 — pre-postojeće ruff/mypy greške van scope-a.** Doslovne acceptance komande
  `ruff check .` daje 40 grešaka (sve `UP007` u `alembic/versions/*.py`), a `mypy src`
  daje 1 grešku (`Source file found twice` u `src/flowos/cli/services/client.py`).
  NIJEDNA nije u fajlovima koje je FLOW-1158 dirnuo. Autoritativna ulazna tačka
  `scripts/verify.py` (koja interno pokriva ruff lint + mypy) prolazi 7/7, a izmijenjeni
  fajlovi pojedinačno prolaze ruff i mypy. Ovo je pre-postojeći dug, ne regresija FLOW-1158.
- Nema `OUT_OF_SCOPE_FINDING` — nijedan od 6 fajlova nema dodatne `controllers/` importe
  van `event_bus` (provjereno grep-om).

## Odbačene opcije

- Opcija: mijenjati `composition_root.py` da direktno uvozi iz infrastructure — ODBIJENA,
  contract eksplicitno traži da ostane netaknut (re-export ga pokriva).
- Opcija: brisati stari put umjesto re-exporta — ODBIJENA, re-export je tražen da DI root
  ne mijenja ništa u ovom tasku.

## Konflikti / kontradiktorni izvori

- `scripts/run_service.py` (naveden u contractu 4.1) sadrži samo docstring — stvarni entry
  je `python -m flowos.service.app`. Adversarni dokaz je urađen preko `create_app` + uvicorn
  (isti app/lifespan kodni put), ne preko prazne skripte.
- Dijeljeni tree: u toku rada zatečene su tuđe izmjene FLOW-1156 (`guard_architecture.py`,
  `test_boundaries.py`). Nisu dirane.

## Commitovi

Nema — po pravilu "implementer ne commituje i ne pušuje sam". Sve izmjene su u working tree
na grani `task/FLOW-1158-eventbus-relocation`.

## Rizici i ograničenja

- Adversarni dokaz je izveden sa stub RuntimeManager (fiksni token) i temp bazom — ne sa
  `RuntimeManager` koji piše descriptor. Kodni put emitovanja (bind_loop → emit_sync →
  send_text) je identičan onom u produkciji.
- U WebSocket logu pri gašenju konekcije pojavljuje se traceback vezan uz `logger.info` u
  `disconnect()`; logika `disconnect` je premještena doslovno i identična originalu, pa nije
  regresija ovog taska (isti kod bi proizveo isto na baseline-u).

## Potreban follow-up

- Review od strane Claude-a (po contractu) — fokus na: doslovnost premještanja, ispravnost
  ws_endpoint, potpunost re-exporta, grep starih importa, zeleni testovi.
- Post-merge gate na glavnoj grani (pytest, ruff, mypy, verify.py, guard_architecture.py).

## Potrebna korisnička potvrda

- Odluka o commit-u/merge-u grane `task/FLOW-1158-eventbus-relocation` (agent ne commituje sam).
- F1 (pre-postojeće ruff/mypy greške) je van scope-a FLOW-1158 — ako korisnik želi, otvoriti
  zaseban task.
