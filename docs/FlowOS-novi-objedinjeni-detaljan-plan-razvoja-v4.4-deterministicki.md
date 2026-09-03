# FlowOS — novi objedinjeni detaljan plan razvoja v4.4
## Deterministički human control plane — proof over claims, bez internog LLM-a i bez agent orchestrationa

**Datum:** 2026-09-02  
**Status:** revidirani kandidat za kanonski roadmap  
**Osnova:** v4.3 + repo-grounded Claude analiza + lekcije iz Atomic verifiable-runtime dizajna, uz zadržavanje FlowOS granice: FlowOS ne izvršava agente

---

# 0. Zašto postoji v4.4

v4.3 je riješio najvažniju arhitektonsku grešku starijih planova: FlowOS više nije agent orchestrator i nema interni LLM koji odlučuje umjesto čovjeka.

Naknadna repo-grounded analiza pokazala je, međutim, da roadmap i dalje na nekoliko mjesta ne polazi dovoljno precizno od **stvarno postojećeg koda**. Istovremeno, analiza Atomic-a je potvrdila da su neke ideje o verifikaciji, provenance-u i inspectable proof-u vrlo vrijedne za FlowOS čak i kada se potpuno odbaci njihov runtime/orchestration sloj.

v4.4 zato radi četiri stvari:

1. **usklađuje roadmap sa postojećim kodom**, umjesto da ponovo projektuje servise koji već postoje;
2. **zaključava pasivnu granicu prema agentima** i čisti mrtve tragove starog wrapper/launch smjera;
3. **formalizuje proof model**: činjenica, izvedena činjenica, mehanički dokaz, heuristika, claim i ljudska odluka nisu ista stvar;
4. **razdvaja dva vrijednosna stuba proizvoda po redoslijedu**, bez odustajanja od ijednog:
   - prvo kontinuitet, evidence i human decision;
   - zatim paralelna koordinacija i conflict visibility.

Glavno pravilo ostaje:

> **AI radi. FlowOS pamti, povezuje i dokazuje. Čovjek odlučuje.**

Dodatna v4.4 formulacija:

> **FlowOS durability znači da engineering state preživljava nestanak chata ili agentske sesije — ne da FlowOS pokušava nastaviti LLM trace ili agentsko izvršenje.**

I:

> **Graph u FlowOS-u opisuje odnose. Ne izvršava rad.**

# 1. North Star

> **FlowOS je lokalni, deterministički human control plane za agent-potpomognuti razvoj. Održava provjerljivu vezu između ljudske namjere, Taska, eksternih razvojnih sesija, Git/worktree stvarnosti, dokaza, reviewa i odluka tako da čovjek može pouzdano razumjeti gdje je projekat, šta je dokazano i šta treba odlučiti bez ručne rekonstrukcije iz chatova, terminala i report direktorijuma.**

FlowOS ne optimizuje za:

```text
što više agenata
što više modela
što više tokena
što više paralelnih sesija
što više automatskih AI odluka
```

nego za:

```text
što više razumljivog i provjerljivog engineering rada
po jedinici ljudske pažnje
```

## 1.1 Dva vrijednosna stuba — jedan redoslijed

FlowOS ima dva povezana problema koja želi riješiti.

### Stub A — kontinuitet i dokazivost

Odgovara na pitanja:

```text
Šta je Task?
Šta trenutno važi?
Šta se stvarno promijenilo?
Koji dokaz postoji?
Šta je samo claim?
Šta nije provjereno?
Koja ljudska odluka važi?
Kako nastaviti bez starog chata?
```

Ovo je **prvi proof-of-value** i P0/P1 prioritet.

### Stub B — koordinacija paralelnog rada

Odgovara na pitanja:

```text
Koji Taskovi rade nad povezanim dijelovima koda?
Koji worktree je stale?
Gdje postoji write overlap?
Gdje postoji dependency conflict bez path overlap-a?
Koji ownership/attribution je stvarno dokaziv, a koji je samo heuristika?
Gdje je workflow bottleneck?
```

Ovo ostaje core vrijednost FlowOS-a, ali se implementira **nakon** što Stub A radi pouzdano.

To nije napuštanje paralelizma. To je redoslijed:

```text
proof + continuity
        ↓
human-controlled dogfood baseline
        ↓
parallel coordination intelligence
```

## 1.2 Primarni korisnički profil u ovoj fazi

Prva implementacija ostaje:

```text
jedan korisnik
lokalni Windows 10/11
više eksternih coding alata po izboru korisnika
Git/worktree projekti
SQLite
```

Team/multi-machine/PostgreSQL dolaze samo ako dogfooding ili realni korisnik dokaže potrebu.

# 2. Granica proizvoda

Arhitektura treba ostati ovakva:

```text
ČOVJEK
   │
   ├──────────────► Claude Code
   ├──────────────► Codex
   ├──────────────► Pi
   ├──────────────► Crush
   ├──────────────► Fusion Harness
   └──────────────► drugi alat
                         │
                         │ rade nad projektom
                         ▼
                 Git / files / worktrees
                         │
                         ▼
┌────────────────────────────────────────────────────┐
│                     FLOWOS                         │
│                                                    │
│  prati stanje                                      │
│  povezuje događaje                                 │
│  čuva canonical podatke                            │
│  razlikuje činjenice, signale i claimove           │
│  izvršava determinističke provjere                 │
│  prikazuje konflikte i nedostatke dokaza           │
│  održava Current State                             │
│  generiše deterministički Handoff                  │
│  prikazuje čovjeku gdje je potrebna odluka         │
│                                                    │
│               NEMA INTERNOG LLM-a                  │
│               NE POKREĆE AGENTE                    │
└────────────────────────┬───────────────────────────┘
                         │
                         ▼
                      ČOVJEK
```

FlowOS može integrisati podatke iz eksternih alata samo kao:

```text
READ
INGEST
CORRELATE
VERIFY
DISPLAY
```

Ne kao:

```text
START
PROMPT
SELECT
DELEGATE
RETRY
CONTROL
```

---

# 3. Deset trajnih arhitektonskih odluka v4.4

## D1 — FlowOS nikada ne spawn-uje agentski alat

FlowOS Session je logički tracking zapis, ne parent process Claude Code/Codex/Pi/Crush/Fusion procesa.

Dozvoljeni obrazac:

```text
FlowOS registruje Task / Session / worktree kontekst
        ↓
korisnik sam pokreće eksterni agentski alat
        ↓
eksterni alat radi nad projektom
        ↓
FlowOS posmatra i povezuje provjerljive posljedice
```

Postojeći launch-capability kod koji nema produkcijskog konzumenta tretira se kao mrtav trag starog smjera i čisti se.

`agent_scanner`-tip mehanizma je kompatibilan sa D1 jer samo posmatra.

## D2 — FlowOS ne gradi paralelni GitNexus

FlowOS koristi:

```text
BUILT-IN DETERMINISTIČKE SIGNALE
- Git changed paths
- worktree/base odnos
- explicit Task dependencies
- jednostavne lokalne reference gdje su trivijalno provjerljive

OPTIONAL EXTERNAL DEPENDENCY EVIDENCE
- GitNexus
- drugi read-only graph/index provider
```

Minimalni koncept je:

```text
DependencyEvidenceProvider
```

Provider vraća dokazive veze sa provenance-om. Provider nije authority i njegova nedostupnost ne smije srušiti core FlowOS.

## D3 — GUI primitive nastaju iz stvarnog Task Detail use-casea

Ne praviti GUI framework unaprijed.

`FLOW-1204 Task Detail` mora izvući samo one primitive koje su stvarno potrebne:

```text
DetailSection
StatusBadge
ActorBadge
ReferenceLink
EvidenceRow / EvidencePanel
TimelineItem / TimelineView
DecisionPanel
Empty / Unknown / MissingEvidence state
TaskDetailShell
```

Prvi dokaz da su zaista reusable dolazi u `FLOW-1302 Workflow History GUI`.

Dakle:

```text
Task Detail prvo
→ extract minimal reusable primitive
→ sljedeći ekran dokazuje reuse
```

Ne obrnuto.

## D4 — Atribucija ima strukturni plafon

FlowOS pasivno posmatra eksterni rad. Shared-tree attribution je po prirodi ograničen.

Koristiti:

```text
DIRECT
ISOLATED
HEURISTIC
UNKNOWN
```

Pravila:

- `HEURISTIC` nikad nije canonical authority;
- `HEURISTIC` ne može sama proizvesti hard block;
- `UNKNOWN` je validan rezultat;
- Bottleneck View se prvenstveno gradi iz canonical Task/Ledger state-a.

Postojeća legacy semantika (`WORKTREE / SOLE_ACTIVE / HINT / UNATTRIBUTED / USER` + `HIGH/MEDIUM/LOW`) mora biti eksplicitno mapirana ili uklonjena prije nego novi GUI počne da je prikazuje kao novu taksonomiju.

## D5 — Relativni sizing prije kalendarskih procjena

Svaki netrivijalni Task:

```text
S
M
L
XL
```

> **XL se ne implementira direktno. Mora se razbiti.**

Velocity se počinje bilježiti čim stvarni dogfooding plan proradi, ne tek na kraju P0.

Kalendarska procjena dolazi tek nakon stvarnog uzorka.

## D6 — Semantika informacije ima šest klasa

```text
SOURCE_FACT
DERIVED_FACT
MECHANICAL_EVIDENCE
HEURISTIC_SIGNAL
CLAIM
HUMAN_DECISION
```

Definicije:

### SOURCE_FACT

Direktno opažena činjenica iz konkretnog izvora.

Primjer:

```text
Git HEAD = abc123
fajl X je modified
worktree path = ...
```

### DERIVED_FACT

Deterministički zaključak izveden iz jednog ili više source factova.

Primjer:

```text
isti fajl je u changed-setu Taska A i Taska B
→ WRITE_OVERLAP
```

### MECHANICAL_EVIDENCE

Rezultat izvršive ili objektivne provjere koji može podržati ili oboriti konkretan kriterij.

Primjer:

```text
pytest command
exit_code = 0
stdout/stderr artifact
target_commit = abc123
```

Mechanical evidence nije automatski isto što i acceptance.

### HEURISTIC_SIGNAL

Objašnjiv signal koji nije dovoljno jak za canonical tvrdnju.

### CLAIM

Tvrdnja čovjeka, agenta, reporta ili eksternog alata koja nije sama po sebi mehanički dokaz.

### HUMAN_DECISION

Eksplicitna odluka korisnika koja ima workflow authority tamo gdje je to definisano.

### Gdje semantička klasa živi

Ne dodavati novu `information_class` kolonu u svaku postojeću tabelu bez potrebe.

Default:

```text
canonical entitet/event
→ semantika se izvodi iz tipa izvora

read-model / DTO
→ eksplicitno nosi semantic_class

importovani artifact/claim
→ čuva provenance + tip izvora dovoljan za determinističku klasifikaciju
```

Perzistirati dodatnu klasu samo gdje bez nje originalni izvor gubi značenje.

## D7 — Evidence mora imati provenance i validity kontekst

Minimalni evidence/artifact metadata model treba moći izraziti:

```text
source
producer/tool
task_id
session_reference nullable
worktree/reference nullable
command/check nullable
started_at / finished_at gdje postoji
target_commit / base_commit gdje postoji
exit_code nullable
artifact path/reference
content hash
semantic class
current / stale / unknown validity
```

Evidence bez konteksta nad kojim je proizveden nije dovoljno jak za dugoročni proof.

## D8 — Origin ≠ Actor ≠ Attribution

FlowOS ne smije spajati tri različita pitanja.

```text
ORIGIN
ko je inicirao/otvorio radni kontekst ili zapis, ako je poznato

ACTOR
ko je izvršio konkretnu evidentiranu akciju, ako je poznato

ATTRIBUTION
na osnovu čega FlowOS povezuje promjenu/commit/session sa Taskom
```

Ako neki podatak nije poznat:

```text
UNKNOWN
```

Ne nagađati.

## D9 — Recorded artifact ≠ instruction ≠ authority

To što je nešto sačuvano u FlowOS-u ne znači da je:

```text
uputstvo agentu
odobrenje
canonical decision
dokaz
```

AgentReport može biti recorded artifact i CLAIM.

Test output može biti MECHANICAL_EVIDENCE.

TASK_DECISION može biti HUMAN_DECISION.

Handoff je exported context, ne autoritet koji FlowOS automatski dispatchuje agentu.

## D10 — Graph je inspectable projection, nikada execution graph

FlowOS smije prikazati odnose:

```text
Task
→ dependency
→ Session
→ Worktree
→ Commit
→ Evidence
→ Review
→ Finding
→ Decision
```

Ali taj graph:

```text
ne pokreće node
ne scheduluje agent
ne radi retry
ne pause/resume agent
ne mijenja model
```

FlowOS graph objašnjava stanje i veze. Ne izvršava posao.

# 4. Neupitne arhitektonske granice

1. Primarna platforma ostaje Windows 10/11.
2. GUI ostaje PySide6 + Qt Widgets.
3. Backend ostaje odvojen Python/FastAPI proces.
4. Arhitektura ostaje `View → Controller → Services`.
5. SQLite ostaje lokalna baza dok stvarna potreba ne opravda PostgreSQL.
6. Git je autoritet za stanje koda, ali commit nije workflow acceptance.
7. Worktree je izolacija rada, ne Task.
8. Task, Session, Worktree, Report, Review, Finding, Evidence i Decision ostaju različiti koncepti.
9. FlowOS ne radi automatski merge/push zaštićenog targeta.
10. AgentReport je claim/evidence container, ne canonical authority.
11. Model ili agent ne potvrđuje sam svoj rezultat kao konačan dokaz.
12. `IMPLEMENTED ≠ VERIFIED ≠ ACCEPTED`.
13. User decision ostaje canonical authority za acceptance/rejection.
14. Prompt nije security boundary.
15. FlowOS core radi bez cloud servisa i bez LLM-a.
16. FlowOS core ne poziva LLM API radi zaključivanja.
17. FlowOS ne pokreće agentske alate.
18. FlowOS ne šalje prompt agentu ili modelu.
19. FlowOS ne bira model.
20. FlowOS ne dodjeljuje Task agentu.
21. FlowOS ne pokreće retry/correction petlju nad agentom.
22. FlowOS ne organizuje debate, opinion fan-out, swarm, fusion ili multi-agent collaboration.
23. FlowOS ne odlučuje semantički koji plan, model ili agent je bolji.
24. Ne uvoditi LLM gdje Git, SQL, state machine, parser, uski AST rule, eksterni deterministički evidence provider ili test mogu riješiti problem.
25. Ne uvoditi paralelne ručne `current.md`, `progress.md`, `decisions.md` kao izvore istine.
26. Generisani Current State/Handoff je projekcija canonical podataka, nikada input authority-ja.
27. Ne prikazivati procenat napretka bez objašnjivog pravila.
28. Ne izmišljati atribuciju, status ili completion kada nema dokaza.
29. Svaka nova složenost mora imati dokazanu potrebu i jasan konzument.
30. Eksterni deterministic evidence provider nije authority; provenance ostaje vidljiv.
31. Recorded artifact nije automatski instruction, proof ili authority.
32. FlowOS durability odnosi se na engineering state, ne na LLM trace ili agent execution.
33. Graph u FlowOS-u je read-model/projection, ne workflow executor.
34. `UNKNOWN` je legitimno stanje kada nema dovoljno podataka.
35. Nema paralelnog read-modela ako postojeći servis može biti proširen bez kršenja odgovornosti.

# 5. Dvije odvojene osi: proizvod i metod rada

## A. Product roadmap

Šta ugrađujemo u FlowOS.

## B. Engineering method

Kako čovjek, uz pomoć eksternih agentskih alata ako želi, radi svaki veći FlowOS Task.

Metod rada ne postaje automatski backend subsystem.

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
Locked Task Contract
        ↓
Implementation
        │
        ├─ contract i dalje važi
        │      → nastavi
        │
        └─ implementation pretpostavka je dokazivo pogrešna
               ↓
          Evidence-backed contract deviation
               │
               ├─ isti goal/scope/acceptance/risk
               │      → dokumentuj dokaz i nastavi
               │
               └─ mijenja scope/architecture/risk/acceptance
                      → STOP
                      → human decision
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

FlowOS može evidentirati artefakte i status ovog procesa.

FlowOS ga ne izvršava umjesto čovjeka.

---

# 6. Program Design i Locked Contract

## 6.1 Program Design checkpoint

Za veći scope, gdje je opravdano:

```text
Koji fajlovi se mijenjaju?
Koji tipovi/signature nastaju?
Kako izgleda call/data flow?
Koji testovi će dokazati rezultat?
Koje odluke su najmanje sigurne?
Kako se posao razbija na vertikalne, provjerljive rezove?
```

## 6.2 Locked ne znači nepogrešiv

Authoritative boundary:

```text
goal
scope / out_of_scope
acceptance
risk / approval granice
```

Implementation assumptions:

```text
predloženi fajlovi
konkretan tehnički recept
očekivani call path
pomoćna struktura
```

Ako je implementation assumption dokazivo pogrešna, bounded alternativa je dozvoljena samo kada:

```text
[ ] goal ostaje isti
[ ] scope ostaje isti
[ ] acceptance ostaje isti
[ ] risk nije povećan
[ ] postoji reproduktivan dokaz da je pretpostavka pogrešna
[ ] odstupanje je zapisano u report/evidence
```

U suprotnom:

```text
STOP
→ human decision
```

---

# 7. Polazna tačka

Postojeći temelj koji se zadržava:

- backend/control-plane;
- Workflow Ledger;
- `IMPLEMENTATION_COMPLETED`;
- `TEST_RESULT`;
- `REVIEW_COMPLETED`;
- `TASK_DECISION`;
- `WorkflowDecisionService`;
- Project Resume/reconciliation;
- Session evidencija;
- AgentReport;
- worktree/Git stanje;
- verification;
- postojeći `EvidenceService`;
- postojeći `ProjectStateService`;
- postojeći project/session timeline read-modeli;
- postojeći architecture guard;
- postojeći passive `agent_scanner` mehanizam.

## 7.1 Važna v4.4 korekcija: prvo inventar, onda novi read-model

Prije `FLOW-1203`, `FLOW-1302` i `FLOW-1602` mora biti jasno šta se dešava sa postojećim:

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

Bez te odluke roadmap ne smije praviti paralelni izvor istine.

## 7.2 Stanje FLOW-1109

Prema posljednjoj repo-grounded provjeri koja je bila osnova za v4.4, `FLOW-1109 Secret redaction` je završen i commitovan.

Zato više nije aktivni blocker.

U roadmapu ostaje kao historical security checkpoint čiji testovi moraju ostati non-regression.

## 7.3 Aktivni near-term blokatori

```text
FLOW-1110 — Safe worktree identity
FLOW-1105 — Plan Import contract
FLOW-1106 — Real dogfood import
FLOW-1107 — Start velocity baseline
FLOW-1111 — Passive Session cleanup
FLOW-1112 — Evidence Semantics & Provenance Contract
FLOW-1113 — Existing Read-Model Inventory
FLOW-1114 — FlowOS-owned Subprocess Safety
FLOW-1115 — Documentation / Repository Contract Alignment
```

---

# 8. FAZA A — Sigurnosni, semantički i dogfooding blokatori

## FLOW-1109 — Secret redaction `[COMPLETED / NON-REGRESSION]`

Ne planirati novi implementation scope osim ako regression pokaže problem.

Stalni gate:

- registrovani secret ne završava u persisted report/artifact outputu;
- redaction se dešava prije truncation-a;
- targeted security testovi ostaju green.

## FLOW-1110 — Safe worktree identity `[M]`

Postojeći prefix obrazac mora biti uklonjen **svuda gdje path identitet utiče na managed worktree odluku**, ne samo u cleanup grani.

Zabranjeno:

```python
wt.path == path or wt.path.startswith(path)
```

Obavezno:

- canonical/resolved path;
- Windows case semantics;
- bez prefix collision-a;
- cleanup samo tačnog worktree-a;
- managed/main identitet ne koristi tekstualni prefix;
- project_id provjera;
- dirty zaštita;
- fail-closed ponašanje.

Gate najmanje:

```text
FLOW-1 ≠ FLOW-10
slični prefiksi nisu identitet
pogrešan project_id se odbija
pogrešan path ne cleanup-uje drugi tree
managed/main odluka koristi tačan path identitet
tačan worktree cleanup radi
dirty zaštita ostaje
```

## FLOW-1105 — Plan Import contract `[S]`

Problem se tretira kao slomljen E2E contract, ne samo naming drift.

Obavezno:

- jedan canonical field: `markdown_text`;
- GUI šalje isti contract;
- FastAPI endpoint prima `PlanImportRequest`, ne raw `body: dict`;
- parser dobija isti payload;
- contract test;
- čitljiva import greška;
- realni Markdown payload prolazi `GUI → API → Pydantic contract → parser`.

## FLOW-1106 — Real dogfood import `[S]`

- FlowOS projekat registrovan;
- plan importovan kroz LIVE tok;
- faze/items/criteria/dependencies potvrđeni;
- nejasnoće prikazane čovjeku;
- nema retroaktivnog fabrikovanja Ledger istorije.

## FLOW-1107 — Start velocity baseline `[S]`

Odmah nakon 1106 početi zapis za svaki naredni stvarni FlowOS Task:

```text
Task ID
size S/M/L
calendar start/end
human attention gdje je poznat
review time
broj korekcija
rework
```

Bez analytics platforme.

`FLOW-1505` kasnije samo analizira već prikupljen uzorak.

## FLOW-1111 — Passive Session cleanup `[S]`

Ovo nije velika nova arhitektura. Produkcijski `session_start` već ne treba da spawn-uje agentski alat.

Cilj je ukloniti kontradiktorne tragove starog smjera.

Provjeriti i riješiti:

```text
AdapterCapabilities.can_launch default
AgentProcessLauncher / launch() mrtav produkcijski put
kill_process_tree koji postoji samo radi starog launch smjera
pid=os.getpid() ako se upisuje kao "session PID"
prazni execution/jobs/approvals/usage/process paketi koji reklamiraju ukinutu arhitekturu
get_command()/get_environment() u adapterima
```

Za `get_command/get_environment` eksplicitno odlučiti:

```text
KEEP AS PASSIVE TOOL METADATA
ili
REMOVE
```

`agent_scanner.py` ostaje dozvoljen passive observation mehanizam.

Gate:

```text
FlowOS session register/start ne spawn-uje agent
nema lažnog session PID-a
nema can_launch defaulta koji reklamira nedozvoljenu capability
mrtvi launch kod nema produkcijskog konzumenta
pasivni scanner ostaje read-only
```

## FLOW-1112 — Evidence Semantics & Provenance Contract `[M]`

Zaključati šest klasa iz D6:

```text
SOURCE_FACT
DERIVED_FACT
MECHANICAL_EVIDENCE
HEURISTIC_SIGNAL
CLAIM
HUMAN_DECISION
```

Obavezno:

- definisati determinističko pravilo klasifikacije po source type-u;
- ne dodavati semantic column u svaku tabelu po defaultu;
- read-model DTO nosi `semantic_class`;
- importovani artifact/claim čuva provenance;
- `MECHANICAL_EVIDENCE` je posebna klasa;
- claim se ne promoviše u proof;
- derived fact može pokazati source fact reference;
- UI ima različitu prezentaciju za proof/claim/heuristic/unknown.

### Legacy attribution map

U istom Tasku definisati kako postojeći:

```text
WORKTREE
SOLE_ACTIVE
HINT
UNATTRIBUTED
USER

HIGH / MEDIUM / LOW
```

mapira ili migrira u:

```text
DIRECT
ISOLATED
HEURISTIC
UNKNOWN
```

Ne dozvoliti da P0 GUI koristi dvije nekompatibilne taksonomije.

## FLOW-1113 — Existing Read-Model Inventory `[S]`

Napraviti kratku, repo-grounded odluku za:

```text
EvidenceService
ProjectStateService
project_timeline
sessions/timeline
reconciliation
```

Za svaki zapisati:

```text
trenutna odgovornost
ključ
koji source koristi
koji roadmap Task ga proširuje
da li ostaje canonical projection
da li nešto treba deprecated
```

Gate:

> `FLOW-1203`, `1301/1302` i `1602` ne uvode paralelni read-model bez eksplicitne odluke iz ovog inventara.

## FLOW-1114 — FlowOS-owned Subprocess Safety `[M]`

Ovo je **nova obaveza**, ne postojeći non-regression contract, dok se ne implementira.

Odnosi se samo na FlowOS-owned determinističke subprocess-e, npr. `verify.py`.

Obavezno:

- filtered/allowlisted env;
- secrets nisu proslijeđeni bez potrebe;
- timeout završava cijeli FlowOS-owned child process tree na Windowsu;
- exit code/stdout/stderr ostaju tačni;
- cancel semantics se ne predstavljaju jače nego što stvarno jesu.

Gate:

```text
child koji spawn-uje grandchild
+ timeout
→ nema preživjelog FlowOS-owned procesa

sensitive env var
+ verify subprocess
→ nije proslijeđen bez allowlist pravila
```

## FLOW-1115 — Documentation / Repository Contract Alignment `[S]`

Ažurirati dokumente koji agenti moraju čitati:

```text
CLAUDE.md
AGENTS.md
README.md
drugi canonical project instructions ako postoje
```

Ukloniti ili označiti deprecated:

```text
Wrapper kao kičma ako implicira launch
obavezni agent adapter redoslijed za launch
Managed Execution
Durable Agent Engine
Worker/Checker orchestration
model routing kao FlowOS odgovornost
can_launch capability kao dozvoljena core funkcija
```

Dokumentacija mora eksplicitno reći:

> FlowOS posmatra, pamti, povezuje, provjerava i prikazuje. Ne izvršava agentski rad.

### Gate faze A

Ne prelaziti u Fazu 12 dok:

```text
[ ] 1109 security regression ostaje green
[ ] 1110 accepted
[ ] 1105 PlanImport radi end-to-end
[ ] 1106 dogfood plan je aktivan
[ ] 1107 velocity zapis je počeo
[ ] 1111 passive session cleanup accepted
[ ] 1112 evidence/provenance taxonomy zaključana
[ ] legacy attribution je mapiran
[ ] 1113 existing read-model inventory završen
[ ] 1114 subprocess safety accepted
[ ] 1115 canonical docs usklađeni
```

# 9. FAZA 12 — Projekat i Task postaju stvarna radna površina

## FLOW-1201 — Minimalni izbor i registracija projekta `[S]`

- aktivni projekat vidljiv;
- izbor postojećeg projekta;
- `Dodaj projekat`;
- bez automatskog `git init`;
- Plan/Zadaci/Sesije/Resume/Aktivnost prate aktivni projekat.

## FLOW-1202 — `Zadaci` na stvarni backend `[M]`

Prikazati:

- human-readable naslov;
- Task ID sekundarno;
- status;
- PlanItem vezu;
- attention signal samo iz objašnjivih pravila;
- bez AI prioritizationa;
- bez fake progressa.

Gate:

> Task kreiran u backendu pojavljuje se u LIVE GUI-ju bez mock podataka.

## FLOW-1203 — Task Current State read-model `[M]`

Ne uvoditi `TaskContract` kao dependency — strukturisani Task Contract model još nije dio P0.

Polaziti od odluke iz `FLOW-1113`.

Sastaviti ili proširiti postojeću projekciju iz:

```text
Task
PlanItem
SessionTaskBinding history
AgentReport
Workflow Ledger
Verification / EvidenceService
Git/worktree state
latest TASK_DECISION
reconciliation
blockers
```

Output:

```text
Task identity
Goal/description iz postojećeg Task/Plan modela
Plan position
Current workflow facts
Relevant external sessions
Current Git/worktree state
Latest implementation claim/evidence
Latest mechanical verification evidence
Latest review
Latest user decision
Open evidence gaps
Current blockers
```

Svaka stavka po potrebi nosi:

```text
semantic_class
provenance/reference
validity/currentness
```

Pravila:

- nema AI summary-ja kao authority;
- nema `DONE` izvedenog iz commita ili session close-a;
- `UNKNOWN`/`Nema dokaza` je validno;
- novija canonical odluka nadjačava stariji claim.

## FLOW-1204 — Task Detail GUI + prvi reusable primitives `[L]`

Prvih 10 sekundi odgovara:

```text
Šta je ovo?
Zašto postoji?
Gdje pripada u planu?
Ko je radio — ako je poznato?
Šta se promijenilo?
Šta je dokazano?
Šta je samo claim?
Šta je heuristika?
Šta je stale?
Šta nedostaje?
Šta traži moju pažnju?
```

Minimalni layout:

```text
Task naslov + status + plan veza

TRENUTNO STANJE
DOKAZI
WORKFLOW HISTORY placeholder
ODLUKA placeholder
```

Tokom stvarne implementacije izvući samo korištene primitive:

```text
DetailSection
StatusBadge
ActorBadge
ReferenceLink
EvidenceRow / EvidencePanel
TimelineItem / TimelineView ako je stvarno potreban
DecisionPanel
Empty / Unknown / MissingEvidence state
TaskDetailShell
```

Ne praviti apstrakciju za hipotetičke buduće ekrane.

### Gate

- Task Detail radi nad LIVE backendom;
- semantic classes su vizuelno razlikovane;
- evidence otvara provenance;
- korisnik može objasniti Task i current state bez starog chata;
- reusable primitive su izvučene samo gdje su već stvarno korištene.

Prvi pravi reuse gate dolazi u FLOW-1302.

# 10. FAZA 13 — Workflow History i inspectable evidence

## FLOW-1301 — Unified Task Workflow History read-model `[M]`

Postojeća četiri canonical eventa dolaze iz više writer/service mjesta.

Read-model mora eksplicitno ujediniti:

```text
IMPLEMENTATION_COMPLETED
TEST_RESULT
REVIEW_COMPLETED
TASK_DECISION
```

bez stvaranja novog authority source-a.

Pravila:

- append-only;
- stvarni event time + stabilan tie-break;
- commit/file/session close nisu completion event;
- AgentReport body nije history authority.

## FLOW-1302 — Workflow History GUI + reuse proof `[M]`

Koristi primitive nastale iz `FLOW-1204`.

Razlikovati:

```text
External implementer/agent
Sistem / mechanical evidence
Reviewer
Korisnik
```

### GUI reuse gate

Najmanje jedan primitive iz Task Detail-a mora biti ponovo korišten bez copy/paste paralelne widget strukture.

Ako reuse izgleda neprirodno:

> korigovati primitive, ne forsirati apstrakciju.

## FLOW-1303 — Inspectable Evidence navigation `[M]`

Iz history/evidence reda otvoriti:

```text
implementation → report/claim
test → command + exit code + stdout/stderr artifact + target commit gdje postoji
review → review report + provenance
decision → decision metadata
```

Nedostajući dokaz ostaje nedostajući.

Evidence prikaz treba odgovoriti:

```text
odakle dolazi?
koji Task?
koji commit/worktree?
kada je proizveden?
koji check?
koji hash/reference?
da li je current, stale ili unknown?
```

Nikada se ne generiše zamjenski AI dokaz.

## FLOW-1304 — Workflow History ≠ Technical Activity `[S]`

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

## FLOW-1305 — Regression Proof baseline `[M]`

Pravilo:

```text
BUGFIX
→ pre-change FAIL / post-change PASS dokaz je obavezan gdje je tehnički reproducibilan

NEW FEATURE
→ pre-change FAIL nije obavezan ako kriterij nema smislen prethodni failure state
```

Za bugfix:

```text
pre-change code + novi regression test → FAIL
patched code + isti test → PASS
```

Historical replay ne mijenja aktivni implementation worktree.

Koristiti:

```text
git show
git ls-tree
git cat-file
```

ili izolovani privremeni worktree.

### Gate faze 13

```text
[ ] sva 4 canonical eventa su objedinjena u Task history
[ ] history i Technical Activity su odvojeni
[ ] stvarni test evidence se može otvoriti do provenance detalja
[ ] missing/stale evidence se ne prikriva
[ ] jedan stvarni bugfix ima FAIL→PASS regression proof
```

# 11. FAZA 14 — Human Decision i prvi pravi E2E tok

## FLOW-1401 — TASK_DECISION kontrole `[M]`

```text
Prihvati rezultat
Vrati u doradu
Odbaci rezultat
```

Prije odluke prikazati:

- Task;
- relevantni diff/report;
- MECHANICAL_EVIDENCE;
- CLAIM-ove;
- HEURISTIC_SIGNAL-e ako postoje;
- review;
- šta je stale;
- šta nije provjereno.

## FLOW-1402 — Backend-confirmed consequence `[S]`

GUI poslije odluke reloaduje canonical state.

`ACCEPTED` ne glumi `VERIFIED`.

UI ne zaključuje consequence iz lokalnog klika prije potvrđenog backend state-a.

## FLOW-1403 — Kompletan dogfooding tok `[M]`

Jedan stvarni FlowOS development Task:

```text
IMPLEMENTATION_COMPLETED
→ TEST_RESULT
→ REVIEW_COMPLETED
→ TASK_DECISION
```

Cijela priča mora biti razumljiva kroz LIVE FlowOS.

## FLOW-1404 — SessionTaskBinding historical proof `[M]`

Dokazati:

```text
A → B → A
A → B → UNASSIGNED
```

Istorijski binding nadjačava trenutni session field za attribution istorijskog eventa.

### Gate faze 14

Bez terminalske rekonstrukcije korisnik može:

```text
1. objasniti šta je Task trebao uraditi
2. otvoriti relevantni proof
3. razlikovati claim / evidence / heuristic / decision
4. vidjeti šta nije provjereno
5. vidjeti šta je stale
6. donijeti TASK_DECISION
7. nakon odluke vidjeti backend-confirmed state
```

Faza 14 nije ACCEPTED dok jedan stvarni Task ne prođe cijeli tok.

# 12. FAZA 15 — UX simplification, baseline i velocity calibration

## FLOW-1501 — Zabilježiti stvarne UX probleme `[S]`

Za 5–10 Taskova zabilježiti:

- gubitak mentalnog modela;
- potrebu za starim chatom;
- nedostupan evidence;
- previše tehničkih detalja;
- teško vidljiv scope drift;
- prevelik review;
- slab Resume;
- nejasnu razliku između claim/proof/heuristic.

## FLOW-1502 — Pojednostaviti navigaciju uz eksplicitnu sudbinu postojećih stranica `[M]`

Ciljni primarni nivo, ako dogfooding potvrdi:

```text
Pregled
Zadaci
Plan
Aktivnost
```

Sekundarni/tehnički kandidat:

```text
Sesije
Radna stabla
```

Ali ne smije tiho nestati postojeći GUI.

Za svaku postojeću stranicu zapisati odluku:

```text
Agenti
Konflikti
Izvještaji
Projekti
Postavke
```

Dozvoljene odluke:

```text
KEEP
MERGE INTO TASK/ACTIVITY
RELOCATE
REMOVE
```

Svaka `REMOVE` odluka mora imati dokaz da funkcija nema konzumenta ili je potpuno zamijenjena.

`Aktivnost` kao primarna stranica se ne uvodi samo nazivom — mora biti jasno da li zamjenjuje postojeći widget/page i šta u nju ulazi.

## FLOW-1503 — Ukloniti MOCK/live nejasnoće `[M]`

- nema hardkodiranih statistika;
- placeholder jasno označen;
- MOCK i LIVE se ne miješaju;
- centralni presentation sloj statusa;
- semantic class badge/label je konzistentan.

## FLOW-1504 — Zamrznuti prvi dogfood baseline `[S]`

Obavezno:

- screenshotovi LIVE ekrana;
- šta stvarno radi;
- šta je odgođeno;
- poznati problemi;
- evidence kompletnog E2E toka;
- odluka o sudbini postojećih GUI stranica;
- korisnička odluka o sljedećem prioritetu.

## FLOW-1505 — Velocity calibration `[S]`

Analizirati podatke koji se prikupljaju od `FLOW-1107`.

Za najmanje 5 stvarnih Taskova:

```text
size S/M/L
calendar elapsed
human attention time gdje je poznat
review time
broj korekcija
rework
```

Cilj:

> procijeniti da li je P1 realno sedmice ili mjeseci i gdje je stvarni bottleneck.

Ne stvarati analytics platformu.

### ROADMAP GATE

Prije P1:

```text
[ ] 1504 accepted
[ ] najmanje 5 Taskova ima velocity podatke
[ ] Task Detail primitive su dokazale reuse u 1302 ili su korigovane
[ ] navigation odluke su eksplicitne
[ ] nema paralelnih read-modela izvan odluke FLOW-1113
```

# 13. FAZA 16 — Current State Projection i portable Handoff

## FLOW-1601 — Strukturisani Current State `[M]`

Polaziti od `FLOW-1113` i postojećih read-modela.

Tri projekcije iz istog canonical stanja:

```text
Project State
Human Attention State
Handoff State
```

Ne tri nove baze i ne tri paralelna authority modela.

## FLOW-1602 — Project State `[S]`

```text
current goal
active PlanItem/Task
latest canonical decision
active/recent sessions
Git/worktree state
mechanical evidence
open blockers
last safe checkpoint
```

Ako postojeći `ProjectStateService` već daje dio ovoga:

> proširiti ga ili sastaviti tanku projekciju; ne praviti novi servis sa istom odgovornošću.

## FLOW-1603 — Human Attention State `[M]`

Prioriteti:

1. blocking/risky human decision;
2. failed/missing/stale verification;
3. material finding;
4. implementation bez verificationa;
5. verification bez user decisiona;
6. state mismatch;
7. informativna aktivnost.

Task može zadovoljiti više pravila.

Deterministička semantika:

```text
priority_rank = najviši relevantni prioritet
reasons = svi pogođeni razlozi
```

Stabilni tie-break:

```text
severity
→ oldest waiting_since
→ stable Task ID
```

UI prikazuje sve razloge, ne samo prvi.

Bez AI prioritizationa.

## FLOW-1604 — Handoff State `[M]`

```text
Goal
Current state
Relevant files
Constraints
Definition of done
Checks to run
References
```

Po potrebi:

```text
latest authoritative decisions
canonical failed approaches
active findings
worktree/base commit
relevant evidence references
```

FlowOS handoff:

```text
generiše
prikazuje
kopira
eksportuje
```

Ne šalje ga agentu.

Recorded Handoff nije instruction ni authority.

## FLOW-1605 — Handoff rendereri `[S]`

```text
Markdown
JSON/API
Clipboard
GUI preview
```

## FLOW-1606 — Fresh-session dogfood `[M]`

```text
eksterna sesija stane
→ FlowOS generiše handoff
→ korisnik ručno otvara novi eksterni alat/session
→ korisnik predaje handoff
→ rad se nastavlja bez starog chata
```

### Durability gate

FlowOS dokazuje svoju vrstu durability-ja ako:

> engineering state i reference potrebne za nastavak prežive nestanak prethodne chat/session istorije.

FlowOS ne pokušava resume LLM trace-a.

# 14. FAZA 17 — Structured Findings lifecycle

Pokrenuti samo ako report-only findings postanu stvarni bottleneck.

## FLOW-1701 — Finding model `[M]`

Minimalno:

```text
id
task_id
review_id/report_id nullable
source_type
category
finding_code nullable
severity
title
description
evidence reference
status
created_at
```

`category` nije slobodan neograničen tekst.

Početni kontrolisani skup može biti:

```text
SECURITY
ARCHITECTURE
REGRESSION
TEST_EFFECTIVENESS
SCOPE_DRIFT
CONTRACT_ASSUMPTION
DATA_INTEGRITY
RUNTIME
UX
DOCUMENTATION
OTHER
```

`finding_code` je stabilniji identifikator konkretne klase problema, npr.:

```text
ARCH-VIEW-001
TEST-PATH-001
SEC-SECRET-001
```

Za `FLOW-2004 Repeated Finding → Guard Candidate` automatsko grupisanje je dozvoljeno samo kada postoji isti stabilni `finding_code` ili drugo eksplicitno deterministic normalization pravilo.

Ne grupisati free-text findings LLM-om.

Source može biti:

```text
human review
eksterni agent report
verification result
deterministički guard
```

FlowOS ne generiše finding LLM zaključivanjem.

## FLOW-1702 — FINDING_DECIDED `[S]`

Čovjek bira:

```text
FIX_REQUIRED
ACCEPTED_RISK
REJECTED_FINDING
DEFERRED
```

## FLOW-1703 — FIX_COMPLETED `[S]`

FlowOS evidentira prijavljeni fix i evidence.

Ne pokreće implementera.

## FLOW-1704 — VERIFICATION_COMPLETED `[M]`

```text
CLOSED
OPEN
PARTIAL
```

`FIXED ≠ VERIFIED`.

## FLOW-1705 — Findings GUI `[L]`

Mora koristiti primitive dokazano upotrebljive iz Task Detail/History toka.

Ne praviti novi paralelni detail framework.

## FLOW-1706 — USER_VALIDATION kandidat `[S]`

Samo gdje business/UX ponašanje stvarno zahtijeva ručnu potvrdu.

# 15. FAZA 18 — Strukturisani Task Contract i pre-execution design gates

Do ove faze `Task Contract` postoji kao metod/artefakt rada, ne kao potvrđeni canonical DB model.

Zato se više ne koristi naziv „v2“ koji implicira strukturisani v1 u kodu.

## FLOW-1801 — Structured Task Contract `[M]`

Minimalno:

```text
goal
scope
out_of_scope
acceptance criteria
risk
allowed paths hint
verification commands
```

Po potrebi:

```text
working hypothesis
unknowns
dependencies
```

### Authoritative boundary

```text
goal
scope / out_of_scope
acceptance
risk / approval granice
```

### Implementation assumption

```text
predloženi fajlovi
konkretan tehnički recept
očekivani call path
pomoćna struktura
```

Bounded deviation je dozvoljen samo uz evidence da authoritative boundary nije promijenjen.

## FLOW-1802 — Risk/size-based planning depth `[S]`

```text
Mali:
Task Contract → implement → verify

Srednji:
Goal/Product clarification → Program Design → slices → implementation

Visok rizik:
Grill → Research Probe → Architecture → Program Design → human approval → slices
```

FlowOS ne pokreće ove AI/metodološke korake.

## FLOW-1803 — Program Design artifact `[M]`

```text
files
types/signatures
call/data flow
test plan
least-confident decisions
implementation assumptions
```

## FLOW-1804 — Decision Inbox `[M]`

Prikazuje:

```text
decision/question
confidence ako ga source eksplicitno dostavi
impact
alternatives
evidence
source
```

FlowOS ne odlučuje.

## FLOW-1805 — Vertical Slice Plan `[M]`

Ne praviti horizontalni megadiff bez provjerljivog end-to-end checkpointa.

## FLOW-1806 — Acceptance Criterion ↔ Evidence Mapping `[M]`

Za svaki strukturisani acceptance criterion omogućiti vezu prema evidence-u.

Stanja:

```text
PROVEN
UNPROVEN
STALE
MANUAL_CONFIRMATION_REQUIRED
```

Pravila:

- `PROVEN` samo kada postoji odgovarajući current MECHANICAL_EVIDENCE ili eksplicitna human validation odluka gdje je kriterij ručan;
- AgentReport claim ne može sam dati `PROVEN`;
- jedan evidence artifact može podržati više kriterija samo uz eksplicitnu vezu;
- jedan kriterij može imati više evidence artefakata;
- promjena relevantnog commita/fajla može stanje vratiti u `STALE`.

FlowOS tada smije deterministički reći:

```text
2/3 kriterija imaju current proof
1 kriterij zahtijeva manual confirmation
```

Ne smije reći:

```text
Task je 67% gotov
```

ako takav procenat nema eksplicitno definisanu semantiku.

# 16. FAZA 19 — Deterministička observability i correlation

## FLOW-1901 — External Session metadata `[M]`

Prvi provider podataka treba biti ono što već postoji i što je pasivno, uključujući postojeći scanner gdje je primjenjivo.

Gdje je dostupno:

```text
session reference
tool/harness label
project
recorded start/end
task binding
worktree
external session id nullable
status known/unknown
origin nullable
actor nullable
```

Session metadata nije Task completion.

Scanner signal:

```text
observed process exists
```

nije isto što i:

```text
Task is being implemented
```

## FLOW-1902 — Session ↔ Git correlation `[L]`

Povezati gdje je dokazivo:

```text
session
worktree
branch
base commit
changed files
commit
Task
```

Attribution koristi:

```text
DIRECT
ISOLATED
HEURISTIC
UNKNOWN
```

i eksplicitno navodi `attribution_basis`.

Ne koristiti numerički confidence procenat bez stvarnog statističkog modela.

Origin/actor/attribution se ne miješaju.

## FLOW-1903 — Evidence ingestion i provenance `[M]`

Ingest/index:

```text
AgentReport
review report
test output
verification artifact
diff/commit metadata
structured findings
external deterministic provider result
```

Minimalni artifact metadata iz D7:

```text
source
producer/tool
task
session nullable
worktree nullable
command/check nullable
started_at / finished_at nullable
target_commit / base_commit nullable
exit_code nullable
artifact path/reference
content hash
semantic class
validity/currentness
```

Import ne znači povjerenje sadržaju.

## FLOW-1904 — Information semantics enforcement `[M]`

Backend/API/UI očuvavaju:

```text
SOURCE_FACT
DERIVED_FACT
MECHANICAL_EVIDENCE
HEURISTIC_SIGNAL
CLAIM
HUMAN_DECISION
```

Recorded item nema implicitno instruction/authority značenje.

## FLOW-1905 — Stale evidence detection `[L]`

Ako se promijeni dokazivo relevantni:

```text
target/base commit
relevantni fajl
worktree state
structured Task Contract
verification command/version gdje je relevantno
```

FlowOS označava raniji evidence kao:

```text
CURRENT
STALE
UNKNOWN_VALIDITY
```

Ne tvrdi da je evidence sadržajno pogrešan bez dokaza.

### Phase 19 hard rule

`HEURISTIC_SIGNAL` može proizvesti upozorenje, ali ne može sam proizvesti:

```text
Task rejection
canonical attribution
hard conflict block
user decision
```

# 17. FAZA 20 — Deterministički senzori i preventivni guardovi

## FLOW-2001 — Guard Registry `[M]`

Prvi cilj nije stvaranje novih guardova, nego registracija onoga što već postoji.

Minimalno:

```text
guard_id
name
scope
source
severity
command/parser
enabled
version
description
```

Prvi kandidat za registraciju:

```text
scripts/guard_architecture.py
```

Ako već ruši `verify.py`, registry ga opisuje i povezuje sa evidence-om; ne pravi drugi paralelni architecture guard.

## FLOW-2002 — Deterministički izvori `[M]`

```text
Git
Ruff/Pylint
mypy
pytest
postojeći architecture guard
AST za usko definisan rule
dependency evidence provider
path policy
known static rule
```

## FLOW-2003 — Architecture guardovi `[M]`

Prvo mapirati šta postojeći `guard_architecture.py` već provjerava.

Novi rule dodati samo za dokazanu rupu.

Primjeri:

```text
View direktno mutira Service
Controller koristi persistence direktno
Service zavisi od UI sloja
```

ali samo ako takvo pravilo nije već pokriveno.

## FLOW-2004 — Repeated Finding → Guard Candidate `[M]`

Automatski kandidat samo ako postoji:

```text
isti finding_code
na najmanje 2 nezavisna Taska
```

ili drugo eksplicitno deterministic normalization pravilo.

FlowOS ne koristi LLM za semantičko grupisanje nalaza.

FlowOS ne kreira automatski guard.

## FLOW-2005 — Guard provenance `[S]`

Za promjenu/suppress guard-a prikazati:

```text
Task
diff
reason/report
human decision ako postoji
```

# 18. FAZA 21 — Cross-worktree conflict intelligence

Ova faza je namjerno sužena da FlowOS ne postane novi GitNexus.

## FLOW-2100 — Dependency Evidence Strategy & Provider Contract `[S]`

GitNexus se tretira kao postojeći praktični izvor dependency/impact podataka koji već ima vrijednost u svakodnevnom radu.

Cilj nije ponovo dokazivati da dependency graph može biti koristan.

Cilj je definisati **minimalni read-only provider ugovor**.

Minimalni rezultat:

```text
provider_id
provider_version nullable
project/repo reference
relation_kind
source_path/symbol
target_path/symbol
evidence/reference
observed_at
content/index revision ili hash gdje postoji
status = AVAILABLE / UNAVAILABLE / STALE / ERROR
```

Minimalne `relation_kind` vrijednosti:

```text
IMPORTS
REFERENCES
CALLS
TEST_TARGETS
DEPENDS_ON
IMPACT
```

Pravila:

- provider output ima provenance;
- provider nedostupan ne ruši FlowOS core;
- FlowOS ne izmišlja relation kada provider nema dokaz;
- provider result nije canonical ownership authority;
- cache može postojati, ali stale index mora biti vidljiv.

Default:

> Ne graditi vlastiti general-purpose AST/call graph engine.

## FLOW-2101 — WRITE_OVERLAP `[M]`

Built-in:

```text
Task A changed/allowed paths
∩
Task B changed/allowed paths
```

Ne zavisi od attribution heuristike da bi pokazao overlap činjenicu.

## FLOW-2102 — STALE_BASE `[M]`

Prikazati da worktree/branch radi nad starijom relevantnom bazom.

Ne raditi automatski rebase.

## FLOW-2103 — DEPENDENCY_REFERENCE `[L]`

Prioritet izvora:

```text
1. explicit Task dependency
2. existing GitNexus/DependencyEvidenceProvider
3. usko definisana built-in referenca samo gdje je jednostavna i provjerljiva
```

Ako pouzdan provider ne postoji:

> FLOW-2103 se odgađa. Ne gradi se generički graph samo da bi roadmap bio „kompletan“.

## FLOW-2104 — ASSUMPTION_INVALIDATED `[M]`

Samo kada postoji strukturisan dokaziv signal.

Ne koristiti opšti semantic AI conflict engine.

### Conflict severity pravilo

```text
SOURCE_FACT / DERIVED_FACT
+ DIRECT / ISOLATED attribution gdje je ownership potreban
→ jak conflict warning

HEURISTIC attribution
→ possible conflict signal

UNKNOWN
→ nema ownership tvrdnje
```

### Gate faze 21

```text
[ ] write overlap radi bez GitNexusa
[ ] stale base radi bez GitNexusa
[ ] provider unavailable ne ruši core
[ ] provider evidence ima provenance
[ ] dependency conflict može biti uhvaćen bez path overlap-a kada provider daje dokaz
[ ] unrelated modul ne daje false positive u testnom scenariju
```

# 19. FAZA 22 — Project Readiness i bottleneck visibility

## FLOW-2201 — Project Readiness `[M]`

Deterministički:

```text
verify command postoji?
build poznat?
test suite postoji?
Git state poznat?
active worktree?
project instructions postoje?
migration state?
unresolved findings?
clean baseline?
```

Bez neobjašnjivog score-a.

## FLOW-2202 — Bottleneck View `[M]`

Iz canonical workflow stanja:

```text
5 Taskova čeka review
3 čeka human decision
2 čeka fix
1 čeka verification
```

Ne bazirati bottleneck na HEURISTIC session ownershipu.

## FLOW-2203 — Human Attention Projection `[M]`

Povezati:

```text
blockers
verification gaps
findings
pending decisions
state mismatch
```

Bez AI prioritizationa.

---

# 20. FAZA 23 — Human comprehension i relationship visibility

## FLOW-2301 — Review budget `[S]`

Veliki diff + širok scope + slab evidence:

```text
→ signal da je potreban manji checkpoint
```

Ne automatski rejection.

## FLOW-2302 — Comprehension checkpoint `[S]`

Za visok rizik, šablonska pitanja:

```text
Šta se ponašajno promijenilo?
Koji su ključni trade-offi prema Program Design artefaktu?
Šta nije dokazano?
Koji findings su ostali?
```

Bez LLM generisanja.

## FLOW-2303 — Deterministički Evidence Summary `[M]`

Primjer:

```text
Changed files: 7
Targeted tests: PASS
Regression suite: PASS
Review: PASS_WITH_NOTES
Open HIGH findings: 0
Open MEDIUM findings: 1
Acceptance criteria proven: 2/3
User decision: PENDING
```

## FLOW-2304 — Inspectable Relationship Graph Projection `[M]`

Opcioni GUI/read-model ako linearni Task Detail više nije dovoljan.

Prikaz može povezati:

```text
Task
PlanItem
dependency
Session
Worktree
Commit
Evidence
Review
Finding
Decision
```

Hard rule:

```text
graph = projection
graph ≠ executor
```

Nema:

```text
run node
retry edge
pause/resume
agent scheduling
model routing
```

Graph služi samo ljudskom razumijevanju i navigaciji evidence-a.

# 21. FAZA 24 — Scale samo po dokazanoj potrebi

Mogući sadržaj:

```text
PostgreSQL
multi-machine/team read-model
central artifact store
VS Code extension
shared project state
organization integrations
```

Ne uključivati:

```text
remote agent workers
agent scheduler
agent sandbox orchestrator
model provider router
LLM inference service
```

Gate:

```text
dokazan korisnički problem
postojeći workaround je stvarno preskup
jasan konzument
mjerljiv benefit
```

---

# 22. GUI north star

GUI se organizuje prema ljudskim pitanjima.

## Pregled

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

### GUI arhitektonsko pravilo

Prije dodavanja novog Task-centric ekrana prvo provjeriti može li koristiti primitive koje su nastale iz FLOW-1204 i dokazale reuse u FLOW-1302.

Ako ne može, dokumentovati zašto prije pravljenja novog paralelnog widget obrasca.

---

# 23. „Gdje si stao“

Project Resume nije source of truth.

To je Current State projekcija.

Za projekat:

```text
current goal
last relevant Task
latest evidence
Git/reconciliation
open blockers
next required workflow phase
```

Za Task:

```text
current implementation state
latest verification
latest review
latest decision
next required action
```

`next required action` dolazi iz state machine-a ili eksplicitnog workflow pravila.

Ne iz LLM zaključka.

---

# 24. Context pravila

## Stable context

```text
AGENTS.md
ADRs
architecture docs
project conventions
verification commands
external-system metadata bez secreta
```

## Current context

FlowOS projection.

## History

```text
Git
Ledger
Events
Reports
```

## Conversation

Privremeni kontekst eksternog alata.

FlowOS ne pokušava da conversation history pretvori u vlastiti LLM memory.

---

# 25. `docs/external/` i durable project knowledge

Vrijedna praksa:

```text
docs/adr/
docs/external/
```

`docs/external/` može opisati:

- env var nazive;
- deployment lokaciju;
- payment provider;
- test account oznake;
- support kanal;
- vanjske API contracte.

Nikada secret vrijednosti.

FlowOS može deterministički uključiti reference u Handoff projekciju.

---

# 26. Security contract — potvrđene invarijante i otvorene obaveze

Ova sekcija više ne naziva neimplementirane funkcije „non-regression“ zaštitama.

Postoje dvije kategorije:

```text
A. CONFIRMED / SHOULD NOT REGRESS
B. OPEN UNTIL SPECIFIC FLOW TASK IS ACCEPTED
```

## 26.1 Path safety — OPEN do FLOW-1110, zatim NON-REGRESSION

Nikad:

```text
string prefix = containment
```

Tačan path identity mora pokriti sva mjesta gdje managed/main/cleanup odluka zavisi od putanje.

## 26.2 Secret redaction — NON-REGRESSION

`FLOW-1109` se tretira kao završen security checkpoint.

Secret ne smije procuriti kroz persisted report/artifact/verification output.

## 26.3 FlowOS-owned subprocess environment — OPEN do FLOW-1114

Dok FLOW-1114 nije ACCEPTED, ne tvrditi da FlowOS koristi filtered env.

Nakon ACCEPTED:

- minimalni/allowlisted env;
- credential values se ne loguju;
- verify/test subprocess dobija samo ono što mu treba.

## 26.4 FlowOS-owned process-tree timeout — OPEN do FLOW-1114

Dok FLOW-1114 nije ACCEPTED, `subprocess timeout` nije dovoljan dokaz da je cijelo Windows child tree završeno.

Nakon ACCEPTED:

```text
timeout/cancel
→ cijeli FlowOS-owned process tree završava
```

Ovo se ne odnosi na agentske procese, jer ih FlowOS ne pokreće.

## 26.5 Watcher/Git — NON-REGRESSION gdje je već dokazano

- callback greške se ne gutaju;
- stop je idempotentan;
- untracked files se vide;
- Git parser je stabilan;
- watcher event nije workflow completion.

Svaka tvrdnja u dokumentaciji mora imati stvarni test/dokaz za konkretan invariant.

## 26.6 Historical replay — NON-REGRESSION

Dozvoljeno:

```text
git show
git ls-tree
git cat-file
```

Za test starog stanja:

```text
privremeni/detached worktree
ili izolovana scratch lokacija
```

Zabranjeno nad aktivnim implementation worktreejem:

```text
git checkout
git reset
git restore
```

radi historical replay-a.

Regression gate:

```text
dirty implementation worktree
+ historical replay
→ implementation diff ostaje byte-identičan
```

## 26.7 Documentation truthfulness — TRAJNI INVARIANT

Nije dozvoljeno napisati:

```text
Git čist
testovi prolaze
filtered env implementiran
process tree ugašen
feature verified
```

ako stvarni dokaz to ne potvrđuje.

# 27. Standardni acceptance gate za budući Task

Svaki netrivijalni Task treba imati najmanje:

```text
1. cilj
2. scope / out-of-scope
3. DoD / acceptance
4. Git baseline
5. exact changed-files pregled
6. targeted tests
7. relevant regression
8. scripts/verify.py gdje je primjenjivo
9. Implementer/AgentReport ako se koristi
10. independent review za HIGH/rizičan rad
11. human TASK_DECISION gdje workflow to zahtijeva
12. commit scope provjeru
13. remote SHA provjeru prije tvrdnje "pushed"
14. historical replay ne smije mutirati aktivni worktree
15. evidence za bounded contract deviation ako postoji
```

Agentov report nikada nije sam po sebi acceptance.

---

# 28. Commit / integration gate

Prije commita:

```text
git status
exact diff
unrelated files excluded
fresh tests
review stanje
open material findings = none
```

Poslije commita/pusha:

```text
verify SHA
verify remote target gdje je relevantno
clean/expected working tree
```

---

# 29. Sizing pravila i početna mapa

## Pravila

```text
S = jedan mali, dobro omeđen vertical change
M = nekoliko povezanih promjena, ali jedan jasan subsystem/use-case
L = veći ekran/read-model ili više slojeva koji moraju zajedno proraditi
XL = preveliko za direktnu implementaciju; obavezno razbijanje
```

Ovo nije procjena vremena.

## P0 sizing v4.4

| Task | Size | Napomena |
|---|---:|---|
| FLOW-1109 | DONE | security non-regression |
| FLOW-1110 | M | path identity na svim relevantnim call-siteovima |
| FLOW-1105 | S | Pydantic PlanImport contract |
| FLOW-1106 | S | real dogfood import |
| FLOW-1107 | S | početi velocity zapis |
| FLOW-1111 | S | dead launch/session cleanup |
| FLOW-1112 | M | six-class semantics + provenance + legacy attribution map |
| FLOW-1113 | S | existing read-model inventory |
| FLOW-1114 | M | filtered env + Windows process-tree timeout |
| FLOW-1115 | S | CLAUDE/AGENTS/README alignment |
| FLOW-1201 | S | project selection |
| FLOW-1202 | M | Tasks backend binding |
| FLOW-1203 | M | Current State preko postojećih servisa |
| FLOW-1204 | L | Task Detail + prvi realni GUI primitives |
| FLOW-1301 | M | unified history projection |
| FLOW-1302 | M | history GUI + reuse proof |
| FLOW-1303 | M | inspectable evidence navigation |
| FLOW-1304 | S | activity/history separation |
| FLOW-1305 | M | regression proof policy |
| FLOW-1401 | M | decision UX |
| FLOW-1402 | S | canonical reload |
| FLOW-1403 | M | real E2E dogfood |
| FLOW-1404 | M | historical binding proof |
| FLOW-1501 | S | UX notes |
| FLOW-1502 | M | navigation + fate of existing pages |
| FLOW-1503 | M | LIVE/MOCK/semantic presentation cleanup |
| FLOW-1504 | S | baseline freeze |
| FLOW-1505 | S | analyze accumulated velocity |

## P1 sizing kandidat

| Task | Size |
|---|---:|
| FLOW-1601 | M |
| FLOW-1602 | S |
| FLOW-1603 | M |
| FLOW-1604 | M |
| FLOW-1605 | S |
| FLOW-1606 | M |
| FLOW-1701 | M |
| FLOW-1702 | S |
| FLOW-1703 | S |
| FLOW-1704 | M |
| FLOW-1705 | L |
| FLOW-1706 | S |
| FLOW-1801 | M |
| FLOW-1802 | S |
| FLOW-1803 | M |
| FLOW-1804 | M |
| FLOW-1805 | M |
| FLOW-1806 | M |

Ako bilo koji `L` ispadne `XL`, obavezno ga razbiti prije implementationa.

Kalendarske procjene P1 nastaju tek iz podataka prikupljenih od FLOW-1107 do FLOW-1505.

# 30. Metrike koje imaju smisla

Prvo kvalitativni dogfooding.

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
stale/missing evidence count
conflicts caught before integration
```

Ne koristiti kao north star:

```text
lines of code
number of agents
number of sessions
token utilization
number of model calls
number of commits
```

---

# 31. Predloženi prioriteti

## P0 — završiti prvi human-controlled proof/evidence baseline

```text
1110
1105
1106
1107
1111
1112
1113
1114
1115
1201–1204
1301–1305
1401–1404
1501–1505
```

`1109` ostaje security non-regression checkpoint, ne aktivni implementation Task.

## P1 — nakon potvrđenog baseline-a i stvarnog velocity uzorka

```text
1600 Current State / Handoff
1700 Structured Findings
1800 Structured Task Contract / Program Design / Acceptance↔Evidence
```

## P2 — parallel coordination i deterministic quality

```text
1900 Passive observability/correlation
2000 Deterministic sensors/guards
2100 Cross-worktree conflict intelligence
2200 Readiness/bottleneck
```

Ovdje se vraća drugi vrijednosni stub: koordinacija paralelnog rada.

## P3 — samo po dokazu

```text
2300 Human comprehension + relationship graph projection
2400 PostgreSQL / team state / central artifacts / extensions
```

# 32. Šta se eksplicitno NE gradi

Ovo nije samo „ne sada“.

Ovo nije FlowOS core misija:

```text
interni LLM
LLM API pozivi radi zaključivanja
AI orchestration engine
agent launcher
agent process manager
agent scheduler
agent retry/correction loop
autonomous task decomposition
automatic model router
model recommendation engine
opinion/debate/fusion engine
multi-agent collaboration executor
automatic prompt dispatch
worker/checker orchestrator
durable agent job engine
remote agent workers
agent sandbox orchestration
AI priority score
AI completion percentage
LLM-generated Current State kao authority
LLM-generated evidence
auto merge/push
vlastiti general-purpose GitNexus replacement
```

---

# 33. Test matrica

## Passive Session Contract

- registracija Sessiona ne spawn-uje agent process;
- nema hidden child launch-a;
- nema lažnog `pid=os.getpid()` kao agent PID-a;
- session close nije completion;
- external session ID može nedostajati;
- passive scanner ne mijenja agentski process;
- `can_launch` capability ne reklamira nedozvoljenu core mogućnost.

## Evidence semantics & provenance

- claim nije mechanical evidence;
- mechanical evidence ima command/check + result + target context gdje je dostupno;
- derived fact navodi source fact reference;
- heuristic signal je vizuelno/semantički odvojen;
- human decision ostaje canonical authority;
- unknown ostaje unknown;
- semantic class se može izvesti bez per-table kolone gdje source type to dozvoljava;
- imported artifact čuva provenance i hash/reference.

## Legacy attribution compatibility

- WORKTREE/HIGH mapira u novu semantiku samo uz definisano pravilo;
- HINT/LOW ne postaje DIRECT;
- UNATTRIBUTED ostaje UNKNOWN;
- dvije attribution taxonomije ne izlaze istovremeno sirove korisniku.

## Existing read-model reuse

- FLOW-1203 koristi/proširuje odluku iz FLOW-1113;
- nema drugog paralelnog EvidenceService/ProjectStateService sa istom odgovornošću;
- timeline source je eksplicitno izabran.

## FlowOS-owned subprocess safety

- filtered env ne prosljeđuje test secret bez allowlist pravila;
- child→grandchild process tree ne preživi timeout;
- exit code/stdout/stderr ostaju tačni;
- agent process nije dio ovog lifecycle-a.

## Current State

- stariji report vs novija canonical odluka;
- missing evidence;
- stale evidence;
- unassigned report;
- multiple sessions;
- historical binding;
- stale Git snapshot;
- no history.

## Task Detail

- Task sa/bez PlanItem;
- implementation bez testova;
- test bez reviewa;
- accepted ali nije verified;
- evidence missing;
- claim + mechanical evidence prikazani različito;
- heuristic + unknown imaju posebna stanja;
- provenance se otvara.

## GUI primitive reuse

- primitive nastaje iz stvarnog 1204 use-casea;
- 1302 ponovo koristi bar jedan primitive;
- ako reuse nije prirodan, primitive se pojednostavljuje;
- novi ekran ne zahtijeva copy/paste cijelog detail layouta.

## Workflow History

- sva četiri canonical eventa se spajaju iz stvarnih writer/source mjesta;
- stabilan ordering;
- Workflow History i Technical Activity nisu ista lista.

## Regression proof

- bugfix: pre-change FAIL / post-change PASS kada je reproducibilan;
- feature: nema besmislenog zahtjeva za pre-change failure;
- historical replay ne dira active dirty worktree.

## Human Decision

- ACCEPTED ≠ VERIFIED;
- decision reloaduje backend-confirmed state;
- claim ne utiče na authority više nego dozvoljeno.

## Handoff

- fresh eksterni session;
- drugi alat/model;
- current decision supersedes old;
- missing reference;
- worktree changed;
- blocker postoji;
- FlowOS ne šalje handoff automatski;
- Handoff nije instruction/authority.

## Findings

- category dolazi iz kontrolisanog skupa;
- repeated-finding detection traži isti finding_code ili deterministic normalization;
- free-text similarity ne koristi LLM;
- FIXED ≠ VERIFIED.

## Acceptance Criterion ↔ Evidence

- current mechanical evidence → PROVEN;
- claim-only → UNPROVEN;
- relevantna promjena → STALE;
- manual criterion → MANUAL_CONFIRMATION_REQUIRED;
- jedan artifact može podržati više kriterija samo uz eksplicitnu vezu.

## Attribution

- explicit binding + isolated worktree → DIRECT;
- isolated worktree bez potpunog bindinga → ISOLATED;
- shared-tree temporal signal → HEURISTIC;
- insufficient evidence → UNKNOWN;
- origin ≠ actor ≠ attribution;
- HEURISTIC ne proizvodi hard block.

## Cross-worktree conflicts

- write overlap;
- stale base;
- dependency reference preko provider evidence-a;
- zero path overlap + dokaziva dependency referenca;
- unrelated modul ne daje false positive;
- HEURISTIC ownership ne podiže hard conflict severity.

## Dependency provider

- provider result ima provenance;
- AVAILABLE/UNAVAILABLE/STALE/ERROR stanja;
- unavailable provider ne ruši core;
- stale provider index je vidljiv;
- nema dupliranja general-purpose graph engine-a.

## Guards

- postojeći `guard_architecture.py` se registruje prije pravljenja novog;
- deterministic guard nalazi poznat prekršaj;
- false positive nije predstavljen kao dokazani failure;
- guard promjena ima provenance;
- repeated finding samo stvara candidate;
- FlowOS ne pokušava automatski fix.

## Relationship graph

- graph samo prikazuje postojeće veze;
- klik vodi do izvornog Task/Evidence/Finding/Decision zapisa;
- nema run/retry/pause/scheduling akcija.

# 34. Predloženi razvojni ritam

Za svaki Task:

```text
1. jedan Task
2. jedan odgovorni implementer
3. evidence
4. independent reviewer kada je opravdano
5. jedan finding/fix scope po korekciji
6. user decision
7. exact commit
8. remote verification
9. tek onda sljedeća akcija
```

Implementer može biti čovjek ili eksterni agentski alat koji čovjek koristi.

FlowOS ga ne bira i ne pokreće.

Za svaki `L` Task prije rada:

```text
provjeri da nije zapravo XL
provjeri GUI reuse
provjeri da ne uvodi novi source of truth
provjeri da ne uvodi skriveni LLM/agent orchestration
```

---

# 35. Kada ćemo znati da je FlowOS stvarno uspio

## Milestone 1 — Inspectable proof

> **Jedan stvarni development Task može od početne namjere do ljudske odluke biti razumljiv i dokaziv kroz LIVE FlowOS bez ručne rekonstrukcije iz chatova, terminala i report direktorijuma.**

## Milestone 2 — Durable engineering state

> **FlowOS deterministički generiše dovoljan Handoff da korisnik ručno otvori novu eksternu sesiju i nastavi rad bez prethodnog chata.**

To je FlowOS durability.

Ne resume LLM trace-a.

## Milestone 3 — Semantička disciplina

> **FlowOS jasno razlikuje SOURCE_FACT, DERIVED_FACT, MECHANICAL_EVIDENCE, HEURISTIC_SIGNAL, CLAIM i HUMAN_DECISION.**

## Milestone 4 — Acceptance proof

> **Za strukturisani Task može se vidjeti koji acceptance kriterij ima current proof, koji je stale, koji je unproven i koji zahtijeva manual confirmation.**

## Milestone 5 — Parallel coordination

> **FlowOS prije integracije hvata relevantan worktree/dependency konflikt bez izgradnje vlastitog general-purpose dependency engine-a.**

## Milestone 6 — Preventivni kvalitet

> **Ponovljeni materijalni finding može, uz ljudsku odluku, postati deterministički guard kandidat i kasnije stvarni guard.**

## Milestone 7 — Realističan razvojni kapacitet

> **Dogfooding daje stvaran velocity uzorak iz kojeg je moguće procijeniti veličinu narednih faza bez lažne preciznosti.**

Ni jedan milestone ne zahtijeva interni LLM niti pokretanje agenta iz FlowOS-a.

# 36. Konačna razvojna mapa

```text
SADA — CLEANUP + CONTRACTS + REAL DOGFOOD
│
├─ 1109  Secret redaction [DONE / non-regression]
├─ 1110  Safe worktree identity
├─ 1105  PlanImport Pydantic contract
├─ 1106  Real dogfood import
├─ 1107  Start velocity baseline
├─ 1111  Passive Session cleanup
├─ 1112  Evidence semantics + provenance + attribution map
├─ 1113  Existing read-model inventory
├─ 1114  FlowOS-owned subprocess safety
└─ 1115  Canonical docs alignment
        │
        ▼
TASK-CENTRIC PROOF SURFACE
│
├─ 1201  Project selection
├─ 1202  Tasks backend binding
├─ 1203  Task Current State via existing read-models
├─ 1204  Task Detail + first real GUI primitives
├─ 1300  Unified Workflow History + Inspectable Evidence
├─ 1400  Human Decision + real E2E
└─ 1500  UX baseline + velocity calibration
        │
        ▼
DURABLE ENGINEERING STATE + METHOD
│
├─ 1600  Current State / Attention / Handoff
├─ 1700  Structured Findings lifecycle
└─ 1800  Structured Task Contract / Program Design / Acceptance↔Evidence
        │
        ▼
PARALLEL COORDINATION + DETERMINISTIC QUALITY
│
├─ 1900  Passive Session / Git / Evidence correlation
├─ 2000  Existing + new deterministic guards
├─ 2100  Conflict intelligence + DependencyEvidenceProvider
└─ 2200  Project Readiness / bottleneck visibility
        │
        ▼
ONLY IF PROVEN
│
├─ 2300  Comprehension + inspectable relationship graph
└─ 2400  PostgreSQL / team state / artifacts / extensions
```

Namjerno ne postoji grana:

```text
Managed Execution
Model Routing
Durable Agent Jobs
Worker/Checker Automation
Agent Orchestration
LLM-in-FlowOS
Execution Graph
```

FlowOS ima **relationship graph**, ne execution graph.

# 37. Trajni filter za svaku novu ideju

## Q1 — Da li funkcija zahtijeva da FlowOS pokrene, promptuje, rasporedi, izabere, retry-a ili kontroliše LLM/agent?

Ako **DA**:

> **nije FlowOS core funkcija.**

## Q2 — Može li FlowOS funkciju pouzdano ostvariti iz Git-a, filesystema, SQL-a, parsera, uskog AST pravila, state machine-a, strukturisanog artefakta, eksternog determinističkog evidence provider-a ili testa?

Ako **DA**:

> **dobar je kandidat za FlowOS.**

## Q3 — Koja je semantička klasa rezultata?

```text
SOURCE_FACT?
DERIVED_FACT?
MECHANICAL_EVIDENCE?
HEURISTIC_SIGNAL?
CLAIM?
HUMAN_DECISION?
```

Ako se ne može jasno klasifikovati, funkcija nije spremna za canonical workflow.

## Q4 — Da li novi subsystem duplira specijalizovani alat ili postojeći FlowOS read-model?

Ako **DA**:

> prvo pokušati reuse/extension/read-only provider.

Novi paralelni servis je posljednja opcija.

## Q5 — Da li novi GUI ekran ponavlja postojeći Task-centric obrazac?

Ako **DA**:

> prvo provjeriti primitive koje su već dokazale reuse.

Ne praviti framework prije stvarnog use-casea.

## Q6 — Da li recorded podatak slučajno dobija više authority-ja nego što njegov source dozvoljava?

Provjeriti:

```text
artifact ≠ instruction
claim ≠ proof
proof ≠ acceptance
heuristic ≠ fact
session end ≠ task completion
commit ≠ human acceptance
```

## Q7 — Da li se „durability“ odnosi na engineering state ili pokušava vratiti agent runtime?

Ako funkcija pokušava:

```text
resume LLM trace
checkpoint agent thinking
retry external agent run
```

> nije FlowOS core.

## Q8 — Da li graph prikazuje veze ili ih izvršava?

Ako graph počinje:

```text
run
schedule
retry
pause
resume
route model
```

> to je orchestration i ne pripada FlowOS-u.

# 38. Konačna preporuka

v4.4 zadržava odluku iz v4.3 da FlowOS ne treba postati agent runtime.

Ali sada je granica preciznija.

Atomic i slični sistemi mogu biti:

```text
verifiable coding-agent runtime
```

FlowOS treba biti:

```text
verifiable human control plane
```

Zajednički princip je:

> **proof over claims**

Razlika je:

```text
runtime izvršava rad
FlowOS objašnjava, povezuje i dokazuje stanje rada
```

FlowOS vrijednost je da:

```text
zna koji Task postoji
zna koji plan i ljudska odluka važe
zna stvarni Git/worktree state
zna šta je source fact
zna šta je izvedena činjenica
zna koji mechanical evidence postoji
zna šta je samo heuristic signal
zna šta je claim
zna kada je evidence stale
povezuje evidence sa acceptance kriterijem
povezuje session/commit/task bez izmišljanja ownershipa
pokazuje cross-worktree konflikt
koristi GitNexus ili drugi provider bez pravljenja drugog GitNexusa
generiše portable Handoff
čuva durable engineering state
prikazuje relationship graph bez izvršavanja graph-a
omogućava čovjeku da odluči sa manjim mentalnim teretom
```

Osnovni princip ostaje:

> **AI radi. FlowOS pamti, povezuje i dokazuje. Čovjek odlučuje.**

v4.4 dodaje četiri praktične zaštite:

> **FlowOS radije priznaje UNKNOWN nego da izmisli atribuciju.**

> **FlowOS radije proširuje postojeći read-model nego da napravi paralelni source of truth.**

> **FlowOS radije koristi inspectable mechanical proof nego ubjedljiv claim.**

> **FlowOS čuva engineering state; ne pokušava posjedovati ili nastaviti agentski runtime.**
