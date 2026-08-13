---
flowos_report_version: 1
agent: codex
model: gpt-5
session_id: unknown
report_id: a1b45fc7-9517-47a8-9b02-7b9ad200efcf
report_type: analysis
tasks:
  - FLOW-1101
commits: []
created_at: 2026-08-12T22:03:42+02:00
---

# FLOW-1101 — Backend startup QueuePool root-cause analysis

READ ONLY analiza nad baselineom:

```text
33d2f32415e3866d6b55186416b840ad10c9162a
33d2f32 feat: add workflow ledger task decisions
```

Nisam mijenjao kod. Nisam mijenjao plan. Nisam pravio commit. Nisam pushovao.

Git status prije analize nije bio čist zbog već postojećih untracked artefakata iz prethodnih read-only zadataka i dogfooding plana; nisu dirani.

## Reprodukcija

Kvar je reprodukovan izolovano, bez korištenja stvarne FlowOS baze:

- privremeni SQLite fajl;
- isti pool oblik: `pool_size=1`, `max_overflow=0`;
- skraćen `pool_timeout=1` da se ne čeka 30s;
- stvarni `_scan_existing_agent_reports_for_project()`;
- stvarni `AgentReportIngestionService`;
- stvarni ORM modeli.

Reprodukcioni tok:

```text
1. Kreiran Project sa repo_path koji ima agent_reports/*.md.
2. Otvorena startup session: init_db = SessionLocal()
3. Pozvano: init_db.query(Project).all()
4. Pool status: Current Checked out connections: 1
5. Bez zatvaranja init_db pozvan _scan_existing_agent_reports_for_project(...)
6. Startup scan otvara novu session i ulazi u AgentReportIngestionService.ingest_file(...)
7. Prvi DB query u _check_identity() timeoutuje:
   QueuePool limit of size 1 overflow 0 reached
```

Reprodukcioni izlaz:

```text
SCENARIO current_startup_scope
after project query: Pool size: 1  Connections in pool: 0 Current Overflow: 0 Current Checked out connections: 1
scan result len: 0
log: AgentReport startup ingestion nije uspio: ...\agent_reports\2026-08-12_repro.md
```

Kontrolni scenario, isti kod scan-a ali sa zatvorenim `init_db` prije scan-a:

```text
SCENARIO release_before_scan
after project query: Pool size: 1  Connections in pool: 0 Current Overflow: 0 Current Checked out connections: 1
after init_db close: Pool size: 1  Connections in pool: 1 Current Overflow: 0 Current Checked out connections: 0
scan result len: 1
log: AgentReport startup ingestion: NEEDS_LINK ...
```

To potvrđuje da je prva konekcija zauzeta startup project-listing sessionom, a ne ingestion/ledger servisom samim po sebi.

## ROOT CAUSE

Tačan tok:

1. `create_app()` u `src/flowos/service/composition_root.py` kreira jedan engine i jedan `session_factory`.
2. Engine iz `src/flowos/service/services/infrastructure/persistence/engine.py` koristi:

   ```text
   pool_size=1
   max_overflow=0
   ```

3. Lifespan startup u `composition_root._make_lifespan()` otvara startup session:

   ```python
   init_db = app.state.session_factory()
   ```

4. Zatim učitava projekte:

   ```python
   projects = init_db.query(Project).all()
   ```

5. Taj query checkoutuje jedinu SQLAlchemy/SQLite konekciju iz pool-a. Session ostaje otvoren i transakcija/connection ownership se ne vraća pool-u do `finally: init_db.close()`.
6. Dok `init_db` još drži konekciju, kod ulazi u:

   ```python
   for proj in projects:
       ...
       _scan_existing_agent_reports_for_project(
           proj.id,
           proj.repo_path,
           app.state.session_factory,
           logger,
       )
   ```

7. `_scan_existing_agent_reports_for_project()` za svaki report otvara novu DB session:

   ```python
   db = session_factory()
   result = AgentReportIngestionService(db).ingest_file(...)
   ```

8. `AgentReportIngestionService.ingest_file()` parsira fajl i zatim prvi put traži DB konekciju u `_check_identity()`:

   ```python
   self._session.query(AgentReport)
       .filter(AgentReport.source_report_id == front_matter.report_id)
       .first()
   ```

9. Pool nema slobodnu konekciju, jer je jedina konekcija još checkoutovana od `init_db`.
10. Pošto je `max_overflow=0`, SQLAlchemy ne smije otvoriti drugu konekciju.
11. Nakon timeout-a nastaje:

   ```text
   sqlalchemy.exc.TimeoutError:
   QueuePool limit of size 1 overflow 0 reached
   ```

## CONNECTION OWNERSHIP

Konekciju drži:

```text
composition_root._make_lifespan()
  init_db = app.state.session_factory()
  projects = init_db.query(Project).all()
```

Kada:

- od trenutka `init_db.query(Project).all()` u startup-u;
- kroz cijelu `for proj in projects:` petlju;
- sve do `finally: init_db.close()`.

Zašto:

- SQLAlchemy Session koristi autobegin ponašanje;
- prvi ORM query checkoutuje connection;
- connection ostaje vezana za session dok se session ne commit/rollback/close;
- kod ne zatvara `init_db` prije pokretanja per-project startup work-a koji otvara nove sessione.

Nije primarni vlasnik:

- `AgentReportIngestionService`;
- `ReportService`;
- `WorkflowLedgerService`;
- watcher callback.

Ti servisi u ovom toku koriste session koji dobiju izvana. Problem nastaje prije njih: druga session ne može dobiti konekciju jer startup listing session još nije vraćena u pool.

## SECOND CONNECTION REQUEST

Drugu konekciju traži:

```text
_scan_existing_agent_reports_for_project()
  db = session_factory()
  AgentReportIngestionService(db).ingest_file()
    _check_identity()
      self._session.query(AgentReport).first()
```

Zašto:

- startup scan namjerno koristi novi session scope po report fajlu;
- to je samo po sebi validan pattern ako prethodna startup session ne drži jedinu pool konekciju;
- prva DB operacija u ingestion-u je source identity check nad `AgentReport`.

U reprodukciji je timeout nastao baš na:

```text
src/flowos/service/services/reports/ingestion.py:178-181
existing_by_id = self._session.query(AgentReport)...
```

## Provjera posebnih hipoteza

### Nested Session usage

Potvrđeno na startup composition nivou.

Nije klasičan “service otvara novu Session iznutra”; `AgentReportIngestionService`, `ReportService` i `WorkflowLedgerService` koriste session koji im je proslijeđen.

Ali startup composition drži `init_db` session otvorenu dok poziva helper koji otvara novu session. To je efektivno nested session scope preko istog pool-a.

### Servis koji otvara novu Session unutar postojeće transakcije

Nije nađeno u `AgentReportIngestionService`/`ReportService`/`WorkflowLedgerService`.

Nađeno je u caller granici:

```text
lifespan startup session ostaje otvoren
→ startup scan otvara novu session po reportu
```

### Iterator/query drži konekciju dok ingestion otvara novu Session

Da, potvrđeno.

`init_db.query(Project).all()` nije streaming iterator, ali `Session` poslije `.all()` i dalje drži connection/transaction dok se ne zatvori. Reprodukcioni pool status poslije project query-a:

```text
Current Checked out connections: 1
```

### Startup composition koristi više session scope-ova

Da.

Jedan scope:

```text
init_db u _make_lifespan()
```

Drugi scope:

```text
db u _scan_existing_agent_reports_for_project()
```

Drugi scope nastaje prije zatvaranja prvog.

### Watcher/startup concurrency

Watcher se pokreće prije startup scan-a:

```python
w.start(proj.repo_path)
...
_scan_existing_agent_reports_for_project(...)
```

To može dodatno povećati šansu za pool contention ako watcher event dođe tokom startup-a. Međutim, reprodukcija dokazuje da watcher concurrency nije potreban da kvar nastane. Root cause je dovoljan i bez watcher eventa: otvoreni `init_db` + novi scan session + pool size 1.

### Commit/rollback/close lifecycle

`_scan_existing_agent_reports_for_project()` pravilno radi `commit/rollback/close` nad svojom `db` session.

Ali to ne pomaže jer nova session ne može ni dobiti connection. Ključni lifecycle problem je što se `init_db.close()` dešava tek poslije cijelog watcher/scan loop-a.

## MINIMAL FIX

Minimalna ispravna granica popravke:

```text
U _make_lifespan(), session koja služi samo za učitavanje Project liste
mora biti zatvorena prije pokretanja watcher-a i startup AgentReport scan-a.
```

Konkretno:

1. U startup-u otvoriti `init_db`.
2. Učitati samo potrebne immutable vrijednosti iz projekata, npr:

   ```text
   [(project.id, project.repo_path), ...]
   ```

3. Odmah zatvoriti `init_db`.
4. Tek zatim u posebnoj petlji pokrenuti watcher i `_scan_existing_agent_reports_for_project(...)`.

Primjer oblika popravke:

```python
project_rows = []
init_db = app.state.session_factory()
try:
    project_rows = [(p.id, p.repo_path) for p in init_db.query(Project).all()]
except Exception:
    logger.exception("Greška pri učitavanju projekata za watcher-e")
finally:
    init_db.close()

for project_id, repo_path in project_rows:
    ...
    _scan_existing_agent_reports_for_project(
        project_id,
        repo_path,
        app.state.session_factory,
        logger,
    )
```

Još čišća varijanta je query samo kolona, ne ORM objekata:

```python
project_rows = init_db.query(Project.id, Project.repo_path).all()
```

Ne preporučujem “rješenje” povećanjem `pool_size`. To bi sakrilo lifecycle bug i ne bi riješilo pogrešnu granicu startup session ownership-a.

## FILES THAT WOULD CHANGE

Minimalno:

```text
src/flowos/service/composition_root.py
```

Testovi:

```text
tests/integration/test_composition_root.py
```

ili:

```text
tests/integration/test_agent_report_ingestion.py
```

Bolje mjesto za regresiju je `test_composition_root.py`, jer kvar nije u ingestion parseru nego u lifespan/composition session boundary-ju.

Ne bi trebalo mijenjati:

```text
src/flowos/service/services/infrastructure/persistence/engine.py
src/flowos/service/services/reports/ingestion.py
src/flowos/service/services/reports/service.py
src/flowos/service/services/workflow/ledger.py
```

## SEMANTICS IMPACT

Popravka može biti izvedena bez mijenjanja AgentReport ingestion i Workflow Ledger semantike.

Zašto:

- isti `AgentReportIngestionService.ingest_file()` ostaje jedini ingestion path;
- isti source identity/idempotency/immutable conflict logic ostaje netaknut;
- isti `ReportService.link_report_to_binding()` ostaje netaknut;
- isti `WorkflowLedgerService.append_implementation_completed_from_report()` i `append_review_completed_from_report()` ostaju netaknuti;
- mijenja se samo lifetime startup project-listing session-a.

Eventualna diskusija o redoslijedu watcher start vs startup scan može biti odvojena, ali nije potrebna za minimalnu FLOW-1101 popravku. Root-cause fix je release `init_db` connection prije per-project scan-a.

## TEST PLAN

Minimalni testovi:

1. Reprodukcioni regression test za startup session boundary:
   - koristiti file-backed SQLite engine sa `pool_size=1`, `max_overflow=0`, kratkim `pool_timeout`;
   - kreirati Project čiji `repo_path/agent_reports` sadrži validan report front matter;
   - simulirati startup project query;
   - potvrditi da novi/fiksirani startup tok zatvara listing session prije `_scan_existing_agent_reports_for_project()`;
   - očekivanje: nema `QueuePool TimeoutError`, scan vraća kontrolisan ingestion outcome.

2. Negativna/protective provjera postojećeg bug path-a može ostati kao dokumentovan reprodukcioni helper ili test koji bi failovao na starom kodu:
   - držati `init_db` otvoren poslije `query(Project).all()`;
   - pozvati `_scan_existing_agent_reports_for_project()`;
   - potvrditi da staro ponašanje timeoutuje kada pool ima jednu konekciju.

3. Postojeći ingestion regression testovi:
   - `tests/integration/test_agent_report_ingestion.py`;
   - posebno startup scan + watcher no-op slučaj.

4. Full relevant verify nakon popravke:
   - AgentReport ingestion testovi;
   - Workflow Ledger 3A/3C review-completed testovi;
   - session completion testovi ako startup change dodirne service composition.

## Zaključak

```text
ROOT CAUSE:
Lifespan startup drži init_db SQLAlchemy Session otvorenu nakon Project query-a.
Ta session drži jedinu SQLite pool konekciju, a startup AgentReport scan
otvara drugu Session prije init_db.close().

CONNECTION OWNERSHIP:
init_db u composition_root._make_lifespan(), od query(Project).all()
do finally init_db.close().

SECOND CONNECTION REQUEST:
AgentReportIngestionService._check_identity() tokom startup scan-a,
preko nove db session kreirane u _scan_existing_agent_reports_for_project().

MINIMAL FIX:
Materijalizovati project id/repo_path listu i zatvoriti init_db prije
watcher/startup scan loop-a; ne povećavati pool_size kao default rješenje.
```

Finalni verdict:

```text
FLOW-1101 ROOT CAUSE CONFIRMED
```
