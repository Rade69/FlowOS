# FlowOS — kanonski plan daljeg razvoja i agentskog rada v1.0

**Status:** ACTIVE / CANONICAL  
**Datum:** 2026-09-02  
**Repo:** `Rade69/FlowOS`  
**Product architecture source:** `FlowOS-novi-objedinjeni-detaljan-plan-razvoja-v4.4-deterministicki.md`  
**Operational workflow source:** prilagođeni principi iz `AI_CAMPAIGN_STUDIO_AGENT_WORKFLOW.md`  
**Glavni arhitekta / koordinator:** ChatGPT  
**Human Owner:** korisnik

> **AI radi. FlowOS pamti, povezuje i dokazuje. Čovjek odlučuje.**

---

# 0. Svrha

FlowOS već ima detaljan produktni roadmap v4.4 i stvarno implementiran backend. Ovaj dokument spaja:

1. stvarno stanje GitHub repoa;
2. v4.4 produktnu granicu;
3. način rada sa eksternim coding agentima;
4. risk-tier i review pravila;
5. redoslijed narednih taskova;
6. način na koji se task priprema, implementira, provjerava, ispravlja i prihvata.

Ovaj dokument je **kanonski plan izvršenja**. Ne zamjenjuje v4.4 kao produktni roadmap; određuje kako se v4.4 realizuje nad stvarnim kodom.

---

# 1. Red autoriteta

Kada se izvori ne slažu:

```text
1. Eksplicitna odluka Human Ownera
2. Ovaj kanonski plan izvršenja
3. FlowOS v4.4 product roadmap
4. Task Contract konkretnog taska
5. Stvarni kod / Git / test output / runtime evidence
6. AgentReport / reviewer report
7. Stari planovi i istorijska dokumentacija
```

Važno:

```text
AgentReport = claim/evidence container
Git/test/runtime = provjerljive činjenice
Human Owner = konačni authority za prihvatanje
```

Ako dokument kaže jedno, a kod drugo, kod je činjenica o trenutnom stanju i dokument se mora uskladiti.

---

# 2. Zaključana product granica

FlowOS ostaje:

> **lokalni, deterministički human control plane za agent-potpomognuti razvoj.**

FlowOS smije:

```text
READ
INGEST
CORRELATE
VERIFY
DISPLAY
EXPORT
```

FlowOS ne smije kao core odgovornost:

```text
START AGENT
PROMPT AGENT
SELECT MODEL
DELEGATE TASK
RETRY AGENT
CONTROL AGENT PROCESS
ORCHESTRATE SWARM
AUTO-MERGE PROTECTED TARGET
```

Trajne invarijante:

```text
nema internog LLM-a
nema LLM API zaključivanja u core-u
nema agent orchestrationa
nema automatskog prompt dispatcha
nema model routera kao FlowOS odgovornosti
nema hidden source of truth
Git je authority za kod, ali commit ≠ acceptance
Task ≠ Session ≠ Worktree ≠ Evidence ≠ Review ≠ Decision
claim ≠ proof
proof ≠ acceptance
heuristic ≠ fact
session end ≠ task completion
UNKNOWN je legitimno stanje
IMPLEMENTED ≠ VERIFIED ≠ ACCEPTED
```

---

# 3. Stvarni repo baseline

**Verifikovani remote baseline 2026-09-02:**

```text
main = 08f915c08c2fb3eb4eb2a978faca7d6b1d4781e5
```

Potvrđeno:

1. Architecture guard je blocking dio `scripts/verify.py`.
2. Posljednji architecture commit prijavljuje `8/8 PASS`.
3. GUI ima odvojene controllere: `PlanController`, `AgentsController`, `SystemController`, `OverviewController`.
4. `GuiApiClient.import_plan()` već šalje `markdown_text`.
5. Backend import endpoint još prima sirovi `body: dict`; Pydantic `PlanImportRequest` nije implementiran.
6. `_find_worktree()` još koristi `wt.path == path or wt.path.startswith(path)`; FLOW-1110 je stvarni otvoreni problem.
7. README i dio repoa još opisuju staru orchestration/launcher filozofiju.
8. U repou postoje tragovi starih `execution/jobs/approvals/usage` smjerova.
9. Pasivni `agent_scanner` postoji i kompatibilan je sa v4.4.
10. v4.4 još nije kanonski commitovan u remote repo; u `docs/` je posljednja objedinjena verzija v4.1.

Zaključak:

> Kod je dovoljno zreo za praktičan nastavak, ali repo i dokumentacija još nisu potpuno usklađeni sa pasivnom v4.4 granicom.

---

# 4. Uloge

## Human Owner

Konačni autoritet za:

- product scope;
- prioritet;
- prihvatanje kompromisa;
- HIGH risk acceptance;
- konačni merge/integration kada nije unaprijed delegiran.

## Glavni arhitekta / koordinator — ChatGPT

Odgovornosti:

- provjerava stvarni GitHub prije novog taska kada stanje može biti promijenjeno;
- drži v4.4 granice;
- određuje sljedeći task;
- klasifikuje risk;
- pravi Task Contract;
- pravi **jedan** zaključan prompt za jednog agenta;
- određuje implementera i reviewer profil;
- traži GitNexus evidence kada je potrebno;
- pregleda stvarni remote diff, ne samo agent summary;
- razlikuje potvrđeno / procjenu / nepoznato;
- kreira uski fix prompt za konkretan finding;
- ne širi scope u fix rundi;
- poslije pusha provjerava remote SHA i stvarne fajlove;
- predlaže ACCEPT / FIXES REQUIRED / REJECT;
- za HIGH task sintetizuje Codex + Claude review prije Human Owner odluke.

Pravilo:

> **Jedna akcija = jedan korak.**

## Implementeri

Kandidati:

```text
Crush
Pi
MiniMax
Codex
Claude
```

Implementer:

- radi samo unutar `allowed_paths`;
- slijedi Task Contract;
- ne mijenja arhitekturu bez contract-deviation procedure;
- ne širi scope;
- pokreće tačno tražene testove;
- daje doslovan output;
- prijavljuje `OUT_OF_SCOPE_FINDING`;
- provjerava touched-file header pravilo;
- piše implementer report;
- commit/push radi samo ako prompt to eksplicitno dozvoli.

Default:

> implementer smije pushovati samo **task branch**, nikad `main`, osim ako Human Owner eksplicitno naredi drugačije.

## Reviewer profili

### Codex

Prioritet:

- da li test stvarno dokazuje acceptance;
- negative/adversarial test;
- regression;
- edge cases;
- concurrency/state;
- migration/rollback;
- test loopholes;
- blast radius.

### Claude

Prioritet:

- `View → Controller → Services`;
- dependency direction;
- source-of-truth duplication;
- lifecycle/composition;
- security boundary;
- v4.4 passive-agent granica;
- over-engineering;
- integration sa ostatkom FlowOS-a.

### Glavni arhitekta

Prioritet:

- stvarni GitHub diff;
- usklađenost sa Task Contractom;
- produktna granica;
- dokaz da je task riješio pravi problem;
- da se ne uvodi novi dug bez potrebe;
- konačna sinteza reviewa.

---

# 5. Risk tier i review politika

## LOW

Primjeri: dokumentacija, izolovan tekst/resource, mali test, lokalna prezentaciona korekcija.

Tok:

```text
Task Contract
→ implementer
→ targeted verification
→ push task branch
→ glavni arhitekta review
→ Human Owner merge odluka ili unaprijed delegirana merge akcija
→ post-merge provjera
```

GitNexus nije obavezan samo uz eksplicitno obrazloženje.

## MEDIUM

Primjeri: use-case, shared service, read-model, worktree identitet, API contract, GUI Controller/Service integration, provenance/evidence semantics.

Tok:

```text
GitNexus pre-impact
→ Task Contract
→ implementer
→ targeted tests
→ relevant regression
→ GitNexus detect-changes / impact evidence
→ push task branch
→ glavni arhitekta remote review
→ 1 formal reviewer ako task dira shared contract, architecture boundary
  ili je testna sigurnost netrivijalna
→ Human Owner odluka
→ merge
→ post-merge full relevant gate
→ GitNexus re-index gdje je primjenjivo
```

Ako review pokaže HIGH blast radius:

```text
STOP
→ reclassify HIGH
```

## HIGH

Primjeri: security invariant, DB schema/migration sa podacima, destructive Git/worktree cleanup, credential handling, central bootstrap/composition, architecture-wide refactor, koruptivan concurrency/lifecycle problem.

Tok:

```text
GitNexus pre-impact
→ HIGH Task Contract + rollback
→ implementer
→ targeted + adversarial proof
→ full relevant verification
→ GitNexus detect-changes / impact
→ push task branch
→ Codex independent review
→ Claude independent architecture/security review
→ glavni arhitekta sinteza
→ Human Owner eksplicitno odobrenje
→ merge
→ post-merge full gate
→ remote SHA provjera
→ GitNexus re-index
```

---

# 6. Obavezni read protocol

Agent ne čita cijeli repo bez potrebe.

Prije implementacije:

```text
1. AGENTS.md
2. CLAUDE.md
3. ovaj kanonski execution plan
4. FlowOS v4.4 roadmap
5. konkretan Task Contract
6. relevantni source + tests
7. GitNexus context/impact ako je required
```

Progressive disclosure:

```text
repo mapa / direktorij
→ ime fajla
→ prvih ~10–20 linija / header
→ odbaci nerelevantne fajlove
→ puni sadržaj samo relevantnih
```

Ne skenirati cijeli `docs/` i `agent_reports/` bez razloga.

---

# 7. Agent-friendly file headers

Primjenjuje se touched-file pravilo.

Za relevantni source fajl header treba kratko reći:

1. šta fajl radi;
2. šta owns;
3. šta ne owns ako je granica važna;
4. canonical contract samo gdje je stvarno korisno.

Ne stavljati istoriju izmjena, imena agenata, review narativ, bug backlog ili TODO istoriju.

Header je navigaciona pomoć, ne source of truth.

Ako task materijalno mijenja odgovornost fajla, agent mora provjeriti da li header i dalje govori istinu.

Ne raditi masovnu header migraciju.

---

# 8. Task Contract

Svaki netrivijalni task dobija:

```text
agent_reports/<TASK-ID>-task-contract.md
```

Minimalni YAML:

```yaml
task_id:
title:
phase:
risk:
coordinator:
implementer:
reviewers:
status:
created_at:
dependencies:
allowed_paths:
forbidden_paths:
gitnexus_required:
adversarial_required:
baseline_sha:
branch:
worktree:
```

Tijelo mora sadržati:

1. kontekst;
2. objective;
3. zašto task postoji sada;
4. source-of-truth reference;
5. repo-grounded pre-change facts;
6. GitNexus pre-impact evidence;
7. implementation steps;
8. acceptance criteria;
9. verification commands;
10. allowed / forbidden paths;
11. adversarial strategy;
12. review fokus;
13. rollback za MEDIUM/HIGH;
14. dependency baseline;
15. commit/push pravila;
16. stop conditions.

---

# 9. Contract deviation

Task Contract nije nepogrešiv.

Bounded deviation je dozvoljen samo ako:

```text
goal ostaje isti
scope ostaje isti
acceptance ostaje isti
risk nije povećan
postoji reproducibilan dokaz da je implementation assumption pogrešna
odstupanje je zapisano u reportu
```

Ako odstupanje mijenja scope, architecture, risk, acceptance, security boundary ili source of truth:

```text
STOP
→ human decision
```

Format:

```yaml
finding: OUT_OF_SCOPE_FINDING
description:
location:
risk:
evidence:
proposed_task:
```

---

# 10. Split-kontrakta

Ako glavni arhitekta prije implementacije otkrije prerequisite gap:

```text
NE proširivati originalni task.
```

Postupak:

1. poseban prerequisite task;
2. originalni task dobija dependency;
3. originalni task postaje BLOCKED;
4. oba kontrakta objašnjavaju zašto su odvojena.

Risk prati stvarni blast radius prerequisite taska.

---

# 11. GitNexus

Obavezan za:

```text
MEDIUM
HIGH
shared interface/protocol/dataclass
public API contract
worktree/Git shared logic
migration/schema
bootstrap/composition
security boundary
rename/move shared simbola
funkciju/klasu sa više callera
```

Pre-change tražiti:

```text
index freshness
target symbols
upstream callers
downstream dependencies
affected flows
blast radius
partial/unknown stanje
```

Pre-review:

```text
detect-changes / impact
```

Ako GitNexus ne radi u task worktree-u:

- ne tumačiti `0 impact` kao dokaz;
- pokušati iz glavnog checkouta / eksplicitnim repo bindingom;
- ako ni tada nema pouzdanog rezultata: `GitNexus = UNKNOWN`;
- kompenzovati `git diff`, `rg` i caller pregledom;
- ne izmišljati sigurnost.

Poslije merge-a: re-index/update gdje je primjenjivo.

---

# 12. Worktree i branch politika

Netrivijalan task:

```text
../FlowOS-worktrees/<TASK-ID>-<short-name>
```

Branch:

```text
task/<TASK-ID>-<short-name>
```

Prije branch-a:

```bash
git status --short --branch
git log -5 --oneline
git log -1 --oneline main
```

Obavezno dokazati:

```text
task baseline == očekivani remote main
dependencies su stvarno merged
```

Default:

```text
commit + push task branch
→ arhitekta pregleda remote diff
→ merge tek poslije odluke
```

---

# 13. Paralelizacija

Dva taska mogu paralelno samo ako:

```text
allowed_paths(A) ∩ allowed_paths(B) = ∅
```

i nemaju skrivenu semantic dependency.

Ako postoji sumnja: raditi sekvencijalno.

Ne graditi coordination subsystem unaprijed. Tek ako 4+ paralelna worktree-a pokažu stvaran problem, razmatrati deterministički claim mehanizam.

---

# 14. Implementer report

Format:

```text
agent_reports/YYYY-MM-DD-<TASK-ID>-<agent>.md
```

Mora sadržati:

```text
Task
Baseline SHA
Branch/worktree
Files changed
Implementation summary
GitNexus pre-change evidence
GitNexus post-change evidence kada je required
Verification commands
DOSLOVAN output
Tests added/changed
Adversarial proof ako je required
OUT_OF_SCOPE_FINDINGS
Not verified
Commit SHA
Push target
Odstupanja od prompta
```

`Tests pass` bez outputa nije dokaz.

---

# 15. Review report

Format:

```text
agent_reports/YYYY-MM-DD-<TASK-ID>-review-<agent>.md
```

Header:

```yaml
verdict: PASS|PASS_WITH_NOTES|REJECT
scope: PASS|REJECT
acceptance: PASS|REJECT
architecture: PASS|REJECT
security: PASS|REJECT
tests: PASS|REJECT
gitnexus_impact: PASS|REJECT|NOT_REQUIRED|UNKNOWN
blocking_findings: []
```

Narativ:

```text
CILJ
PROVJERENO
STVARNI DIFF
GITNEXUS / IMPACT
BLOCKING FINDINGS
TESTOVI
ADVERSARIALNA PROVJERA
NE DIRATI U FIX RUNDI
SLJEDEĆE
```

Reviewer mora čitati stvarni kod/diff.

---

# 16. Fix runda

Jedan finding = jedan uski fix scope.

Fix prompt mora navesti:

```text
Finding ID
Root cause
Allowed files
Forbidden files
Tačnu očekivanu promjenu
Regression test
Adversarial case
Šta ne dirati
Report format
```

Nakon fixa radi se re-review materijalno promijenjenog scope-a.

Novi nezavisan problem postaje `OUT_OF_SCOPE_FINDING`, ne scope creep.

---

# 17. Adversarial proof

Obavezan kada task tvrdi novi invariant.

Primjeri:

```text
prefix path više ne bira pogrešan worktree
claim se ne prikazuje kao mechanical evidence
HEURISTIC ne može napraviti hard block
redaction se dešava prije truncation-a
View ne zove persistence
Service ne zavisi od Controller sloja
session register ne spawn-uje agent
filtered env ne prosljeđuje secret
timeout gasi cijeli FlowOS-owned process tree
```

Procedura:

```text
1. test tvrdi da štiti invariant
2. privremeno poznato-loša varijanta
3. isti test mora FAIL
4. vratiti ispravnu implementaciju
5. isti test mora PASS
6. dokumentovati oba outputa
```

Ako test prolazi i na lošoj varijanti, test nije dokaz.

---

# 18. Standardna verifikacija

Task Contract definiše targeted commands.

Relevantni opšti gate:

```bash
ruff format --check ...
ruff check ...
python -m mypy src --explicit-package-bases
python scripts/guard_architecture.py
pytest tests/architecture/ ...
pytest <targeted/relevant tests>
python scripts/verify.py
```

Prije merge-a MEDIUM/HIGH taska `scripts/verify.py` je default završni gate ako nema tehničkog razloga da nije primjenjiv.

Ne tvrditi `full green` ako je pokrenut samo targeted test.

---

# 19. Definition of Done

Task nije DONE samo zato što:

```text
agent kaže gotovo
report postoji
testovi su jednom prošli
commit postoji
branch je pushovan
```

Netrivijalan Task je DONE kada ima:

```text
[ ] Task Contract
[ ] implementation
[ ] exact diff pregled
[ ] targeted tests
[ ] relevant regression
[ ] GitNexus evidence kada je required
[ ] adversarial proof kada je required
[ ] implementer report
[ ] required independent review
[ ] nema otvorenog BLOCKER/HIGH/MEDIUM nalaza
[ ] Human Owner odluka gdje workflow to zahtijeva
[ ] merge/integration
[ ] post-merge gate
[ ] remote SHA provjera
[ ] GitNexus re-index kada je primjenjivo
```

---

# 20. Kanonski redoslijed daljeg razvoja

Ovaj redoslijed važi dok evidence ne dokaže da ga treba mijenjati.

## BOOT-0 — Kanonski dokumenti u repou `[LOW, docs-only]`

Prije prvog novog code taska:

1. dodati v4.4 roadmap u `docs/`;
2. dodati ovaj execution plan u `docs/`;
3. ne prepravljati još cijeli README/CLAUDE/AGENTS;
4. osigurati da svaki budući Task Contract referencira stvarne canonical dokumente u repou.

Zašto prvi:

> remote repo trenutno nema v4.4; bez ovoga bi agenti radili prema dokumentu koji nije dio repoa.

Ovo je procesni bootstrap, ne product subsystem.

---

# 21. GATE A — Cleanup + contracts + real dogfood

## FLOW-1110 — Siguran identitet worktree putanja `[M]`

**Prvi code task.**

Stvarni bug:

```python
wt.path == path or wt.path.startswith(path)
```

Cilj:

- canonical/resolved path identity;
- Windows case semantics;
- nema prefix collision-a;
- project identity provjera;
- cleanup fail-closed;
- managed/main odluka ne koristi textual prefix;
- dirty zaštita ostaje.

Obavezni dokaz:

```text
FLOW-1 ≠ FLOW-10
slični prefiksi nisu identitet
drugi project_id se odbija
pogrešan path ne cleanup-uje drugi tree
main ne može biti pogrešno klasifikovan
tačan cleanup radi
dirty zaštita ostaje
```

**Risk:** MEDIUM sa destruktivnim karakterom → rigorozniji review od običnog MEDIUM.

## FLOW-1105 — Plan Import Pydantic contract `[S]`

Repo fact:

- GUI već šalje `markdown_text`;
- backend još koristi `body: dict`.

Cilj:

```text
GUI
→ GuiApiClient
→ FastAPI PlanImportRequest
→ service/parser
```

Jedan canonical contract. Ne vraćati se na stari naming bug koji više ne postoji.

## FLOW-1106 — Stvarni dogfood import `[S]`

- registruj/izaberi FlowOS projekat;
- importuj stvarni plan kroz LIVE tok;
- potvrdi phases/items/criteria/dependencies;
- prikaži nejasnoće čovjeku;
- ne fabrikuj retroaktivni Ledger history.

## FLOW-1107 — Velocity baseline `[S]`

Za svaki naredni task zapisati:

```text
Task
size S/M/L
calendar start/end
review time
broj korekcija
rework
human attention gdje je poznat
```

Bez analytics sistema.

## FLOW-1111 — Passive Session cleanup `[S]`

Očistiti mrtve tragove stare orchestration filozofije:

```text
can_launch default
AgentProcessLauncher mrtvi put
kill_process_tree samo ako pripada starom launch smjeru
pid=os.getpid() ako glumi agent PID
execution/jobs/approvals/usage prazni/mrtvi paketi
get_command/get_environment — KEEP metadata ili REMOVE
```

`agent_scanner` ostaje read-only.

Gate:

```text
Session register/start ne spawn-uje agent
nema lažnog agent PID-a
nema core can_launch capability
pasivni scanner ne mutira agent process
```

## FLOW-1112 — Evidence semantics + provenance `[M]`

Zaključati:

```text
SOURCE_FACT
DERIVED_FACT
MECHANICAL_EVIDENCE
HEURISTIC_SIGNAL
CLAIM
HUMAN_DECISION
```

Pravila:

- ne dodavati `semantic_class` u svaku tabelu po defaultu;
- izvoditi iz source type-a gdje je moguće;
- read-model DTO može nositi klasu;
- claim se ne promoviše u proof;
- derived fact referencira source fact;
- UI kasnije razlikuje proof/claim/heuristic/unknown.

Legacy attribution map mora povezati postojeće vrijednosti sa:

```text
DIRECT / ISOLATED / HEURISTIC / UNKNOWN
```

bez dvije paralelne taksonomije u GUI-ju.

## FLOW-1113 — Existing read-model inventory `[S]`

Repo-grounded odluka za:

```text
EvidenceService
ProjectStateService
project_timeline
sessions/timeline
reconciliation
```

Za svaki:

```text
EXTEND
REUSE
REPLACE
KEEP SEPARATE
DEPRECATE
```

Bez novog paralelnog source of truth.

## FLOW-1114 — FlowOS-owned subprocess safety `[M]`

Samo za determinističke subprocess-e koje FlowOS sam pokreće.

Cilj:

- filtered/allowlisted env;
- secrets se ne prosljeđuju bez potrebe;
- timeout gasi cijeli FlowOS-owned child tree na Windowsu;
- exit/stdout/stderr ostaju tačni.

Ne odnosi se na agentske procese.

## FLOW-1115 — Repository contract alignment `[S]`

Nakon čišćenja koda uskladiti:

```text
README.md
CLAUDE.md
AGENTS.md
druge canonical instruction dokumente
```

Ukloniti tvrdnje da je FlowOS agent launcher/process manager/model router/worker-checker orchestrator.

Canonical rečenica:

> **FlowOS posmatra, pamti, povezuje, provjerava i prikazuje. Ne izvršava agentski rad.**

### Gate A exit

```text
[ ] 1110 accepted
[ ] 1105 typed PlanImport contract radi
[ ] 1106 dogfood plan je aktivan
[ ] 1107 velocity zapis je počeo
[ ] 1111 passive session granica je čista
[ ] 1112 semantics/provenance zaključani
[ ] 1113 read-model inventory završen
[ ] 1114 subprocess safety dokazan
[ ] 1115 docs govore istu istinu kao kod
```

---

# 22. GATE B — Task-centric proof surface

## FLOW-1201 — Project selection `[S]`

Aktivni projekat mora biti jasan i stvaran.

## FLOW-1202 — Zadaci na stvarni backend `[M]`

Bez mock podataka.

## FLOW-1203 — Task Current State `[M]`

Graditi preko odluka iz FLOW-1113. Ne praviti paralelni ProjectState/Evidence sistem.

## FLOW-1204 — Task Detail `[L]`

Prvih 10 sekundi mora odgovoriti:

```text
Šta je ovo?
Zašto postoji?
Šta trenutno važi?
Šta je dokazano?
Šta je samo claim?
Šta je heuristika?
Šta je stale?
Šta je UNKNOWN?
Šta traži moju pažnju?
```

### Važan product gate

**Odmah nakon FLOW-1204 počinje svakodnevno dogfooding korištenje Task Detail-a.**

Ne čekati 1300/1400/1500 da bismo otkrili da je UX pretežak.

Ako Task Detail povećava administraciju umjesto da smanjuje mentalni teret:

```text
STOP
→ UX/product korekcija prije širenja
```

---

# 23. GATE C — Workflow History + inspectable evidence

## FLOW-1301 — Unified Task Workflow History `[M]`

Ujediniti:

```text
IMPLEMENTATION_COMPLETED
TEST_RESULT
REVIEW_COMPLETED
TASK_DECISION
```

## FLOW-1302 — Workflow History GUI `[M]`

Dokaz stvarnog GUI primitive reuse-a iz 1204.

## FLOW-1303 — Inspectable Evidence `[M]`

Evidence mora otvoriti provenance.

## FLOW-1304 — Workflow History ≠ Technical Activity `[S]`

Ne miješati procesnu istinu sa sirovom tehničkom aktivnošću.

## FLOW-1305 — Regression Proof baseline `[M]`

Za reproducibilan bugfix:

```text
pre-change FAIL
post-change PASS
```

bez mutiranja aktivnog implementation worktree-a.

---

# 24. GATE D — Human Decision + prvi kompletan E2E

## FLOW-1401 — TASK_DECISION controls `[M]`

```text
Prihvati
Vrati u doradu
Odbaci
```

## FLOW-1402 — Backend-confirmed consequence `[S]`

GUI reloaduje canonical backend state.

## FLOW-1403 — Real E2E dogfood `[M]`

Jedan stvarni FlowOS task mora proći:

```text
IMPLEMENTATION_COMPLETED
→ TEST_RESULT
→ REVIEW_COMPLETED
→ TASK_DECISION
```

bez ručne rekonstrukcije iz terminala/chata.

## FLOW-1404 — Historical SessionTaskBinding proof `[M]`

Istorijski binding nadjačava trenutni session field za istorijski event.

---

# 25. GATE E — UX baseline + velocity calibration

## FLOW-1501 — Real UX problems `[S]`

Posmatrati 5–10 stvarnih taskova.

## FLOW-1502 — Navigation simplification `[M]`

Za svaku postojeću stranicu:

```text
KEEP
MERGE
RELOCATE
REMOVE
```

bez tihog nestanka funkcija.

## FLOW-1503 — LIVE/MOCK cleanup `[M]`

Nema fake statistika/progressa.

## FLOW-1504 — First dogfood baseline `[S]`

Screenshotovi, stvarni behavior, poznati problemi, E2E evidence.

## FLOW-1505 — Velocity calibration `[S]`

Tek tada kalendarski procjenjivati naredne faze.

---

# 26. P1 — Tek nakon dokazanog baseline-a

```text
1600 Current State / Handoff
1700 Structured Findings
1800 Structured Task Contract / Acceptance ↔ Evidence
```

Ne postaju automatski obaveza samo zato što su u roadmapu.

Proof gates:

- 1600 ide dalje samo ako Resume/Handoff stvarno smanjuje potrebu za starim chatom;
- 1700 ide dalje samo ako report-only finding postane bottleneck;
- 1800 ide dalje samo ako strukturisani acceptance/evidence donosi stvarnu review vrijednost.

---

# 27. P2 — Parallel coordination + deterministic quality

Tek poslije proof/continuity baseline-a:

```text
1900 Passive observability/correlation
2000 Deterministic guards
2100 Cross-worktree conflicts
2200 Readiness/bottleneck
```

Ne praviti vlastiti GitNexus.

`DependencyEvidenceProvider` je read-only provider, ne authority.

---

# 28. P3 — Samo po dokazu

```text
2300 Human comprehension + relationship graph
2400 PostgreSQL / team / central artifacts / extensions
```

Nema remote agent workers, schedulera, model routera ili execution grapha.

---

# 29. Product kill/pivot signali

## K1

Task Detail traži više ručnog unosa nego mentalnog rada koji uklanja.

## K2

Korisnik i dalje mora otvarati stare chatove da bi razumio većinu taskova.

## K3

Claim/proof semantika je tehnički tačna ali UX-om preteška za svakodnevnu upotrebu.

## K4

Pasivna korelacija eksternih sesija proizvodi previše pogrešnih attribution tvrdnji.

Rješenje nije AI nagađanje, nego:

```text
više UNKNOWN
jači deterministic evidence
bolji UX
manje scope-a
```

## K5

Nove faze se grade prije nego što prethodni gate ima stvarnog konzumenta.

Tada:

```text
STOP expansion
→ dogfood
→ pojednostavi
```

---

# 30. Metrike

Pratiti:

```text
time-to-resume
time-to-find-evidence
time-to-review
cycle time do accepted commita
rework
broj review korekcija
missing/stale evidence
IMPLEMENTED → VERIFIED conversion
VERIFIED → ACCEPTED conversion
conflict detection prije integrationa
human coordination time
```

Ne optimizovati:

```text
broj agenata
broj tokena
broj sesija
broj commitova
lines of code
```

---

# 31. Prvi praktični redoslijed od danas

```text
KORAK 0
BOOT-0 — staviti v4.4 + ovaj execution plan u repo

KORAK 1
FLOW-1110 — Siguran identitet worktree putanja

KORAK 2
FLOW-1105 — Plan Import Pydantic contract

KORAK 3
FLOW-1106 — Stvarni dogfood import

KORAK 4
FLOW-1107 — Početak velocity baseline-a

KORAK 5
FLOW-1111 — Passive Session cleanup

KORAK 6
FLOW-1112 — Evidence semantics + provenance

KORAK 7
FLOW-1113 — Existing read-model inventory

KORAK 8
FLOW-1114 — FlowOS-owned subprocess safety

KORAK 9
FLOW-1115 — Repository contract alignment

KORAK 10+
FLOW-1201 → FLOW-1204
```

Nema paralelnog otvaranja svih taskova. Svaki sljedeći nastaje tek nakon što je prethodni dovoljno zatvoren ili je dokazano da može paralelno bez presjeka.

---

# 32. Prvi code task poslije BOOT-0

**FLOW-1110 — Siguran identitet worktree putanja**

Zašto prvi:

1. bug je potvrđen u trenutnom `main`;
2. utiče na destruktivne cleanup odluke;
3. v4.4 ga označava kao near-term blocker;
4. dovoljno je usko da odmah testiramo novi agentski workflow;
5. dobar je kandidat za implementer → remote review → adversarial proof → fix/re-review tok.

To će biti prvi task za koji glavni arhitekta pravi zaključan Task Contract i jedan implementer prompt.

---

# 33. Trajni filter prije svakog novog taska

```text
Q1 — Da li je problem potvrđen u stvarnom kodu?
Q2 — Da li već postoji servis/read-model koji treba proširiti?
Q3 — Da li task uvodi LLM/orchestration mimo v4.4 granice?
Q4 — Koji je najmanji vertical scope?
Q5 — Koji GitNexus blast radius postoji?
Q6 — Koji test stvarno dokazuje acceptance?
Q7 — Možemo li test učiniti adversarialnim?
Q8 — Koji evidence mora ostati poslije sesije?
Q9 — Ko je implementer, ko reviewer?
Q10 — Koja ljudska odluka je potrebna prije merge-a?
```

Ako na Q1 nema dokaza:

> prvo research/probe, ne implementation prompt.

---

# 34. Završna radna formula

```text
Stvarni repo problem
        ↓
Arhitekta pregleda evidence
        ↓
Task Contract
        ↓
Jedan zaključan prompt
        ↓
Jedan implementer
        ↓
Testovi + report + push task branch
        ↓
Arhitekta pregleda stvarni GitHub diff
        ↓
Independent review po risku
        ↓
Jedan finding → jedan fix prompt
        ↓
Human decision
        ↓
Merge
        ↓
Post-merge proof
        ↓
Remote SHA verification
        ↓
Tek onda sljedeći task
```

> **AI radi. FlowOS pamti, povezuje i dokazuje. Čovjek odlučuje.**

> **Jedna akcija = jedan korak.**

> **Proof over claims.**

> **FlowOS čuva engineering state; ne posjeduje agentski runtime.**
