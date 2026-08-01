# FlowOS — kompletan plan realizacije

**Datum:** 20. juli 2026.
**Status:** Plan realizacije, kompletan opseg
**Namjena:** FlowOS kao lični operativni sistem: koordinacija paralelnih agentskih sesija (Claude Code, Codex, pi), zatim samostalno pokretanje agenata, observability, trajno izvršavanje i multiagentski tokovi. Jedan dokument, cijeli put, redoslijedom kojim se gradi.

---

## 1. Sažetak

FlowOS se gradi u deset faza, od kojih prve četiri daju sistem koji se koristi svaki dan (≈ 4–5 sedmica), a ostale ga nadograđuju modulima čiji je redoslijed fiksan, a početak svakog uslovljen dokazanom vrijednošću prethodnog:

```text
Faza 0   Validacija workflowa                    2–3 dana
Faza 1   Temelj: baza, API, mini Task            1 sedmica
Faza 2   CLI wrapper + watcher + Aktivne sesije  1–2 sedmice   ← dnevna upotreba
Faza 3   Konflikti, timeline, reporti, verify    1 sedmica
Faza 4   Worktree tok                            1 sedmica
─────── prva korisna verzija ──────────────────────────────────
Faza 5   Core proširenje (Inbox/Danas/Review)    2–3 sedmice
Faza 6   Managed Execution                       3–4 sedmice
Faza 7   Observability i evaluacija              2 sedmice
Faza 8   Durable Job Engine                      3–5 sedmica
Faza 9   Multiagent: implementator + verifier    2–3 sedmice
Faza 10  Distribucija i jača izolacija           samo po potrebi
```

Dvije odluke definišu cijeli plan i razlikuju ga od prethodnih verzija:

1. **Detekcija umjesto deklaracije.** Izvor istine o agentskoj aktivnosti su posmatrani događaji (filesystem watcher + Git), ne ručno deklarisani ownership globovi. Deklaracija postoji samo kao opcioni hint za atribuciju.
2. **Wrapper je kičma.** Sesija se registruje automatski jer je pokrenuta kroz `flowos session start`. Sve što zavisi od discipline ručnog unosa metapodataka je izbačeno, jer takav unos ne preživljava sedmicu stvarne upotrebe.

---

## 2. Problem koji se rješava

Stvarni tok rada danas:

```text
VS Code nad jednim projektom
├── Claude Code sesija
├── Codex sesija
├── pi agent (terminal 1, model A)
├── pi agent (terminal 2, model B)
└── ručne komande, testovi i korisničke izmjene
```

Više agenata radi paralelno, ponekad u istom Git working treeju. FlowOS mora, bez obilaska terminala, odgovoriti na sedam pitanja:

1. Koji agent trenutno radi?
2. Na kojem projektu i zadatku?
3. U kojem direktoriju, branchu ili worktreeju?
4. Koje fajlove **stvarno mijenja** (ne: namjerava mijenjati)?
5. Preklapa li se s radom drugog agenta?
6. Šta je promijenio i provjerio?
7. Gdje je stao i šta korisnik treba odlučiti?

Kasnije faze proširuju odgovore: faza 6 dodaje "pokreni i kontroliši agenta iz FlowOS-a", faza 7 "koliko košta i koji model je najbolji za koju vrstu posla", faza 8 "posao preživljava pad i restart", faza 9 "nezavisni pregled prije prihvatanja".

---

## 3. Principi

**3.1 Detekcija > deklaracija.** Agent ne zna unaprijed koje će fajlove dirati; deklarisani globovi su ili preuski (lažna upozorenja) ili preširoki (beskorisni). Konflikt-detekcija se gradi nad posmatranim upisima.

**3.2 Registracija je nusprodukt rada.** Nijedan korak toka ne smije tražiti održavanje metapodataka kao poseban posao. Wrapper registruje, snima i zatvara sesiju sam.

**3.3 Git je autoritet za kod.** FlowOS čuva namjeru, sesije, događaje i izvještaje. Dokaz promjene je commit, diff i `git status` — ne FlowOS zapis. Commit je ujedno i checkpoint (§14).

**3.4 Prava atribucija zahtijeva izolaciju.** U dijeljenom treeju atribucija promjene sesiji je vremenska heuristika i tako se prikazuje. Pouzdana atribucija postoji samo uz worktree po sesiji.

**3.5 Model ne potvrđuje sam svoj rezultat.** Rezultat je prihvaćen kada prođu determinističke provjere (testovi, lint, build) i, za rizičnije promjene, nezavisni review (faza 9). Verifikacija proizvodi dokaze, ne uvjeravanje.

**3.6 Prompt nije sigurnosna granica.** Dozvoljene putanje, komande, tajne i vanjske akcije kontrolišu se kodom i OS mehanizmima (allowlist, filtriran environment, Job Object), ne instrukcijama modelu.

**3.7 Svaka složenost mora opravdati postojanje mjerenjem.** Lease protokol, distribuirani workeri, PostgreSQL, container sandbox i slično se ne grade dok mjerenje iz stvarne upotrebe ne pokaže konkretan, ponovljen problem koji jednostavniji mehanizam ne rješava. Za svaku izbačenu stavku definisan je uslov povratka (§21).

**3.8 Dnevna upotreba od druge sedmice.** Plan je uspio ako se FlowOS koristi svakodnevno prije kraja prvog mjeseca; propao je ako se prvi mjesec gradi infrastruktura bez upotrebe. Svaka faza završava vertikalnim tokom koji se odmah koristi.

**3.9 Modularni monolit.** Jedan Python backend proces; moduli sa vlastitim tabelama i ugovorima. Core ne zavisi od izvršnih modula; nijedan modul ne poznaje konkretan agentski alat — to znaju samo adapteri.

---

## 4. Arhitektura

```text
Electron/React GUI
        ↓
FlowOS API (FastAPI, lokalni servis)
        ↓
┌──────────────────────────────────────────────────────────┐
│ FlowOS Core                                              │
│ Projects │ Tasks │ Decisions │ Reports │ (od faze 5:     │
│ Inbox │ Danas │ Review │ Task Contract)                  │
└──────────────────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────────────────┐
│ Session Coordination                                     │
│ Session Registry │ Activity Watcher │ Git Snapshots      │
│ Conflict Rules │ Timeline │ Attribution                  │
└──────────────────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────────────────┐
│ flowos CLI wrapper (kičma)                               │
│ session start/end │ worktree │ report                    │
└──────────────────────────────────────────────────────────┘
        ↓ opcioni moduli (isti proces, jasne granice)
┌────────────────┐ ┌────────────────┐ ┌───────────────────┐
│ Managed        │ │ Observability  │ │ Durable Job       │
│ Execution (F6) │ │ & Eval (F7)    │ │ Engine (F8)       │
└────────────────┘ └────────────────┘ └───────────────────┘
        ↓
┌──────────────────────────────────────────────────────────┐
│ Agent adapteri (capability-based)                        │
│ ClaudeCode │ Pi │ Codex │ GenericCli │ Manual            │
└──────────────────────────────────────────────────────────┘
        ↓
Terminali │ CLI procesi │ Git repoi i worktreeji │ sandbox
```

Zavisnosti: `Managed/Durable/Observability → Core i Session ugovori`. Zabranjeno: `Core → bilo koji adapter`. Backend radi kao stalni lokalni servis (system tray) jer watcher mora raditi i kad je GUI zatvoren.

Tehnologije: Python 3.12 + FastAPI, SQLite (WAL), watchdog, Electron/React GUI, PowerShell/Python CLI. Windows je primarna platforma; supervizija procesa preko Job Objects.

---

## 5. Režimi sesije

| Režim | Ko pokreće | FlowOS zna | Kontrole |
|---|---|---|---|
| `WRAPPED_TERMINAL` | korisnik, kroz `flowos session start` | PID, cwd, Git start/end snapshot, fs aktivnost, exit code | evidencija, timeline, report draft |
| `EXTERNAL_TRACKED` | korisnik direktno; ručna registracija | ručni unos + fs/Git detekcija na nivou repoa | samo evidencija; GUI jasno prikazuje ograničenja |
| `MANAGED` | FlowOS kroz adapter (faza 6) | sve iz WRAPPED + strukturirani rezultat | timeout, soft/hard cancel, allowlist, approval |
| `DURABLE` | Durable Job Engine (faza 8) | sve iz MANAGED + koraci, attempti, recovery | retry, resume, startup recovery, budžeti |

`WRAPPED_TERMINAL` je primarni režim od prvog dana. `EXTERNAL_TRACKED` postoji da sistem ne bude sve-ili-ništa; heartbeat se za njega ne glumi — prikazuje se `last_activity` izveden iz fs/Git događaja.

---

## 6. CLI wrapper — potpuna specifikacija

### 6.1 Komande

```powershell
flowos session start --agent claude-code --task FLOW-42
flowos session start --agent codex --task FLOW-43 --worktree
flowos session start --agent pi --model glm --task FLOW-44 `
  --hint "python_backend/app/auth/**"     # opcioni hint za atribuciju

flowos session list
flowos session end <id>                    # ručno zatvaranje po potrebi
flowos worktree new --task FLOW-43
flowos worktree integrate <id>             # diff pregled + vođena integracija
flowos worktree clean                      # uz potvrdu, poštuje retention
flowos report <session-id>                 # otvori/dopuni draft izvještaja
flowos job submit --task FLOW-50 --workflow coding   # od faze 8
flowos job status <job-id>                           # od faze 8
```

### 6.2 Tok `session start`

1. Upiše `AgentSession` (agent, model, task, cwd, terminal label) — direktno u bazu ako je backend nedostupan, sinhronizacija kasnije; wrapper nikad ne blokira rad.
2. Snimi početni Git snapshot: `rev-parse HEAD`, `status --porcelain=v2`, branch. Prljav tree → upozorenje + zapis, bez blokiranja.
3. Uz `--worktree`: kreira branch i worktree po naming pravilu (§9.3) i pokrene agenta u njemu.
4. Pokrene agentov CLI kao child proces u Windows Job Objectu (potomci ne ostaju siročad; kill ubija cijelo stablo).
5. Tokom rada: `last_activity_at` se izvodi iz fs događaja i živosti procesa. Poseban heartbeat mehanizam ne postoji.
6. Na izlazu: završni Git snapshot, diff stat, commitovi tokom sesije, trajanje, exit code; status `COMPLETED`; pokuša `scripts/verify.py` ako postoji; generiše draft `AgentReport`.
7. Ako je wrapper ubijen: backend pri sljedećem startu nalazi sesije sa mrtvim PID-om, snima završni snapshot i stavlja ih u `NEEDS_REVIEW`.

### 6.3 Adapteri unutar wrappera

Wrapper zna kako se koji CLI pokreće (komanda, argumenti, env). Redoslijed implementacije: **Claude Code** (najstabilniji headless interfejs), zatim **pi** (vlastiti kod, najlakša integracija i jedini koji može emitovati bogatije događaje), zatim **Codex**, zatim `GenericCliAdapter` za sve ostalo.

Capability model (koristi se od faze 6, deklariše se od početka):

```text
can_launch          # FlowOS smije pokrenuti alat
can_stream_events   # alat emituje strukturirane događaje
can_report_usage    # alat prijavljuje tokene/trošak
can_cancel          # podržava kontrolisani prekid
can_use_worktree    # radi ispravno u zadatom worktreeju
```

Namjerno izostavljeno iz ugovora: `can_cooperative_pause`, `can_resume_step`, `can_request_approval` — nijedan ciljani alat ih danas ne podržava; dodaju se kada prvi alat to stvarno ponudi.

---

## 7. Detekcija aktivnosti i konflikta

### 7.1 Izvori signala

- **Filesystem watcher** (watchdog) na root svakog registrovanog repoa i worktreeja: create/modify/delete, debounce 500 ms; ignoriše `.git/`, `node_modules/`, `__pycache__/`, `dist/`, build artefakte (konfigurabilan ignore po repou).
- **Git polling** svakih 30 s po aktivnom repou: `status --porcelain=v2`, novi commitovi (`log --since`), trenutni branch/HEAD.
- **PID i exit code** child procesa (`WRAPPED_TERMINAL` i `MANAGED`).
- **Adapter eventi** gdje postoje (pi; kasnije drugi) — obogaćuju, nikad uslov.

### 7.2 Atribucija promjene

```text
Fajl u worktreeju sesije X          → pripisano X          (pouzdano)
Fajl u dijeljenom treeju:
  ├── jedna aktivna sesija u treeju → pripisano njoj       (vjerovatno)
  ├── više aktivnih sesija          → hint match ili NEATRIBUIRANO
  └── nijedna aktivna sesija        → korisnik/vanjski proces (USER)
```

GUI razlikuje "pripisano" i "vjerovatno/neatribuirano" — heuristika se ne prikazuje kao činjenica.

### 7.3 Pravila upozorenja

| Situacija | Nivo | Akcija |
|---|---|---|
| Dvije aktivne sesije upisuju u isti fajl u istom treeju unutar 10 min | VISOKO | preporuči worktree, jedan klik do `worktree new` |
| Sesija upisuje u fajl koji je druga mijenjala u zadnjih 30 min | SREDNJE | prikaži obje sesije i fajl |
| Branch/HEAD promijenjen ispod aktivne sesije (checkout, rebase) | SREDNJE | upozori, zabilježi event |
| Sesija bez fs aktivnosti i bez živog procesa > 30 min | INFO | predloži `ABANDONED` |
| Završni snapshot ima izmjene bez ijednog commita | INFO | podsjeti na commit u reportu |

Pragovi (10/30 min) su konfigurabilni; lista se proširuje samo na osnovu stvarno viđenih konflikata iz dnevnika upotrebe (§3.7).

### 7.4 Politika radnog prostora

- isti tree: analiza, review, kratke koordinisane izmjene;
- worktree: svaka paralelna implementacija (`--worktree` flag čini ovo jeftinim);
- container/sandbox: rizični i nepouzdani zadaci (faza 10);
- integrator je uvijek korisnik kroz `flowos worktree integrate` — automatski merge se ne gradi ni u jednoj fazi.

---

## 8. Podatkovni model

Model raste po fazama; svaka faza dodaje svoje tabele, ne mijenja tuđe. Sve tabele imaju `created_at`; append-only tabele nemaju update.

### 8.1 Core (faza 1, prošireno u fazi 5)

**Project**

```text
id, name, repo_path, status, notes, created_at
```

**Task**

```text
id, project_id, title, status, priority, notes, created_at, done_at
status: OPEN | IN_PROGRESS | BLOCKED | DONE
priority: LOW | NORMAL | HIGH | URGENT
```

**Decision** (faza 5)

```text
id, project_id, task_id, title, decision, rationale, decided_at
```

**TaskContract** (faza 5; tekstualni prilog zadatku, ne poseban DSL)

```text
id, task_id, goal, scope, out_of_scope, acceptance_criteria,
allowed_paths_hint, risks, created_at, approved_at
```

### 8.2 Session Coordination (faze 1–4)

**AgentSession**

```text
id, task_id, project_id
agent_type, model_name, execution_mode, terminal_label
working_directory, repo_path, branch_name, worktree_path
base_commit_sha, pid
status, started_at, last_activity_at, ended_at, exit_code
status: ACTIVE | IDLE | COMPLETED | ABANDONED | NEEDS_REVIEW
```

`NEEDS_REVIEW` pokriva: sumnjiv završetak, nepoznate izmjene, konflikt koji traži odluku — jedan status umjesto tri.

**SessionEvent** (append-only)

```text
id, session_id, event_type, summary, payload_json, occurred_at, source,
idempotency_key (nullable, unique kad postoji)
event_type: STARTED | GIT_SNAPSHOT | COMMIT_OBSERVED | CONFLICT_WARNING |
            VERIFY_RESULT | CHECKPOINT | COMPLETED | ABANDONED | NOTE
```

**FileActivity** (zasebna tabela — nad njom se rade upiti preklapanja)

```text
id, session_id (nullable), repo_path, file_path, change_type,
attribution, observed_at
attribution: WORKTREE | SOLE_ACTIVE | HINT | UNATTRIBUTED | USER
```

Retention: 30 dana; agregat po sesiji ostaje u reportu.

**GitSnapshot**

```text
id, session_id, snapshot_type, commit_sha, branch_name,
status_porcelain, diff_stat, created_at
snapshot_type: START | END | PERIODIC
```

**AgentReport**

```text
id, session_id, agent_job_id (nullable), summary, changed_files,
commit_shas, verification_summary, open_risks, cost_summary,
duration_summary, user_verdict, created_at
user_verdict: ACCEPTED | NEEDS_WORK | REJECTED | null
```

**AgentArtifact**

```text
id, session_id, agent_job_id (nullable), artifact_type,
storage_key, sha256, size_bytes, mime_type, created_at, retention_policy
artifact_type: DIFF | PATCH | TEST_REPORT | LINT_REPORT | STDOUT_LOG |
               STDERR_LOG | SCREENSHOT | HANDOFF | FINAL_REPORT | CONTEXT_PACK
```

### 8.3 Managed Execution (faza 6)

**AgentJob**

```text
id, project_id, task_id, task_contract_id
workflow_type, risk_level, execution_mode
requested_agent, selected_adapter, selected_model
worktree_path, branch_name, base_commit_sha, result_commit_sha
status, error_class, error_message
created_at, started_at, completed_at, version
status: DRAFT | QUEUED | RUNNING | WAITING_APPROVAL | PAUSED |
        BLOCKED | COMPLETED | FAILED | CANCELLED
```

Osam radnih statusa + DRAFT. `PAUSED` znači "ne pokreći sljedeći korak" — ne zamrzavanje procesa. `version` je optimistic locking.

**ApprovalRequest** (faza 6, samo za rizične vanjske akcije)

```text
id, agent_job_id, action_type, risk_level, reason,
payload_artifact_id, status, requested_at, resolved_at, idempotency_key
```

Odluka se veže za snimljeni payload artefakt (ono što je prikazano je ono što je odobreno); ponovljeni klik je idempotentan; odbijeno ne ide u automatski retry. Kanonski hash i risk-matrica se ne uvode — jedan korisnik odobrava vlastite akcije.

### 8.4 Durable ekstenzija (faza 8)

**AgentStep**

```text
id, agent_job_id, name, sequence, status,
attempt_count, max_attempts, timeout_seconds, retry_policy,
input_manifest, output_manifest, started_at, completed_at,
last_error_class, last_error_message
status: PENDING | RUNNING | COMPLETED | FAILED | SKIPPED
```

**StepAttempt**

```text
id, agent_step_id, attempt_number, pid, status,
started_at, completed_at, exit_code, error_class, error_message,
stdout_artifact_id, stderr_artifact_id, usage_json
status: RUNNING | COMPLETED | FAILED | LOST | CANCELLED
```

Bez WorkerLease tabele: na jednom računaru backend je jedini dodjeljivač poslova, supervizija je PID + Job Object, a startup recovery (§14.3) čisti mrtve attempte. Lease + fencing generation se uvode tek sa udaljenim workerima (faza 10).

Bez Checkpoint tabele: checkpoint = commit SHA + `handoff.md` artefakt, zapisan kao `CHECKPOINT` event sa `commit_sha` i `artifact_id` u payloadu (§14.1).

### 8.5 Observability (faza 7)

**UsageRecord**

```text
id, session_id (nullable), agent_job_id (nullable), agent_type,
model_name, input_tokens, output_tokens, estimated_cost,
duration_seconds, source, recorded_at
source: ADAPTER_REPORTED | ESTIMATED
```

### 8.6 Baza

SQLite, WAL mode, foreign keys ON, kratke transakcije, jedan writer proces (backend; wrapper piše kroz API, direktno u bazu samo offline uz kasniju sinhronizaciju). Dnevni backup kopiranjem fajla + `PRAGMA wal_checkpoint`. Migracije: Alembic od prvog dana. PostgreSQL isključivo uz fazu 10.

---

## 9. Workspace, Git i worktree pravila

### 9.1 Snimanje dokaza

Na početku i kraju svake sesije/joba:

```bash
git rev-parse HEAD
git status --porcelain=v2
git diff --stat <base_commit>
git diff --name-status <base_commit>
```

Puni diff se snima kao artefakt tek na kraju (veličina), stat na svakom snapshotu.

### 9.2 Pravila

- implementacija nikad direktno na glavnoj grani kada ide kroz FlowOS;
- jedan writable worktree = najviše jedna writer sesija;
- verifier (faza 9) radi read-only;
- merge/integracija je uvijek korisnička akcija kroz `worktree integrate`;
- napušteni worktree se ne briše prije retention perioda i pregleda.

### 9.3 Naming

```text
branch:    flow/<task-id>-<slug>        (flow/FLOW-42-auth-token)
worktree:  <repo>/../worktrees/<task-id>/
```

### 9.4 Integracija više rezultata

`flowos worktree integrate` vodi korisnika: prikaži diff prema bazi → pokreni verify u worktreeju → merge/rebase uz konflikte prikazane u GUI-ju → završni verify na cilju → zatvori sesiju i report. Redoslijed integracije kad je više worktreejeva spremno bira korisnik; FlowOS samo prikazuje šta čeka (integracijski red je lista, ne mašinerija).

---

## 10. API ugovori

### 10.1 Session API (faze 1–4)

```text
POST   /sessions                  registracija (wrapper i GUI)
PATCH  /sessions/{id}             status, task, hint, label
POST   /sessions/{id}/events      idempotency ključ obavezan
POST   /sessions/{id}/end         završni snapshot + report draft
GET    /sessions/active
GET    /sessions/{id}/timeline
GET    /conflicts
CRUD   /projects, /tasks
GET/PATCH /reports/{id}
GET    /artifacts/{id}
```

### 10.2 Managed Execution API (faza 6)

```text
POST   /jobs                      kreiraj iz taska + contracta
POST   /jobs/{id}/launch
POST   /jobs/{id}/cancel          soft; hard poslije grace perioda
GET    /jobs/{id}
GET    /jobs/{id}/timeline
POST   /approvals/{id}/resolve    approve/reject, idempotentno
```

### 10.3 Durable API (faza 8)

```text
POST   /jobs/{id}/pause           ne pokreći sljedeći korak
POST   /jobs/{id}/resume
POST   /jobs/{id}/steps/{sid}/retry
POST   /jobs/{id}/resolve-blocked
GET    /jobs/{id}/steps
GET    /jobs/{id}/attempts
```

### 10.4 Observability API (faza 7)

```text
POST   /usage
GET    /usage/summary?by=agent|model|project|task_type
GET    /timeline?project=...
```

Idempotency ključ na svim write endpointima koje wrapper ili adapter mogu ponoviti (events, usage, approvals resolve, complete/fail koraka).

---

## 11. GUI plan

### 11.1 Aktivne sesije (faza 2) — glavni ekran

Kartica po sesiji:

```text
Claude Code · nas-agent · FLOW-42
Worktree: ../worktrees/FLOW-42  ·  Branch: flow/FLOW-42-auth-token
Zadnja aktivnost: prije 20 s  ·  3 fajla  ·  1 commit
[⚠ dijeli tree sa Codex/FLOW-43]
```

Upozorenja su badge na kartici + filter na vrhu. Poseban Conflict Center ekran se gradi tek ako broj istovremenih upozorenja to opravda mjerenjem.

### 11.2 Timeline sesije/joba (faza 3)

Tri nivoa: **sažetak** (stanje, gdje je stao, naredni potez, otvorene odluke) → **timeline** (poslovno relevantni događaji) → **tehnički detalji** (snapshoti, fajlovi, komande, logovi, usage). Nikad prikaz svakog tokena.

### 11.3 Zadaci i projekat (faza 1, prošireno u fazi 5)

Lista po projektu: naslov, status, vezane sesije/jobovi, blokade, otvorene odluke. Faza 5 dodaje Inbox (brzo bilježenje), Danas (dnevni plan), Review (sedmični pregled) i prikaz odluka sa razlozima.

### 11.4 Report pregled (faza 3)

Draft iz wrappera: izmijenjeni fajlovi, commitovi, verify rezultat, otvoreni rizici → korisnikov verdict (prihvaćeno / dorada / odbijeno).

### 11.5 Execution Console (faza 6)

Pokreni agenta: izbor taska i contracta → adapter/model → isti tree ili worktree → prikaz dozvola → praćenje događaja uživo → cancel → approval zahtjevi sa snimljenim payloadom → završni diff, verify i verdict.

### 11.6 Job pregled (faza 8)

Koraci sa statusima, attempti, retry dugme po koraku, razlog blokade, posljednji checkpoint (commit + handoff), pause/resume.

### 11.7 Troškovi i evaluacija (faza 7)

Trošak i trajanje po agentu/modelu/projektu; stopa prihvatanja po agentu i tipu zadatka; poređenje modela na istoj vrsti posla.

---

## 12. Managed Execution — model izvršenja (faza 6)

Adapter interfejs:

```python
class CodingAgentAdapter(Protocol):
    def capabilities(self) -> AdapterCapabilities: ...
    async def prepare(self, request: AgentRequest) -> PreparedExecution: ...
    async def launch(self, prepared: PreparedExecution) -> ExecutionHandle: ...
    async def observe(self, handle: ExecutionHandle) -> ExecutionStatus: ...
    async def request_cancel(self, handle: ExecutionHandle) -> ControlResult: ...
    async def collect_result(self, handle: ExecutionHandle) -> AgentResult: ...
    async def cleanup(self, handle: ExecutionHandle) -> None: ...
```

Supervizija procesa: subprocess u Windows Job Objectu; timeout po jobu; soft cancel (signal/stdin ako alat podržava) → grace period → terminate Job Objecta (ubija cijelo stablo). stdout/stderr idu u artefakte uz redakciju vjerovatnih tajni.

Vertikalni tok faze 6:

```text
FlowOS task → potvrđen task contract → worktree → agent (jedan adapter)
→ verify.py → diff + report → korisnički verdict
```

---

## 13. Durable Job Engine — model izvršenja (faza 8)

### 13.1 Workflow

Posao = unaprijed definisan niz sekvencijalnih koraka (bez DAG-ova, bez workflow jezika). Standardni coding workflow:

```text
PREPARE_CONTEXT → CREATE_WORKTREE → IMPLEMENT → VERIFY
→ [REVIEW → FIX_CONFIRMED] (faza 9) → WAIT_FOR_APPROVAL → FINALIZE
```

Svaki korak ima: ulazne artefakte, timeout, retry politiku, očekivani izlaz i completion check (deterministički gdje god je moguće: exit code, postojanje artefakta, prošao verify).

### 13.2 Retry politika

Klasifikacija grešaka (zadržano iz v2 — dobar dio):

```text
TRANSIENT               mrežni timeout, API limit, crash prije trajne promjene
                        → automatski retry, ograničen backoff sa jitterom
RETRYABLE_WITH_REVIEW   nestabilna test infrastruktura, nepotpun izlaz agenta
                        → retry uz zapis; poslije 2. puta → BLOCKED
NON_RETRYABLE           pogrešan contract, odbijen approval, zabranjena akcija,
                        ponovljena deterministička greška bez nove strategije
                        → BLOCKED ili FAILED, nikad automatska petlja
```

Budžeti po jobu: max pokušaja po koraku, max ukupno pokušaja, max trajanje, opcioni token/troškovni limit. Potrošen budžet → `BLOCKED`, korisnička odluka.

### 13.3 Checkpoint = commit + handoff

Checkpoint nije snimka rezonovanja modela. To je:

- commit u worktreeju (kod), i
- `handoff.md` artefakt: šta je urađeno, šta je ostalo, otvoreni problemi, sljedeća očekivana akcija, ključni fajlovi.

Zapisuje se kao `CHECKPOINT` event. Sigurne tačke: poslije pripreme konteksta, poslije commita, poslije verify, prije approvala. Resume = novi proces dobija contract + handoff + worktree na posljednjem commitu. FlowOS ne obećava nastavak "od posljednje misli" i GUI to jasno prikazuje.

### 13.4 Startup recovery

Pri startu backenda:

```text
Nađi RUNNING attempte
→ provjeri PID (živ i pripada našem Job Objectu?)
→ mrtav: attempt = LOST, snimi Git snapshot worktreeja
→ worktree čist ili na poznatom commitu: korak → PENDING (retry po politici)
→ worktree ima nepoznate izmjene / nejasna vanjska akcija: job → BLOCKED
```

Automatski recovery se NE radi kada: worktree sadrži izmjene koje se ne mogu objasniti, vanjska akcija je možda izvršena (idempotency zapis nepotpun), ili je budžet potrošen. Tada `BLOCKED` + jasan razlog u GUI-ju.

### 13.5 Idempotentnost i side-effect barrier

Za svaku vanjsku ili nepovratnu akciju (instalacija, migracija, slanje, push):

```text
provjeri approval → rezerviši idempotency ključ → zapiši ACTION_STARTED
→ izvrši → zapiši rezultat
```

Recovery prvo provjerava `ACTION_STARTED` bez rezultata → job u `BLOCKED` ("nejasan ishod vanjske akcije"), nikad slijepo ponavljanje.

### 13.6 Pause/resume i cancel

Pause = ne pokreći sljedeći korak (tekući korak se završava ili kill po izboru korisnika). Resume = validiraj worktree + handoff → job u `QUEUED`. Soft cancel → grace → hard cancel (Job Object terminate) → recovery provjera worktreeja → worktree ostaje za pregled (diff, spasi djelimično, odbaci, novi task).

---

## 14. Verifikacija

- Svaki repo: jedna ulazna tačka `scripts/verify.py` (format, lint, type-check, testovi, build smoke — po repou).
- Wrapper je pokreće na kraju sesije (faza 3); Managed/Durable je pokreću kao `VERIFY` korak.
- Obim po veličini promjene: mala → format+lint+ciljani testovi; srednja → +type-check+širi paket; velika/rizična → +integracijski testovi+security scan+nezavisni review (faza 9)+approval.
- Rezultat je uvijek artefakt (report + exit code), nikad samo tekst agenta.

---

## 15. Multiagent tokovi (faza 9)

### 15.1 Implementator + verifier

```text
Agent A implementira → deterministički testovi → Agent B (read-only)
pregleda SAMO dokazni paket (contract, diff, test rezultati, rizici —
ne rezonovanje implementatora) → Agent A popravlja POTVRĐENE nalaze
→ završna verifikacija
```

Svaki nalaz obavezno sadrži: severity, fajl/lokaciju, konkretan problem, **dokaz ili reprodukciju**, vezu s acceptance kriterijumom, prijedlog, confidence. Nalaz bez reprodukcije se ne prosljeđuje implementatoru.

**Uslov terminacije (obavezan):** najviše 2 review runde po jobu i troškovni budžet po review ciklusu. Poslije toga → korisnička odluka. Bez ovoga je tok token-ponor.

### 15.2 Ostali obrasci

- Planner + implementator: samo za složene zadatke; za male izmjene je čist overhead.
- Paralelno istraživanje: dozvoljeno za stvarno nezavisne podteme (arhitektura / sigurnost / analiza koda), jedan agent sintetiše.
- Zabranjeno: slanje svakog zadatka svim modelima; glasanje modela kao dokaz ispravnosti.

### 15.3 Model routing

```text
Nivo 0  deterministički kod      CRUD, filteri, statusi, verify komande
Nivo 1  jeftin model             klasifikacija inboxa, sažeci, ekstrakcija
Nivo 2  jedan jak agent          ograničen problem, mali diff, review
Nivo 3  durable workflow         višekorački posao, recovery, approval
```

Routing je vidljivo pravilo koje korisnik može promijeniti, ne neprozirna AI odluka. Postojeća praksa (jaki orkestrator + jeftini radni modeli, execution-based verifikacija) se prenosi direktno.

---

## 16. Sigurnost

- Nijedan model nema proizvoljan shell iz FlowOS Corea.
- Praćenje sesije ne daje procesu nikakve dodatne dozvole.
- Managed Execution: allowlist komandi za determinističke korake, eksplicitne dozvoljene putanje, filtriran environment (bez tajni po defaultu).
- Tajne u Windows Credential Manageru / OS keychainu, nikad u bazi ni logovima; logovi prolaze redakciju vjerovatnih tajni prije pohrane.
- Dependency instalacija, mrežne akcije, migracije, push → approval (faza 6+).
- Produkcijske, finansijske i komunikacijske akcije → uvijek eksplicitni approval.
- Artefakti unutar kontrolisanog root direktorija.
- Worktree NIJE sandbox; za nepouzdane zadatke container (faza 10).
- Prompt nije granica (§3.6) — ograničenja se sprovode kodom.

---

## 17. Observability i evaluacija (faza 7)

- Usage po sesiji/jobu: iz adaptera gdje postoji (`ADAPTER_REPORTED`), inače procjena (`ESTIMATED`) — izvor je uvijek označen.
- Agregati: trošak/trajanje po agentu, modelu, projektu, tipu zadatka; stopa prihvatanja (verdict iz reporta); broj retryja; udio vremena orkestracije naspram rada.
- Evaluation skup: 10–20 stvarnih završenih zadataka kao referentni set za poređenje modela na istoj vrsti posla.
- OpenTelemetry izvoz: tek ako se pojavi vanjski konzument — ne unaprijed.
- Zapisuju se poslovno relevantni događaji; nikad svaki token, nikad privatno rezonovanje modela.

---

## 18. Retention i čišćenje

- metadata, reporti, odluke, approvali: trajno;
- SessionEvent, GitSnapshot: trajno (mali su);
- FileActivity: 30 dana, agregat u reportu;
- stdout/stderr i veliki artefakti: 30–90 dana; hash i manifest duže od fajla;
- neuspješni/napušteni worktreeji: min. 7–30 dana pa ručno čišćenje uz potvrdu;
- integrisani worktreeji: brisanje poslije potvrde i retention perioda;
- čišćenje je auditirano i nikad ne dira aktivnu ili blokiranu sesiju/job.

---

## 19. Test strategija

### Faze 2–4 (Session Coordination, wrapper, worktree)

- dvije writer sesije, isti tree, isti fajl → VISOKO upozorenje;
- worktree sesija + main tree sesija → bez lažnog upozorenja;
- korisnik ručno mijenja fajl tokom sesije → USER atribucija;
- wrapper ubijen → NEEDS_REVIEW + završni snapshot pri sljedećem startu;
- child ubijen → siročad počišćena Job Objectom;
- backend nedostupan pri startu → wrapper radi offline, sync kasnije;
- dirty tree pri startu; base commit nije više HEAD; branch promijenjen ispod sesije; djelimično stageovane promjene; worktree konflikt pri integraciji;
- sesija bez commita na kraju → INFO u reportu.

### Faza 6 (Managed)

- normalan završetak; timeout; soft cancel; hard cancel + potomci; izlaz bez strukturiranog rezultata; promjena izvan dozvoljene putanje; dependency instalacija traži approval; GUI zatvoren dok proces radi (servis nastavlja).

### Faza 8 (Durable) — fault injection obavezan

- proces ubijen prije i poslije checkpointa; dupli completion event (idempotency); server restart sa RUNNING poslovima; nejasan ishod vanjske akcije → BLOCKED; retry budžet potrošen → BLOCKED; nepoznate izmjene u worktreeju → BLOCKED; pause tokom dugog koraka; soft→hard cancel.

### Faza 9

- nalaz bez reprodukcije se odbacuje; review se zaustavlja poslije 2 runde; mjerenje: stopa prihvatanja sa i bez verifier-a na istom evaluation skupu.

Bez fault injection testova tvrdnje o trajnosti i recoveryju se ne smatraju dokazanima.

---

## 20. Faze realizacije — detaljno

### Faza 0 — validacija (2–3 dana)

Voditi dnevnik stvarnih sesija jednu radnu sedmicu (tekstualni fajl): agent, model, tree/worktree, trajanje, konflikti. Mapirati ≥ 10 sesija na model iz §8.
**Kriterij:** model pokriva stvarne sesije bez natezanja; lista stvarno viđenih konflikata postoji.

### Faza 1 — temelj (1 sedmica)

SQLite šema (Core + Session tabele) + Alembic; FastAPI servis (tray); Session i Task endpointi; ručna registracija (`EXTERNAL_TRACKED`) kao fallback.
**Kriterij:** sesija se registruje i vidi kroz API; backend preživi restart bez gubitka.

### Faza 2 — wrapper i watcher (1–2 sedmice)

`flowos session start/end/list`; Git start/end snapshot; Job Object supervizija; fs watcher + Git polling; atribucija; ekran Aktivne sesije; adapter: Claude Code.
**Kriterij:** svakodnevni rad ide kroz wrapper; "ko radi šta" vidljivo bez terminala. **Tačka dnevne upotrebe — sve poslije se gradi uz živ sistem.**

### Faza 3 — konflikti, timeline, reporti (1 sedmica)

Pravila upozorenja §7.3; timeline sesije; draft AgentReport + verdict; verify.py integracija; pi adapter (drugi).
**Kriterij:** bar jedno stvarno preklapanje otkriveno prije štete; svaka sesija završava reportom.

### Faza 4 — worktree tok (1 sedmica)

`worktree new/integrate/clean`; naming pravila; vođena integracija sa diff pregledom i verify; retention; Codex adapter (treći).
**Kriterij:** dvije paralelne implementacije bez dijeljenog writable treeja, integracija kroz FlowOS.

**Prva korisna verzija: faze 0–4 ≈ 4–5 sedmica.**

### Faza 5 — Core proširenje (2–3 sedmice)

Inbox i brzo bilježenje; Danas; sedmični Review; Decision zapisi; TaskContract; povezivanje inbox → task → sesija.
**Kriterij:** FlowOS je koristan i za ne-agentski lični rad; contract postoji za svaki netrivijalan agentski zadatak.

### Faza 6 — Managed Execution (3–4 sedmice)

Adapter interfejs §12 + capability ugovor; Claude Code launch adapter; Execution Console; timeout, soft/hard cancel; allowlist + filtriran env; stdout/stderr artefakti; ApprovalRequest za rizične akcije; vertikalni tok task→contract→worktree→agent→verify→diff→verdict.
**Kriterij:** jedan ograničen coding zadatak prolazi cijeli tok iz GUI-ja bez terminala.

### Faza 7 — Observability (2 sedmice)

UsageRecord + agregati; ekran troškova; stopa prihvatanja; evaluation skup 10–20 zadataka; poređenje modela.
**Kriterij:** moguće je odgovoriti gdje odlazi vrijeme i novac i koji model daje najbolji prihvaćeni rezultat po vrsti posla.

### Faza 8 — Durable Job Engine (3–5 sedmica)

AgentStep + StepAttempt; state machine sa centralnom validacijom tranzicija; retry + klasifikacija grešaka + budžeti; checkpoint (commit + handoff); startup recovery; pause/resume; idempotency + side-effect barrier; `flowos job submit/status`; fault injection testovi.
**Kriterij:** posao preživljava ubijen proces i restart servera i nastavlja od posljednjeg commita + handoffa bez dupliranja rizične akcije.

### Faza 9 — multiagent (2–3 sedmice)

Verifier tok §15.1 sa limitom rundi i budžetom; strukturirani nalazi sa reprodukcijom; drugi model kao verifier; mjerenje na evaluation skupu.
**Kriterij:** verifier tok pokazuje mjerljivo bolju stopu prihvatanja od jednog agenta uz prihvatljiv dodatni trošak — inače se gasi.

### Faza 10 — distribucija i jača izolacija (samo po potrebi, bez procjene)

Uslovi ulaska: stvarna potreba za udaljenim workerom ili nepouzdanim kodom. Sadržaj: WorkerLease + heartbeat + fencing generation; PostgreSQL (`FOR UPDATE SKIP LOCKED`); container supervisor sa mrežnim/CPU/mem ograničenjima; kratkotrajni kredencijali; centralno skladište artefakata.
**Kriterij:** udaljeno/rizično izvršavanje tehnički izolovano bez promjene Core ugovora.

---

## 21. Šta se namjerno ne gradi (i uslov povratka)

| Stavka | Zašto ne | Vraća se kada |
|---|---|---|
| Lease + heartbeat + fencing | jedan računar: PID + Job Object + startup recovery | faza 10 (udaljeni workeri) |
| Checkpoint tabela | commit + handoff.md pokrivaju sve | nikad kao tabela; ostaje event |
| Ownership manifesti kao temelj | nagađanje unaprijed → šum ili beskorisnost | nikad kao temelj; hint ostaje |
| Hash-check čitanje→upis | traži adapter read-evente koji ne postoje | alat počne emitovati read-evente |
| ControlRequest model | status kolone + PID kontrola dovoljni | nikad; durable koristi status |
| Approval kanonski hash + risk matrica | korisnik odobrava vlastite akcije; payload artefakt dovoljan | vanjski approveri ili automatske critical akcije |
| Cooperative pause/resume procesa | ciljani CLI alati ne podržavaju | prvi alat ponudi |
| AgentSpan kao durable backend | omotava SDK agente (LangGraph/OpenAI SDK/ADK), ne eksterne CLI procese; Conductor/Java server pretežak za lokalni solo setup | evaluirati samo za pi agenta ako pi zatraži durable izvršavanje |
| DAG-ovi, workflow jezik, vizuelni editor | sekvencijalni koraci pokrivaju stvarne poslove | mjerenje pokaže stvaran DAG slučaj |
| Automatski merge | integracija je korisnička odluka | nikad u ovom opsegu |
| Model voting | nije dokaz ispravnosti | nikad |
| Message broker, mikroservisi, klaster | modularni monolit + SQLite dovoljni | faza 10, i tada minimalno |
| VS Code ekstenzija | wrapper dokazuje tok jeftinije | wrapper stabilan i korišten ≥ 1 mjesec |
| Replay tokena / internog rezonovanja | nemoguće i nepotrebno | nikad |

---

## 22. Rizici i odgovori

| Rizik | Odgovor |
|---|---|
| Infrastruktura pojede projekat | svaka faza završava vertikalnim tokom u dnevnoj upotrebi; faza ne počinje dok prethodna ne živi |
| Wrapper preskup za korištenje → registar umire | metrika #1 (§23); ako < 80 % sesija ide kroz wrapper, to je glavni bug i staje sve ostalo |
| Šum upozorenja → ignorisanje | mala lista pravila, konfigurabilni pragovi, proširenje samo iz stvarnih konflikata |
| Lažan osjećaj kontrole ručnih sesija | GUI jasno prikazuje režim i šta sistem stvarno zna |
| Lažan osjećaj nastavka "od posljednje misli" | GUI prikazuje checkpoint = commit + handoff, ništa više ne obećava |
| Dupliranje side effecta pri retryju | idempotency ključ + side-effect barrier + BLOCKED kod nejasnog ishoda |
| Dva writera u istom treeju | detekcija + VISOKO upozorenje + jednoklik worktree; pravilo jedan writer po worktreeju |
| Verifier petlja troši tokene | limit 2 runde + budžet po ciklusu + nalaz bez reprodukcije se odbacuje |
| Nepouzdan verifier nalaz | obavezan dokaz/reprodukcija + confidence |
| Tajne u logovima | redakcija prije pohrane + OS keychain + filtriran env |
| Oštećen handoff/checkpoint | commit je uvijek validan fallback; nejasno stanje → BLOCKED |
| Dupliranje pi runtimea | FlowOS kontroliše izvana (proces, worktree, rezultat); agent zadržava vlastiti runtime, memoriju i tool selection |

---

## 23. Metrike uspjeha

1. **% sesija kroz wrapper** — cilj > 80 % poslije mjesec dana; ispod toga je registracija preskupa i to je bug broj jedan.
2. Vrijeme da se utvrdi "ko radi šta" — cilj < 10 s, jedan pogled.
3. Preklapanja otkrivena prije štete naspram poslije.
4. % sesija sa reportom i verdictom.
5. FlowOS overhead po sesiji — cilj < 30 s ukupno.
6. (od F6) % managed jobova završenih bez ručne intervencije.
7. (od F7) trošak po prihvaćenoj promjeni, po modelu.
8. (od F8) % poslova uspješno oporavljenih poslije ubijenog procesa; broj dupliranih rizičnih akcija (cilj: 0).
9. (od F9) razlika stope prihvatanja sa i bez verifiera, na istom skupu.

---

## 24. Vertikalni eksperimenti (gate za sljedeću fazu)

**E1 (kraj faze 3):** tri stvarne sesije kroz wrapper (Claude Code, Codex, pi); dvije u istom treeju, jedna u worktreeju; namjerno WRITE/WRITE preklapanje → upozorenje stiže prije štete; sve tri završe sa reportom i tačnom atribucijom; izmjeriti metrike 1–5. Uspjeh: jedan radni dan bez otvaranja terminala radi uvida.

**E2 (kraj faze 6):** jedan stvarni coding zadatak iz GUI-ja: contract → worktree → agent → verify → diff → verdict; jedan namjeran timeout i jedan hard cancel sa čišćenjem potomaka.

**E3 (kraj faze 8):** durable posao od ≥ 3 koraka; ubiti proces poslije commita → recovery nastavlja od handoffa; restart servera sa RUNNING poslom; pause pa resume; provjeriti da rizična akcija nije duplirana; kompletan timeline tačan.

**E4 (kraj faze 9):** 10 zadataka iz evaluation skupa sa i bez verifiera; uporediti stopu prihvatanja i trošak; odluka: verifier ostaje ili se gasi.

---

## 25. Odluke prije faze 1

1. **Repo:** FlowOS kao zaseban repozitorij (čist rez, vlastiti verify.py, vlastiti AGENTS.md).
2. **Backend:** stalni lokalni servis (tray, autostart) — watcher mora raditi bez GUI-ja.
3. **Redoslijed adaptera:** Claude Code → pi → Codex → GenericCli.
4. **Naming:** `flow/<task-id>-<slug>`, `../worktrees/<task-id>/`.
5. **Privatnost:** ništa ne napušta računar; nema cloud telemetrije; backup lokalno.
6. **Dogfooding projekat:** jedan stvarni aktivni repo od faze 2 (preporuka: onaj s najviše paralelnih sesija).

---

## 26. Konačna preporuka

```text
FlowOS Core        = namjera: projekti, zadaci, odluke, review
Session Coord.     = istina o tome ko šta stvarno radi (detekcija)
flowos wrapper     = registracija kao nusprodukt rada
Worktree pravila   = izolacija i pouzdana atribucija
verify.py          = dokaz kvaliteta, deterministički
Managed Execution  = pokretanje i kontrola iz FlowOS-a
Observability      = trošak, trajanje, koji model za koji posao
Durable Engine     = posao preživljava pad: commit + handoff + recovery
Verifier tok       = nezavisni pregled sa dokazom i limitom rundi
Approval           = ljudska odluka za rizične akcije
```

Sistem je uspješan ako pouzdano odgovara na šest pitanja: šta je agent trebao uraditi; šta je stvarno uradio; gdje je stao; može li se bezbjedno nastaviti; koji dokazi potvrđuju rezultat; koju odluku korisnik sada treba donijeti. Svaki dio plana koji ne doprinosi jednom od tih odgovora — ne gradi se.
