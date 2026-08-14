# FlowOS — agent context kao autoritativni Current Work State

**Status:** konceptualna analiza / arhivski dokument  
**Tema:** kako FlowOS može generisati čitljiv i pouzdan dokument za agente, bez davanja AI-u authority nad samim workflowom

---

# 1. Osnovna ideja

Ključna granica ostaje ista:

> **AI ne odlučuje kako se FlowOS workflow mijenja.**

FlowOS sam, deterministički, održava stanje kroz:

- TaskContract;
- PlanItem;
- WorkflowLedger;
- Session;
- Git stanje;
- verification;
- checkpoint/handoff;
- approval;
- report;
- korisničke odluke.

AI ne smije biti authority za:

- promjenu workflow statusa;
- prihvatanje rezultata;
- promjenu scope-a;
- approval rizične akcije;
- određivanje canonical current state-a.

Ali iz tog determinističkog stanja FlowOS može napraviti **čitljiv radni dokument za agenta**.

To je sasvim druga stvar.

---

# 2. Šta FlowOS zapravo daje agentu

Ideja nije:

```text
AI procijeni stanje
→ AI odluči šta sada važi
→ AI promijeni workflow
```

Nego:

```text
FlowOS utvrdi šta sada važi
→ generiše čitljiv dokument
→ agent ga pročita
→ agent zna gdje je projekat i šta je dozvoljeno
```

Najvažnija formulacija:

> **FlowOS ne govori agentu šta da misli; FlowOS mu daje pouzdanu sliku onoga što je trenutno istina.**

---

# 3. Dokument nije source of truth

Generisani fajl, bez obzira na naziv:

```text
FLOWOS_CURRENT.md
CURRENT_WORK_STATE.md
AGENT_CONTEXT.md
```

ne bi bio novi izvor istine.

On bi bio samo **renderovana projekcija postojećeg canonical stanja**.

Arhitektura:

```text
DATABASE / LEDGER / GIT / VERIFICATION
                ↓
     Current State Projector
                ↓
        Markdown dokument
                ↓
      Claude / Codex / pi
```

Ako se fajl obriše, ništa nije izgubljeno.

FlowOS ga može ponovo generisati.

To je ključna osobina.

---

# 4. Zašto je ovo važno

Agent danas često dobija kombinaciju:

- prethodnog chata;
- velikog CONTEXT fajla;
- više reportova;
- project rooma;
- Git istorije;
- starih odluka;
- raznih bilješki.

Problem je što sve to nije jednako autoritativno.

Fresh agent može pročitati:

```text
stara odluka A
novija odluka B
```

i pogrešno nastaviti po A.

Current Work State treba prikazati samo:

```text
šta trenutno važi
```

dok istorija ostaje dostupna kao referenca.

---

# 5. Primjer sadržaja dokumenta

Mogući generisani dokument:

```md
# Current Work State

## Project
FlowOS

## Current goal
Implementirati read-model koji prikazuje trenutno autoritativno stanje projekta.

## Active work item
Phase 3E — Current State Projection

## Current status
IN_PROGRESS

## Authoritative decisions
- WorkflowLedger je source of truth za user decisions.
- AgentReport.user_verdict je compatibility projection.
- IMPLEMENTED nije isto što i VERIFIED.
- VERIFIED nije isto što i ACCEPTED.

## Scope
- app/services/current_state/
- relevant repositories
- read-only projection

## Out of scope
- AI next-action recommendation
- novi workflow eventi
- OpenTelemetry
- promjena authority modela

## Repository state
Branch: ...
Worktree: ...
Base commit: ...

## Last completed work
Phase 3D authority cutover.

## Verification
- independent review completed
- 28 integration tests PASS
- relevant regression suite PASS

## Known issues
- ...

## Current deterministic requirement
Napraviti read-model iz postojećih canonical podataka.

## Stop / ask user when
- nedostaje authority pravilo;
- postoje kontradiktorni canonical izvori;
- zahtijeva se promjena scope-a.

## References
- relevant docs
- relevant agent reports
- relevant tests
```

Agent dobija mali, svjež i čitljiv radni paket umjesto cijele istorije.

---

# 6. Veza sa AGENTS.md

Ovdje postoji vrlo čista podjela.

## AGENTS.md

Odgovara na pitanje:

> **Kako se radi u ovom repozitorijumu?**

Sadrži:

- trajna pravila;
- sigurnosne granice;
- mapu repoa;
- standarde;
- approval pravila;
- procedure koje važe šire.

## FLOWOS_CURRENT.md

Odgovara na pitanje:

> **Šta trenutno radimo i šta sada važi?**

Sadrži:

- trenutni cilj;
- aktivni work item;
- posljednje authoritative odluke;
- scope;
- trenutno verification stanje;
- blocker;
- sljedeću dozvoljenu workflow fazu;
- reference ka dubljim izvorima.

Podjela:

```text
AGENTS.md
= stable context

FLOWOS_CURRENT.md
= current context
```

---

# 7. Stale informacija: primjer 14 → 28 testova

Dobar realni primjer je prethodna greška:

```text
stari report:
14 integration testova PASS

kasniji independent review:
28 integration testova PASS
```

Ako agent dobije oba dokumenta bez authority modela, postoji rizik da uzme 14 kao trenutnu činjenicu.

FlowOS Current State Projection treba raditi ovako:

```text
raw historical claim:
14

later authoritative verification:
28

current projection:
28

history:
14 → superseded
```

Dakle:

> **Istorija ostaje dostupna, ali current state ima veći autoritet.**

To je jedan od glavnih razloga za postojanje ovog dokumenta.

---

# 8. Dokument je output, ne input authority-ja

Agent ne smije moći uraditi:

```text
izmijeni FLOWOS_CURRENT.md
→ FlowOS to prihvati kao novu istinu
```

To bi ponovo stvorilo dva izvora istine.

Ispravan tok:

```text
agent uradi rad
        ↓
FlowOS detektuje stvarno stanje
        ↓
verification / user decision
        ↓
canonical state se promijeni
        ↓
FLOWOS_CURRENT.md se regeneriše
```

Agent može eventualno prijaviti:

```text
"Mislim da je ova informacija zastarjela."
```

Ali promjena authority-ja mora proći kroz FlowOS workflow i, gdje treba, korisničku odluku.

---

# 9. Gdje čovjek ostaje authority

Neke stvari FlowOS ne može sam zaključiti:

- „Odustajemo od pristupa A.”
- „Ovaj modul više ne diramo.”
- „Promijenio sam poslovni prioritet.”
- „Ovaj rezultat ne prihvatam.”
- „Ova nova informacija mijenja scope.”

To su ljudske odluke.

Tok treba biti:

```text
User decision
→ FlowOS canonical state
→ ledger/state transition
→ regenerisan Current Work State
→ fresh agent vidi novu odluku
```

Čovjek ne mora ručno uređivati generisani Markdown.

---

# 10. Razlika između workflow next action i agentovog tehničkog poteza

Ovo treba strogo razdvojiti.

## FlowOS može deterministički reći

```text
VERIFIED = false
→ verification još nije završena

approval = pending
→ čeka se korisnička odluka

session = crashed + safe checkpoint
→ potreban reconcile/resume

NEEDS_WORK
→ PlanItem se vraća u IN_PROGRESS
```

To je workflow logika.

## Agent odlučuje kako tehnički izvršiti zadatak

Ako FlowOS kaže:

```text
Current goal:
Napraviti Current State read-model.
```

agent sam može odlučiti:

- koje fajlove prvo pregledati;
- kako organizovati implementaciju;
- kakve testove napisati;
- kojim redoslijedom izvršiti tehnički rad.

Dok poštuje:

- scope;
- out-of-scope;
- acceptance kriterijume;
- safety pravila.

Najvažnija granica:

```text
FlowOS određuje:
šta je dozvoljeni workflow state.

Agent određuje:
kako izvršiti dodijeljeni tehnički zadatak.
```

---

# 11. Current State Projection kao centralni model

FlowOS već ima dosta writera:

```text
TaskContract
PlanItem
Session
WorkflowLedgerEvent
AgentReport
GitSnapshot
FileActivity
Checkpoint
Verdict
```

Oni proizvode činjenice.

Ključna nedostajuća vrijednost je reader koji od tih činjenica napravi:

```text
Šta sada važi?
```

Mogući read-model:

```text
ProjectState
│
├── goal
├── active_plan_item
├── workflow_status
├── latest_authoritative_decision
├── active_sessions[]
├── last_safe_checkpoint
├── git_state
├── verification_state
├── blockers[]
├── pending_approvals[]
└── next_required_workflow_action
```

To nije AI summary.

To je deterministička projekcija.

---

# 12. AI može doći tek poslije determinističke projekcije

Ispravna arhitektura:

```text
CANONICAL DATA
      ↓
DETERMINISTIC PROJECTION
      ↓
optional AI explanation
```

Ne:

```text
CANONICAL DATA
      ↓
AI interpretation
      ↓
new source of truth
```

AI eventualno može napraviti:

- kraći sažetak;
- objašnjenje čovjeku;
- prirodniji prikaz;
- pomoć u čitanju.

Ali ne smije odlučivati šta je canonical stanje.

---

# 13. Jedan state, više rendera

Pošto Current State Projection postoji kao strukturisan model, iz istog izvora se mogu praviti različiti prikazi:

```text
                   CurrentStateProjection
                     /        |        \
                    /         |         \
                   ▼          ▼          ▼
               FlowOS GUI   Markdown   JSON/API
```

## GUI

Za čovjeka:

- Gdje si stao;
- Od posljednjeg pregleda;
- Zahtijeva pažnju;
- Brzi dokazi.

## Markdown

Za Claude, Codex, pi ili drugog agenta.

## JSON/API

Za buduće integracije, orchestrator ili automatske alate.

Svi renderi dolaze iz istog source of truth modela.

---

# 14. Tri različite projekcije

Moguće je da ne treba jedan ogromni CurrentState, nego tri fokusirana read-modela.

## Project State

Odgovara:

> Gdje je projekat sada?

## Human Attention State

Odgovara:

> Šta čovjek mora pogledati ili odlučiti?

## Agent Handoff State

Odgovara:

> Šta fresh agent mora znati da nastavi?

Arhitektura:

```text
                    canonical state
                          │
            ┌─────────────┼─────────────┐
            ▼             ▼             ▼
       Project View   Human Attention   Agent Context
```

To može biti čistije i praktičnije od jednog prevelikog dokumenta.

---

# 15. Agent Context treba biti mali

Cilj nije napraviti novu enciklopediju.

Dobro pravilo:

```text
mali
svjež
autoritativan
čitljiv
provjerljiv
```

Idealno:

- nekoliko KB;
- samo active state;
- reference ka dubljim izvorima;
- bez cijelog conversation historyja;
- bez dupliranja canonical dokumentacije.

Agent po potrebi otvara dublje izvore.

Princip:

```text
mapa, ne enciklopedija
```

---

# 16. Zašto je ovo posebno dobro za multi-agent rad

Isti Current Work State mogu pročitati:

```text
Claude Code
Codex
pi
DeepSeek agent
drugi budući agent
čovjek
```

To nije vendor-specific.

FlowOS tako postaje neutralni sloj između:

```text
čovjeka
i
više različitih agentskih alata
```

Agent ne mora znati internu strukturu FlowOS baze.

Dobija čitljiv, standardizovan radni kontekst.

---

# 17. Zašto ovo može biti jedna od najvrjednijih FlowOS funkcija

Problem više nije samo:

```text
Kako sačuvati šta su agenti uradili?
```

nego:

```text
Kako iz svih sačuvanih činjenica
pouzdano izvesti šta trenutno treba vjerovati?
```

Ako FlowOS to može uraditi, onda:

- fresh session počinje brže;
- context window ostaje čistiji;
- stare odluke gube authority;
- više agenata dobija isti current state;
- handoff postaje pouzdaniji;
- čovjek ne mora rekonstruisati stanje iz više terminala i reportova.

---

# 18. Najvažnija zaštita od budućeg bloat-a

Ne praviti paralelne ručne fajlove kao nove izvore istine:

```text
current.md
decisions.md
progress.md
contextmap.md
```

ako iste informacije već postoje u FlowOS canonical modelu.

Bolje:

```text
canonical state
→ generisani agent context
```

nego:

```text
canonical state
+
ručni current.md
+
ručni decisions.md
+
ručni progress.md
```

Jer drugi pristup ponovo proizvodi drift.

---

# 19. Minimalna verzija koju vrijedi dokazati

Prva verzija ne mora znati sve.

Dovoljno je da generisani dokument pouzdano odgovori:

```text
1. Koji je trenutni cilj?
2. Koji PlanItem je aktivan?
3. Koja je posljednja authoritative odluka?
4. Koja je aktivna/posljednja sesija?
5. Koji je Git/worktree state?
6. Šta je implementirano?
7. Šta je verificirano?
8. Šta još nije prihvaćeno?
9. Postoji li blocker ili approval?
10. Šta je sljedeća dozvoljena workflow faza?
11. Gdje agent može pronaći dublje reference?
```

Ako ovo radi pouzdano, ideja je već veoma vrijedna.

---

# 20. Konačna definicija funkcije

Najpreciznija formulacija:

> **FlowOS generiše mali, svjež i autoritativan radni kontekst za agente iz determinističkog current-state read-modela. Dokument nije novi source of truth, nego čitljiva projekcija postojećih canonical podataka. Agent koristi dokument da razumije šta trenutno važi, dok FlowOS i čovjek zadržavaju authority nad workflowom.**

Najkraće:

```text
FlowOS ne odlučuje umjesto agenta kako da kodira.

Agent ne odlučuje umjesto FlowOS-a šta je workflow istina.

FlowOS kaže:
“ovo je trenutno stanje i ovo su granice.”

Agent kaže:
“u redu, evo kako ću izvršiti zadatak.”
```

I jedna rečenica koja najbolje opisuje ideju:

> **FlowOS ne govori agentu šta da misli; FlowOS mu daje pouzdanu sliku onoga što je trenutno istina.**
