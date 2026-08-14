---
flowos_report_version: 1
agent: codex
model: gpt-5
session_id: unknown
report_id: 8d04ec06-41be-4686-89f8-b32930cad4d1
report_type: analysis
tasks:
  - unassigned
commits: []
created_at: 2026-08-12T18:49:10+02:00
---

# FlowOS dogfooding plan — pre-import check

READ ONLY provjera plana:

`docs/FlowOS-plan-faze-11-15-dogfooding.md`

Baseline koji je korisnik zadao i koji je potvrđen u Git-u:

```text
33d2f32415e3866d6b55186416b840ad10c9162a
33d2f32 feat: add workflow ledger task decisions
```

Working tree nije bio čist prije ove provjere jer već postoje untracked artefakti iz prethodnog GUI runtime reporta i sam dogfooding plan:

```text
?? agent_reports/2026-08-12-flowos-current-gui-runtime-review.md
?? agent_reports/gui_runtime_2026-08-12/
?? docs/FlowOS-plan-faze-11-15-dogfooding.md
```

Nisam mijenjao kod. Nisam mijenjao plan. Nisam pravio commit. Nisam pushovao.

GitNexus je provjeren, ali indeks za FlowOS je 6 commitova iza HEAD i query indeks je degradiran, pa je autoritet za ovaj report stvarni trenutni kod na disku i stvarni `PlanMarkdownParser`.

## 1. Parser check

Stvarni parser:

- `src/flowos/service/services/plan_import.py::PlanMarkdownParser`
- `src/flowos/service/services/plan_import.py::PlanImportService`

Direktni rezultat `PlanMarkdownParser().parse(markdown)`:

```text
phases: 5
items: 20
criteria: 141
dependencies: 20
unclear_sections: 20
```

Rezultat internog parsing puta koji koristi `PlanImportService._parse_with_phases(...)`:

```text
phases: 5
items: 20
criteria: 141
dependencies: 20
unclear_sections: 0
```

End-to-end import u privremenu in-memory SQLite bazu stvarnim `PlanImportService.import_plan(...)` je prošao:

```text
db.phases: 5
db.items: 20
db.criteria: 141
db.dependencies: 20
```

### Parser nalaz

Parser tačno parsira 5 faza i 20 `FLOW` stavki.

Međutim, direktni `PlanMarkdownParser.parse()` svaku `#### FLOW-...` stavku prijavljuje i kao `unclear_section`, jer unclear kolektor provjerava `heading.startswith("##")`, a `####` takođe počinje sa `##`.

To nije semantički problem plana, nego parser behavior. Ali za formalni parser check rezultat nije čist.

### Detalji po FLOW stavci

| FLOW | Heading | Risk | `Dokaz` criterion | `Obavezno` criteria | Dependency parsing |
|---|---|---|---|---|---|
| FLOW-1101 | OK | HIGH OK | OK | 5 REQ + OUT_OF_SCOPE OK | nema dependency |
| FLOW-1102 | OK | MEDIUM OK | OK | 4 REQ + OUT_OF_SCOPE OK | `FLOW-1101` kao `BLOCKS_START` |
| FLOW-1103 | OK | MEDIUM OK | OK | 5 REQ + OUT_OF_SCOPE OK | `FLOW-1101`, `FLOW-1102` kao `BLOCKS_START` |
| FLOW-1104 | OK | MEDIUM OK | OK | 5 REQ + OUT_OF_SCOPE OK | `FLOW-1103` kao `BLOCKS_START` |
| FLOW-1201 | OK | MEDIUM OK | OK | 5 REQ + OUT_OF_SCOPE OK | `FLOW-1104` kao `BLOCKS_START` |
| FLOW-1202 | OK | MEDIUM OK | OK | 5 REQ + OUT_OF_SCOPE OK | `FLOW-1201` kao `BLOCKS_START` |
| FLOW-1203 | OK | HIGH OK | OK | 6 REQ + OUT_OF_SCOPE OK | `FLOW-1202` kao `BLOCKS_START` |
| FLOW-1204 | OK | MEDIUM OK | OK | 5 REQ + OUT_OF_SCOPE OK | `FLOW-1203` kao `BLOCKS_START` |
| FLOW-1301 | OK | HIGH OK | OK | 6 REQ + OUT_OF_SCOPE OK | `FLOW-1203` kao `BLOCKS_START` |
| FLOW-1302 | OK | MEDIUM OK | OK | 6 REQ + OUT_OF_SCOPE OK, ali početni backtick se gubi na event-name kriterijumima | `FLOW-1301` kao `BLOCKS_START` |
| FLOW-1303 | OK | MEDIUM OK | OK | 5 REQ + OUT_OF_SCOPE OK, ali početni backtick se gubi na event-name kriterijumima | `FLOW-1302` kao `BLOCKS_START` |
| FLOW-1304 | OK | MEDIUM OK | OK | 4 REQ + OUT_OF_SCOPE OK | `FLOW-1302` kao `BLOCKS_START` |
| FLOW-1401 | OK | HIGH OK | OK | 6 REQ + OUT_OF_SCOPE OK, ali početni backtick se gubi na button/status kriterijumima | `FLOW-1302` kao `BLOCKS_START` |
| FLOW-1402 | OK | MEDIUM OK | OK | 4 REQ + OUT_OF_SCOPE OK | `FLOW-1401` kao `BLOCKS_START` |
| FLOW-1403 | OK | HIGH OK | OK | 7 REQ + OUT_OF_SCOPE OK | `FLOW-1402` kao `BLOCKS_START` |
| FLOW-1404 | OK | HIGH OK | OK | 5 REQ + OUT_OF_SCOPE OK | `FLOW-1403` kao `BLOCKS_START` |
| FLOW-1501 | OK | LOW OK | OK | 4 REQ + OUT_OF_SCOPE OK | `FLOW-1404` kao `BLOCKS_START` |
| FLOW-1502 | OK | MEDIUM OK | OK | 5 REQ + OUT_OF_SCOPE OK | `FLOW-1501` kao `BLOCKS_START` |
| FLOW-1503 | OK | MEDIUM OK | OK | 4 REQ + OUT_OF_SCOPE OK | `FLOW-1502` kao `BLOCKS_START` |
| FLOW-1504 | OK | LOW OK | OK | 5 REQ + OUT_OF_SCOPE OK | `FLOW-1503` kao `BLOCKS_START` |

### Posebni parser zahtjevi

- Pogrešan `INFORMATIONAL` dependency: nije viđen.
- `BLOCKS_START` nije prepoznat: nije viđeno; sve eksplicitne “Završiti X prije Y” reference su prepoznate kao `BLOCKS_START`.
- Dupliran dependency: nije viđeno.
- Izgubljen criterion: nije viđeno kao nestanak cijelog kriterijuma.
- Oštećen tekst criterion-a: viđeno kada numerisana `Obavezno:` stavka počinje inline code tokenom. Parser regex skida početni backtick, pa npr. `IMPLEMENTATION_COMPLETED` postaje `IMPLEMENTATION_COMPLETED``.
- `unclear_sections`: 20, po jedna za svaku `#### FLOW-...` stavku u direktnom `PlanMarkdownParser.parse()` rezultatu.

Minimalna tekstualna korekcija koja bi popravila oštećene criterion tekstove:

```text
1. Događaj `IMPLEMENTATION_COMPLETED` prikazati ...
2. Događaj `TEST_RESULT` prikazati ...
3. Događaj `REVIEW_COMPLETED` prikazati ...
4. Događaj `TASK_DECISION` prikazati ...
```

i analogno:

```text
1. Akcija `Prihvati rezultat` mapira se ...
2. Akcija `Vrati u doradu` mapira se ...
3. Akcija `Odbaci rezultat` mapira se ...
6. Verdict `ACCEPTED` ne smije ...
```

Za 20 `unclear_sections` ne postoji sigurna Markdown-only korekcija koja istovremeno čuva postojeće `#### FLOW-...` heading parsiranje. Ako se `####` promijeni da ne počinje sa `##`, item headings prestaju biti parser-compatible. To je parser/import-reporting problem, ne plan redesign problem.

## 2. Current code reality check po FLOW stavci

| FLOW | Status | Dokaz iz trenutnog koda |
|---|---|---|
| FLOW-1101 | VALID | `create_sqlite_engine()` koristi `pool_size=1`, `max_overflow=0`; `composition_root._scan_existing_agent_reports_for_project()` radi startup ingestion; prethodni runtime report/log pokazuje QueuePool timeout tokom `AgentReport startup ingestion`. |
| FLOW-1102 | VALID | `GuiApiClient._handle_response()` u error grani radi `if callable(signal): signal(...) elif signal: signal.emit(...)`; runtime je pokazao `TypeError` nad native Qt signalom. |
| FLOW-1103 | PARTIALLY ALREADY IMPLEMENTED | `pyproject.toml` ima `flowos-gui` i `flowos-service`; `gui/app.py` podržava `--live`; `composition_root._ensure_service_running()` pokušava `flowos-service.exe`. Ali `scripts/run_gui.py` i `scripts/run_service.py` su samo docstring placeholderi. |
| FLOW-1104 | PARTIALLY ALREADY IMPLEMENTED | `PlanImportService`, `PlanProgressService.import_plan()` i ruta `/projects/{project_id}/import-plan` postoje. Međutim GUI `_on_import_plan()` šalje `{"markdown": content}`, a ruta očekuje `markdown_text`, pa postojeći GUI import tok nije ispravno spojen. |
| FLOW-1201 | PARTIALLY ALREADY IMPLEMENTED | Backend `/projects` CRUD postoji i `GuiApiClient.create_project()` postoji. `ProjectsPage` samo renderuje listu; nema `Dodaj projekat` UI/formu, a `FlowOsGui._on_projects()` automatski uzima prvi projekat. |
| FLOW-1202 | PARTIALLY ALREADY IMPLEMENTED | Backend `/tasks` CRUD i `TaskService` postoje; `TasksPage` postoji kao tabela. `GuiApiClient` nema `get_tasks`, a `composition_root.py` ne wire-upuje `TasksPage` na `/tasks`. |
| FLOW-1203 | PARTIALLY ALREADY IMPLEMENTED | `Task`, `SessionTaskBinding`, `AgentReportBindingLink` i `WorkflowLedgerService.list_for_task()` postoje. Ne postoji minimalni Task Detail read endpoint/service koji sve to objedini za GUI. |
| FLOW-1204 | VALID | `TasksPage` nema selection/detail wiring; ne postoji stvarni Task Detail GUI. Plan je validan kao naredna implementacija nakon read modela. |
| FLOW-1301 | PARTIALLY ALREADY IMPLEMENTED | `WorkflowLedgerService.list_for_task()` postoji i ledger model ima task/plan/session scope. Ne postoji HTTP/API read model koji to izlaže kao Task workflow history. |
| FLOW-1302 | VALID | GUI nema Task Detail ekran ni Workflow History komponentu; `GuiApiClient` nema ledger metode. |
| FLOW-1303 | PARTIALLY ALREADY IMPLEMENTED | Backend ledger payloadi čuvaju `source_path/source_report_id` za report događaje i verification artifact metadata za `TEST_RESULT`. Nema GUI otvaranja reporta/test dokaza iz task istorije. |
| FLOW-1304 | PARTIALLY ALREADY IMPLEMENTED | `ProjectTimelineService` već spaja `FileActivity` i `SessionEvent` kao tehničku aktivnost; `WorkflowLedgerService` je zaseban. GUI još nema workflow history, pa razlika nije korisnički vidljiva. |
| FLOW-1401 | PARTIALLY ALREADY IMPLEMENTED | Backend `WorkflowDecisionService.record_report_decision()` kreira `TASK_DECISION` i `ReportService.set_verdict()` delegira na njega. Nema GUI kontrola ni vidljive rute za report verdict decision tok. |
| FLOW-1402 | PARTIALLY ALREADY IMPLEMENTED | Backend za `NEEDS_WORK/REJECTED` vraća povezane `PlanItem` u `IN_PROGRESS` kroz `_apply_plan_item_consequences()`. GUI ne prikazuje ovaj tok niti čeka confirmed response. |
| FLOW-1403 | VALID | Pojedinačni backend dijelovi postoje, ali kompletan GUI-visible dogfooding tok ne postoji. Planirana stavka je stvarni end-to-end vertical slice. |
| FLOW-1404 | PARTIALLY ALREADY IMPLEMENTED | `SessionTaskBinding` model, service i `/sessions/{id}/bindings`/`switch` rute postoje. GUI ne prikazuje binding istoriju niti task attribution history. |
| FLOW-1501 | VALID | Ovo je namjerno post-dogfooding analysis/artifact stavka; nije očekivano da je sada implementirana. |
| FLOW-1502 | VALID | Sidebar danas ima sve primarne stavke; odluka o pojednostavljenju poslije dogfoodinga je validna i ne traži trenutnu arhitekturu promjenu. |
| FLOW-1503 | PARTIALLY ALREADY IMPLEMENTED | GUI runtime review je već dokazao stare mock/placeholder pretpostavke. Kod sadrži stare hardkodirane widgete u `overview_skeleton.py`, dok composition root koristi novije view komponente. |
| FLOW-1504 | VALID | Buduća baseline/checkpoint stavka poslije faza 11–15; ne kontradiktuje trenutni kod. |

## 3. Posebna provjera faze 11

### FLOW-1101 — startup/QueuePool

Pretpostavka plana je potvrđena.

Dokazi:

- `src/flowos/service/services/infrastructure/persistence/engine.py` koristi SQLite engine sa `pool_size=1`, `max_overflow=0`.
- `src/flowos/service/composition_root.py` u lifespan startup-u pokreće watcher pa odmah `_scan_existing_agent_reports_for_project(...)`.
- Prethodni runtime report i log navode `sqlalchemy.exc.TimeoutError: QueuePool limit of size 1 overflow 0 reached` tokom `AgentReport startup ingestion`.

### FLOW-1102 — GUI API error path

Pretpostavka plana je potvrđena.

Dokaz:

- `GuiApiClient._handle_response()` u error grani emituje `error_occurred`, ali zatim tretira `signal` kao callable ako `callable(signal)` vrati true za Qt signal instancu. Runtime screenshot/capture je uhvatio `TypeError: native Qt signal instance ... is not callable`.

### FLOW-1103 — LIVE launch put

Pretpostavka plana je djelimično potvrđena.

Dokazi:

- `pyproject.toml` ima console script `flowos-gui = flowos.gui.app:main`.
- `src/flowos/gui/app.py` koristi `--live` za live režim; default je MOCK.
- `src/flowos/gui/composition_root.py` u live režimu zove `_ensure_service_running()` i pokušava `flowos-service.exe`.
- README navodi `python scripts/run_gui.py` i `python scripts/run_service.py`, ali skripte trenutno nisu funkcionalni runneri.

### FLOW-1104 — postojeći PlanImport/API/GUI import tok

Pretpostavka plana je djelimično potvrđena.

Dokazi:

- Parser i `PlanImportService.import_plan()` postoje i ovaj plan mogu importovati u privremenu DB.
- HTTP ruta `/projects/{project_id}/import-plan` postoji.
- GUI `PlanProgressView` ima dugme `Uvezi plan`.
- Ali GUI šalje body polje `markdown`, dok backend route očekuje `markdown_text`; dakle trenutni GUI import ne bi prošao bez korekcije.

## 4. Architecture contract check

Nisu nađeni plan kontradiktorni `PLAN-CONFLICT-XX` nalazi.

Provjera zaključanih odluka:

- Task ≠ PlanItem: PASS. `Task` i `PlanItem` su odvojeni ORM modeli; plan eksplicitno traži da se ne tretiraju kao isto.
- DecisionItem ≠ ImplementationTask: PASS. Plan ne uvodi `DecisionItem` kao zamjenu za implementation task; `TASK_DECISION` se tretira kao workflow event/odluka.
- SessionTaskBinding istorija ostaje canonical za task binding: PASS. Plan u FLOW-1203 i FLOW-1404 eksplicitno traži istorijske binding segmente i zabranjuje “jedna sesija = jedan task”.
- Workflow Ledger Phase 3A–3D ostaje canonical workflow history: PASS. Plan traži GUI/read model nad postojećim ledger događajima, ne novi history sistem.
- AgentReport nije workflow authority: PASS. Plan kaže report body ostaje evidence, ne Task status authority.
- ACCEPTED ne znači automatski DONE/VERIFIED: PASS. FLOW-1401 eksplicitno kaže da `ACCEPTED` ne smije automatski postaviti PlanItem na DONE/VERIFIED ako backend contract to ne radi.
- Nema AI guessing-a za core workflow činjenice: PASS. Više stavki eksplicitno zabranjuje AI/LLM interpretaciju i AI guess za binding.
- FlowOS je deterministic observer/evidence/workflow sistem: PASS. Plan se oslanja na backend read modele, ledger, verification artifact i existing evidence.

## 5. Dogfooding redoslijed

Redoslijed je tehnički ostvariv i dependency smislen:

```text
Faza 11: LIVE runtime + import plana
↓
Faza 12: Task postaje stvarna radna površina
↓
Faza 13: Workflow Ledger postaje vidljiv
↓
Faza 14: TASK_DECISION kroz GUI + stvarni dogfooding
↓
Faza 15: UX odluke nakon stvarnog korištenja
```

Nema potrebe za reorder-om.

Stvarni dependency problem nije redoslijed nego dva konkretna preduvjeta u Fazi 11:

1. live backend/startup mora stvarno raditi;
2. GUI/API import body mismatch mora biti riješen prije korisničkog uvoza plana kroz GUI.

## 6. Nalazi po ozbiljnosti

### BLOCKER

1. `PlanMarkdownParser.parse()` vraća 20 `unclear_sections` za svih 20 `#### FLOW` headinga.
   - Efekat: formalni parser check nije PASS.
   - Napomena: `PlanImportService` import path ipak vraća `unclear=0` i može upisati plan u privremenu bazu.

2. GUI import plan tok nije trenutno kompatibilan sa backend rutom.
   - GUI šalje `{"markdown": content}`.
   - Backend očekuje `markdown_text`.
   - Efekat: korisnički “Uvezi plan” kroz GUI vjerovatno vraća 400.

3. Live backend runtime problem iz prethodne provjere je i dalje relevantan za Fazu 11.
   - `pool_size=1/max_overflow=0` + startup ingestion path + zabilježen QueuePool timeout.
   - Efekat: dogfooding kroz live GUI nije pouzdan dok se ovo ne riješi.

### HIGH

1. `GuiApiClient._handle_response` error path baca sekundarni `TypeError` na connection/backend grešci.
   - Efekat: live GUI ne degradira čisto kada backend nije dostupan.

2. Task Detail read model ne postoji.
   - Efekat: Faze 12–14 ne mogu biti user-visible bez novog read model/API sloja.

### MEDIUM

1. Neki `Obavezno:` kriterijumi gube početni backtick ako linija počinje inline code tokenom.
   - Efekat: kriterijum nije izgubljen, ali tekst nije tačno očuvan.

2. `ReportsPage`, `ConflictsPage` i `TasksPage` postoje kao UI školjke, ali nisu wire-upovane na svoje backend rute.

3. `ProjectsPage` nema minimalan create/select UX; aktivni projekat se bira implicitno kao prvi projekat.

### LOW

1. README navodi `scripts/run_gui.py` i `scripts/run_service.py`, ali ti fajlovi su placeholderi.
2. GitNexus indeks je zastario za trenutni HEAD; nije blokirao ovu read-only provjeru jer je korišten stvarni kod.

## 7. Finalni rezultat

```text
PARSER: FIXES REQUIRED
PLAN VS CURRENT CODE: PASS
ARCHITECTURE CONTRACT: PASS
DOGFOODING ORDER: VALID
```

Zaključak:

```text
PLAN CORRECTION REQUIRED BEFORE IMPORT
```

Preciznije: plan semantički odgovara trenutnom FlowOS smjeru i ne ruši zaključane contracte, ali formalni parser/import readiness nije čist. Minimalne tekstualne korekcije mogu popraviti oštećene inline-code kriterijume; `unclear_sections` problem i GUI/API import body mismatch su problemi postojećeg parser/import puta, ne problem arhitektonskog sadržaja plana.
