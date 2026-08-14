# FlowOS kao human control plane za dugotrajni i multi-agent razvoj

**Datum:** 13. avgust 2026.  
**Status:** analiza i preciziranje koncepta — bez izmjene implementacionog plana  
**Svrha:** povezati stvarni FlowOS koji se već razvija sa problemima koje OpenAI, Anthropic i Arize javno opisuju kod dugotrajnih i paralelnih AI agenata, te precizno objasniti šta FlowOS već rješava, šta bi mogao rješavati svojim postojećim modelom i gdje su granice.

---

# 1. Izvršni sažetak

Najvažniji zaključak ove analize je:

> **FlowOS nije najzanimljiviji kao još jedan task manager niti kao još jedan “superagent”. Njegova najjača moguća uloga je lokalni human control plane za agent-potpomognuti razvoj: sistem koji održava autoritativno trenutno stanje rada, povezuje agente sa zadacima, Git promjenama, dokazima i ljudskim odlukama, i omogućava da čovjek ili fresh agent nastavi rad bez oslanjanja na prethodni chat.**

To direktno pogađa problem na koji su različitim putem naišli:

- **OpenAI Harness Engineering** — veliki `AGENTS.md` postaje groblje zastarjelih pravila; agentu treba kratka mapa i progresivno otkrivanje relevantnog znanja.
- **OpenAI Symphony** — čovjek može praktično pratiti samo nekoliko paralelnih agent sesija prije nego ljudska pažnja postane bottleneck; zato se stanje rada prebacuje na project board/control plane.
- **Anthropic long-running harness** — compaction nije dovoljna; fresh sesija treba strukturisan handoff, progress file, Git istoriju i test oracle.
- **Anthropic scientific computing** — dugotrajni rad zahtijeva prenosivu memoriju koja čuva trenutno stanje, neuspjele pristupe i mjerljiv napredak.
- **Arize Alyx** — plan ne smije biti samo davna poruka u razgovoru; mora biti strukturisano stanje izvan noisy historyja, stalno vidljivo agentu i djelimično sprovedeno kodom.

FlowOS je već projektovan oko gotovo istih primitiva, ali ih spaja na jednom mjestu:

```text
Project / PlanItem / TaskContract
        ↓
AgentSession
        ↓
GitSnapshot + FileActivity + Worktree
        ↓
Verify + artifacts
        ↓
AgentReport
        ↓
User verdict / workflow decision
        ↓
canonical workflow ledger
        ↓
novo trenutno stanje
```

To je važnije od same činjenice da FlowOS može prikazati “koji agent radi”.

---

# 2. Od čega ova analiza polazi

## 2.1. Stvarni FlowOS materijal

Analiza je zasnovana na postojećim FlowOS dokumentima i izvještajima, posebno:

- `FlowOS-kompletan-plan.md`
- `FlowOS-novi-detaljan-plan-PySide6-v2-plan-progress.md`
- `ANALIZA_FLOWOS_MOCKUP_OPUS_4_8.md`
- `2026-08-12-workflow-ledger-phase-3d-authority-cutover-analysis.md`
- `2026-08-12-workflow-ledger-phase-3d-authority-cutover-implementation.md`
- `AGENT_FRIENDLY_CODE.md`
- `APP_DEVELOPMENT_PROCESS.md`

Važno: ovdje se razlikuju tri nivoa tvrdnji:

1. **implementirano prema agent reportu** — postoji izvještaj o stvarnoj izmjeni i testovima;
2. **definisano u operativnom planu** — planirano i modelirano, ali ne znači da je već kompletno implementirano;
3. **moja izvedena interpretacija** — moguća uloga FlowOS-a izvedena iz postojećeg modela, bez tvrdnje da funkcionalnost već postoji.

---

# 3. Šta FlowOS originalno pokušava riješiti

Kompletan plan vrlo jasno definiše stvarni problem svakodnevnog rada:

```text
VS Code nad jednim projektom
├── Claude Code sesija
├── Codex sesija
├── pi agent / drugi CLI agent
├── ručne komande
├── testovi
└── korisničke izmjene
```

FlowOS treba bez obilaska terminala odgovoriti:

1. koji agent trenutno radi;
2. na kojem projektu i zadatku;
3. u kojem direktoriju, branchu ili worktreeju;
4. koje fajlove stvarno mijenja;
5. preklapa li se sa drugim agentom;
6. šta je promijenio i provjerio;
7. gdje je stao i šta korisnik treba odlučiti.

To je već mnogo bliže **control planeu** nego klasičnom task manageru.

FlowOS plan dodatno uvodi:

- detekciju aktivnosti umjesto ručne deklaracije;
- Git kao autoritet za promjene koda;
- worktree kao osnovu pouzdane atribucije;
- dokaz umjesto agentove tvrdnje;
- sigurnosna pravila u kodu, ne u promptu;
- managed execution;
- durable jobs;
- recovery;
- approval;
- evaluator/checker;
- mjerenje troška i prihvatanja.

---

# 4. Problem 1: previše paralelnih sesija prelazi kapacitet ljudske pažnje

OpenAI u objavi o Symphonyju navodi da su inženjeri praktično mogli komforno upravljati sa otprilike **3–5 paralelnih Codex sesija**. Iznad toga je rastao context-switching trošak: zaboravljalo se koja sesija radi šta, gdje je zastala i koju treba usmjeriti.

Symphony zato project-management board pretvara u control plane za agente.

## FlowOS odgovor

FlowOS od ranog plana ima:

- `AgentSession`;
- agent/model identitet;
- execution mode;
- task/project vezu;
- working directory;
- branch;
- worktree;
- PID;
- status;
- `last_activity`;
- početni i završni Git snapshot;
- timeline;
- file activity;
- konflikt signal;
- report.

Time se mentalni model mijenja iz:

```text
Ja moram zapamtiti šta radi pet terminala.
```

u:

```text
FlowOS prikazuje:
- ko radi;
- gdje radi;
- na čemu radi;
- šta je stvarno promijenjeno;
- šta je završeno;
- šta traži moju pažnju.
```

## Zašto je ovo važnije od “još jednog dashboarda”

Pravi bottleneck nije nedostatak još jednog prozora.

Bottleneck je:

```text
ljudska radna memorija
```

FlowOS može eksternalizovati tu memoriju u strukturisano, dokazivo stanje.

To je ista klasa problema koju Symphony rješava, ali FlowOS ima drugačiji fokus:

| Symphony | FlowOS |
|---|---|
| Codex-orijentisana orkestracija preko issue boarda | heterogeni lokalni agenti: Claude Code, Codex, pi, Generic CLI |
| svaki ticket dobija agenta | prvo prati stvarni postojeći workflow; kasnije može managed launch |
| cloud/team-orijentisan obrazac | single-user lokalni control plane |
| issue board je radna tabla | Git + sesije + plan + evidence + verdict čine model stanja |
| fokus na throughput | fokus i na atribuciju, konflikt, dokaz, recovery i ljudsku odluku |

---

# 5. Problem 2: transcript nije current state

Ovo je možda najvažnija ideja cijele teme.

Razgovor ili event history govori:

```text
šta se sve dogodilo
```

ali ne govori nužno:

```text
šta sada važi
```

Primjer:

```text
09:00  odluka: SQLite
11:00  pronađen problem
13:00  nova odluka: PostgreSQL
```

Sva tri događaja su legitimna istorija.

Ali fresh agent ne treba tretirati i SQLite i PostgreSQL kao jednako važeće instrukcije.

## FlowOS ima materijal za odvajanje ova dva nivoa

### Istorija

FlowOS model već ima:

```text
SessionEvent
GitSnapshot
FileActivity
AgentReport
WorkflowLedgerEvent
Git history
```

To je audit trail.

### Trenutno važeće stanje

Plan model razlikuje:

```text
IN_PROGRESS
IMPLEMENTED
VERIFIED
ACCEPTED
REJECTED
```

Task i PlanItem veze, user verdict i workflow decision stvaraju osnovu za **projekciju trenutnog stanja**.

To je ključna razlika:

> FlowOS ne mora koristiti chat istoriju kao trenutno stanje. Može iz canonical događaja izvesti read-model “šta sada važi”.

---

# 6. Problem 3: stara odluka nastavlja upravljati novim radom

U transkriptu o progressive context shapingu primjer je stara instrukcija koja je ranije bila korisna, ali je kasnije postala kontraproduktivna. Agent ju je nastavljao slijediti jer je i dalje bila dio aktivnog konteksta.

U običnom chatu rješenje je ručno prepisati `current.md`.

FlowOS može ovo riješiti strukturnije.

## Workflow authority je ovdje centralni koncept

FlowOS je već naišao na konkretan authority problem:

```text
report kaže NEEDS_WORK
ali PlanItem možda ostane IMPLEMENTED/VERIFIED
```

Analiza Phase 3D je to prepoznala kao split-brain.

Zatim implementation report od 12. avgusta 2026. navodi uvedeni:

```text
WorkflowDecisionService
```

i canonical:

```text
TASK_DECISION
```

u workflow ledgeru.

Prema tom implementation reportu:

- `ACCEPTED` upisuje korisničku odluku, ali ne lažira `VERIFIED`;
- `NEEDS_WORK` vraća dokazivo povezani `PlanItem` iz `IMPLEMENTED/VERIFIED` u `IN_PROGRESS`;
- `REJECTED` čuva drugačiju semantiku, ali trenutno ima isti deterministic consequence;
- report projection i workflow consequence rade u jednoj transakciji;
- ako consequence ne uspije, cijela odluka se rollbackuje;
- 14 novih integration testova je prijavljeno kao PASS;
- 102 relevantna regresiona testa su prijavljena kao PASS;
- report je završio statusom `READY FOR INDEPENDENT REVIEW`.

Ovo je izuzetno relevantno za progressive context shaping.

Jer “promijenili smo mišljenje” više ne mora biti samo nova rečenica u Markdownu.

Može postati:

```text
korisnička odluka
→ canonical event
→ deterministic consequence
→ novo stanje work targeta
→ budući read model vidi novu istinu
```

To je jače od prostog progress fajla.

---

# 7. Problem 4: fresh agent ne smije zavisiti od stare konverzacije

Anthropicov long-running harness je pokazao da compaction nije dovoljna.

Koriste:

- progress file;
- Git istoriju;
- feature list;
- initializer agent;
- incremental coding sessions;
- čist Git checkpoint;
- structured handoff;
- end-to-end test prije nastavka rada.

U scientific computing radu `CHANGELOG.md` služi kao prenosiva memorija i čuva:

- trenutno stanje;
- završene taskove;
- neuspjele pristupe;
- razlog neuspjeha;
- mjerne checkpoint-e;
- poznata ograničenja.

## FlowOS već modelira jači oblik handoffa

Durable plan predviđa:

```text
checkpoint = commit + handoff
```

Handoff sadrži:

- šta je urađeno;
- šta je ostalo;
- otvorene probleme;
- sljedeću očekivanu akciju;
- ključne fajlove.

Resume ne obećava nastavak “od posljednje misli”.

Umjesto toga:

```text
novi proces
← task contract
← handoff
← worktree na posljednjem sigurnom commitu
```

Ovo je vrlo zdrava odluka.

## Zašto je bolja od pokušaja čuvanja “mozga” agenta

FlowOS model pretpostavlja:

```text
session je potrošna
state mora biti trajan
```

To je upravo obrazac na koji su Anthropic i OpenAI došli.

Fresh agent ne treba privatni tok rezonovanja starog agenta.

Treba mu:

- rezultat;
- dokaz;
- posljednja važeća odluka;
- poznata ograničenja;
- posljednji siguran kod;
- sljedeći korak.

---

# 8. Problem 5: plan je zakopan u noisy historyju

Arize je kod Alyx agenta naišao na vrlo konkretan problem.

Jedan task je proizveo 27 LLM poziva, od kojih je većina bila reorganizovanje vlastite todo liste.

Rješenje nije bilo:

```text
“Molim te, drži se plana.”
```

Rješenje je bilo arhitektonsko:

```text
System
→ Current Plan
→ Session History
→ Current Turn
```

Plan:

- živi izvan historyja;
- ima strukturisana stanja;
- rekonstruiše se iz current state-a;
- stalno je na autoritativnoj poziciji;
- finish se može blokirati ako postoje nezavršene stavke.

## FlowOS paralela

FlowOS već ima strukturisani `PlanItem` i eksplicitnu razliku:

```text
IN_PROGRESS
IMPLEMENTED
VERIFIED
ACCEPTED
REJECTED
```

To ide korak dalje od običnog:

```text
pending / completed
```

Posebno je važno što:

```text
IMPLEMENTED ≠ VERIFIED ≠ ACCEPTED
```

To sprječava da modelova tvrdnja “uradio sam” postane automatski projekat “gotov”.

## Potencijalni FlowOS princip

FlowOS ne mora imati bukvalni `current.md`.

Može održavati **Current State Projection** iz svoje baze i ledger događaja.

Takva projekcija bi konceptualno mogla sadržavati:

```text
Current goal
Active PlanItem
Latest authoritative decisions
Current execution/session
Current worktree/branch
Verified evidence
Open blockers
Last safe checkpoint
Required human decision
Next allowed action
```

Ovo je **izvedena preporuka**, ne tvrdnja da je taj read-model već kompletno implementiran.

---

# 9. Problem 6: “agent završio” nije isto što i “dokazano”

OpenAI i Anthropic sve više naglašavaju feedback loop i verifier.

FlowOS je od početka eksplicitan:

> model ne potvrđuje sam svoj rezultat.

Plan već ima:

- `VERIFY_RESULT`;
- `TEST_REPORT`;
- `LINT_REPORT`;
- `BUILD_REPORT`;
- `SCREENSHOT`;
- `CHECKER_REPORT`;
- `VERIFY_REPORT`;
- `AgentReport.verification_summary`;
- independent review;
- user verdict.

## Najvažniji vertikalni tok

```text
PlanItem
→ Session
→ Verify
→ Report
→ Verdict
```

Ovo je važnije od pojedinačnih funkcionalnosti.

Jer povezuje:

```text
namjeru
→ izvršenje
→ dokaz
→ ljudsku odluku
→ novo workflow stanje
```

To je zatvorena petlja.

---

# 10. Problem 7: current state mora razlikovati tri različita pojma

FlowOS-ova razlika između:

```text
IMPLEMENTED
VERIFIED
ACCEPTED
```

je strateški veoma dobra.

## IMPLEMENTED

Agent ili session tvrdi da je implementacija napravljena i postoji diff/report.

To je tvrdnja o izvršenju.

## VERIFIED

Postoje acceptance kriterijumi i dokaz da su zadovoljeni.

To je tehnička tvrdnja zasnovana na evidenceu.

## ACCEPTED

Čovjek prihvata poslovni, UX ili rizični ishod.

To je authority odluka.

Ove tri stvari se u velikom broju agent sistema miješaju pod:

```text
DONE
```

A upravo to proizvodi lažni current state.

FlowOS-ov model ovdje može biti precizniji od običnog progress fajla.

---

# 11. Problem 8: više agenata ne stvara samo context problem nego i fizički konflikt

OpenAI Symphony najviše govori o koordinaciji zadataka.

FlowOS dodatno modelira:

- realne filesystem promjene;
- Git status;
- commitove;
- branch/worktree;
- overlap;
- conflict warning;
- confidence atribucije.

`FileActivity.attribution` eksplicitno razlikuje:

```text
WORKTREE
SOLE_ACTIVE
HINT
UNATTRIBUTED
USER
```

To je važna odluka.

FlowOS ne bi trebalo da glumi preciznost koju nema.

Primjer:

```text
Git commit author = korisnik
```

ne dokazuje:

```text
korisnik je napisao kod
```

Ako je Codex radio u shared treeju, atribucija je samo heuristika.

Worktree daje mnogo jači dokaz.

## To znači da FlowOS ima dvije vrste konflikta

### Kontekstualni konflikt

Stara odluka protiv nove odluke.

### Izvršni konflikt

Dva agenta mijenjaju isti ili povezan kod.

Ovo drugo `current.md` ili issue board sami po sebi ne rješavaju.

---

# 12. Problem 9: istorija mora ostati dostupna, ali ne smije imati isti autoritet kao trenutno stanje

Dobar agent sistem ne treba brisati istoriju.

Treba joj smanjiti **autoritet**.

FlowOS append-only elementi su prikladni za to:

```text
SessionEvent
WorkflowLedgerEvent
Git history
AgentReport
```

Dok current projection treba pokazati samo:

```text
šta je trenutno aktivno
```

## Model četiri sloja konteksta

Najkorisnija podjela iz transkripta može se skoro direktno mapirati na FlowOS:

### 1. Stable instructions

Gdje žive:

```text
AGENTS.md
kratak CLAUDE.md
canonical docs
safety enforcement
```

Svrha:

```text
kako radimo
šta je trajno pravilo
šta zahtijeva approval
```

### 2. Current state

Gdje bi logički trebalo da živi:

```text
FlowOS read model / workflow projection
```

Svrha:

```text
šta sada važi
šta je aktivno
šta slijedi
šta blokira
šta čovjek mora odlučiti
```

### 3. Map

Gdje već postoje elementi:

```text
TaskContract
PlanItem
CONTEXT_PACK
repo mapa
artifact references
GitNexus/reference pointers
```

Svrha:

```text
gdje agent nalazi dublji kontekst
```

### 4. History

Gdje već živi:

```text
Git
SessionEvent
WorkflowLedger
AgentReport
decision history
```

Svrha:

```text
kako smo došli ovdje
```

Ovo je vrlo čista mentalna arhitektura za FlowOS.

---

# 13. Problem 10: “novo od zadnjeg pregleda” je vjerovatno važnije od kompletnog dashboarda

Analiza FlowOS mockupa već je identificovala da glavni ekran treba imati tri prioritetne zone:

1. **Novo od zadnjeg pregleda**
2. **Zahtijeva pažnju**
3. **Svi aktivni tokovi**

To sada dobija još jače opravdanje.

Ako je ljudska pažnja bottleneck, FlowOS ne treba prvenstveno pokazivati:

```text
sve što zna
```

nego:

```text
šta se promijenilo od mog zadnjeg pregleda
i šta zahtijeva moju odluku
```

## To je human attention routing

Primjer:

```text
Od posljednjeg pregleda

• Codex završio Phase 3D implementaciju
• 14 novih integration testova PASS
• 102 regresiona testa PASS
• mypy i dalje pada zbog prethodno poznatog problema
• rezultat još čeka independent review
```

Ovo je mnogo korisnije od:

```text
Session #127 ACTIVE
Session #128 COMPLETED
Session #129 COMPLETED
```

---

# 14. Problem 11: dokaz mora biti klikabilan

FlowOS mockup analiza već je postavila ispravno pravilo:

> Ne vjeruj tvrdnji bez dokaza.

Ako GUI kaže:

```text
“Testovi prošli”
```

korisnik treba moći otvoriti:

```text
test report
```

Ako kaže:

```text
“Codex izmijenio 4 fajla”
```

treba moći otvoriti:

```text
diff / commit / attribution evidence
```

Ako kaže:

```text
“PlanItem VERIFIED”
```

treba moći otvoriti:

```text
acceptance criteria
+ evidence linkove
```

FlowOS time postaje:

```text
evidence navigation system
```

a ne samo status display.

---

# 15. Problem 12: dugotrajni posao mora preživjeti pad procesa

Običan progress fajl rješava semantički handoff.

FlowOS Durable plan pokušava riješiti i runtime problem:

```text
process crash
service restart
retry
unknown side effect
lost attempt
```

Planirani Durable Job Engine sadrži:

- `AgentStep`;
- `StepAttempt`;
- retry klasifikaciju;
- max attempts;
- max duration;
- opcioni token/cost budget;
- checkpoint;
- startup recovery;
- idempotency;
- side-effect barrier;
- pause/resume između koraka.

## To je bitna razlika

Anthropic progress file kaže:

```text
fresh agent zna šta je bilo
```

FlowOS Durable cilj kaže:

```text
sistem zna:
- koja izvršna faza je bila aktivna;
- koji attempt je izgubljen;
- da li je worktree na poznatom commitu;
- da li je retry siguran;
- da li mora BLOCKED zbog nejasnog side-effecta.
```

To je workflow durability, ne samo memorija.

---

# 16. Problem 13: ljudska odluka mora biti trajna workflow činjenica

Approval i user verdict ne treba tretirati kao UI dugme bez posljedica.

FlowOS to već modelira kao trajno stanje.

Primjer managed flowa:

```text
rizična akcija
→ WAITING_APPROVAL
→ ApprovalRequest
→ korisnik APPROVED / REJECTED
→ tek onda nastavak
```

Phase 3D workflow ledger ide još dalje:

```text
user decision
→ canonical event
→ projection
→ deterministic consequence
```

Ovo je vrlo važno za human control plane:

> Čovjek nije samo reviewer na kraju. Čovjek je authority source za odluke koje mijenjaju budući tok rada.

---

# 17. Problem 14: plan i stvarni rad moraju biti povezani

FlowOS v2 plan uvodi veze:

```text
Task ↔ PlanItem
AgentSession ↔ PlanItem
AgentReport ↔ PlanItem
```

i report treba da navede:

- završene kriterijume;
- nezavršene kriterijume;
- rad van plana.

To rješava važan problem:

```text
mnogo aktivnosti
≠
stvarni napredak plana
```

Bez toga agent može napraviti 20 commitova, a da ključni acceptance kriterijum ostane netaknut.

FlowOS može zato razlikovati:

```text
activity
progress
verification
acceptance
```

To su četiri različita pojma.

---

# 18. Problem 15: agent ne smije tiho promijeniti scope

`TaskContract` već modelira:

```text
goal
working_hypothesis
verify_hypothesis
scope
out_of_scope
acceptance_criteria
allowed_paths_hint
risks
risk_level
```

To je vrlo dobra osnova za context pack.

Fresh agent ne treba dobiti cijelu istoriju.

Treba dobiti mali paket:

```text
šta treba postići
šta ne smije dirati
šta trenutno važi
koji dokaz mora proizvesti
koje odluke su već donesene
gdje da pronađe dublje izvore
```

---

# 19. Kako bi FlowOS mogao proizvesti “current context” bez još jednog ručno održavanog fajla

Ovo je najvažnija izvedena preporuka ovog dokumenta.

Ne predlaže se novi `current.md` kao dodatni izvor istine.

FlowOS već ima dovoljno strukturisanih elemenata da **generiše current context projection**.

Konceptualni paket za fresh agenta:

```markdown
# Current Work State

## Goal
<iz TaskContracta>

## Active work item
<PlanItem>

## Scope
...

## Out of scope
...

## Latest authoritative decisions
<iz Workflow Ledgera>

## Current implementation state
...

## Verified evidence
...

## Known failed approaches
<iz handoffa/reporta/decision history, samo posljedica>

## Worktree / branch / base commit
...

## Last safe checkpoint
...

## Open blockers
...

## Required human decision
...

## Next allowed action
...

## References
- relevant doc
- relevant test
- relevant artifact
```

Ovo bi bilo:

```text
generated read model
```

a ne:

```text
novi ručni dokument koji može driftovati
```

FlowOS već ima `CONTEXT_PACK` kao planirani artifact type, pa se koncept uklapa u postojeći model.

---

# 20. Zašto FlowOS ne treba kopirati `current.md`, `contextmap.md`, `decisions.md`

Takvi fajlovi su odlični za jednostavan agent harness.

Ali FlowOS već ima strukturne ekvivalente.

| Starter-kit fajl | FlowOS ekvivalent |
|---|---|
| `current.md` | current-state projection iz plana, ledger odluka, sesija, checkpointa i evidencea |
| `decisions.md` | `Decision` + `WorkflowLedgerEvent(TASK_DECISION)` + eventualni ADR |
| `contextmap.md` | TaskContract + repo mapa + artifact/reference pointers + `CONTEXT_PACK` |
| progress file | checkpoint HANDOFF + AgentReport + SessionEvents + Git |
| history | WorkflowLedger + Git + append-only events |

Dodavanje paralelnih ručnih fajlova bi moglo ponovo stvoriti:

```text
dva izvora istine
→ drift
```

To je upravo problem koji FlowOS pokušava izbjeći.

---

# 21. FlowOS naspram OpenAI Harness Engineeringa

OpenAI-jev obrazac:

```text
kratak AGENTS.md
→ docs kao system of record
→ active execution plans
→ progress/decision logs
→ stale-doc gardening
```

FlowOS nije zamjena za to.

Naprotiv, najbolja kombinacija je:

```text
repo znanje ostaje u repou
FlowOS održava stanje rada nad repoom
```

## Granica odgovornosti

### Repo je autoritet za:

- arhitekturu;
- canonical docs;
- izvorni kod;
- testove;
- Git istoriju;
- decision records.

### FlowOS je autoritet za:

- koja sesija radi;
- na kojem work targetu;
- aktivni workflow status;
- posljednju workflow odluku;
- link evidencea;
- konflikt/attribution stanje;
- checkpoint/resume;
- šta zahtijeva ljudsku pažnju.

Ta podjela je zdrava.

---

# 22. FlowOS naspram Symphonyja

Symphony:

```text
issue tracker
→ agent picks ticket
→ agent works continuously
→ human reviews result
```

FlowOS trenutni pravac:

```text
postojeći agent workflow
→ wrapper registruje stvarni rad
→ watcher/Git detektuju realnost
→ FlowOS povezuje task, session, evidence, report i decision
```

Kasniji `MANAGED` i `DURABLE` modovi mogu preći i u orkestraciju.

## Potencijalna prednost FlowOS-a

FlowOS ne zahtijeva od prvog dana da svi agenti budu pokrenuti kroz isti orkestrator.

Postoji:

```text
WRAPPED_TERMINAL
EXTERNAL_TRACKED
MANAGED
DURABLE
```

To znači postepen put:

```text
observe
→ coordinate
→ manage
→ durable automate
```

Ovo je vrlo razumno za solo developera.

---

# 23. FlowOS naspram Anthropic progress/handoff obrasca

Anthropic:

```text
progress file + git
→ fresh session
```

FlowOS:

```text
Git
+ SessionEvent
+ AgentReport
+ HANDOFF
+ PlanItem
+ TaskContract
+ workflow decisions
+ checkpoint
→ fresh process / fresh agent
```

FlowOS je složeniji, ali i rješava više:

- attribution;
- conflict;
- formalni status;
- approval;
- durability;
- evidence;
- decision authority.

## Rizik

Ako svi ti slojevi postanu ručno održavani, FlowOS bi bio gori od progress fajla.

Zato je jedan od originalnih najboljih FlowOS principa:

> **registracija i stanje moraju biti nusprodukt stvarnog rada, ne dodatni administrativni posao.**

---

# 24. FlowOS naspram Arize PlanMessage obrasca

Arize ključne ideje:

- plan je structured state;
- plan je izvan historyja;
- plan ima `pending / in_progress / completed / blocked`;
- agentu se stalno daje current plan;
- finish gate je strukturna provjera.

FlowOS je semantički bogatiji:

```text
PlanItem
TaskContract
Session
IMPLEMENTED
VERIFIED
ACCEPTED
BLOCKED
workflow decisions
```

## Šta je lekcija za FlowOS

Status ne treba slati agentu kao cijelu bazu.

Fresh agentu treba kompaktan read model:

```text
šta je current
```

History treba ostati dostupna na zahtjev.

---

# 25. Najjača moguća definicija proizvoda

Ranije definicije FlowOS-a poput:

```text
lični task manager
```

ili:

```text
pregled AI sesija
```

ne obuhvataju ono što je arhitektura postala.

Preciznija definicija:

> **FlowOS je lokalni human control plane za agent-potpomognuti razvoj softvera. Održava provjerljivo trenutno stanje rada između čovjeka, agenata, Git-a, plana i dokaza; upravlja handoffom i odlukama; i omogućava nastavak rada bez oslanjanja na prethodnu konverzaciju.**

Kraća verzija:

> **FlowOS održava istinu o tome šta se trenutno dešava u razvoju, šta je dokazano, šta je čovjek odlučio i šta agent smije uraditi sljedeće.**

---

# 26. Šta FlowOS potencijalno rješava bolje od pojedinačnih metoda iz transkripta

## 26.1. Ne samo memory nego authority

Progress file pamti.

FlowOS može razlikovati:

```text
history
od
canonical current decision
```

## 26.2. Ne samo plan nego evidence

Todo lista kaže da je task završen.

FlowOS može zahtijevati:

```text
implementation
→ verification evidence
→ human acceptance
```

## 26.3. Ne samo agent orchestration nego worktree reality

Issue board može reći:

```text
agent A radi ticket X
```

FlowOS može dodatno pokazati:

```text
branch
worktree
real files changed
commits
overlap
confidence atribucije
```

## 26.4. Ne samo handoff nego crash recovery

FlowOS Durable cilj uključuje pokušaje, lost process, retry klasifikaciju, safe checkpoint i side-effect barrier.

## 26.5. Ne samo “human in the loop” nego human authority

User verdict može postati canonical workflow event sa deterministic consequenceom.

---

# 27. Šta FlowOS još NE rješava automatski

Važno je ne precijeniti proizvod.

## 27.1. Ne može deterministički razumjeti svaku kontradikciju u prozi

Lako je utvrditi:

- commit se desio;
- fajl je promijenjen;
- status se razlikuje;
- working tree je dirty.

Nije lako deterministički dokazati:

```text
“dokument kaže X, ali semantika koda sada znači Y”
```

Za to treba:

- strukturisana tvrdnja;
- model;
- ili ljudski review.

## 27.2. Ne može automatski znati poslovnu ispravnost

Test može biti zelen, a odluka pogrešna.

## 27.3. Ne može garantirati atribuciju u shared treeju

Worktree je jedini visokopouzdan dokaz ownershipa promjena.

## 27.4. Ne može pretvoriti svaki agent report u istinu

Report je claim/evidence container, ne autoritet sam po sebi.

## 27.5. Ne može ukloniti human attention bottleneck

Može ga **usmjeriti**.

To je realniji cilj.

---

# 28. Najveći rizik FlowOS-a

Najveća opasnost nije da tehnologija neće raditi.

Najveća opasnost je da FlowOS postane novi sloj birokratije:

```text
agent radi
+
čovjek radi
+
još mora ručno održavati FlowOS
```

Ako se to desi, proizvod gubi smisao.

Zato mora ostati princip:

```text
detect first
derive state automatically
ask user only for real decisions
```

Ne tražiti od korisnika da ručno održava:

- ko radi;
- koji fajl;
- koji commit;
- kada je sesija završila;
- koji test je pokrenut;

ako se to može detektovati.

Korisnik treba unositi ono što sistem ne može zaključiti:

- poslovnu odluku;
- prihvatanje;
- promjenu cilja;
- rizični approval;
- objašnjenje zašto stara odluka više ne važi.

---

# 29. Drugi veliki rizik: previše paralelnih izvora istine

Potencijalni izvori:

```text
Task status
PlanItem status
AgentReport status
AgentJob status
Session status
WorkflowLedger
Git
Markdown tracker
```

Svaki od njih mora imati preciznu semantiku.

Najgori slučaj:

```text
Task = DONE
PlanItem = VERIFIED
Report = NEEDS_WORK
Job = COMPLETED
Git = dirty
```

bez jasnog pravila šta korisnik treba vjerovati.

Phase 3D authority cutover je upravo važan zato što pokušava razdvojiti:

```text
canonical decision history
od
compatibility projection
```

To treba ostati opšti princip.

---

# 30. Ključni koncept: Current State Projection

Ovo je možda najkorisniji naziv za ono što FlowOS treba predstavljati čovjeku i fresh agentu.

Ne novi canonical datastore.

Nego:

```text
projekcija iz postojećih autoritativnih izvora
```

Primjer logike:

```text
TaskContract.goal
+
active PlanItem
+
latest canonical workflow decision
+
current Session/Job
+
Git/worktree stanje
+
last CHECKPOINT/HANDOFF
+
latest verifier evidence
+
open approval/blocker
=
Current State Projection
```

Ta projekcija može hraniti:

- GUI “Gdje si stao”;
- “Od posljednjeg pregleda”;
- “Zahtijeva pažnju”;
- `CONTEXT_PACK` za fresh agenta;
- Resume;
- Next Action;
- checker brief.

Ovo povezuje skoro sve FlowOS komponente u jednu korisničku vrijednost.

---

# 31. Ključni koncept: Attention Projection

Uz Current State postoji i drugi važan read-model:

```text
šta čovjek mora pogledati sada
```

Primjeri:

- agent završio, verifier nije pokrenut;
- `NEEDS_WORK` decision;
- konflikt u shared treeju;
- unknown/unattributed promjena;
- dirty worktree nakon crashed sessiona;
- approval čeka;
- test fail;
- state mismatch;
- agent report bez dokazivog targeta;
- implementation complete ali nema acceptance evidencea.

To je prirodna osnova za:

```text
Zahtijeva pažnju
```

---

# 32. Ključni koncept: “Od posljednjeg pregleda”

Ovo je delta, ne snapshot.

FlowOS zna događaje i timestampove, pa može konceptualno izvesti:

```text
šta je novo od posljednjeg user review checkpointa
```

To rješava realan problem solo developera:

> “Nisam otvarao projekat dva dana — reci mi šta se zaista promijenilo, ne pokazuj mi cijeli projekat.”

Ovo je mnogo bliže ljudskoj potrebi nego običan activity feed.

---

# 33. Šta ovaj pogled mijenja u razumijevanju GUI-ja

Glavni ekran ne bi trebalo da bude organizovan prvenstveno prema entitetima baze:

```text
Projects
Tasks
Sessions
Reports
Artifacts
```

To je tehnički model.

Čovjek razmišlja:

```text
1. Šta se promijenilo?
2. Šta traži moju pažnju?
3. Šta trenutno radi?
4. Gdje sam stao?
5. Koji je dokaz?
6. Šta trebam odlučiti?
```

Zato je raniji mockup pravac:

- Novo od zadnjeg pregleda;
- Zahtijeva pažnju;
- Aktivni tokovi;
- Brzi dokazi;

vrlo dobro usklađen sa ulogom human control planea.

---

# 34. Kako FlowOS može pomoći progressive context shapingu bez “AI magije”

Progressive context shaping ne mora biti LLM feature.

Može biti obična workflow mehanika.

Primjer:

```text
1. TaskContract kaže cilj A.
2. Agent istražuje.
3. Evidence pokaže da je pretpostavka pogrešna.
4. Čovjek donese TASK_DECISION.
5. Ledger čuva odluku.
6. PlanItem/status se promijeni.
7. Current State Projection više ne prikazuje staru pretpostavku kao aktivnu.
8. Fresh agent dobije novi CONTEXT_PACK.
9. Stara odluka ostaje u historyju.
```

To je progressive context shaping kao **sistemsko svojstvo**, ne prompt trik.

---

# 35. Veza sa nalazom “humans plan, agents execute”

Anthropicova analiza oko 400.000 Claude Code sesija navodi da ljudi donose većinu planning odluka, a Claude većinu execution odluka. Takođe, veća domenska ekspertiza korisnika poboljšava uspjeh i omogućava modelu više rada po instrukciji.

To se savršeno uklapa u FlowOS podjelu:

## Čovjek

- cilj;
- prioritet;
- scope;
- acceptance;
- interpretacija novog evidencea;
- risk approval;
- finalna odluka.

## Agent

- istraživanje;
- implementacija;
- testiranje;
- generisanje artefakata;
- izvršenje jasno definisanih koraka.

## FlowOS

- čuva vezu između ta dva sloja;
- osigurava da agent radi prema **najnovijoj** odluci;
- prikazuje čovjeku gdje je potreban judgment.

To je vjerovatno najbolji način da se opiše njegova uloga.

---

# 36. Šta ne treba raditi

Ova analiza ne znači da FlowOS sada treba dobiti još deset novih modula.

Posebno ne treba automatski dodavati:

```text
current.md
contextmap.md
decisions.md
progress.md
memory.md
```

ako postojeći model već ima iste informacije.

Takođe ne treba:

- odmah praviti full Symphony klon;
- uvoditi event bus samo zato što zvuči agentic;
- praviti autonomne merge botove;
- automatski zaključivati semantičke kontradikcije;
- praviti “AI summary” kao novi source of truth;
- gurati cijelu istoriju u context pack;
- dozvoliti reportu da bude authority;
- miješati `COMPLETED`, `VERIFIED` i `ACCEPTED`.

---

# 37. Šta je već posebno dobro u FlowOS pravcu

## 37.1. Detekcija > deklaracija

Veoma važan princip za stvarnu upotrebu.

## 37.2. Git je autoritet za kod

FlowOS nije novi Git.

## 37.3. Worktree kao pravi ownership signal

Ne glumi preciznost shared-tree atribucije.

## 37.4. Model ne potvrđuje sam sebe

Verifier proizvodi dokaz.

## 37.5. Prompt nije safety boundary

Dozvole su tehnički sprovedene.

## 37.6. Kompleksnost mora dokazati vrijednost

Verifier se čak planira gasiti ako ne donosi mjerljivu korist.

## 37.7. Durable checkpoint je commit + handoff

Praktičan i auditabilan.

## 37.8. User decision se pretvara u workflow authority

Phase 3D je posebno značajan korak u tom pravcu.

---

# 38. Precizniji proizvodni “north star”

FlowOS ne treba optimizovati za:

```text
što više agenata
```

nego za:

```text
što više pouzdanog rada po jedinici ljudske pažnje
```

Moguća north-star metrika:

```text
accepted verified work
/
human review + coordination time
```

Uz prateće metrike:

- vrijeme da korisnik shvati current state;
- vrijeme da utvrdi ko radi šta;
- broj konflikata uhvaćenih prije integracije;
- procenat `IMPLEMENTED` stavki koje prelaze u `VERIFIED`;
- procenat `VERIFIED` stavki koje korisnik prihvata bez reworka;
- broj resume slučajeva bez gubitka rada;
- broj state mismatch/split-brain incidenta;
- review vrijeme po agent sesiji;
- cost per accepted change.

---

# 39. Predloženi test da li FlowOS zaista rješava problem

Ne mjeriti samo da li GUI radi.

Napraviti realan eksperiment:

## Bez FlowOS-a

Pokrenuti:

- Claude Code;
- Codex;
- pi;

na tri izolovana zadatka kroz nekoliko sati.

Nakon pauze od nekoliko sati ili narednog jutra izmjeriti:

- koliko treba da se shvati ko je šta radio;
- gdje je svako stao;
- koji rezultati su dokazani;
- koji posao treba vratiti;
- gdje postoji konflikt;
- šta treba uraditi sljedeće.

## Sa FlowOS-om

Isti tip rada.

Mjeriti:

```text
time-to-resume
time-to-review
conflict discovery time
state accuracy
evidence retrieval time
human context switches
```

Ako FlowOS ovo značajno smanji, njegova osnovna vrijednost je dokazana.

---

# 40. Granica između FlowOS-a i agent frameworka

FlowOS ne mora znati kako svaki agent “misli”.

Treba znati:

```text
task contract
session
observable effects
artifacts
evidence
decision
state transition
```

To ga čini manje zavisnim od:

- Claude Code internog prompta;
- Codex harnessa;
- pi implementacije;
- jednog modela;
- jednog vendor API-ja.

To je jaka arhitektonska prednost.

---

# 41. Jedna rečenica koja povezuje cijeli sistem

Najpreciznija formulacija koju bih sada koristio:

> **FlowOS pretvara prolazne agent sesije u trajno, provjerljivo stanje razvoja kojim čovjek upravlja.**

Prolazno:

```text
chat
terminal
agent process
```

Trajno:

```text
goal
task contract
plan state
decision
Git
evidence
handoff
verdict
history
```

---

# 42. Konačna procjena

Posljednji transkript nije pokazao da FlowOS treba kopirati još jedan framework.

Pokazao je da FlowOS već pokušava riješiti problem koji se pojavljuje čim agentski razvoj pređe sa:

```text
jedan agent
jedan prompt
jedan task
```

na:

```text
više agenata
više sesija
više sati/dana
promjenjive odluke
ograničena ljudska pažnja
```

OpenAI rješava dijelove kroz:

- kratki `AGENTS.md`;
- repo knowledge;
- execution plans;
- Symphony.

Anthropic kroz:

- progress file;
- Git handoff;
- test oracle;
- fresh sessions;
- structured long-running harness.

Arize kroz:

- plan van transcript historyja;
- structured task state;
- fixed-position current plan;
- hard completion gates.

FlowOS ima mogućnost da ove obrasce objedini kao lokalni sistem:

```text
STABLE RULES
       ↓
TASK CONTRACT / PLAN
       ↓
CURRENT STATE PROJECTION
       ↓
AGENT EXECUTION
       ↓
OBSERVED GIT/FILESYSTEM REALITY
       ↓
VERIFICATION EVIDENCE
       ↓
HUMAN DECISION
       ↓
WORKFLOW LEDGER
       ↓
NOVO CURRENT STATE
```

To je mnogo jača i preciznija svrha od “pregleda agentskih sesija”.

---

# 43. Zaključna definicija

> **FlowOS je lokalni human control plane za agent-potpomognuti razvoj softvera. Njegova svrha nije da zamijeni agente, Git ili projektnu dokumentaciju, nego da održava provjerljivu vezu između ljudske namjere, aktivnog agentskog rada, stvarnih promjena u repozitoriju, dokaza i odluka. Time fresh agent ili čovjek može pouzdano nastaviti rad iz trenutnog stanja, bez oslanjanja na staru konverzaciju ili ljudsku memoriju.**

Najkraće:

```text
FlowOS ne treba da pamti sve.

Treba da zna:
šta sada važi,
zašto tome vjerujemo,
ko trenutno radi,
šta je sljedeće,
i gdje čovjek mora odlučiti.
```

---

# 44. Izvori

## FlowOS interna dokumentacija

- `FlowOS-kompletan-plan.md`
- `FlowOS-novi-detaljan-plan-PySide6-v2-plan-progress.md`
- `ANALIZA_FLOWOS_MOCKUP_OPUS_4_8.md`
- `2026-08-12-workflow-ledger-phase-3d-authority-cutover-analysis.md`
- `2026-08-12-workflow-ledger-phase-3d-authority-cutover-implementation.md`
- `AGENT_FRIENDLY_CODE.md`
- `APP_DEVELOPMENT_PROCESS.md`

## OpenAI

- Harness engineering: leveraging Codex in an agent-first world  
  https://openai.com/index/harness-engineering/

- An open-source spec for Codex orchestration: Symphony  
  https://openai.com/index/open-source-codex-orchestration-symphony/

## Anthropic

- Effective harnesses for long-running agents  
  https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

- Long-running Claude for scientific computing  
  https://www.anthropic.com/research/long-running-Claude

- Agentic coding and persistent returns to expertise  
  https://www.anthropic.com/research/claude-code-expertise

- Harness design for long-running application development  
  https://www.anthropic.com/engineering/harness-design-long-running-apps

## Arize

- How to Build Planning Into Your Agent  
  https://arize.com/blog/how-to-build-planning-into-your-agent/

- AI Agent Debugging: Four Lessons From Shipping Alyx  
  https://arize.com/blog/ai-agent-debugging-four-lessons-from-shipping-alyx-to-production/

- Context management in agent harnesses  
  https://arize.com/blog/context-management-in-agent-harnesses/

---

# 45. Napomena o pouzdanosti

Neke brojke iz javnih objava, kao što su OpenAI-jevih 500% više landed PR-ova na pojedinim timovima, predstavljaju interne observacije kompanija, ne kontrolisane eksperimente. U ovom dokumentu koriste se kao dokaz da je **human attention/context switching stvarni operativni problem**, ne kao dokaz univerzalnog procentualnog povećanja produktivnosti.

Isto tako, FlowOS implementation report od 12. avgusta navodi uspješnu Phase 3D implementaciju i testove, ali sam report završava sa `READY FOR INDEPENDENT REVIEW`; zato se u ovom dokumentu tretira kao jak projektni dokaz implementacije, ali ne kao nezavisno potvrđena završna verifikacija.
