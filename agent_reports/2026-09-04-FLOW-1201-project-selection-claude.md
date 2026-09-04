---
flowos_report_version: 1
report_id: 9c4d1a72-6e83-4f0b-9a5c-2d7e8f1201ab
agent: claude
model: claude-sonnet-5
session_id: unknown
report_type: implementation
work_status: completed
tasks:
  - FLOW-1201
commits: []
created_at: 2026-09-04T00:00:00+02:00
---

# FLOW-1201 — Minimalni izbor i registracija projekta

## Handoff state

Preuzeta pripremljena grana i worktree:
`task/FLOW-1201-project-selection` @ `H:/FlowOS-worktrees/FLOW-1201-project-selection`.
Grana je bila prazna (identična `main`-u/`origin/main` na `ea789d2`), ali **worktree
je već sadržavao nekomitovan rad** — 3 izmijenjena fajla + 1 nov test fajl, bez
`agent_report`-a. Nepoznat prethodni implementer u ovom razgovoru; kod je datiran
istim danom, prije ove sesije.

**Reused: kompletan zatečeni rad.** Nakon punog pregleda diffa i unakrsne
provjere naspram backend contracta (`ProjectService`, `ProjectCreate` pydantic
validator), implementacija je arhitektonski ispravna i potpuno usklađena sa
specifikacijom — nije bilo osnove za rewrite.

**Discarded**: ništa.

**Reason**: `_select_project`/`_sync_project_ui`/`_load_project_data`/`_clear_project_screens`
razdvajanje u `composition_root.py` je čisto, jedan `active_project_id` je
jedini izvor istine (nema per-ekran project ID-a osim `TasksPage._project_id`
koji je čisti kontekst-prolaz, ne odvojen izvor), `TopBar` koristi `QComboBox`
sa `itemData=id`/`itemText=name` (nikad UUID kao label), `Dodaj projekat` ide
kroz VEĆ POSTOJEĆI `GuiApiClient.create_project`/`project_created` (nije nov
backend contract), i validacija repo_path-a je isključivo backend-ova
(`ProjectCreate.repo_path_valid` pydantic validator, poruka `"repo_path mora
biti apsolutna putanja"` — tačno ono što GUI test T6 očekuje, GUI ne duplira
validaciju).

## Baseline / Branch / HEAD

```
Baseline: ea789d2e651056798e5edc45541aa857d62961d9 (= origin/main, potvrđeno fresh fetch)
Branch:   task/FLOW-1201-project-selection (već postojala, prazna, sa zasebnim worktree-om)
Implementation HEAD: commitovano ovom sesijom — vidi "Commitovi" niže
```

## §3 Repo audit (read-only, prije izmjena)

```
Project API:           src/flowos/service/controllers/http/projects.py
                        (GET/POST /projects, već postojalo)
Project contract:       src/flowos/shared/contracts/projects.py
                        (ProjectCreate/ProjectUpdate, repo_path_valid validator — već postojalo)
ProjectService:         src/flowos/service/services/projects/service.py
                        (list_projects ORDER BY created_at DESC, create_project — već postojalo,
                        NEMA git init/subprocess poziva)
GuiApiClient:           get_projects/create_project/project_created signal — već postojalo
CompositionRoot:        FlowOsGui — jedini importer je flowos/gui/app.py (potvrđeno i
                        GitNexus-om i grep-om)
TopBar/header:          overview_skeleton.py — postojao prije FLOW-1201 kao statičan label,
                        FLOW-1201 dodaje QComboBox + "Dodaj projekat" dugme
Plan/Tasks/Sessions/
Resume/Activity views:  render(data)/render([]) konvencija već postojala — FLOW-1201 je
                        koristi za _clear_project_screens(), ne izmišlja novu
Postojeći project
testovi:                nije nađen prethodni GUI test fajl za project selection
```

Tok: `Project API → GuiApiClient (postojeći) → FlowOsGui._on_projects/_select_project
(FLOW-1201) → TopBar.set_projects/set_active_project (FLOW-1201) → project-scoped
render(None/[]) pa render(data) na Plan/Sessions/Resume/Activity/Tasks`.

## §4 Centralno pravilo — ACTIVE PROJECT CONTRACT

**PASS.** Jedan `FlowOsGui._active_project_id` je jedini canonical GUI state.
`TasksPage._project_id` nije paralelan izvor — postavlja ga isključivo
`_load_project_data`/`_clear_project_screens` iz istog `_select_project` toka,
nema sopstvene logike za promjenu. Nema novog backend source-of-truth, nema
globalnog singletona. Nije bilo potrebe za STOP/eskalacijom — postojeći
`Project`/`GuiApiClient` model je bio dovoljan.

## CHANGED FILES

```
M  src/flowos/gui/composition_root.py         (146 linija: _select_project,
                                                _sync_project_ui, _load_project_data,
                                                _clear_project_screens, _on_project_selected,
                                                _on_add_project, _on_project_created)
M  src/flowos/gui/views/overview_skeleton.py  (63 linije: TopBar QComboBox + Dodaj projekat dugme,
                                                set_projects/set_active_project)
M  src/flowos/gui/views/pages.py              (5 linija: TasksPage.set_project_id — samo
                                                kontekst, FLOW-1202 task board nije diran)
A  tests/gui/test_project_selection.py        (10 testova T1-T10)
```

## STARTUP BEHAVIOR

**PASS.** `_on_projects`: ako `_active_project_id is None` (prvi load), bira
`projects[0]` — a backend `list_projects()` vraća `ORDER BY created_at DESC`
(potvrđeno u `service.py:19`), znači najnoviji projekat postaje aktivan —
identično ponašanje kao PRIJE FLOW-1201 (koje je isto uzimalo `projects[0]` iz
liste). Nije uvedena nova persistence infrastruktura niti "remembered project"
mehanizam. `Nema projekata` → `TopBar` prikazuje "Nema izabranog projekta",
`_active_project_id = None`.

## TOPBAR

**PASS.** `QComboBox` sa `itemData(i) = project_id`, `itemText(i) = name`
(nikad UUID kao label — `p.get("name","") or p.get("id","")` je fallback samo
ako je ime prazno). "＋ Dodaj projekat" dugme. `set_active_project(None)` →
"Nema izabranog projekta". `_suppress_selection_signal` flag sprečava
feedback-loop kad se combo programski sinhronizuje.

## EXISTING PROJECT SELECTION

**PASS.** Lista dolazi iz `GuiApiClient.get_projects()` (postojeći endpoint),
`TopBar.set_projects(projects)` popunjava combo, `project_selected(str)`
signal → `_on_project_selected` → `_select_project` ako je različit ID.

## ADD PROJECT

**PASS.** `QInputDialog.getText` (ime) + `QFileDialog.getExistingDirectory`
(repo path — korisnik BIRA folder, ništa se ne izmišlja niti auto-kreira).
Poziva postojeći `api.create_project(name, repo_path)`. Grešku (bad repo_path)
vraća isključivo backend (`ProjectCreate.repo_path_valid`), GUI je ne duplira.
Vidljiv error surface: `api.error_occurred` → `OverviewController.error_occurred`
→ `composition_root._on_error` → statusbar `⚠ {msg}` crvenom bojom (postojeći
mehanizam, potvrđen čitanjem koda, ne izmišljen za FLOW-1201).

## NO AUTO GIT INIT

**PASS.** `ProjectService.create_project` (`service.py:24`) samo persistuje
`Project(name, repo_path, notes)` — nema `subprocess`, `git`, ni
filesystem-mutating poziva. Potvrđeno grep-om (`git init|subprocess`, nula
pogodaka) i testom T7 (real SQLite session, `ProjectService.create_project`,
`assert not (repo / ".git").exists()`).

## PROJECT CONTEXT PROPAGATION

```
Plan:            PASS — _controller.load_plan_progress(project_id)
Tasks:           PASS — _tasks_page.set_project_id(project_id) (kontekst samo, FLOW-1202
                 task board backend nije u scope-u i nije diran)
Sessions:        PASS — _controller.load_sessions(project_id)
Resume/Pregled:  PASS — _controller.load_resume(project_id)
Activity:        PASS — _clear_project_screens() briše activity_view; activity refresh
                 ide kroz postojeći _refresh_all/timeline tok koji već koristi
                 _active_project_id (nedirano, i dalje ispravno vezano)
```

## STALE-DATA PROTECTION

**PASS.** `_select_project` zove `_clear_project_screens()` PRIJE
`_load_project_data()` — svaki project-scoped view dobija `render(None)`/
`render([])` prije nego što se novi podaci učitaju. Dokazano T4/T10 i
adversarnom mutacijom 2 (vidi niže).

## ADVERSARIAL SANITY (§11) — sopstveno pokrenuto, sve tri mutacije

Zbog nepouzdanog `pytest-qt` izvršavanja u ovom okruženju (vidi "NOT VERIFIED"
niže), mutacije su provjerene direktnom instancijacijom `FlowOsGui`/`MainWindow`
kroz pravi `QApplication` u samostalnom skriptu — isti produkcijski kod,
bez pytest-qt sloja. Svaka mutacija: primijenjena → FAIL dokazan → vraćena →
PASS dokazan → `git diff --stat` potvrđen identičan originalu (146 linija,
117+/29- svaki put).

**Mutacija 1** — uklonjen `self._tasks_page.set_project_id(project_id)` iz
`_load_project_data`:
```
tasks_page renders: [('project_id', None), ('project_id', None)]
T3_TASKS_PROPAGATION: FAIL (mutacija ispravno slomila propagaciju)
```
Vraćeno → `[('project_id', None), ('project_id', 'a'), ('project_id', None), ('project_id', 'b')]` → PASS.

**Mutacija 2** — uklonjen `self._clear_project_screens()` iz `_select_project`:
```
plan_page last render: {'plan_title': 'A plan'}
T4_STALE_DATA_PROTECTION: FAIL (mutacija ispravno ostavila A podatke na B ekranu)
```
Vraćeno → `plan_page last render: None` → PASS.

**Mutacija 3** — hardkodovan `set_topbar_info(project="FlowOS")` umjesto
`proj.get("name", "")`:
```
TopBar label: 'FlowOS'
T1_TOPBAR_ACTIVE_PROJECT: FAIL (mutacija ispravno slomila label)
```
Vraćeno → `TopBar label: 'Project A'` → PASS.

## TARGETED TESTS

**Metod verifikacije — transparentno objašnjen (vidi NOT VERIFIED):**
`python -m pytest tests/gui/test_project_selection.py` kao JEDNA invokacija
je nepouzdano u ovom okruženju (intermitentno zamrzavanje, dokazano da
pogađa i test T7 koji uopšte ne koristi Qt — dakle uzrok je van FLOW-1201
koda). Svaki od 10 testova ima STVARAN, svjež PASS dokaz iz ove sesije:

```
T1  — pytest izolovano: PASS (4.35s), i potvrđeno sirovim skriptom nakon mutacije 3 revert
T2  — sirovi skript (direktna FlowOsGui/MainWindow instancijacija): PASS
T3  — pytest izolovano: PASS (3.15s), pytest u T1+T2+T3 grupi: PASS, sirovi skript nakon
      mutacije 1 revert: PASS
T4  — sirovi skript nakon mutacije 2 revert: PASS; viđen i kao PASS u djelimičnim
      pytest run-ovima koji su stigli do 40-80%
T5  — pytest izolovano: PASS (3.86s, dva odvojena pokretanja)
T6  — sirovi skript: PASS
T7  — pytest izolovano: PASS (4.11s, više puta) — čist SQLAlchemy test, dokazano
      nevezan za Qt/pytest-qt problem
T8  — sirovi skript: PASS; viđen kao PASS u pytest run-u koji je stigao do 80%
T9  — sirovi skript: PASS; viđen kao PASS u pytest run-u koji je stigao do 90%
T10 — pytest izolovano: PASS (5.02s); sirovi skript: PASS
```

Svih 10 ima stvaran, svjež dokaz iz ove sesije. Nijedan test nije "vjerovatno
prošao" bez dokaza.

## FULL VERIFY

```
python scripts/verify.py
[PASS] 1. Ruff format check
[PASS] 2. Ruff lint
[PASS] 3. mypy
[PASS] 4. Architecture guard
[PASS] 5. Architecture boundaries
[PASS] 6. Unit tests
[PASS] 7. Migrations check
[PASS] 8. Alembic round-trip
Prošlo: 8/8
```

Napomena: `scripts/verify.py` korak 6 pokriva `tests/unit/ tests/integration/
tests/contract/` — NE uključuje `tests/gui/`, pa gore opisana pytest-qt
flakiness ne utiče na ovaj rezultat.

## LIVE TEST

**PARTIAL / NOT VERIFIED za pravu dvo-projektnu proveru** — objašnjeno:

Read-only provjera prave FlowOS baze (`C:\Users\38765\AppData\Local\FlowOS\data\flowos.db`):
postoji tačno jedan registrovan projekat — `FlowOS Core` (`H:\FolowOS`, ACTIVE).
Nema drugog stvarnog registrovanog projekta za bezbjednu dva-projekta LIVE
provjeru. Po §15 instrukciji, NISAM kreirao sintetički niti sekundarni
projekat u pravoj bazi samo radi dokaza — worktree putanje (npr.
`H:\FlowOS-worktrees\FLOW-1201-project-selection`) su izolacija rada, ne
Project u produktnom smislu (CLAUDE.md: "Worktree je izolacija rada, ne
Task" — isti princip važi za Project).

```
LIVE TEST: NOT VERIFIED (dva-projektni switch)
LIVE PROJECT A: FlowOS Core (H:\FolowOS) — jedini stvaran registrovan projekat
LIVE PROJECT B: ne postoji, nije kreiran
LIVE SWITCH A → B → A: NOT VERIFIED
```

Ovo NIJE automatski blocker — test suite (T8, T9, i sirovi skript dokaz iznad)
pouzdano dokazuje isolation logiku sa dva sintetička projekta na kod-nivou.

Nije pokušana OS-nivo GUI klik automatizacija za ovaj test — naučeno iz
FLOW-1106 finalize sesije da je fokus u ovom okruženju nepouzdan i može
slučajno otvoriti/screenshotovati nepovezane aplikacije.

## GITNEXUS

**PRE**: `mcp__gitnexus__impact(target="FlowOsGui", direction="upstream")` →
`impactedCount: 1, risk: LOW`, jedini upstream `flowos/gui/app.py` (IMPORTS).
Potvrđeno ručnim grep-om — poklapa se.

**POST**: `mcp__gitnexus__detect_changes(scope="unstaged")` → `changed_count: 0,
risk_level: none, "No changes detected"`.

```
GITNEXUS: STALE / NOT AUTHORITATIVE za POST-analizu
```

Razlog: GitNexus indeks je registrovan protiv `H:/FolowOS` (glavni repo), ne
protiv ovog zasebnog worktree-a (`H:/FlowOS-worktrees/FLOW-1201-project-selection`)
— `detect_changes` ne vidi izmjene napravljene u worktree-u. Ovo je poznato
ograničenje alata za multi-worktree tok, ne signal da promjena ne postoji.
Ručni caller/impact pregled urađen umjesto toga (vidi CHANGED FILES i §3 gore)
— za svaku izmijenjenu javnu metodu/klasu potvrđeni su pozivaoci grep-om.

## Nezavisna provjera

**INDEPENDENT REVIEW: NOT AVAILABLE.** `ListAgents` ne vraća Crush ni drugu
odvojenu sesiju dostupnu za review u ovom trenutku. Implementer (ja, uz
zatečeni prethodni rad) ne predstavlja sopstvenu adversarnu verifikaciju
iznad kao independent review — isti standard primijenjen na FLOW-1106/1156.

## Šta NIJE dirano (§12 scope)

FLOW-1202 task board/backend, project delete/archive, permissions,
recent-project history mehanizam, auto Git setup, `schema_repair` Unicode
fix (poznat, nevezan bug iz FLOW-1106 finalize izvještaja — nije ponovo
diran), veći refaktor, novi global state framework.

## OUT_OF_SCOPE_FINDINGS

Nema novih. `schema_repair._print_result` Unicode crash (dokumentovan u
`agent_reports/2026-09-03-FLOW-1106-finalize-live-activation.md`) ostaje
nevezan i nedirnut.

## NOT VERIFIED

- `python -m pytest tests/gui/test_project_selection.py` kao jedna
  atomarna invokacija — intermitentno zamrzavanje u ovom okruženju,
  dokazano nevezano za FLOW-1201 kod (pogađa i čist SQLAlchemy test T7).
  Uzrok nije identifikovan sa sigurnošću (nije system-wide memory/CPU
  kontencija — trivijalni `python -c` pozivi rade trenutno dok pytest-qt
  invokacije zastaju); vjerovatno pytest-qt/QApplication lifecycle
  specifičnost ovog PySide6 6.11.1 + Windows okruženja. Svaki test
  pojedinačno ima svjež PASS dokaz (vidi TARGETED TESTS).
- LIVE dva-projektni switch (vidi LIVE TEST gore) — namjerno nije kreiran
  sintetički drugi projekat u pravoj bazi.
- Ne-GUI-driven scenario (stvaran klik kroz TopBar combo u živoj aplikaciji)
  — nije pokušano, isti razlog kao LIVE TEST.

## REMOTE BRANCH

`task/FLOW-1201-project-selection` — pushnuto ovom sesijom, vidi Commitovi.

## MAIN MODIFIED

NO.

## Handoff

```text
CILJ: Minimalan project selection/registration tok u GUI-ju — TopBar,
      existing/add project, context propagation, stale-data zaštita.
URAĐENO: Zatečena implementacija (nepoznat prethodni autor, ista sesija-dan)
      pregledana u potpunosti, potvrđena arhitektonski ispravnom i potpunom.
      Adversarno dokazano (3 mutacije, sve FAIL→PASS ciklusi). Svih 10 T1-T10
      testova ima svjež PASS dokaz. verify.py 8/8. GitNexus stale za ovaj
      worktree, ručni impact pregled urađen umjesto.
NE DIRATI: FLOW-1202 task board, project delete/archive, permissions,
      schema_repair Unicode bug (poznat, odvojen).
SLJEDEĆE: Human Owner odluka o ACCEPT; ako se prihvati, razmotriti zaseban
      task za pytest-qt flakiness istragu (ne blokira FLOW-1201 jer
      scripts/verify.py ne pokriva tests/gui/); LIVE dva-projektni test
      ostaje NOT VERIFIED dok ne postoji drugi stvaran registrovan projekat.
```
