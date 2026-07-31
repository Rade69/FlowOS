# Agent Report — FLOW-102 SQLite i migracije

**Datum:** 2026-07-31
**Agent:** pi (Claude opus model)
**Scope:** FLOW-102 — SQLAlchemy ORM modeli, SQLite/WAL engine, Alembic baseline migracija

## Task contract

- **Cilj:** Postaviti perzistentni sloj — ORM modele, engine, migracije
- **Scope:** persistence modul, Alembic, integracioni testovi
- **Out-of-scope:** FastAPI rute, poslovna logika, GUI
- **Acceptance kriterij:** ORM modeli funkcionalni, migracija prolazi, FK i WAL testirani

## Impact analiza

MEDIUM — postavlja perzistentni sloj. Nema pozivalaca (niko još ne koristi modele). Promene su aditivne.

## Šta je urađeno

### 1. SQLAlchemy ORM modeli (4 entiteta)

| Model | Tabela | Indeksi |
|---|---|---|
| `Project` | `projects` | status |
| `Task` | `tasks` | project_id, status, priority |
| `AgentSession` | `agent_sessions` | project_id, task_id, status, execution_mode |
| `SessionEvent` | `session_events` | session_id, event_type, occurred_at |

Svi modeli:
- UUID string PK (generisan u aplikativnom sloju)
- UTC vremena
- ForeignKey sa CASCADE/SET NULL
- `passive_deletes=True` za ispravno cascade brisanje
- `idempotency_key` UNIQUE constraint

### 2. Engine (engine.py)

- `create_sqlite_engine()` — SQLite sa WAL-om, FK ON, pool_size=1
- `create_session_factory()` — sessionmaker sa autoflush
- `get_data_directory()` — `%LOCALAPPDATA%/FlowOS/data/`

### 3. Alembic

- `alembic init` + konfiguracija
- `env.py` — koristi Base.metadata, programski postavlja URL
- Baseline migracija: `03de14cbf6aa_baseline_initial_schema.py`
- Migracija uspešno primenjena (`alembic upgrade head`)

### 4. Integracioni testovi (17 testova)

- Project CRUD (create, update, delete)
- Task CRUD (create sa FK, belongs_to, cascade delete)
- AgentSession CRUD (minimalan, sa svim poljima, task_id nullable)
- SessionEvent (create, unique idempotency_key, cascade delete)
- SQLite podešavanja (WAL, FK ON, FK violation, sve tabele postoje, file DB)

## Zašto je urađeno

ORM modeli su temelj za sve buduće servise. Bez njih nema:
- ProjectService, TaskService (faza 1)
- SessionService (faza 2)
- ConflictService, ReportService (faza 3)

## Kako je urađeno

- SQLAlchemy 2.x Mapped stil (ne legacy `Column`)
- `DeclarativeBase` kao osnova za sve modele
- `event.listens_for(engine, "connect")` za PRAGMA podešavanja
- Alembic `env.py` koristi programsko postavljanje URL-a (ne ini fajl)
- Testovi koriste `:memory:` bazu za izolaciju + `TemporaryDirectory` za fajl test

## Izmijenjeni fajlovi

| Fajl | Promena |
|---|---|
| `src/flowos/service/services/infrastructure/persistence/base.py` | Nov — DeclarativeBase |
| `src/flowos/service/services/infrastructure/persistence/engine.py` | Nov — SQLite/WAL engine + session factory |
| `src/flowos/service/services/infrastructure/persistence/models.py` | Nov — 4 ORM modela (Project, Task, AgentSession, SessionEvent) |
| `alembic/` + `alembic.ini` | Alembic inicijalizacija + baseline migracija |
| `tests/integration/test_persistence.py` | Nov — 17 integracionih testova |

## Verifikacija

| Provera | Rezultat |
|---|---|
| Ruff format + lint | ✅ |
| Unit testovi (contracts) | ✅ 39/39 |
| Integracioni testovi (persistence) | ✅ 17/17 |
| Architecture testovi | ✅ 7/7 |
| Alembic upgrade head | ✅ |

**Ukupno: 63/63 testova**

## Pronađeni problemi

- `:memory:` baza ne podržava WAL (vraća "memory") — WAL se testira u fajl testu
- `session.add_all([project, task])` ne radi bez prethodnog `flush()` — FK zahteva poznat ID
- `passive_deletes=True` neophodan za ispravno cascade brisanje sa SQLAlchemy session-om

## Rizici i ograničenja

- ORM modeli su privatni za persistence sloj — ne smeju se importovati izvan service sloja
- `pool_size=1` zbog SQLite single-writer ograničenja
- `expire_on_commit=False` za izbegavanje lazy load posle commit-a

## Potreban follow-up

- FLOW-103: Service runtime (FastAPI + single-instance lock)
- FLOW-104: Projects/Tasks Services i API Controllers

## Potrebna korisnička potvrda

Nema — FLOW-102 je završen.