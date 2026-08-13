---
flowos_report_version: 1
report_id: b3d44452-fdb6-4a90-b845-d6d1e6ff4535
agent: codex
model: gpt-5
session_id: unknown
report_type: implementation
work_status: completed
tasks:
  - FLOW-1101A
commits: []
created_at: 2026-08-13T08:18:00.2115908+02:00
---

# FLOW-1101A — local DB schema repair implementation

## Datum

2026-08-13

## Agent / model / sesija

- Agent: Codex
- Model: gpt-5
- Sesija: unknown

## ARCHITECTURE DECISION

```text
DETECT + EXPLICIT SAFE REPAIR
```

FlowOS servis sada detektuje poznati lokalni schema drift prije runtime upotrebe baze, ali ne radi silent startup repair. Stvarna schema mutacija postoji samo kroz eksplicitnu developersku komandu.

## REAL LOCAL DB MODIFIED

```text
NO
```

Stvarna lokalna baza je na kraju read-only provjerena i ostala je u starom stanju:

```text
C:\Users\38765\AppData\Local\FlowOS\data\flowos.db
alembic_version = 03de14cbf6aa
agent_reports.report_type = missing
workflow_ledger_events = missing
```

## Scope

Implementiran je minimalni FLOW-1101A repair path:

- deterministic schema detector;
- eksplicitni repair CLI;
- backup-first repair;
- idempotentni repair poznatog hibridnog drift-a;
- unknown drift refusal;
- startup detection bez silent mutation;
- targeted regression testovi;
- full `scripts/verify.py`.

Van scope-a ostaje generalni DB architecture cleanup.

## Task contract / acceptance kriteriji

Acceptance kriteriji iz prompta:

- normal startup ne smije silent auto-repair;
- poznati drift mora biti detektovan prije AgentReport ingestion SQL pada;
- explicit repair mora prvo napraviti backup;
- unknown drift mora blokirati repair bez DDL/stamp-a;
- repair mora biti idempotent;
- postojeći podaci moraju preživjeti;
- AgentReport ORM i WorkflowLedgerEvent ORM moraju raditi nakon repair-a;
- Alembic version smije biti postavljen na `b7c2e1d4a903` samo nakon schema/ORM verifikacije;
- stvarna lokalna baza ne smije biti popravljena tokom implementacije;
- `scripts/verify.py` mora biti 7/7 PASS.

## GitNexus impact ili ručni blast radius

Pre-change GitNexus impact:

- `_run_migrations` u `src/flowos/service/app.py`
  - risk: LOW
  - direct caller: `main`
  - affected process: service main startup
- `_make_lifespan` u `src/flowos/service/composition_root.py`
  - risk: LOW
  - direct caller: `create_app`
  - nije mijenjan nakon procjene

Post-change `gitnexus_detect_changes(scope=all)`:

```text
changed symbols:
- src/flowos/service/app.py::_run_migrations
- src/flowos/service/app.py::main
- src/flowos/service/app.py::runtime

risk_level: medium
affected processes:
- Main → _acquire_windows_mutex
- Main → _acquire_unix_lock
- Main → _port_is_free
- Main → _utcnow_iso
```

Napomena: GitNexus detect_changes je mapirao tracked `app.py` diff. Novi untracked helper/test/report fajlovi su ručno uključeni u blast radius:

- `src/flowos/service/services/infrastructure/persistence/schema_repair.py`
- `tests/unit/test_schema_repair.py`
- ovaj agent report

Architecture-guard skill je korišten. `python scripts/guard_architecture.py` standalone prijavljuje 9 već postojećih prekršaja u drugim fajlovima, ali `scripts/verify.py` architecture suite je prošao 7/7. Novi `schema_repair.py` ne uvodi GUI/controller boundary prekršaj.

## Reprodukcija prije izmjene

Iz authoritative analysis reporta i read-only provjere:

```text
local DB alembic_version = 03de14cbf6aa
repo Alembic head = b7c2e1d4a903
agent_reports.report_type = missing
workflow_ledger_events = missing
standard alembic upgrade head on copy = FAIL, table projects already exists
```

Novi test `test_startup_detection_blocks_known_drift_before_legacy_bootstrap` reprodukuje poznati hibridni drift i dokazuje da `_run_migrations(db_path)` blokira prije legacy bootstrap/create_all pokušaja.

## Šta je urađeno

### SCHEMA DETECTOR

```text
implemented
```

Dodan je `inspect_local_schema()` u:

```text
src/flowos/service/services/infrastructure/persistence/schema_repair.py
```

Detector razlikuje:

```text
HEALTHY
KNOWN_REPAIRABLE_DRIFT
UNKNOWN_DRIFT
```

Ne oslanja se samo na `alembic_version`, nego provjerava stvarnu SQLite šemu:

- required hybrid tabele;
- `agent_reports` kolone;
- `agent_reports` source identity indekse;
- `agent_reports.work_status` check constraint;
- `workflow_ledger_events` tabelu;
- Workflow Ledger kolone/indekse/unique idempotency constraint;
- tipove i NOT NULL očekivanja za postojeće target kolone.

### EXPLICIT REPAIR COMMAND

```text
python -m flowos.service.services.infrastructure.persistence.schema_repair repair-db
```

Za test/kopiju može se koristiti:

```text
python -m flowos.service.services.infrastructure.persistence.schema_repair repair-db --db-path <path-to-copy.db>
```

Komanda radi:

1. inspect;
2. refusal za UNKNOWN_DRIFT;
3. backup;
4. repair;
5. schema verification;
6. Alembic stamp;
7. ORM access verification;
8. JSON-ish success output.

### BACKUP

```text
implemented
```

`create_schema_backup()` koristi SQLite backup API za sadržaj baze i čuva WAL/SHM fajlove ako postoje. Backup direktorijum je collision-safe:

```text
<db-dir>/backups/schema-repair-<timestamp>-<uuid>/
```

Repair ne počinje ako backup padne.

### KNOWN HYBRID REPAIR

```text
PASS
```

Repair za poznatu hibridnu bazu:

- rebuilda `agent_reports` tabelu sa v2/source identity kolonom i `work_status` check constraintom;
- čuva postojeće `agent_reports` redove;
- rekreira `ix_agent_reports_session_id`, `ix_agent_reports_status`, `ix_agent_reports_source_report_id`, `ix_agent_reports_source_path`;
- kreira `workflow_ledger_events` sa target kolonom, unique idempotency constraintom i očekivanim indeksima;
- stampuje `alembic_version` na `b7c2e1d4a903` tek nakon schema verification-a;
- verifikuje ORM query nad `AgentReport` i `WorkflowLedgerEvent`.

### UNKNOWN DRIFT REFUSAL

```text
PASS
```

Test sa namjerno inkompatibilnom kolonom `agent_reports.source_path INTEGER` odbija repair, ne pravi DDL i ne stampuje head.

### IDEMPOTENCY

```text
PASS
```

Drugi repair nad već repaired bazom je safe no-op:

- nema duplih kolona;
- nema duplih indeksa;
- nema data mutation;
- version ostaje head.

### DATA PRESERVATION

```text
PASS
```

Targeted test seeduje reprezentativne:

- `Project`
- `PlanItem`
- `Task`
- `AgentSession`
- legacy `AgentReport`
- `SessionTaskBinding`
- `AgentReportBindingLink`

Provjereno je da ID-jevi i reprezentativne vrijednosti preživljavaju repair.

### Startup detection

`src/flowos/service/app.py::_run_migrations()` sada prvo poziva schema detector.

Ako je DB:

- `HEALTHY`: legacy bootstrap nastavlja kao ranije;
- `KNOWN_REPAIRABLE_DRIFT`: startup se zaustavlja sa jasnom porukom i repair komandom;
- `UNKNOWN_DRIFT`: startup se zaustavlja sa jasnom nepoznat-drift porukom.

Nema automatskog repair-a pri startup-u.

## Zašto je urađeno

Zato što je stvarna lokalna baza hibrid: `create_all()` je napravio dio novijih tabela, ali Alembic stamp je ostao baseline i postojeće tabele nisu dobile nove kolone. Slijepi `alembic upgrade head` na takvoj bazi pada. Minimalna sigurna granica je eksplicitni repair koji prvo dokazuje da je drift poznat i additivan.

## Kako je urađeno

Implementacija koristi:

- SQLite read-only introspekciju za detection;
- SQLite backup API prije DDL-a;
- SQLite table rebuild za `agent_reports`, jer CHECK constraint nije sigurno dodati običnim `ALTER TABLE ADD COLUMN`;
- direktni deterministički DDL za postojeći Alembic head target;
- schema verification prije stamp-a;
- ORM verification nakon stamp-a;
- no-op put za već healthy/repaired bazu.

Nije korišten LLM/AI za workflow činjenice i nije uveden novi migration head.

## Izmijenjeni fajlovi i ponašanje

Promijenjeni/dodani fajlovi u FLOW-1101A scope-u:

```text
src/flowos/service/app.py
src/flowos/service/services/infrastructure/persistence/schema_repair.py
tests/unit/test_schema_repair.py
agent_reports/2026-08-13-FLOW-1101A-local-db-schema-repair-implementation.md
```

Ponašanje:

- service startup više ne pušta poznati schema drift da padne kasnije kroz `no such column` / `no such table`;
- repair se ne radi implicitno;
- developer dobija eksplicitnu komandu za repair;
- repair nad stvarnom DB nije izvršen u ovoj implementaciji.

## Šta nije dirano

Nije dirano:

- stvarna lokalna baza;
- AgentReport service logic;
- WorkflowLedgerService logic;
- Alembic migration fajlovi;
- Workflow Ledger semantika;
- AgentReport semantika;
- GUI repair UX;
- globalni `create_all()` / Alembic redesign;
- globalna test DB strategija;
- historijski backfill;
- Git commit/push.

## Verifikacija i stvarni rezultat

### TARGETED TESTS

```text
pytest tests/unit/test_schema_repair.py -v --tb=short --no-header
6 passed in 4.74s
```

Poslije format/mypy popravke:

```text
pytest tests/unit/test_schema_repair.py -q
6 passed in 4.45s
```

### RELEVANT REGRESSIONS

AgentReport ingestion + Workflow Ledger Phase 3A/3C/3D:

```text
pytest tests/integration/test_agent_report_ingestion.py \
       tests/integration/test_workflow_ledger_phase3a.py \
       tests/integration/test_workflow_ledger_phase3c.py \
       tests/integration/test_workflow_ledger_phase3d.py \
       -v --tb=short --no-header
93 passed in 6.52s
```

Composition root/startup:

```text
pytest tests/integration/test_composition_root.py -v --tb=short --no-header
9 passed, 1 warning in 15.52s
```

Alembic round-trip:

```text
python scripts/verify_roundtrip.py
[PASS] Round-trip na privremenoj bazi
```

Lint/type targeted:

```text
ruff check src/flowos/service/services/infrastructure/persistence/schema_repair.py \
           src/flowos/service/app.py \
           tests/unit/test_schema_repair.py
All checks passed!

python -m mypy src --explicit-package-bases
Success: no issues found in 133 source files
```

### scripts/verify.py

```text
7/7
```

Fresh output:

```text
[PASS] 1. Ruff format check
[PASS] 2. Ruff lint
[PASS] 3. mypy
[PASS] 4. Architecture boundaries
[PASS] 5. Unit tests
[PASS] 6. Migrations check
[PASS] 7. Alembic round-trip

Prošlo: 7/7
[PASS] VERIFIKACIJA PROŠLA
```

Full test count u verify:

```text
468 passed, 1 warning
```

Warning:

```text
StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated
```

Nije povezan sa FLOW-1101A promjenom.

## Nezavisna provjera

Nije rađena nezavisna agentska provjera u ovoj sesiji. Implementacija je spremna za independent review nakon full verify 7/7.

## Pronađeni problemi

### FLOW-1101A-F1

- severity: MEDIUM
- fajl: `src/flowos/service/app.py`
- dokaz: startup mora blokirati poznati drift prije ingestion-a
- uticaj: mijenja service startup failure mode za poznatu hibridnu bazu
- status: riješeno targeted testom `test_startup_detection_blocks_known_drift_before_legacy_bootstrap`

### FLOW-1101A-F2

- severity: MEDIUM
- fajl: `schema_repair.py`
- dokaz: `agent_reports` CHECK constraint ne može biti sigurno dodat samo običnim additive ALTER-om
- uticaj: repair mora raditi table rebuild uz data preservation
- status: riješeno rebuildom + data preservation testom

### FLOW-1101A-F3

- severity: LOW
- fajl: `scripts/guard_architecture.py` output
- dokaz: standalone guard prijavljuje 9 postojećih service→controller import prekršaja u drugim fajlovima
- uticaj: nije novo i nije dio FLOW-1101A; `tests/architecture` u full verify prolazi 7/7
- status: deferred / out of scope

## Odbačene opcije

### Silent startup repair

- zašto razmatrano: najlakše bi uklonilo runtime grešku
- zašto odbačeno: locked contract zabranjuje silent auto-repair
- kada ponovo otvoriti: samo novom product odlukom

### Slijepi `alembic upgrade head`

- zašto razmatrano: standardni migration path
- zašto odbačeno: već dokazano pada na hibridnoj kopiji sa `table projects already exists`
- kada ponovo otvoriti: ne za ovaj hibrid bez prethodnog repair/stamp plana

### Slijepi `alembic stamp head`

- zašto razmatrano: riješio bi stale version
- zašto odbačeno: sakrio bi missing kolone/tabelu bez fizičke schema verifikacije
- kada ponovo otvoriti: nikad kao blind korak; samo nakon verify target schema

### Nova Alembic migracija

- zašto razmatrano: mogla bi formalizovati repair
- zašto odbačeno: target head schema već postoji; problem je lokalni hibridni drift, ne nova schema
- kada ponovo otvoriti: samo ako independent review nađe da current head migration contract nije dovoljan

## Konflikti/kontradiktorni izvori

Nema kontradikcije sa promptom. Prompt zaključava `DETECT + EXPLICIT SAFE REPAIR`; implementacija prati tu granicu.

Jedina napomena: standalone `scripts/guard_architecture.py` i `tests/architecture` ne daju isti rezultat. Standalone guard prijavljuje stare import nalaze; verify architecture suite prolazi. To nije proširivano u ovom tasku.

## Commitovi

Nema commitova.

## Rizici i ograničenja

- Repair DDL je namijenjen poznatom FLOW-1101A hibridnom drift-u, ne opštoj automatskoj DB migracionoj platformi.
- `create_all()` / Alembic split ostaje kao deferred tehnički dug.
- Service-style fresh DB razlika prema Alembic fresh DB nije riješena osim što detector/repair put sada može eksplicitno obraditi drift.
- Stvarna lokalna baza još nije popravljena; backend će na toj bazi sada očekivano blokirati startup i tražiti explicit repair.

## Potreban follow-up

1. Independent review FLOW-1101A implementacije.
2. Ako review prihvati scope, korisnik/developer može kasnije eksplicitno pokrenuti:

```text
python -m flowos.service.services.infrastructure.persistence.schema_repair repair-db
```

3. Tek nakon toga pokrenuti servis nad stvarnom lokalnom bazom.

## Potrebna korisnička potvrda

Da — prije stvarnog repair-a lokalne baze treba korisnička potvrda, jer komanda mijenja `%LOCALAPPDATA%\FlowOS\data\flowos.db` i pravi backup.

## SELF-CHECK

```text
silent startup migration introduced? NO
real local DB modified? NO
backup required before DDL? YES
unknown drift blocks repair? YES
blind alembic upgrade used? NO
blind stamp used? NO
existing data preserved in tests? YES
repair idempotent? YES
Workflow Ledger semantics changed? NO
AgentReport semantics changed? NO
new migration head created? NO
verify.py 7/7? YES
```

Finalni status:

```text
READY FOR INDEPENDENT REVIEW
```

