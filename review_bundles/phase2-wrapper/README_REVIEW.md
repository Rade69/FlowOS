# Review bundle — FlowOS Faza 2 (Wrapper, Watcher, Sesije)

## Zadatak
FLOW-201 do FLOW-208 — Kompletna faza 2: CLI, sesije, adapteri, watcher, Git polling, atribucija, GUI sesije, overview integracija

## Status
OK

## Scope
- CLI troslojni skeleton (FLOW-201)
- Session API + CLI komande (FLOW-202)
- Claude Code adapter (FLOW-203)
- Watcher pipeline (FLOW-204)
- Git polling (FLOW-205)
- AttributionService (FLOW-206)
- Aktivne sesije GUI (FLOW-207)
- Overview minimalni ekran (FLOW-208)

## Šta je urađeno
- 8 FLOW zadataka implementirano u celosti
- 192 testa, svi prolaze (dodato 26 novih testova za adapter, git, atribuciju, prevode)
- CLI sa 10+ komandi (health, project CRUD, task CRUD, plan progress, resume, session start/end/list)
- SessionService + API (5 endpointa)
- Claude Code adapter (capability model, command/env, AgentProcessLauncher)
- Watcher pipeline (watchdog, debounce 500ms, ignore lista)
- GitPoller (git status/rev-parse/branch, detect_changes)
- AttributionService (WORKTREE/SOLE_ACTIVE/UNATTRIBUTED/USER)
- GUI aktivne sesije integrisane sa backend-om
- OverviewController proširen (sessions, plan, resume mapping)

## Šta nije urađeno
- Claude Code adapter — nije testiran sa stvarnim Claude Code CLI (samo unit testovi)
- Watcher — nije integrisan sa WebSocket emitovanjem (faza 3)
- Git polling — nije povezan sa ProjectWorkspaceState (faza 3)
- GUI — mock podaci u skeleton-u, live mod radi ali nije full-featured

## Usklađenost sa planom
- Svi FLOW zadaci faze 2 implementirani
- Arhitektura View → Controller → Services poštovana
- Architecture testovi: 7/7 prolaze
- Nema rada van plana

## Arhitektonski slojevi
- View: overview_skeleton.py (preveden, popravljen desni panel)
- Controller: OverviewController (proširen sa sessions)
- GUI Services: GuiApiClient (proširen sa sessions)
- Backend Services: SessionService (nov), AttributionService (nov)
- Infrastructure: GitPoller (nov), WatcherPipeline (nov), ClaudeCodeAdapter (nov)
- CLI: Typer app sa 10+ komandi, CliApiClient (httpx)
- Prekršene granice: NEMA

## Verifikacija
- Ruff: prolazi (per-file-ignores za CLI B904)
- mypy shared: 0 errors
- Pytest: 192/192
- Architecture: 7/7
- Alembic: 3 migracije

## Poznati rizici
- Watcher nije testiran sa stvarnim fajl sistemom (samo unit testovi)
- GitPoller testovi zahtevaju Git instaliran na sistemu
- Claude Code adapter — AgentProcessLauncher exit_code može biti -1 na Windows-u sa CREATE_NEW_PROCESS_GROUP
- Live GUI mod zahteva pokrenut backend servis

## Gdje je rad stao
Faza 2 kompletno implementirana. Spremno za Fazu 3 (Konflikti, timeline, verify, reporti).

## Sljedeći korak
FLOW-301 — ConflictDetectionService sa pravilima konflikata.

## Prije nastavka provjeriti
- Potvrditi da li želimo prvo integrisati watcher sa WebSocket-om
- Testirati Claude Code adapter sa stvarnim CLI alatom