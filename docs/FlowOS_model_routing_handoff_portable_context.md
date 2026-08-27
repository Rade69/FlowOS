# FlowOS — model routing, handoff i portable context

**Status:** strateška bilješka za arhivu; nije implementaciona specifikacija  
**Izvor:** Nate B. Jones transkript o korištenju jeftinijih modela unutar Claude Code/Codex harnessa  
**Zašto vrijedi arhivirati:** transkript donosi nekoliko novih i direktno primjenjivih ideja za FlowOS: jasnu razliku model/harness/project-context/conversation, minimalni handoff format, task-routing po boundednessu i verifikabilnosti, te ideju “fully loaded cost” umjesto cijene tokena.

---

## 1. Najvažniji novi model

Transkript razdvaja četiri stvari koje se često miješaju:

```text
MODEL
= reasoning / code capability

HARNESS
= kako model čita fajlove, koristi alate, pokreće komande i traži dozvole

PROJECT CONTEXT
= durable pravila, dokumentacija, testovi, skills, scripts, hooks

CONVERSATION
= privremena istorija konkretne sesije
```

Za FlowOS je korisno dodati još jedan, iznad conversation sloja:

```text
FLOWOS CANONICAL STATE
= autoritativno trenutno stanje rada, odluka i verifikacije
```

Tako dobijamo:

```text
MODEL
        ↓
HARNESS / EXECUTION ENVIRONMENT
        ↓
DURABLE PROJECT CONTEXT
        ↓
FLOWOS CANONICAL CURRENT STATE
        ↓
SESSION / CONVERSATION
```

Ključna posljedica: **model se može promijeniti, a projekat ne smije izgubiti svoj smisao, odluke ni radno stanje.**

---

## 2. Handoff treba biti mali i eksplicitan

Autor predlaže vrlo mali handoff:

```text
goal
current state
relevant files
constraints
what done means
checks to run
```

Ovo je izuzetno relevantno za FlowOS.

Ne treba kopirati kao ručni fajl koji postaje novi source of truth.

Bolji FlowOS obrazac:

```text
canonical state
      ↓
deterministički handoff projection
      ↓
Markdown / JSON / clipboard paket
      ↓
fresh Claude / Codex / GLM / drugi agent
```

Minimalni handoff paket mogao bi izgledati ovako:

```text
Goal
Current state
Relevant files
Constraints
Definition of done
Verification commands
```

To je dovoljno malo da novi agent može brzo početi, a dovoljno konkretno da ne mora dobiti cijeli prethodni chat.

---

## 3. Task boundary je pravo mjesto za promjenu modela

Jedan od najjačih praktičnih zaključaka transkripta:

> Ne mijenjati model usred nejasnog, dugog razgovora ako se to može izbjeći.

Praktično:

```text
duga sesija + mnogo implicitnog konteksta
→ skupa i rizična migracija na drugi model
```

Bolje:

```text
jasno zatvoren work item
        ↓
handoff
        ↓
nova sesija / novi model
```

Za FlowOS ovo sugeriše vrlo čistu granicu:

```text
PlanItem / Task boundary
= prirodni model-switch boundary
```

Ne znači da se model nikada ne može promijeniti usred rada, ali to treba tretirati kao izuzetak koji zahtijeva eksplicitan handoff.

---

## 4. Jeftiniji model ne treba birati po cijeni nego po obliku zadatka

Autorov najkorisniji kriterijum nije “GLM je jeftiniji”, nego:

```text
jasan cilj
+ jasan scope
+ jasne dozvole
+ jasan Definition of Done
+ jaki testovi / objective checks
= dobar kandidat za slabiji / jeftiniji worker
```

Nasuprot tome:

```text
hidden state
+ konfliktni dokazi
+ root-cause investigation
+ arhitektonska neizvjesnost
+ rizičan trade-off
= zadržati jači model i više ljudskog nadzora
```

To je mnogo važnije od konkretnog modela.

FlowOS ne treba automatski odlučivati koji model “mora” raditi zadatak. Ali može pokazati da li je zadatak dovoljno **bounded i verifiable** da je pogodan za delegaciju jeftinijem workeru.

---

## 5. Task suitability, ne AI authority

Potencijalno koristan read-model za kasnije:

```text
Task Suitability

target_clarity
scope_clarity
permission_clarity
definition_of_done_clarity
verification_strength
hidden_state_risk
business_risk
```

Iz toga FlowOS eventualno može prikazati:

```text
SUITABLE FOR CHEAP WORKER
REQUIRES STRONGER MODEL
REQUIRES HUMAN DECISION
```

Ali ovo ne treba biti novi autonoman AI router u MVP-u.

Prva verzija može biti:

```text
FlowOS prikazuje činjenice
čovjek bira model
```

Tek ako se kasnije dokaže dovoljno pouzdan obrazac, routing može postati djelimično automatizovan.

---

## 6. “Fully loaded cost” je bolji koncept od cijene tokena

Transkript veoma dobro upozorava da:

```text
jeftiniji token
≠
jeftiniji završen zadatak
```

Pravi trošak je približno:

```text
model cost
+ context transfer
+ retries
+ failed attempts
+ review time
+ verifier cost
+ rework
```

Za FlowOS je ovo vrlo vrijedna buduća metrika:

```text
COST PER VERIFIED / ACCEPTED TASK
```

a ne:

```text
tokens per task
```

Primjer:

```text
Model A:
$1.20 execution
+ 3 retries
+ 25 min review

Model B:
$4.80 execution
+ 0 retries
+ 5 min review
```

Model B može biti stvarno jeftiniji.

Ne treba sada uvoditi telemetry infrastrukturu samo zbog ove ideje. Prvo se može bilježiti minimalan outcome tamo gdje već postoji podatak.

---

## 7. Conversation nije durable memory

Ovo je direktna potvrda progressive-context ideje.

Ako ključna odluka postoji samo u chatu:

```text
session ends
→ decision effectively disappears for fresh agent
```

Ako postoji u canonical stanju:

```text
fresh agent
→ može je ponovo dobiti
```

Pravilo:

```text
Ako fresh agent mora znati činjenicu da bi nastavio ispravno,
ona ne smije postojati samo u conversation historyju.
```

Ali to ne znači da treba zapisivati svaku poruku.

Treba sačuvati samo:

```text
consequential decisions
constraints
validated findings
failed approaches worth avoiding
current state
definition of done
```

---

## 8. Worktree i multi-session obrazac

Autor preporučuje:

```text
lead model/session
+
worker model/session
+
jasan handoff
+
worktree ako oba uređuju kod
```

To se veoma dobro poklapa sa FlowOS pravcem.

FlowOS vrijednost tu nije da “izmisli swarm”, nego da drži vidljivim:

```text
koji session radi šta
na kojem worktreeu
sa kojim modelom/harnessom
koji handoff je dobio
koje fajlove je promijenio
šta je verificirano
```

To je kontrolni sloj, ne autonomni komandni centar.

---

## 9. Worker/checker razdvajanje dobija dodatnu ekonomsku dimenziju

Postojeći princip:

```text
worker generiše
checker dokazuje
human prihvata rizično / poslovno
```

ovdje se može proširiti:

```text
jeftiniji worker
+
jači checker kada je opravdano
```

ali samo ako totalni rezultat ostaje povoljniji.

Dakle ne:

```text
cheap model = worker po defaultu
```

nego:

```text
bounded task + jak verifier + nizak ambiguity risk
= kandidat za jeftiniji worker
```

---

## 10. FlowOS treba jasno razlikovati model i harness

Ako postojeći model podataka negdje tretira “Claude”, “Codex”, “GLM” kao isti tip identiteta, dugoročno to može biti problem.

Korisnija taksonomija:

```text
Provider
Model
Harness
Execution Environment
Session
```

Primjer:

```text
Provider: Z.AI
Model: GLM 5.3
Harness: Claude Code
Environment: worktree X
Session: 123
```

ili:

```text
Provider: OpenAI
Model: GPT-*
Harness: Codex
Environment: worktree Y
Session: 456
```

Ovo je strateški korisno za vendor-neutralnost, ali ne treba zbog toga sada mijenjati roadmap bez konkretnog konzumenta.

---

## 11. Najvažniji princip za FlowOS

Transkript snažno potvrđuje raniju ideju:

> **Iznajmi inteligenciju; posjeduj memoriju, procedure, odluke, kontekst i standarde.**

Još preciznije za FlowOS:

```text
MODEL JE ZAMJENJIV.
HARNESS JE ZAMJENJIV.
SESSION JE PRIVREMEN.

CANONICAL STATE, DECISIONS, EVIDENCE I PROJECT RULES
MORAJU OSTATI TVOJI.
```

To je jedan od najjačih razloga za postojanje FlowOS-a.

---

## 12. Šta je korisno sada, a šta kasnije

Ovaj transkript ne mijenja zaključani prioritet read-modela i ne treba da proizvede nove FLOW brojeve.

**Sada vrijedi:**

```text
- zadržati jasnu razliku model / harness / context / conversation;
- koristiti explicit handoff na granici zadataka;
- ne mijenjati modele nasumično usred dugog rada;
- koristiti worktree za paralelne edit sesije;
- čuvati durable odluke izvan chata;
- birati worker prema boundednessu i verifieru, ne samo cijeni.
```

**Kasnije, ako stvarna upotreba opravda:**

```text
- Task Suitability read-model;
- provider/model/harness metadata u session prikazu;
- cost per VERIFIED/ACCEPTED task;
- model capability profile po repou;
- assisted model routing.
```

---

## 13. Najveća nova vrijednost za Agent Context ideju

Ranije smo imali:

```text
FLOWOS_CURRENT.md
= šta trenutno važi
```

Ovaj transkript daje vrlo dobar minimalni podskup za **Agent Handoff**:

```text
Goal
Current state
Relevant files
Constraints
Definition of done
Checks to run
```

To je vjerovatno najbolji početni format jer je:

```text
kratak
portable
vendor-neutral
verifiable
```

i može biti potpuno deterministički generisan iz FlowOS canonical podataka.

---

## 14. Konačni zaključak

Ovaj transkript vrijedi arhivirati jer uvodi novi praktični sloj u FlowOS razmišljanje:

> **Ne treba samo znati šta agent radi; treba moći prenijeti isti rad između modela i harnessa bez gubitka autoritativnog konteksta.**

Najkraće:

```text
Task ima granice.
Session je privremen.
Model je zamjenjiv.
Handoff prenosi rad.
FlowOS čuva ono što mora preživjeti sve njih.
```

I još jedan važan ekonomski princip:

> **Najjeftiniji model nije onaj sa najnižom cijenom tokena, nego onaj koji uz review, retry i verification najjeftinije dovede zadatak do VERIFIED/ACCEPTED stanja.**
