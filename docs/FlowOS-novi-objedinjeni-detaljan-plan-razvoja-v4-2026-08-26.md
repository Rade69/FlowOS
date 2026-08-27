# FlowOS — novi objedinjeni detaljan plan razvoja v4

**Datum:** 2026-08-26  
**Status:** prijedlog novog kanonskog roadmapa za korisničku potvrdu  
**Namjena:** objediniti postojeću implementaciju, dogfooding roadmap, Current State / Agent Context ideje, human-control-plane princip, portable handoff/model-routing ideje, GUI lekcije, security korektivne lekcije i kasnije managed/durable mogućnosti u jedan razvojni redoslijed.

---

# 0. Zašto postoji novi plan

FlowOS je u prethodnim mjesecima dobio mnogo dobrih ideja, ali su one nastajale u različitim fazama:

- početni PySide6 plan;
- Project Resume / „Gdje si stao“;
- wrapper, watcher, Git, atribucija i worktree;
- AgentReport i verification;
- Workflow Ledger;
- human authority / `TASK_DECISION`;
- dogfooding faze 11–15;
- Current State Projection;
- progressive context i Agent Context;
- portable handoff i model/harness razdvajanje;
- human attention / comprehension;
- managed execution;
- durable jobs;
- worker/checker;
- model routing i trošak po prihvaćenom radu.

Ako se svi prijedlozi samo saberu, FlowOS bi lako postao prevelik prije nego što dokaže svoju osnovnu vrijednost.

Zato ovaj plan uvodi jedno pravilo:

> **Prvo završiti najmanji kompletan human-controlled dogfooding tok nad postojećim backendom. Tek poslije toga dodavati nove authority evente, managed execution, routing, durability i naprednu automatizaciju.**

---

# 1. North Star

Najpreciznija ciljna definicija FlowOS-a:

> **FlowOS je lokalni, deterministički human control plane za agent-potpomognuti razvoj. Održava provjerljivu vezu između ljudske namjere, Taska, agentskih sesija, Git/worktree stvarnosti, dokaza, reviewa i odluka tako da čovjek ili fresh agent može pouzdano nastaviti rad bez oslanjanja na prethodni chat.**

Kraće:

> **AI radi. FlowOS pamti, povezuje i dokazuje. Čovjek odlučuje.**

FlowOS ne optimizuje za:

```text
što više agenata
što više tokena
što više generated code-a
što više paralelnih sesija
```

nego za:

```text
što više pouzdano prihvaćenog engineering rada
po jedinici ljudske pažnje
```

---

# 2. Neupitne arhitektonske granice

Ove odluke se ne otvaraju ponovo bez konkretnog dokaza da blokiraju razvoj.

1. Primarna platforma ostaje Windows 10/11.
2. GUI ostaje PySide6 + Qt Widgets.
3. Backend ostaje odvojen Python/FastAPI proces.
4. Arhitektura ostaje `View → Controller → Services`.
5. SQLite ostaje lokalna baza dok stvarna potreba ne opravda PostgreSQL.
6. Git je autoritet za stanje koda, ali commit nije workflow acceptance.
7. Worktree je izolacija izvršenja, ne Task.
8. Task, Session, ExecutionAttempt, Worktree, Report, Review i Decision ostaju različiti koncepti.
9. FlowOS ne radi automatski merge/push zaštićenog targeta kao posljedicu agentovog završetka.
10. AgentReport je evidence/claim container, ne canonical authority.
11. Model ne potvrđuje sam svoj rezultat kao konačan dokaz.
12. `IMPLEMENTED ≠ VERIFIED ≠ ACCEPTED`.
13. User decision ostaje canonical authority za acceptance/rejection.
14. Prompt nije security boundary.
15. Core mora raditi bez cloud servisa i bez obaveznog LLM-a.
16. Ne uvoditi LLM tamo gdje Git, SQL, state machine, parser ili test mogu deterministički riješiti problem.
17. Ne uvoditi paralelne ručne `current.md`, `progress.md`, `decisions.md` kao nove izvore istine.
18. Generisani Agent Context/Handoff je projekcija canonical podataka, nikada input authority-ja.
19. Ne prikazivati procenat napretka bez objašnjivog pravila.
20. Ne izmišljati atribuciju, status ili completion kada nema dokaza.
21. Svaka nova složenost mora imati dokazanu potrebu i jasan konzument.

---

# 3. Dvije odvojene osi: proizvod i metod

FlowOS razvoj od sada treba eksplicitno razlikovati:

## A. Product roadmap

Šta ugrađujemo u sam FlowOS.

## B. Engineering method

Kako radimo svaki veći FlowOS task.

Metod ne smije automatski postati novi backend subsystem.

Preporučeni metod:

```text
Idea / problem
        ↓
Alignment / Grill
        ↓
Product destination
        ↓
Research / Probe — samo ako postoji stvarna nepoznanica
        ↓
Architecture
        ↓
Program Design
        ↓
Vertical Slice plan
        ↓
Locked Task Contract / prompt
        ↓
Implementation
        ↓
Evidence / tests
        ↓
Independent review
        ↓
Finding → Fix → Re-review
        ↓
Human decision
        ↓
Commit / integration gate
```

### Program Design checkpoint

Prije većeg implementation scope-a treba, gdje je opravdano, odgovoriti:

```text
Koji fajlovi se mijenjaju?
Koji tipovi/signature nastaju?
Kako izgleda call/data flow?
Koji testovi će dokazati rezultat?
Koje odluke su najmanje sigurne?
Kako se posao razbija na vertikalne, provjerljive rezove?
```

Ovo je prvenstveno **metod rada**. FlowOS ga tek kasnije može modelovati strukturisano ako dogfooding dokaže korist.

---

# 4. Polazna tačka

Plan polazi od posljednjeg verifikovanog radnog snapshot-a:

- backend/control-plane temelj već postoji;
- Workflow Ledger već podržava `IMPLEMENTATION_COMPLETED`, `TEST_RESULT`, `REVIEW_COMPLETED` i `TASK_DECISION`;
- `WorkflowDecisionService` već čuva canonical user authority;
- Project Resume/reconciliation, sessions, AgentReport, worktrees i verification već postoje;
- najveći trenutni deficit je što GUI ne spaja sve to u `Task Detail → Workflow History → Evidence → Human Decision`.

Near-term blokatori prije tog toka:

```text
FLOW-1109 — Redakcija tajni iz logova i artefakata
FLOW-1110 — Siguran worktree identitet i cleanup
FLOW-1105 — Usklađivanje GUI/backend Plan Import formata
FLOW-1106 — Stvarni uvoz dogfooding plana
```

---

# 5. FAZA A — Zatvaranje sigurnosnih i dogfooding blokatora

## Cilj

Doći do čistog, sigurnog i stvarno dogfoodabilnog LIVE FlowOS baseline-a.

## A1. FLOW-1109 — Redakcija tajni iz logova i artefakata

### Trenutni cilj

Završiti focused independent security re-review H1 fixa.

### Gate

Za ACCEPT mora biti dokazano:

- `AgentReport.verification_summary` ne može persistovati registrovani secret;
- `/worktrees/{id}/verify` ne može vratiti secret;
- redakcija se radi prije truncation-a;
- raw `VerificationResult` ostaje raw u memoriji;
- ArtifactStore redakcija ostaje ispravna;
- targeted/regression/verify testovi prolaze;
- nema novog BLOCKER/HIGH/MEDIUM nalaza.

### Poslije ACCEPT-a

- exact-scope commit;
- push;
- provjera remote SHA;
- tek onda prelazak na A2.

## A2. FLOW-1110 — Siguran worktree identitet i cleanup

### Problem

String prefix nije identitet putanje.

Nije dozvoljeno oslanjati se na:

```python
wt.path == path or wt.path.startswith(path)
```

### Obavezno

- canonical/resolved path identitet;
- Windows case semantics;
- bez prefix collision-a;
- cleanup cilja samo tačan managed worktree;
- containment/junction razmatranje gdje je relevantno;
- project_id provjera;
- jedan aktivni writer;
- nikakav destruktivan fallback „najbližeg“ worktree-a.

### Gate

Testovi moraju dokazati najmanje:

```text
FLOW-1 ≠ FLOW-10
slični textualni prefiksi nisu identitet
worktree drugog projekta nije prihvatljiv
cleanup pogrešnog patha fail-closed
tačan worktree cleanup radi
dirty zaštita ostaje
```

## A3. FLOW-1105 — Usklađivanje GUI/backend Plan Import formata

### Obavezno

- izabrati jedan canonical request field;
- GUI i backend koriste isti field;
- contract test;
- nema paralelnog legacy fielda samo radi prikrivanja drifta;
- import greška korisniku je čitljiva.

### Gate

Isti realni Markdown payload prolazi kroz GUI → API → parser.

## A4. FLOW-1106 — Stvarni uvoz dogfooding plana

### Obavezno

- FlowOS projekat registrovan/izabran;
- plan stvarno importovan kroz LIVE tok;
- faze/items/criteria/dependencies potvrđeni;
- nejasnoće prikazane, ne AI-pogođene;
- već završeni rad se ne retroaktivno fabrikuje kao Ledger history;
- plan postaje operativna mapa daljeg razvoja.

### Gate faze A

Ne prelaziti dalje dok:

```text
[ ] FLOW-1109 remote potvrđen
[ ] FLOW-1110 accepted
[ ] PlanImport radi end-to-end
[ ] dogfood plan je stvarno aktivan
[ ] FlowOS može pratiti vlastiti naredni Task
```

---

# 6. FAZA 12 — Projekat i Task postaju stvarna radna površina

## FLOW-1201 — Minimalni izbor i registracija projekta

### Obavezno

- TopBar jasno prikazuje aktivni projekat;
- korisnik bira postojeći projekat;
- `Dodaj projekat`;
- repo path se ne izmišlja;
- bez automatskog `git init`;
- Plan, Zadaci, Sesije, Resume i Activity prate aktivni projekat.

### Dokaz

Dva projekta mogu postojati i GUI pouzdano mijenja kontekst između njih.

## FLOW-1202 — Povezati `Zadaci` sa stvarnim backendom

### Cilj

`Zadaci` prestaje biti placeholder.

### Obavezno

Prikazati:

- human-readable naslov;
- Task key/ID sekundarno;
- status;
- PlanItem vezu ili `Nije vezan za plan`;
- osnovni attention signal ako postoji;
- nema AI prioritizationa;
- nema fake progressa.

### Dokaz

Task kreiran u backendu pojavljuje se u LIVE GUI-ju bez mock podataka.

## FLOW-1203 — Minimalni Task Current State read-model

### Ključni read-model MVP-a

Ne praviti novi source of truth.

Sastaviti projekciju iz postojećih podataka:

```text
Task
TaskContract ako postoji
PlanItem
SessionTaskBinding history
latest/relevant AgentReport
Workflow Ledger
Verification evidence
Git/worktree state
latest canonical TASK_DECISION
blockers / pending approval ako postoje
```

### Minimalni output

```text
Task identity
Goal / description
Plan position
Current workflow facts
Relevant sessions
Current worktree/Git state
Latest implementation evidence
Latest verification evidence
Latest review
Latest user decision
Open evidence gaps
Current blockers
```

### Stroga pravila

- nema AI summary-ja kao source of truth;
- nema `DONE` izvedenog iz commita/session close-a;
- nedostajući podatak = `Nije poznato` / `Nema dokaza`;
- istorijske tvrdnje ne smiju nadjačati noviju canonical odluku.

### Dokaz

Za jedan stvarni Task backend deterministički vraća tačnu „šta sada važi“ sliku.

## FLOW-1204 — Task Detail GUI

### Cilj

Task postaje glavno mjesto rada.

Prvih 10 sekundi treba odgovoriti:

```text
Šta je ovo?
Zašto postoji?
Gdje pripada u planu?
Ko je radio?
Šta je promijenjeno?
Šta je dokazano?
Šta nedostaje?
Šta traži moju pažnju?
```

### Preporučeni layout

```text
Task naslov + status + plan veza

TRENUTNO STANJE
- aktivni/predhodni rad
- worktree/branch
- latest evidence
- blocker

WORKFLOW HISTORY
- placeholder do Faze 13

DOKAZI
- latest report/test metadata

ODLUKA
- read-only do Faze 14
```

### Human comprehension acceptance

Korisnik može objasniti namjeru Taska i trenutni state bez čitanja starog chata.

---

# 7. FAZA 13 — Workflow history i evidence navigation

## FLOW-1301 — Task workflow history read-model

Podržati samo postojeće canonical evente:

```text
IMPLEMENTATION_COMPLETED
TEST_RESULT
REVIEW_COMPLETED
TASK_DECISION
```

Pravila:

- append-only redoslijed;
- stvarni event time + stabilan tie-break;
- commit/file/session close nisu completion event;
- AgentReport body nije history authority.

## FLOW-1302 — Workflow History GUI

Ljudski tekst, npr.:

```text
Implementacija završena
Testovi prošli / pali / timeout
Nezavisni review završen
Korisnik vratio u doradu
```

Tehnički enum može biti sekundaran.

Razlikovati aktera:

```text
Agent
Sistem / mehanički dokaz
Reviewer
Korisnik
```

## FLOW-1303 — Otvaranje stvarnih dokaza

Iz history reda:

- implementation → report;
- test → artifact metadata/stdout/stderr gdje je dozvoljeno;
- review → review report;
- decision → decision metadata.

Nedostajući dokaz se prikazuje kao nedostajući.

Nikada se ne generiše zamjenski „AI dokaz“.

## FLOW-1304 — Odvojiti Workflow History od Technical Activity

Workflow:

```text
šta se procesno dogodilo sa Taskom
```

Technical Activity:

```text
file changes
Git
session events
watcher
worktree
```

Te dvije stvari ne prikazivati kao jednu neoznačenu timeline listu.

## FLOW-1305 — Verification evidence quality baseline

**Nova preporučena stavka, bez novog Ledger eventa.**

Za regression fix gdje je praktično:

```text
pre-change code + novi regression test → FAIL
patched code + isti test → PASS
```

To je `Regression Proof` / `Test Effectiveness Evidence`.

Ne zahtijevati mutation testing za svaki Task.

### Gate

Najmanje jedan stvarni bugfix u dogfoodingu ima dokaz da test zaista hvata problem.

---

# 8. FAZA 14 — Human decision i prvi pravi end-to-end FlowOS tok

## FLOW-1401 — TASK_DECISION kontrole

Na Task Detail-u:

```text
Prihvati rezultat
Vrati u doradu
Odbaci rezultat
```

Prije odluke prikazati:

- Task;
- relevantni diff/report;
- verification;
- review;
- šta nije provjereno.

## FLOW-1402 — Prikaz backend posljedice odluke

GUI ne nagađa.

Nakon odluke ponovo učitava backend-confirmed state.

Posebno:

- `ACCEPTED` ne glumi VERIFIED;
- `NEEDS_WORK/REJECTED` consequence se prikazuje kako ga backend stvarno primijeni.

## FLOW-1403 — Kompletan dogfooding tok

Jedan stvarni FlowOS development Task mora proći:

```text
IMPLEMENTATION_COMPLETED
→ TEST_RESULT
→ REVIEW_COMPLETED
→ TASK_DECISION
```

i cijela priča mora biti vidljiva kroz LIVE FlowOS.

### Human comprehension acceptance

Bez terminalske rekonstrukcije korisnik može:

1. reći šta je Task trebao uraditi;
2. otvoriti relevantni evidence;
3. razlikovati implemented/tested/reviewed/accepted;
4. vidjeti šta nije provjereno;
5. donijeti odluku.

## FLOW-1404 — SessionTaskBinding historical proof

Dokazati scenario:

```text
A → B → A
```

i:

```text
A → B → UNASSIGNED
```

Report/Ledger attribution koristi istorijski binding, ne trenutni session field.

---

# 9. FAZA 15 — UX simplification i prvi zamrznuti dogfood baseline

## FLOW-1501 — Zabilježiti stvarne UX probleme

Za 5–10 stvarnih Taskova zabilježiti:

- gdje je korisnik izgubio mentalni model;
- gdje je morao otvoriti chat;
- gdje evidence nije bio dostupan;
- gdje je GUI imao previše tehničkih detalja;
- gdje je scope drift bio teško vidljiv;
- gdje je review bio prevelik;
- gdje „Gdje si stao“ nije bio dovoljan.

Ne uvoditi analytics sistem za ovaj korak.

## FLOW-1502 — Pojednostaviti navigaciju

Ciljni primarni nivo, ako dogfooding potvrdi:

```text
Pregled
Zadaci
Plan
Aktivnost
```

Sekundarni/tehnički:

```text
Sesije
Agenti
Radna stabla
```

Reports/evidence/conflicts idealno se otvaraju iz Task konteksta.

Ne redizajnirati samo zbog estetike.

## FLOW-1503 — Ukloniti lažno live / placeholder stanje

- nema hardkodiranih statistika;
- placeholder jasno označen;
- MOCK i LIVE se ne miješaju;
- engleski interni enum ne izlazi sirov korisniku;
- svi statusi kroz centralni translation/presentation sloj.

## FLOW-1504 — Zamrznuti prvi dogfood baseline

### Obavezno

- screenshotovi glavnih LIVE ekrana;
- šta stvarno radi;
- šta je namjerno odgođeno;
- poznati problemi;
- evidence da kompletan dogfood tok radi;
- korisnička odluka o sljedećem prioritetu.

### Ovo je veliki ROADMAP GATE

Prije `FLOW-1504 ACCEPTED` ne uvoditi:

- puni structured Findings backend;
- USER_VALIDATION event;
- managed execution;
- auto model routing;
- durable job engine;
- telemetry platform;
- autonomni multi-agent orchestration.

---

# 10. FAZA 16 — Current State Projection i portable Agent Handoff

Ova faza je preporučeni prvi korak poslije dogfood baseline-a jer direktno smanjuje context switching bez velikog authority širenja.

## FLOW-1601 — Strukturisani Current State Projection

Iz istih canonical podataka napraviti fokusirane read-modele:

```text
Project State
Human Attention State
Agent Handoff State
```

Ne tri nove baze. Tri projekcije.

## FLOW-1602 — Project State

Odgovara:

> Gdje je projekat sada?

Sadrži:

```text
current goal
active PlanItem/Task
latest canonical decision
active/recent sessions
Git/worktree state
verified evidence
open blockers
last safe checkpoint
```

## FLOW-1603 — Human Attention State

Odgovara:

> Šta čovjek mora pogledati sada?

Deterministički prioriteti:

1. blocking/risky decision;
2. failed/missing verification;
3. material review finding;
4. implementation bez verificationa;
5. verification bez user decisiona;
6. state mismatch / reconciliation;
7. informativna aktivnost.

Bez AI prioritization enginea u prvoj verziji.

## FLOW-1604 — Agent Handoff State

Minimalni vendor-neutral paket:

```text
Goal
Current state
Relevant files
Constraints
Definition of done
Checks to run
References
```

Dodatno po potrebi:

```text
latest authoritative decisions
known failed approaches worth avoiding
active findings
worktree/base commit
```

Conversation history nije durable memory.

Ako fresh agent mora znati činjenicu, ona mora biti u canonical stanju ili referenceable durable project contextu.

## FLOW-1605 — Handoff rendereri

Iz istog modela:

```text
Markdown
JSON/API
Clipboard
GUI preview
```

`FLOWOS_CURRENT.md` ili sličan fajl može biti generisan output.

Ručna izmjena tog fajla nema workflow authority.

## FLOW-1606 — Fresh-session dogfood

Stvarna sesija:

```text
Agent A završi / stane
→ FlowOS generiše handoff
→ nova sesija, drugi model ili isti model
→ nastavlja bez čitanja starog chata
```

### Gate

Fresh agent može ispravno nastaviti jedan realan Task samo iz handoffa + repo referenci.

---

# 11. FAZA 17 — Structured Findings, fix i verification lifecycle

Faza se pokreće samo ako `FLOW-1504` potvrdi da report-only findings postaju bottleneck.

## FLOW-1701 — Finding model

Minimalno:

```text
id
task_id
review_id/report_id
severity
title
description
evidence reference
status
created_at
```

Severity:

```text
BLOCKER
HIGH
MEDIUM
LOW
```

## FLOW-1702 — FINDING_DECIDED

Čovjek odlučuje:

```text
FIX_REQUIRED
ACCEPTED_RISK
REJECTED_FINDING
DEFERRED
```

Finding nije automatski workflow authority samo zato što ga je reviewer napisao.

## FLOW-1703 — FIX_COMPLETED

Fix agent zatvara samo konkretan Finding scope.

`FIX_COMPLETED` ne znači verified.

## FLOW-1704 — VERIFICATION_COMPLETED

Independent re-review / verification potvrđuje:

```text
CLOSED
OPEN
PARTIAL
```

> **FIXED ≠ VERIFIED**

## FLOW-1705 — Findings GUI

Task Detail:

```text
Otvoreni findings
Decision
Fix evidence
Re-review
Status
```

## FLOW-1706 — USER_VALIDATION kandidat

Uvesti samo gdje je business/UX ponašanje stvarno potrebno ručno potvrditi.

Ne koristiti USER_VALIDATION za svaki tehnički Task.

---

# 12. FAZA 18 — Task Contract v2 i pre-execution design gates

Ovo je mjesto za Product/Architecture/Program Design/Vertical Slice metod ako dogfooding pokaže da pogrešan upfront smjer proizvodi rework.

## FLOW-1801 — Task Contract v2

Obavezna polja netrivijalnog Taska:

```text
goal
scope
out_of_scope
definition_of_done / acceptance
risk
allowed paths hint
verification commands
```

Dodatna polja samo gdje treba:

```text
working hypothesis
unknowns
dependencies
```

## FLOW-1802 — Risk/size-based planning depth

Ne koristiti četiri gatea za trivialni tweak.

### Mali / lako reverzibilan

```text
Task Contract
→ implement
→ verify
```

### Srednji

```text
Product/goal clarification
→ Program Design
→ slices
→ implementation
```

### Visok rizik / arhitektura

```text
Grill
→ Research Probe
→ Product
→ Architecture
→ Program Design
→ human approval
→ slices
```

## FLOW-1803 — Program Design artifact/projection

Prije implementationa može sadržati:

```text
files
types/signatures
call/data flow
test plan
least-confident decisions
```

Ne mora biti novi canonical DB entitet u prvoj verziji.

Može biti versioned artifact povezan sa Taskom i DecisionItem-ima.

## FLOW-1804 — Least-confident decisions → Decision Inbox

Agent može prijaviti:

```text
decision
confidence
impact
alternatives
```

FlowOS samo strukturisano prikazuje. Ne prihvata automatski.

## FLOW-1805 — Vertical Slice Plan

Task/feature se razlaže na reviewable tracer-bullet cjeline.

Pravilo:

> Ne praviti horizontalni DB → service → API → GUI megadiff bez provjerljivog end-to-end checkpointa.

---

# 13. FAZA 19 — Managed Execution

Ovo se uvodi tek kada external/wrapped dogfooding radi pouzdano.

## Cilj

FlowOS može pokrenuti i kontrolisati **jedan** ograničen agentski coding task, ali ne preuzima product authority.

## Model

```text
AgentJob
ExecutionAttempt
ApprovalRequest
```

Arhitektonske granice:

```text
AgentAdapter
ExecutionBackend
WorkspaceProvider
CredentialProvider
```

Ne spajati ih u jednu vendor-specifičnu klasu.

## Capability semantics

Akcija je dozvoljena samo ako je podržava presjek:

```text
adapter capability
∩ runtime capability
∩ execution mode
∩ current state
```

FlowOS ne smije prikazati `Cancel` za proces koji ne može stvarno kontrolisati.

## Obavezno

- managed worktree;
- jedan writer;
- allowed-path enforcement;
- command policy;
- filtered environment;
- secret-safe logging;
- stdout/stderr artifact;
- timeout;
- graceful cancel;
- hard process-tree cancel;
- approval za rizične akcije;
- `PROBE` workflow;
- no merge/push target authority.

### Windows

Ako se tvrdi Job Object podrška, mora postojati stvarni Windows Job Object i kill-on-close semantics.

## Gate

Jedan mali realni coding Task prolazi:

```text
Task Contract
→ managed worktree
→ agent launch
→ verify
→ report
→ human decision
```

i namjerni timeout/hard cancel ne ostavlja child procese.

---

# 14. FAZA 20 — Evaluation, model/harness metadata i assisted routing

Tek kada postoji dovoljno stvarnih izvršenja.

## FLOW-2001 — Razdvojiti identitet izvršenja

Model:

```text
Provider
Model
Harness
Execution Environment
Session/Attempt
```

## FLOW-2002 — Usage/outcome zapis

Ne samo tokeni.

Bilježiti gdje je dostupno:

```text
execution cost
duration
retries
verification cost
review time
rework
final Task outcome
```

## FLOW-2003 — Fully loaded cost

Ključna metrika:

```text
model cost
+ context transfer
+ retries
+ failed attempts
+ verification
+ review time
+ rework
=
cost per VERIFIED / ACCEPTED Task
```

## FLOW-2004 — Task Suitability read-model

Deterministički ili rule-based input:

```text
target clarity
scope clarity
permission clarity
Definition of Done clarity
verification strength
hidden-state risk
business risk
```

Prvi UI daje **informaciju**, ne automatsku odluku.

## FLOW-2005 — Assisted model routing

Samo nakon realnog evaluation skupa.

FlowOS može preporučiti:

```text
bounded / strong verifier → cheaper worker candidate
ambiguous / root-cause / architecture → stronger model + human oversight
```

Čovjek bira.

Automatsko routing ponašanje dolazi samo ako kasniji evidence opravda.

---

# 15. FAZA 21 — Durable Job Engine

Ne graditi prije stabilnog Managed Executiona.

## Model

```text
AgentJob
AgentStep
StepAttempt
Checkpoint
Handoff
```

## Ključni princip

> **Session je potrošna. State mora biti trajan.**

## Obavezno

- centralne status tranzicije;
- retry klasifikacija;
- max attempts;
- timeout/budget;
- idempotency;
- startup recovery;
- `LOST` attempt;
- side-effect barrier;
- pause/resume samo na sigurnim granicama;
- checkpoint = siguran commit + handoff;
- ne nastavljati „od posljednje misli“.

## Gate

Fault injection:

```text
kill prije checkpointa
kill poslije checkpointa
restart servisa
dupli completion event
unknown external side-effect
retry exhausted
dirty worktree
```

Sistem ne smije duplirati rizičnu akciju niti izmišljati completion.

---

# 16. FAZA 22 — Worker/Checker automatizacija

Independent review već postoji kao metod prije ove faze.

Ovdje se automatizuje samo ako donosi dokazanu vrijednost.

## CheckerReview

Odvojeno od worker reporta.

Checker dobija:

```text
spec / Task Contract
diff
verification evidence
project rules
```

Ne treba privatni worker reasoning.

## Obavezno

- standards review;
- spec review;
- confirmed/unconfirmed findings;
- reprodukcija/evidence;
- najviše dvije runde po jobu;
- human authority ostaje.

### Gate

Na istom evaluation skupu dokazati da checker:

- nalazi materijalne probleme;
- smanjuje rework ili povećava acceptance;
- ne povećava fully loaded cost iznad opravdane koristi.

Ako ne — ne širiti checker automatizaciju.

---

# 17. FAZA 23 — Human comprehension i quality safeguards

Ovo je opcioni sloj poslije stvarnog korištenja.

## 23.1 Review budget / autonomy envelope

Veliki diff + širok scope + slab evidence:

```text
→ manji checkpoint
```

Ne automatski rejection.

## 23.2 Comprehension checkpoint

Samo za visoki rizik:

```text
šta se ponašajno promijenilo?
koji su ključni trade-offi?
šta nije dokazano?
```

Ne praviti birokratski klik za svaki mali Task.

## 23.3 Human Understanding Check

Opcioni AI sloj:

- kratko objašnjenje;
- Mermaid dijagram;
- quiz;
- pitanja o novoj logici.

AI objašnjava deterministički izabrani evidence/context.

Ne postaje authority.

## 23.4 Repeated-tedium signal

Ako se isti boilerplate/finding ponavlja kroz više Taskova:

```text
→ predloži poseban refactor Task
```

Ne automatski refactor.

---

# 18. FAZA 24 — Project Readiness i bottleneck visibility

Samo nakon dovoljno istorije.

## Project Readiness

Deterministički pokazati:

```text
verify command postoji?
build poznat?
test suite postoji?
Git state poznat?
active worktree?
agent instructions?
migration state?
unresolved findings?
clean execution baseline?
```

Bez automatskog „score 87/100“ ako formula nije objašnjiva.

## Bottleneck View

FlowOS ne treba pokazivati samo:

```text
4 agenta rade
```

nego gdje rad stoji:

```text
5 Taskova čeka review
3 čeka human decision
2 čeka fix
1 čeka verification
```

Cilj je Theory-of-Constraints pogled:

> Ne optimizuj stanicu koja nije bottleneck.

---

# 19. FAZA 25 — Scale samo po dokazanoj potrebi

Bez datuma.

Mogući sadržaj:

- PostgreSQL;
- multi-machine/team mode;
- remote workers;
- WorkerLease/heartbeat/fencing;
- container sandbox;
- central artifact store;
- VS Code extension;
- network/CPU/memory policy;
- richer organization integrations.

### Gate

Svaka stavka mora imati:

```text
dokazan korisnički problem
postojeći workaround koji je stvarno preskup
jasan konzument
mjerljiv benefit
```

---

# 20. GUI north star

GUI se ne organizuje prema tabelama baze nego prema ljudskim pitanjima.

## Pregled

Odgovara:

```text
Šta se promijenilo?
Šta traži pažnju?
Šta je aktivno?
Gdje sam stao?
```

## Zadaci

Glavna radna površina.

## Plan

Mapa pravca i zavisnosti.

## Aktivnost

Technical activity / dijagnostika.

## Task Detail

Centralna jedinica razumijevanja i odluke.

---

# 21. „Gdje si stao“ ostaje važan, ali mijenja ulogu

Project Resume ne treba biti paralelni source of truth.

Treba postati jedna renderovana projekcija Current State modela.

Za projekat:

```text
current goal
last relevant Task
latest evidence
Git/reconciliation
open blockers
next safe workflow phase
```

Za Task:

```text
current implementation state
latest review
latest decision
next required action
```

---

# 22. Agent Context — pravila

## Stable context

Repo:

```text
AGENTS.md
ADRs
architecture docs
project conventions
verification commands
external-system metadata bez secreta
```

Odgovara: **Kako se radi u ovom projektu?**

## Current context

FlowOS projection.

Odgovara: **Šta trenutno važi?**

## History

Git + Ledger + Events + Reports.

Odgovara: **Kako smo došli ovdje?**

## Conversation

Privremena sesija.

Odgovara: **Šta smo u ovom razgovoru trenutno razmatrali?**

Ne miješati ove slojeve.

---

# 23. `docs/external/` i durable project knowledge

Vrijedna buduća praksa za agent-friendly repo:

```text
docs/adr/
docs/external/
```

`docs/external/` može opisati:

- koje env varijable postoje;
- koji payment provider;
- gdje je deployment;
- koje test account oznake;
- gdje korisnici šalju support;
- vanjske API contracte.

Nikada secret vrijednosti.

FlowOS može kasnije reference uključivati u Context Bundle.

---

# 24. Security non-regression contract

Lekcije iz ranijih korektivnih faza postaju stalne provjere.

## 24.1 Path safety

Nikad:

```text
string prefix = containment
```

Centralna path helper semantika.

## 24.2 Process lifecycle

- exit code 0 mora ostati 0;
- timeout gasi cijelo managed process tree;
- ne tvrditi Job Object ako ga nema;
- cancel ≠ process exited;
- external process capabilities se ne izmišljaju.

## 24.3 Environment

- allowlist/filtered env;
- credential values se ne loguju;
- caller ne prepisuje kritične interne varijable bez pravila.

## 24.4 Runtime descriptor

Validirati:

```text
schema/fields
port
instance identity gdje postoji
health
auth token snapshot
```

Ne koristiti stale podatke slijepo.

## 24.5 Watcher/Git

- callback greške ne gutati;
- stop je idempotentan;
- untracked files se vide;
- Git state parser je stabilan;
- observer event nije automatski workflow event.

## 24.6 Transaction ownership

Jedan jasan transaction owner po operaciji.

Ne dupli commit ownership.

## 24.7 Documentation truthfulness

Nije dozvoljeno napisati:

```text
Git čist
svi testovi prolaze
watcher integrisan
feature verified
```

ako dokaz to ne potvrđuje.

---

# 25. Standardni acceptance gate za svaki budući Task

Svaki netrivijalni implementation Task treba imati najmanje:

```text
1. Jasno definisan cilj
2. Scope / out-of-scope
3. DoD / acceptance
4. Git baseline
5. Exact changed-files pregled
6. Targeted tests
7. Relevant regression
8. scripts/verify.py gdje je primjenjivo
9. AgentReport
10. Independent review za HIGH/rizičan rad
11. Human TASK_DECISION gdje workflow to zahtijeva
12. Commit scope provjeru
13. Remote SHA provjeru prije tvrdnje "pushed"
```

Agentov završni report nikada nije sam po sebi acceptance.

---

# 26. Commit / integration gate

Prije commita:

```text
git status
exact diff
unrelated files excluded
fresh tests
review stanje
open material findings = none
```

Commit:

```text
jedan scope
jasna poruka
bez slučajnog unrelated sadržaja
```

Poslije:

```text
verify SHA
remote main/target ako je pushano
clean/expected working tree
tek onda sljedeći Task
```

---

# 27. Metrike koje imaju smisla

MVP prvo kvalitativno dogfooding.

Kasnije:

```text
time-to-resume
time-to-find-evidence
time-to-review
cycle time do accepted commita
review yield
rework
conflict detection before integration
IMPLEMENTED → VERIFIED conversion
VERIFIED → ACCEPTED conversion
human coordination time
fully loaded cost per ACCEPTED task
```

Ne koristiti kao north star:

```text
lines of code
number of agents
number of sessions
token utilization
number of commits
```

---

# 28. Predloženi prioriteti

## P0 — odmah

```text
FLOW-1109
FLOW-1110
FLOW-1105
FLOW-1106
FLOW-1201–1204
FLOW-1301–1305
FLOW-1401–1404
FLOW-1501–1504
```

## P1 — poslije dogfood baseline-a

Preporučeni redoslijed, uz potvrdu `FLOW-1504`:

```text
Current State / Handoff (1600)
Structured Findings (1700)
Task Contract / Program Design / slices (1800)
```

## P2 — tek nakon toga

```text
Managed Execution (1900)
Evaluation / routing (2000)
Durable Engine (2100)
Worker/Checker automation (2200)
```

## P3 — samo po dokazu

```text
Comprehension/quality automation
Project Readiness
Bottleneck analytics
Team/remote/PostgreSQL/container/extension
```

---

# 29. Šta se eksplicitno NE gradi sada

Do završetka `FLOW-1504`:

- AI orchestration engine;
- autonomous task decomposition authority;
- automatic model router;
- auto merge/push;
- full Findings lifecycle backend;
- USER_VALIDATION event;
- durable DAG engine;
- remote workers;
- telemetry platform;
- cloud sync;
- team permissions;
- AI priority score;
- completion percentage iz AI procjene;
- huge context/memory subsystem;
- manual `current.md` bureaucracy.

---

# 30. Test matrica koja mora nastaviti rasti

## Current State

- stariji report vs novija canonical odluka;
- missing evidence;
- unassigned report;
- multiple sessions;
- historical binding;
- stale Git snapshot;
- reconciliation event;
- no history.

## Task Detail

- Task sa PlanItem;
- Task bez PlanItem;
- implementation bez testova;
- test bez reviewa;
- review + NEEDS_WORK;
- accepted ali nije verified;
- evidence missing.

## Handoff

- fresh same model;
- fresh drugi model;
- current decision supersedes old;
- reference file missing;
- worktree changed;
- blocker postoji.

## Findings

- finding bez evidence;
- accepted risk;
- fix completed ali nije verified;
- re-review reopen;
- duplicate review finding.

## Managed

- timeout;
- cancel tree;
- path violation;
- command violation;
- approval required;
- stale capability;
- GUI zatvoren dok process radi.

## Durable

- process crash;
- service restart;
- duplicate event;
- unknown side effect;
- checkpoint restore;
- retry exhausted.

---

# 31. Predloženi razvojni ritam

Za svaki Task:

```text
1. jedan Task
2. jedan implementer
3. evidence
4. independent reviewer kada je opravdano
5. jedan finding/fix scope po korekciji
6. user decision
7. exact commit
8. remote verification
9. tek onda sljedeća akcija
```

To je namjerno disciplinovanije od „pokreni deset agenata“, ali povećava količinu rada koju čovjek može razumjeti i odgovorno prihvatiti.

---

# 32. Kada ćemo znati da je FlowOS stvarno uspio

Prvi važan milestone nije:

> FlowOS može pokrenuti agenta.

Nego:

> **Jedan stvarni development Task može od početne namjere do ljudske odluke biti razumljiv i dokaziv kroz LIVE FlowOS bez ručne rekonstrukcije iz chatova, terminala i report direktorijuma.**

Drugi milestone:

> **Fresh agent može nastaviti stvarni Task iz FlowOS Handoff State-a bez prethodnog chata.**

Treći:

> **Managed execution može bezbjedno automatizovati ograničeni tehnički korak bez preuzimanja ljudskog authority-ja.**

Četvrti:

> **FlowOS može dokazom pokazati da određeni agent/model/workflow smanjuje fully loaded cost po VERIFIED/ACCEPTED Tasku.**

Tek tada ima smisla skalirati broj agenata i automatizaciju.

---

# 33. Konačna razvojna mapa

```text
SADA
│
├─ 1109  Secret redaction
├─ 1110  Safe worktree identity
├─ 1105  PlanImport contract
└─ 1106  Real dogfood import
        │
        ▼
TASK-CENTRIC CONTROL PLANE
│
├─ 1200  Project + Tasks + Current State + Task Detail
├─ 1300  Workflow History + Evidence
├─ 1400  Human Decision + real E2E
└─ 1500  Dogfood UX baseline
        │
        ▼
CONTEXT + METHOD
│
├─ 1600  Current State / Attention / Handoff
├─ 1700  Structured Findings lifecycle
└─ 1800  Task Contract v2 / Program Design / Vertical Slices
        │
        ▼
CONTROLLED AUTOMATION
│
├─ 1900  Managed Execution
├─ 2000  Evaluation + model/harness + assisted routing
├─ 2100  Durable Job Engine
└─ 2200  Worker/Checker automation
        │
        ▼
ONLY IF PROVEN
│
├─ 2300  Comprehension / review budget
├─ 2400  Project Readiness / bottleneck view
└─ 2500  Team / remote / PostgreSQL / sandbox / extensions
```

---

# 34. Izvori objedinjeni u ovom planu

Primarno su objedinjene ideje iz dostavljenih dokumenata:

- `FlowOS_agent_context_current_work_state.md`
- `FlowOS_human_control_plane_progressive_context_analysis.md`
- `FlowOS_model_routing_handoff_portable_context.md`
- `FlowOS_unapredjenja_iz_Brett_transkripta.md`
- `FlowOS-detaljan-plan-unapredjenja-GUI-za-Crush-agenta.md`
- `FlowOS-Faza2-strogi-korektivni-nalog-za-pi-agenta.md`
- `FlowOS-novi-detaljan-plan-PySide6-v3-project-resume.md`

Plan takođe zadržava postojeći dogfooding redoslijed 11–15 kao najvažniji kratkoročni put i ugrađuje novije metodološke zaključke iz tekuće analize samo tamo gdje ne stvaraju novi authority source ili nepotrebnu infrastrukturu.

---

# 35. Konačna preporuka

Najvažnija promjena u odnosu na stare planove je redoslijed.

Stari plan je relativno rano uvodio:

```text
Inbox / Today
Managed Execution
Usage
Durable
Checker
```

Novi plan to namjerno pomjera iza prvog stvarnog dogfooding baseline-a.

Prvo treba dokazati:

```text
Task
→ stvarni rad
→ evidence
→ independent review
→ human decision
→ current state
```

Ako FlowOS tu petlju radi dobro, onda managed execution, handoff, model routing i durability postaju pojačivači stvarno vrijednog sistema.

Ako ta petlja ne radi, dodatna automatizacija bi samo brže proizvodila stanje koje čovjek ne može razumjeti.

Zato je glavni princip novog roadmapa:

> **Prvo napravi pouzdan control plane. Tek onda ubrzavaj fabriku.**
