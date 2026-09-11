---
flowos_report_version: 1
report_id: 9df66e30-1572-4de1-9a26-e8dce2270690
agent: codex
model: gpt-5
session_id: unknown
report_type: implementation
work_status: completed
tasks:
  - FLOW-1202
commits:
  - b34747e50778179185c0176eb88ac9552a241b4f
  - 7d07d8aa9a4482782cb79560d5b9ad2ac51ad05e
created_at: 2026-09-11T18:32:32+02:00
---

# FLOW-1202 — Zadaci ekran na stvarnom `/tasks` backendu

## Baseline i reuse

- Base: `ca891a7daeef15f6de2a16031ba45c14c6397995` (`main`).
- Izolovani worktree: `H:/FlowOS-worktrees/FLOW-1202-live-tasks`.
- Branch: `task/FLOW-1202-live-tasks`.
- Prije cherry-picka lokalni Git je potvrdio izvorni commit
  `4f7a440429866446a77ab8ac34cb9bc39e469789` i parent
  `8628dbef6f8bf757ee96ff4006b4dc8827f65c0d`.
- Cherry-pick je proizveo `b34747e50778179185c0176eb88ac9552a241b4f` i ponovo
  iskoristio dokazani FLOW-1202A `TaskResponse.plan_item_id` rad.

## Implementirano

- `GuiApiClient.get_tasks(project_id, generation)` čita
  `/tasks?project_id=...` i emituje isti `project_id + generation` kontekst kao
  ostali project-scoped readovi.
- `FlowOsGui._load_project_data()` uključuje Tasks u postojeći batch; `_on_tasks()`
  odbacuje drugi projekat, stariju generation i ne-list error envelope.
- Promjena projekta briše prethodne Task redove prije novog odgovora.
- `TasksPage` prikazuje naslov, status, prioritet, PlanItem ili jasno
  `Nije vezano za plan`, te zaseban Task ID. PlanItem se ne prikazuje kao Task.
- Nisu uvedeni novi async framework, kanban, procenat završenosti niti
  FLOW-1203/FLOW-1204 funkcionalnost.

## Acceptance kriteriji

1. **PASS — minimalni read API client tok.**
   `src/flowos/gui/services/client.py:GuiApiClient.get_tasks`;
   `tests/gui/test_api_client_auth.py::test_tasks_read_uses_project_route_and_context_envelope`.
2. **PASS — identitet, naslov, status i vezani PlanItem.**
   `src/flowos/gui/views/pages.py:TasksPage.render`; GUI T21; backend T2.
3. **PASS — unassigned Task je validan i jasan.** Backend T1 i GUI T21;
   LIVE red `task-free` prikazan kao `Nije vezano za plan`.
4. **PASS — PlanItem nije tretiran kao Task.** Odvojene kolone `Plan stavka` i
   `Task ID`; LIVE red zadržava oba različita identiteta.
5. **PASS — nema nedeterminističkog procenta.** Nema takve kolone ni derivacije
   u izmijenjenom sourceu; exhaustive `rg` pregled diffa/call-siteova.
6. **PASS — project-scoped aktivni context.** `/tasks?project_id=...`, backend T3,
   GUI T17 i direktna source potvrda `_load_project_data()`.
7. **PASS — stale drugi projekat i starija generation se odbacuju.** GUI T18/T19.
8. **PASS — deterministički switch/out-of-order regression testovi.** GUI T18–T20.
9. **PASS — isti batch generation ugovor.** GUI T17 i source
   `FlowOsGui._load_project_data`.

## Fixture reprodukcija

Odmah poslije cherry-picka standardni direktni backend run je dao `1 failed,
2 errors`: SQLAlchemy mapper nije imao učitan `AgentReportBindingLink`, a
timeline fixture nije imao učitan `FileActivity`. Minimalna test-fixture
popravka u `tests/integration/test_projects_tasks_api.py` samo registruje
`report_models` i `activity_models`; produkcijski kod nije mijenjan zbog fixturea.
Nakon popravke cijeli fajl: `20 passed`.

## RED → GREEN

Prije GUI produkcijske implementacije dodani testovi T17–T21 i API client test:
`6 failed, 22 passed`, tačno zbog nepostojećeg requesta/signala/handlera/cleara
i nedostajućeg realnog rendera. Nakon implementacije i error-envelope guarda:
fokusirani finalni run `49 passed, 1 warning`.

## Code intelligence i blast radius

Aktuelna politika je ispoštovana: GitNexus nije pozivan niti reaktiviran.
Graft `blast` je prijavio `0 impacted symbols`; po politici je to **UNKNOWN**, ne
LOW. Zato su zaključci potvrđeni exhaustive `rg` pretragom i direktnim čitanjem
svih pozivalaca `_load_project_data`, `_clear_project_screens`, `_on_tasks`,
`get_tasks`, `tasks_received` i `TasksPage`. Stvarni batch pozivaoci uključuju
project selection, refresh, worktree refresh i uspješan plan import.

Graft je tokom blast provjere regenerisao untracked `graft/` u worktreeju;
provjerena tačna putanja je uklonjena prije commita. Eksterni sibling indeks
nije dio repozitorija niti commita.

## Verifikacija

- `python -m pytest -p no:cacheprovider tests/gui/test_project_selection.py
  tests/gui/test_api_client_auth.py tests/integration/test_projects_tasks_api.py -q`
  → `49 passed, 1 warning`.
- Širi GUI + relevantni backend run → `75 passed, 1 warning`.
- `python scripts/verify.py` nakon finalnog formatiranja → `8/8 PASS`:
  207 fajlova formatirano, ruff clean, mypy 139 source fajlova, architecture
  guard PASS, 10 architecture testova PASS, 591 unit/integration/contract
  testova PASS, migrations PASS, Alembic round-trip PASS.
- Jedina warning stavka je postojeći Starlette `httpx` deprecation warning.

## LIVE dokaz

Izolovan FastAPI `/tasks` controller + stvarni `TaskService` radio je nad
privremenom SQLite bazom na loopbacku; stvarni `GuiApiClient` je asinhrono
napunio vidljivi Qt `Zadaci` ekran. Runtime dokaz:

```text
LIVE_PASS
rows=[
  ['Unassigned backend task', 'OPEN', 'NORMAL', 'Nije vezano za plan', 'task-free'],
  ['Linked backend task', 'IN_PROGRESS', 'HIGH', 'FLOW-1202', 'task-linked']
]
```

Screenshot: `H:/FlowOS-worktrees/FLOW-1202-live-proof.png` (izvan repozitorija).
Korisnička FlowOS baza nije čitana ni mijenjana. Prva dva pokušaja harnessa nisu
prihvaćena kao dokaz (nedostajući `PYTHONPATH`, zatim prerani paint/order assert);
finalni pokušaj je ispisao `LIVE_PASS`, a screenshot je zasebno vizuelno pregledan.
Nakon dokaza harness je zapeo na postojećem modalnom window-close toku, pa je
ugašen samo vlastiti proces; backend/GUI behavioral asserti i screenshot su već
bili završeni.

## Nezavisni review

**PASS** nad tačnim implementation HEAD-om
`7d07d8aa9a4482782cb79560d5b9ad2ac51ad05e`. Fresh reviewer nije našao
CRITICAL, IMPORTANT ni MINOR nalaze. Nezavisno je dobio:

- fokusirani paket: `56 passed`, jedna postojeća Starlette warning stavka;
- `python scripts/verify.py`: `8/8 PASS`, uključujući 591 test;
- vlastiti `FRESH_LIVE_PASS` tok: privremeni SQLite → stvarni FastAPI `/tasks`
  → loopback HTTP → stvarni `GuiApiClient`/Qt network → `TasksPage`;
- adversarial potvrdu da generation 3 ostaje prikazana nakon generation 1 i
  odgovora drugog projekta;
- svih devet acceptance kriterija: PASS.

Review je bio read-only; reviewer nije mijenjao fajlove, DB ili Git istoriju.

## Main / FlowOS state

- `main` nije izmijenjen.
- Nema pusha, mergea, DB/status/ledger promjene, Human ACCEPT-a niti CLOSED-a.

## Handoff

```text
CILJ: Povezati postojeći Zadaci ekran sa stvarnim project-scoped /tasks readom.
URAĐENO: Implementacija, lokalna verifikacija i fresh independent review PASS.
NE DIRATI: FLOW-1203/1204, FlowOS DB/status/ledger, main i merge.
SLJEDEĆE: STOP za Human Owner ACCEPT / NEEDS_WORK odluku.
```
