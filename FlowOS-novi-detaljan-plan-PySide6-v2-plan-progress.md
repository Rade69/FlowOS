# FlowOS — novi detaljan plan realizacije v2

**Datum:** 31. juli 2026.  
**Status:** Operativni plan za početak implementacije — dopunjen praćenjem napretka po planu  
**Primarni izvršilac:** pi agent  
**Primarna platforma:** Windows 10/11  
**Arhitektura:** View → Controller → Services  
**GUI:** Python 3.12 + PySide6 + Qt Widgets  
**Backend:** Python 3.12 + FastAPI  
**Baza:** SQLite, WAL režim  
**Electron:** zabranjen  
**Node.js:** nije dio aplikacije ni build procesa

---

## 0. Svrha dokumenta

Ovaj dokument zamjenjuje raniji FlowOS plan tamo gdje je raniji plan predviđao Electron/React/Node GUI. Sve vrijedne odluke iz ranijeg plana ostaju, ali se implementacija prebacuje na čisti Python desktop stack.

Dokument je namijenjen direktnom radu sa pi agentom. Agent ne smije pokušati implementirati cijeli dokument u jednom zadatku. Radi se fazno, jedan jasno ograničen zadatak, jedan worktree, jedan skup dokaza i jedan `agent_report`.

Plan je izveden iz sljedećih izvora:

- `FlowOS-kompletan-plan.md`
- `BOOTSTRAP.md`
- `UNIVERSAL_CLAUDE.md` / `UNIVERSAL_CLAUDE(1).md`
- `METHOD.md`
- `agent_report_template.md`
- `project_room_template.md`
- odobreni FlowOS mockup ekrana Pregled
- dogovor da cijela aplikacija poštuje View → Controller → Services

`UNIVERSAL_CLAUDE.md` i `UNIVERSAL_CLAUDE(1).md` predstavljaju istu verziju. U projektu se zadržava samo jedna kanonska kopija tokom bootstrap-a; poslije spajanja pravila ne ostavljati duplikate.

---

# 1. Neupitne odluke

Pi agent ove odluke tretira kao potvrđene projektne činjenice. Ne otvara ih ponovo bez konkretnog dokaza da odluka blokira realizaciju.

1. FlowOS je lokalna desktop aplikacija za jednog korisnika.
2. Primarna platforma je Windows 10/11.
3. GUI se radi u PySide6 i Qt Widgets.
4. Ne koristiti Electron, React, Node.js, npm, pnpm, yarn ni QML.
5. Backend je odvojen Python proces i nastavlja rad kada je GUI zatvoren.
6. Backend nije Windows Service. Pokreće se kao per-user proces nakon prijave korisnika, jer mora pokretati terminale i agentske procese u korisničkoj sesiji.
7. Arhitektura cijelog toka je View → Controller → Services.
8. View ne poziva Services direktno.
9. Controller ne pristupa SQLite bazi, Git-u, filesystemu ni subprocessima direktno.
10. Services ne zavisi od PySide6 View klasa niti od FastAPI ruta.
11. Git je autoritet za promjene koda: commit, diff i status su dokaz.
12. Wrapper je primarni način registracije sesije.
13. Worktree je osnovna izolacija paralelnih writer sesija.
14. FlowOS ne radi automatski merge. Korisnik je uvijek integrator.
15. Model ne verifikuje sam svoj rezultat kao konačan dokaz.
16. Prompt nije sigurnosna granica; dozvole se sprovode kodom i OS mehanizmima.
17. SQLite ostaje baza dok stvarna potreba ne dokaže da je potreban PostgreSQL.
18. Nema message brokera, mikroservisa, DAG enginea ni udaljenih workera u početnom opsegu.
19. Nema cloud telemetrije. Podaci ostaju lokalno.
20. Svaka nova složenost mora imati dokazanu potrebu i mjerljiv problem koji rješava.
21. Plan projekta nije samo Markdown dokument: potvrđene faze, stavke, acceptance kriterijumi i zavisnosti imaju strukturisani prikaz u bazi.
22. Svaka agentska sesija i svaki AgentReport moraju, kada je primjenjivo, biti vezani za tačno jednu planiranu stavku.
23. Status planirane stavke ne određuje samo agentova tvrdnja. Sistem razlikuje implementirano, verifikovano i korisnički prihvaćeno.
24. FlowOS ne zaključuje automatski da je proizvoljan dio Markdown plana završen. Import plana proizvodi prijedlog koji korisnik potvrđuje prije aktivacije.
25. Procenat napretka se ne prikazuje bez eksplicitnog i objašnjivog pravila računanja.

---

# 2. Cilj prve korisne verzije

Prva korisna verzija mora omogućiti da korisnik, bez obilaska terminala, za aktivni projekat vidi:

1. koji agenti rade;
2. na kojem zadatku rade;
3. u kojem direktoriju, branchu ili worktreeju rade;
4. koje fajlove stvarno mijenjaju;
5. gdje postoji preklapanje ili konflikt;
6. koji commitovi i provjere postoje;
7. gdje je svaka sesija stala;
8. koji tačno dio odobrenog plana agent trenutno realizuje;
9. koje su planirane stavke implementirane, verifikovane i korisnički prihvaćene;
10. šta je ostalo nedovršeno ili blokirano;
11. šta korisnik treba odlučiti.

Prva korisna verzija obuhvata faze 0–4. Minimalno strukturisano praćenje plana uvodi se već u fazi 1, jer bez veze između plana, taska, sesije, dokaza i izvještaja FlowOS pokazuje aktivnost, ali ne i stvarni napredak projekta. Managed Execution, durable poslovi i multiagent verifier dolaze tek nakon što je osnovni wrapper svakodnevno korišten.

---

# 3. Topologija procesa

```text
flowos-gui.exe
┌────────────────────────────────────────────────────┐
│ View                                               │
│ PySide6 ekrani, widgeti, modeli prikaza, delegati  │
│        ↓                                           │
│ Controller                                         │
│ tok ekrana, korisničke namjere, mapiranje rezultata│
│        ↓                                           │
│ GUI Services                                       │
│ API klijent, WebSocket klijent, lokalne postavke   │
└───────────────────────┬────────────────────────────┘
                        │ localhost HTTP/WebSocket
                        ▼
flowos-service.exe
┌────────────────────────────────────────────────────┐
│ API Controllers                                    │
│ FastAPI rute i WebSocket ulaz                      │
│        ↓                                           │
│ Backend Services                                   │
│ sesije, Git, watcher, konflikti, reporti, poslovi  │
│        ↓                                           │
│ interne implementacije Services sloja              │
│ SQLite, filesystem, subprocess, Job Objects        │
└───────────────────────┬────────────────────────────┘
                        │
                        ▼
Claude Code │ Codex │ pi │ Generic CLI │ Git worktree

flowos.exe
┌────────────────────────────────────────────────────┐
│ CLI View: Typer komande i terminalni prikaz        │
│        ↓                                           │
│ CLI Controller                                     │
│        ↓                                           │
│ CLI Services: API klijent + offline spool          │
└────────────────────────────────────────────────────┘
```

## 3.1 Zašto tri izvršna ulaza

- `flowos-gui.exe` prikazuje stanje i šalje korisničke komande.
- `flowos-service.exe` je jedini vlasnik baze, watchera i agentskih procesa.
- `flowos.exe` je wrapper i CLI kojim se sesije prirodno registruju kao nusprodukt rada.

GUI može biti zatvoren, a backend i wrapped sesije nastavljaju raditi.

## 3.2 Pokretanje servisa

MVP ne uvodi system tray unutar backend procesa. Miješanje Qt event loopa i FastAPI servera u istom procesu stvara nepotrebnu složenost.

Redoslijed:

1. GUI i CLI čitaju `%LOCALAPPDATA%\FlowOS\runtime\service.json`.
2. Ako je servis dostupan, koriste njegov port i verziju protokola.
3. Ako nije dostupan, GUI pokušava pokrenuti `flowos-service.exe`.
4. Servis koristi single-instance lock/mutex.
5. Servis bira slobodan loopback port i upisuje runtime descriptor.
6. Servis sluša samo na `127.0.0.1`.
7. Per-user autostart se uvodi nakon stabilnog MVP-a preko Task Schedulera ili Startup mehanizma.

Opcioni `flowos-tray.exe` može se dodati kasnije samo ako se pokaže da korisniku stvarno treba stalna tray kontrola.

---

# 4. Troslojna arhitektura

## 4.1 View

View je isključivo prikaz i prikupljanje korisničkih akcija.

View smije:

- prikazati DTO/ViewModel podatke;
- emitovati Qt signal sa korisničkom namjerom;
- upravljati lokalnim vizuelnim stanjem: selekcija, fokus, proširen red, scroll;
- koristiti `QAbstractTableModel`, `QStyledItemDelegate` i `QPainter` za prikaz;
- prikazati loading, empty i error stanje koje mu preda Controller.

View ne smije:

- pozivati FastAPI direktno;
- pristupati bazi;
- izvršavati Git komande;
- pokretati procese;
- sadržavati pravila konflikta, atribucije ili statusnih tranzicija;
- donositi odluku da li je neka akcija dozvoljena;
- zavisiti od backend Services implementacija.

Primjer dozvoljenog View interfejsa:

```python
class SessionsView(QWidget):
    refresh_requested = Signal()
    end_session_requested = Signal(str)
    open_terminal_requested = Signal(str)

    def render(self, state: SessionsViewState) -> None:
        ...
```

## 4.2 Controller

Controller je koordinator toka.

Controller smije:

- povezati View signale sa akcijama;
- validirati UI format i obavezna polja;
- pozvati jedan ili više Service metoda;
- mapirati DTO u ViewState;
- odlučiti koji dio Viewa treba osvježiti;
- orkestrirati potvrdu korisnika prije rizične akcije;
- prevoditi servisne greške u korisnički razumljivo stanje.

Controller ne smije:

- sadržavati SQL;
- formirati Git ili shell komande;
- direktno koristiti `subprocess`;
- implementirati poslovna pravila;
- izračunavati atribuciju promjene;
- odlučivati o retry politici;
- mijenjati bazu mimo Service ugovora.

## 4.3 Services

Services sadrži ponašanje sistema.

Backend Services odgovornosti:

- projekti i zadaci;
- registracija i životni ciklus sesije;
- Git snapshoti i worktree operacije;
- filesystem događaji i debounce;
- atribucija promjena;
- konflikt pravila;
- verifikacija;
- izvještaji i artefakti;
- pokretanje i kontrola agentskih procesa;
- approval, retry, recovery i durable workflow u kasnijim fazama;
- persistence i migracije.

GUI Services odgovornosti:

- HTTP komunikacija;
- WebSocket pretplata;
- čitanje lokalne runtime konfiguracije;
- mapiranje transportnih grešaka;
- nikakva backend poslovna logika.

CLI Services odgovornosti:

- API pozivi;
- offline JSONL spool ako servis nije dostupan;
- kasnija idempotentna sinhronizacija spool događaja.

## 4.4 Dozvoljene zavisnosti

```text
GUI View → GUI Controller → GUI Services → shared contracts
API Controller → Backend Services → interne implementacije Services sloja
CLI View → CLI Controller → CLI Services → shared contracts
```

## 4.5 Zabranjene zavisnosti

```text
GUI View → GUI Services
GUI View → backend
GUI View → SQLite/Git/subprocess/filesystem
GUI Controller → SQLite/Git/subprocess/filesystem
Backend Services → GUI View/Controller/PySide6
Backend Services → FastAPI route objekti
API Controller → SQLite/Git/subprocess direktno
shared → bilo koji konkretan sloj
```

## 4.6 Automatsko sprovođenje granica

Uvesti `import-linter` ili ekvivalentan AST test najkasnije u fazi 1.

Obavezni ugovori:

1. `flowos.service.services` ne smije importovati `flowos.gui`.
2. `flowos.gui.views` ne smije importovati `flowos.gui.services`.
3. `flowos.gui.controllers` ne smije importovati backend interne module.
4. `flowos.service.controllers` ne smije importovati persistence implementacije direktno.
5. `flowos.shared` ne smije importovati `gui`, `service` ni `cli`.

Kršenje arhitektonske granice ruši `scripts/verify.py`.

---

# 5. Tehnološki stack

## 5.1 Produkcija

- Python 3.12
- PySide6, Qt Widgets
- FastAPI
- Uvicorn
- Pydantic v2 za transportne ugovore
- SQLAlchemy 2.x
- Alembic
- SQLite, WAL mode, foreign keys ON
- watchdog
- Typer za CLI
- `httpx` za CLI API klijent
- Qt `QNetworkAccessManager` i `QWebSocket` za GUI komunikaciju
- `pywin32` za Windows Job Objects i Windows specifičnu kontrolu procesa
- standardni `subprocess` za Git; ne uvoditi GitPython u MVP-u

## 5.2 Razvoj i verifikacija

- pytest
- pytest-qt
- pytest-asyncio
- coverage
- Ruff
- mypy
- import-linter ili projekat-specifični AST boundary test

## 5.3 Pakovanje

- `pyside6-deploy`/Nuitka za izvršne fajlove;
- Inno Setup za Windows installer nakon faze 4;
- reproducibilan build skript u `scripts/build.py`;
- Node nije dio build chaina.

## 5.4 Package management

Koristiti standardni `pyproject.toml`. `uv` je preporučeni razvojni alat, ali projekat mora ostati instalabilan i standardnim `pip` tokom.

---

# 6. Ciljana struktura repozitorija

Ne kreirati sve foldere unaprijed. Pi agent u svakoj fazi kreira samo ono što ta faza stvarno koristi. Ovo je ciljna struktura, ne nalog za stvaranje prazne infrastrukture.

```text
FlowOS/
├── pyproject.toml
├── README.md
├── AGENTS.md
├── CLAUDE.md
├── scripts/
│   ├── verify.py
│   ├── run_service.py
│   ├── run_gui.py
│   └── build.py                 # tek kada pakovanje postane stvarno
├── agent_reports/
├── project_rooms/               # kreirati kada prvi HIGH/CRITICAL plan nastane
├── docs/
│   ├── architecture/
│   │   ├── boundaries.md
│   │   └── decisions/
│   └── CONTEXT.md               # tek kada nastane evergreen znanje
├── src/flowos/
│   ├── shared/
│   │   ├── contracts/
│   │   ├── dto/
│   │   ├── enums/
│   │   ├── errors/
│   │   └── time.py
│   ├── gui/
│   │   ├── app.py
│   │   ├── composition_root.py
│   │   ├── views/
│   │   ├── controllers/
│   │   ├── services/
│   │   ├── models/              # presentation modeli, bez poslovne logike
│   │   ├── delegates/
│   │   ├── widgets/
│   │   └── theme/
│   ├── service/
│   │   ├── app.py
│   │   ├── composition_root.py
│   │   ├── controllers/
│   │   │   ├── http/
│   │   │   └── websocket/
│   │   └── services/
│   │       ├── projects/
│   │       ├── tasks/
│   │       ├── sessions/
│   │       ├── activity/
│   │       ├── attribution/
│   │       ├── conflicts/
│   │       ├── git/
│   │       ├── worktrees/
│   │       ├── verification/
│   │       ├── reports/
│   │       ├── execution/       # faza 6
│   │       ├── jobs/            # faza 8
│   │       ├── approvals/       # faza 6+
│   │       ├── usage/           # faza 7
│   │       └── infrastructure/  # interne implementacije Services sloja
│   │           ├── persistence/
│   │           ├── filesystem/
│   │           ├── process/
│   │           └── agent_adapters/
│   └── cli/
│       ├── app.py
│       ├── views/
│       ├── controllers/
│       └── services/
└── tests/
    ├── unit/
    ├── integration/
    ├── contract/
    ├── architecture/
    ├── gui/
    ├── windows/
    └── fixtures/
```

`infrastructure` nije četvrti arhitektonski sloj. To su interne tehničke implementacije koje koristi Services sloj. Ne smiju se pozivati iz Viewa ili Controllera.

Svaki executable ima jedan `composition_root.py`. Ne uvoditi dependency-injection framework. Zavisnosti se eksplicitno konstruišu na jednom mjestu.

---

# 7. Podatkovni model

Svi vremenski podaci čuvaju se u UTC, a GUI ih prikazuje u lokalnom vremenu. Identifikatori su UUID stringovi. ORM modeli ne napuštaju backend Services sloj; API vraća Pydantic DTO objekte.

## 7.0 Plan, faze i dokazivi napredak

Plan napretka je centralna veza između onoga što je dogovoreno, onoga što agent trenutno radi i dokaza da je rezultat prihvatljiv.

### Plan

```text
id, project_id, title, source_artifact_id nullable,
version, status, imported_at, activated_at, created_at

status:
DRAFT | ACTIVE | SUPERSEDED | ARCHIVED
```

Samo jedan plan po projektu može biti `ACTIVE`. Nova verzija plana ne prepisuje istoriju prethodne.

### PlanPhase

```text
id, plan_id, phase_key, title, description,
sequence, status, created_at, updated_at

status:
NOT_STARTED | IN_PROGRESS | BLOCKED | IMPLEMENTED |
VERIFIED | ACCEPTED | REJECTED
```

Status faze izvodi se iz njenih stavki, ali korisnik može potvrditi ili odbiti prelazak u `ACCEPTED`.

### PlanItem

```text
id, plan_phase_id, item_key, title, description,
sequence, risk_level, status, progress_source,
owner_session_id nullable, started_at, implemented_at,
verified_at, accepted_at, blocked_reason, created_at, updated_at

risk_level:
LOW | MEDIUM | HIGH | CRITICAL

status:
NOT_STARTED | IN_PROGRESS | BLOCKED | IMPLEMENTED |
VERIFIED | ACCEPTED | REJECTED

progress_source:
MANUAL | AGENT_REPORTED | EVIDENCE_DERIVED | USER_CONFIRMED
```

`item_key` je stabilan identifikator iz plana, npr. `FLOW-103`.

### PlanItemCriterion

Acceptance kriterijumi su zasebni zapisi da bi FlowOS mogao prikazati šta je tačno završeno, a šta nije.

```text
id, plan_item_id, criterion_key, description,
status, evidence_artifact_id nullable,
verification_summary, verified_at, verified_by,
created_at, updated_at

status:
PENDING | IN_PROGRESS | PASSED | FAILED |
NOT_APPLICABLE | NEEDS_REVIEW
```

### PlanItemDependency

```text
id, plan_item_id, depends_on_plan_item_id,
dependency_type, created_at

dependency_type:
BLOCKS_START | BLOCKS_VERIFICATION | INFORMATIONAL
```

Ciklične zavisnosti nisu dozvoljene.

### PlanProgressEvent

Append-only audit promjena statusa.

```text
id, plan_item_id, session_id nullable,
agent_report_id nullable, from_status, to_status,
reason, evidence_artifact_ids_json,
source, occurred_at

source:
USER | AGENT | VERIFICATION_SERVICE | IMPORTER | SYSTEM
```

### Pravila statusa

```text
NOT_STARTED
→ stavka nije početa

IN_PROGRESS
→ postoji aktivna sesija ili korisnik je označio početak

BLOCKED
→ dalji rad zahtijeva odluku, zavisnost ili otklanjanje problema

IMPLEMENTED
→ agent je završio izmjenu i predao report/diff, ali dokaz još nije dovoljan

VERIFIED
→ obavezni acceptance kriterijumi imaju odgovarajući dokaz

ACCEPTED
→ korisnik je prihvatio poslovni/UX/rizični ishod

REJECTED
→ rezultat nije prihvaćen; dalji rad zahtijeva novu odluku ili zadatak
```

Nije dozvoljen direktan skok `IN_PROGRESS → ACCEPTED` bez eksplicitnog korisničkog override-a i zapisanog razloga. `DONE` se ne koristi kao jedinstven status jer skriva razliku između tvrdnje, dokaza i prihvatanja.

### Veza plana sa taskom, sesijom i reportom

- `Task` može biti vezan za jedan `PlanItem`.
- `AgentSession` mora imati `plan_item_id` kada radi na stavci aktivnog plana.
- `AgentReport` mora navesti planiranu stavku, završene kriterijume, nezavršene kriterijume i rad van plana.
- Jedna sesija ne smije tiho raditi na više planiranih stavki. Ako je to potrebno, korisnik potvrđuje podjelu ili se kreiraju odvojene sesije/reporti.
- Promjena statusa plana uvijek ostavlja `PlanProgressEvent`.

## 7.1 Faza 1–5

### Project

```text
id, name, repo_path, status, notes, created_at, updated_at
```

### Task

```text
id, project_id, plan_item_id nullable,
title, description, status, priority,
created_at, updated_at, done_at
status: OPEN | IN_PROGRESS | BLOCKED | DONE
priority: LOW | NORMAL | HIGH | URGENT
```

### TaskContract

TaskContract direktno ugrađuje strukturisani intake iz agent metode.

```text
id, task_id,
goal,
working_hypothesis,
verify_hypothesis,
scope,
out_of_scope,
acceptance_criteria,
allowed_paths_hint,
risks,
risk_level,
approved_at,
created_at
risk_level: LOW | MEDIUM | HIGH | CRITICAL
```

### Decision

```text
id, project_id, task_id,
title, fact_found, decision_required, recommendation,
consequence, final_decision, rationale, decided_at
```

### AgentSession

```text
id, task_id, project_id, plan_item_id nullable,
agent_type, model_name, execution_mode, terminal_label,
session_role, launch_surface,
working_directory, repo_path, branch_name, worktree_path,
base_commit_sha, pid,
status, started_at, last_activity_at, ended_at, exit_code

execution_mode:
WRAPPED_TERMINAL | EXTERNAL_TRACKED | MANAGED | DURABLE

session_role:
IMPLEMENTATION | REVIEW | RESEARCH | VERIFICATION | MANUAL

launch_surface:
VSCODE | TERMINAL | FLOWOS_GUI | EXTERNAL

status:
ACTIVE | IDLE | COMPLETED | ABANDONED | NEEDS_REVIEW
```

### SessionEvent

Append-only.

```text
id, session_id, event_type, summary, payload_json,
source, idempotency_key, occurred_at

event_type:
STARTED | GIT_SNAPSHOT | COMMIT_OBSERVED | FILE_ACTIVITY |
CONFLICT_WARNING | VERIFY_RESULT | CHECKPOINT | NOTE |
COMPLETED | ABANDONED
```

### FileActivity

```text
id, session_id nullable, repo_path, file_path,
change_type, attribution, observed_at

attribution:
WORKTREE | SOLE_ACTIVE | HINT | UNATTRIBUTED | USER
```

Retention sirovih aktivnosti: 30 dana. Agregat ostaje u reportu.

### GitSnapshot

```text
id, session_id, snapshot_type, commit_sha, branch_name,
status_porcelain, diff_stat, changed_files_json, created_at
snapshot_type: START | PERIODIC | END
```

### AgentReport

AgentReport u bazi predstavlja strukturisani sažetak, ali se kompletna Markdown verzija čuva kao artefakt i prati `agent_report_template.md`.

```text
id, session_id, agent_job_id nullable, plan_item_id nullable,
status, scope, impact_summary, reproduction_summary,
plan_alignment_summary, completed_criteria_json,
incomplete_criteria_json, out_of_plan_work_json,
summary, rationale, implementation_summary,
untouched_scope, verification_summary,
independent_review_summary, found_issues,
rejected_options, conflicting_sources,
commit_shas, open_risks, follow_up,
user_confirmation_required, user_verdict,
created_at

user_verdict:
ACCEPTED | NEEDS_WORK | REJECTED | null
```

Sekcija bez sadržaja u Markdown exportu ostaje sa vrijednošću `Nema.` umjesto da bude izbrisana.

### AgentArtifact

```text
id, session_id nullable, agent_job_id nullable,
artifact_type, storage_key, sha256, size_bytes,
mime_type, retention_policy, created_at

artifact_type:
DIFF | PATCH | TEST_REPORT | LINT_REPORT | BUILD_REPORT |
STDOUT_LOG | STDERR_LOG | SCREENSHOT | HANDOFF |
CONTEXT_PACK | PROJECT_ROOM | AGENT_REPORT_MD |
CHECKER_REPORT | VERIFY_REPORT
```

## 7.2 Faza 6

### AgentJob

```text
id, project_id, task_id, task_contract_id,
workflow_type, risk_level, execution_mode,
requested_agent, selected_adapter, selected_model,
worktree_path, branch_name, base_commit_sha, result_commit_sha,
status, error_class, error_message,
created_at, started_at, completed_at, version

workflow_type:
CODING | REVIEW | PROBE

status:
DRAFT | QUEUED | RUNNING | WAITING_APPROVAL | PAUSED |
BLOCKED | COMPLETED | FAILED | CANCELLED
```

`PROBE` je throwaway istraživanje. Grana `probe/<slug>` se nikada automatski ne mergea.

### ApprovalRequest

```text
id, agent_job_id, action_type, risk_level, reason,
payload_artifact_id, status, requested_at, resolved_at,
idempotency_key
status: PENDING | APPROVED | REJECTED
```

## 7.3 Faza 7

### UsageRecord

```text
id, session_id nullable, agent_job_id nullable,
agent_type, model_name, input_tokens, output_tokens,
estimated_cost, duration_seconds, source, recorded_at
source: ADAPTER_REPORTED | ESTIMATED
```

## 7.4 Faza 8

### AgentStep

```text
id, agent_job_id, name, sequence, status,
attempt_count, max_attempts, timeout_seconds,
retry_policy, input_manifest, output_manifest,
started_at, completed_at, last_error_class, last_error_message

status: PENDING | RUNNING | COMPLETED | FAILED | SKIPPED
```

### StepAttempt

```text
id, agent_step_id, attempt_number, pid, status,
started_at, completed_at, exit_code, error_class,
error_message, stdout_artifact_id, stderr_artifact_id,
usage_json

status: RUNNING | COMPLETED | FAILED | LOST | CANCELLED
```

## 7.5 Faza 9

### CheckerReview

Worker report i checker review su odvojeni dokazi.

```text
id, agent_job_id, reviewer_agent, reviewer_model,
standards_review, spec_review, challenged_assumptions,
confirmed_findings, unconfirmed_findings,
ready_for_acceptance, evidence_artifact_id,
round_number, created_at
```

Najviše dvije review runde po jobu.

---

# 8. API ugovori

API Controlleri su tanki. Svaka ruta validira transportni oblik, poziva Service metodu i vraća DTO. Nema poslovne logike u ruti.

## 8.1 Sistem

```text
GET  /health
GET  /version
GET  /runtime
```

## 8.2 Plan i napredak

```text
GET    /projects/{project_id}/plans
POST   /projects/{project_id}/plans/import
GET    /plans/{plan_id}
POST   /plans/{plan_id}/activate
POST   /plans/{plan_id}/supersede

GET    /plans/{plan_id}/phases
GET    /plans/{plan_id}/items
GET    /plan-items/{id}
PATCH  /plan-items/{id}
POST   /plan-items/{id}/start
POST   /plan-items/{id}/block
POST   /plan-items/{id}/mark-implemented
POST   /plan-items/{id}/verify
POST   /plan-items/{id}/accept
POST   /plan-items/{id}/reject

GET    /plan-items/{id}/criteria
PATCH  /plan-item-criteria/{id}
GET    /plan-items/{id}/progress-events
GET    /projects/{project_id}/plan-progress
```

Import ne aktivira plan automatski. API vraća parser rezultat sa prepoznatim fazama, stavkama, kriterijumima, zavisnostima i listom nejasnoća. Korisnik potvrđuje ili ispravlja rezultat prije `activate`.

Statusne tranzicije se centralno validiraju u `PlanProgressService`. API Controller ne smije direktno mijenjati status kolone.

## 8.3 Projekti i zadaci

```text
GET    /projects
POST   /projects
GET    /projects/{id}
PATCH  /projects/{id}

GET    /tasks?project_id=...
POST   /tasks
GET    /tasks/{id}
PATCH  /tasks/{id}

GET    /tasks/{id}/contract
PUT    /tasks/{id}/contract
GET    /tasks/{id}/decisions
POST   /tasks/{id}/decisions
```

## 8.4 Sesije

```text
POST   /sessions
GET    /sessions/active
GET    /sessions/{id}
PATCH  /sessions/{id}
POST   /sessions/{id}/events
POST   /sessions/{id}/end
GET    /sessions/{id}/timeline
GET    /sessions/{id}/report
PATCH  /sessions/{id}/report
```

## 8.5 Aktivnost i konflikti

```text
GET    /activity/recent?project_id=...&limit=...
GET    /conflicts?project_id=...&status=open
POST   /conflicts/{id}/acknowledge
```

## 8.6 Worktree i Git

```text
POST   /worktrees
GET    /worktrees?project_id=...
POST   /worktrees/{id}/verify
POST   /worktrees/{id}/integrate/prepare
POST   /worktrees/{id}/cleanup
```

Integracija nikada ne izvršava automatski merge bez zasebne korisničke potvrde.

## 8.7 Verifikacija i artefakti

```text
POST   /verification/run
GET    /verification/{id}
GET    /artifacts/{id}
```

## 8.8 Managed i durable

```text
POST   /jobs
POST   /jobs/{id}/launch
POST   /jobs/{id}/cancel
POST   /jobs/{id}/pause
POST   /jobs/{id}/resume
GET    /jobs/{id}
GET    /jobs/{id}/timeline
GET    /jobs/{id}/steps
GET    /jobs/{id}/attempts
POST   /jobs/{id}/steps/{step_id}/retry
POST   /approvals/{id}/resolve
```

## 8.9 Greške

Sve API greške koriste isti format:

```json
{
  "code": "SESSION_NOT_FOUND",
  "message": "Sesija nije pronađena.",
  "details": {},
  "correlation_id": "uuid"
}
```

Interni traceback ne vraća se GUI-ju. Čuva se u lokalnom logu sa correlation ID-em.

---

# 9. WebSocket događaji

GUI dobija promjene uživo preko jednog WebSocket kanala.

Envelope:

```json
{
  "schema_version": 1,
  "event_id": "uuid",
  "type": "session.updated",
  "occurred_at": "2026-07-31T10:45:18Z",
  "project_id": "uuid",
  "payload": {}
}
```

Početni događaji:

```text
service.ready
project.updated
task.updated
plan.imported
plan.activated
plan_item.updated
plan_item.criterion.updated
plan_progress.updated
session.created
session.updated
session.completed
file_activity.created
conflict.created
conflict.updated
git_snapshot.created
verification.completed
report.updated
```

Kasnije:

```text
job.updated
job.step.updated
approval.requested
usage.recorded
checker_review.created
```

WebSocket nije izvor istine. Nakon reconnecta GUI poziva REST refresh za trenutno stanje. Događaji samo ubrzavaju prikaz.

---

# 10. Wrapper i režimi sesije

## 10.1 Komande

```powershell
flowos session start --agent claude-code --task FLOW-42
flowos session start --agent codex --task FLOW-43 --worktree
flowos session start --agent pi --model glm --task FLOW-44
flowos session start --agent pi --task FLOW-45 --hint "src/flowos/service/**"

flowos session list
flowos session end <session-id>
flowos worktree new --task FLOW-43
flowos worktree integrate <worktree-id>
flowos worktree clean
flowos report <session-id>

# faza 8+
flowos job submit --task FLOW-50 --workflow coding
flowos job status <job-id>
```

## 10.2 Primarni tok `session start`

1. CLI View parsira komandu.
2. CLI Controller validira obavezne argumente.
3. CLI Service pronalazi backend preko runtime descriptora.
4. Registruje sesiju preko API-ja sa idempotency ključem.
5. Backend SessionService snima startni Git snapshot.
6. Ako je `--worktree`, WorktreeService kreira branch i worktree.
7. ProcessService pokreće agent CLI kao child proces u Windows Job Objectu.
8. Watcher i Git polling prate aktivnost.
9. Na izlazu se snima završni snapshot, exit code, commitovi i diff stat.
10. Ako postoji `scripts/verify.py`, VerificationService ga pokreće.
11. ReportService pravi draft izvještaja.
12. Status postaje `COMPLETED` ili `NEEDS_REVIEW`.

## 10.3 Offline spool

Wrapper nikada ne piše direktno u SQLite.

Ako backend nije dostupan:

```text
%LOCALAPPDATA%\FlowOS\spool\<session-id>.jsonl
```

Svaki zapis ima idempotency ključ. Kada se servis vrati, CLI ili servis uvozi spool redom. Uvoz mora biti siguran za ponavljanje.

## 10.4 Oporavak mrtve sesije

Pri startu servisa:

1. pronađi sesije sa statusom ACTIVE/IDLE;
2. provjeri PID i vlasništvo procesa;
3. ako proces nije živ, snimi završni Git snapshot;
4. ako postoji nejasan dirty state, postavi `NEEDS_REVIEW`;
5. ne pokušavaj automatski nastaviti wrapped terminal sesiju.

---

# 11. Watcher, Git i atribucija

## 11.1 Izvori signala

- watchdog za create/modify/delete;
- Git polling svakih 30 sekundi po aktivnom repou;
- PID i exit code;
- strukturirani adapter događaji kada ih alat stvarno podržava.

Ignore lista:

```text
.git/
.worktrees/
node_modules/
.venv/
venv/
__pycache__/
dist/
build/
generated/
backups/
```

Lista je konfigurabilna po projektu.

## 11.2 Concurrency model

Watchdog callback ne piše direktno u bazu.

```text
watchdog thread
→ normalizovan event
→ bounded queue
→ debounce/coalescing 500 ms
→ ActivityService
→ persistence
→ WebSocket emit
```

Git i filesystem operacije koje mogu blokirati event loop izvršavaju se u kontrolisanom thread poolu.

## 11.3 Atribucija

```text
Fajl unutar worktreeja sesije X
→ WORKTREE, visoka pouzdanost

Dijeljeni tree + samo jedna aktivna sesija
→ SOLE_ACTIVE, srednja pouzdanost

Dijeljeni tree + više sesija + hint match
→ HINT, srednja pouzdanost

Dijeljeni tree + više sesija bez dokaza
→ UNATTRIBUTED, niska pouzdanost

Nijedna aktivna sesija
→ USER
```

GUI nikad ne prikazuje heuristiku kao sigurnu činjenicu.

## 11.4 Početna pravila konflikta

| Situacija | Nivo | Akcija |
|---|---|---|
| Dvije aktivne sesije upisuju isti fajl u istom treeju unutar 10 min | VISOKO | preporuči worktree |
| Sesija upisuje fajl koji je druga mijenjala u zadnjih 30 min | SREDNJE | prikaži obje sesije i diff |
| Branch ili HEAD se promijeni ispod aktivne sesije | SREDNJE | zabilježi i upozori |
| Sesija nema aktivnost i nema živ proces >30 min | INFO | predloži ABANDONED |
| Završetak ima izmjene bez commita | INFO | dodaj u report |

Ne dodavati nova pravila dok stvarni dnevnik ne pokaže ponovljen problem.

---

# 12. Git i worktree pravila

## 12.1 Snapshot komande

```bash
git rev-parse HEAD
git branch --show-current
git status --porcelain=v2
git diff --stat <base_commit>
git diff --name-status <base_commit>
```

Puni diff se snima na završetku kao artefakt, ne pri svakom pollu.

## 12.2 Pravila

- implementacija kroz FlowOS ne radi direktno na glavnoj grani;
- jedan writable worktree ima najviše jednu writer sesiju;
- verifier je read-only;
- integracija je korisnička akcija;
- napušteni worktree se ne briše prije pregleda i retention perioda;
- `git add -A` i `git add .` su zabranjeni agentima;
- commit mora navesti tačne fajlove ili logički ograničenu grupu.

## 12.3 Naming

```text
branch:   flow/<task-id>-<slug>
worktree: <repo-parent>/worktrees/<task-id>/
probe:    probe/<task-id>-<slug>
```

## 12.4 Integracija

`worktree integrate` vodi korisnika kroz:

1. diff prema base commitu;
2. verify unutar worktreeja;
3. prikaz poznatih konflikata;
4. korisničku potvrdu merge/rebase akcije;
5. završni verify na ciljnoj grani;
6. report i verdict;
7. retention prije cleanup-a.

---

# 13. GUI plan prema odobrenom mockupu

## 13.1 Tehnička pravila GUI-ja

- Qt Widgets, ne QML;
- layouts umjesto ručnih koordinata;
- `QTableView` + `QAbstractTableModel` za podatkovne tabele;
- `QStyledItemDelegate` za badgeve, status tačke i složene ćelije;
- `QPainter` za timeline i specifične vizuelne elemente;
- SVG ikone kroz Qt resource sistem;
- centralni design tokeni;
- QSS za boje, tipografiju, padding i osnovne border stilove;
- ne stvarati widget po svakoj tabelarnoj ćeliji;
- ne koristiti skupe shadow efekte na velikom broju kartica;
- nijedna mrežna ili disk operacija ne smije blokirati GUI thread.

## 13.2 Design tokeni

Kreirati `theme/tokens.py` kao jedini izvor vizuelnih vrijednosti:

```text
spacing: 4, 8, 12, 16, 24, 32
radius: 4, 6, 8, 12
font sizes: 11, 12, 13, 14, 18, 24
panel heights i minimalne širine
status semantic tokens: success, warning, danger, info, muted
```

Tačne boje se izvlače iz mockupa tokom GUI probe-a i potvrđuju screenshotom. Ne rasipati hex vrijednosti po widgetima.

## 13.3 Responsiveness i DPI

Obavezno dokazati ponašanje na:

- 1920×1080 pri 100%;
- 1920×1080 pri 125%;
- 1600×900 pri 100%;
- 2560×1440 pri 125% ili 150%.

Koristiti minimalne/maksimalne širine i `QSplitter`. Fiksne dimenzije su dozvoljene samo za ikone, badgeve i elemente čija je veličina namjerno konstantna.

## 13.4 Ekran Pregled

### View

`OverviewView`

Sadrži:

- sidebar;
- topbar za projekat i zadatak;
- stat kartice;
- aktivne sesije;
- nedavne promjene;
- konflikte;
- brze dokaze;
- sažetak zadatka;
- napomenu;
- timeline događaja.

### Controller

`OverviewController`

Odgovornosti:

- učitavanje trenutnog projekta i zadatka;
- paralelno traženje overview podataka kroz GUI Services;
- mapiranje u `OverviewViewState`;
- reakcija na WebSocket događaje;
- debounce refresha;
- otvaranje detaljnog ekrana;
- confirmation flow za `Završi`, `Prebaci u worktree` i integraciju.

### GUI Services

- `OverviewClientService`
- `SessionClientService`
- `ConflictClientService`
- `VerificationClientService`

Services ne znaju ništa o konkretnim widgetima.

## 13.5 Aktivne sesije

Koristiti `QTableView`, ne karticu po redu sa desetinama widgeta.

Kolone:

```text
Agent/Model | Uloga | Direktorij/Branch | Promjene |
Zadnja aktivnost | Status | Kontrole
```

Kontrole u redu se realizuju delegate-om ili jednom kontekstnom akcijom, ne trajnim `QPushButton` widgetom u svakoj ćeliji ako broj redova raste.

## 13.6 Nedavne promjene

Kolone:

```text
Vrijeme | Sesija | Fajl | Promjena | Atribucija | Izvor
```

Atribucija prikazuje i tekst i semantičku boju:

- Visoka — worktree;
- Srednja — heuristika;
- Niska — shared tree;
- Nepoznato.

## 13.7 Konflikti

`ConflictCard` je custom widget jer sadrži opis, rizik, dokaze i dvije akcije.

Akcije:

- `Poredi promjene`;
- `Prebaci u worktree`.

Controller traži svježe stanje prije izvršenja akcije. View ne pretpostavlja da je konflikt i dalje aktivan.

## 13.8 Timeline

Custom `TimelineWidget` prikazuje sažetak događaja. Ne prikazuje svaki token ni svaki raw filesystem događaj.

Tri nivoa detalja:

1. sažetak;
2. poslovno relevantan timeline;
3. tehnički detalji i artefakti.

## 13.9 Napredak po planu

FlowOS mora imati dvije razine prikaza.

### Sažetak na Overview ekranu

Desni ili centralni panel prikazuje:

```text
NAPREDAK PO PLANU

Faza 1 — Temelj i prvi vertikalni tok
3/7 prihvaćeno · 1 u radu · 1 blokirano

FLOW-103 Service runtime
U RADU · pi · 42 min

5/7 kriterijuma završeno
1 test ne prolazi

[Otvori stavku] [Otvori report]
```

Ne prikazivati procenat ako stavke imaju različitu težinu bez definisanog pravila. Podrazumijevani prikaz koristi broj kriterijuma i statusne brojeve.

### Poseban ekran `PlanProgressView`

Prikazuje:

- aktivnu verziju plana;
- faze redoslijedom;
- stavke po fazi;
- zavisnosti;
- status `NOT_STARTED/IN_PROGRESS/BLOCKED/IMPLEMENTED/VERIFIED/ACCEPTED/REJECTED`;
- vezanu agentsku sesiju;
- acceptance kriterijume i njihove dokaze;
- agent report;
- commitove i verify artefakte;
- rad van plana;
- razlog blokade;
- sljedeću dozvoljenu stavku.

### Controller i Services

- `PlanProgressController`
- `PlanClientService`
- `PlanImportController`
- `PlanImportClientService`

Controller koordinira korisničku potvrdu statusa i importa. View ne računa napredak niti određuje tranzicije.

### Detalj planirane stavke

Klik na `FLOW-103` prikazuje:

```text
Status: IN_PROGRESS
Agent: pi
Aktivna sesija: SESSION-42

Planirani kriterijumi:
✓ FastAPI app sa lifespan-om
✓ single-instance mutex
✓ runtime descriptor
✓ /health i /version
◐ graceful shutdown
○ strukturisani logovi

Dokazi:
- commit: a8f19d2
- verify: 18/19 prolazi
- report: agent_reports/2026-07-31_FLOW-103.md
- otvoreni problem: descriptor ostaje nakon force terminate
```

### Pravila prikaza

- `IMPLEMENTED` nije vizuelno isto što i `VERIFIED`.
- `VERIFIED` nije vizuelno isto što i `ACCEPTED`.
- Agentova tvrdnja se označava kao `AGENT_REPORTED`.
- Dokazi se prikazuju uz konkretan kriterijum.
- Status bez dokaza mora biti vidljivo označen.
- Rad van plana dobija upozorenje i traži korisničku odluku: prihvati kao novu stavku, veži za postojeću ili odbaci iz scope-a.

## 13.10 Ostali ekrani

Faze 1–4:

- Projekti;
- Zadaci;
- Sesije;
- Timeline;
- Nedavne promjene;
- Provjere;
- Worktrees;
- Postavke.

Faza 5:

- Inbox;
- Danas;
- Review;
- Decisions;
- Task Contract.

Faza 6+:

- Poslovi;
- Novi posao;
- Odobrenja;
- Job detalji;
- Troškovi i evaluacija.

---

# 14. Verifikacija

Svaki repo koji FlowOS nadzire može imati jednu standardnu ulaznu tačku:

```text
scripts/verify.py
```

FlowOS vlastiti repo mora je imati od faze 1.

## 14.1 `scripts/verify.py`

Početni redoslijed:

1. Ruff format check;
2. Ruff lint;
3. mypy;
4. architecture boundary test;
5. unit tests;
6. integration testovi koji ne zahtijevaju Windows;
7. Windows testovi kada je platforma Windows;
8. GUI smoke test;
9. build smoke tek kada build postoji.

Skripta vraća jasan exit code i piše strukturisani izvještaj kao artefakt.

## 14.2 Definition of Done po tipu promjene

### View

- screenshot prije/poslije ili referentni mockup;
- ručna provjera na stvarnom ekranu, ne samo offscreen render;
- provjera najmanje dvije rezolucije/DPI kombinacije;
- signal/akcija ne sadrži poslovnu logiku;
- nema blokiranja GUI threada.

### Controller

- test: View signal → Service poziv → novi ViewState;
- test error i loading toka;
- nema direktnog SQL/Git/subprocess importa;
- Controller ostaje tanak.

### Services

- unit test poslovnog pravila;
- integration test na privremenoj bazi/repozitoriju kada postoji I/O;
- greške su eksplicitne i mapirane;
- idempotency je testiran za ponovljive write akcije.

### Baza/migracija

- migracija na praznoj bazi;
- migracija na fixture bazi prethodne verzije;
- rollback ili dokumentovan razlog ako rollback nije siguran;
- nikad prvi put na stvarnim podacima.

### Git/worktree

- test na privremenom Git repou;
- dirty tree;
- promijenjen HEAD;
- konflikt;
- stageovane i nestageovane promjene;
- dokaz da se tuđ WIP ne dira.

### Watcher/atribucija

- create/modify/delete;
- debounce;
- ignored folderi;
- jedan aktivan writer;
- više writera;
- worktree atribucija;
- korisnička izmjena bez sesije.

### Process control

- normalan izlaz;
- child proces sa potomkom;
- soft cancel;
- hard cancel;
- Job Object ubija cijelo stablo;
- recovery nakon pada servisa.

### Pakovanje

- clean build;
- start servisa;
- start GUI-ja;
- kreiranje baze;
- osnovni API health;
- uninstall ne briše korisničke podatke bez potvrde.

## 14.3 Hijerarhija dokaza

```text
deterministički test
→ integration test
→ reproducibilan benchmark
→ build/package rezultat
→ golden/fixture poređenje
→ screenshot/video
→ ručna QA lista
→ agentovo objašnjenje
```

Agentovo objašnjenje nije dovoljan dokaz kada je jači dokaz moguć.

---

# 15. Sigurnost

1. Backend sluša samo na loopback interfejsu.
2. GUI i CLI otkrivaju servis preko runtime descriptora.
3. API koristi lokalni session token ili ekvivalentan mehanizam da slučajni lokalni proces ne upravlja FlowOS-om bez kontrole.
4. Eksterni API ključevi se čuvaju u Windows Credential Manageru, ne u SQLite bazi.
5. Environment agentskog procesa je filtriran; tajne se ne nasljeđuju automatski.
6. Logovi prolaze redakciju vjerovatnih tajni prije upisa.
7. Dependency instalacija, migracija, push i vanjske akcije traže approval u Managed toku.
8. Worktree nije sandbox.
9. Nepouzdan kod i udaljeni workeri nisu dio MVP-a.
10. Nijedan model nema proizvoljan shell iz Core logike; mogućnosti se daju kroz eksplicitne adaptere i dozvole.
11. Svi artefakti su unutar kontrolisanog FlowOS direktorija.
12. Ne bilježi se privatno rezonovanje modela ni token-by-token replay.

---

# 16. Retention i lokalni podaci

```text
%LOCALAPPDATA%\FlowOS\
├── runtime\
├── data\flowos.db
├── artifacts\
├── logs\
├── spool\
├── backups\
└── settings\
```

Politika:

- metadata, odluke, reporti, approvali: trajno;
- SessionEvent i GitSnapshot: trajno dok veličina ostaje razumna;
- FileActivity: 30 dana;
- stdout/stderr: 30–90 dana;
- veliki artefakti: po retention politici;
- napušteni worktreeji: najmanje 7–30 dana, pa ručno čišćenje;
- backup baze: dnevno;
- cleanup nikad ne dira aktivnu ili blokiranu sesiju/job.

SQLite backup koristi provjeren checkpoint/backup postupak, ne kopiranje aktivnog WAL seta naslijepo.

---

# 17. Agent adapteri

## 17.1 Redoslijed

1. Claude Code
2. pi
3. Codex
4. GenericCliAdapter

## 17.2 Capability model

```text
can_launch
can_stream_events
can_report_usage
can_cancel
can_use_worktree
```

Ne deklarisati capability koji alat stvarno ne podržava.

Namjerno izostavljeno dok prvi alat to ne ponudi:

```text
can_cooperative_pause
can_resume_step
can_request_approval
```

## 17.3 Adapter granica

Adapter zna:

- komandu;
- argumente;
- radni direktorij;
- dozvoljeni environment;
- kako prepoznaje izlaz;
- koje događaje može pouzdano emitovati.

Core Services ne zna konkretne CLI detalje pojedinačnog agenta.

---

# 18. Managed Execution, durable tok i verifier

## 18.1 Managed Execution — faza 6

Vertikalni tok:

```text
Task
→ potvrđen TaskContract
→ risk provjera
→ worktree
→ agent adapter
→ verify.py
→ diff + report
→ korisnički verdict
```

`PAUSED` znači: ne pokreći sljedeći korak. Ne znači zamrzavanje živog procesa.

## 18.2 Durable Job Engine — faza 8

Standardni sekvencijalni tok:

```text
PREPARE_CONTEXT
→ CREATE_WORKTREE
→ IMPLEMENT
→ VERIFY
→ WAIT_FOR_APPROVAL
→ FINALIZE
```

Faza 9 umeće:

```text
REVIEW → FIX_CONFIRMED → VERIFY
```

Nema DAG jezika.

## 18.3 Checkpoint

Checkpoint nije snimka modelovih misli.

Checkpoint je:

1. commit SHA;
2. `handoff.md` artefakt sa urađenim, otvorenim, rizicima, sljedećim korakom i ključnim fajlovima.

Resume kreće iz posljednjeg sigurnog commita i handoffa.

## 18.4 Retry

```text
TRANSIENT
→ ograničen automatski retry sa backoffom

RETRYABLE_WITH_REVIEW
→ najviše dva pokušaja, zatim BLOCKED

NON_RETRYABLE
→ BLOCKED ili FAILED, bez automatske petlje
```

Budžeti:

- pokušaji po koraku;
- ukupni pokušaji;
- ukupno trajanje;
- opcioni token/troškovni limit.

## 18.5 Side-effect barrier

Prije nepovratne akcije:

```text
provjeri approval
→ rezerviši idempotency ključ
→ zapiši ACTION_STARTED
→ izvrši
→ zapiši rezultat
```

`ACTION_STARTED` bez rezultata poslije restarta vodi u `BLOCKED`, ne u slijepi retry.

## 18.6 Verifier — faza 9

```text
Worker implementira
→ deterministički testovi
→ checker dobija contract + diff + rezultate + rizike
→ checker pokušava oboriti hipotezu
→ worker dobija samo potvrđene nalaze
→ završni verify
→ korisnički verdict
```

Checker ne dobija privatno rezonovanje workera.

Svaki nalaz mora imati:

- severity;
- fajl/lokaciju;
- problem;
- dokaz ili reprodukciju;
- vezu sa acceptance kriterijumom;
- prijedlog;
- confidence.

Nalaz bez dokaza ne vraća se workeru kao obavezna izmjena.

Najviše dvije review runde. Poslije toga odlučuje korisnik.

---

# 19. Ugradnja agent metode u sam FlowOS

FlowOS ne treba samo biti razvijan ovom metodom; kasnije treba podržati njene artefakte.

## 19.1 Task Contract ekran

Polja:

- Zadatak/cilj;
- radna pretpostavka;
- provjeri hipotezu;
- scope;
- šta se ne dira;
- acceptance kriterijumi;
- allowed paths hint;
- rizici;
- risk level;
- korisnička potvrda.

## 19.2 Project Room

Za HIGH/CRITICAL ili teško reverzibilnu odluku:

- cilj;
- pogođeni simboli/procesi;
- plan;
- šta se ne dira;
- prihvatljiv ishod;
- plan verifikacije;
- rollback;
- nezavisni checker;
- odbačene opcije;
- konfliktni izvori.

U FlowOS-u se čuva kao `PROJECT_ROOM` artefakt. Nakon završetka sadržaj se može konsolidovati u AgentReport, ali se original ne briše prije korisničkog prihvatanja i retention perioda.

## 19.3 Agent Report

UI i Markdown export prate postojeći template:

- Datum;
- Agent;
- Scope;
- Status izvora;
- Impact analiza;
- Reprodukcija prije izmjene;
- Kontekst korišten;
- Šta je urađeno;
- Zašto;
- Kako;
- Šta nije dirano;
- Verifikacija;
- Nezavisna provjera;
- Pronađeni problemi;
- Odbačene opcije;
- Konflikti;
- Commitovi;
- Rizici;
- Follow-up;
- Potrebna korisnička potvrda.

## 19.4 Usklađenost AgentReporta sa planom

Svaki report vezan za planiranu stavku mora imati dodatnu sekciju:

```markdown
## Usklađenost sa planom

- Plan: FlowOS v1
- Faza: Faza 1 — Temelj i prvi vertikalni tok
- Planirana stavka: FLOW-103 — Service runtime
- Status prije rada: IN_PROGRESS
- Predloženi status poslije rada: IMPLEMENTED

### Završeni acceptance kriterijumi
- [x] FastAPI app sa lifespan-om
- [x] single-instance mutex
- [x] runtime descriptor
- [x] /health i /version

### Nezavršeni acceptance kriterijumi
- [ ] graceful shutdown — force terminate ostavlja descriptor
- [ ] rotacija strukturisanih logova

### Rad van plana
Nema.

### Dokazi
- commit: ...
- verify artefakt: ...
- screenshot/log: ...

### Predloženi sljedeći korak
Završiti FLOW-103 prije FLOW-104.
```

Agent smije predložiti `IMPLEMENTED`, ali `VERIFIED` postavlja VerificationService ili korisnik uz dokaz. `ACCEPTED` postavlja samo korisnik.

## 19.5 Worker, checker, čovjek

FlowOS mora prikazivati tri odvojene tvrdnje:

1. worker kaže da je zadatak završen;
2. checker je potvrdio određene dokaze;
3. korisnik prihvata poslovni i rizični ishod.

Ne spajati ih u jedan status `DONE` bez objašnjenja.

---

# 20. Faze realizacije

Procjene su orijentacione. Gate prethodne faze je važniji od kalendara.

## Faza 0 — Validacija, bootstrap i PROBE zadaci

**Trajanje:** 3–5 radnih dana plus paralelno prikupljanje najmanje 10 stvarnih sesija.

### Cilj

Potvrditi ključne tehničke nepoznanice prije produkcione implementacije i pripremiti repo po agent metodi.

### Zadaci

#### FLOW-000 — Bootstrap repozitorija

**Rizik:** HIGH, jer postavlja arhitekturu i radna pravila.

Obavezno:

1. `git status --short`;
2. kreirati `project_rooms/<datum>_flowos-foundation.md`;
3. kreirati minimalni `pyproject.toml`;
4. uspostaviti `src/flowos`, `tests`, `scripts`, `agent_reports`;
5. napraviti `AGENTS.md` kao kanonski izvor pravila;
6. napraviti mali `CLAUDE.md` sa Claude-specifičnim dopunama ili referencom, bez dupliranja;
7. prenijeti potvrđene odluke iz ovog plana;
8. ukloniti duplikat universal fajla tek nakon što je sadržaj pravilno spojen;
9. kreirati početni `scripts/verify.py`;
10. napisati agent report.

**Ne raditi:** GUI funkcionalnost, bazu, watcher, job engine.

**Dokaz:** čist import skeleton, verify prolazi, architecture dokument postoji.

#### PROBE-001 — PySide6 mockup i DPI

Throwaway worktree/grana. Ne mergeati prototip.

Pitanje: može li odobreni ekran Pregled biti izveden u Qt Widgets bez ručnih koordinata i bez neprihvatljivog pada performansi?

Dokazi:

- skeleton sidebar/topbar/stat cards/table/conflict card/timeline;
- screenshot na najmanje tri DPI/rezolucije;
- mjerenje vremena prvog rendera;
- lista custom widgeta/delegata koji su stvarno potrebni;
- zaključak i preporuka.

Prototip se baca. U glavni repo ulazi samo dokazana odluka i design tokeni.

#### PROBE-002 — GUI ↔ FastAPI lifecycle

Throwaway worktree.

Pitanje: može li GUI pouzdano otkriti, pokrenuti i reconnectovati se na odvojeni lokalni servis?

Dokazi:

- service descriptor;
- health poziv;
- WebSocket događaj;
- restart servisa;
- GUI reconnect;
- nema blokiranja GUI threada.

#### PROBE-003 — Windows Job Object

Throwaway worktree.

Pitanje: može li servis pokrenuti dummy parent proces sa potomkom i pouzdano ugasiti cijelo stablo?

Dokazi:

- normalan izlaz;
- hard cancel;
- potvrda da potomak nije ostao živ;
- ponašanje kada servis padne.

#### FLOW-004 — Dnevnik stvarnih sesija

Korisnik i agent evidentiraju najmanje 10 stvarnih sesija:

```text
agent, model, projekat, task, tree/worktree,
trajanje, fajlovi, konflikt, završetak, report
```

Ovaj dnevnik određuje da li početna konflikt pravila odgovaraju stvarnom radu.

### Gate faze 0

- bootstrap pravila su potvrđena;
- tri probe-a imaju dokaz i odluku;
- nema produkcionog koda prenesenog iz throwaway probe grana;
- najmanje 10 sesija je mapirano ili je prikupljanje aktivno sa jasnim rokom;
- korisnik potvrđuje procesnu topologiju i GUI tehnologiju.

---

## Faza 1 — Temelj i prvi vertikalni tok

**Trajanje:** 1–2 sedmice.

### Cilj

Pokrenuti servis i GUI, registrovati projekat/zadatak/sesiju i prikazati stvarne podatke kroz puni View → Controller → Services tok.

### Zadaci

#### FLOW-101 — Shared contracts i error model

- DTO za Project, Task, Session i API error;
- versioned transport contracts;
- unit testovi validacije;
- shared ne importuje druge slojeve.

#### FLOW-102 — SQLite i migracije

- SQLAlchemy setup;
- WAL;
- foreign keys;
- Alembic baseline;
- Project, Task, AgentSession, SessionEvent;
- backend jedini writer;
- temp DB testovi.

#### FLOW-103 — Service runtime

- FastAPI app;
- composition root;
- single-instance lock;
- runtime descriptor;
- `/health`, `/version`;
- strukturisani lokalni logovi;
- graceful shutdown.

#### FLOW-103A — Plan model i statusna mašina

- Plan, PlanPhase, PlanItem, PlanItemCriterion, PlanItemDependency i PlanProgressEvent;
- centralna validacija statusnih tranzicija;
- zabrana cikličnih zavisnosti;
- audit svake promjene statusa;
- temp DB i Service testovi;
- bez Markdown importa u ovom zadatku.

#### FLOW-103B — Import potvrđenog FlowOS plana

- parser samo za strukturisani format ovog plana;
- izdvajanje `Faza`, `FLOW-xxx`, opisa, kriterijuma i zavisnosti;
- rezultat importa je DRAFT;
- lista nejasnoća i neprepoznatih sekcija;
- korisnička potvrda prije aktivacije;
- originalni Markdown ostaje source artefakt;
- nema generičkog AI zaključivanja da je nešto završeno.

#### FLOW-103C — Plan Progress API

- tanke rute;
- aktivacija plana;
- lista faza/stavki;
- statusne akcije kroz PlanProgressService;
- API contract testovi;
- concurrency/optimistic locking za statusne promjene.

#### FLOW-104 — Projects/Tasks Services i API Controllers

- tanke rute;
- Service testovi;
- API contract testovi;
- nema SQL-a u controllerima.

#### FLOW-105 — GUI shell

- MainWindow;
- sidebar;
- topbar;
- centralni stacked view;
- theme tokens;
- Overview placeholder;
- PySide6 View/Controller/Services skeleton;
- GUI Service za health i projects/tasks.

#### FLOW-105A — Plan Progress GUI skeleton

- `PlanProgressView`;
- `PlanProgressController`;
- `PlanClientService`;
- prikaz aktivnog plana, faza i stavki;
- status badgevi;
- detalj acceptance kriterijuma;
- loading/empty/error stanja;
- bez automatskog izračunavanja procenta.

#### FLOW-106 — Prvi vertikalni tok

```text
GUI View
→ ProjectController
→ ProjectClientService
→ FastAPI controller
→ ProjectService
→ SQLite
→ DTO nazad
→ ViewState
```

Prikazati stvaran projekat i zadatak u topbaru, kao i aktivnu planiranu stavku ako je task vezan za plan.

#### FLOW-107 — Architecture enforcement

- import-linter/AST pravila;
- test namjerno zabranjenog importa;
- verify skripta ruši build pri prekršaju.

### Gate faze 1

- servis preživi restart bez gubitka podataka;
- GUI se poveže, prikaže projekat i zadatak;
- View nema direktan API pristup;
- Controller nema bazu/Git/subprocess;
- architecture test prolazi;
- potvrđeni FlowOS plan se može importovati kao DRAFT i aktivirati nakon korisničke potvrde;
- faze, stavke i acceptance kriterijumi vide se u GUI-ju;
- statusne tranzicije ostavljaju audit događaj;
- sve migracije i contract testovi prolaze.

---

## Faza 2 — Wrapper, watcher i Aktivne sesije

**Trajanje:** 1–2 sedmice.

### Cilj

Svakodnevni agentski rad počinje prolaziti kroz FlowOS wrapper.

### Zadaci

#### FLOW-201 — CLI troslojni skeleton

- Typer View;
- CLI Controller;
- API Client Service;
- runtime discovery;
- standardni output format;
- obavezni `--plan-item` ili automatsko preuzimanje iz taska kada je task vezan za aktivni plan.

#### FLOW-202 — `session start/end/list`

- registracija;
- start/end Git snapshot;
- PID;
- exit code;
- backend nedostupan → spool;
- idempotentni sync;
- vezivanje sesije za PlanItem;
- aktivna sesija automatski predlaže `IN_PROGRESS`, ali ne mijenja prihvaćeni status bez pravila tranzicije.

#### FLOW-203 — Claude Code adapter

- capability deklaracija;
- komanda i argumenti;
- working directory;
- filtered environment;
- Job Object;
- cleanup.

#### FLOW-204 — Watcher pipeline

- watchdog;
- bounded queue;
- debounce;
- ignore pravila;
- persistence;
- WebSocket emit.

#### FLOW-205 — Git polling

- status porcelain v2;
- HEAD/branch;
- commit detection;
- 30s polling;
- testni privremeni repo.

#### FLOW-206 — AttributionService

- WORKTREE;
- SOLE_ACTIVE;
- HINT;
- UNATTRIBUTED;
- USER;
- test svih pravila.

#### FLOW-207 — Aktivne sesije GUI

- `SessionsView`;
- `SessionsController`;
- `SessionsClientService`;
- QTableView model;
- status delegate;
- Open terminal/Završi akcije kroz Controller;
- WebSocket refresh.

#### FLOW-207A — Aktivna stavka plana u sesiji

- session detalj prikazuje `plan_item_id`;
- PlanItem prikazuje aktivnu sesiju;
- WebSocket ažurira oba prikaza;
- pokušaj vezivanja jedne sesije za više stavki traži korisničku odluku;
- test prekida sesije i zadržavanja tačnog statusa plana.

#### FLOW-208 — Overview minimalni ekran

- stat kartice;
- aktivne sesije;
- zadnja aktivnost;
- bez konflikata i kompletnog timeline-a za sada;
- panel `Napredak po planu` sa aktivnom fazom, stavkom i brojem kriterijuma.

### Gate faze 2

- najmanje 80% jednog probnog radnog dana ide kroz wrapper;
- korisnik jednim pogledom vidi ko radi šta;
- wrapper overhead <30 s po sesiji;
- servis i GUI restart ne gube aktivno stanje;
- nema orphan child procesa u testu.

---

## Faza 3 — Konflikti, timeline, verify i reporti

**Trajanje:** 1–2 sedmice.

### Cilj

FlowOS detektuje stvarna preklapanja i svaka sesija završava dokaznim paketom.

### Zadaci

#### FLOW-301 — ConflictDetectionService

- početna pravila;
- konfigurabilni pragovi;
- open/acknowledged status;
- testovi lažno pozitivnih slučajeva.

#### FLOW-302 — Conflict GUI

- ConflictCard;
- poređenje promjena;
- akcija prebaci u worktree kao confirmation flow;
- svježa provjera prije akcije.

#### FLOW-303 — Session timeline

- poslovno relevantni eventi;
- paginacija;
- tehnički detalji odvojeni;
- reconnect refresh.

#### FLOW-304 — VerificationService

- detekcija `scripts/verify.py`;
- timeout;
- stdout/stderr artefakti;
- exit code;
- VERIFY_RESULT event.

#### FLOW-305 — ReportService

- draft report nakon sesije;
- Markdown export po template-u;
- prazne sekcije ostaju `Nema.`;
- obavezna sekcija `Usklađenost sa planom`;
- završeni i nezavršeni acceptance kriterijumi;
- rad van plana;
- predloženi status `IMPLEMENTED`;
- korisnički verdict;
- commit i verification dokaz.

#### FLOW-305A — PlanEvidenceService

- povezuje verify artefakt, commit, report i checker nalaz sa konkretnim kriterijumom;
- kriterijum ne prelazi u PASSED bez prihvatljivog dokaza;
- svi obavezni kriterijumi PASSED → PlanItem može preći u VERIFIED;
- neuspjeli obavezni kriterijum sprečava VERIFIED;
- korisnik može override samo uz razlog i audit događaj.

#### FLOW-306 — Brzi dokazi panel

- posljednji commit;
- broj izmijenjenih fajlova;
- test/lint/build status;
- vrijeme provjere;
- otvori izvještaj.

#### FLOW-307 — pi adapter

- capability model;
- launch;
- strukturirani eventi samo ako su stvarno dostupni;
- fallback na PID/Git/watcher.

### Gate faze 3

- namjerno WRITE/WRITE preklapanje se otkrije prije štete;
- svaka završena sesija ima report draft;
- verify rezultat je artefakt, ne samo tekst;
- GUI razlikuje visoku/srednju/nisku atribuciju;
- timeline ne prikazuje sirove evente bez vrijednosti;
- report jasno pokazuje koji dio plana je urađen, djelimičan ili nezavršen;
- agentova oznaka IMPLEMENTED ne prikazuje se kao VERIFIED;
- svaki VERIFIED status ima dokaz vezan za acceptance kriterijume.

---

## Faza 4 — Worktree tok i prva korisna verzija

**Trajanje:** oko 1 sedmica.

### Cilj

Dvije paralelne implementacije rade bez dijeljenog writable treeja, a korisnik ih može pregledati i integrisati.

### Zadaci

#### FLOW-401 — WorktreeService

- create;
- naming;
- list;
- status;
- retention;
- cleanup sa potvrdom.

#### FLOW-402 — Wrapper `--worktree`

- kreira branch/worktree;
- pokreće agenta u njemu;
- pouzdana atribucija;
- report vezan za worktree.

#### FLOW-403 — Guided integration

- diff pregled;
- verify prije integracije;
- prikaz konflikta;
- confirmation gate;
- završni verify;
- report/verdict;
- bez automatskog mergea.

#### FLOW-404 — Worktrees GUI

- aktivni/spremni/napušteni;
- base i result commit;
- verify status;
- akcije pregledaj, pripremi integraciju, cleanup.

#### FLOW-405 — Codex adapter

- capability model;
- wrapper launch;
- worktree provjera;
- cleanup.

#### FLOW-406 — MVP pakovanje

- build servis, GUI i CLI;
- lokalni installer;
- clean-machine smoke test;
- korisnički podaci odvojeni od instalacije.

### Gate faze 4

- dvije writer sesije u dva worktreeja;
- tačna atribucija;
- vođena integracija;
- verify prije i poslije integracije;
- instalacija na čistom testnom Windows profilu;
- FlowOS je koristan u stvarnom dnevnom radu.

---

## Faza 5 — Inbox, Danas, Review, Decisions i Task Contract

**Trajanje:** 2–3 sedmice.

### Cilj

FlowOS postaje lični operativni sistem i za ne-agentski rad.

### Sadržaj

- Inbox brzo bilježenje;
- Danas;
- sedmični Review;
- Decision zapis sa Fact/Decision/Recommendation/Consequence;
- TaskContract ekran;
- povezivanje Inbox → Task → Session/Job;
- prikaz razloga odlaganja;
- bez automatske AI klasifikacije dok ručni tok ne bude dokazan.

### Gate

- svaki netrivijalan agentski task ima odobren contract;
- odluke i razlozi se mogu pronaći bez čitanja cijelog chata;
- sedmični review daje jasan sljedeći potez.

---

## Faza 6 — Managed Execution

**Trajanje:** 3–4 sedmice.

### Sadržaj

- AgentJob;
- ApprovalRequest;
- adapter interface;
- Claude Code managed launch;
- Execution Console;
- timeout;
- soft/hard cancel;
- allowlist komandi;
- allowed paths;
- filtered environment;
- stdout/stderr artefakti;
- task → contract → worktree → agent → verify → diff → verdict;
- workflow type `PROBE`.

### Gate

Jedan ograničen stvarni coding task prolazi puni tok iz GUI-ja bez terminala, uključujući namjerni timeout i hard cancel.

---

## Faza 7 — Observability i evaluacija

**Trajanje:** 1–2 sedmice.

### Sadržaj

- UsageRecord;
- trošak i trajanje;
- izvor `ADAPTER_REPORTED` ili `ESTIMATED`;
- stopa prihvatanja;
- retry broj;
- trošak po prihvaćenoj promjeni;
- evaluation skup 10–20 stvarnih zadataka;
- poređenje modela po vrsti posla;
- bez OpenTelemetry dok nema stvarnog vanjskog konzumenta.

### Gate

Može se dokazom odgovoriti koji agent/model je najisplativiji za koju vrstu zadatka.

---

## Faza 8 — Durable Job Engine

**Trajanje:** 3–5 sedmica.

### Sadržaj

- AgentStep;
- StepAttempt;
- centralna validacija tranzicija;
- retry klasifikacija;
- budžeti;
- commit + handoff checkpoint;
- startup recovery;
- pause/resume između koraka;
- idempotency;
- side-effect barrier;
- fault injection testovi.

### Gate

Posao preživljava pad procesa i restart servisa, nastavlja iz posljednjeg sigurnog commita + handoffa i ne duplira rizičnu akciju.

---

## Faza 9 — Implementator + checker

**Trajanje:** 2–3 sedmice.

### Sadržaj

- CheckerReview;
- standards review;
- spec review;
- potvrđeni nalazi sa reprodukcijom;
- najviše dvije runde;
- poseban checker artefakt;
- evaluacija sa i bez checker-a na istom skupu.

### Gate

Verifier ostaje samo ako mjerljivo povećava prihvatanje uz prihvatljiv dodatni trošak. Ako ne, tok se gasi.

---

## Faza 10 — Samo po dokazanoj potrebi

Ne planirati datum.

Mogući sadržaj:

- udaljeni workeri;
- WorkerLease/heartbeat/fencing;
- PostgreSQL;
- container sandbox;
- mrežna/CPU/memory ograničenja;
- centralno skladište artefakata;
- VS Code ekstenzija tek nakon najmanje mjesec dana stabilnog wrapper toka.

---

# 21. Test matrica kritičnih slučajeva

## Session Coordination

- dvije writer sesije, isti tree, isti fajl;
- dvije sesije, različiti worktreeji;
- korisnik ručno mijenja fajl;
- wrapper ubijen;
- child ubijen;
- backend nedostupan;
- spool duplo uvezen;
- dirty tree na startu;
- HEAD promijenjen ispod sesije;
- djelimično stageovane promjene;
- sesija bez commita.

## Managed Execution

- normalan završetak;
- timeout;
- soft cancel;
- hard cancel sa potomcima;
- izlaz bez strukturiranog rezultata;
- promjena van dozvoljene putanje;
- dependency instalacija traži approval;
- GUI zatvoren dok posao radi.

## Durable

- kill prije checkpointa;
- kill poslije checkpointa;
- dupli completion event;
- restart sa RUNNING jobom;
- nejasan ishod vanjske akcije;
- potrošen retry budžet;
- nepoznate izmjene u worktreeju;
- pause pa resume.

## Verifier

- nalaz bez reprodukcije se odbacuje;
- checker ne vidi worker reasoning;
- dvije runde maksimum;
- standard review i spec review se vode odvojeno;
- mjeri se korist i trošak.

---

# 22. Metrike uspjeha

1. Udio sesija kroz wrapper: cilj >80% poslije mjesec dana.
2. Vrijeme da se utvrdi ko radi šta: <10 sekundi.
3. FlowOS overhead po sesiji: <30 sekundi.
4. Broj konflikata otkrivenih prije štete.
5. Udio sesija sa reportom i verdictom.
6. Broj lažnih konflikt upozorenja.
7. Vrijeme prvog rendera Overview ekrana.
8. GUI ne blokira duže od 100 ms zbog I/O rada.
9. Od faze 6: managed jobovi bez ručne intervencije.
10. Od faze 7: trošak po prihvaćenoj promjeni.
11. Od faze 8: uspješan recovery i nula dupliranih rizičnih akcija.
12. Od faze 9: razlika prihvatanja sa i bez checker-a.
13. Udio aktivnih sesija vezanih za planiranu stavku: cilj >90%.
14. Udio `VERIFIED` stavki sa dokazom za svaki obavezni kriterijum: cilj 100%.
15. Broj stavki označenih `IMPLEMENTED`, ali još neverifikovanih.
16. Broj otkrivenih radova van plana i vrijeme do korisničke odluke.
17. Vrijeme da korisnik utvrdi „šta je po planu gotovo i šta se trenutno radi“: cilj <10 sekundi.

---

# 23. Šta se namjerno ne gradi

| Stavka | Razlog | Uslov povratka |
|---|---|---|
| Electron/React/Node | nepotreban drugi runtime i frontend stack | ne vraća se bez potpuno novog proizvoda |
| QML | dodatni deklarativni sloj bez jasne koristi za data-heavy desktop | samo ako se pojavi UI koji Qt Widgets dokazano ne može razumno izvesti |
| Windows Service | otežava interakciju sa korisničkim terminalima | samo za odvojen headless worker |
| Tray unutar backend procesa | miješa event loopove i odgovornosti | poseban tray proces ako korisnik dokaže potrebu |
| Direktan CLI upis u SQLite | ruši single-writer pravilo | nikad; koristi spool |
| PostgreSQL | SQLite je dovoljan za lokalnog jednog korisnika | udaljeni/multi-worker režim |
| Message broker | nepotrebna složenost | više procesa/mašina sa dokazanim problemom |
| DAG/workflow jezik | sekvencijalni tok pokriva stvarne slučajeve | stvarni posao zahtijeva grananje |
| Automatski merge | integracija je ljudska odluka | nikad u ovom opsegu |
| Model voting | nije dokaz ispravnosti | nikad |
| Replay privatnog rezonovanja | nepotrebno i pogrešan model memorije | nikad |
| Container sandbox | worktree nije sandbox, ali MVP ne izvršava nepouzdan kod | faza 10 |
| VS Code ekstenzija | wrapper je jeftiniji dokaz vrijednosti | wrapper stabilan i korišten ≥1 mjesec |

---

# 24. Pravila rada pi agenta

## 24.1 Prije svakog zadatka

1. pročitaj `AGENTS.md`;
2. pročitaj relevantni TaskContract;
3. pročitaj aktivni PlanItem i njegove acceptance kriterijume;
4. potvrdi da su task, sesija i PlanItem ispravno povezani;
5. pokreni `git status --short`;
6. utvrdi postoji li tuđi WIP;
7. potvrdi ili odbaci radnu hipotezu dokazom;
8. uradi impact analizu;
9. klasifikuj rizik;
10. za HIGH/CRITICAL napravi project room i čekaj potvrdu;
11. za dugotrajan ili paralelan rad koristi zaseban worktree;
12. napiši 2–4 rečenice šta si razumio, koju stavku plana radiš i šta planiraš.

## 24.2 Tok zadatka

- ne širi scope;
- ne prelazi na drugu PlanItem stavku bez eksplicitne promjene zadatka;
- sav rad van plana odmah evidentiraj i traži korisničku odluku;
- ne mijenjaj arhitekturu usput;
- ne dodaj apstrakciju bez stvarne potrebe;
- ne miješaj refactor i funkcionalnu promjenu;
- ne izmišljaj poslovna pravila;
- ne pitaj korisnika činjenicu koju možeš provjeriti u kodu;
- ne odlučuj sam poslovnu, UX ili arhitektonsku odluku;
- ne koristi široki git add;
- ne prenosi kod iz PROBE grane direktno u produkciju.

## 24.3 Poslije zadatka

1. pokreni relevantne testove;
2. pokreni `scripts/verify.py` kada je primjenjivo;
3. provjeri `git status --short`;
4. commituj logičku cjelinu;
5. napiši `agent_reports/YYYY-MM-DD_naziv.md` po template-u;
6. popuni `Usklađenost sa planom`, završene i nezavršene kriterijume;
7. predloži status najviše `IMPLEMENTED`; ne proglašavaj `VERIFIED` ili `ACCEPTED`;
8. navedi šta nije provjereno;
9. za HIGH/CRITICAL obezbijedi nezavisnog checkera;
10. ne počinji sljedeći task bez korisničke potvrde ako task mijenja arhitekturu ili scope plana.

## 24.4 Standardni završni odgovor

```text
STATUS: OK | PARCIJALNO | BLOKIRANO
PLAN STAVKA: npr. FLOW-103
PREDLOŽENI STATUS PLANA: IN_PROGRESS | BLOCKED | IMPLEMENTED
ZAVRŠENI KRITERIJUMI: lista
NEZAVRŠENI KRITERIJUMI: lista
RAD VAN PLANA: Nema | opis
IZMIJENJENI FAJLOVI: lista
ŠTA JE URAĐENO: kratko
ŠTA NIJE URAĐENO: ako postoji
VERIFIKACIJA: komande i rezultati
REPORT: putanja
COMMITOVI: hash i poruka
PITANJA/ODLUKE: ako postoje
```

---

# 25. Prvi nalog koji treba dati pi agentu

```markdown
Pročitaj u cijelosti `FlowOS-novi-detaljan-plan-PySide6.md`, `METHOD.md`,
`BOOTSTRAP.md`, `agent_report_template.md` i `project_room_template.md`.

Radi isključivo zadatak FLOW-000 — Bootstrap repozitorija.

Prije izmjene:
1. pokreni `git status --short`;
2. prikaži Shared Understanding Check;
3. klasifikuj impact i rizik;
4. napravi project room jer se postavlja arhitektura cijelog projekta;
5. čekaj moju potvrdu project room plana prije upisa produkcionih fajlova.

Ne implementiraj GUI, bazu, FastAPI rute, watcher, wrapper ni adaptere.
Ne kreiraj foldere budućih faza bez stvarne potrebe.
AGENTS.md je kanonski izvor pravila za sve agente; CLAUDE.md ne smije
kopirati kompletan sadržaj i driftovati.

Nakon potvrde uradi samo minimalni skeleton, architecture boundary dokument,
početni verify.py i agent report. Ne prelazi na PROBE-001 bez moje nove
potvrde.
```

---

# 26. Konačni kriterij projekta

FlowOS nije uspješan zato što ima mnogo ekrana, tabela ili agentskih adaptera.

Uspješan je kada pouzdano i dokazivo odgovara:

1. šta je agent trebao uraditi;
2. šta je stvarno uradio;
3. gdje je radio;
4. koje je fajlove promijenio;
5. gdje je stao;
6. može li se bezbjedno nastaviti;
7. koji testovi, commitovi i artefakti potvrđuju rezultat;
8. šta checker jeste i nije potvrdio;
9. koji dio odobrenog plana je trenutno u radu;
10. šta je samo implementirano, šta je verifikovano, a šta korisnik prihvatio;
11. koji acceptance kriterijumi još nisu zadovoljeni;
12. da li je urađeno nešto van plana;
13. koju odluku korisnik sada treba donijeti.

Svaki dio sistema koji ne doprinosi jednom od ovih odgovora mora dokazati svoju vrijednost prije nego što se gradi.
