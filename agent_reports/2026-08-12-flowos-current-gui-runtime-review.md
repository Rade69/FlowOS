---
flowos_report_version: 1
agent: codex
model: gpt-5
session_id: unknown
report_id: 3c6bb9db-97a0-49a0-a020-d0a30de7f937
report_type: analysis
tasks:
  - unassigned
commits: []
created_at: 2026-08-12T17:49:46+02:00
---

# FlowOS current GUI runtime review

OVO JE FLOWOS GUI DANAS.

## Baseline

Provjera je urađena read-only nad trenutnim `main`.

```text
git status --short: clean prije kreiranja ovog reporta i screenshot foldera
git rev-parse HEAD: 33d2f32415e3866d6b55186416b840ad10c9162a
git log -1 --oneline: 33d2f32 feat: add workflow ledger task decisions
```

Nije mijenjan funkcionalni kod. Nije pravljen commit. Nije pravljen push.

## Podržani launch put

Iz `pyproject.toml`:

```text
flowos-gui = flowos.gui.app:main
flowos-service = flowos.service.app:main
```

Iz `src/flowos/gui/app.py`:

```text
flowos-gui          -> MOCK režim, bez backend-a
flowos-gui --live   -> LIVE režim, povezuje se na backend
```

README navodi `python scripts/run_gui.py` i `python scripts/run_service.py`, ali ti fajlovi trenutno sadrže samo docstring i nisu stvarni runtime wrapperi.

## Runtime rezultat

GUI se može konstruisati i prikazati. Navigacija između glavnih stranica radi.

Live backend tokom ove provjere nije bio upotrebljiv:

- runtime descriptor je pokazivao `127.0.0.1:9100`, ali port je odbijao konekciju;
- proces pokrenut kao servisna proba nije slušao TCP port;
- zadnji servisni log pokazuje `sqlalchemy.exc.TimeoutError: QueuePool limit of size 1 overflow 0 reached` tokom startup AgentReport ingestion-a;
- live GUI error path dodatno baca `TypeError` u `GuiApiClient._handle_response`, jer na grešci pokušava pozvati Qt signal kao funkciju.

Zato je ukupno stanje:

```text
GUI PARTIALLY RUN — BLOCKERS DOCUMENTED
```

## Screenshot artefakti

Screenshotovi su stvarni render postojeće PySide6 aplikacije, snimljeni iz trenutne grane:

| Screenshot | Ekran | Mode | Stanje |
|---|---|---|---|
| `agent_reports/gui_runtime_2026-08-12/01_pregled_live.png` | Pregled | LIVE | GUI otvoren, backend ne daje podatke |
| `agent_reports/gui_runtime_2026-08-12/02_plan_live.png` | Plan | LIVE | prazna plan tabela |
| `agent_reports/gui_runtime_2026-08-12/03_zadaci_live.png` | Zadaci | LIVE | prazna task tabela |
| `agent_reports/gui_runtime_2026-08-12/04_sesije_live.png` | Sesije | LIVE | nema aktivnih sesija |
| `agent_reports/gui_runtime_2026-08-12/05_agenti_live.png` | Agenti | LIVE | scan dugme postoji, backend scan ne uspijeva |
| `agent_reports/gui_runtime_2026-08-12/06_radna_stabla_live.png` | Radna stabla | LIVE | prazna worktree tabela |
| `agent_reports/gui_runtime_2026-08-12/07_konflikti_live.png` | Konflikti | LIVE | prazna tabela, nije wire-upovana |
| `agent_reports/gui_runtime_2026-08-12/08_izvjestaji_live.png` | Izvještaji | LIVE | prazna tabela, nije wire-upovana |
| `agent_reports/gui_runtime_2026-08-12/09_projekti_live.png` | Projekti | LIVE | nema projekata prikazanih |
| `agent_reports/gui_runtime_2026-08-12/10_postavke_live.png` | Postavke | LIVE | statički settings tekst |
| `agent_reports/gui_runtime_2026-08-12/11_pregled_mock_default.png` | Pregled | MOCK | default režim bez backend-a |

## Pregled ekran

Izvor: MJEŠOVITO.

Šta se vidi:

- TopBar: statički `FlowOS`, refresh dugme.
- Sidebar: navigacija, aktivni projekat, brze akcije.
- Aktivni projekat: `Nema projekta`.
- `Gdje si stao`: prazno stanje, tekst da nema završene sesije.
- Status summary: `0 Nije započeto`.
- Current Phase / Plan Progress: `Nema podataka o planu`.
- Aktivne sesije: tabela sa praznim stanjem.
- Recent activity: `Nema nedavne aktivnosti`.
- Attention panel: `Nema otvorenih blokatora`.
- PlanItem details: `Izaberite stavku plana`.
- Reconciliation panel: nije prikazan dok resume ne vrati workspace state.
- Footer/service status: tokom live pokušaja ostaje `Servis: povezuje se...` ili prelazi u `Connection refused`.

Šta stvarno radi:

- sidebar navigacija;
- refresh signal postoji;
- `Nastavi rad` iz `ResumeHeroView` prebacuje na Plan, ali se prikazuje samo kad resume ima istoriju;
- plan item detail load postoji samo ako `CurrentPhaseView.item_selected` emituje item id.

Šta nije povezano ili nije dokazano:

- nema live projekta zbog backend blockera;
- nema live plan progress podataka;
- nema live resume podataka;
- nema live active sessions podataka;
- nema live recent activity podataka;
- nema Workflow Ledger prikaza.

Relevantni fajlovi:

- `src/flowos/gui/app.py`
- `src/flowos/gui/composition_root.py`
- `src/flowos/gui/controllers/overview.py`
- `src/flowos/gui/services/client.py`
- `src/flowos/gui/views/overview_skeleton.py`
- `src/flowos/gui/views/project_resume.py`
- `src/flowos/gui/views/plan_progress.py`
- `src/flowos/gui/views/sessions.py`

## Ekrani

### Plan

Izvor: LIVE BACKEND kad backend radi, trenutno prazno zbog blockera.

`PlanProgressView` ima `render(data)` i prikazuje plan title, faze, stavke, kriterijume i status count. `composition_root.py` ga puni preko `/projects/{project_id}/plan-progress`, ali projekat nije učitan jer backend nije odgovarao.

Interaktivno:

- dugme `Uvezi plan` otvara file dialog i šalje `/projects/{project_id}/import-plan`, samo ako postoji aktivni projekat.

### Zadaci

Izvor: PLACEHOLDER/PARTIAL.

`TasksPage` postoji kao tabela sa kolonama `Naziv`, `Status`, `Prioritet`, `Plan stavka`, ali u `GuiApiClient` nema `get_tasks`, a `composition_root.py` ne povezuje ovu stranicu sa `/tasks`.

Ovo znači da GUI danas ne prikazuje stvarni Task ekran, iako backend ima `/tasks` rute.

### Sesije

Izvor: LIVE BACKEND kad backend radi, trenutno prazno zbog blockera.

`SessionsView` prikazuje samo aktivne sesije iz `/sessions/active?project_id=...`. Kolone su agent, plan stavka, radno stablo, trajanje, posljednja aktivnost i status.

Ne prikazuje:

- istoriju završenih sesija;
- model;
- execution mode;
- SessionTaskBinding istoriju;
- report povezan sa sesijom;
- detaljnu razliku agent/session/task/worktree.

### Agenti

Izvor: LIVE BACKEND kad backend radi, trenutno djelimično.

`AgentsPage` ima dugme `Skeniraj procese`, povezano na `/agents/scan`. Dugme `Prati` može kreirati `EXTERNAL_TRACKED` sesiju preko `/sessions`, ali samo ako postoji aktivni projekat i repo path.

Tokom ove provjere scan nije mogao raditi jer backend nije odgovarao.

### Radna stabla

Izvor: LIVE BACKEND kad backend radi, trenutno prazno zbog blockera.

`WorktreesView` se puni preko `/worktrees?project_id=...`. UI ima akcije `Pregledaj izmjene` i `Cleanup`, mapirane na integration prepare i cleanup API.

Ne prikazuje nezavisno Git stanje bez aktivnog projekta.

### Konflikti

Izvor: PLACEHOLDER/PARTIAL.

`ConflictsPage` ima tabelu i `render(conflicts)`, ali `GuiApiClient` nema metodu za `/conflicts`, a `composition_root.py` ne poziva backend za konflikte. Backend ima `/conflicts`, ali GUI ga danas ne koristi.

### Izvještaji

Izvor: PLACEHOLDER/PARTIAL.

`ReportsPage` ima tabelu i `render(reports)`, ali GUI nema `get_reports` metodu i nema wire-up. Backend `/reports` trenutno vraća `{ "reports": [], "session_id": ... }`, ne stvarnu listu reportova.

Nema prikaza:

- Markdown report tijela;
- AgentReport v2 source identity;
- report binding linkova;
- user verdict UI;
- review report UI.

### Projekti

Izvor: LIVE BACKEND kad backend radi, trenutno prazno zbog blockera.

`ProjectsPage` prikazuje listu projekata koju dobije iz `/projects`. Nema vidljivog dugmeta za registraciju/kreiranje projekta na ovoj stranici, iako `GuiApiClient.create_project` postoji.

### Postavke

Izvor: HARDCODED.

Prikazuje:

- `FlowOS v0.1.0`;
- opis sistema;
- backend URL `http://127.0.0.1:9100`;
- DB path `%LOCALAPPDATA%/FlowOS/data/flowos.db`.

`SettingsPage.render()` je `pass`, nema stvarnu konfiguraciju.

## Workflow Ledger vs GUI

Backend kod ima Workflow Ledger događaje:

- `IMPLEMENTATION_COMPLETED`;
- `TEST_RESULT`;
- `REVIEW_COMPLETED`;
- `TASK_DECISION`.

GUI danas nema ekran koji prikazuje `WorkflowLedgerEvent`.

Ne postoji dokazani GUI prikaz za:

- Workflow Ledger timeline;
- `TASK_DECISION` UI za `ACCEPTED` / `NEEDS_WORK` / `REJECTED`;
- `TEST_RESULT` artifact UI;
- review completed UI;
- task history iz ledger-a.

`GuiApiClient` nema ledger metode. `composition_root.py` koristi `/projects/{project_id}/timeline`, ali to je `ProjectTimelineService`, ne direktan Workflow Ledger UI.

Zaključak: Workflow Ledger postoji u backend domenu, ali nije korisnički vidljiv kroz GUI.

## Project Resume / “Gdje si stao”

GUI put:

- `GuiApiClient.get_resume(project_id)` -> `/projects/{project_id}/resume`;
- `OverviewController._on_resume()` mapira polja u `ResumeHeroView`;
- `ResumeHeroView` prikazuje prazno stanje kad je status `NO_HISTORY`.

U trenutnom runtime testu prikazano je prazno stanje jer backend nije vratio projekat/resume.

Bitno ograničenje: dugme `Otvori izvještaj` postoji u starom `ProjectResumeWidget` mock/demonstracionom widgetu, ali stvarni `ResumeHeroView` u composition root-u prikazuje samo `Nastavi rad`. `report_requested` signal postoji, ali nije wire-upovan.

## Plan / Task granica

GUI trenutno jasno prikazuje plan progress kao `PlanItem` strukturu.

Task ekran nije povezan na backend `/tasks`. Zbog toga GUI danas praktično koristi Plan kao glavnu radnu površinu, dok je `Zadaci` samo prazna tabela.

Ne postoji UI koji objašnjava ili prikazuje granicu:

- `DecisionItem` nije isto što i `ImplementationTask`;
- `Task` nije isto što i `PlanItem`;
- Task ↔ PlanItem veza nije vidljiva;
- task history nije vidljiv.

Ovo je zastarjela GUI pretpostavka: korisnik bi iz aplikacije lako mogao zaključiti da je Plan stavka operativni task, jer stvarni Task ekran nije funkcionalno prisutan.

## Sessions / Agents / Worktrees granica

GUI ima tri odvojena ekrana:

- `Sesije`;
- `Agenti`;
- `Radna stabla`.

Ali danas ne prikazuje dovoljno domain context-a da korisnik jasno vidi:

- jedna AgentSession može imati binding istoriju;
- agent proces nije isto što i session;
- session nije isto što i task;
- worktree nije isto što i session, iako može biti vezan;
- `EXTERNAL_TRACKED` ima ograničene capability-je.

`SessionsView` prikazuje aktivne sesije, ali ne istoriju, bindinge ni reportove. `AgentsPage` može pratiti proces samo uz aktivni projekat. `WorktreesView` radi samo kroz aktivni project id.

## Zastarjele GUI pretpostavke dokazane kodom

1. Default launch je MOCK, iako README sugeriše razvojni run script.
2. `scripts/run_gui.py` i `scripts/run_service.py` nisu stvarni runneri.
3. Live GUI pokušava automatski pokrenuti `flowos-service.exe`, ali nema robustan fallback kad descriptor/port nisu zdravi.
4. `GuiApiClient._handle_response` error path za Qt signal ima runtime bug.
5. `Zadaci` ekran postoji, ali nije wire-upovan na `/tasks`.
6. `Konflikti` ekran postoji, ali nije wire-upovan na `/conflicts`.
7. `Izvještaji` ekran postoji, ali nije wire-upovan na `/reports`.
8. Workflow Ledger je backend-only za korisnika GUI-ja.
9. Report verdict / TASK_DECISION authority nema GUI površinu.
10. Project registration UI nije vidljiv na `Projekti` ekranu.

## Final classification

| Functionality | Status | Evidence |
|---|---|---|
| Project selection | PARTIAL | prvi projekat se auto-bira u `_on_projects`, nema ručne selekcije u UI |
| Project registration | NOT IMPLEMENTED | client ima `create_project`, stranica nema formu/dugme |
| Plan | PARTIAL | `PlanProgressView` + `/plan-progress`, ali trenutno bez backend podataka |
| Tasks | PLACEHOLDER | `TasksPage.render([])`, nema API wire-up |
| Plan item details | PARTIAL | `/plan-items/{item_id}` postoji, ali selection u view-u nije praktično izložena u tabeli |
| Project Resume | PARTIAL | `/resume` put postoji, runtime prikazuje empty state |
| Sessions | PARTIAL | samo aktivne sesije, nema istorije/bindinga/reportova |
| Agent scan | PARTIAL | `/agents/scan` wire-up postoji, runtime backend nije odgovorio |
| Agent tracking | PARTIAL | `Prati` šalje `/sessions`, ali traži aktivni projekat/repo path |
| Reports | PLACEHOLDER | GUI nema `get_reports`, backend route vraća prazno |
| Workflow Ledger history | NOT IMPLEMENTED | nema GUI client metode ni ekran |
| TASK_DECISION UI | NOT IMPLEMENTED | nema ACCEPTED/NEEDS_WORK/REJECTED decision UI |
| TEST_RESULT UI | NOT IMPLEMENTED | nema artifact/test result prikaza |
| Review UI | NOT IMPLEMENTED | nema review report/REVIEW_COMPLETED prikaza |
| Recent activity | PARTIAL | koristi `/projects/{id}/timeline`, nije ledger UI |
| Worktrees | PARTIAL | list/prepare/cleanup wire-up postoji, zavisi od aktivnog projekta |
| Conflicts | PLACEHOLDER | backend route postoji, GUI nije povezan |
| Reconciliation | PARTIAL | prikaz postoji kroz resume `workspace_state`, nije samostalna stranica |
| Settings | HARDCODED | statički tekst, `render()` je `pass` |
| Service health | BROKEN | backend refused + GUI error path TypeError |
| Shutdown | PARTIAL | close dialog i `/system/shutdown/*` put postoje, nije end-to-end potvrđeno zbog service blocker-a |

## Verdict

GUI PARTIALLY RUN — BLOCKERS DOCUMENTED
