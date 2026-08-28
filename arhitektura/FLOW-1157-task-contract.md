---
task_id: FLOW-1157
risk: MEDIUM
implementer: Codex
reviewers: [Claude]
status: "OPEN — task contract napisan prije koda"
created_at: 2026-08-28
---

# FLOW-1157 — Izvlačenje poslovne logike iz `composition_root.py` u Controllere

## 1. Kontekst

Arhitektura projekta je `View → Controller → Services` (granica 4 u planu
v4.3, provođena kroz `scripts/guard_architecture.py` i
`tests/architecture/test_boundaries.py`).

GUI ima samo jedan stvarni Controller — `gui/controllers/overview.py`, čiji
docstring kaže „Ne pristupa bazi/Git-u/subprocessu" i koji to i drži.

`gui/composition_root.py` (617 linija) je istovremeno wiring/DI root i de
facto neslužbeni Controller. Osamnaest handlera živi u njemu. Četrnaest su
čisto mapiranje DTO → view i **ne diraju se u ovom tasku**. Četiri nose
poslovnu logiku i konstrukciju zahtjeva, i predmet su ovog taska.

Zašto sada, a ne kasnije:

- Sljedeći task (FLOW-1156) proširuje architecture guard da pokrije
  `flowos.gui.composition_root`. Guard ne može proći dok ovi prekršaji stoje,
  a allowlist da bi bio zelen je gaming senzora — po blueprintu §17 ozbiljniji
  problem od samog prekršaja. Zato 1157 ide **prije** 1156.
- Svaka nova View akcija trenutno ima presedan da dobije ad-hoc handler ovdje.
  Naredna faza dodaje najmanje četiri ekrana.

Dokazano stanje na commitu `b83f197`:

```text
composition_root.py:226–239   _on_import_plan — čita fajl sa diska,
                              gradi request dict, zove privatnu _api._post
composition_root.py:246–267   _track_agent — gradi session payload,
                              zove privatnu _api._post
composition_root.py:158–191   _on_shutdown_requested — sam gradi QNetworkRequest,
                              zove privatne _api._apply_auth_header i _api._nam,
                              parsira JSON odgovor
views/overview_skeleton.py:846–862  View direktno zove subprocess.Popen(["explorer", ...])
                              sa putanjom relativnom na __file__
```

`GuiApiClient` nema javne metode za import plana, kreiranje sesije ni
shutdown-prepare. Zato pozivaoci koriste privatne `_post`, `_apply_auth_header`
i `_nam`.

## 2. Cilj

Poslije ovog taska:

- `composition_root.py` sadrži wiring, DI i signal-connect — nijednu
  konstrukciju request payloada, nijedno čitanje fajla sa diska, nijedan
  poziv privatne metode API klijenta, nijedno parsiranje HTTP odgovora;
- `GuiApiClient` izlaže javnu metodu za svaku operaciju koju GUI koristi;
- View sloj ne pokreće OS proces;
- `guard_architecture.py` pušten sa proširenim pravilima (FLOW-1156) prijavljuje
  nula prekršaja na novom kodu i tri na starom.

## 3. Traženo rješenje

### 3.1 Nove javne metode na `GuiApiClient`

Dodati u `src/flowos/gui/services/client.py`, po uzoru na postojeće javne
metode (`get_projects`, `create_project`, `get_plan_progress`):

```python
def import_plan(self, project_id: str, markdown_text: str, on_success):
    """Uvozi plan. Canonical field je markdown_text (vidi PlanImportRequest)."""
    self._post(
        f"/projects/{project_id}/import-plan",
        {"markdown_text": markdown_text},
        on_success,
    )

def create_tracked_session(
    self, project_id: str, agent_type: str, repo_path: str, pid: int
):
    """Kreira EXTERNAL_TRACKED sesiju za već pokrenut agentski proces."""
    self._post(
        "/sessions",
        {
            "project_id": project_id,
            "agent_type": agent_type,
            "repo_path": repo_path,
            "execution_mode": "EXTERNAL_TRACKED",
            "pid": pid,
        },
        self.sessions_received,
    )

def prepare_shutdown(self, on_ready):
    """GET /system/shutdown/prepare. on_ready prima dict ili None pri grešci."""
    ...
```

`prepare_shutdown` mora unutar klijenta obaviti: `QNetworkRequest`,
`_apply_auth_header`, `self._nam.get(...)`, provjeru `reply.error()`, i
parsiranje JSON tijela. Pozivalac dobija samo `dict | None`.

**Napomena o `markdown_text`:** postojeći kod šalje `markdown`, a endpoint
`plan_progress.py:180` čita `markdown_text`. To je zaseban bug (FLOW-1105).
U ovom tasku **koristi `markdown_text`**, jer je to polje deklarisano u
`shared/contracts/plan_progress.py:150` (`PlanImportRequest`) i jedino koje
endpoint čita.

### 3.2 Novi Controlleri

Tri nova fajla u `src/flowos/gui/controllers/`, po uzoru na `overview.py`.
Svaki prima `GuiApiClient` u konstruktoru, emituje Qt signale, i ne dodiruje
bazu, Git, filesystem ni subprocess — osim gdje je izričito navedeno niže.

```text
plan.py       PlanController
              import_plan(project_id, file_path) — čita fajl, zove api.import_plan
agents.py     AgentsController
              track_agent(project_id, repo_path, pid, agent_type)
                — normalizuje agent_type, validira repo_path, zove klijent
system.py     SystemController
              request_shutdown() — zove api.prepare_shutdown, emituje jedan od
                signala: shutdown_allowed / shutdown_blocked(active_count) /
                shutdown_failed
              open_reports_folder(path) — otvara folder platform-svjesno
```

Čitanje `.md` fajla u `PlanController` je dozvoljeno: to je ulaz koji je
korisnik izabrao kroz dijalog, ne pristup persistenciji. Otvaranje foldera u
`SystemController` je jedino dozvoljeno mjesto za `subprocess` u GUI stablu.

### 3.3 Izmjene u `composition_root.py`

`_on_import_plan` zadržava samo `QFileDialog` i delegira:

```python
def _on_import_plan(self) -> None:
    from PySide6.QtWidgets import QFileDialog

    path, _ = QFileDialog.getOpenFileName(
        self._window, "Uvezi plan", "", "Markdown (*.md)"
    )
    if path and self._plan_controller and self._active_project_id:
        self._plan_controller.import_plan(self._active_project_id, path)
```

`_track_agent` delegira na `AgentsController`. `_on_shutdown_requested`
delegira na `SystemController` i samo povezuje njegove signale na postojeće
dijaloge (`_show_shutdown_blocked_dialog`, `_do_shutdown_confirm`,
`_quit_app`). Ugniježđena funkcija `_on_prepare_ready` nestaje.

Dijalozi (`QMessageBox`) ostaju u `composition_root` ili odlaze u View — ne u
Controller.

### 3.4 View: otvaranje foldera

`views/overview_skeleton.py:846–862` — ukloniti `import subprocess` i
`subprocess.Popen(["explorer", ...])`. Widget emituje signal, a
`composition_root` ga povezuje na `SystemController.open_reports_folder`.
Putanja se ne konstruiše relativno na `__file__`.

Platform-svjesno otvaranje u Controlleru:

```text
win32   explorer <path>
darwin  open <path>
ostalo  xdg-open <path>
```

### 3.5 Postojeći test

`tests/gui/test_plan_import_flow.py:37` tvrdi:

```python
assert fake_api.posts == [("/projects/project-1/import-plan", {"markdown": "# Plan\n"})]
```

Taj test prolazi jer provjerava GUI naspram lažnog API-ja, ne naspram ugovora
endpointa — zelen je iako je kod slomljen. Prepisati ga tako da provjerava
poziv `PlanController.import_plan`, a `markdown_text` kao ključ.

## 4. Acceptance

Svaka stavka provjerljiva komandom ili direktnim čitanjem koda.

```text
[ ] gui/controllers/ sadrži overview.py, plan.py, agents.py, system.py
[ ] grep -n "_api\._post\|_api\._nam\|_api\._apply_auth_header" src/flowos/gui/composition_root.py
    → nula pogodaka
[ ] grep -rn "subprocess" src/flowos/gui/views/ → nula pogodaka
[ ] grep -n "__file__" src/flowos/gui/views/overview_skeleton.py
    → nema konstrukcije putanje do agent_reports
[ ] GuiApiClient ima javne import_plan, create_tracked_session, prepare_shutdown
[ ] composition_root.py ne sadrži json.loads, pathlib.Path(...).read_text,
    QNetworkRequest ni QNetworkReply
[ ] svaki novi Controller ne importuje flowos.service, sqlalchemy ni flowos.gui.views
[ ] python scripts/guard_architecture.py → PASS
[ ] pytest tests/gui tests/integration/test_composition_root.py tests/architecture -q → PASS
[ ] python scripts/verify.py → PASS
[ ] ruff check . → clean
[ ] mypy src → clean
[ ] test_plan_import_flow.py provjerava markdown_text, ne markdown
```

### 4.1 Adversarni dokaz (obavezan)

Ovaj task mijenja PUT izvršavanja (`composition_root → API` postaje
`composition_root → Controller → API`), pa po blueprint §9 važi procedura
TEST-ADVERSARIAL:

```text
1. Napisati test koji tvrdi da import ide kroz PlanController.
2. Privremeno vratiti stari kod (direktan _api._post u composition_root).
3. Pokrenuti taj test — MORA pasti.
4. Ako prolazi, test ne dokazuje ništa; prepraviti ga (npr. spy na
   PlanController.import_plan + _api._post postavljen da baci grešku ako je
   pozvan direktno iz composition_root).
5. Vratiti ispravan kod.
6. Isti test MORA proći.
7. Doslovan output oba pokretanja ide u izvještaj.
```

Isto ponoviti za `_track_agent`.

## 5. Allowed / Forbidden paths

**Allowed:**

```text
src/flowos/gui/controllers/__init__.py
src/flowos/gui/controllers/plan.py           (novo)
src/flowos/gui/controllers/agents.py         (novo)
src/flowos/gui/controllers/system.py         (novo)
src/flowos/gui/composition_root.py
src/flowos/gui/services/client.py
src/flowos/gui/views/overview_skeleton.py    (samo uklanjanje subprocess bloka + novi signal)
tests/gui/test_plan_import_flow.py
tests/gui/                                    (novi testovi)
tests/architecture/test_boundaries.py         (samo ako novi Controlleri traže novo pravilo)
```

**Forbidden:**

```text
src/flowos/service/**            — backend se ne dira
scripts/guard_architecture.py    — proširenje guarda je FLOW-1156, ne ovaj task
src/flowos/cli/**
alembic/**
docs/**
bilo koja druga datoteka pod src/flowos/gui/views/ osim overview_skeleton.py
```

Ne mijenjati preostalih 14 mapping handlera u `composition_root.py`
(`_on_health`, `_on_projects`, `_on_plan_progress`, `_on_plan_item_received`,
`_on_sessions`, `_on_resume`, `_on_error`, `_on_timeline`,
`_on_agents_scanned`, `_on_projects_page`, `_on_ws_message`,
`_on_page_changed`, `_load_plan_item_details`, `_refresh_all`). Oni se
prepravljaju u fazi C kad se ekrani ionako diraju.

Odstupanje od kontrakta prijaviti kao `OUT_OF_SCOPE_FINDING`, ne popravljati
tiho i ne širiti scope.

## 6. Review

**Reviewer: Claude.** Nezavisan — nije implementirao.

Fokus, tim redom:

```text
1. Je li poslovna logika stvarno izašla, ili je samo premještena u fajl koji
   se zove Controller a i dalje zove privatne metode klijenta
2. Adversarni dokaz — je li test stvarno pada na starom kodu, ili je pisan
   tako da bi prošao i prije promjene
3. Granica sloja — importi novih Controllera, i da View više ne zove OS proces
4. Scope — je li dirano nešto van allowed_paths, posebno preostalih 14 handlera
5. Ponašanje — import plana, praćenje agenta, shutdown tok i otvaranje foldera
   rade isto kao prije iz korisničke perspektive
```

Reviewer čita **stvaran diff**, ne samo izvještaj, i sam pokreće
`scripts/verify.py`.

Verdict blok na vrhu review izvještaja:

```yaml
verdict: PASS|PASS_WITH_NOTES|REJECT
scope: PASS|REJECT
acceptance: PASS|REJECT
architecture: PASS|REJECT
security: PASS|REJECT
blocking_findings:
  - <kod>: <jednoredni opis>
```

## 7. Koordinacija

```text
grana:     task/FLOW-1157-gui-controllers
worktree:  <repo>-worktrees/FLOW-1157-gui-controllers
baseline:  b83f197 ili noviji main — provjeriti `git rev-parse HEAD` i navesti u izvještaju
zavisnosti: nema
blokira:   FLOW-1156 (proširenje guarda) — ne počinjati 1156 dok 1157 nije mergovan
```

Implementer **ne commituje i ne pušuje sam**. Kad je gotov, piše izvještaj sa
doslovnim outputom verifikacionih komandi i predaje ga koordinatoru.

Poslije mergea: post-merge gate na glavnoj grani (`pytest -q`, `ruff check .`,
`mypy src`, `python scripts/verify.py`), pa ažuriranje statusa u ovom
kontraktu.

## 8. Izvještaj implementera

```text
agent_reports/<YYYY-MM-DD>-FLOW-1157-codex-gui-controllers.md
```

Sadrži: baseline SHA, listu stvarno promijenjenih fajlova, doslovan output
svih komandi iz sekcije 4, oba rezultata adversarnog dokaza iz 4.1, i svaki
`OUT_OF_SCOPE_FINDING`.

Formulacija „testovi prolaze" bez doslovnog outputa nije prihvatljiva.
