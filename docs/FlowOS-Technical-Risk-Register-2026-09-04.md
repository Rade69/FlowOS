# FlowOS — Technical Risk Register i rezultati dubljeg istraživanja

**Datum:** 2026-09-04  
**Status:** istraživanje / arhitektonske odluke  
**Namjena:** trajna tehnička referenca za buduće FlowOS taskove  
**Napomena:** ovaj dokument ne predstavlja plan implementacije niti mijenja kod. Cilj je da sačuva potvrđene nalaze, procjene rizika i pravila koja treba koristiti kada odgovarajući problem postane predmet zasebnog taska.

---

## 1. Osnovni princip FlowOS-a

FlowOS je **lokalni deterministički human control plane za agent-assisted development**.

Ključna pravila:

- AI/agent radi posao.
- FlowOS pamti, povezuje, provjerava i prikazuje stanje.
- Čovjek donosi konačnu odluku.
- Agentov iskaz nije automatski činjenica.
- Dokaz ima prednost nad tvrdnjom.
- Trigger nije source of truth.
- Derived state nije source of truth.
- Automatizovati deterministički rad deterministički.
- LLM koristiti samo gdje stvarno postoji problem zaključivanja.

Canonical workflow:

`Idea/Need → Alignment/Research → Spec/Task Contract → Implementer → Evidence → Independent Review → Findings/Fix → Human Decision → Integration → Remote Verify`

---

# 2. Authority map — ko je autoritet za koju činjenicu

Ovo treba postati eksplicitna FlowOS konvencija.

| Pitanje / činjenica | Autoritativni izvor |
|---|---|
| Trenutni Git `HEAD` | Git |
| Trenutni branch | Git |
| Dirty stanje worktree-a | Git |
| Da li fajl postoji | Filesystem |
| Da li proces postoji | OS |
| Šta agent tvrdi da je uradio | AgentReport |
| Da li je test stvarno izvršen/prošao | Verification artifact / stvarni test output |
| Da li je Human ACCEPT dat | FlowOS DB |
| Koji plan je ACTIVE | FlowOS DB |
| Trenutni canonical Task/Session/Binding state | FlowOS DB |
| Istorijski audit | Workflow Ledger / audit modeli |
| „Da li je bezbjedno nastaviti?“ | izvedeni FlowOS zaključak |

**Pravilo:** `source of truth ≠ observation ≠ derived state`.

---

# 3. Temeljni tehnički principi

## D1 — Identity

Svaka važna stvar mora imati stabilan identitet:

- project_id
- task_id
- session_id
- report_id
- worktree_id
- verification/evidence identity
- event/idempotency key
- request generation / request identity
- process identity

PID sam po sebi nije dovoljan kao trajni identitet procesa.

## D2 — Freshness

FlowOS mora znati:

- kada je nešto opaženo;
- iz kojeg snapshot-a/generacije;
- da li je informacija još aktuelna;
- da li je rezultat izveden iz starije opservacije.

Važni koncepti:

- `observed_at`
- `reconciled_at`
- `generation`
- `request_id`
- `snapshot fingerprint`
- `stale / current / unknown`

## D3 — Atomicity

Kompleksna state promjena koja predstavlja jedan poslovni događaj mora biti jedna transakcija.

Primjer:

`activate plan → supersede old → activate new → regenerate resume → append ledger → commit`

Ne smije ostati parcijalno stanje.

## D4 — Single transaction owner

Za svaki use case treba postojati jedan vlasnik transakcije.

Poželjno:

- HTTP dependency / Unit of Work drži transakcionu granicu;
- service smije `flush`;
- controller ne treba nasumično `commit()` ako već postoji spoljašnji transaction owner.

## D5 — Trigger ≠ truth

Watcher, WebSocket, timer, agent report ili UI event ne treba da kažu šta je istina.

Oni treba samo da kažu:

> „Možda se nešto promijenilo — ponovo pročitaj autoritativni izvor.“

## D6 — Reconciliation ne smije automatski „heal-ovati“ Git

FlowOS treba da:

`Observe → Compare → Classify → Evidence → Human Decision`

Ne treba po defaultu da:

- resetuje branch;
- vraća commit;
- briše fajlove;
- automatski „popravlja“ worktree.

Human control ostaje granica.

---

# 4. Risk Register

## R1 — Async GUI project-context race

**Severity:** HIGH

### Potvrđeno

Qt networking je asinhron. Odgovori mogu stići drugačijim redoslijedom od requestova.

Prvobitni `project_id` guard rješava:

`A request → switch B → late A response`

ali ne rješava:

`A request N → A request N+1 → N+1 stigne → N stigne kasnije`

niti:

`A → B → A → stari A response`

### Zaključak

Samo `project_id` nije dovoljan.

Potrebno je:

`project_id + generation/request identity`

### Implementacioni princip

Svi requestovi jednog kompletnog project-data refresha dijele istu monotonu generation vrijednost.

Render samo ako:

`project_id == active_project_id AND generation == active_generation`

### FLOW-1201 rezultat

Ovaj princip je implementiran kroz `(project_id, generation, payload)`.

Dodatno je potvrđen problem sa partial refreshom: globalna generation smije rasti samo kada se pokreće kompletan project-data batch.

### Pravilo

**Globalna project generation pripada kompletnom snapshot/batch-u, ne pojedinačnom resursu.**

---

## R2 — GUI CompositionRoot može postati god object

**Severity:** MEDIUM-HIGH

### Potvrđeno

`FlowOsGui` već drži:

- aktivni project context;
- controller wiring;
- refresh;
- WebSocket;
- navigation;
- render orchestration;
- backend startup/shutdown integracije.

### Procjena

Još nije opravdan veliki refactor samo radi estetike.

### Odluka

- Ne uvoditi DI framework.
- Zadržati eksplicitni composition root.
- Ekstrahovati male coordinatore tek kada cross-screen orchestration postane teško razumljiva ili teško testabilna.

Mogući budući kandidati:

- `ProjectContextCoordinator`
- `TaskCoordinator`

Ali samo kada stvarno nastane potreba.

---

## R3 — Canonical state i invariants

**Severity:** HIGH

### Problem

FlowOS kombinuje:

- Plan
- PlanItem
- Task
- Session
- Report
- Review
- Binding
- Worktree
- Resume
- Workflow Ledger
- Git stanje
- Human decision

Bez jasnih authority pravila lako nastaje nekonzistentnost.

### Potvrđen primjer

FLOW-1106 je pokazao da aktivacija plana nije bila kompletna dok nije atomarno obuhvatila:

- jedan ACTIVE plan;
- prethodni ACTIVE → SUPERSEDED;
- Resume refresh;
- PLAN_ACTIVATED ledger event;
- DB invariant.

### Odluka

- canonical relational tables ostaju source of truth;
- derived state se regeneriše iz canonical izvora;
- hard invariants štititi DB constraintima gdje je moguće;
- optimistic versioning koristiti samo gdje stvarna concurrent stale-update opasnost postane mjerljiva;
- ne uvoditi Event Sourcing.

---

## R4 — Git/filesystem reality vs FlowOS DB

**Severity:** VERY HIGH dugoročno

### Ispravan obrazac

Najkorisniji uzor je Kubernetes-style reconciliation:

`Observe actual state → Snapshot → Compare → Classify → Evidence → Human Decision`

### Predložene klase

- `CURRENT`
- `EXPECTED_CHANGE`
- `DRIFT`
- `CONFLICT`
- `UNKNOWN`

Uz `reason code`, npr:

- `HEAD_CHANGED_EXTERNALLY`
- `ACTIVE_SESSION_WORKTREE_MISSING`
- `BRANCH_CHANGED`
- `OBSERVATION_FAILED`

### Važno

Vanjski event ne smije biti source of truth.

Ako se event izgubi, kasniji reconciliation mora moći obnoviti tačno stanje.

---

## R5 — SQLite migrations / backup / recovery

**Severity:** MEDIUM-HIGH

### Potvrđeno

SQLite migracije često zahtijevaju batch `create-copy-drop-rename` obrazac.

`PRAGMA integrity_check` ne provjerava foreign keys.

Za FK provjeru treba posebno:

`PRAGMA foreign_key_check`

### Standardni migration gate

1. provjeri schema/alembic head;
2. napravi konzistentan SQLite backup;
3. izvrši migraciju;
4. potvrdi alembic head;
5. `PRAGMA integrity_check`;
6. `PRAGMA foreign_key_check`;
7. provjeri FlowOS application invariants;
8. tek onda normalan start servisa.

### High-risk migration opcija

Za rizične data/schema migracije može se koristiti **shadow migration**:

`live DB → backup/snapshot → shadow DB → migrate → full verify → zamjena`

Ne koristiti za svaku malu migraciju.

### Python compatibility rizik

Python `sqlite3` transaction-control ponašanje se mijenja kroz nove Python verzije.

**Pravilo:** Python runtime upgrade mora imati poseban SQLite transaction/migration compatibility test.

---

## R6 — Event ordering, duplicates i idempotency

**Severity:** MEDIUM sada / HIGH ako causal ordering postane business-critical

### Potvrđeno

Workflow Ledger već ima:

- unique `idempotency_key`;
- `occurred_at`;
- `recorded_at`;
- stabilan display ordering.

### Važna razlika

`recorded_at + id` daje stabilan prikaz, ali ne garantuje stvarni causal ordering.

### Odluka

- zadržati unique idempotency keys;
- držati canonical state + audit event u istoj DB transakciji gdje correctness to zahtijeva;
- ne uvoditi Kafka/Outbox/EventStore sada;
- aggregate sequence/version dodati samo ako consumers počnu zavisiti od strogog redoslijeda.

### Workflow Ledger odluka

**Ledger ostaje audit/evidence, ne Event Store i ne source of truth.**

Event Sourcing se svjesno odbacuje za trenutni FlowOS.

---

## R7 — SQLite concurrency i multi-agent load

**Severity:** MEDIUM, potrebno empirijski potvrditi

### Trenutno stanje

FlowOS koristi SQLite WAL i SQLAlchemy pool:

- `pool_size=1`
- `max_overflow=0`

To praktično znači jednu DB konekciju za read i write tokove.

### Potvrđen simptom

Kod već sadrži komentar da otvorena listing session može držati jedinu konekciju i izazvati `QueuePool TimeoutError`.

### Važna posljedica

Trenutni model ne koristi potpuno WAL prednost više paralelnih čitača.

Ali slijepo povećanje pool-a nije automatsko rješenje, jer SQLite i dalje ima jednog writera.

### Ne donositi preranu odluku

Ne prelaziti na PostgreSQL sada.

### Prvo uraditi concurrency probe

Simulirati:

- GUI read fan-out:
  - Plan
  - Resume
  - Sessions
  - Timeline
  - Worktrees
- watcher burst;
- agent report ingestion;
- 2–5 bliskih session completion operacija;
- reconciliation;
- Human action (accept/activate/update).

### Mjeriti

- pool checkout wait;
- transaction duration;
- query duration;
- HTTP latency;
- `QueuePool timeout`;
- `SQLITE_BUSY`;
- rollback count;
- WAL/checkpoint stanje.

### Fail kriteriji

- izgubljen/parcijalan canonical write;
- deadlock;
- QueuePool timeout pod realnim lokalnim loadom;
- ponavljani `database is locked`;
- GUI readovi koji redovno čekaju sekunde zbog background writea;
- WAL koji kontinuirano raste bez checkpoint napretka.

### Ako postojeći model postane bottleneck

Prvi kandidat:

`concurrent READ connections + serialized whole-transaction WRITE path`

Ne queue pojedinačnih SQL naredbi.

Write serialization mora obuhvatiti cijeli Unit of Work / transaction.

---

## R8 — GUI test infrastructure

**Severity:** MEDIUM

### Potvrđeno

`pytest-qt` teardown poziva `.close()` nad widgetima koje je `qtbot.addWidget()` registrovao.

Ako production `closeEvent()` otvara modalni dialog, test može deterministički da visi.

FLOW-1201 je to već dokazao.

### Odluka

- production `closeEvent` ne mijenjati samo radi testova;
- test fixture može neutralisati modal;
- preferirati widget/controller testove i stvarni Qt signal path;
- OS mouse/screenshot automatizacija nije correctness gate.

### Deterministički async harness

Dugoročno napraviti mali fake/controlled Qt transport koji dozvoljava testu da odredi redoslijed odgovora:

`request A1 → request A2 → complete A2 → complete A1`

To omogućava pouzdane stale-response testove bez:

- `sleep`;
- pravog HTTP servera;
- OS miša;
- race zavisnog od brzine računara.

---

## R9 — Process identity / PID reuse

**Severity:** MEDIUM dugoročno, HIGH prije automatizovanog process lifecyclea

### Potvrđeno

Agent scanner trenutno bilježi:

- PID
- agent_type
- image
- detected_at

PID nije trajni identitet procesa.

Windows može ponovo koristiti PID nakon završetka procesa.

### Rizik

FlowOS ne smije zaključiti:

`PID postoji → to je ista session/process instanca`

ako je PID zapamćen duže vrijeme.

### Minimalni sigurniji identitet

- `pid`
- `process_creation_time`

Poželjno dodatno:

- executable identity;
- command fingerprint;
- process handle kada FlowOS sam pokreće proces.

### Pravilo

Prije bilo kakvog automatskog:

- kill;
- reconnect;
- auto-complete;
- ownership zaključka;
- „session još živa?“ provjere

process identity mora biti jači od samog PID-a.

---

# 5. Konkretni nalazi u trenutnom reconciliation kodu

Ovo nisu više samo teorijski rizici.

## F1 — HIGH: Git read failure može postati lažno `CURRENT`

### Trenutno ponašanje

`GitStateReader._run_git()` na grešku vraća prazan string.

Tada `read_state()` može proizvesti:

- `commit_sha = ""`
- `branch = ""`
- `is_dirty = False`

bez jasnog signala da Git čitanje nije uspjelo.

### Problem

`ReconciliationService` očekuje da će Git read failure biti exception/error.

Pošto se greška proguta, reconciliation može zaključiti da nema promjene i postaviti:

`reconciliation_status = CURRENT`

i osvježiti `last_reconciled_at`.

### Rizik

FlowOS može prikazati lažnu sigurnost:

> „CURRENT“

iako zapravo ne zna Git stanje.

### Odluka

Git observation failure mora postati:

- `UNKNOWN`
- ili `OBSERVATION_FAILED`

Nikada `CURRENT`.

---

## F2 — MEDIUM/HIGH: `git status --porcelain=v2 -z` parser je netačan

### Dobar dio

Izbor `--porcelain=v2 -z` je ispravan jer je machine-readable.

### Problem

Trenutni parser dijeli record sa:

`entry.split(" ", 1)`

i tretira ostatak kao pathname.

Za tracked v2 record to nije pathname, nego cijeli ostatak recorda sa statusom/modovima/hash vrijednostima.

Rename/copy record ima još kompleksniji NUL format.

### Posljedica

`changed_files` evidence nije pouzdan za tracked promjene.

### Potrebni fixture testovi

- modified;
- staged;
- deleted;
- renamed;
- copied;
- unmerged;
- untracked;
- filename sa razmakom.

### Odluka

Ostati na porcelain v2, ali implementirati parser prema Git specifikaciji.

---

## F3 — MEDIUM: stabilno dirty stanje može proizvoditi ponovljene EXTERNAL_CHANGES evente

### Trenutno ponašanje

Ako `changed_files` nije prazan:

- dodaje se `FILES_CHANGED`;
- `changes_detected = True`.

Ne provjerava se da li je dirty snapshot zaista drugačiji od prošlog.

### Scenario

`file.py modified → reconcile → EXTERNAL_CHANGES`

120 sekundi ništa novo.

`file.py i dalje modified → reconcile → opet EXTERNAL_CHANGES`

### Posljedice

- dupli reconciliation eventi;
- ponovljeni Resume regeneration;
- nepotrebni WebSocket refreshi;
- audit koji sugeriše promjene koje se zapravo nisu desile.

### Odluka

Reconciliation mora porediti:

`snapshot N vs snapshot N-1`

a ne samo:

`da li trenutno postoji dirty file`.

Već postoji `last_known_dirty_fingerprint`; treba ga koristiti u odluci.

---

## F4 — MEDIUM: `last_observed_at` i `last_reconciled_at` nisu pravilno razdvojeni u praksi

Model već ima oba polja.

Ali GitState ima `observed_at`, dok reconciliation uglavnom ažurira samo `last_reconciled_at`.

### Semantika

`last_observed_at`  
= kada je autoritativni izvor stvarno uspješno pročitan.

`last_reconciled_at`  
= kada je izvršen compare/classification pokušaj.

To nisu iste stvari.

### Odluka

- uspješan Git read → update `last_observed_at`;
- reconciliation attempt/result → update `last_reconciled_at`;
- observation failure ne smije izgledati kao uspješno opažanje.

---

# 6. Watcher research

## Potvrđeno

Filesystem watcher nije kompletan istorijski audit.

Platforme mogu izgubiti evente:

- Windows `ReadDirectoryChangesW` može izgubiti informacije pri buffer overflowu;
- Linux `inotify` queue može overflowovati.

Naš watcher dodatno:

- debounce 500 ms;
- čuva posljednji event po putanji;
- ignoriše `.git`;
- nema `on_moved`;
- prati create/modify/delete.

### Odluka

Watcher treba tretirati kao:

`trigger / hint`

ne kao:

`canonical evidence of every filesystem transition`.

### Ispravan obrazac

`watcher event → enqueue/re-read → current-state observation → reconciliation`

Periodični Git reconciliation ostaje važan backstop.

---

# 7. Reconciliation model koji preporučujemo

```text
Trigger
  │
  ▼
Observe authoritative source
  │
  ├─ FAIL ──> UNKNOWN / OBSERVATION_FAILED
  │
  ▼
Immutable/identified snapshot
  │
  ▼
Compare snapshot N vs N-1
  │
  ▼
Classify
  │
  ├─ CURRENT
  ├─ EXPECTED_CHANGE
  ├─ DRIFT
  ├─ CONFLICT
  └─ UNKNOWN
  │
  ▼
Evidence / Ledger
  │
  ▼
Human decision when required
```

Poželjni metadata elementi:

- `project_id`
- `observation_id`
- `generation`
- `observed_at`
- `source`
- `source_fingerprint`
- `status`
- `reason`
- `message`

---

# 8. Šta svjesno NE uvodimo sada

Da se istraživanje ne pretvori u nepotreban redizajn:

## Ne uvoditi sada

- PostgreSQL
- Kafka
- RabbitMQ
- Temporal
- EventStore/Kurrent
- Event Sourcing
- Transactional Outbox
- DI framework
- veliki CompositionRoot refactor
- per-resource async framework ako global batch generation radi
- automatski Git self-healing
- ručni WAL checkpoint daemon
- write queue po pojedinačnim SQL naredbama

Sve ovo se ponovo procjenjuje samo ako konkretan problem i test pokažu potrebu.

---

# 9. Prioritet budućih zasebnih taskova

Ovo nije rollout plan, nego redoslijed tehničke važnosti kada odgovarajući rad dođe na red.

## P1 — Reconciliation correctness

Obuhvatiti:

- Git read failure → UNKNOWN;
- pravilni porcelain v2 parser;
- snapshot/fingerprint compare;
- spriječiti duple dirty evente;
- ispravno `observed_at` vs `reconciled_at`.

Ovo je najvažnije prije nego Current State/Reconciliation postane glavni source korisničkog povjerenja.

## P2 — SQLite concurrency probe

Prije bilo kakve DB arhitektonske promjene.

Cilj:

- izmjeriti stvarni lokalni load;
- dokazati da li `pool_size=1` postaje bottleneck;
- tek onda odlučivati o read pool / serialized writer modelu.

## P3 — Deterministički Qt async test harness

Napraviti controlled/fake API/network transport za:

- response reordering;
- delays;
- cancellation;
- stale generations;
- error injection.

## P4 — Process identity hardening

Prije nego FlowOS počne agresivnije upravljati agent procesima.

Minimalno:

`PID + process creation time`

## P5 — Migration/recovery standard

Formalizovati:

- backup;
- migrate;
- integrity;
- FK;
- invariants;
- rollback/recovery;
- Python runtime compatibility gate.

---

# 10. Tehnički sažetak

Najvažnija riječ nije „agent“.

Najvažniji tehnički pojmovi za FlowOS postaju:

- **IDENTITY**
- **AUTHORITY**
- **FRESHNESS**
- **OBSERVATION**
- **ATOMICITY**
- **IDEMPOTENCY**
- **SERIALIZATION**
- **EVIDENCE**
- **HUMAN DECISION**

Ako FlowOS pravilno zna:

1. **šta je stvarna činjenica;**
2. **ko je autoritet za nju;**
3. **kada je opažena;**
4. **kojoj generaciji/snapshot-u pripada;**
5. **da li je rezultat još aktuelan;**
6. **koja promjena je atomarna;**
7. **koji događaj je duplikat;**
8. **šta je samo agentova tvrdnja;**

onda Git drift, stale GUI response, session state, report ingestion, verification, Resume i Current State prestaju biti odvojeni ad-hoc problemi.

Postaju isti opšti model:

`TRIGGER → OBSERVATION → VALIDATION → IDENTITY → COMPARE → CLASSIFY → EVIDENCE → HUMAN DECISION`

---

# 11. Status dokumenta i implementacije

- Ovaj dokument je istraživački/risk register.
- Ne predstavlja ACCEPT za bilo koji nezavršen task.
- Ne mijenja FLOW-1201 acceptance status.
- Nijedan ovdje navedeni budući rizik ne treba automatski ubacivati u tekući task.
- Svaki konkretni fix treba dobiti svoj jasan task contract, implementera i nezavisni review.
