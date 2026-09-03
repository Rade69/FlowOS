---
task_id: FLOW-DOC-001
risk: MEDIUM
implementer: ChatGPT
reviewers: [Radovan, Codex]
status: "OPEN — change spec napisan prije izrade v5"
created_at: 2026-08-28
---

# Change Spec: FlowOS plan v4.3 → v5

**Šta je ovo:** ugovor za jedan zadatak — proizvesti
`docs/FlowOS-plan-razvoja-v5-<datum>.md` iz postojećeg v4.3, sa
prestrukturiranim fazama i ugrađenim nalazima iz koda.

**Šta ovo nije:** nije plan. Ne kopirati ovaj dokument u v5.

---

## 0. Podjela posla

Analiza koja stoji iza ovog spec-a je urađena. Tvoj posao je:

1. **nezavisno potvrditi ili opovrgnuti** svaki nalaz iz sekcije 4 čitanjem repoa;
2. primijeniti izmjene iz sekcija 5–8 na v4.3;
3. proizvesti v5 i zaseban izvještaj o tome šta si provjerio i našao.

Nalazi u sekciji 4 su tvrdnje sa navedenom lokacijom. **Ne preuzimaj ih na
riječ.** Ako se tvoj nalaz razlikuje od navedenog, ne ispravljaj tiho —
zapiši neslaganje u izvještaj i primijeni ono što si sam dokazao.

---

## 1. Ulazni dokumenti

Obavezno pročitati u cijelosti prije pisanja:

```text
docs/FlowOS-novi-objedinjeni-detaljan-plan-razvoja-v4.1-2026-08-26.md
FlowOS-novi-objedinjeni-detaljan-plan-razvoja-v4_3-deterministicki.md   (osnova za v5)
AGENTIC_WORKFLOW_BLUEPRINT.md                                          (specifikacija proizvoda)
KAKO-RADIM.md                                                          (stvarni tok rada)
CLAUDE.md
AGENTS.md
README.md
```

Napomena: v4.3 se poziva na v4.2 kao osnovu. **v4.2 nije u repou.** Provjeri
i, ako ga nema, zabilježi to u izvještaju i u v5 ispravi lanac izvođenja na
stvarno stanje.

---

## 2. Nepregovarano — šta se NE smije promijeniti

Sve niže je zadržano iz v4.3 i ne otvara se ponovo:

```text
IMPLEMENTED ≠ VERIFIED ≠ ACCEPTED
Ljudska odluka je jedini canonical authority za acceptance/rejection
AgentReport je claim/evidence container, ne authority
Arhitektura ostaje View → Controller → Services
FlowOS ne pokreće, ne promptuje, ne bira i ne kontroliše agentski alat
FlowOS ne koristi LLM da izvodi zaključke, prioritete ili atribuciju
FlowOS ne radi automatski merge/push zaštićenog targeta
Git je autoritet za stanje koda; commit nije workflow acceptance
Worktree je izolacija rada, ne Task
Task, Session, Worktree, Report, Review, Finding, Decision ostaju odvojeni pojmovi
Ne uvoditi paralelne ručne current.md / progress.md / decisions.md kao izvore istine
Generisani Current State / Handoff je projekcija, nikada input authority-ja
Ne prikazivati procenat napretka bez objašnjivog pravila
Ne izmišljati atribuciju, status ili completion kada nema dokaza
```

### 2.1 Slojevita arhitektura — posebno pravilo

Ovo je izdvojeno jer v5 uvodi podsisteme kojih u v4.3 nema, a upravo tu se
sloj najlakše probije.

```text
View ne pristupa bazi, Gitu, filesystemu ni subprocessu.
Controller mapira DTO u ViewState; ne sadrži SQL, Git, subprocess ni poslovna pravila.
Services su jedino mjesto gdje živi poslovna logika i pristup persistenciji.
CLI komanda nije prečica do servisa — ide kroz isti Controller sloj.
HTTP ruta ne sadrži ORM upit.
```

Svaki novi podsistem u fazama B i D mora poštovati ovu granicu i mora biti
pokriven guardom.

**Upozorenje:** postojeći `scripts/guard_architecture.py` trenutno ovo ne
pokriva. Ima pet import-based pravila i ne vidi `flowos.gui.composition_root`,
ne vidi pozive (samo importe), i ne vidi stdlib pozive iz View sloja. Vidi
provjere 30b–30e. Zato je proširenje guarda zaseban task u fazi A
(FLOW-1156), a ne usputni posao.

Tri mjesta pod najvećim rizikom, koja v5 mora imenovati:

```text
FLOW-1163  claim registar — ne smije se zvati direktno iz CLI-ja
FLOW-1167  post-merge gate — pokreće ga servis, ne skripta mimo sloja
FLOW-1170  agentska read površina — ruta bez ORM upita, čita kroz servis
```

Postojeći presedan koji ovo ugrožava: svaka nova View akcija trenutno dobija
ad-hoc handler u `composition_root.py` umjesto vlastitog Controllera. Faza C
dodaje najmanje četiri nova ekrana. Bez FLOW-1156 i FLOW-1157 taj obrazac se
umnožava.

Zadržati i §4 (30 granica), §37 (filter Q1–Q5) i §32 (šta se ne gradi) iz
v4.3, sa izmjenama koje su izričito navedene u sekciji 7.

---

## 3. Pravila numeracije

```text
Faze se prestrukturiraju u A, B, C, D, E.
FLOW brojevi postojećih taskova ostaju NEPROMIJENJENI.
Novi taskovi koriste opseg FLOW-1150 .. FLOW-1199.
Nijedan postojeći FLOW broj se ne smije ponovo upotrijebiti za drugi sadržaj.
```

Razlog: 76 izvještaja u `agent_reports/` referiše postojeće brojeve.
Renumeracija bi pokidala te veze.

v5 mora sadržati **tabelu preslikavanja** stara faza → nova faza za svaki
zadržani FLOW broj.

---

## 4. Obavezne provjere u repou

Za svaku stavku: provjeri, pa u izvještaju napiši `POTVRĐENO`,
`OPOVRGNUTO` ili `DJELIMIČNO` sa onim što si stvarno vidio.

### 4.0 Pravila provjere

**Fiksiran commit.** Sve provjere se rade nad jednim commitom. Zabilježi
njegov puni SHA na vrhu izvještaja i navedi ga uz svaki nalaz. Bez toga se
review ne može ponoviti, jer se `HEAD` pomjera. Nalazi u tabelama niže
zabilježeni su nad `b83f197`; ako radiš nad novijim commitom, razlika je
očekivana i navodi se, nije neslaganje.

**Negativni nalazi.** Devet stavki tvrdi da nešto **ne postoji** — nalazi
6, 14, 20, 21, 22, 26, 27, 29 i dio 9. Za njih pretraga koda nije dovoljan
dokaz: indeks pretrage može biti nepotpun, pa odsustvo pogotka nije
odsustvo koda.

Za svaku takvu stavku obavezno:

```text
1. pročitati stablo direktorija rekurzivno, ne osloniti se na pretragu
2. otvoriti konkretne fajlove u kojima bi se tražena stvar nalazila
3. u izvještaju navesti KOJE si fajlove otvorio da bi zaključio da nečega nema
```

Formulacija „pretraga nije vratila rezultate" nije prihvatljiv dokaz
odsustva.

**Pozitivni nalazi.** Za stavke koje tvrde da nešto postoji na određenoj
liniji, navesti fajl, liniju i doslovan isječak koda.

### 4.1 Stanje blokatora

| # | Provjeri | Navodni nalaz |
|---|---|---|
| 1 | Je li FLOW-1109 (redakcija tajni) završen i commitovan | Da — commit `c9c92d8`, re-review verdikt `CLOSED / PASS` |
| 2 | `worktrees/service.py` — prefix poređenje putanja | Linija ~393 sadrži `wt.path == path or wt.path.startswith(path)`; isti obrazac i na ~152 i ~429 |
| 3 | Koje polje GUI šalje na `import-plan`, koje endpoint čita | GUI `composition_root.py:238` šalje `markdown`; endpoint `plan_progress.py:180` čita `markdown_text` → import iz GUI-ja uvijek pada na 400 |
| 4 | Koristi li import endpoint svoj Pydantic model | Ne — prima `body: dict`; `PlanImportRequest(markdown_text)` u `shared/contracts/plan_progress.py:150` je neiskorišten |

### 4.2 Agent-launch semantika

| # | Provjeri | Navodni nalaz |
|---|---|---|
| 5 | Pokreće li `flowos session start` agentski proces | Ne — `cli/app.py:310–342` samo `POST /sessions` |
| 6 | Ima li `AgentProcessLauncher.launch()` produkcijskog pozivaoca | Ne — `claude_code.py:160–220`; jedini pozivalac je `tests/unit/test_agent_adapter.py` |
| 7 | Šta se upisuje kao `pid` sesije | `os.getpid()` — PID CLI procesa, ne agenta |
| 8 | `AdapterCapabilities.can_launch` default | `True` |
| 9 | Jesu li paketi `services/execution`, `jobs`, `approvals`, `usage`, `git`, `infrastructure/process`, `infrastructure/filesystem` prazni | Da — samo `__init__.py` |
| 10 | Docstring `infrastructure/process/__init__.py` | Tvrdi da ga koristi „Wrapper (CLI Service) i Managed Execution" |

### 4.3 Duplirani read-modeli

| # | Provjeri | Navodni nalaz |
|---|---|---|
| 11 | Postoji li `EvidenceService` i po čemu je ključan | `services/evidence.py` — `EvidenceBundle` iz session → commits → changed files → verification → report verdict → conflicts → criteria, ključan po `plan_item_id` |
| 12 | Postoji li `ProjectStateService` | `services/project_state.py` — konsoliduje PlanItem, Session, Conflict, WorkspaceState, Worktree, Verification |
| 13 | Postoje li timeline servisi | `services/project_timeline.py` i `services/sessions/timeline.py` |
| 14 | Postoji li `TaskContract` bilo gdje u kodu | Ne — nema `task_contracts` tabele; `tasks` ima samo `title`, `description`, `status`, `priority`, `plan_item_id` |

### 4.4 Ledger, izvještaji, verdikti

| # | Provjeri | Navodni nalaz |
|---|---|---|
| 15 | Gdje su definisani canonical eventi | `workflow/ledger.py:29,32,35` — IMPLEMENTATION_COMPLETED, TEST_RESULT, REVIEW_COMPLETED; `workflow/decisions.py:30` — TASK_DECISION. Dva odvojena writer-a |
| 16 | Šema YAML front-mattera za izvještaje | `reports/front_matter.py:74–121` — stroga allowlista. Obavezno: `flowos_report_version, report_id, session_id, report_type, tasks, created_at`. Opciono: `work_status, agent, model, commits`. **Nepoznat ključ podiže grešku** |
| 17 | Postoji li strukturisan reviewerov verdikt | Ne — `AgentReport.user_verdict` je čovjekova odluka; reviewerov je slobodan tekst u `independent_review_summary` |
| 18 | Ulazi li agentski izvještaj u FlowOS | Da — `reports/ingestion.py` uvozi `<repo>/agent_reports/*.md` |

### 4.5 Konflikti i koordinacija

| # | Provjeri | Navodni nalaz |
|---|---|---|
| 19 | Šta detektuje `conflicts/service.py` | WRITE_WRITE (10 min), LATE_OVERLAP (30 min), BRANCH_CHANGE, STALE_SESSION, NO_COMMIT — sve detekcija poslije činjenice |
| 20 | Postoji li ikakav claim/rezervacija fajlova | Ne postoji nigdje u repou |
| 21 | Postoji li `coordination.py` ili `agent_sensors.py` | Ne — oni su iz Dentaland projekta |
| 22 | Postoji li MCP surface za FlowOS | Ne. GitNexus MCP se koristi (`CLAUDE.md:593`), FlowOS nema svoj |

### 4.6 GUI

| # | Provjeri | Navodni nalaz |
|---|---|---|
| 23 | Koliko stranica ima GUI i u kojim grupama | 10, u tri grupe (`overview_skeleton.py:205–209`): RAD — Pregled, Plan, Zadaci, Sesije; NADZOR — Agenti, Radna stabla, Konflikti, Izvještaji; SISTEM — Projekti, Postavke |
| 24 | Je li stranica `Zadaci` povezana na backend | Ne — `TasksPage()` instanciran inline na `composition_root.py:490`, referenca se ne čuva, nema `connect`, `render([])` u konstruktoru |
| 25 | Koje stranice imaju stvarno wiring | Pregled, Plan, Sesije, Agenti, Radna stabla, Projekti. Nemaju: Zadaci, Konflikti, Izvještaji, Postavke |
| 26 | Postoji li stranica „Aktivnost" | Ne — `activity_view` je widget na Pregledu |

### 4.7 Sigurnost i granice

| # | Provjeri | Navodni nalaz |
|---|---|---|
| 27 | Koristi li verify subprocess filtriran environment | Ne — `verification/service.py:179` poziva `subprocess.run` bez `env=` |
| 28 | Ubija li timeout stablo procesa | Ne — `subprocess.run(timeout=)` ubija samo direktno dijete; Job Objects paket je prazan |
| 29 | Ima li u `src` `git checkout`/`reset`/`restore` | Ne — worktree servis koristi samo `worktree add/list/remove/prune`, `status`, `branch`, `rev-parse`, `fetch` |
| 30 | Postoji li `guard_architecture.py` i pokreće li se | `scripts/guard_architecture.py`, pokreće se iz `verify.py` |
| **30b** | Koja pravila guard ima i šta ne pokriva | Pet pravila (`:14–29`), sva **import-based**, uparena po prefiksu modula. Ne pokriva: (a) `flowos.gui.composition_root` — ne odgovara nijednom boundary izvoru, guard ga preskače; (b) pozive, samo importe — `self._api._post(...)` je nevidljiv; (c) `subprocess` i drugi stdlib pozivi iz View sloja; (d) `flowos.gui.views` koji importuje `flowos.service.*`; (e) `flowos.cli` — nema nijedno pravilo |
| **30c** | Ista pravila u testu | `tests/architecture/test_boundaries.py` — provjeriti da li ima ista ograničenja |
| **30d** | Koliko Controller klasa GUI stvarno ima | Jedna — `gui/controllers/overview.py`. `composition_root.py` (617 linija) je de facto neslužbeni „God Controller": `_on_import_plan` (`:226–239`) sam čita fajl sa diska, sam gradi request body i zove privatnu `self._api._post`; `GuiApiClient` nema javnu `import_plan()` metodu. Isti obrazac u `_track_agent` |
| **30e** | View koji direktno zove OS proces | `overview_skeleton.py:846–862` — `import subprocess` i `Popen(["explorer", ...])`, putanja hardkodirana relativno na `__file__` |

### 4.8 Atribucija

| # | Provjeri | Navodni nalaz |
|---|---|---|
| 31 | Koje nivoe vraća `attribution/service.py` | `WORKTREE`, `SOLE_ACTIVE`, `HINT`, `UNATTRIBUTED`, `USER` uz `confidence` `HIGH/MEDIUM/LOW` |
| 32 | Gdje se u v4.3 uvodi D4 taksonomija (DIRECT/ISOLATED/HEURISTIC/UNKNOWN) | Tek u FLOW-1902, faza 19 (P2) |

### 4.9 Prenosivost

| # | Provjeri | Navodni nalaz |
|---|---|---|
| 33 | Ima li single-instance lock ne-Windows granu | Da — `runtime.py:88–110`, Windows named mutex i `fcntl.flock` |
| 34 | Šta radi `dir_security.py` van Windowsa | Samo `mkdir`, bez ikakve restrikcije dozvola (`:166–182`) — a runtime descriptor nosi API bearer token |
| 35 | Windows-only mjesta | `app_paths.py` (`%LOCALAPPDATA%`, 8 direktorija), `agent_scanner.py:18` (`tasklist`), `overview_skeleton.py:862` (`explorer`), `pages.py:310` (hardkodiran tekst putanje), `cli/app.py:74–132` (`.exe`, `tasklist`, `_find_exe`) |
| 36 | Je li `pywin32` uslovna zavisnost | Da — `pyproject.toml:35`, `sys_platform == 'win32'` |
| 37 | Koliko testova ima platform skip | Jedan fajl — `tests/unit/test_dir_security.py` |

### 4.10 Dokumentacija

| # | Provjeri | Navodni nalaz |
|---|---|---|
| 38 | Šta CLAUDE.md, AGENTS.md i README propisuju | „Wrapper kao kičma", `flowos session start` kao primarni tok, obavezan redoslijed adaptera Claude Code → pi → Codex → GenericCliAdapter, `can_launch` u capability ugovoru, faze 6–9 kao Managed Execution / Durable Job Engine / implementator+verifier — sve ukinuto u v4.3 |

---

## 5. Nova struktura faza

v4.3 je organizovan po fazama 12–24 naslijeđenim iz starijih planova. v5 se
organizuje po jezgru iz `AGENTIC_WORKFLOW_BLUEPRINT.md` §18.6, koje kaže:

> NE preskakati sekcije 4, 6, 7, 8, 13, 14 — ovo je jezgro sistema, sve
> ostalo je pojačanje jezgra.

Od tih šest, tri (§4 Task Contract, §8 review verdict, §14 post-merge gate)
u v4.3 ne postoje u P0 ili ne postoje uopšte. Nova struktura to ispravlja.

```text
FAZA A — Ugovori i blokatori
   cilj: ništa se ne može mehanički provjeriti dok ovo ne stoji

FAZA B — Blueprint jezgro
   cilj: FlowOS izvršava tok iz blueprinta, ne samo bilježi

FAZA C — Čovjekova radna površina
   cilj: Milestone 1 — jedan Task razumljiv i dokaziv kroz LIVE FlowOS

FAZA D — Agentska površina
   cilj: Milestone 2 — agent čita isto stanje, deterministički

FAZA E — Uslovljeno proširenje
   cilj: samo po dokazanoj potrebi
```

### Faza A — Ugovori i blokatori

| FLOW | Sadržaj | Size |
|---|---|---|
| ~~1109~~ | **UKLONITI** — završen, commit `c9c92d8` | — |
| 1110 | Siguran worktree identitet. Proširiti na linije 152 i 429. **Napisati sa dvije path semantike od početka** (case-sensitive / case-insensitive), ne kao naknadni port | L |
| 1105 | Plan Import contract. Dodati: endpoint mora koristiti `PlanImportRequest`, ne `body: dict`. **Dodati i GUI stranu** — `GuiApiClient` dobija javnu `import_plan()` metodu; `_on_import_plan` prestaje sam čitati fajl, graditi dict i zvati privatnu `_post`. Bug postoji upravo zato što nema jedne testirane metode za import. **Postojeći test zaključava bug:** `tests/gui/test_plan_import_flow.py:37` tvrdi `{"markdown": ...}` i prolazi jer provjerava GUI naspram lažnog API-ja, ne naspram ugovora endpointa — kanonski primjer iz blueprint §9. Popravka mora obuhvatiti i taj test, uz adversarni dokaz | M |
| 1106 | Stvarni uvoz dogfooding plana | S |
| 1111 | Passive Session Contract. Proširiti na: `can_launch` default, `kill_process_tree`, `pid=os.getpid()`, brisanje praznih paketa, docstring `process/__init__.py`, odluka o sudbini `get_command`/`get_environment` u adapterima. **Preveličan u v4.3 — realno S** | S |
| 1112 | Evidence Semantics Contract. Dodati tri otvorena pitanja: (a) šta je `MECHANICAL_EVIDENCE` — šesta klasa ili alias, (b) perzistuju li se klase kao kolone ili se izvode iz izvora, (c) mapiranje postojećih attribution nivoa. **Ako se perzistuju kolone, nije S** | M |
| **1150** | **NOVO** — Report front-matter v2: dodati `risk`, `implementer`, `reviewers`; strukturisan reviewerov verdikt (`verdict/scope/acceptance/architecture/security/blocking_findings`) po blueprint §8. Bez ovoga nezavisnost reviewa nije mehanički provjerljiva | M |
| **1151** | **NOVO** — Filtriran environment za FlowOS-owned subprocess | S |
| **1152** | **NOVO** — Timeout ubija stablo procesa, ne samo direktno dijete | M |
| **1153** | **NOVO** — Linux iz izvornog koda: `app_paths` XDG, `agent_scanner` psutil, `dir_security` POSIX grana (`chmod 0o700`, provjera vlasništva, fail-closed) | M |
| **1154** | **NOVO** — CI matrica: dodati `ubuntu-latest` uz Windows | S |
| **1155** | **NOVO** — Sinhronizacija CLAUDE.md, AGENTS.md, README sa v5 | S |
| **1156** | **NOVO** — Proširenje architecture guarda. Pokriti `flowos.gui.composition_root` i `flowos.cli` kao boundary izvore; dodati pravilo protiv poziva OS procesa iz View sloja; zabraniti pozivanje privatnih metoda servisnog klijenta iz View/composition sloja. Ista pravila u `tests/architecture/test_boundaries.py`. **Guard koji ne prijavi tri postojeća poznata prekršaja (`_on_import_plan`, `_track_agent`, `explorer` Popen) nije prihvaćen** — replay validacija po blueprint §17 | M |
| **1157** | **NOVO** — Izvući iz `composition_root.py` četiri handlera koji nose poslovnu logiku (`_on_import_plan`, `_track_agent`, `_on_prepare_ready`, `_on_shutdown_requested`) u prave Controllere. `GuiApiClient` dobija javne metode umjesto poziva privatne `_post`. **Ne dirati preostalih 14 handlera** — oni su čisto mapiranje DTO → view i prepravljaju se u fazi C kad se ekrani ionako diraju. `overview_skeleton.py:846–862` — otvaranje foldera ide kroz Controller → Service, bez `subprocess` u View sloju | M |
| 1305 | **Premješteno ovamo iz faze 13.** Regression Proof je procesno pravilo, ne GUI task, i već važi za FLOW-1157. **Zamijeniti „gdje je praktično" tvrdim pravilom:** obavezno za svaki bugfix i svaku promjenu puta izvršavanja; opciono za novu funkcionalnost. Uskladiti sa blueprint §9 (TEST-ADVERSARIAL, 7 koraka). Blueprint §9 uzima baš prekršaj sloja kao kanonski primjer (`View poziva Service direktno` → `View poziva Service kroz Controller`) | M |

**Redoslijed 1157 → 1156 je obavezan.** Guard ne može proći dok prekršaji
stoje, a allowlist da bi guard bio zelen je po blueprint §17 gaming senzora —
ozbiljniji problem od samog prekršaja.

**Gate A:**

```text
[ ] 1110 accepted, oba path ponašanja pokrivena testom
[ ] PlanImport radi end-to-end kroz GUI
[ ] dogfood plan je aktivan
[ ] agent-launch semantika uklonjena iz koda i dokumentacije
[ ] evidence taxonomy zaključana
[ ] front-matter v2 prihvata risk/implementer/reviewers i strukturisan verdikt
[ ] verify subprocess ima filtriran env i ubija stablo
[ ] CI zelen na Windows i Linux
[ ] guard prijavljuje sva tri poznata prekršaja sloja na starom kodu i
    nijedan na ispravljenom (replay validacija)
[ ] composition_root.py je wiring root, ne handler za poslovnu logiku
[ ] CLAUDE.md/AGENTS.md/README ne propisuju ukinutu arhitekturu
```

### Faza B — Blueprint jezgro

Ovo je faza koje v4.3 nema. Izvor je blueprint §4, §5, §6, §8, §10, §14.

| FLOW | Sadržaj | Blueprint | Size |
|---|---|---|---|
| **1160** | Task Contract v1 — model i persistencija: `goal`, `risk`, `scope`, `out_of_scope`, `allowed_paths`, `forbidden_paths`, `acceptance`, `implementer`, `reviewers`, `verification_commands` | §4 | M |
| **1161** | Uloge kao prvorazredni pojam. `agent_type` je alat, uloga je odvojena. Mehanička provjera implementer ≠ reviewer | §1 | M |
| **1162** | Risk tier kao gate — LOW/MEDIUM/HIGH određuje obavezan broj nezavisnih reviewera | §2 | S |
| **1163** | File-claim registar: `claim` / `status` / `release` / `check`. Registar je u FlowOS bazi (jedan servis, jedna baza, dostupan iz svakog worktreeja). Putanje normalizovane relativno na korijen worktreeja | §5 | M |
| **1164** | Presjek `allowed_paths` prije dodjele — deterministička provjera može li dva Taska ići paralelno | §10 | S |
| **1165** | Detekcija zastarjelog claima: Task mergovan, claim još aktivan | §5 | S |
| **1166** | Provjera da je zavisni Task stvarno u `main` prije branchanja — ne samo da postoji kao grana | §6 | S |
| **1167** | Post-merge integration gate — obavezan korak poslije svakog mergea u glavnu granu, na glavnoj grani | §14 | M |
| 1505 | Velocity calibration — **premješteno ovdje sa kraja P0**. D5 traži mjerenje poslije prvih 5–10 taskova; A+B daje taj uzorak | — | S |

**Gate B:**

```text
[ ] Task Contract postoji kao model, ne kao markdown konvencija
[ ] claim se ne može uzeti nad fajlom koji drži drugi aktivan Task
[ ] presjek allowed_paths odbija paralelnu dodjelu kad postoji preklapanje
[ ] zastarjeli claim je vidljiv, ne otkriva se tek kad blokira rad
[ ] post-merge gate je zabilježen kao događaj, ne kao usmena praksa
[ ] Task sa risk=HIGH ne prelazi u ACCEPTED bez dva nezavisna reviewera
[ ] velocity uzorak postoji za najmanje 5 stvarnih Taskova
```

### Faza C — Čovjekova radna površina

**Ova faza je bitno smanjena u odnosu na v4.3.** Razlog je preciziranje
stvarne potrebe korisnika, koje mijenja centralni objekat ekrana.

#### C.0 Šta je stvarni problem

v4.3 gradi FLOW-1204 Task Detail `[L]` — dubok pogled na **jedan** Task, sa
devet pitanja u prvih deset sekundi. To je ekran u koji se ulazi kad se već
zna koji Task je zanimljiv.

Stvarna potreba je obrnuta: plitak pogled preko **svih** aktivnih Taskova.
Korisnik već zna ko šta radi jer je sam dodijelio zadatke. Ono što ne zna je
gdje je svaki od njih **sada**, i mora to provjeravati prelazeći između VS
Code prozora i terminala. Zadaci nisu jednako složeni i ne traju jednako, pa
je glavni trošak neizvjesnost kada je nešto završeno ili stalo.

Centralni objekat faze C je zato **tabla**, ne Task Detail. Tabla se ne
dobija besplatno iz Task Detaila — to je druga primitiva iz istih podataka.

#### C.1 Oblik ekrana

Jedan ekran, red po Tasku, pet kolona:

```text
Task        Ko radi   Gdje je         Zadnji signal    Čeka
FLOW-1157   Codex     IMPLEMENTED     commit, 6 min    review
FLOW-1105   Pi        u radu          fajl, 2 min      —
FLOW-1110   Crush     —               tišina 3h        ?
FLOW-1112   Claude    VERIFIED        review, 20 min   tebe
```

Klik na red otvara dokaz (izvještaj, diff, verify output). Ne otvara ekran sa
devet sekcija.

#### C.2 Dvije vrste signala se moraju razlikovati vizuelno

Ovo je D6 primijenjen konkretno, i v5 to mora eksplicitno propisati:

```text
MEHANIČKI SIGNAL — ne traži saradnju agenta, FlowOS ih već skuplja
  watcher: izmjena fajla u worktreeju
  git polling: commit na grani
  agent_scanner: proces još živ
  → klasa SOURCE_FACT

WORKFLOW STANJE — postoji samo ako je agent napisao izvještaj
  IMPLEMENTATION_COMPLETED, TEST_RESULT, REVIEW_COMPLETED, TASK_DECISION
  → klasa CLAIM (osim TASK_DECISION, koji je USER_DECISION)
```

Tabla nije senzor završetka. Ako agent završi a ne napiše izvještaj, kolona
„Gdje je" ostaje prazna dok „Zadnji signal" pokazuje aktivnost. **Taj
nesklad se prikazuje kao rupa, ne kao „u radu".**

#### C.3 Taskovi

| FLOW | Sadržaj |
|---|---|
| 1201 | Minimalni izbor i registracija projekta. Bez izmjene |
| 1202 | Stranica Zadaci na stvarni backend. **Ovo jeste tabla** — ne zasebna lista pored table. Polazna tačka je nalaz 24 |
| 1203 | Read-model, ali sveden na nivo table (red po Tasku), ne na nivo jednog Taska. `TaskContract` postoji iz 1160. Mora **proširiti** `EvidenceService`, ne graditi drugu projekciju |
| 1301 | Ujedinjen workflow read-model. Dodati: canonical eventi dolaze iz dva writer-a (`ledger.py` i `decisions.py`) |
| 1303 | Otvaranje stvarnih dokaza — ono što se dešava na klik na red |
| **1180** | **NOVO** — Detekcija tišine. Task bez ijednog signala (fajl, commit, izvještaj) duže od praga. Deterministički izračunljivo, bez heuristike o vlasništvu. **Ovo je najkorisnija kolona i nema je u v4.3** |
| **1181** | **NOVO** — Kolona „čeka na mene". Task koji ima verifikaciju i review a nema `TASK_DECISION` je red za korisnika. Čist upit nad ledgerom |
| 1401 | TASK_DECISION kontrole — jer „čeka tebe" bez dugmeta nije korisno |
| 1402 | Backend-confirmed consequence — reload canonical stanja poslije odluke |
| 1403 | Kompletan dogfooding tok kroz LIVE FlowOS |

#### C.4 Odgođeno iz v4.3 faze 12–15

Ne brisati iz plana — premjestiti u fazu E sa oznakom `ODGOĐENO`, uz razlog:

```text
FLOW-1200  GUI primitivi — izvlače se kad postoji drugi ekran, ne prije
FLOW-1204  Task Detail kako je dizajniran — tabla pokriva stvarnu potrebu
FLOW-1302  Workflow History kao zaseban ekran
FLOW-1304  Workflow History ≠ Technical Activity — bez 1302 nema šta razdvajati
FLOW-1404  SessionTaskBinding historical proof
FLOW-1501  Zabilježiti UX probleme
FLOW-1502  Čišćenje navigacije — tabla ne traži reorganizaciju svih 10 stranica
FLOW-1503  MOCK/live nejasnoće
FLOW-1504  Zamrznuti dogfood baseline
```

Sedamnaest taskova postaje deset.

#### C.5 Gate C = Milestone 1

```text
[ ] jedan ekran pokazuje sve aktivne Taskove, red po Tasku
[ ] mehanički signal i workflow stanje su vizuelno razdvojeni
[ ] Task koji je utihnuo je vidljiv bez traženja
[ ] Task koji čeka korisnikovu odluku je vidljiv bez traženja
[ ] odluka se donosi sa tog ekrana i canonical stanje se ponovo učita
[ ] Task čiji agent ne piše izvještaje prikazan je kao rupa, ne kao „u radu"
[ ] cijeli tok prošao nad najmanje jednim stvarnim dogfooding Taskom
```

**Šta Milestone 1 ne rješava, i v5 to mora reći otvoreno:** rad se i dalje
dešava u VS Code i terminalu. Nestaje *provjeravanje*, ne rad.

### Faza D — Agentska površina

Nova faza. Osnova: agenti su prvorazredni čitaoci FlowOS stanja, po uzoru na
GitNexus MCP koji već koriste.

| FLOW | Sadržaj | Size |
|---|---|---|
| **1170** | Read-only pristup canonical stanju za agente (MCP ili read-only lokalni API). FlowOS odgovara na upit, ne inicira ništa | L |
| **1171** | Svaki odgovor nosi semantičku klasu iz 1112 i provenance | M |
| **1172** | Formalizovati postojeći pisani smjer (`reports/ingestion.py`) kao dio ugovora, ne kao slučajnu konvenciju | S |
| 1905 | **Premješteno iz P2.** Stale evidence detection. Agent koji pročita zastarjeli `verified` je gori nego agent bez FlowOS-a — ovo postaje preduslov, ne dodatak | L |
| 1604, 1605 | Handoff State i rendereri — pomjereni ovdje jer su prirodni izlaz agentske površine | M, S |

**Granica koju v5 mora eksplicitno zapisati:**

```text
FlowOS ne inicira. Agent povlači.
FlowOS ne sažima kontekst da stane u token budžet — projekcija je
deterministička (filtriranje, sortiranje, odsijecanje po pravilu).
Sažimanje je LLM na mala vrata i zabranjeno je.
```

**Gate D = Milestone 2.**

### Faza E — Uslovljeno proširenje

Sve niže ostaje iz v4.3 sa navedenim izmjenama, ali bez obećanog redoslijeda —
pokreće se samo po dokazanoj potrebi.

| Grupa | Izmjena |
|---|---|
| **Odgođeno iz faze C** | 1200, 1204, 1302, 1304, 1404, 1501, 1502, 1503, 1504 — nose oznaku `ODGOĐENO` sa razlogom iz C.4. Ne brisati; preispitati poslije Milestone 1, na osnovu stvarnog korištenja table |
| 1601–1603, 1606 | Current State / Attention. Dodati: mora **proširiti** `ProjectStateService`, ne duplirati ga. 1603 mora imati pravilo za slučaj kad Task ispunjava više prioritetnih uslova |
| 1701–1706 | Findings. Dodati `category` kao **kontrolisan enum** — bez toga FLOW-2004 ne može raditi |
| 1801–1805 | Task Contract v2. Preimenovati u „proširenje", jer v1 sada dolazi iz 1160 |
| 1901–1904 | Observability. 1902 uvodi D4 taksonomiju — do tada u kodu žive dvije semantike atribucije; v5 to mora eksplicitno priznati ili riješiti ranije u 1112 |
| 2001–2005 | Guardovi. **Dodati obavezan uslov iz blueprint §17:** replay validacija protiv poznate istorije prije ulaska u CI — senzor mora naći tačno poznate prošle prekršaje, ni manje ni više. 2003 mora registrovati postojeći `guard_architecture.py`, ne izmišljati novi mehanizam. Zabilježiti da blueprint §17 označava senzore kao **nedokazanu praksu** |
| 2100–2104 | Conflict intelligence. Dodati: postojeći `conflicts/service.py` već detektuje pet tipova poslije činjenice i njegova GUI stranica nije povezana. 2100 mora zapisati postojeće iskustvo sa GitNexusom, ne otvarati istraživanje. Definisati minimalni oblik rezultata `DependencyEvidenceProvider` — bez toga 2103 nema kriterijum za odgodu |
| 2201–2203 | Readiness. Zabilježiti da je 2201 skoro identičan blueprint §3 bootstrap checklisti |
| 2301–2303, Faza 24 | Bez izmjene |

---

## 6. Nove sekcije koje v5 mora sadržati

### 6.1 Tri sloja provođenja

v4.3 ima slogan „FlowOS ne izvršava metod umjesto čovjeka" bez konkretne
granice. v5 mora imati tabelu:

```text
MEHANIČKI PROVODIVO — FlowOS može odbiti ili blokirati
  file-claim registar
  presjek allowed_paths
  implementer ≠ reviewer
  broj reviewera po risk tieru
  post-merge gate kao obavezan korak
  zavisni Task je stvarno u main
  claim oslobođen prije zatvaranja Taska
  Task Contract postoji prije prvog commita

SAMO BILJEŽIVO — FlowOS vidi da postoji, ne ocjenjuje kvalitet
  dubina reviewa
  kvalitet Task Contracta
  je li adversarni dokaz dokazao pravu stvar
  je li OUT_OF_SCOPE_FINDING ispravno klasifikovan

OSTAJE U DOKUMENTU — FlowOS ne pokušava
  fresh reviewer eskalacija (blueprint §11)
  redizajn kontrakta da preklapanje nestane (§10)
  čišćenje state dokumenta (§15)
```

### 6.2 Postojeći kod — šta se proširuje, šta zamjenjuje

Obavezna tabela. Za svaki postojeći servis navesti odluku:

```text
services/evidence.py            → proširuje se u FLOW-1203 (Task-ključan)
services/project_state.py       → proširuje se u FLOW-1602
services/project_timeline.py    → odluka u FLOW-1302
services/sessions/timeline.py   → odluka u FLOW-1302
services/conflicts/service.py   → zadržava se, GUI se povezuje
services/reports/ingestion.py   → zadržava se, ugovor formalizovan u FLOW-1172
scripts/guard_architecture.py   → registruje se kao prvi guard u FLOW-2003
services/attribution/service.py → mapiranje u FLOW-1112, taksonomija u FLOW-1902
```

Bez ove tabele v5 ponovo projektuje tri postojeća read-modela pod novim
brojevima, što krši §4 tačku 25.

### 6.3 Prenosivost kao poprečno pravilo

Ne faza, nego pravilo koje važi za svaki task:

```text
Ne dodavati novi Windows-only kod.
Svaka putanja ide kroz app_paths.
Svaki subprocess ide kroz jedan wrapper.
Nijedan novi direktan os.environ ili platform poziv.

Primarna platforma: Windows 10/11
Podržano iz izvornog koda: Linux (potvrđen korisnik na Fedora 44)
Otvoreno: macOS — samo ako se pojavi stvaran korisnik

Fedora 44 napomene:
  python3 je 3.14; repozitorij ima i 3.12/3.13 → venv na 3.12 ili 3.13
  GDM je Wayland-only → Qt smoke test prije svega ostalog
  fajlsistem je case-sensitive → vidi FLOW-1110
```

### 6.4 Preslikavanje blueprint sekcija

Tabela: svaka sekcija blueprinta → FLOW broj koji je pokriva → sloj
provođenja iz 6.1 → faza. Sekcije bez pokrića navesti eksplicitno kao
nepokrivene, ne prećutati.

---

## 7. Izmjene u zadržanim sekcijama v4.3

| Sekcija v4.3 | Izmjena |
|---|---|
| §0 | Ispraviti lanac izvođenja — v4.2 nije u repou |
| §3 D3 | Riješiti kontradikciju redoslijeda 1200/1204 |
| §3 D4 | Dodati da postojeći kod ima drugu taksonomiju i kada se mapira |
| §3 D5 | Uskladiti sa premještanjem 1505 u fazu B |
| §3 D6 | Riješiti status `MECHANICAL_EVIDENCE` |
| §4 | Zadržati 30 granica. **Preformulisati tačku 18** iz „ne šalje prompt agentu" u „FlowOS ne inicira komunikaciju sa agentom; agent povlači podatke" — inače faza D formalno krši granicu koju ne krši suštinski |
| §26 | **Preimenovati.** Nije „non-regression contract" jer 26.2 i 26.3 opisuju stvari koje nikad nisu implementirane. Razdvojiti na „potvrđeno stanje" (26.1, 26.4, 26.5) i „obaveze sa FLOW brojem" (26.2 → 1152, 26.3 → 1151) |
| §29 | Prepraviti sizing mapu prema novoj strukturi |
| §31 | Zamijeniti P0–P3 fazama A–E |
| §32 | Zadržati. **Dodati:** „sažimanje konteksta LLM-om radi token budžeta" |
| §36 | Prepraviti mapu prema A–E |
| §37 | Zadržati Q1–Q5 nepromijenjeno |

---

## 8. Šta ostaje nepromijenjeno

Ne prepisivati, ne „poboljšavati", ne skraćivati:

```text
§1 North Star
§2 Granica proizvoda (dijagram)
§5 Dvije ose: proizvod i metod
§6 Program Design i Locked Contract
§22 GUI north star
§23 „Gdje si stao"
§24 Context pravila
§25 docs/external/
§27 Standardni acceptance gate
§28 Commit / integration gate
§30 Metrike
§33 Test matrica
§34 Razvojni ritam
§35 Milestones
§38 Konačna preporuka
```

---

## 9. Isporuka

Dva artefakta:

```text
docs/FlowOS-plan-razvoja-v5-<datum>.md
agent_reports/<YYYY-MM-DD>-FLOW-DOC-001-chatgpt-v5-izrada.md
```

Izvještaj nosi YAML front-matter po `reports/front_matter.py` šemi
(`flowos_report_version: 1`, `report_id`, `session_id`, `report_type:
implementation`, `work_status`, `tasks: [FLOW-DOC-001]`, `created_at`).
Ako parser odbije neki ključ, to je nalaz za FLOW-1150, ne razlog da se
front-matter izostavi.

Način isporuke, po redoslijedu poželjnosti:

```text
1. PR na granu task/FLOW-DOC-001-plan-v5 — ako imaš write pristup
2. dva fajla kao tekst u odgovoru — korisnik commituje
```

U oba slučaja:

- ne mijenjati nijedan drugi fajl u repou;
- ne mergovati ništa u `main`;
- ne zatvarati ni otvarati issues;
- ne pokretati ni rerunovati GitHub Actions jobove osim ako korisnik
  eksplicitno zatraži.

Ako otvaraš PR, opis PR-a sadrži samo rezime i link na izvještaj — nalazi
idu u izvještaj, ne u opis PR-a.

---

## 10. Acceptance

v5 je prihvatljiv kada:

```text
[ ] izvještaj navodi puni SHA commita nad kojim su rađene sve provjere
[ ] svaka stavka iz sekcije 4 ima zapisan ishod POTVRĐENO/OPOVRGNUTO/DJELIMIČNO
    sa navedenim fajlom i linijom
[ ] za svaki negativan nalaz navedeno je koji su fajlovi otvoreni da bi se
    zaključilo odsustvo — ne samo da pretraga nije vratila rezultat
[ ] svaki novi task u fazama B i D navodi kroz koji sloj prolazi i je li
    pokriven guard_architecture.py; gdje nije, proširenje guarda je dio tog taska
[ ] isporučena su oba artefakta iz sekcije 9, i nijedan drugi fajl nije mijenjan
[ ] svaka izmjena iz sekcija 5–7 je primijenjena i pronalaziva u v5
[ ] nijedna sekcija iz sekcije 8 nije mijenjana
[ ] nijedna stavka iz sekcije 2 nije oslabljena
[ ] tabela preslikavanja stara faza → nova faza pokriva svaki zadržani FLOW broj
[ ] nijedan FLOW broj nije ponovo upotrijebljen za drugi sadržaj
[ ] svaka faza ima gate — uključujući C, koji ga u v4.3 nema
[ ] sekcije 6.1, 6.2, 6.3, 6.4 postoje u v5
[ ] svaki task ima size S/M/L; nijedan XL nije ostavljen za direktnu implementaciju
[ ] izvještaj o radu postoji kao zaseban fajl u agent_reports/
```

Izvještaj mora sadržati: ishod svake provjere iz sekcije 4, spisak neslaganja
sa ovim spec-om, i spisak svega što je u v5 promijenjeno a nije traženo ovdje
(sa obrazloženjem po stavci).

---

## 11. Zabranjeno

```text
Tvrditi da je nešto provjereno bez navođenja fajla i linije.
Zaključiti da nešto ne postoji samo zato što pretraga nije vratila rezultat.
Mijenjati bilo koji fajl u repou osim dva artefakta iz sekcije 9.
Mergovati u main, zatvarati issues ili pokretati Actions bez zahtjeva.
Tiho ispravljati nalaz iz sekcije 4 koji se ne poklapa sa stvarnim stanjem —
  neslaganje ide u izvještaj.
Uvoditi nove faze, taskove ili koncepte koji nisu u ovom spec-u.
Mijenjati sekcije navedene u sekciji 8.
Slabiti bilo šta iz sekcije 2.
Popunjavati praznine uvjerljivim tekstom umjesto oznakom OTVORENO.
Kopirati ovaj spec u v5.
Renumerisati postojeće FLOW brojeve.
```

Gdje odgovor nije poznat iz repoa ili ulaznih dokumenata, napisati
`OTVORENO — potrebna odluka korisnika` i navesti tačno šta se odlučuje.
