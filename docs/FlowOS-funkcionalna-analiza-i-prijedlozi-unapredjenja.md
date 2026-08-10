# FlowOS — funkcionalna analiza izvornog koda i prijedlozi za unapređenje

## Osnova analize

Ovaj dokument je zasnovan na čitanju izvornog bundle-a:

```text
FlowOS-source-v0.1.0.zip
```

Fokus nije GUI izgled, nego ono što aplikacija stvarno radi ili pokušava raditi kroz:

- FastAPI servis;
- PySide6 GUI;
- CLI;
- SQLite persistence;
- planski model;
- agentske sesije;
- worktree izolaciju;
- watcher;
- atribuciju promjena;
- konfliktni sistem;
- verifikaciju;
- izvještaje;
- „Gdje si stao“;
- timeline;
- WebSocket događaje;
- agent adaptere.

Gdje kod ne podržava zaključak, to je jasno označeno kao prijedlog ili izvedena preporuka.

---

# 1. Trenutna funkcionalna slika FlowOS-a

FlowOS već ima više od običnog pregleda agentskih sesija.

Iz koda se vidi pet glavnih funkcionalnih stubova:

```text
1. Projekat i plan
2. Agentska sesija i njen životni ciklus
3. Git/worktree praćenje i konfliktna detekcija
4. Verifikacija i izvještaji
5. Nastavak rada kroz Project Resume i Timeline
```

## 1.1 Projekti

Postoji:

- kreiranje projekta;
- izmjena projekta;
- brisanje projekta;
- lista projekata;
- repo putanja;
- aktivni plan;
- projektno Git stanje;
- project resume state.

Relevantni fajlovi:

```text
services/projects/service.py
controllers/http/projects.py
persistence/models.py
persistence/resume_models.py
```

## 1.2 Planovi

Postoji ozbiljan planski model:

- Plan;
- PlanPhase;
- PlanItem;
- PlanItemCriterion;
- PlanItemDependency;
- PlanProgressEvent.

Podržani su statusi:

```text
NOT_STARTED
IN_PROGRESS
BLOCKED
IMPLEMENTED
VERIFIED
ACCEPTED
```

Postoji:

- Markdown import plana;
- aktiviranje plana;
- validacija statusnih tranzicija;
- zavisnosti;
- detekcija ciklusa;
- kriterijumi;
- audit promjena statusa;
- grupisani pregled plana.

Relevantni fajlovi:

```text
services/plan_import.py
services/plan_progress.py
persistence/plan_models.py
controllers/http/plan_progress.py
```

## 1.3 Sesije

Postoji:

- registracija sesije;
- status;
- agent tip;
- model;
- repo;
- branch;
- worktree;
- plan item;
- task;
- PID;
- heartbeat;
- završetak sesije;
- result commit;
- timeline.

Relevantni fajlovi:

```text
services/sessions/service.py
services/sessions/completion.py
services/sessions/timeline.py
persistence/models.py
controllers/http/sessions.py
```

## 1.4 Worktree izolacija

Postoji:

- pravljenje worktree-a;
- lista worktree-ova;
- status;
- diff prema bazi;
- changed files;
- retention;
- cleanup;
- abandoned worktree lista;
- prepare integration;
- povezivanje sesije sa worktree-om;
- označavanje integracije.

Relevantni fajlovi:

```text
services/worktrees/service.py
services/worktrees/manager.py
persistence/worktree_models.py
controllers/http/worktrees.py
```

## 1.5 Aktivnosti i atribucija

Watcher bilježi promjene fajlova kao `FileActivity`.

Postoji:

- normalizacija putanje;
- tree identity;
- repo/worktree razlikovanje;
- pokušaj atribucije aktivnoj sesiji;
- confidence;
- event ID;
- trajni zapis aktivnosti.

Relevantni fajlovi:

```text
services/activity/service.py
services/attribution/service.py
infrastructure/watcher.py
persistence/activity_models.py
```

## 1.6 Konflikti

Postoje tipovi:

```text
WRITE_WRITE
LATE_OVERLAP
BRANCH_CHANGE
STALE_SESSION
NO_COMMIT
```

Postoji:

- conflict key;
- first seen;
- last seen;
- occurrence count;
- evidence;
- acknowledge;
- resolve;
- lista otvorenih konflikata.

Relevantni fajlovi:

```text
services/conflicts/service.py
persistence/conflict_models.py
controllers/http/conflicts.py
```

## 1.7 Verifikacija

Postoji:

- pronalazak `scripts/verify.py`;
- pokretanje kroz isti Python interpreter;
- timeout;
- stdout/stderr;
- exit code;
- trajanje;
- artifact ID;
- metadata;
- SHA-256;
- čuvanje artefakata;
- VERIFY_RESULT događaj.

Relevantni fajlovi:

```text
services/verification/service.py
controllers/http/verification.py
```

## 1.8 Izvještaji

Postoji bogat `AgentReport` model sa:

- scope;
- summary;
- implementation summary;
- verification summary;
- rizicima;
- where stopped;
- next step;
- preconditions;
- confidence;
- impact;
- reprodukcijom;
- odbačenim opcijama;
- konfliktima izvora;
- commitovima;
- changed files;
- user verdict;
- verdict audit;
- Markdown exportom.

Relevantni fajlovi:

```text
services/reports/service.py
persistence/report_models.py
controllers/http/reports.py
```

## 1.9 „Gdje si stao“

`ProjectResumeService` pokušava rekonstruisati:

- aktivni plan;
- posljednju relevantnu plan stavku;
- posljednju sesiju;
- workspace stanje;
- blokatore;
- gdje se stalo;
- sljedeći konkretan korak;
- preuslove;
- confidence;
- resume status.

Relevantni fajlovi:

```text
services/project_resume.py
persistence/resume_models.py
controllers/http/project_resume.py
```

## 1.10 WebSocket

Postoji `EventBus` i `/ws` endpoint.

Deklarisani događaji:

```text
service.ready
session.updated
session.completed
conflict.created
reconciliation.created
plan_progress.updated
project.resume.updated
```

Međutim, u pregledanom source-u nisam pronašao stvarne pozive:

```python
event_bus.emit(...)
```

van samog EventBus modula.

Znači infrastruktura postoji, ali funkcionalni real-time tok još nije povezan.

---

# 2. Najvažniji zaključak

FlowOS trenutno ima dobar skup pojedinačnih servisa, ali još nema dovoljno jak **zatvoreni operativni tok**.

Drugim riječima, postoje komponente:

```text
plan
sesija
watcher
konflikt
verify
report
resume
timeline
```

ali aplikacija još nedovoljno automatski pretvara njihove rezultate u:

```text
jasnu odluku
sljedeću akciju
status stavke
status projekta
siguran nastavak rada
```

Najveći funkcionalni dobitak neće doći iz dodavanja još mnogo ekrana, nego iz povezivanja postojećih funkcija u nekoliko pouzdanih vertikalnih tokova.

---

# 3. Prvi veliki prijedlog — napraviti centralni „Project State Engine“

## Trenutni problem

Status projekta je trenutno rasut kroz:

- PlanItem status;
- AgentSession status;
- Conflict status;
- ProjectWorkspaceState;
- Worktree status;
- AgentReport verdict;
- Verification result;
- ProjectResumeState.

Svaki servis računa dio slike.

Ne postoji jedna centralna funkcija koja odgovara:

```text
Da li je projekat siguran za nastavak?
Da li je stavka završena?
Da li je potrebna korisnička odluka?
Koja je sljedeća dozvoljena akcija?
```

## Prijedlog

Uvesti servis:

```text
ProjectStateService
```

ili:

```text
ProjectDecisionService
```

koji iz postojećih trajnih izvora izvodi jedinstveno stanje.

Primjer izlaza:

```json
{
  "project_id": "...",
  "operational_state": "NEEDS_ATTENTION",
  "active_plan_item_id": "...",
  "active_session_ids": ["..."],
  "open_conflicts": 1,
  "verification_state": "FAILED",
  "git_state": "DIRTY",
  "resume_state": "BLOCKED",
  "next_action": {
    "type": "REVIEW_FAILED_VERIFICATION",
    "label": "Pregledati neuspjelu verifikaciju",
    "target_id": "artifact-id"
  }
}
```

## Moguća stanja

```text
READY
WORK_IN_PROGRESS
NEEDS_ATTENTION
BLOCKED
NEEDS_REVIEW
READY_TO_ACCEPT
SAFE_TO_CONTINUE
EXTERNAL_CHANGES
NO_ACTIVE_PLAN
```

## Zašto je ovo važno

Ovaj servis bi postao autoritativni izvor za:

- početni ekran;
- „Gdje si stao“;
- badge u topbaru;
- CLI status;
- automation;
- upozorenja;
- odluku da li se smije pokrenuti nova sesija;
- odluku da li se smije integrisati worktree.

---

# 4. Drugi veliki prijedlog — pretvoriti plan u izvršni sistem

## Trenutno stanje

Plan model je napredan, ali u velikoj mjeri ostaje evidencioni sistem.

Postoje:

- statusi;
- kriterijumi;
- zavisnosti;
- progress eventi.

Ali nema dovoljno automatike između:

```text
sesija završila
verify prošao
report napravljen
korisnik prihvatio
plan stavka promijenila status
```

## Predloženi zatvoreni tok

```text
1. Korisnik označi stavku IN_PROGRESS
2. FlowOS kreira ili povezuje task
3. Pokreće se agentska sesija
4. Sesija se veže za plan item
5. Sesija završava
6. Git stanje se čita
7. Verify se pokreće
8. Draft report se pravi
9. Stavka automatski prelazi u IMPLEMENTED ako postoje dokazi
10. Nezavisna provjera prelazi u VERIFIED
11. Korisnički verdict prelazi u ACCEPTED ili vraća u IN_PROGRESS/BLOCKED
```

## Predložena tranziciona pravila

### IN_PROGRESS → IMPLEMENTED

Dozvoliti samo ako:

- sesija je završena;
- postoji rezultat commit ili eksplicitna no-code oznaka;
- nema otvorenog kritičnog konflikta;
- report postoji.

### IMPLEMENTED → VERIFIED

Dozvoliti samo ako:

- verify artifact postoji;
- verify rezultat je PASS;
- acceptance kriterijumi su označeni;
- nema neprovjerenog Git stanja.

### VERIFIED → ACCEPTED

Samo korisničkom odlukom:

```text
ACCEPTED
NEEDS_WORK
REJECTED
```

### NEEDS_WORK

Ne bi trebalo samo ostati verdict u reportu.

Treba automatski:

- vratiti PlanItem u `IN_PROGRESS` ili `BLOCKED`;
- napraviti progress event;
- zapisati razlog;
- postaviti next step;
- povezati novi follow-up task.

## Dobitak

FlowOS tada prestaje biti samo preglednik i postaje sistem koji stvarno vodi razvojni proces.

---

# 5. Treći veliki prijedlog — uvesti „Evidence Graph“

## Trenutni problem

Dokazi su rasuti:

- commit SHA u sesiji;
- changed files u reportu;
- verification artifact;
- criterion evidence artifact ID;
- conflict evidence JSON;
- timeline događaji;
- progress event evidence JSON.

Nema jedinstvenog odnosa:

```text
PlanItem
→ Session
→ FileActivity
→ Commit
→ Verification
→ Report
→ Verdict
```

## Prijedlog

Uvesti domain entitet ili read model:

```text
EvidenceBundle
```

Primjer:

```json
{
  "plan_item_id": "FLOW-403-id",
  "session_id": "...",
  "base_commit": "...",
  "result_commit": "...",
  "changed_files": ["..."],
  "verification_artifact_id": "...",
  "report_id": "...",
  "conflict_ids": ["..."],
  "criteria": [
    {
      "criterion_id": "...",
      "status": "PASSED",
      "evidence_refs": ["artifact:...", "commit:..."]
    }
  ]
}
```

## Šta bi to omogućilo

- „Brzi dokazi“ panel;
- tačnu odluku da li je stavka implementirana;
- nezavisnu provjeru;
- lak handoff drugom agentu;
- audit;
- automatski izvještaj;
- mogućnost kasnijeg RAG pretraživanja dokaza.

---

# 6. Četvrti veliki prijedlog — završiti WebSocket kao stvarni event sistem

## Trenutno stanje

`EventBus` postoji, ali nije stvarno korišten.

GUI se zato oslanja na polling i periodic refresh.

## Prijedlog

Emitovati događaje nakon uspješnog commita transakcije.

Minimalni događaji:

```text
project.created
project.updated
plan.activated
plan_item.updated
plan_item.blocked
session.created
session.heartbeat
session.completed
activity.recorded
conflict.created
conflict.resolved
verification.completed
report.created
report.verdict_set
resume.updated
worktree.created
worktree.cleaned
```

## Važno pravilo

Ne emitovati prije DB commita.

Najsigurniji obrazac:

```text
service izvrši promjenu
DB commit
event publisher emit
```

ili koristiti mali outbox.

## MVP varijanta

Uvesti tabelu:

```text
event_outbox
```

sa:

```text
id
event_type
payload_json
created_at
published_at
attempts
```

Background publisher šalje WebSocket događaje.

## Dobitak

- GUI više ne mora osvježavati sve svakih 10 sekundi;
- manje API poziva;
- brža reakcija;
- precizno osvježavanje samo pogođenog panela;
- događaji postaju temelj automatizacije.

---

# 7. Peti veliki prijedlog — uvesti automatizovan „Next Action Engine“

## Trenutno stanje

`ProjectResumeService` generiše tekstualni `next_concrete_step`.

Pravila su jednostavna:

- IN_PROGRESS → završi;
- IMPLEMENTED → pokreni verify;
- VERIFIED → korisnik prihvata;
- BLOCKED → riješi blokadu.

To je korisno, ali previše plitko.

## Prijedlog

Umjesto samo stringa, generisati strukturisanu akciju:

```json
{
  "action_type": "RUN_VERIFICATION",
  "label": "Pokrenuti verifikaciju za FLOW-403",
  "target_type": "PLAN_ITEM",
  "target_id": "...",
  "priority": "HIGH",
  "reason": "Stavka je implementirana, ali nema PASS artefakt",
  "preconditions": [],
  "can_execute": true
}
```

## Primjeri akcija

```text
START_FIRST_PLAN_ITEM
CONTINUE_ACTIVE_SESSION
REVIEW_FAILED_VERIFICATION
RESOLVE_CONFLICT
RECONCILE_EXTERNAL_CHANGES
ACCEPT_VERIFIED_ITEM
CREATE_FOLLOW_UP_SESSION
CLEANUP_WORKTREE
IMPORT_PLAN
```

## Zašto je bolje od teksta

GUI može prikazati dugme koje stvarno zna šta radi.

CLI može pokrenuti:

```text
flowos next
```

Kasnije agent može koristiti:

```text
GET /projects/{id}/next-action
```

---

# 8. Šesti veliki prijedlog — stvarno povezati agent adaptere sa sesijama

## Trenutno stanje

Postoje adapteri:

- Claude Code;
- Codex;
- DeepSeek.

Postoji i:

```text
AgentProcessLauncher
```

Međutim, iz pregledanog koda nije vidljiv potpun tok u kojem FlowOS:

```text
kreira sesiju
pokreće adapter
registruje PID
šalje heartbeat
hvata exit code
pokreće completion
```

## Prijedlog

Uvesti jedan autoritativni servis:

```text
AgentExecutionService
```

Odgovornosti:

```text
1. validira agent request
2. kreira worktree ako treba
3. kreira AgentSession
4. bira adapter
5. pokreće proces
6. registruje PID
7. pokreće heartbeat monitor
8. zapisuje stdout/stderr ili lokaciju loga
9. hvata exit code
10. poziva SessionCompletionService
```

## Adapter ugovor

Svi adapteri trebaju imati isti interface:

```python
class AgentAdapter(Protocol):
    def build_command(self, request: AgentRequest) -> list[str]: ...
    def capabilities(self) -> AdapterCapabilities: ...
    def normalize_result(self, ...) -> AgentResult: ...
```

## Dodatni prijedlog

Capabilities trebaju uključiti:

```text
supports_workdir
supports_noninteractive
supports_resume
supports_json_output
supports_model_selection
supports_system_prompt
supports_timeout
supports_streaming
```

## Dobitak

FlowOS tada stvarno upravlja agentima, a ne samo registruje sesije koje su pokrenute van njega.

---

# 9. Sedmi veliki prijedlog — napraviti „Session Command Center“

## Trenutni problem

Sesija je sada dominantno evidencioni zapis.

Nedostaje kompletan operativni pogled:

```text
šta je zadatak
šta agent trenutno radi
šta je izmijenio
da li je živ
da li je blokiran
koji dokaz je napravio
šta treba poslije
```

## Predloženi read model

```text
SessionOperationalView
```

Polja:

```text
session
project
task
plan_item
agent
model
worktree
branch
process_state
heartbeat_state
last_activity
changed_files
current_commit
verification
open_conflicts
report
recommended_action
```

## Statusi procesa

Odvojiti:

```text
session_status
process_status
work_state
```

Primjer:

```text
session_status = ACTIVE
process_status = ALIVE
work_state = IDLE
```

Umjesto da jedan `status` pokušava predstavljati sve.

---

# 10. Osmi veliki prijedlog — poboljšati heartbeat i procesni nadzor

## Trenutno stanje

Postoji `record_heartbeat()`.

To je dobro.

Ali iz pregledanog koda nije vidljivo da adapteri periodično pozivaju heartbeat.

## Prijedlog

Dodati:

```text
SessionMonitorService
```

Koji svakih npr. 15 sekundi provjerava:

- PID živ;
- heartbeat svjež;
- watcher aktivan;
- worktree postoji;
- proces exit code;
- posljednju aktivnost.

## Izvedena stanja

```text
HEALTHY
QUIET
UNRESPONSIVE
PROCESS_EXITED
WATCHER_FAILED
WORKTREE_MISSING
UNKNOWN
```

## Pravilo

Nedostatak file aktivnosti nije isto što i neaktivan proces.

`last_activity_at` i `last_heartbeat_at` moraju ostati semantički odvojeni.

---

# 11. Deveti veliki prijedlog — napraviti pravi reconciliation tok

## Trenutno stanje

Postoje modeli:

```text
ProjectWorkspaceState
ProjectReconciliationEvent
ExternalActivity
```

`ProjectResumeService` ih koristi.

Ali u pregledanom source-u nije vidljiv kompletan servis koji periodično:

- čita Git stanje projekta;
- poredi sa posljednjim poznatim stanjem;
- identifikuje vanjske izmjene;
- ažurira workspace state;
- kreira reconciliation event;
- generiše ExternalActivity.

## Prijedlog

Uvesti:

```text
ReconciliationService
```

Tok:

```text
1. GitStateReader.read_state()
2. poređenje sa ProjectWorkspaceState
3. klasifikacija razlike
4. atribucija FlowOS sesiji ako postoji dokaz
5. inače ExternalActivity
6. ProjectReconciliationEvent
7. ažuriranje workspace state
8. resume regeneracija
9. WebSocket event
```

## Kategorije

```text
HEAD_CHANGED
BRANCH_CHANGED
WORKTREE_DIRTY
UNTRACKED_FILES
FILES_CHANGED
EXTERNAL_COMMIT
FORCED_RESET
REBASE_DETECTED
UNKNOWN_CHANGE
```

## Dobitak

„Gdje si stao“ više ne zavisi od zastarjelog workspace state-a.

---

# 12. Deseti veliki prijedlog — automatizovati Project Resume regeneraciju

## Trenutni problem

`ProjectResumeService.regenerate()` postoji, ali nije jasno da se automatski poziva nakon svih relevantnih promjena.

## Pozivati nakon:

```text
plan aktiviran
plan item status promijenjen
sesija pokrenuta
sesija završena
verify završen
report kreiran
verdict postavljen
konflikt kreiran
konflikt riješen
reconciliation završen
worktree integrisan
```

## Prijedlog

Ne pozivati ručno iz svakog kontrolera.

Koristiti domain event:

```text
resume.rebuild_requested
```

ili centralni application service.

## Dodatna korekcija logike

Trenutni izbor `last_item` prolazi faze redom i u svakoj fazi iteme unazad.

To može izabrati stavku iz ranije faze prije relevantnije stavke u kasnijoj fazi.

Bolje pravilo:

```text
1. aktivna IN_PROGRESS stavka
2. BLOCKED sa najvećim prioritetom
3. posljednje updated_at
4. posljednje progress event vrijeme
```

Ne oslanjati se samo na sequence i status.

---

# 13. Jedanaesti veliki prijedlog — unaprijediti Task model iz CRUD-a u radni inbox

## Trenutno stanje

`TaskService` je osnovni CRUD.

Postoji:

- title;
- description;
- priority;
- status;
- plan_item_id;
- done_at.

Nema:

- due date;
- source;
- reason;
- blocked reason;
- estimate;
- next action;
- relation sa session outcome;
- automatske konverzije iz konflikta, reporta ili resume-a.

## Prijedlog

Task treba postati operativna jedinica.

Dodati:

```text
source_type
source_id
task_type
due_at
deferred_until
blocked_reason
assigned_agent_type
execution_mode
created_from_report_id
created_from_conflict_id
created_from_plan_item_id
next_action_json
```

## Automatsko kreiranje taska

Primjeri:

```text
verification FAIL
→ task „Popraviti neuspjelu verifikaciju“

conflict WRITE_WRITE
→ task „Riješiti konflikt sesija“

report NEEDS_WORK
→ follow-up task

external changes
→ reconciliation task
```

## Važno

Ne praviti odmah ClickUp klon.

Cilj je da Task bude izvršni most između:

```text
problem
→ odluka
→ sljedeća sesija
```

---

# 14. Dvanaesti veliki prijedlog — poboljšati kriterijume plana

## Trenutno stanje

Kriterijum ima:

- status;
- evidence artifact ID;
- verification summary;
- verified_at;
- verified_by.

To je dobar temelj.

## Nedostatak

Nema tipa kriterijuma i načina verifikacije.

## Dodati

```text
criterion_type
verification_command
verification_mode
required
weight
failure_policy
```

Primjeri tipa:

```text
COMMAND
FILE_EXISTS
TEST_RESULT
MANUAL_REVIEW
DIFF_CHECK
API_RESPONSE
SCREENSHOT
REPORT_FIELD
```

## Primjer

```json
{
  "criterion_key": "AC-3",
  "description": "Svi testovi prolaze",
  "criterion_type": "COMMAND",
  "verification_command": "python scripts/verify.py",
  "required": true
}
```

## Dobitak

FlowOS može sam provjeriti dio acceptance kriterijuma.

---

# 15. Trinaesti veliki prijedlog — povezati Verification sa plan kriterijumima

## Trenutno stanje

Verify pokreće cijeli `scripts/verify.py`.

Criterion ima evidence artifact ID, ali nije vidljiv automatski tok koji mapira verify rezultat na kriterijume.

## Prijedlog

Uvesti:

```text
CriterionVerificationService
```

Koji za svaki kriterijum:

- pokreće definisanu provjeru;
- čuva artifact;
- ažurira criterion status;
- zapisuje verified_by;
- pravi PlanProgressEvent;
- vraća zbirni rezultat.

## Zbirna odluka

```text
svi required kriterijumi PASSED
→ stavka može u VERIFIED

neki required FAILED
→ ostaje IMPLEMENTED ili ide NEEDS_WORK
```

---

# 16. Četrnaesti veliki prijedlog — uvesti „Verification Profile“

## Problem

Svaki projekat ima jedan `scripts/verify.py`.

To je praktično, ali ograničeno.

## Prijedlog

Projekt može imati profil:

```text
QUICK
STANDARD
FULL
RELEASE
```

Primjer:

```yaml
quick:
  - ruff check src
  - pytest tests/unit -q

standard:
  - python scripts/verify.py

release:
  - python scripts/verify.py
  - python scripts/build.py
  - smoke test exe
```

## Korist

- agent može brzo provjeriti tokom rada;
- završetak sesije koristi STANDARD;
- release koristi FULL/RELEASE;
- report zna tačno koji nivo je prošao.

---

# 17. Petnaesti veliki prijedlog — poboljšati worktree integracioni tok

## Trenutno stanje

Postoji:

- prepare integration;
- diff;
- changed files;
- verify;
- mark integrated;
- cleanup.

Nema potpunog domain toka.

## Predloženi tok

```text
WORKING
→ READY_FOR_REVIEW
→ VERIFIED
→ APPROVED_FOR_INTEGRATION
→ INTEGRATED
→ CLEANUP_PENDING
→ CLEANED
```

## Za prelaz u VERIFIED

Potrebno:

- verify PASS;
- nema otvorenog konflikta;
- worktree nije nestao;
- base commit nije neočekivano promijenjen.

## Za prelaz u INTEGRATED

Potrebno:

- korisnička potvrda;
- zapis target branch;
- merge/rebase/cherry-pick rezultat;
- integration commit SHA;
- post-integration verify.

## Ne predlažem odmah automatski merge

Prvo napraviti guided integration:

```text
prikaži diff
prikaži konflikte
prikaži verify
predloži komande
korisnik potvrđuje
FlowOS zapisuje rezultat
```

---

# 18. Šesnaesti veliki prijedlog — centralizovati statusne tranzicije

## Trenutni problem

Statusi su često stringovi:

```text
ACTIVE
IDLE
COMPLETED
IN_PROGRESS
IMPLEMENTED
READY
INTEGRATED
```

Validacija postoji u dijelovima, ali nije centralizovana.

## Prijedlog

Za svaki domain napraviti state machine:

```text
PlanItemStateMachine
SessionStateMachine
WorktreeStateMachine
ConflictStateMachine
ReportStateMachine
```

Svaka tranzicija treba vratiti:

```text
allowed
reason
required_preconditions
side_effects
```

## Primjer

```python
decision = plan_item_machine.can_transition(
    current="IMPLEMENTED",
    target="VERIFIED",
    context=evidence_bundle,
)
```

## Dobitak

- manje nelogičnih statusa;
- lakše testiranje;
- GUI može objasniti zašto dugme nije dostupno;
- audit je potpuniji.

---

# 19. Sedamnaesti veliki prijedlog — poboljšati session completion

## Trenutno stanje

`SessionCompletionService` radi mnogo važnih stvari:

- Git;
- verify;
- report;
- NO_COMMIT;
- status.

To je funkcionalno korisno, ali servis je već orkestrator više odgovornosti.

## Problem

Ako jedan korak padne:

- Git može pasti;
- verify može timeout;
- report može pasti;
- conflict zapis može pasti.

Trenutno je tok uglavnom jedna transakcija do kraja.

## Prijedlog

Pretvoriti u eksplicitni pipeline:

```text
LOAD_CONTEXT
CAPTURE_GIT_STATE
RUN_VERIFICATION
BUILD_EVIDENCE
CREATE_REPORT
DETECT_COMPLETION_CONFLICTS
UPDATE_PLAN_PROGRESS
REBUILD_RESUME
EMIT_EVENTS
FINALIZE_SESSION
```

Za svaki korak čuvati:

```text
status
started_at
completed_at
error
retry_count
```

## Minimalna implementacija

Ne treba odmah novi workflow engine.

Dovoljna je tabela:

```text
session_completion_steps
```

ili JSON stanje na sesiji.

## Dobitak

- retry samo neuspjelog koraka;
- nema ponovnog verify-a ako je već završen;
- jasna dijagnostika;
- GUI može prikazati „završetak sesije 6/9“.

---

# 20. Osamnaesti veliki prijedlog — izvještaj treba automatski puniti stvarnim dokazima

## Trenutno stanje

`ReportService` model je bogat.

Ali `SessionCompletionService.create_draft()` mu trenutno šalje uglavnom:

- summary;
- commit SHA;
- verification summary.

Ne šalje sve što već postoji.

## Automatski popuniti

```text
scope
task title
plan item
base commit
result commit
changed files
worktree
branch
open conflicts
verification artifact ID
where stopped
next step
resume preconditions
confidence
```

## Važno

Agent report ne treba biti samo tekst agenta.

Treba razlikovati:

```text
agent-provided fields
system-derived fields
user verdict
independent review
```

Dodati `source` po polju ili grupi.

---

# 21. Devetnaesti veliki prijedlog — napraviti nezavisni review kao funkciju

## Trenutno stanje

Model već ima:

```text
independent_review_summary
found_issues
rejected_options
conflicting_sources
```

Ali nema posebnog domain toka za review.

## Prijedlog

Uvesti:

```text
ReviewRun
```

Sa:

```text
reviewer_agent
reviewed_report_id
reviewed_commit
review_profile
verdict
findings
artifact_id
created_at
```

## Tok

```text
Agent A implementira
Agent B verifikuje
Korisnik prihvata
```

Ne dozvoliti da ista sesija sama sebi dodijeli nezavisnu provjeru bez jasne oznake.

---

# 22. Dvadeseti veliki prijedlog — Event Timeline treba postati projekcioni read model

## Trenutno stanje

Timeline spaja više tabela pri svakom čitanju.

To je u redu za mali broj podataka.

Kasnije može postati:

- spor;
- teško paginiran;
- nedosljedan;
- teško filtriran.

## Prijedlog

Uvesti append-only tabelu:

```text
timeline_events
```

Svaki relevantni domain događaj zapisuje jedan normalizovan event.

Polja:

```text
id
project_id
session_id
plan_item_id
event_type
level
source
summary
payload_json
occurred_at
```

## Dobitak

- jednostavan timeline;
- stabilna paginacija;
- WebSocket;
- projekat-wide aktivnosti;
- lakši search;
- budući RAG.

Za trenutni MVP ovo nije hitno, ali je prirodan naredni korak kada broj događaja poraste.

---

# 23. Funkcionalne slabosti koje se vide direktno iz koda

## 23.1 GUI composition root je placeholder

```text
src/flowos/gui/composition_root.py
```

još baca `NotImplementedError`.

To treba riješiti jer GUI bootstrap i wiring ne bi trebali živjeti direktno u `app.py`.

## 23.2 WebSocket nema publish pozive

EventBus postoji, ali bez `emit()` poziva ne daje funkcionalnu vrijednost.

## 23.3 TaskService je samo CRUD

Ne koristi FlowOS događaje za automatsko stvaranje zadataka.

## 23.4 Project Resume koristi relativno jednostavna pravila

Tekst je više statusni opis nego stvarna inteligentna preporuka.

## 23.5 Resume status zavisi od workspace state-a

Ako reconciliation nije redovno osvježavan, resume može biti zastario.

## 23.6 Agent adapteri nisu spojeni u jedan execution flow

Postoje klase, ali nije vidljiv autoritativni orchestration servis.

## 23.7 SessionService kreira sesiju prije worktree ekskluzivne provjere

Sesija se `add()` i `flush()` prije provjere zauzeća worktree-a.

Rollback na request nivou možda ukloni zapis, ali je čistije validirati sve prije kreiranja.

## 23.8 `record_heartbeat()` vraća završenu sesiju u ACTIVE

Kod radi:

```python
if session_obj.status not in ("ACTIVE", "IDLE"):
    session_obj.status = ACTIVE
```

To znači da zakašnjeli heartbeat može teorijski vratiti:

```text
COMPLETED
FAILED
INTERRUPTED
```

sesiju u `ACTIVE`.

Ovo treba zabraniti.

Heartbeat treba biti prihvaćen samo za:

```text
STARTING
ACTIVE
IDLE
```

Za terminalna stanja treba vratiti konflikt ili ignorisati heartbeat bez promjene statusa.

## 23.9 `TaskService.update_task()` ne čisti `done_at`

Ako se status promijeni iz `DONE` nazad u drugi status, `done_at` ostaje.

## 23.10 Project Resume blokirane stavke prvo čita globalno

Kod radi query svih `PlanItem.status == BLOCKED`, pa zatim filtrira plan preko relationshipa.

Bolje je joinom odmah filtrirati samo aktivni plan.

## 23.11 Project Resume ne koristi stvarni AgentReport

Komentar kaže da confidence uzima report u obzir, ali pregledani dio `regenerate()` dominantno koristi plan, session i workspace state.

Potrebno je potvrditi i direktno ugraditi report kvalitet u resume.

## 23.12 Globalni WebSocket EventBus je procesni singleton

Za lokalni jedan servis to može raditi, ali otežava testiranje i čist lifecycle.

Bolje ga injektovati kroz `app.state`.

## 23.13 Globalni exception handler skriva detalje

Korisnik dobija `Interna greška servisa`, što je dobro za sigurnost, ali log treba obavezno sadržati:

- correlation ID;
- request path;
- exception;
- session/project ID gdje postoji.

Correlation ID se trenutno vraća, ali u prikazanom handleru nije vidljivo logovanje samog exceptiona sa tim ID-em.

## 23.14 Background session completion pravi novi default engine

`create_app(engine=...)` može koristiti injektovani engine, ali background completion ponovo radi:

```python
create_sqlite_engine()
```

To može koristiti drugu bazu u testovima ili posebnim runtime konfiguracijama.

Treba koristiti isti `app.state.session_factory`.

## 23.15 Lifespan i watcher takođe kreiraju default engine

Isti problem postoji u watcher lifecycle-u.

Treba imati jedan autoritativni engine po app instanci.

---

# 24. Preporučeni prioriteti

# P0 — stabilnost i zatvaranje postojećih funkcija

## P0.1 Jedan app engine/session factory

Popraviti:

- background completion;
- lifespan;
- watcher callback;
- API dependencies.

Sve mora koristiti isti engine iz composition root-a.

## P0.2 Heartbeat terminalna stanja

Zabraniti vraćanje završene sesije u ACTIVE.

## P0.3 Session creation validacija prije flush-a

Prije kreiranja sesije provjeriti:

- project postoji;
- task pripada projektu;
- plan item pripada projektu;
- worktree pripada projektu;
- worktree nije zauzet;
- branch/worktree kombinacija je validna.

## P0.4 Automatski resume refresh

Pozvati resume rebuild nakon glavnih domain događaja.

## P0.5 Stvarni event emit

Povezati bar:

```text
session.completed
conflict.created
verification.completed
plan_item.updated
resume.updated
```

## P0.6 Dovršiti GUI composition root

Ukloniti placeholder.

---

# P1 — ključna funkcionalna vrijednost

## P1.1 Project State Engine

Jedinstveni status projekta i next action.

## P1.2 Plan execution workflow

Automatske tranzicije:

```text
session → verify → report → plan status → verdict
```

## P1.3 Evidence Bundle

Jedan prikaz svih dokaza za stavku.

## P1.4 AgentExecutionService

Jedan tok pokretanja i nadzora adaptera.

## P1.5 ReconciliationService

Stvarno osvježavanje ProjectWorkspaceState.

## P1.6 Session Command Center

Jedinstveni operativni read model.

---

# P2 — produktivnost i automatizacija

## P2.1 Automatski taskovi iz problema

- failed verify;
- conflict;
- NEEDS_WORK;
- external changes.

## P2.2 Criterion verification

Automatska provjera acceptance kriterijuma.

## P2.3 Verification profiles

QUICK, STANDARD, FULL, RELEASE.

## P2.4 Guided integration workflow

Review → verify → approve → integrate → cleanup.

## P2.5 Independent review model

Poseban review entitet i reviewer agent.

---

# P3 — skaliranje i napredne mogućnosti

## P3.1 Timeline projection

Jedinstvena event tabela.

## P3.2 Event outbox

Pouzdani WebSocket događaji.

## P3.3 RAG nad dokazima i reportima

Kasnije omogućiti pitanja:

```text
Zašto je FLOW-403 prihvaćen?
Koji agent je mijenjao ovaj fajl?
Koji test je zadnji padao?
Gdje je projekat stao prije tri dana?
```

## P3.4 Policy engine

Pravila po projektu:

```text
nema integracije bez verify PASS
nema druge writer sesije u istom worktree-u
kritični konflikt zahtijeva korisničku odluku
```

---

# 25. Preporučeni sljedeći razvojni paket

Ne bih odmah implementirao sve iz dokumenta.

Najbolji naredni paket rada bio bi:

```text
FlowOS Functional Closure — Iteracija 1
```

Obuhvat:

```text
1. Jedan engine/session factory
2. Siguran heartbeat
3. Validacija session creation prije flush-a
4. Automatski resume rebuild
5. WebSocket eventi za pet ključnih događaja
6. Strukturisani NextAction
7. ProjectState endpoint
```

## Novi endpointi

```text
GET /projects/{project_id}/state
GET /projects/{project_id}/next-action
POST /projects/{project_id}/resume/regenerate
```

## Novi događaji

```text
project.state.updated
project.resume.updated
session.completed
verification.completed
conflict.created
```

## Zašto ovaj paket

On povezuje već implementirane funkcije bez otvaranja prevelikog novog scope-a.

Nakon njega GUI dobija stvarne podatke za:

- „Gdje si stao“;
- „Sljedeći korak“;
- upozorenja;
- real-time refresh;
- status projekta.

---

# 26. Mjerljivi kriterijumi uspjeha

FlowOS funkcionalno napreduje kada korisnik može uraditi ovaj tok bez ručnog sastavljanja informacija:

```text
1. Otvori projekat
2. Vidi gdje je stao
3. Vidi tačno jednu preporučenu sljedeću akciju
4. Pokrene sesiju povezanu sa plan stavkom
5. FlowOS prati heartbeat i aktivnosti
6. FlowOS otkrije konflikt
7. Sesija završi
8. FlowOS pokrene verify
9. Kreira report i evidence
10. Promijeni status plan stavke
11. Traži korisnički verdict
12. Ažurira resume
13. Ponudi sljedeću akciju
```

Dok ovaj tok nije zatvoren, dodavanje novih ekrana daje manju vrijednost od povezivanja postojećih servisa.

---

# 27. Konačna procjena

## Šta je dobro

FlowOS već ima:

- smislen domain model;
- dobru razdvojenost servisa;
- append-only audit dijelove;
- bogat plan model;
- worktree izolaciju;
- konfliktni sistem;
- verification artifacte;
- report model;
- project resume;
- timeline;
- adaptere;
- GUI i CLI ulaze.

To nije više samo ideja ni maketa.

## Šta nedostaje

Najviše nedostaje:

```text
automatsko povezivanje posljedica
```

Odnosno:

```text
događaj
→ odluka
→ promjena stanja
→ dokaz
→ sljedeća akcija
```

## Najvažnija preporuka

Ne širiti FlowOS odmah na deset novih modula.

Prvo zatvoriti tri vertikalna toka:

```text
A. PlanItem → Session → Verify → Report → Verdict
B. Watcher → Activity → Conflict → Resolution
C. Git state → Reconciliation → Resume → Next Action
```

Kada ta tri toka budu pouzdana, FlowOS će postati stvarni lični operativni sistem za agentski razvoj, a ne samo kvalitetan preglednik razvojnih podataka.
