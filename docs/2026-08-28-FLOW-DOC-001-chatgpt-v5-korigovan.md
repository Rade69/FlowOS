---
flowos_report_version: 1
report_id: 68dc1fcd-c861-4308-99f7-38093cbad84b
session_id: chatgpt-flow-doc-001-2026-08-28
report_type: implementation
work_status: completed
tasks:
  - FLOW-DOC-001
created_at: 2026-08-28T08:00:00+02:00
agent: ChatGPT
model: GPT-5.6-Sol
commits: []
---

# FLOW-DOC-001 — Izrada FlowOS plana razvoja v5

## Scope

Izrada dva dokumentaciona artefakta iz `FlowOS-change-spec-v4.3-to-v5.md`, uz nezavisnu source-level provjeru nalaza nad jednim fiksiranim GitHub snapshotom.

Nijedan produkcijski source fajl nije mijenjan. Nije rađen merge, push, issue update niti GitHub Actions rerun.

## Fiksirani Git snapshot

```text
repository: Rade69/FlowOS
ref: main u trenutku početka provjere
full SHA: b83f197ec12d1a57209d3858ef4fe0a878015b7f
commit message: docs: add unified development plan v4.1 and workflow documents
```

Sve code provjere u tabeli niže odnose se na ovaj SHA.

## Ulazi

Pročitani/dostupni:

- `FlowOS-change-spec-v4.3-to-v5.md`
- `FlowOS-novi-objedinjeni-detaljan-plan-razvoja-v4.3-deterministicki.md`
- `FlowOS-novi-objedinjeni-detaljan-plan-razvoja-v4.1-2026-08-26.md`
- `KAKO-RADIM.md`
- `CLAUDE.md` na fiksiranom SHA-u
- `AGENTS.md` na fiksiranom SHA-u
- `README.md` na fiksiranom SHA-u
- stvarni source/tree/test fajlovi navedeni po nalazu

### Nedostajući obavezni inputi

1. `AGENTIC_WORKFLOW_BLUEPRINT.md` nije bio dostupan u prvom passu, ali je korisnik naknadno dostavio puni dokument i korektivni pass ga je pročitao u cijelosti.
2. v4.3 tvrdi da je izveden iz v4.2, ali v4.2 nije pronađen u fiksiranom repo snapshotu ni među dostupnim ulaznim dokumentima.

Konačni ispravljeni v5 više nema blueprint rupe nastale zbog nedostupnog dokumenta; samo v4.2 ostaje nedostajući input.

## Ishod provjere §4 change speca

| # | Ishod | Sažetak | Dokaz / šta je otvoreno |
|---|---|---|---|
| 1 | **POTVRĐENO** | FLOW-1109 je završen i commitovan | commit c9c92d88... je ancestor pina; redaction kod postoji u `sessions/completion.py` i worktree verify HTTP izlazu; committed review evidence navodi targeted/regression/verify PASS. **Lokacija:** `src/flowos/service/services/sessions/completion.py`; `src/flowos/service/controllers/http/worktrees.py`; commit `c9c92d88d98f3920fd6a716bff9b0fc8239b650c`. |
| 2 | **POTVRĐENO** | Tri unsafe string-prefix provjere postoje u `worktrees/service.py`. | `list_flowos_worktrees`: `wt.path.replace("\", "/").startswith(wt_dir)`; `_find_worktree`: `wt.path == path or wt.path.startswith(path)`; `_dict_to_info`: `is_main = not path.replace("\", "/").startswith(wt_dir)`. **Lokacija:** `src/flowos/service/services/worktrees/service.py` ~152, ~393, ~429 na SHA `b83f197ec12d1a57209d3858ef4fe0a878015b7f`. |
| 3 | **POTVRĐENO** | GUI/backend Plan Import field mismatch. | GUI šalje `{"markdown": content}`; endpoint čita `body.get("markdown_text", "")`. **Lokacija:** `src/flowos/gui/composition_root.py` ~226–239; `src/flowos/service/controllers/http/plan_progress.py` ~173–184. |
| 4 | **POTVRĐENO** | Import endpoint ne koristi postojeći Pydantic request model. | Endpoint prima `body: dict`; `PlanImportRequest` definiše `markdown_text`. **Lokacija:** `src/flowos/service/controllers/http/plan_progress.py` ~173; `src/flowos/shared/contracts/plan_progress.py` ~150. |
| 5 | **POTVRĐENO** | `flowos session start` ne pokreće agentski proces. | Funkcija radi samo HTTP `POST /sessions`. **Lokacija:** `src/flowos/cli/app.py` ~300–350. |
| 6 | **POTVRĐENO** | Nije nađen produkcijski caller `AgentProcessLauncher.launch()`. | Pregledan je kompletan services tree, service composition root, CLI session start i adapter; konkretan caller je u unit testu. Repo search nije našao drugi caller. **Lokacija:** Otvoreno: `src/flowos/service/composition_root.py`, `src/flowos/cli/app.py`, `src/.../agent_adapters/claude_code.py`, `tests/unit/test_agent_adapter.py`; rekurzivni `src/flowos/service/services` tree. |
| 7 | **POTVRĐENO** | Session CLI upisuje PID CLI procesa. | Payload sadrži `"pid": os.getpid()`. **Lokacija:** `src/flowos/cli/app.py` ~320–340. |
| 8 | **POTVRĐENO** | `AdapterCapabilities.can_launch` default je True. | Dataclass i ClaudeCodeAdapter capability to potvrđuju. **Lokacija:** `src/flowos/service/services/infrastructure/agent_adapters/claude_code.py` ~20–55. |
| 9 | **POTVRĐENO** | Navedeni paketi su prazni osim `__init__.py`. | Rekurzivni services tree nema druge fajlove u execution/jobs/approvals/usage/git/infrastructure/process/infrastructure/filesystem. **Lokacija:** Rekurzivno otvoren `src/flowos/service/services` tree; konkretni direktoriji navedeni u nalazu. |
| 10 | **POTVRĐENO** | Process package docstring tvrdi Wrapper + Managed Execution upotrebu. | Doslovno: `Koristi ga Wrapper (CLI Service) i Managed Execution.` **Lokacija:** `src/flowos/service/services/infrastructure/process/__init__.py` ~1–6. |
| 11 | **POTVRĐENO** | `EvidenceService` postoji i ključan je po `plan_item_id`. | `EvidenceBundle` sastavlja sessions, commits, changed files, verification, verdict, conflicts i criteria. **Lokacija:** `src/flowos/service/services/evidence.py` ~1–170. |
| 12 | **POTVRĐENO** | `ProjectStateService` postoji. | Konsoliduje PlanItem/Session/Conflict/WorkspaceState/Worktree/Verification podatke. **Lokacija:** `src/flowos/service/services/project_state.py` ~1–230. |
| 13 | **POTVRĐENO** | Postoje dva timeline servisa. | Postoje `ProjectTimelineService` i session timeline servis. **Lokacija:** `src/flowos/service/services/project_timeline.py`; `src/flowos/service/services/sessions/timeline.py`. |
| 14 | **POTVRĐENO** | Nema `TaskContract` modela/tabele u sadašnjem kodu. | Rekurzivno stablo nema task_contract modul; `Task` ORM ima title/description/status/priority/plan_item_id; task contracts DTO takođe nema Contract model. **Lokacija:** Otvoreno: rekurzivni services tree, `infrastructure/persistence/models.py`, `shared/contracts/tasks.py`, `service/controllers/http/tasks.py`. |
| 15 | **POTVRĐENO** | Canonical eventi su raspoređeni preko dva writer-a. | Ledger definiše IMPLEMENTATION_COMPLETED/TEST_RESULT/REVIEW_COMPLETED; decisions servis definiše TASK_DECISION. **Lokacija:** `src/flowos/service/services/workflow/ledger.py` ~25–40; `workflow/decisions.py` ~25–40. |
| 16 | **POTVRĐENO** | Front-matter ima strogu allowlistu. | Required: flowos_report_version/report_id/session_id/report_type/tasks/created_at; optional work_status/agent/model/commits; unknown key podiže FrontMatterError. **Lokacija:** `src/flowos/service/services/reports/front_matter.py` ~70–125. |
| 17 | **POTVRĐENO** | Nema strukturisanog reviewer verdicta. | `user_verdict` je ljudska odluka; review je free-text `independent_review_summary`/`found_issues`. **Lokacija:** `src/flowos/service/services/infrastructure/persistence/report_models.py` ~1–170. |
| 18 | **POTVRĐENO** | Agent report ulazi kroz ingestion servis. | Ingestion prati/parsa `<repo>/agent_reports/*.md`, validira source identity i ingestuje u DB. **Lokacija:** `src/flowos/service/services/reports/ingestion.py` ~1–100+. |
| 19 | **POTVRĐENO** | ConflictService ima pet post-fact tipova. | WRITE_WRITE (10m), LATE_OVERLAP (30m), BRANCH_CHANGE, STALE_SESSION, NO_COMMIT. **Lokacija:** `src/flowos/service/services/conflicts/service.py` cijeli servis; NO_COMMIT ~390+. |
| 20 | **POTVRĐENO** | Nema file-claim registryja u FlowOS kodu. | Rekurzivni services/persistence tree nema claim servis/model; postojeći conflict servis počinje od opažene aktivnosti. **Lokacija:** Otvoreno: kompletan `src/flowos/service/services` tree, persistence modeli, conflicts service, tasks service. |
| 21 | **POTVRĐENO** | Nema `coordination.py` ni `agent_sensors.py` u FlowOS repou. | Nema ih u rekurzivnom FlowOS services/source treeju; pojavljuju se samo kao iskustvo drugog projekta u KAKO-RADIM dokumentu. **Lokacija:** Otvoreno: rekurzivni FlowOS source tree + `KAKO-RADIM.md`. |
| 22 | **POTVRĐENO** | FlowOS nema svoj MCP surface. | Nema MCP package/entrypoint/rute u source treeju; AGENTS/CLAUDE referišu GitNexus MCP kao eksterni alat. **Lokacija:** Otvoreno: kompletan source tree, `AGENTS.md`, `CLAUDE.md`, `pyproject.toml`. |
| 23 | **POTVRĐENO** | GUI ima 10 stranica u 3 grupe. | RAD 4, NADZOR 4, SISTEM 2. **Lokacija:** `src/flowos/gui/views/overview_skeleton.py` ~205–220. |
| 24 | **POTVRĐENO** | `Zadaci` nije wired na backend. | `TasksPage()` se instancira inline; nema reference/connect/render flowa. **Lokacija:** `src/flowos/gui/composition_root.py` ~485–500; `gui/services/client.py`. |
| 25 | **POTVRĐENO** | Stvarno wiring imaju Pregled/Plan/Sesije/Agenti/Radna stabla/Projekti; ne Tasks/Conflicts/Reports/Settings. | Pregledano composition-root konstrukcija i signal wiring. **Lokacija:** `src/flowos/gui/composition_root.py` ~110–330 i ~450–550. |
| 26 | **POTVRĐENO** | Nema zasebne stranice `Aktivnost`. | NAV_GROUPS je ne navodi; activity_view se prikazuje u Pregledu. **Lokacija:** `src/flowos/gui/views/overview_skeleton.py` ~205–220; `gui/composition_root.py` overview wiring. |
| 27 | **POTVRĐENO** | Verify subprocess nema filtered `env`. | `subprocess.run(..., cwd=..., capture_output=True, text=True, timeout=...)` nema `env=`. **Lokacija:** `src/flowos/service/services/verification/service.py` ~175–195. |
| 28 | **POTVRĐENO** | Verification timeout ne dokazuje process-tree kill. | Koristi `subprocess.run(timeout=...)`; dedicated process package je prazan. **Lokacija:** `verification/service.py` ~175–205; `infrastructure/process/__init__.py`; rekurzivni services tree. |
| 29 | **POTVRĐENO** | U pregledanim produkcijskim Git/worktree servisima nema checkout/reset/restore historical replaya. | WorktreeService koristi worktree add/list/remove/prune, status, branch, rev-parse/fetch; GitStateReader koristi rev-parse/branch/status. Nema historical mutation u očekivanim Git-owner modulima. **Lokacija:** Otvoreno: `worktrees/service.py`, `worktrees/manager.py`, `infrastructure/git_poller.py`; rekurzivni services tree. |
| 30 | **POTVRĐENO** | `guard_architecture.py` postoji; `verify.py` pokreće architecture testove, ali **ne pokreće direktno guard skriptu**. | Verify korak 4 je `pytest tests/architecture/`. Zato FLOW-1156 acceptance eksplicitno provjerava i skriptu i test suite. **Lokacija:** `scripts/guard_architecture.py`; `scripts/verify.py` ~80–115. |
| 30b | **POTVRĐENO** | Guard ima pet import-based pravila i ozbiljne rupe. | Ne pokriva composition_root/CLI calls/stdlib subprocess i ne vidi private method calls. **Lokacija:** `scripts/guard_architecture.py` ~14–100. |
| 30c | **DJELIMIČNO** | Architecture testovi dijele većinu ograničenja, ali nisu identični guard skripti. | Test je i dalje import-based, ali ima dodatni `cli_ne_importuje_gui`; i dalje ne vidi composition_root call bypass ili View subprocess call. **Lokacija:** `tests/architecture/test_boundaries.py` ~1–170. |
| 30d | **POTVRĐENO** | GUI ima jednu stvarnu Controller klasu; composition_root je de facto preopterećen. | Controllers dir ima samo `overview.py` (+ init). Composition root sadrži `_on_import_plan`, `_track_agent`, `_on_prepare_ready`, `_on_shutdown_requested`. **Lokacija:** `src/flowos/gui/controllers/`; `src/flowos/gui/composition_root.py`. |
| 30e | **POTVRĐENO** | View direktno zove OS proces. | `overview_skeleton.py` importuje subprocess i radi `Popen(["explorer", ...])`. **Lokacija:** `src/flowos/gui/views/overview_skeleton.py` ~846–862. |
| 31 | **POTVRĐENO** | AttributionService vraća WORKTREE/SOLE_ACTIVE/HINT/UNATTRIBUTED/USER uz HIGH/MEDIUM/LOW. | Pregledan source. **Lokacija:** `src/flowos/service/services/attribution/service.py` ~1–210. |
| 32 | **POTVRĐENO** | D4 DIRECT/ISOLATED/HEURISTIC/UNKNOWN u v4.3 dolazi tek u FLOW-1902. | Potvrđeno čitanjem v4.3 plana; kod trenutno koristi drugu taksonomiju. **Lokacija:** Ulazni v4.3 §3 D4 i §16 FLOW-1902; `attribution/service.py`. |
| 33 | **POTVRĐENO** | Runtime ima Windows mutex i non-Windows flock. | `CreateMutexW` vs `fcntl.flock`. **Lokacija:** `src/flowos/service/services/infrastructure/runtime.py` ~65–115. |
| 34 | **POTVRĐENO** | dir_security van Windowsa samo radi mkdir i return. | Nema chmod/owner provjere na non-Windows grani. **Lokacija:** `src/flowos/service/services/infrastructure/dir_security.py` ~160–185. |
| 35 | **POTVRĐENO** | Navedena Windows-only mjesta postoje. | app_paths koristi LOCALAPPDATA; scanner tasklist; View explorer; Settings path tekst; CLI .exe/tasklist pretpostavke. **Lokacija:** `app_paths.py`; `agent_scanner.py`; `overview_skeleton.py`; `pages.py`; `cli/app.py`. |
| 36 | **POTVRĐENO** | pywin32 je uslovna Windows zavisnost. | `pywin32>=306; sys_platform == 'win32'`. **Lokacija:** `pyproject.toml` dependencies ~20–40. |
| 37 | **DJELIMIČNO** | `test_dir_security.py` potvrđeno sadrži više Windows-specific runtime skipova; globalna tvrdnja da nijedan drugi test fajl nema platform skip nije dovoljno jaka. | Otvoren je konkretan test fajl i repo search je dodatno provjeren, ali negativni globalni zaključak nije korišten kao authority. **Lokacija:** `tests/unit/test_dir_security.py`; repo search za skip obrasce. |
| 38 | **POTVRĐENO** | CLAUDE/AGENTS/README i dalje propisuju dio stare wrapper/Managed/Durable arhitekture. | AGENTS: wrapper primary, adapter redoslijed, Managed/Durable; CLAUDE: wrapper kičma, can_launch, faze 6–9; README: service→subprocess/JobObject→agents. **Lokacija:** `AGENTS.md` početne sekcije; `CLAUDE.md` arhitektura/wrapper/faze; `README.md` arhitektura. |

## Negativni nalazi — šta je otvoreno prije zaključka o odsustvu

Change spec izričito zabranjuje zaključak „ne postoji“ samo iz search rezultata. Za negativne nalaze su korišteni tree inspection + očekivani owner fajlovi:

### #6 — produkcijski caller AgentProcessLauncher

Otvoreno:

```text
rekurzivni src/flowos/service/services tree
src/flowos/service/composition_root.py
src/flowos/cli/app.py
src/flowos/service/services/infrastructure/agent_adapters/claude_code.py
tests/unit/test_agent_adapter.py
```

Unit test je konkretan caller; u pregledanom production wiring-u caller nije pronađen.

### #14 — TaskContract

Otvoreno:

```text
rekurzivni services tree
infrastructure/persistence/models.py
shared/contracts/tasks.py
controllers/http/tasks.py
tasks/service.py
```

Nema TaskContract modela/tabele/DTO-a.

### #20 — claim registry

Otvoreno:

```text
rekurzivni services tree
persistence modeli
conflicts/service.py
tasks/service.py
worktrees/service.py
```

Nema claim modela ili servisa.

### #21 — coordination.py / agent_sensors.py

Otvoren rekurzivni FlowOS source tree; tih fajlova nema. `KAKO-RADIM.md` ih opisuje kao iskustvo/alat iz drugog workflowa, ne kao FlowOS source.

### #22 — FlowOS MCP

Otvoreno:

```text
rekurzivni FlowOS source tree
pyproject.toml
AGENTS.md
CLAUDE.md
```

GitNexus MCP je eksterni alat; FlowOS MCP surface nije prisutan.

### #26 — Aktivnost stranica

Otvoreni NAV_GROUPS + composition-root wiring. Aktivnost je widget na Pregledu, ne sidebar page.

### #27 — filtered verification environment

Otvoren konkretan subprocess owner `verification/service.py`; `subprocess.run` nema `env=`.

### #29 — checkout/reset/restore u produkcijskom Git/worktree owner sloju

Otvoreno:

```text
worktrees/service.py
worktrees/manager.py
infrastructure/git_poller.py
rekurzivni services tree
```

U tim owner modulima nema historical checkout/reset/restore puta. Zaključak je ograničen na produkcijski source snapshot, ne na report tekstove ili test fixtures.

## Neslaganja sa change specom

### Korektivni review — EVIDENCE-01 FLOW-1110 — ISPRAVLJENO

Prva ChatGPT revizija je **pogrešno** tvrdila da mjesto oko ~429 koristi `Path.is_relative_to()` i zbog toga je nalaz #2 označila `DJELIMIČNO`.

Nezavisni Claude review je osporio tu tvrdnju. Ponovnim čitanjem istog fiksiranog SHA-a potvrđeno je:

```python
# ~152
wt.path.replace("\\", "/").startswith(wt_dir)

# ~393
wt.path == path or wt.path.startswith(path)

# ~429
is_main = not path.replace("\\", "/").startswith(wt_dir)
```

Ishod:

```text
nalaz #2 → POTVRĐENO
FLOW-1110 → ponovo obuhvata sva tri potvrđena prefix mjesta
prethodno suženje scope-a → poništeno
```

Ovo je važna audit korekcija: pogrešan evidence je bio krenuo u smjeru sužavanja sigurnosnog taska, pa je ispravka zapisana eksplicitno umjesto tihog prepisivanja.

### Neslaganje 1 — Architecture tests vs guard — DJELIMIČNO

`tests/architecture/test_boundaries.py` nije potpuno identičan `scripts/guard_architecture.py`: test ima dodatnu CLI→GUI import zabranu. Ipak, i test i skripta ostaju import-based i ne hvataju ključna call-level kršenja iz composition root-a i View subprocess poziv.

### Neslaganje 2 — Platform skip broj — DJELIMIČNO

Potvrđeno je da `tests/unit/test_dir_security.py` sadrži Windows-specific runtime skipove. Globalna tvrdnja „tačno jedan test fajl u cijelom repou“ nije korištena kao potpuno dokazana činjenica jer repo search nije dovoljno jak dokaz odsustva.

### Ranija ulazna rupa — Blueprint — RAZRIJEŠENO

`AGENTIC_WORKFLOW_BLUEPRINT.md` je naknadno dostavljen i pročitan u cijelosti. Konačni v5 eksplicitno mapira §1–§18.

### Neslaganje/ulazna rupa 3 — v4.2 nije dostupan

V5 ispravlja derivation chain na stvarno dostupne dokumente i ne tvrdi da je v4.2 provjeren.

## Korektivni review — CONTRADICTION-01 §22 / §33 — RAZRIJEŠENO BEZ MIJENJANJA ZAŠTIĆENOG TEKSTA

Nezavisni review je tačno utvrdio da byte-identični v4.3 §22 i §33 koriste Task Detail / GUI primitive semantiku, dok revidirana Faza C sada ima board-first Milestone 1.

Change spec istovremeno zabranjuje izmjenu tih sekcija. Zato nije prepisan zaštićeni tekst.

Izabrana je kompatibilna opcija:

```text
§22 ostaje byte-identičan
+ neposredno prije njega v5 napomena:
  Task Detail opisuje post-Milestone-1 / Faza E target

§33 ostaje byte-identičan
+ neposredno prije njega v5 napomena:
  Task Detail / GUI primitives testovi nisu Gate C testovi
```

Time board-first Faza C ostaje trenutni operativni milestone, a v4.3 north-star/test sadržaj ostaje očuvan kao budući conditional target.

## Korektivni review — guard execution semantics

Potvrđeno je da:

```text
scripts/verify.py
→ pokreće pytest tests/architecture/
→ NE pokreće direktno scripts/guard_architecture.py
```

FLOW-1156 je zato dopunjen da eksplicitno zahtijeva oba enforcement puta plus puni verify.

## Šta je promijenjeno u v5

1. Faze su prestrukturirane u A/B/C/D/E.
2. FLOW-1109 je uklonjen iz aktivnog roadmapa i ostavljen kao istorijski closed evidence.
3. FLOW-1110/1105/1111/1112 su prošireni tačno prema change specu i source nalazima.
4. Dodani su samo novi taskovi iz rezervisanog opsega koje change spec zahtijeva: FLOW-1150–1157, 1160–1167, 1170–1172.
5. FLOW-1157 → FLOW-1156 redoslijed je zaključan.
6. Blueprint core je premješten prije ljudske board-first radne površine.
7. FLOW-1200/1204 kontradikcija je riješena bez renumeracije: oba su ODGOĐENA u E; aktivna Faza C počinje tablom (`Zadaci`) i ne izvlači generičke primitive prije drugog stvarnog ekrana.
8. FLOW-1203 proširuje postojeći EvidenceService.
9. FLOW-1302 eksplicitno mora riješiti odnos prema postojećim project/session timeline servisima.
10. FLOW-1305 je premješten u A i predstavlja tvrd adversarial gate za bugfix/execution-path/architecture-path promjene.
11. FLOW-1505 je premješten u B.
12. Agentska površina je read-only/pull model; nema FlowOS-initiation.
13. FLOW-1905 i 1604/1605 su premješteni u D.
14. Faza E je uslovljena, ne obećani linearni nastavak.
15. Dodane su tri enforcement kategorije, reuse tabela, portability rule i blueprint mapping.
16. Security §26 je razdvojen na potvrđeno stanje i numerisane obaveze 1151/1152.
17. Prioriteti/sizing/mapa su prepravljeni za A–E.
18. U §32 je dodana zabrana LLM sažimanja konteksta radi token budžeta.
19. Dodata je potpuna tabela preslikavanja svih zadržanih FLOW brojeva.
20. Nakon nezavisnog Claude reviewa ispravljen je EVIDENCE-01: FLOW-1110 opet obuhvata sva tri prefix mjesta (~152/~393/~429).
21. §22 i §33 nisu mijenjani; dodane su samo v5 napomene o primjenjivosti koje razrješavaju board-first vs future Task Detail semantiku.
22. FLOW-1156 acceptance sada eksplicitno pokreće guard skriptu, architecture testove i puni verify.

## Sekcije koje su namjerno prenesene bez izmjene

Sljedeće v4.3 sekcije su kopirane byte-for-byte iz osnovnog dokumenta:

```text
§1
§2
§5
§6
§22
§23
§24
§25
§27
§28
§30
§33
§34
§35
§38
```

§37 Q1–Q5 je takođe prenesen bez izmjene.

## Izmjene koje nisu tražene change specom

```text
NONE
```

Nisu dodani novi FLOW taskovi van specifikovanog opsega i sadržaja.

## Šta nije verifikovano izvršavanjem

Ovaj zadatak je dokumentaciona transformacija/source audit. Nisu pokretani:

```text
pytest
scripts/verify.py
GUI
uvicorn
GitHub Actions
```

Kada izvještaj kaže da je postojeći report imao PASS, to je committed evidence u repou, ne novo izvršavanje od strane ChatGPT-a.

## Isporučeni artefakti

```text
docs/FlowOS-plan-razvoja-v5-2026-08-28.md
agent_reports/2026-08-28-FLOW-DOC-001-chatgpt-v5-izrada.md
```

## Preporučeni review

Risk ovog dokumentacionog taska je MEDIUM.

Prema change specu:

```text
implementer: ChatGPT
reviewers:
- Radovan
- Codex
```

Dokument nije automatski canonical authority dok korisnik/reviewer ne donese odluku.

## Korektivni pass — revidirani change spec / 2026-08-28

Nakon prve isporuke korisnik je dostavio novu verziju `FlowOS-change-spec-v4.3-to-v5`, puni `AGENTIC_WORKFLOW_BLUEPRINT.md` i prošireni `KAKO-RADIM-v2`. Ovaj pass **nije ponavljao GitHub source audit**; code nalazi i fiksirani SHA iz prethodnog dijela izvještaja ostaju isti. Promijenjena je dokumentaciona sinteza.

### Ispravljena greška prve verzije

Prva verzija v5 je Fazu C zadržala preblizu v4.3: centralni objekat je bio duboki Task Detail. Revidirani change spec eksplicitno mijenja proizvodni problem i traži board-first Milestone 1.

Ispravka:

```text
Task Detail-first
→ UKLONJENO iz aktivne Faze C

Faza C sada = jedna tabla svih aktivnih Taskova
Task / Ko radi / Gdje je / Zadnji signal / Čeka
```

### Konkretne promjene

- FLOW-1305 premješten iz C u A i postao obavezan TEST-ADVERSARIAL gate za bugfix/execution-path promjene.
- FLOW-1180 `Detekcija tišine` dodat u C.
- FLOW-1181 `Čeka na mene` dodat u C.
- Aktivna Faza C sada ima tačno 10 taskova: 1201, 1202, 1203, 1301, 1303, 1180, 1181, 1401, 1402, 1403.
- 1200, 1204, 1302, 1304, 1404, 1501, 1502, 1503, 1504 premješteni su u E kao `ODGOĐENO`, bez renumeracije.
- D3 je promijenjen na board-first: UI primitive se ne izvlače prije drugog stvarnog ekrana.
- §7.4 sada preslikava svih 18 sekcija blueprinta; nema više lažnog `OTVORENO` zbog nedostupnog blueprinta.
- `Ko radi` je deklarisana Task Contract dodjela, ne heuristička runtime atribucija.
- `Gdje je` i `Zadnji signal` su odvojeni: mehanička aktivnost ne proizvodi workflow completion.
- sizing, prioriteti, v4.3→v5 mapping i konačna roadmap mapa usklađeni su sa novom C.

### Input status nakon korekcije

Dostupni i pročitani u ovom passu:

```text
FlowOS-change-spec-v4.3-to-v5(1).md
AGENTIC_WORKFLOW_BLUEPRINT.md
KAKO-RADIM-v2-prosireno(1).md
KAKO-RADIM(1).md
FlowOS-novi-objedinjeni-detaljan-plan-razvoja-v4.1-2026-08-26.md
FlowOS-novi-objedinjeni-detaljan-plan-razvoja-v4.3-deterministicki.md
prethodno generisani FlowOS-plan-razvoja-v5-2026-08-28.md
```

`v4.2` i dalje nije dostupan.

### Validacija ispravljenog plana

```text
protected v4.3 sekcije §1, §2, §5, §6, §22, §23, §24, §25, §27, §28, §30, §33, §34, §35, §38: byte-identične
§37: byte-identičan
svi zadržani FLOW brojevi: prisutni
novi FLOW brojevi: samo dozvoljeni 1150–1157, 1160–1167, 1170–1172, 1180–1181
aktivni C taskovi: tačno 10
svih 18 blueprint sekcija: eksplicitno mapirano
```

## Nezavisni review nakon korektivnog passa

Claude Code mehanički review:

```yaml
verdict: PASS_WITH_NOTES
scope: PASS
acceptance: PASS
architecture: PASS
security: PASS
```

Materijalne napomene `EVIDENCE-01` i `CONTRADICTION-01` su adresirane u ovom korektivnom passu.

Konačni human acceptance i dalje ostaje na korisniku.
