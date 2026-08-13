---
flowos_report_version: 1
report_id: 03dad147-a542-4893-90d9-e4380b6fb308
agent: claude
model: claude-sonnet-5
session_id: unknown
report_type: review
work_status: completed
tasks:
  - FLOW-1101
commits: []
created_at: 2026-08-13T06:35:55+02:00
---

# FLOW-1101 — Backend startup QueuePool fix, independent review

## Scope

READ ONLY. Nije mijenjan kod, nisu popravljani testovi, nije pravljen commit, nije
pushovano. Cilj: nezavisno potvrditi da je FLOW-1101 popravka tačna, minimalna, i
da ne mijenja zaključanu AgentReport/Workflow Ledger semantiku.

Baseline: `33d2f32`.

## 1. Scope

```
git status --short
 M src/flowos/service/composition_root.py
 M tests/integration/test_composition_root.py
?? agent_reports/2026-08-12-FLOW-1101-startup-queuepool-analysis.md
?? agent_reports/2026-08-12-dogfooding-plan-pre-import-check.md
?? agent_reports/2026-08-12-flowos-current-gui-runtime-review.md
?? agent_reports/2026-08-13-FLOW-1101-startup-queuepool-implementation.md
?? agent_reports/gui_runtime_2026-08-12/
?? docs/FlowOS-plan-faze-11-15-dogfooding-v2.md
?? docs/FlowOS-plan-faze-11-15-dogfooding.md
```
```
git diff --stat
 src/flowos/service/composition_root.py     | 53 ++++++++++--------
 tests/integration/test_composition_root.py | 89 ++++++++++++++++++++++++++++++
 2 files changed, 119 insertions(+), 23 deletions(-)
```

**Jedini dozvoljeni produkcijski fajl je stvarno jedini izmijenjeni produkcijski
fajl.** Test fajl odgovara očekivanom. Neotraćeni `docs/*` i drugi `agent_reports/*`
fajlovi nisu dio FLOW-1101 diff-a (nisu produkcijski kod, ne utiču na review) — nije
scope deviation, ali se ne odnose na FLOW-1101.

**Nema scope deviation.**

## 2. Root cause fix

Pročitan pun diff `composition_root.py`. Prije popravke: `init_db.query(Project).all()`
vraća pune ORM instance, a `for proj in projects:` petlja (watcher start +
`_scan_existing_agent_reports_for_project()` poziv za svaki projekat) je bila
UNUTAR istog `try` bloka kao `init_db` — `finally: init_db.close()` se izvršavao
tek NAKON cijele petlje. To znači da je listing sesija držala jedinu pool
konekciju (`pool_size=1, max_overflow=0`) tokom cijelog scan-a, dok je scan
pokušavao otvoriti SVOJU sesiju za `ingest_file()`.

Poslije popravke, tačan redoslijed:
1. `init_db = app.state.session_factory()` — otvara DB.
2. `project_rows = init_db.query(Project.id, Project.repo_path).all()` — samo
   skalarne kolone (ne pune ORM instance).
3. `project_rows = [(row.id, row.repo_path) for row in project_rows]` —
   materijalizacija u plain tuple-e, PRIJE close-a.
4. `finally: init_db.close()` — listing sesija se zatvara ODMAH nakon
   materijalizacije, PRIJE watcher/scan petlje.
5. `for project_id, repo_path in project_rows:` — petlja (watcher start +
   `_scan_existing_agent_reports_for_project()`) je STRUKTURALNO IZVAN i NAKON
   `try/finally` bloka.

`_scan_existing_agent_reports_for_project()` se poziva isključivo iz koraka 5,
koji dolazi POSLIJE koraka 4 — nemoguće je da se pozove dok listing sesija još
drži konekciju, jer `finally` garantuje close prije nego što se izvršenje uopšte
stigne do petlje.

**Potvrđeno probe-om**: simulacija STAROG ponašanja (listing sesija ostaje otvorena
dok se poziva `_scan_existing_agent_reports_for_project`, isti `pool_size=1,
max_overflow=0, pool_timeout=2`) proizvodi tačno:
```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 1 overflow 0 reached,
connection timed out, timeout 2.00
```
unutar `ingest_file()` → `_check_identity()`. Ovo dokazuje i dijagnozu root cause-a
i da popravka (zatvaranje listing sesije prije petlje) direktno adresira taj uzrok.

**Potvrđeno.**

## 3. Connection ownership

`project_rows` sadrži plain `(str, str)` tuple-e (id, repo_path), ne ORM `Project`
instance. Petlja koristi `project_id, repo_path` direktno kao stringove — nema
`.id`/`.repo_path` atributskog pristupa na ORM objektu nakon `init_db.close()`,
dakle nema lazy-load rizika.

**Nema lazy ORM pristupa poslije close-a. Nije BLOCKER.**

## 4. No pool workaround

```
grep -rn "pool_size|max_overflow|pool_timeout" src/
src\flowos\service\composition_root.py:348:  (komentar, ne kod)
src\flowos\service\services\infrastructure\persistence\engine.py:43: pool_size=1,
src\flowos\service\services\infrastructure\persistence\engine.py:44: max_overflow=0,
```

`engine.py` (gdje se produkcijski engine kreira) NIJE u listi izmijenjenih fajlova
(potvrđeno u Section 1 — `git diff --stat` pokazuje samo 2 fajla). `pool_size=1,
max_overflow=0` ostaju netaknuti.

**Potvrđeno — FLOW-1101 je session-lifetime fix, ne capacity workaround.**

## 5. Semantics boundary

Pošto je jedini produkcijski fajl `composition_root.py`, a `ReportService`,
`WorkflowLedgerService`, `WorkflowDecisionService`, `AgentReportIngestionService`
i `report_models.py`/`workflow_ledger_models.py` NISU u `git diff --stat` listi —
njihova semantika je **kodom dokazano nepromijenjena** (0 izmijenjenih linija).

Sam diff u `composition_root.py` ne dira `_scan_existing_agent_reports_for_project()`
ni `_make_watcher_callback()` interno (potvrđeno čitanjem punog diff-a — jedina
izmjena je REDOSLIJED i NAČIN učitavanja `project_rows` prije petlje; tijela
funkcija koje se pozivaju su identična pozivima iz prije popravke).

**Potvrđeno — AgentReport ingestion identity/idempotency, ReportService,
AgentReportBindingLink, IMPLEMENTATION_COMPLETED, REVIEW_COMPLETED,
WorkflowLedgerService semantika nisu dirani.**

## 6. Regression test quality

Pročitan `TestStartupSessionBoundary::test_startup_scan_releases_listing_connection`
(`test_composition_root.py:446-534`). Potvrđeno:

- **file-backed SQLite**: `db_path` fixture koristi `tempfile.NamedTemporaryFile
  (suffix=".db")` — stvaran fajl na disku, ne `:memory:`.
- **pool_size=1, max_overflow=0, pool_timeout=2** — tačno kao produkcijski engine.
- **Stvaran `Project`** — upisan u zasebnoj sesiji, commit-ovan, sesija zatvorena.
- **Stvaran `agent_reports/*.md` fajl** — pravi front matter (validan `report_id`
  UUID, `report_type: implementation`, `work_status: completed`).
- **Stvaran startup scan helper**: poziva se pravi
  `_scan_existing_agent_reports_for_project()` (import iz `composition_root`), ne
  mock.
- **Stvaran `AgentReportIngestionService`**: `_scan_existing_agent_reports_for_project`
  interno poziva pravi `ingest_file()`.

Test eksplicitno provjerava `pool.checkedout() == 0` NAKON `listing_db.close()` —
direktna provjera INTERNOG STANJA POOL-a (ne mock assertion), zatim poziva pravi
scan i provjerava `len(results) == 1` sa smislenim outcome-om
(`NEEDS_LINK`/`INGESTED`/`ALREADY_INGESTED`) — dokaz da je scan stvarno dobio
konekciju i prošao kroz pravi ingestion put, ne samo da funkcija "nije pukla".

**Nijansa (ne blokira)**: test rekonstruiše isti listing→close→scan obrazac
UNUTAR test tijela, umjesto da direktno pozove `_make_lifespan()` iz
`composition_root.py` (ASGI lifespan hook je težak za izolovano testiranje bez
punog app+event loop-a). To znači da test dokazuje da JE OBRAZAC ISPRAVAN (i
empirijski, mojim probe-om, da suprotan obrazac stvarno puca), ali ne izvršava
direktno izmijenjeni kod unutar `_make_lifespan()`. Ispravnost stvarnog koda u
`_make_lifespan()` je potvrđena čitanjem (Section 2), ne izvršavanjem ovog testa.
Ovo je MEDIUM nalaz (test coverage gap), ne HIGH/BLOCKER — test SAM PO SEBI ne može
proći bez stvarnog release-a konekcije (potvrđeno eksplicitnom `pool.checkedout()`
provjerom), što je tačno kriterijum iz zahtjeva.

**Test nije `mock.assert_called_once()` tipa — potvrđen kao pravi behavior test.**

## 7. Fresh tests

```
python -m pytest tests/integration/test_composition_root.py::TestStartupSessionBoundary::test_startup_scan_releases_listing_connection -v --tb=short
1 passed in 1.86s
```

```
python -m pytest tests/integration/test_agent_report_ingestion.py -v --tb=short
26 passed in 2.57s
```

```
python -m pytest tests/integration/test_workflow_ledger_phase3a.py tests/integration/test_workflow_ledger_phase3c.py -v --tb=short
39 passed in 2.16s  (17 + 22)
```

Sve zeleno, 0 failed.

## 8. Full verify

```
python scripts/verify.py
[PASS] 1. Ruff format check
[PASS] 2. Ruff lint
[PASS] 3. mypy
[PASS] 4. Architecture boundaries
[PASS] 5. Unit tests
[PASS] 6. Migrations check
[PASS] 7. Alembic round-trip
Prošlo: 7/7
```

**7/7 PASS.**

## 9. Live runtime proof

Servis pokrenut na normalan podržan razvojni način (`python -c "from
flowos.service.app import main; main()"`, ekvivalent `flowos-service` console
script entry pointa iz `pyproject.toml`).

- **Proces živ**: `tasklist` potvrđuje `python.exe` PID 23600.
- **Runtime descriptor postoji**: `%LOCALAPPDATA%\FlowOS\runtime\service.json` sa
  `{"pid": 23600, "port": 9100, "status": "running", ...}`.
- **Port stvarno sluša**: `netstat -ano` → `TCP 127.0.0.1:9100 LISTENING 23600`.
- **`/health` vraća HTTP 200**: `{"status":"ok","uptime":13.65...}`.
- **`/runtime` se poklapa sa descriptorom**: `{"pid":23600,"port":9100,...}`.

**QueuePool timeout tokom startup AgentReport scan-a**: pretražen kompletan novi
log izlaz (od trenutka starta servisa do kraja startup scan-a, ~2150+ linija) za
`QueuePool`/`TimeoutError` — **0 pojavljivanja**. Scan je obradio sve `agent_reports/*.md`
fajlove u repou (desetine fajlova, i legacy i front-matter formata) i završio
normalno, nakon čega je servis prešao u normalan watcher/reconciliation rad
(`Reconciliation: promene detektovane...`). Servis je nakon toga zaustavljen
(`taskkill /F`, moj vlastiti test proces) — nije ostavljen da radi u pozadini.

**QueuePool timeout se više NE pojavljuje tokom startup AgentReport scan-a —
potvrđeno stvarnim pokretanjem, ne samo testom.**

## 10. Novi SQLite schema blocker

Implementation report navodi `sqlite3.OperationalError: no such column:
agent_reports.report_type`. Provjereno direktno na live lokalnoj bazi:

```
PRAGMA table_info(agent_reports) → kolone: id, session_id, agent_job_id, status,
scope, impact_summary, ..., user_verdict, user_notes, verdict_audit_json,
created_at, updated_at
report_type prisutan? False
```

```
SELECT version_num FROM alembic_version → 03de14cbf6aa
python -m alembic heads → b7c2e1d4a903 (head)
```

**A) Da li je odvojen problem od FLOW-1101**: DA. Greška se javlja UNUTAR
`ingest_file()` → identity provjere (`SELECT ... FROM agent_reports WHERE
source_report_id = ?`) — SQL greška na nivou kolone, ne greška dobijanja
konekcije iz pool-a. U logu se pojavljuje TEK nakon što je konekcija uspješno
dobijena (upit se uopšte izvršio i pukao na `no such column`, što je nemoguće bez
prethodno uspješno dobijene konekcije).

**B) Da li servis ipak dolazi do HEALTH PASS stanja**: DA, potvrđeno u Section 9
— `/health` je vratio HTTP 200 dok su ove greške već bile ispisane u logu (scan je
bio završen prije health provjere).

**C) Da li je QueuePool timeout uzrok ovog failure-a**: NE. Nula pojavljivanja
`QueuePool`/`TimeoutError` u cijelom log izlazu (Section 9). Greška je
isključivo `OperationalError: no such column`.

**D) Da li problem proizlazi iz lokalne postojeće baze bez novije schema kolone**:
DA, direktno dokazano — `PRAGMA table_info(agent_reports)` na živoj lokalnoj bazi
(`%LOCALAPPDATA%\FlowOS\data\flowos.db`) potvrđuje da `report_type` kolona
fizički ne postoji u toj tabeli, i da je baza na alembic reviziji `03de14cbf6aa`,
dok je trenutni migration head `b7c2e1d4a903` — baza je zaostala za više migracija.
Ovo NIJE nagađanje, dokazano je direktnim upitom na stvarnu bazu.

**Ovaj schema problem je potvrđeno odvojen od FLOW-1101 i NIJE pretvoren u
migration implementaciju u okviru ovog reviewa (nije dirana baza, nije pravljena
migracija).**

## 11. Finalni nalazi

**MEDIUM**

- **M1** — `tests/integration/test_composition_root.py:446-534`
  (`test_startup_scan_releases_listing_connection`). Test rekonstruiše
  listing→close→scan obrazac unutar test tijela umjesto da direktno pozove
  `_make_lifespan()` iz `composition_root.py`. **Zašto je važno**: regresija
  uvedena isključivo u glue kodu `_make_lifespan()` (npr. neko vrati scan petlju
  nazad unutar `try` bloka) ne bi bila uhvaćena ovim testom, jer test ne izvršava
  taj specifičan kod put. Produkcijski kod je nezavisno potvrđen ispravnim
  čitanjem (Section 2) i probe-om (Section 2), pa ovo NE mijenja verdict, ali je
  vrijedan test-coverage nalaz. **Minimalna ispravka**: dodati integracioni test
  koji stvarno pokreće `_make_lifespan()` (npr. preko `TestClient` lifespan
  context managera) sa istim pool ograničenjima, ili eksplicitno dokumentovati
  zašto se to izbjegava.

**LOW**

- **L1** — Postojeća lokalna baza developera (`%LOCALAPPDATA%\FlowOS\data\flowos.db`)
  je zaostala za migracijama (`03de14cbf6aa` vs head `b7c2e1d4a903`), što
  uzrokuje po-report ingestion greške tokom startup scan-a (odvojeno od
  FLOW-1101, dokumentovano u implementation reportu). Nije follow-up za ovaj
  review, ali vrijedi zabilježiti da servis TRENUTNO ne primjenjuje migracije
  automatski pri startup-u za postojeće developer instalacije — to je poznat,
  odvojen produktni rizik za buduću fazu, ne za FLOW-1101 scope.

Nema BLOCKER ni HIGH nalaza.

### Ocjena

```
ROOT CAUSE FIX = ACCEPT
REGRESSION TEST = ACCEPT
SEMANTICS PRESERVED = YES
LIVE QUEUEPOOL BLOCKER = CLOSED
NEW DB SCHEMA BLOCKER = CONFIRMED (odvojen problem, dokazano D)
```

```
FLOW-1101 = ACCEPT
```

**FLOW-1101 CLOSED — DATABASE SCHEMA BLOCKER IS A SEPARATE FOLLOW-UP**
