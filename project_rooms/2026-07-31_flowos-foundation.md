# Project Room — FLOW-000 Bootstrap repozitorija

**Datum:** 2026-07-31
**Task:** FLOW-000
**Impact:** HIGH
**Status:** Plan — čeka potvrdu

---

## Cilj

Postaviti kompletan skeleton FlowOS repozitorijuma sa PySide6 GUI stackom, troslojnom arhitekturom, i svim pratećim fajlovima prema `FlowOS-novi-detaljan-plan-PySide6.md`.

## Pogođeno

- **Korenski fajlovi:** `pyproject.toml`, `AGENTS.md`, `CLAUDE.md`, `README.md`
- **Izvorni kod:** `src/flowos/shared/`, `src/flowos/gui/`, `src/flowos/service/`, `src/flowos/cli/`
- **Testovi:** `tests/unit/`, `tests/integration/`, `tests/contract/`, `tests/architecture/`
- **Skripte:** `scripts/verify.py`, `scripts/run_service.py`, `scripts/run_gui.py`
- **Novi folderi:** `project_rooms/` (ovaj fajl)
- **Postojeći folderi:** `agent_reports/` (već postoji)

## Plan — redosled koraka

### Korak 1: `pyproject.toml`

Minimalni Python 3.12 projekat sa:
- Metadata (naziv, verzija, opis)
- Zavisnosti: `pyside6`, `fastapi`, `uvicorn`, `pydantic`, `sqlalchemy`, `alembic`, `watchdog`, `typer`, `httpx`, `pywin32`
- Dev zavisnosti: `pytest`, `pytest-qt`, `pytest-asyncio`, `coverage`, `ruff`, `mypy`
- Ruff konfiguracija
- mypy konfiguracija
- pytest konfiguracija

### Korak 2: `src/flowos/shared/` — Contracts sloj

Samo DTO, enumi, greške i vremenski utilities. Ne zavisi ni od čega osim Pydantica i standardne biblioteke.

```
src/flowos/shared/
├── __init__.py
├── contracts/          # Pydantic modeli za API transport
│   ├── __init__.py
│   ├── system.py       # HealthResponse, VersionResponse, RuntimeResponse
│   ├── projects.py     # ProjectCreate, ProjectResponse, ProjectUpdate
│   ├── tasks.py        # TaskCreate, TaskResponse, TaskUpdate
│   ├── sessions.py     # SessionCreate, SessionResponse, SessionUpdate
│   ├── events.py       # SessionEventCreate, SessionEventResponse
│   ├── conflicts.py    # ConflictResponse
│   ├── reports.py      # ReportResponse, ReportUpdate
│   └── errors.py       # ApiErrorResponse
├── enums/
│   ├── __init__.py
│   ├── task.py         # TaskStatus, Priority
│   ├── session.py      # ExecutionMode, SessionStatus
│   ├── event.py        # EventType
│   ├── activity.py     # ChangeType, Attribution
│   ├── job.py          # WorkflowType, JobStatus, RiskLevel
│   └── report.py       # UserVerdict
├── errors/
│   ├── __init__.py
│   └── codes.py        # ErrorCode enum
└── time.py             # UTC now helper
```

### Korak 3: `src/flowos/gui/` — GUI skeleton

Samo skeleton sa troslojnom strukturom, bez funkcionalnosti. Svaki modul ima prazne `__init__.py` sa docstringom koji objašnjava ulogu.

```
src/flowos/gui/
├── __init__.py
├── app.py              # QApplication, MainWindow konstrukcija
├── composition_root.py # Eksplicitno povezivanje View→Controller→Services
├── views/
│   ├── __init__.py
│   ├── main_window.py
│   ├── overview.py     # Placeholder za ekran Pregled
│   └── sessions.py     # Placeholder za Aktivne sesije
├── controllers/
│   ├── __init__.py
│   ├── overview.py     # Placeholder
│   └── sessions.py     # Placeholder
├── services/
│   ├── __init__.py
│   └── client.py       # HTTP + WebSocket klijent (skeleton)
├── models/             # Presentation ViewModel/ViewState
│   └── __init__.py
├── delegates/          # QStyledItemDelegate podklase
│   └── __init__.py
├── widgets/            # Custom widgeti
│   └── __init__.py
└── theme/
    ├── __init__.py
    └── tokens.py       # Design tokeni — spacing, radius, font, boje
```

### Korak 4: `src/flowos/service/` — Backend skeleton

FastAPI aplikacija sa tankim kontrolerima i odvojenim servisima. Bez SQL-a i bez implementacije.

```
src/flowos/service/
├── __init__.py
├── app.py              # FastAPI app, CORS (loopback only), lifespan
├── composition_root.py # Eksplicitno konstruisanje servisa
├── controllers/
│   ├── __init__.py
│   ├── http/
│   │   ├── __init__.py
│   │   ├── system.py   # /health, /version, /runtime
│   │   ├── projects.py # CRUD tanke rute
│   │   ├── tasks.py    # CRUD tanke rute
│   │   └── sessions.py # CRUD tanke rute
│   └── websocket/
│       ├── __init__.py
│       └── events.py   # WebSocket endpoint
└── services/
    ├── __init__.py
    ├── projects.py     # Placeholder
    ├── tasks.py        # Placeholder
    ├── sessions.py     # Placeholder
    └── infrastructure/ # Interne implementacije (kasnije)
        ├── __init__.py
        ├── persistence/ # SQLAlchemy modeli i session (faza 1)
        ├── filesystem/
        ├── process/
        └── agent_adapters/
```

### Korak 5: `src/flowos/cli/` — CLI skeleton

Typer aplikacija sa troslojnom strukturom.

```
src/flowos/cli/
├── __init__.py
├── app.py              # Typer app, top-level komande
├── views/
│   ├── __init__.py
│   └── output.py       # Formatirani izlaz
├── controllers/
│   ├── __init__.py
│   └── session.py      # session start/end/list komande
└── services/
    ├── __init__.py
    └── client.py       # httpx API klijent
```

### Korak 6: `tests/` — Testni skeleton

```
tests/
├── __init__.py
├── conftest.py
├── unit/
│   └── __init__.py
├── integration/
│   └── __init__.py
├── contract/
│   └── __init__.py
├── architecture/
│   ├── __init__.py
│   └── test_boundaries.py  # import-linter ekvivalent
├── gui/
│   └── __init__.py
└── fixtures/
    └── __init__.py
```

### Korak 7: `scripts/verify.py`

Standardna ulazna tačka za CI/agente:
1. Ruff format check
2. Ruff lint
3. mypy
4. Architecture boundary test
5. pytest

Svaki korak se izvršava; na prvoj grešci ne staje (prikazuje sve probleme). Exit code 0 samo ako svi prolaze.

### Korak 8: Ažuriranje `AGENTS.md`

Dodati eksplicitne reference na PySide6 stack:
- "Electron/React je zabranjen. GUI se radi u PySide6 + Qt Widgets."
- "Node.js, npm, pnpm, yarn i QML nisu dio projekta."
- "Arhitektura: View → Controller → Services. Kršenje granice ruši verify.py."

### Korak 9: Ažuriranje `CLAUDE.md`

Isto — dodati PySide6 u opis stacka. Sva postojeća pravila ostaju.

### Korak 10: `README.md`

Kratak — šta je FlowOS, kako se pokreće u razvoju, linkovi na plan i CLAUDE.md.

### Korak 11: Agent report

`agent_reports/2026-07-31_flowos-foundation.md` — kompletan izveštaj.

### Korak 12: Commit

Jedan atomski commit sa svim fajlovima: `feat(FLOW-000): bootstrap skeleton repozitorijuma`

---

## Šta NE dirati

- `FlowOS-kompletan-plan.md` — ostaje kao istorijski dokument
- `FlowOS-novi-detaljan-plan-PySide6.md` — netaknut
- `FolowOS-MOKAP-nove-3.png`, `FolowOS-MOKAP-novi.png` — netaknuti
- Postojeće `.gitignore` — može se dopuniti, ne brisati
- Nema implementacije GUI funkcionalnosti, baze, watchera, wrappera, adaptera
- Nema kreiranja foldera za buduće faze bez stvarne potrebe
- Ne diramo `FlowOS-kompletan-plan.md` — ostaje kao referenca, ne briše se

---

## Prihvatljiv ishod

1. `python scripts/verify.py` prolazi (ruff + mypy + architecture test + pytest)
2. Svi importi su čisti — `python -c "from flowos.shared import contracts; from flowos.gui import app; from flowos.service import app; from flowos.cli import app"` radi bez greške
3. Nijedan modul ne krši granice (architecture test prolazi)
4. `AGENTS.md` i `CLAUDE.md` su usklađeni sa PySide6 odlukom
5. Svi fajlovi imaju header docstring prema CLAUDE.md pravilu

---

## Plan verifikacije

| Korak | Komanda |
|---|---|
| Ruff format check | `ruff format --check src/ tests/ scripts/` |
| Ruff lint | `ruff check src/ tests/ scripts/` |
| mypy | `mypy src/` |
| Architecture test | `pytest tests/architecture/ -v` |
| Import skeleton | `python -c "import flowos.shared; import flowos.gui; import flowos.service; import flowos.cli"` |
| Unit testovi | `pytest tests/unit/ -v` (prazni — prolaze) |

---

## Rollback / oporavak

Ako nešto krene naopako:
- `git reset --hard HEAD~1` vraća stanje pre commita
- Svi fajlovi su novi — ne prepisuju ništa postojeće (osim AGENTS.md i CLAUDE.md, koji se lako revertuju)
- Rizik je nizak jer nema brisanja postojećeg koda

---

## Nezavisni checker

Nije dostupan u ovoj fazi (projekat ima jednog agenta). Korisnik vrši ljudski review diff-a pre potvrde.

---

## Odbačene opcije

| Opcija | Zašto razmatrana | Zašto odbačena | Kada ponovo otvoriti |
|---|---|---|---|
| `uv` kao obavezan tool | Brži od pip-a | Mora ostati instalabilan i sa `pip`-om (§5.4) | Nikad — `uv` je preporučen, ne obavezan |
| Dependency injection framework | Čistija kompozicija | Plan eksplicitno zabranjuje (§6) | Ako composition_root postane neodrživ |
| Kreirati sve buduće foldere unapred | "Spremno za sve" | Plan eksplicitno zabranjuje (§6): "Ne kreirati sve foldere unaprijed" | Svaka faza dodaje svoje |
| Obrisati `FlowOS-kompletan-plan.md` | Izbegavanje dupliranja | Sadrži vredne odluke i istorijski kontekst; novi plan ga ne poništava u celosti | Ako postane potpuno zastareo |

## Konfliktni izvori

- `FlowOS-kompletan-plan.md` propisuje Electron/React; novi plan propisuje PySide6. Novi plan ima prednost za GUI odluke. Stari plan ostaje kao referenca za backend arhitekturu, podatkovni model i faze 5+.