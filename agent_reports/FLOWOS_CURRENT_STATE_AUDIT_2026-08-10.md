# FlowOS — audit trenutnog stanja repozitorija

**Datum snimka:** 2026-08-10  
**Predmet:** stvarno stanje koda nakon commitovanja Crush implementacije i pratećih arhitektonskih/alatnih artefakata
**Metod:** čitanje izvornog koda, ORM modela, migracija, contracta, API kontrolera, GUI wiring-a i testova. Planovi i raniji izvještaji korišteni su samo za poređenje. GitNexus je nakon oba commita osvježen na 6.693 čvora, 10.685 veza i 176 execution flowova; kod ostaje primarni dokaz.

## Sažetak

FlowOS danas jeste Python desktop sistem sa tri izvršna ulaza: FastAPI servis, PySide6/Qt Widgets GUI i Typer CLI. Backend trajno čuva projekte, zadatke, planove, sesije, više vrsta događaja, konflikte, worktree metapodatke, izvještaje i materijalizovano „Gdje si stao“ stanje u SQLite bazi. Servis pri radu pokreće filesystem watchere po projektu, periodičnu detekciju konflikata i Git reconciliation. GUI je već povezan sa dijelom REST API-ja i WebSocket signalima, ali dio stranica je samo statički ili djelimično povezan.

Najvažnija činjenica za migraciju jeste da postoje paralelni koncepti: generički `Task` i planski `PlanItem`; direktna veza sesije sa jednim taskom i jednim plan itemom; najmanje četiri odvojena trajna toka aktivnosti/događaja; te dva različita značenja „agent reporta“ — Markdown konvencija u repositoryju i strukturisani `AgentReport` u bazi. Novi YAML front matter se ne parsira. Postoje i konkretna contract/model neslaganja u sada commitovanom kodu, zbog kojih neke nove funkcije ne mogu raditi kako su napisane.

## Osvježenje nakon commitovanja

Audit je prvobitno napravljen dok je dio pregledanog stanja bio necommitovan. To stanje je potom sačuvano u dva commita i više nije privremeni working-tree snapshot:

- `729c8da` — `fix: close P0 bugs, add P1 workflow, evidence bundle, and GUI fixes`: Crushov commit sa 21 fajlom, 2.423 dodate i 210 obrisanih linija. Uključuje prošireni GUI wiring i prikaze, shutdown/agent scan API, WebSocket i session/completion promjene, `EvidenceService` i njegove unit testove.
- `25ae36f` — `chore: preserve current FlowOS architecture and tooling work`: objedinjeni commit preostalih 37 fajlova, 14.451 dodatom i 181 obrisanom linijom. Uključuje arhitektonske ADR/feasibility dokumente, funkcionalne analize, PyInstaller/package artefakte, preostale CLI/GUI/backend fajlove, GitNexus skillove i ovaj audit.

Prije commita `25ae36f` pokrenut je `python scripts/verify.py`. Verifikacija nije prošla: Ruff je prijavio neformatirane fajlove, a migration roundtrip `sqlite3.OperationalError: table projects already exists`. Promjene su, po eksplicitnom korisničkom zahtjevu, commitovane bez popravljanja ili preformatiranja zatečenog koda. Poslije commita working tree je bio čist. Osvježavanje ovog dokumenta je jedina naknadna izmjena.

# 1. Identitet projekta

| Stavka | Stvarno stanje | Dokaz |
|---|---|---|
| Root | `C:\Users\38765\Desktop\FolowOS` | Git i filesystem pregled |
| Branch | `main` | `git branch --show-current` |
| HEAD | `25ae36f` (`chore: preserve current FlowOS architecture and tooling work`) prije ovog osvježenja dokumenta | `git rev-parse HEAD`, `git log --oneline` |
| Prethodni funkcionalni commit | `729c8da` (`fix: close P0 bugs, add P1 workflow, evidence bundle, and GUI fixes`) | `git show --stat 729c8da` |
| Working tree | Bio čist poslije `25ae36f`; sada sadrži samo ovo traženo osvježenje audit dokumenta | `git status --short` |
| Jezik/framework | Python ≥3.12; FastAPI, SQLAlchemy/Alembic, SQLite/WAL; PySide6 Qt Widgets; Typer | `pyproject.toml` |
| Backend start | `flowos-service` → `flowos.service.app:main`; alternativno `scripts/run_service.py`; PyInstaller spec postoji | `pyproject.toml`, `src/flowos/service/app.py`, `flowos-service.spec` |
| GUI start | `flowos-gui` → `flowos.gui.app:main`; alternativno `scripts/run_gui.py`; bez `--live` radi u mock režimu | `pyproject.toml`, `src/flowos/gui/app.py` → `main()` |
| CLI | `flowos` → `flowos.cli.app:main` | `pyproject.toml`, `src/flowos/cli/app.py` |

Glavni dependency/config fajlovi su `pyproject.toml`, `alembic.ini`, `alembic/env.py`, `.gitignore`, tri `flowos*.spec` PyInstaller fajla, `scripts/build.py`, `scripts/package.py`, `scripts/verify.py` i `scripts/guard_architecture.py`. Nema Node/Electron/QML build sloja.

Važna ograda: arhitektonske ocjene opisuju sadržaj commitova `729c8da` i `25ae36f`. Commitovanje dokazuje da su fajlovi sačuvani u Git istoriji, ali ne dokazuje da je svaka funkcionalnost ispravna; puna verifikacija prije `25ae36f` je pala.

# 2. Struktura repositoryja

```text
FolowOS/
├── src/flowos/
│   ├── service/                 FastAPI aplikacija, HTTP/WS kontroleri, domenski servisi
│   │   ├── controllers/http/    REST rute
│   │   ├── controllers/websocket/events.py
│   │   └── services/
│   │       ├── infrastructure/  SQLite, runtime, watcher, Git reader, adapteri
│   │       ├── projects, tasks, sessions, reports, worktrees
│   │       ├── plan_import.py, plan_progress.py, project_resume.py
│   │       └── conflicts, activity, attribution, reconciliation, evidence
│   ├── gui/                     PySide6 View → Controller → GuiApiClient
│   │   ├── views/               glavni prozor i stranice/paneli
│   │   ├── controllers/         GUI orkestracija bez baze/Git-a
│   │   └── services/client.py   REST klijent
│   ├── cli/                     Typer wrapper i HTTP klijent
│   └── shared/                  Pydantic contracti, enum-i, greške, vrijeme
├── alembic/versions/            šest migracija, jedna razgranata/nelinarna istorija
├── tests/                       unit, integration, architecture, contract, gui namespace
├── scripts/                     start, build/package, verify, architecture guard
├── agent_reports/               ručno održavani Markdown izvještaji
├── docs/                        planovi, korektivni nalozi, GUI specifikacije, backlog
├── arhitektura/                 ADR i agent-observability feasibility dokumenti
├── project_rooms/               plan rada visokog rizika
├── artifacts/                   runtime/verifikacioni artefakti; nije programski kod
├── assets/, screenshots/        GUI reference i snimci
└── metadata/, review_bundles/   pomoćni/review artefakti
```

`src/flowos/service/services/infrastructure/persistence/` je stvarni ORM sloj. Poseban repository/store interfejs ne postoji; servisi direktno koriste SQLAlchemy `Session` i ORM modele. `shared/contracts/` je API DTO sloj, dok GUI uglavnom koristi obične `dict` objekte, ne posebne GUI domenske modele.

# 3. Entry points i tok pokretanja

## Backend

1. `src/flowos/service/app.py` → `main()` kreira `RuntimeManager`, uzima single-instance lock, bira slobodan port i atomski piše runtime descriptor.
2. `_run_migrations()` importuje ORM module, poziva `Base.metadata.create_all(engine)` i best-effort `ALTER TABLE agent_sessions ADD COLUMN last_heartbeat_at`. Ovo nije puna Alembic migracija; greške su prigušene.
3. `src/flowos/service/composition_root.py` → `create_app(runtime, engine=None)` registruje sve REST routere i `/ws`, kreira jedan engine i `session_factory` na `app.state`.
4. FastAPI lifespan (`_make_lifespan`) učitava sve projekte, pokreće po jedan `WatcherPipeline` nad `Project.repo_path`, zatim background taskove: conflict detection svakih 60 s i reconciliation svakih 120 s.
5. Svaka HTTP ruta otvara kratku SQLAlchemy sesiju preko lokalno definisanog `get_session()` dependencyja. Nema centralnog Unit of Work objekta.
6. GUI/CLI do podataka dolaze isključivo HTTP-om; GUI dodatno sluša `/ws` i na relevantne evente radi refresh.

Dokaz: `src/flowos/service/app.py` → `main()`, `_run_migrations()`; `src/flowos/service/composition_root.py` → `create_app()`, `_make_lifespan()`, `_create_watcher_callback()`.

## GUI

`src/flowos/gui/app.py` → `main()` kreira `QApplication`, temu i `create_gui(use_live=...)`. `create_gui()` u `src/flowos/gui/composition_root.py` konstruiše `MainWindow`, konkretne View objekte, `GuiApiClient` i `OverviewController`. U live režimu čita port iz runtime descriptora i po potrebi pokušava pokrenuti servis. `FlowOsGui` spaja signale, periodično osvježava aktivni projekat i sluša WebSocket. Bez `--live`, GUI je mock/statički.

## CLI

`src/flowos/cli/app.py` definiše Typer komande za health, projects, tasks, plan progress/resume i session start/end/list. `CliApiClient` šalje REST pozive. CLI ne koristi adaptere da pokrene agenta; session komande registruju stanje oko zasebno pokrenutog procesa/alata.

# 4. Postojeći data model

## Centralni ORM modeli

### Project

**Fajl:** `src/flowos/service/services/infrastructure/persistence/models.py`  
**Svrha:** registrovani repository/projekat.  
**Polja:** `id`, `name`, `repo_path`, `status`, `notes`, timestamps.  
**Veze:** ORM veza na `Task`; ostale tabele koriste `project_id` bez svuda deklarisanih relationshipa.  
**Upotreba:** aktivna; CRUD API, watcher startup, reconciliation, GUI lista projekata.

### Task

**Fajl:** isti modul.  
**Svrha:** generički razvojni zadatak.  
**Polja:** project, title/description, `OPEN|IN_PROGRESS|BLOCKED|DONE`, priority, `done_at`, opcioni `plan_item_id`.  
**Veze:** Project; više `AgentSession`; opcioni FK na `PlanItem`.  
**Upotreba:** aktivna kroz `/tasks` i CLI; GUI `TasksPage` trenutno nema wiring za učitavanje taskova. Nema tipa `DecisionItem`/`ImplementationTask`.

### AgentSession

**Fajl:** isti modul.  
**Svrha:** registrovana agentska sesija ili praćeni proces.  
**Polja:** jedan `task_id`, jedan `plan_item_id`, project, agent/model, execution mode, repo/branch/worktree/base/result SHA, PID, status i vremena.  
**Veze:** Task i SessionEvent.  
**Upotreba:** aktivna kroz wrapper/API, GUI sessions, attribution, conflicts, completion. Model ne podržava da jedna sesija kroz vrijeme radi na više taskova; `SessionTaskBinding` ne postoji.

### SessionEvent

**Fajl:** isti modul.  
**Svrha:** append-only događaji jedne sesije.  
**Polja:** session, type, ljudski summary, JSON payload, source, idempotency key, occurred_at.  
**Upotreba:** aktivna u completion/timeline logici. Nema `project_id`, iako ga nova timeline ruta direktno filtrira — konkretno neslaganje.

## Plan model

### Plan

`plan_models.py`; project, title, source artifact ID, `DRAFT|ACTIVE|SUPERSEDED`, aktivacija i faze. Aktivno korišten.

### PlanPhase

`plan_models.py`; plan, key/title/description/sequence/status. Status se pri čitanju progressa izvodi iz itema i postavlja na ORM objekt; nije poseban dokazni događaj.

### PlanItem — posebno

**Naziv:** `PlanItem`  
**Fajl:** `src/flowos/service/services/infrastructure/persistence/plan_models.py`  
**Svrha danas:** jedna izvršiva stavka importovanog FlowOS plana, tipično `FLOW-103A`; istovremeno nosi opis posla, rizik, ownership sesije, workflow status i acceptance vremenske oznake.  
**Najvažnija polja:** `plan_phase_id`, `item_key`, title/description/sequence/risk, `status`, `progress_source`, `owner_session_id`, started/implemented/verified/accepted timestamps, `blocked_reason`.  
**Veze:** faza, kriterijumi i progress events; dependencies su zasebna tabela; `Task`, `AgentSession`, resume/external activity ga referenciraju.  
**Da li se koristi:** da, centralno za plan progress, sesije, completion, resume i GUI.  
**Ko ga koristi:** `PlanImportService`, `PlanProgressService`, `SessionService`, `SessionCompletionService`, `ProjectResumeService`, `EvidenceService`, `/plan-items/*`, GUI plan/resume paneli.  
**Stvarno značenje:** nije isto što i generički `Task`, niti eksplicitno razlikuje odluku od implementacije.

### PlanItemCriterion / PlanItemDependency / PlanProgressEvent

`PlanItemCriterion` čuva opis, status i opcioni evidence artifact/verifikaciju. `PlanItemDependency` čuva usmjereni FK i tip `BLOCKS_START|BLOCKS_VERIFICATION|INFORMATIONAL`. `PlanProgressEvent` je append-only audit statusne tranzicije sa opcionalnim session/report/evidence referencama; aktivno se piše pri importu i statusnim akcijama.

## Ostali ORM/read modeli

- `FileActivity` (`activity_models.py`): normalizovan watcher događaj, projekat/sesija, putanja, tip, atribucija/confidence, source i JSON metadata; aktivno korišten.
- `Conflict` (`conflict_models.py`): deduplikovani detektovani konflikt sa nivoom/tipom, session ID listom, evidence JSON i lifecycle statusom; aktivno korišten.
- `Worktree` (`worktree_models.py`): Git worktree metapodaci, jedna session veza, status, clean/conflict flag, retention i integration SHA; aktivno/djelimično korišten.
- `AgentReport` (`report_models.py`): strukturisani report vezan obavezno za jednu session, sadržajne sekcije, commits/files JSON, verdict i audit JSON; aktivno se kreira pri completionu i izlaže API-jem.
- `ProjectWorkspaceState`: zadnji poznati Git snapshot za reconciliation.
- `ProjectResumeState`: materijalizovani „Gdje si stao“ sa pointerima i tekstualnim sažetkom.
- `ProjectReconciliationEvent`: append-only razlika između prethodnog i novog Git stanja.
- `ExternalActivity`: ručno/automatski zabilježena vanjska promjena bez pouzdane atribucije.
- `GitState`, `GitChangeSet`, `VerificationResult`, `EvidenceBundle`, parser `Parsed*` tipovi: dataclass/read modeli, nisu SQL tabele.

Migracije postoje za baznu šemu, plan modele, resume modele, worktrees, phase-3 tabele i result SHA. Istorija je problematična: `d624...` slijedi resume migraciju, dok `96aa...` takođe dodaje `result_commit_sha` i slijedi `d624...`; runtime sada uglavnom koristi `create_all` plus jedan `ALTER`, ne `alembic upgrade`.

# 5. Plan import

Implementacija je u `src/flowos/service/services/plan_import.py`.

- Input: `PlanImportService.import_plan(project_id, markdown, source_artifact_id=None)` prima cijeli Markdown string.
- Naslov: prvi `# ` u prvih deset linija; fallback `FlowOS Plan`.
- Faze: samo heading oblika `## Faza <broj> — <naziv>` ili sa `-`.
- Stavke: samo `#### FLOW-<broj><opciono slovo> — <naziv>`, i samo poslije prepoznate faze.
- Rizik: `**Rizik:** LOW|MEDIUM|HIGH|CRITICAL`; default je `MEDIUM`.
- Acceptance criteria: jedna `**Dokaz:**` linija; numerisana lista neposredno poslije `Obavezno:` ili `Kriterij/Kriterijum:`; `**Ne raditi:**` postaje `OUT_OF_SCOPE` kriterij.
- Dependencies: ograničeni regex za rečenice sa „Završiti/prije/poslije/zavisi od/nakon“; sve druge FLOW reference postaju `INFORMATIONAL`.
- Nejasnoće: javni `PlanMarkdownParser.parse()` bilježi nepriznate H2 sekcije. Međutim servis koristi privatni `_parse_with_phases()`, koji ne sakuplja takve sekcije; praktično se nepriznate sekcije tiho gube. Ciklične dependencyje servis preskače i dodaje tekst u `unclear_sections`.
- Persistence: kreira `Plan(DRAFT)`, `PlanPhase(NOT_STARTED)`, `PlanItem(NOT_STARTED)`, criteria, dependency i inicijalni `PlanProgressEvent`.
- Originalni Markdown: postoji `source_artifact_id`, ali ovaj tok ne kreira niti čuva artifact sam.
- API: `POST /projects/{project_id}/import-plan` u `controllers/http/plan_progress.py`; očekuje JSON ključ `markdown_text`.
- GUI: `FlowOsGui._on_import_plan()` otvara `.md`, čita tekst i šalje isti endpoint sa `markdown_text`; u zatečenom kodu nema mismatcha u request ključu/pathu.
- Contract drift: postoji `PlanImportRequest/Response` Pydantic model, ali ruta prima obični `dict` i ne deklarira response model. Stvarni service rezultat dolazi kroz `PlanProgressService.import_plan()`, ne direktno kroz contract.
- Aktivacija nije automatska: import pravi DRAFT; poseban `POST /plans/{id}/activate` je potreban. GUI poslije importa emituje import rezultat kroz `plan_progress_received`, iako renderer inače očekuje project progress oblik (`plan`, `phases`, totals). To je GUI response-shape mismatch.
- Testovi: `tests/unit/test_plan_import.py` i `tests/integration/test_plan_progress_api.py::TestPlanImportApi` pokrivaju osnovni format, empty request i activation. Nema dokaza za YAML, proizvoljne plan formate ni čuvanje izvornog dokumenta.

Dokazi: `PlanMarkdownParser`, `PlanImportService.import_plan()`, `PlanImportService._parse_with_phases()`; `PlanProgressService.import_plan()`; `FlowOsGui._on_import_plan()`.

# 6. Project registration

Tok dodavanja projekta postoji kroz `POST /projects`, `ProjectCreate` i `ProjectService.create_project()`. Contract provjerava samo da je putanja apsolutna; ne provjerava da postoji, da je Git repository ili da sadrži plan/`agent_reports`. Projekat se čuva kao `name`, `repo_path`, status i notes.

GUI `ProjectsPage` prikazuje projekte dobijene iz `/projects`, ali zatečeni wiring ne pokazuje kompletan folder-picker/create form tok. CLI ima `project create`. Nakon kreiranja projekta u toku rada, `create_project` ruta ne pokreće novi watcher; watcher kolekcija se inicijalizuje za već postojeće projekte samo pri service startupu. Ovo je funkcionalna rupa, ne prijedlog.

Git detekcija pri registraciji: **NE POSTOJI**. Plan selection pri registraciji: **NE POSTOJI**; plan se naknadno importuje. Automatsko nalaženje `agent_reports`: **NE POSTOJI**. Recent projects kao poseban model: **NE POSTOJI**; lista je sortirana po `created_at`, ne po posljednjem otvaranju. Otvaranje postojećeg projekta znači izbor prvog/aktivnog Project zapisa u GUI-ju, ne filesystem discovery.

# 7. Git integracija

| Dio | Ocjena | Stvarno ponašanje i dokaz |
|---|---|---|
| Repo detection | DJELIMIČNO POSTOJI | `ProjectCreate` prihvata apsolutnu putanju; nema `git rev-parse --is-inside-work-tree` registracijske validacije. |
| Branch | POSTOJI | `GitStateReader.read_state()` → `git branch --show-current`; čuva se u session/workspace/reconciliation. |
| HEAD | POSTOJI | `git rev-parse HEAD`; base/result SHA u session/worktree. |
| Status | POSTOJI | porcelain v2, dirty/changed/untracked; čuva se i materijalizuje. |
| Diff sadržaj | NE POSTOJI | nema servis koji vraća puni `git diff`; ispravno se ne duplicira. |
| Commits | DJELIMIČNO POSTOJI | current SHA i reconciliation „new commits“ postoje; nema kompletan commit-history browser. |
| Worktrees | POSTOJI | create/list/get/cleanup/prepare integration/verify preko `WorktreeService`/`WorktreeManager` i `/worktrees`. |
| Attribution | POSTOJI HEURISTIČKI | exact worktree/repo/sole-session/hint logika u `AttributionService`; confidence se čuva. |
| Filesystem watch | POSTOJI | `watchdog` recursive watcher sa debounce i ignore listom. |
| Git polling/reconciliation | POSTOJI | 120 s loop čita Git i piše workspace/reconciliation/external activity. |
| Automatski merge | NE POSTOJI | prepare integration daje informacije; korisnik ostaje vlasnik integracije. |

Zatečena nova `ProjectStateService` referencira nepostojeća polja `Worktree.git_status`, `ProjectWorkspaceState.is_dirty` i slična; endpoint `/projects/{id}/state` zato nije pouzdano operativan.

# 8. Agent integracija

| Agent/dio | Stanje |
|---|---|
| Claude Code adapter | Implementiran (`ClaudeCodeAdapter`) sa command/env/capabilities; nije pronađen produkcijski poziv koji ga bira i pokreće iz API/GUI toka. |
| Codex adapter | Implementiran kao klasa; nije u `ADAPTER_REGISTRY` i nije produkcijski wired. |
| Pi adapter | Placeholder string `PiAdapter` u registryju; klasa/fajl ne postoji. |
| Crush | Samo process scanner prepoznaje ime i GUI/docs ga spominju; adapter/execution ne postoji. |
| DeepSeek | Implementiran API adapter i testiran; registry postoji u njegovom modulu, ali nema centralno wiring mjesto koje ga koristi za session launch. |
| Generic CLI | Samo dokumentovan u `agent_adapters/__init__.py`; implementacija ne postoji. |
| Process launcher | `AgentProcessLauncher` postoji, ali nije pozvan iz HTTP kontrolera/composition roota; navodni „Job Object“ je zapravo `CREATE_NEW_PROCESS_GROUP` i `TerminateProcess`, ne durable supervisor. |
| Process detection | Nova `agent_scanner.scan_agents()` koristi Windows `tasklist` za Claude/Codex/Crush/Pi/Cline/Cursor; `/agents/scan` i GUI Agents stranica ga koriste. |
| Session registration | Stvarno aktivno: CLI/API i GUI „Prati“ poziv kreiraju `AgentSession`. |
| Hooks/telemetry | Nema stvarnih Claude/Codex/Pi hook parsera ni token telemetry pipelinea. DeepSeek ispisuje usage na stderr, ali se ne persistira. |
| Context packages | Nema produkcijski model/tok; samo planovi. |

Važna greška u `SessionService.create_session()`: validacija plan itema koristi `plan_item.plan_id`, ali `PlanItem` ima `plan_phase_id`, ne `plan_id`. Kreiranje sesije sa `plan_item_id` zato nije ispravno.

# 9. `agent_reports`

Postoje dvije odvojene stvari:

1. repository folder `agent_reports/` sa ručno kreiranim Markdown dokumentima po agentskoj konvenciji;
2. SQLite tabela `agent_reports` sa ORM klasom `AgentReport` i `ReportService`.

Folder se ne skenira pri startupu, nema parser, watcher ni importer, i fajlovi se ne povezuju automatski sa agentom/taskom/sessionom. Jedina GUI akcija u starom sidebaru otvara folder kroz Windows Explorer. `ReportsPage` je statička/djelimična i nema dokazano REST učitavanje.

DB report se automatski kreira kao DRAFT u `SessionCompletionService`, veže za session, može dobiti user verdict i izvesti se u Markdown string preko `ReportService.to_markdown()`. Nije pronađen poziv koji taj string automatski zapisuje u repository `agent_reports/`.

YAML front matter: **NE POSTOJI PODRŠKA**. Pretraga koda nije našla YAML/front-matter parser. Novi format iz zahtjeva sistem danas ne razumije. Report nije autoritet korisničkog prihvatanja dok `set_verdict()` eksplicitno ne postavi verdict, što je dobra postojeća granica.

# 10. Event / history / activity sistem

| Stvarni naziv | Šta čuva | Izvor | Aktivnost |
|---|---|---|---|
| `SessionEvent` | događaje vezane za session, summary/payload/source/idempotency | wrapper/completion/verification | aktivan |
| `FileActivity` | raw filesystem create/modify/delete + atribuciju | watcher | aktivan |
| `PlanProgressEvent` | statusne tranzicije PlanItema i reference dokaza | import/status servis | aktivan |
| `ProjectReconciliationEvent` | razliku prethodnog/trenutnog Git stanja i user resolution | reconciliation | aktivan/djelimičan |
| `ExternalActivity` | sažetak vanjskih Git promjena bez sigurne atribucije | reconciliation/manual API | aktivan/djelimičan |
| `Conflict` | detektovan problem i evidence JSON | watcher/periodični conflict/completion | aktivan |
| `AgentReport.verdict_audit_json` | istoriju korisničkih verdicta | ReportService | aktivan |
| `SessionTimelineService` | read model koji spaja više izvora | upit nad navedenim tabelama | postoji; izlaganje/GUI wiring nije potpuno |
| `/projects/{id}/timeline` | ad-hoc spajanje FileActivity + SessionEvent | controller | trenutno neispravno zbog `SessionEvent.project_id` reference |

Ovi sistemi djelimično dupliciraju vremensku liniju, ali ne isti podatak. Git snapshot/reconciliation čuva kopiju statusa i SHA radi poređenja, ne puni diff/history. Nema jedinstvenog modela nazvanog „Workflow Ledger“ niti jedinstvenog actor tipa `AGENT|USER|SYSTEM`.

# 11. Status / state logika

- **Project.status:** ručno postavljen CRUD vrijednost; nema enum validacije ni izračunavanja.
- **Task.status:** ručno preko PATCH, validiran `TaskStatus`; `done_at` postavlja `TaskService` pri DONE.
- **Plan.status:** DRAFT pri importu, ACTIVE preko eksplicitnog endpointa, prethodni ACTIVE postaje SUPERSEDED.
- **PlanItem.status:** centralna tranzicijska matrica u `PlanProgressService`; ručne API akcije i automatika completiona. IMPLEMENTED se može izvesti iz result commit razlike ili dirty fajlova; VERIFIED iz uspješnog `verify.py`; ACCEPTED je eksplicitna akcija. Dokaz nije uvijek pouzdano vezan u `PlanProgressEvent` polja.
- **PlanPhase.status:** izračunat iz item statusa pri progress upitu; zapis na ORM objektu se commitom može materijalizovati.
- **Session.status:** ACTIVE pri registraciji; completion izvodi status iz exit code/verification; heartbeat samo osvježava vrijeme. Enum i servis nisu potpuno usklađeni: servis dopušta FAILED/INTERRUPTED/TIMED_OUT koje `SessionStatus` enum nema.
- **Progress procenat:** GUI računa odnos `completed_items` (samo ACCEPTED) prema `total_items`; nije mjera implementiranosti.
- **Working:** plan item IN_PROGRESS ili aktivne sesije u `ProjectStateService`; heuristički operativni read model.
- **Blocked:** eksplicitni PlanItem status ili otvoreni konflikti/read model; razlog se ne postavlja automatski u svim transition putevima.
- **Review:** VERIFIED/IMPLEMENTED mapira se u NEEDS_REVIEW u read modelu; report verdict je zaseban.
- **Resume confidence:** `ProjectResumeService` heuristički izvodi LOW/MEDIUM/HIGH iz raspoloživih tragova i reconciliation stanja.

# 12. GUI — postojeće funkcionalnosti

| Naziv | Fajl/komponenta | Podaci/API | Stvarno stanje |
|---|---|---|---|
| Pregled / Gdje si stao | `overview_skeleton.MainWindow`, `ResumeHeroView`, `CurrentPhaseView`, `StatusSummaryBar`, `AttentionPanel` | projects, plan-progress, resume, active sessions, timeline | live wiring postoji; dio legacy widgeta sadrži hard-coded mock tekst, ali ga composition root zamjenjuje novim viewovima |
| Projekti | `pages.ProjectsPage` | `GET /projects` | lista se renderuje; kompletan create/open workflow nije povezan |
| Plan | `PlanProgressView` | plan-progress, import-plan, plan-item | prikaz/import/detail rade djelimično; import response shape se šalje rendereru koji očekuje drugi oblik |
| Sesije | `SessionsView` | `GET /sessions/active`; GUI POST `/sessions` za tracking | lista/tracking djelimično povezani |
| Zadaci | `pages.TasksPage` | nema GuiApiClient task metoda/wiringa | statička tabela/prazno stanje, nije funkcionalan CRUD ekran |
| Agenti | `pages.AgentsPage` | `GET /agents/scan`, POST `/sessions` | process scan i „Prati“ signal povezani; nije execution ekran |
| Radna stabla | `WorktreesView` | GET worktrees, prepare integration, cleanup | djelimično funkcionalno; create/verify nisu GUI wired |
| Konflikti | `pages.ConflictsPage` | nema jasno povezanog refresh poziva | uglavnom prezentaciona/djelimična |
| Izvještaji | `pages.ReportsPage` | nema GuiApiClient reports metoda | statička/djelimična |
| Postavke | `pages.SettingsPage` | nema persistence/settings API | placeholder/prezentacija |
| Recent changes/activity | `RecentActivityWidget` | project timeline | poziv postoji, endpoint trenutno ima model mismatch |
| Review/Evidence/History | nema zasebne pune stranice | evidence endpoint postoji samo backend | nije kompletno GUI povezano |

View → Controller → Service granica uglavnom postoji za overview, ali `FlowOsGui` direktno koristi privatne `GuiApiClient._post` i `_nam` detalje za shutdown/import/session tracking; to slabi deklarisanu troslojnu granicu.

# 13. API / backend

| METHOD | PATH | HANDLER | Svrha / potrošač |
|---|---|---|---|
| GET | `/health`, `/version`, `/runtime` | `system.py` | GUI/CLI/service status; `/health` je dvaput deklarisan u istom routeru |
| GET | `/agents/scan` | `scan_agents` | GUI Agents |
| POST/GET | `/shutdown*` | shutdown handleri | GUI close workflow |
| GET/POST | `/projects` | project CRUD | GUI/CLI |
| GET/PATCH/DELETE | `/projects/{id}` | project CRUD | CLI/API; GUI djelimično |
| GET | `/projects/{id}/timeline` | `get_project_timeline` | GUI recent activity; trenutno neispravan SessionEvent filter |
| GET | `/projects/{id}/state` | `get_project_state` | novi read model; GUI ga trenutno ne koristi i model fields su neusklađeni |
| GET/POST/PATCH/DELETE | `/tasks...` | task CRUD | CLI; GUI ne koristi |
| POST/GET | `/sessions`, `/sessions/active`, `/sessions/{id}` | session CRUD/list | GUI/CLI |
| POST | `/sessions/{id}/end`, `/heartbeat` | session lifecycle | CLI/background |
| GET | `/projects/{id}/plan-progress` | plan progress | GUI/CLI |
| GET/PATCH/POST | `/plan-items/...` | item/criteria/events/actions | backend API; GUI koristi samo detail |
| POST | `/projects/{id}/import-plan` | import | GUI |
| POST | `/plans/{id}/activate` | activate | API/test; GUI nije wired |
| GET/POST | `/projects/{id}/resume...` | resume/reconciliation/external activity | GUI resume koristi GET |
| GET | `/conflicts` | conflicts | GUI wiring nije dokazan |
| GET | `/reports` | reports | GUI ne koristi |
| GET | `/verification` | placeholder status | GUI ne koristi |
| CRUD/actions | `/worktrees...` | worktrees | GUI djelimično koristi |
| WS | `/ws` | `ws_endpoint` | GUI refresh na session/plan/resume/conflict/reconciliation evente |

Mrtvost se ne može potpuno dokazati samo statičkom pretragom, ali `/verification`, većina report/conflict ruta, task CRUD i više plan akcija nemaju GUI potrošača. Contract mismatchevi: import response, duplicate `/health`, timeline `SessionEvent.project_id`, project state nepostojeća polja, session plan validation nepostojeći `PlanItem.plan_id`.

# 14. Servisi

| Service/modul | Odgovornost | Poziva / pozvan od | Stanje |
|---|---|---|---|
| `ProjectService` | Project CRUD | ORM; project routes | AKTIVAN |
| `TaskService` | Task CRUD/status | ORM; task routes/CLI | AKTIVAN, GUI nepovezan |
| `SessionService` | session lifecycle/heartbeat | ORM, WS; session routes | AKTIVAN sa plan-item bugom |
| `SessionCompletionService` | Git, verify, report, conflict, auto progress | background nakon end | AKTIVAN |
| `PlanImportService` | deterministički Markdown import | ORM/progress; progress service | AKTIVAN |
| `PlanProgressService` | statusi/dependencies/progress queries | API, completion, reports | AKTIVAN |
| `ActivityService` | watcher event persistence/attribution | watcher callback | AKTIVAN |
| `AttributionService` | confidence atribucija putanje | activity | AKTIVAN |
| `ConflictDetectionService` | write/stale/branch/no-commit konflikti | watcher/periodic/completion | AKTIVAN |
| `GitStateReader` | read-only Git state | completion/conflict/reconciliation | AKTIVAN |
| `WatcherPipeline` | filesystem observer/debounce | lifespan | AKTIVAN |
| `ReconciliationService` | poređenje Git snapshotova | periodic loop | AKTIVAN/DJELIMIČNO POVEZAN |
| `ProjectResumeService` | materijalizovani resume | API/progress/reconciliation | AKTIVAN |
| `ProjectStateService` | jedinstveni read model | novi state endpoint | NEISPRAVNO/NEPOTVRĐENO zbog field mismatcha |
| `ReportService` | DB report/verdict/Markdown export | completion/report routes | AKTIVAN; filesystem reports nepovezani |
| `EvidenceService` | objedinjeni evidence read model | plan-item evidence endpoint | NEISPRAVNO/NEPOTVRĐENO zbog nepostojećih relationshipa (`plan_item.plan.phase`) |
| `WorktreeService/Manager` | Git worktree lifecycle | worktree routes/GUI | AKTIVAN/DJELIMIČAN |
| `VerificationService` | pokreće repo `scripts/verify.py`, čuva artefakt | completion | AKTIVAN |
| `AgentProcessLauncher/adapters` | command/env/process launch | nema produkcijskog caller-a | IMPLEMENTIRANO ALI NEPOVEZANO |

# 15. Testovi

Framework je pytest, sa pytest-asyncio i pytest-qt dependencyjima. Folderi: `tests/unit`, `tests/integration`, `tests/architecture`, `tests/contract`, `tests/gui` (posljednja dva trenutno uglavnom package skeleton ili bez navedenih test fajlova).

Pokrenuto je samo `python -m pytest --collect-only -q`: **295 testova je uspješno kolektovano**, uz jednu Starlette/httpx deprecation warning; testovi nisu izvršeni.

Dobro pokriveno: persistence/WAL/FK, projects/tasks API, plan parser/progress/import, resume, sessions/completion, watcher/activity/attribution/conflicts, worktree izolacija, reports, Git reader, architecture boundaries i phase-3 E2E tok. Novi `EvidenceService` ima unit test fajl, ali collection ne dokazuje prolaz.

Očigledno slabo ili nepokriveno: stvarni PySide6 GUI interakcijski testovi, GUI/backend shape ugovori, agent process scanner, stvarno adapter launch wiring, YAML report parser (ne postoji), runtime migracije nad starom realnom bazom, project-state endpoint, timeline endpoint sa SessionEventom, package/exe smoke u ovom auditu.

# 16. Postojeća dokumentacija i planovi

| Dokument | Ocjena | Razlog |
|---|---|---|
| `README.md` | DJELIMIČNO USKLAĐEN | tačni stack/start ulazi, ali ne opisuje sve nove/djelimične GUI/read modele |
| `docs/FlowOS-novi-detaljan-plan-PySide6.md` | DJELIMIČNO USKLAĐEN | arhitektonske granice prate kod; mnoge kasnije faze nisu implementirane |
| `docs/FlowOS-kompletan-plan.md` | DJELIMIČNO USKLAĐEN | dobar referentni backend koncept, nije snapshot implementacije |
| v2 plan-progress / v3 project-resume planovi | DJELIMIČNO USKLAĐEN | modeli uglavnom postoje, ali contract/wiring i artifact report tok nisu završeni |
| `docs/phase3-backlog.md`, `phase3-migration-history.md` | NE MOŽE SE POTPUNO UTVRDITI | operativni istorijski dokumenti; dio stanja je pretečen novijim commitovanim kodom |
| `docs/FlowOS-Faza3-novi-bundle-nezavisni-pregled.md` | DJELIMIČNO USKLAĐEN | opisuje stvarne phase-3 koncepte, ali nije trenutni inventar |
| `CLAUDE.md` | DJELIMIČNO USKLAĐEN | pravila su ciljna; „Evergreen N/A — nema koda“ je zastarjelo |
| `arhitektura/ADR-*` | DJELIMIČNO USKLAĐEN | dokumenti su sada commitovani, ali više fajlova koristi isti ADR-005 broj i Git commit sam ne razrješava koji je kanonski/usvojen |
| postojeći `agent_reports/*.md` | istorijski dokazi, ne trenutni autoritet | korisni za porijeklo, ali trenutni kod/testovi imaju prednost |

# 17. Duplikati i paralelni sistemi

1. `Task` i `PlanItem` predstavljaju preklapajuće jedinice rada; Task opciono pokazuje na PlanItem, session može direktno pokazivati na oba.
2. Session ima direktni `task_id` i `plan_item_id`, bez istorijske binding tabele.
3. Event/history je razdvojen na SessionEvent, FileActivity, PlanProgressEvent, reconciliation event, ExternalActivity i report verdict audit; timeline ih ad-hoc spaja.
4. Repository Markdown `agent_reports/` i DB `AgentReport` nisu sinhronizovani.
5. `PlanMarkdownParser.parse()` i service `_parse_with_phases()` su dva slična parse puta sa različitim ponašanjem za nejasne sekcije.
6. Pydantic plan import contract postoji, ali ruta koristi raw dict i svoj stvarni shape.
7. GUI sadrži legacy mock widgete i nove live viewove; composition root ih zamjenjuje, ali oba sistema ostaju u istom fajlu.
8. Runtime migriranje (`create_all` + ALTER) i Alembic migracije paralelno postoje.
9. Dvije identične `/health` rute su deklarisane u `system.py`.
10. Agent registry je u DeepSeek modulu i ne uključuje implementirani Codex; package `__init__` samo dokumentuje drugi redoslijed.

# 18. Tehnički dug relevantan za migraciju

- Centralni `PlanItem` spaja plan specifikaciju, izvršni workflow, ownership i acceptance; migracija mora sačuvati podatke bez automatskog poistovjećivanja sa novim `ImplementationTask`.
- Direktni session→task/item FK ne može predstaviti promjenu taska tokom sesije.
- Nema kanonskog workflow event modela ni actor tipa; novi ledger ne treba slijepo progutati raw filesystem događaje.
- DB i filesystem reporti imaju različite identitete/formate; YAML nije podržan.
- ORM relationshipi i novi read modeli su neusklađeni (`PlanItem.plan_id`, `plan_item.plan.phase`, `SessionEvent.project_id`, worktree/workspace fieldovi).
- GUI i backend imaju nekoliko shape mismatcha, posebno import plana.
- Dynamic watcher lifecycle nije vezan za create/update/delete projekta.
- Alembic i runtime schema creation imaju dvije ownership putanje.
- Adapteri izgledaju spremno po nazivima, ali većina nije wired; migracija ih ne smije tretirati kao stvarno dostupne execution providere.
- Statusi sessiona i enum nisu jedinstveni; „done/verified/accepted“ postoje u više domena i nisu isto značenje.

# 19. Migration inventory

| Postojeći dio | Fajl/model/service | Ocjena | Razlog |
|---|---|---|---|
| Project registry | `Project`, `ProjectService` | PRILAGODITI | dobra osnova; dodati dokazanu repo registraciju/metadata bez rušenja ID-jeva |
| Git reader | `GitStateReader` | ZADRŽATI | deterministički read-only adapter ka Git autoritetu |
| Watcher/activity | `WatcherPipeline`, `FileActivity` | PRILAGODITI | korisno za observability; raw događaji nisu workflow ledger |
| AttributionService | attribution modul | PRILAGODITI | confidence model vrijedi; actor tipovi i user fallback treba uskladiti |
| Conflict detection | `ConflictDetectionService`, `Conflict` | ZADRŽATI | stvarna observer funkcija zasnovana na signalima |
| Worktree lifecycle | Worktree servisi/model | PRILAGODITI | zadržati izolaciju, razdvojiti od budućeg ExecutionWorkspace koncepta |
| Task | `models.Task` | PREIMENOVATI | značenje treba eksplicitno mapirati na ImplementationTask ili legacy task prije promjene |
| PlanItem | plan modeli | PRILAGODITI | sačuvati import/progress podatke, razdvojiti specifikaciju od izvršnog taska/odluke |
| DecisionItem | ne postoji | DODATI | novi usvojeni princip eksplicitno zahtijeva odvojenu jedinicu odluke |
| ImplementationTask | ne postoji kao eksplicitan tip | DODATI | postojeći Task/PlanItem nisu jasno taj koncept |
| SessionTaskBinding | ne postoji | DODATI | potreban za session→više taskova kroz vrijeme |
| AgentSession | core ORM | PRILAGODITI | zadržati identitet/trag, ukloniti pretpostavku jedne trajne task veze |
| SessionEvent | core ORM | PRILAGODITI | dobar append-only temelj, ali nije kanonski workflow ledger |
| Workflow Ledger | ne postoji | DODATI | treba čuvati samo usvojene workflow događaje, ne Git/raw watcher duplikate |
| PlanProgressEvent | plan model | ISTRAŽITI PRIJE ODLUKE | dio događaja može mapirati u ledger, dio je interni status audit |
| Reconciliation models | resume modeli | PRILAGODITI | zadržati external-change dokaz, minimizirati dupliciranje Git-a |
| ProjectResumeState | resume model/service | ZADRŽATI | vrijedan materijalizovani read model; regenerisati iz novih izvora |
| EvidenceBundle | `evidence.py` | PRILAGODITI | korisna ideja, trenutna implementacija je neispravna |
| DB AgentReport | report model/service | PRILAGODITI | zadržati verdict/audit; uskladiti sa YAML metadata i filesystem artefaktom |
| Filesystem report convention | `agent_reports/` | PRILAGODITI | dodati parser/watch/import, zadržati human-readable Markdown |
| YAML front matter parser | ne postoji | DODATI | potreban prema usvojenom report formatu |
| Agent adapters | infrastructure adapters | ISTRAŽITI PRIJE ODLUKE | razlikovati observer/provider od neaktivnog execution prototipa |
| DeepSeek inline execution | `deepseek.py` | UKLONITI | protivan observer-first smjeru i zabranjuje sigurno arbitrary inline izvršavanje u Core putu |
| Duplicate parse path | `parse()` / `_parse_with_phases()` | UKLONITI | jedan kanonski parser treba sačuvati sva upozorenja |
| Duplicate `/health` | `system.py` | UKLONITI | dokazani duplikat rute |
| Runtime `create_all` migracije | `service/app.py` | ISTRAŽITI PRIJE ODLUKE | packaging razlog postoji, ali schema ownership je razdvojen |
| GUI View/Controller/Client | `src/flowos/gui` | PRILAGODITI | zadržati Qt Widgets, očistiti private-client pozive i shape drift |
| Managed Execution modeli | ne postoje | ISTRAŽITI PRIJE ODLUKE | princip ih definiše za budućnost, ali ne zahtijeva trenutnu implementaciju |

# 20. Poređenje sa novim principima

- **Observer, ne orchestrator:** watcher, Git reader, sessions, reconciliation i resume već dobro podržavaju observer ulogu. Neaktivni launcher/DeepSeek kod i dokumentovani managed modovi nisu dokaz da je FlowOS sada orchestrator.
- **Git autoritet:** postojeći kod uglavnom čita Git i čuva snapshot/reference. Ne čuva puni diff/history, što treba zadržati.
- **Workflow Ledger:** ne postoji. Postojeći događaji su siroviji i domenski razdvojeni; samo odabrani događaji treba da migriraju.
- **Attribution actor:** sada se čuva attribution string/confidence, ali nema jedinstven `AGENT|USER|SYSTEM`. Unattributed nije automatski USER.
- **Session→Task:** trenutni direktni FK je nedovoljan; istorijska binding tabela je očigledno nedostajuća komponenta.
- **DecisionItem/ImplementationTask:** danas ne postoje kao odvojeni koncepti.
- **Managed execution:** Worktree i AgentSession nisu isto što i `ExecutionWorkspace`, `AgentRun`, `AgentContext`; trenutni kod ih ne treba automatski preimenovati.
- **Agent reports:** DB verdict granica je korisna, ali repository YAML metadata tok ne postoji.

# 21. Šta nisam mogao pouzdano utvrditi

- Koji dijelovi objedinjeni u `25ae36f` predstavljaju usvojenu ciljnu odluku, a koji su samo sačuvani istraživački ili pomoćni artefakti.
- Da li PyInstaller executable-i iz `dist/` odgovaraju trenutnom source treeju; build nije pokrenut.
- Da li svih 295 testova prolazi; urađena je samo kolekcija.
- Stvarno stanje korisničke lokalne SQLite baze i koja migracijska grana je nad njom primijenjena; baza nije otvarana.
- Koji od tri dokumenta sa oznakom ADR-005 je kanonski/usvojen; sva tri su sada commitovana.
- Da li vanjski CLI alati stvarno prihvataju sve argumente koje adapteri generišu; nisu pokretani.
- Da li GUI render radi bez greške na HEAD-u `25ae36f`; nije pokrenut niti vizuelno testiran.
- Da li će route/field greške biti popravljene u narednom radu; na pregledanom HEAD-u ostaju dokumentovane, a standardna verifikacija nije prošla.

# 22. Preporučeni prvi migration korak

## Preporučeni prvi migration korak

Uvesti minimalni append-only `WorkflowEvent` model i read-only mapiranje samo za osam usvojenih workflow događaja, sa `actor_type` (`AGENT|USER|SYSTEM`) i referencama na postojeće Project/Session/Task/PlanItem ID-jeve, bez brisanja ili prepisivanja ijednog postojećeg event sistema. To je najmanje remetilački korak jer postojeći watcher, Git, plan progress, report i resume tokovi mogu nastaviti raditi, a novi ledger se može puniti postepeno samo na mjestima gdje već postoji dokazani workflow događaj.
