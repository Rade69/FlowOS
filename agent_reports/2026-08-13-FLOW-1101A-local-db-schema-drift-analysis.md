---
flowos_report_version: 1
report_id: e8bcdf5e-7dde-43ef-b30b-46c5f493dafe
agent: codex
model: gpt-5
session_id: unknown
report_type: analysis
tasks:
  - FLOW-1101A
commits: []
created_at: 2026-08-13T07:21:29.7347970+02:00
---

# FLOW-1101A — Existing local database schema drift analysis

## Datum

2026-08-13

## Agent / model / sesija

- Agent: Codex
- Model: gpt-5
- Sesija: unknown

## Scope

Read-only analiza za FLOW-1101A: utvrditi zašto postojeća lokalna FlowOS baza nije na aktuelnom Alembic schema head-u i koji je minimalan siguran put da se dovede na šemu koju trenutni backend očekuje.

Stvarna lokalna baza:

```text
C:\Users\38765\AppData\Local\FlowOS\data\flowos.db
```

Trenutni repo baseline:

```text
6c5461a6b2de1d7e0332685452d4f97d61f93797
```

## Task contract / acceptance kriteriji

Acceptance za ovu analizu:

- pročitati stvarni DB/session/startup/Alembic kod;
- pregledati migration chain od `03de14cbf6aa` do `b7c2e1d4a903`;
- read-only uporediti lokalnu SQLite šemu sa ORM modelima i Alembic head-om;
- dokazati zašto standardni upgrade radi ili ne radi na kopiji;
- ne mijenjati produkcijski kod, testove, migracije, planove ili pravu lokalnu bazu;
- sačuvati samo ovaj analysis report.

## GitNexus impact ili ručni blast radius

GitNexus debugging skill je korišten za orijentaciju, ali `gitnexus_query` je vratio:

```text
FTS indexes missing — keyword search degraded
```

Zato je autoritet za ovu analizu bio ručni pregled stvarnog koda i baze.

Ručni blast radius za budući FLOW-1101A fix:

- `src/flowos/service/app.py` — `_run_migrations()` trenutno radi `Base.metadata.create_all()` i jedan ručni `ALTER`;
- `src/flowos/service/services/infrastructure/persistence/engine.py` — kreira lokalni SQLite engine na `%LOCALAPPDATA%\FlowOS\data\flowos.db`;
- `alembic/env.py` — Alembic zna target metadata i default lokalni DB URL;
- `alembic/versions/*.py` — postojeći schema history;
- `src/flowos/service/composition_root.py` — startup scan pokreće AgentReport ingestion;
- `src/flowos/service/services/reports/ingestion.py` — prvi `AgentReport` query puca ako nema v2 kolona;
- `src/flowos/service/services/workflow/ledger.py` i `src/flowos/service/services/workflow/decisions.py` — zavise od `workflow_ledger_events`;
- `scripts/verify.py` i `scripts/verify_roundtrip.py` — već provjeravaju fresh Alembic upgrade/round-trip, ali ne provjeravaju hibridnu postojeću korisničku bazu.

## Reprodukcija prije izmjene

Nije mijenjan kod ni prava baza. Reprodukcija je urađena read-only.

ORM query nad lokalnom bazom:

```text
AgentReport query:
(sqlite3.OperationalError) no such column: agent_reports.report_type

WorkflowLedgerEvent query:
(sqlite3.OperationalError) no such table: workflow_ledger_events
```

SQLite read-only introspekcija:

```text
alembic_version = 03de14cbf6aa
agent_reports.report_type = missing
workflow_ledger_events = missing table
```

Broj relevantnih postojećih zapisa u lokalnoj bazi:

```text
projects = 1
agent_sessions = 30
agent_reports = 0
tasks = 0
plan_items = 30
session_task_bindings = 0
agent_report_binding_links = 0
```

## CURRENT DATABASE AUTHORITY

### WHO CREATES A NEW DATABASE?

Danas postoje dva stvarna mehanizma:

1. `flowos.service.app._run_migrations()`
   - importuje većinu ORM modela;
   - poziva `Base.metadata.create_all(engine)`;
   - zatim pokušava ručni:

```sql
ALTER TABLE agent_sessions ADD COLUMN last_heartbeat_at TIMESTAMP
```

2. Alembic CLI/test workflow
   - `alembic/env.py` importuje ORM metadata i postavlja default URL na `%LOCALAPPDATA%\FlowOS\data\flowos.db` ako `-x sqlalchemy.url=...` nije zadat;
   - `scripts/verify.py` koristi Alembic na privremenoj bazi za migration check.

### WHO UPGRADES AN EXISTING DATABASE?

U produkcijskom startup toku trenutno niko pouzdano ne upgrade-uje postojeću bazu do Alembic head-a.

`_run_migrations()` samo:

- kreira tabele koje ne postoje;
- ne dodaje nove kolone na postojeće tabele osim jednog ručnog `agent_sessions.last_heartbeat_at`;
- ne pokreće `alembic upgrade head`;
- ne ažurira `alembic_version`.

Alembic može upgrade-ovati bazu samo kada se ručno pokrene ili u test/verify toku, ali nije dio `flowos-service` startup-a.

### WHO OWNS SCHEMA AUTHORITY TODAY?

Schema authority je trenutno podijeljen:

- ORM `Base.metadata.create_all()` u `src/flowos/service/app.py`;
- Alembic migrations u `alembic/versions`;
- ručni compatibility `ALTER TABLE` u `src/flowos/service/app.py`.

To je direktan uzrok drift-a: baza može imati tabele iz novog ORM-a, ali star `alembic_version` i stare kolone u već postojećim tabelama.

## MIGRATION CHAIN

Lanac od lokalnog `03de14cbf6aa` do trenutnog head-a `b7c2e1d4a903`:

### 03de14cbf6aa — baseline_initial_schema

- down_revision: `None`
- opis: baseline revision
- promjene: `upgrade()` je `pass`
- destructive/additive: nema promjena
- data migration: ne
- downgrade rizik: nema efektivnih promjena

### 6aca1fa7366b — plan_model_tables

- down_revision: `03de14cbf6aa`
- opis: kreira osnovne plan/project/task/session tabele
- mijenja:
  - `projects`
  - `plans`
  - `plan_phases`
  - `plan_items`
  - `plan_item_criteria`
  - `plan_item_dependencies`
  - `plan_progress_events`
  - `tasks`
  - `agent_sessions`
  - `session_events`
- upgrade: additive za praznu ili stvarno baseline bazu
- data migration: ne
- downgrade rizik: visok, jer downgrade dropuje ove tabele
- važan drift dokaz: na trenutnoj lokalnoj bazi standardni upgrade pada ovdje sa `table projects already exists`

### 41009440b28e — resume_models

- down_revision: `6aca1fa7366b`
- opis: project resume/reconciliation/workspace history tabele
- mijenja:
  - `external_activities`
  - `project_reconciliation_events`
  - `project_resume_states`
  - `project_workspace_states`
- upgrade: additive
- data migration: ne
- downgrade rizik: visok za podatke u tim tabelama, jer downgrade dropuje tabele

### d62470d60bc8 — add_result_commit_sha

- down_revision: `41009440b28e`
- opis: no-op migracija
- mijenja: ništa
- upgrade: nema promjena
- data migration: ne
- downgrade rizik: nema efektivnih promjena

### 96aa6257d45c — add_phase3_tables

- down_revision: `d62470d60bc8`
- opis: conflicts, agent_reports, file_activities i session kolone
- mijenja:
  - kreira `conflicts`
  - kreira `agent_reports`
  - kreira `file_activities`
  - dodaje `agent_sessions.result_commit_sha`
  - dodaje `agent_sessions.last_heartbeat_at`
- upgrade: većinom additive
- data migration: ne
- downgrade rizik: visok, jer dropuje Phase 3 tabele i dvije session kolone

### ce4d3efbde51 — add_worktrees_table

- down_revision: `96aa6257d45c`
- opis: worktree registry tabela
- mijenja:
  - kreira `worktrees`
- upgrade: additive
- data migration: ne
- downgrade rizik: visok za worktree history, jer dropuje tabelu

### 9b2d1f7a4c63 — session_task_bindings

- down_revision: `ce4d3efbde51`
- opis: canonical session/task/plan binding history
- mijenja:
  - kreira `session_task_bindings`
  - dodaje check constraints i partial unique index `uq_session_task_bindings_active`
- upgrade: additive
- data migration: ne
- downgrade rizik: visok za binding history, jer dropuje tabelu

### a17e4c8f9b21 — agent_report_v2_bindings

- down_revision: `9b2d1f7a4c63`
- opis: AgentReport v2 report semantics i binding link tabela
- mijenja:
  - dodaje `agent_reports.report_type`
  - dodaje `agent_reports.work_status`
  - dodaje check constraint `ck_agent_reports_work_status`
  - kreira `agent_report_binding_links`
- upgrade: additive po namjeri; `batch_alter_table` može rebuildati SQLite tabelu zbog check constrainta
- data migration: ne
- downgrade rizik: srednji/visok, jer uklanja v2 kolone i binding link tabelu
- važno: ovo je migracija koja dodaje `agent_reports.report_type`

### 4f2c9a7b8d11 — agent_report_source_identity

- down_revision: `a17e4c8f9b21`
- opis: deterministic source identity za Markdown report ingestion
- mijenja:
  - dodaje `agent_reports.source_report_id`
  - dodaje `agent_reports.source_path`
  - dodaje `agent_reports.source_content_sha256`
  - kreira unique index `ix_agent_reports_source_report_id`
  - kreira unique index `ix_agent_reports_source_path`
- upgrade: additive
- data migration: ne
- downgrade rizik: srednji, jer uklanja source identity kolone/indekse

### b7c2e1d4a903 — workflow_ledger_events

- down_revision: `4f2c9a7b8d11`
- opis: append-only Workflow Ledger event tabela
- mijenja:
  - kreira `workflow_ledger_events`
  - dodaje unique constraint za `idempotency_key`
  - dodaje ledger indekse po project/session/task/plan/source
- upgrade: additive
- data migration: ne
- downgrade rizik: visok za workflow history, jer dropuje ledger tabelu

## ACTUAL LOCAL DB DRIFT

### ALEMBIC VERSION DRIFT

Potvrđeno:

```text
local alembic_version = 03de14cbf6aa
repository head = b7c2e1d4a903
```

Međutim, stvarna lokalna schema nije čisti `03de14cbf6aa`. Ona je hibrid:

- ima tabele koje pripadaju kasnijim ORM/migration fazama;
- nema neke kolone koje Alembic head i ORM očekuju;
- nema `workflow_ledger_events`;
- Alembic stamp nije pomjeren.

### MISSING COLUMN

`agent_reports` postoji, ali nema:

```text
report_type
work_status
source_report_id
source_path
source_content_sha256
```

Nedostaju i source identity indeksi:

```text
ix_agent_reports_source_report_id
ix_agent_reports_source_path
```

### MISSING TABLE

`workflow_ledger_events` ne postoji.

`verification_artifacts` nije tretiran kao schema drift, jer trenutni kod nema ORM tabelu za verification artifacts. `VerificationService` i `ArtifactStore` čuvaju verification artifacte u filesystemu (`artifacts/verification/<id>/`), ne u SQLite tabeli.

### EXTRA LEGACY COLUMN

Nije pronađena relevantna extra legacy kolona u provjerenim tabelama. SQLite `sqlite_autoindex_*` indeksi su interni PK/unique indeksi, ne legacy drift.

### TYPE/NULLABILITY DRIFT

Za provjerene relevantne tabele nije potvrđen kritičan type/nullability drift između SQLite introspekcije i ORM-a. Glavni drift su missing kolone/tabela i Alembic stamp.

### INDEX/CONSTRAINT DRIFT

Potvrđeno:

- `agent_reports` nema unique source identity indekse;
- `agent_reports` nema v2 check constraint iz migracije `a17e4c8f9b21`;
- `workflow_ledger_events` nema nijedan očekivani index/constraint jer tabela ne postoji.

### Tabele koje postoje iako Alembic version tvrdi baseline

Lokalna baza već ima:

```text
projects
plans
plan_phases
plan_items
plan_item_criteria
plan_item_dependencies
plan_progress_events
tasks
agent_sessions
session_events
external_activities
project_reconciliation_events
project_resume_states
project_workspace_states
conflicts
agent_reports
file_activities
worktrees
session_task_bindings
agent_report_binding_links
```

Ovo je praktično nemoguće objasniti standardnim Alembic versionom `03de14cbf6aa`. Najbolje objašnjenje iz stvarnog koda je da ih je napravio `Base.metadata.create_all()` tokom servis startup-a.

## WHY WAS THE DB NOT UPGRADED?

Root cause nije samo “baza nije migrirana”.

Tačan tok:

1. Lokalna baza ima `alembic_version = 03de14cbf6aa`.
2. `flowos-service` startup poziva `src/flowos/service/app.py::_run_migrations()`.
3. `_run_migrations()` ne poziva `alembic upgrade head`.
4. `_run_migrations()` importuje većinu ORM modela i poziva `Base.metadata.create_all(engine)`.
5. `create_all()` kreira tabele koje nedostaju, ali ne mijenja postojeće tabele.
6. Zato su kasnije tabele nastale direktno iz ORM-a.
7. `agent_reports` je već postojao iz ranije Phase 3 šeme, pa `create_all()` nije dodao nove v2 kolone.
8. Ručni compatibility kod pokriva samo `agent_sessions.last_heartbeat_at`.
9. Alembic stamp ostaje `03de14cbf6aa`.
10. Startup AgentReport ingestion zatim koristi ORM model koji selektuje `AgentReport.report_type`, `work_status`, `source_report_id`, `source_path`, `source_content_sha256`.
11. SQLite tabela nema te kolone, pa query pada na:

```text
sqlite3.OperationalError: no such column: agent_reports.report_type
```

Dodatni problem: `_run_migrations()` ne importuje `workflow_ledger_models`, pa ni fresh service-style `create_all()` ne kreira `workflow_ledger_events`.

## NEW DATABASE VS EXISTING DATABASE

### A) Potpuno nova prazna baza kroz Alembic

Na privremenoj bazi je pokrenuto:

```text
python -m alembic -x sqlalchemy.url=sqlite:///TEMP/fresh-alembic.db upgrade head
```

Rezultat:

```text
PASS
alembic_version = b7c2e1d4a903
agent_reports ima report_type/work_status/source_* kolone
workflow_ledger_events postoji
```

Fresh Alembic DB je kompatibilna sa trenutnim ORM modelima za provjerene tabele.

### B) Potpuno nova prazna baza kroz service `_run_migrations()` stil

Na privremenoj bazi je simuliran import-set iz `flowos.service.app._run_migrations()` i `Base.metadata.create_all()`.

Rezultat:

```text
agent_reports ima v2 kolone
workflow_ledger_events ne postoji
alembic_version tabela ne postoji
```

Dakle nova baza kroz service startup nije ista kao nova baza kroz Alembic head.

### C) Postojeća hibridna baza na `03de14cbf6aa`

Standardni `alembic upgrade head` na kopiji postojeće baze ne prolazi.

Prvi failure:

```text
Running upgrade 03de14cbf6aa -> 6aca1fa7366b, plan_model_tables
sqlite3.OperationalError: table projects already exists
```

To znači da trenutna postojeća baza ne može bezbjedno stići na head običnim `alembic upgrade head` dok je stamp `03de14cbf6aa`, jer realna schema već sadrži tabele koje migracije pokušavaju ponovo napraviti.

## SAFE UPGRADE PROOF ON A COPY

Korišten je SQLite backup API da se napravi privremena kopija stvarne lokalne baze. Prava baza nije mijenjana.

Nad kopijom je pokrenuto:

```text
python -m alembic -x sqlalchemy.url=sqlite:///TEMP/flowos-copy.db upgrade head
```

Rezultat:

```text
STANDARD ALEMBIC UPGRADE ON COPY: FAIL
```

Failure:

```text
sqlite3.OperationalError: table projects already exists
```

Stanje kopije poslije failure-a:

```text
alembic_version = 03de14cbf6aa
agent_reports.report_type = missing
workflow_ledger_events = missing
```

Privremene kopije su uklonjene nakon testa.

## DATA SAFETY

Forward migration chain je po namjeri uglavnom additive, ali trenutna lokalna baza je hibridna i zato običan Alembic upgrade nije bezbjedan operativni korak.

Realni rizici:

### RISK-DS-01 — pogrešan Alembic stamp

- migration: cijeli lanac, posebno `6aca1fa7366b`
- dokaz: baza ima `projects`, ali stamp tvrdi `03de14cbf6aa`
- uticaj: običan upgrade pokušava ponovo napraviti postojeće tabele
- minimalni naredni korak: ne raditi `alembic upgrade head` nad pravom bazom bez backup-a i repair plana

### RISK-DS-02 — ručno stampanje bez schema repair-a

- migration: `a17e4c8f9b21`, `4f2c9a7b8d11`, `b7c2e1d4a903`
- dokaz: `agent_report_binding_links` već postoji, ali `agent_reports.report_type` ne postoji
- uticaj: stampanje baze na neki kasniji revision može sakriti missing kolone
- minimalni naredni korak: prije bilo kakvog stamp-a dokazati sve required kolone/tabele/indeksi

### RISK-DS-03 — Workflow Ledger tabela nije dio service create_all import-seta

- migration: `b7c2e1d4a903`
- dokaz: service-style fresh DB nema `workflow_ledger_events`
- uticaj: ledger runtime može pasti čak i na novoj bazi kreiranoj samo kroz servis
- minimalni naredni korak: budući fix mora pokriti ledger model/import ili Alembic authority

Data loss rizik za pažljivo targetirani additive repair uz backup je LOW, jer potrebne promjene dodaju nullable kolone, indekse i nedostajuću ledger tabelu. Data loss rizik postaje MEDIUM/HIGH ako se pokuša slijepo downgrade/upgrade ili brisanje baze.

Ne predlaže se brisanje lokalne baze. Postojeći podaci su razvojni evidence.

## PRODUCT / STARTUP DECISION BOUNDARY

### OPTION A — developer ručno radi `alembic upgrade head`

Tehničko značenje:

- ručni Alembic ostaje authority;
- servis samo očekuje da je DB već ispravna.

Rizik:

- u trenutnoj lokalnoj bazi ovo ne radi; standardni upgrade na kopiji pada zbog hibridnog stanja;
- potrebno je prvo repair/stamp rješenje za već driftovanu bazu.

Arhitektonska promjena:

- mala za budućnost, ali ne rješava postojeći hibrid bez dodatnog lokalnog repair koraka.

### OPTION B — FlowOS service automatski migrira DB pri startup-u

Tehničko značenje:

- `_run_migrations()` bi morao prestati biti `create_all` compatibility hack i postati kontrolisana migration/repair granica;
- mora imati backup, lock, idempotency i jasnu grešku ako repair nije siguran.

Rizik:

- srednji, jer startup automatski mijenja korisničku evidence bazu;
- mora biti vrlo oprezno zbog SQLite i lokalnih vrijednih podataka.

Arhitektonska promjena:

- srednja; mijenja product/startup authority odluku.

### OPTION C — FlowOS detektuje schema drift i blokira/traži korisničku akciju

Tehničko značenje:

- startup provjeri `alembic_version` i ključne kolone/tabele;
- ako je drift, servis ne pokreće ingestion/ledger ili vraća jasan repair status;
- korisnik/developer pokreće odobren repair.

Rizik:

- nizak za podatke, jer nema automatskih DDL izmjena;
- veći UX friction za dogfooding dok se repair ne izvrši.

Arhitektonska promjena:

- mala/srednja; uvodi jasnu granicu umjesto tihog partial startup-a.

### OPTION D — postojeći pattern: `_run_migrations()` compatibility helper

Tehničko značenje:

- proširiti postojeći ručni compatibility kod da doda missing kolone/tabele i eventualno stampuje DB.

Rizik:

- srednji ako nastavi da zaobilazi Alembic history;
- može dodatno produbiti split između fresh DB, migrated DB i user DB.

Arhitektonska promjena:

- mala kratkoročno, ali povećava tehnički dug.

## CURRENT create_all / ALEMBIC SPLIT

Potvrđeno je da FlowOS danas koristi kombinaciju:

```text
Base.metadata.create_all()
+
Alembic migrations
+
manual ALTER compatibility code
```

Tačno gdje:

- `src/flowos/service/app.py::_run_migrations()`
  - `Base.metadata.create_all(engine)`
  - `ALTER TABLE agent_sessions ADD COLUMN last_heartbeat_at TIMESTAMP`
- `alembic/env.py`
  - Alembic target metadata i default lokalni DB URL
- `scripts/verify.py`
  - Alembic fresh migration check
- test fixture-i
  - mnogi testovi koriste `Base.metadata.create_all()` na privremenim bazama

Problemi koje split danas stvara:

- fresh service DB i fresh Alembic DB nisu iste;
- service DB nema `alembic_version`;
- service DB trenutno ne dobija `workflow_ledger_events`, jer `_run_migrations()` ne importuje `workflow_ledger_models`;
- existing DB dobija nove tabele kroz `create_all()`, ali ne dobija nove kolone na postojećim tabelama;
- `alembic_version` može ostati star iako schema sadrži novije tabele;
- standardni Alembic upgrade može pasti na već postojećim tabelama;
- test DB-ovi kreirani kroz `create_all()` mogu sakriti migration probleme.

## FLOW-1101A SCOPE RECOMMENDATION

### MUST FIX NOW

Minimalno za LIVE dogfooding:

1. Ne pokretati slijepi `alembic upgrade head` nad pravom lokalnom bazom.
2. Prije repair-a napraviti backup `%LOCALAPPDATA%\FlowOS\data\flowos.db` zajedno sa WAL/SHM fajlovima ako postoje.
3. Uvesti minimalni, eksplicitni schema drift gate/repair za postojeću hibridnu bazu:
   - detektovati `alembic_version`;
   - detektovati da `projects` i ostale tabele već postoje iako je stamp `03de14cbf6aa`;
   - dodati samo missing nullable AgentReport v2 kolone ako nedostaju;
   - dodati missing source identity indekse ako ne postoje;
   - kreirati `workflow_ledger_events` ako ne postoji;
   - tek nakon dokazano kompatibilne šeme postaviti/stampovati Alembic version na `b7c2e1d4a903`.
4. Dok se product odluka ne donese, preferirati blokirajuću detekciju ili eksplicitan repair command nad tihim automatskim startup upgrade-om.

### DEFER

Odložiti veći cleanup:

- potpuno uklanjanje `create_all()` iz produkcijskog startup-a;
- standardizacija svih testova da koriste Alembic umjesto `create_all()`;
- generalni schema management redesign;
- historijski backfill za `AgentReport` source identity ili Workflow Ledger;
- bilo kakav workflow semantics redesign.

### FILES THAT WOULD CHANGE

Za minimalni budući fix vjerovatna lista:

```text
src/flowos/service/app.py
src/flowos/service/services/infrastructure/persistence/engine.py   (samo ako se uvodi pomoćni backup/URL helper)
src/flowos/service/services/infrastructure/persistence/schema_repair.py   (novi helper, ako se odvoji iz app.py)
tests/integration/test_local_schema_repair.py
tests/unit/test_schema_repair.py
scripts/verify.py   (ako se dodaje old/hybrid schema regression test u standardni verify)
```

Ako se izabere čisti Alembic-first pristup umjesto compatibility helpera, mijenjali bi se i Alembic/bootstrap workflow fajlovi, ali to je šira product/architecture odluka.

### MIGRATION FILE REQUIRED

NO za samu ciljnu šemu: postojeće migracije već opisuju potrebne finalne tabele/kolone.

Moguće je da će biti potreban repair/stamp helper ili posebna idempotentna compatibility rutina, ali to nije nova schema migracija u smislu novog head-a.

### EXISTING MIGRATIONS SUFFICIENT

NO za trenutnu lokalnu hibridnu bazu.

YES samo za fresh Alembic DB ili za bazu čija stvarna schema i `alembic_version` nisu već razdvojeni.

### LOCAL DATA BACKUP REQUIRED BEFORE IMPLEMENTATION

YES.

Prije bilo kakvog repair-a ili stamp-a treba sačuvati:

```text
flowos.db
flowos.db-wal
flowos.db-shm
```

ako WAL/SHM postoje.

## TEST PLAN FOR FUTURE IMPLEMENTATION

Minimalni testovi:

1. Old/hybrid-schema DB → supported startup/upgrade path:
   - fixture baza sa `alembic_version=03de14cbf6aa`, postojećim tabelama i missing `agent_reports` v2 kolonama;
   - repair/gate mora završiti deterministički.
2. Existing data survives:
   - prije repair-a ubaciti `Project`, `AgentSession`, `PlanItem`;
   - poslije repair-a potvrditi isti count i ključne vrijednosti.
3. AgentReport query sa `report_type` radi:
   - `session.query(AgentReport).first()` više ne baca `OperationalError`.
4. `alembic_version` odgovara head-u:
   - poslije uspješnog repair-a `alembic_version = b7c2e1d4a903`.
5. Startup AgentReport ingestion više ne baca schema `OperationalError`:
   - pokrenuti `_scan_existing_agent_reports_for_project` nad test repo fixtureom.
6. Fresh DB i upgraded/repaired DB imaju kompatibilnu schema:
   - uporediti ključne tabele/kolone/indekse: `agent_reports`, `agent_report_binding_links`, `session_task_bindings`, `workflow_ledger_events`, `tasks`, `plan_items`.
7. `scripts/verify.py` ostaje 7/7.
8. Negativni test:
   - ako postoji nepoznat/nesiguran drift, repair ne smije silent-stampovati bazu nego mora blokirati sa jasnom greškom.

## Šta je urađeno

Urađena je samo read-only analiza:

- pročitan je relevantni startup/engine/Alembic kod;
- pročitan je migration chain;
- lokalna baza je otvorena read-only za schema introspekciju;
- standardni Alembic upgrade testiran je isključivo na privremenoj kopiji;
- fresh Alembic DB i fresh service-style `create_all` DB upoređeni su na privremenim bazama;
- reproducirane su read-only ORM greške za `AgentReport` i `WorkflowLedgerEvent`;
- sačuvan je ovaj report.

## Zašto je urađeno

Zato što runtime simptom `no such column: agent_reports.report_type` nije dovoljan kao root cause. Stvarni rizik je dublji: lokalna baza nije ni čista stara baza ni validno migrirana nova baza, nego hibrid nastao iz paralelnog korištenja `create_all()` i Alembic-a.

## Kako je urađeno

Korišteno je:

- `git status --short --branch`;
- `git log -3 --oneline`;
- direktno čitanje `engine.py`, `app.py`, `composition_root.py`, `alembic/env.py`, ORM modela i migration fajlova;
- SQLite `PRAGMA table_info`, `PRAGMA index_list`, `PRAGMA foreign_key_list`;
- SQLAlchemy metadata introspekcija bez `create_all()` nad pravom bazom;
- SQLite backup API za privremenu kopiju baze;
- `alembic upgrade head` samo nad kopijom/temp bazama.

## Izmijenjeni fajlovi i ponašanje

Izmijenjen je samo ovaj report:

```text
agent_reports/2026-08-13-FLOW-1101A-local-db-schema-drift-analysis.md
```

Nije mijenjan produkcijski kod, testovi, migracije, planovi, lokalna baza, Git history ili remote.

## Šta nije dirano

Nije dirano:

- prava lokalna baza u `%LOCALAPPDATA%\FlowOS\data\flowos.db`;
- produkcijski kod;
- testovi;
- Alembic migration fajlovi;
- `AGENTS.md`;
- `CLAUDE.md`;
- prethodni untracked agent reportovi/dokumenti;
- Git commit/push.

## Verifikacija i stvarni rezultat

Read-only verifikacija:

```text
git rev-parse HEAD
=> 6c5461a6b2de1d7e0332685452d4f97d61f93797
```

Local DB:

```text
exists = true
journal_mode = wal
alembic_version = 03de14cbf6aa
```

ORM repro:

```text
AgentReport query => OperationalError: no such column: agent_reports.report_type
WorkflowLedgerEvent query => OperationalError: no such table: workflow_ledger_events
```

Alembic upgrade on copy:

```text
FAIL
first failure: table projects already exists
```

Fresh Alembic DB:

```text
PASS
alembic_version = b7c2e1d4a903
workflow_ledger_events exists = true
```

Fresh service-style `create_all` DB:

```text
workflow_ledger_events exists = false
alembic_version table exists = false
```

`scripts/verify.py` nije pokrenut jer je zadatak read-only analiza i nije tražio punu verifikaciju.

## Nezavisna provjera

Nije rađena nezavisna provjera u ovoj sesiji. Ovo je read-only root-cause/schema drift analiza sa direktnim dokazima iz koda, migracija i lokalne SQLite baze.

## Pronađeni problemi

### BLOCKER-1101A-01

- severity: BLOCKER
- fajl/migration: `src/flowos/service/app.py::_run_migrations`, lokalna DB `alembic_version`
- dokaz: baza ima `projects`, ali `alembic_version=03de14cbf6aa`; `alembic upgrade head` na kopiji pada na `table projects already exists`
- uticaj: standardni Alembic upgrade nije siguran/operativan za trenutnu lokalnu bazu
- minimalni naredni korak: ne pokretati upgrade nad pravom bazom; prvo implementirati backup + drift repair/gate

### HIGH-1101A-02

- severity: HIGH
- fajl/migration: `alembic/versions/a17e4c8f9b21_agent_report_v2_bindings.py`, `alembic/versions/4f2c9a7b8d11_agent_report_source_identity.py`
- dokaz: `agent_reports` nema `report_type`, `work_status`, `source_report_id`, `source_path`, `source_content_sha256`
- uticaj: AgentReport ingestion i bilo koji ORM query koji selektuje `AgentReport` pada
- minimalni naredni korak: dodati missing nullable v2/source identity kolone i indekse kroz kontrolisan repair

### HIGH-1101A-03

- severity: HIGH
- fajl/migration: `alembic/versions/b7c2e1d4a903_workflow_ledger_events.py`, `src/flowos/service/app.py`
- dokaz: lokalna baza nema `workflow_ledger_events`; service-style fresh `create_all` baza je takođe nema jer `_run_migrations()` ne importuje `workflow_ledger_models`
- uticaj: Workflow Ledger Phase 3A–3D runtime može pasti na postojećoj bazi i na service-created fresh bazi
- minimalni naredni korak: repair/gate mora eksplicitno pokriti ledger tabelu ili startup mora koristiti Alembic authority

### MEDIUM-1101A-04

- severity: MEDIUM
- fajl/migration: `src/flowos/service/app.py`, `alembic/env.py`, test fixture-i
- dokaz: repo koristi `create_all`, Alembic i ručni `ALTER`
- uticaj: fresh DB, migrated DB, user DB i test DB mogu završiti sa različitim schema/stamp stanjem
- minimalni naredni korak: za FLOW-1101A riješiti samo runtime drift; veći cleanup odložiti

### LOW-1101A-05

- severity: LOW
- fajl/migration: `scripts/verify.py`
- dokaz: verify provjerava fresh Alembic upgrade i round-trip, ali ne provjerava hibridnu postojeću bazu
- uticaj: regression tip “existing local DB drift” može proći neopaženo
- minimalni naredni korak: u budućoj implementaciji dodati old/hybrid schema regression test

## Odbačene opcije

### Brisanje lokalne baze

- zašto razmatrano: brzo uklanja drift
- zašto odbačeno: korisnički podaci/evidence su vrijedni; prompt izričito ne želi brisanje kao primarno rješenje
- kada ponovo otvoriti: samo uz eksplicitnu korisničku odluku i backup

### Povećati SQLite pool ili mijenjati QueuePool

- zašto razmatrano: prethodni FLOW-1101 je imao QueuePool simptom
- zašto odbačeno: ovaj FLOW-1101A je schema drift; pool size ne dodaje missing kolone/tabele
- kada ponovo otvoriti: ne za ovaj problem

### Slijepi `alembic upgrade head`

- zašto razmatrano: standardni Alembic put
- zašto odbačeno: dokazano pada na kopiji sa `table projects already exists`
- kada ponovo otvoriti: nakon što se baza dovede u konzistentan schema/stamp state

### Slijepi `alembic stamp head`

- zašto razmatrano: pomjerio bi version bez pokretanja kolizionih migracija
- zašto odbačeno: sakrio bi missing kolone i missing `workflow_ledger_events`
- kada ponovo otvoriti: tek nakon automatske/verifikovane schema repair provjere svih required objekata

## Konflikti/kontradiktorni izvori

Prompt navodi da local DB ima `alembic_version=03de14cbf6aa` i da `agent_reports.report_type` ne postoji. To je potvrđeno.

Dodatna kontradikcija pronađena u stvarnom stanju:

- `alembic_version` tvrdi baseline;
- baza ipak ima tabele iz kasnijih faza, uključujući `session_task_bindings` i `agent_report_binding_links`.

To nije kontradikcija prompta, nego dokaz hibridnog schema authority problema.

## Commitovi

Nema commitova.

## Rizici i ograničenja

- Analiza nije mijenjala pravu bazu.
- `foreign_keys` PRAGMA u raw sqlite read-only konekciji je bio `0`; produkcijski SQLAlchemy engine postavlja `PRAGMA foreign_keys=ON` na connect. Ovo nije tretirano kao schema drift.
- Standardni upgrade je testiran na kopiji stvarne baze, što je dovoljno za dokaz failure-a; nije testiran nikakav repair jer je zadatak read-only.
- GitNexus indeks je bio degradiran, pa je ručna analiza bila autoritet.

## Potreban follow-up

FLOW-1101A implementacija treba početi tek nakon korisničke/product odluke o granici:

- blokirajuća schema drift detekcija + eksplicitan repair command;
- ili automatski startup repair/migration sa backupom;
- ili ručni developer workflow.

Najsigurniji minimalni tehnički contract je: backup + idempotentna detekcija hibridnog stanja + dodavanje samo missing additivnih objekata + verifikacija + stamp na head tek poslije uspješne provjere.

## Potrebna korisnička potvrda

Potrebna je korisnička/product odluka da li FlowOS smije automatski mijenjati lokalnu DB šemu pri startup-u ili mora samo blokirati i tražiti eksplicitnu repair akciju.

## Finalni verdict

```text
ROOT CAUSE: CONFIRMED
LOCAL DB SCHEMA DRIFT: CONFIRMED
STANDARD ALEMBIC UPGRADE ON COPY: FAIL
DATA LOSS RISK: LOW
EXISTING MIGRATIONS SUFFICIENT: NO
PRODUCT DECISION REQUIRED: YES
MINIMAL FLOW-1101A IMPLEMENTATION READY: NO
```

Završni status:

```text
FLOW-1101A NEEDS ARCHITECTURE DECISION
```

