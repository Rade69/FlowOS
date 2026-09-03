---
document_type: flowos_plan_amendment
base_document: FlowOS-plan-razvoja-v5-2026-08-28.md
base_status: ispravljeni kandidat za kanonski roadmap
amendment_date: 2026-09-01
scope: minimalna integracija provjerljivih obrazaca iz analize Tactical Agentic Coding / Software Factory pristupa
status: kandidat za ugradnju u isti v5; ne uvodi v6
---

# FlowOS v5 — deterministička harness integracija

## Namjena

Ovo nije novi roadmap i ne mijenja identitet FlowOS-a. Ovo je **minimalna dopuna postojećeg v5** koja ugrađuje samo obrasce koji povećavaju provjerljivost bez pretvaranja FlowOS-a u agent orchestrator ili software factory.

Osnovna granica ostaje:

> **AI radi. FlowOS pamti, povezuje i dokazuje. Čovjek odlučuje.**

Ne uvodi se:

```text
agent launcher
agent scheduler
agent retry/correction loop
model router
agent-to-agent komunikacija
software-factory DAG executor
sandbox/VM orchestrator
auto merge/push
LLM authority
```

Ostatak `FlowOS-plan-razvoja-v5-2026-08-28.md` ostaje nepromijenjen osim tačno navedenih dopuna ispod.

---

# A. Sažetak odluka koje se ugrađuju

## A1 — Post-work Contract Scope Verification

Postojeći `FLOW-1164` više ne provjerava samo preklapanje `allowed_paths` prije paralelnog rada. Mora poslije implementacije uporediti **stvarni Git diff** sa Task Contractom.

Canonical pravilo:

```text
AgentReport.changed_files = CLAIM
Git changed paths          = SOURCE_FACT
```

FlowOS ne vjeruje agentovoj listi promijenjenih fajlova kao dokazu scope-a.

## A2 — Verification Freshness Gate

Dodaje se jedan novi task:

```text
FLOW-1168 — Verification Freshness Gate [M]
```

Razlog: `FLOW-1905` u Fazi D je prekasno za osnovnu sigurnost acceptance workflowa. Potreban je uži, obavezni gate već u Fazi B koji odgovara na pitanje:

> Da li required verification dokaz pripada **trenutnom kodu i trenutnom Task Contract snapshotu**?

## A3 — Mechanical evidence mora objasniti šta je provjereno

`FLOW-1112` se proširuje tako da mechanical evidence, gdje verifier može deterministički razložiti provjeru, nosi `checks[]` uz command/exit/provenance/snapshot.

PASS više ne znači samo:

```text
passed = true
```

nego, gdje je moguće:

```text
koji gate
koji snapshot
koje konkretne provjere
koji command / exit code
koji artifact/hash
```

## A4 — Structured AgentReport envelope

`FLOW-1172` se proširuje iz prostog formalizovanja ingestiona u **versioned machine-readable AgentReport ugovor**. Markdown ostaje ljudski čitljiv, ali machine-relevant podaci ne smiju zavisiti od slobodnog parsiranja proze.

## A5 — Agent Integration Pack

Ne pravi se novi backend subsystem niti novi FLOW task. Kao dio `FLOW-1170–1172` isporučuje se tool-neutral vodič/schema koji eksternom agentu govori:

```text
šta može READ iz FlowOS-a
kako da traži samo potreban kontekst
šta znači SOURCE_FACT / CLAIM / HUMAN_DECISION
kako da napiše AgentReport v2
šta nikad ne smije predstavljati kao dokaz
```

## A6 — Verification-sensitive promjene ne smiju neprimjetno promijeniti "ispit"

Ne uvodi se poseban protected-grader subsystem.

Pravilo se provodi postojećim mehanizmima:

```text
- test/guard/verify/CI fajl koji nije u allowed_paths → SCOPE_VIOLATION
- ako je eksplicitno u allowed_paths → promjena je dozvoljena
- takva promjena čini prethodni relevantni verification evidence nevažećim za trenutni snapshot
- gdje FLOW-1305 važi, adversarial proof ostaje obavezan
- independent review ostaje ljudsko/role pravilo
```

FlowOS ne rollbackuje kod automatski.

## A7 — Evidence-backed Operating Level / Escalation Rule

Ne uvodi se novi FlowOS status niti novi FLOW task. Engineering method dobija pravilo da se **leverage povećava samo dok postoje dovoljno razumijevanja i dokazivosti**.

Kada su domen, Task Contract, acceptance kriteriji i verifier dovoljno jasni, čovjek + agent mogu raditi na višem nivou apstrakcije.

Kada je evidence slab ili stale, sistem/rizik nepoznat, rezultati kontradiktorni ili Task visokog rizika, rad se spušta na niži nivo apstrakcije dok se ponovo ne uspostave kontrola i dokaz.

FlowOS ne pokušava canonicalno izračunati "agentic operating level"; koristi postojeće provjerljive signale kao što su scope violation, missing/stale verification i neispunjeni acceptance kriteriji.

---

# B. Dopuna §4 — Neupitne arhitektonske granice

Poslije postojeće tačke 30 dodati:

```text
31. AgentReport lista promijenjenih fajlova je CLAIM; Git je authority za stvarni changed-path set.
32. VERIFIED je važeći samo za code/contract snapshot na kojem je verification nastao; relevantna kasnija promjena zahtijeva novi fresh verification prije acceptancea.
33. Mechanical gate rezultat mora biti objašnjiv kroz provenance, snapshot i konkretne checks gdje ih verifier može deterministički izložiti.
34. FlowOS može blokirati workflow tranziciju zbog scope/freshness pravila, ali ne rollbackuje, ne popravlja i ne retry-a agentski rad.
```

## Dopuna §4.1 — slojevita arhitektura

Postojeći tekst `Tri posebno rizične nove površine` promijeniti u:

```text
Pet posebno rizičnih novih površina:
```

Uz postojeće `FLOW-1163`, `FLOW-1167` i `FLOW-1170` dodati:

```text
FLOW-1164 — Contract scope verification
Controller/workflow entry
→ TaskScopePolicyService
→ TaskContractService + GitStateReader

FLOW-1168 — Verification freshness gate
WorkflowDecision/verification entry
→ VerificationFreshnessService
→ VerificationService + GitStateReader + TaskContractService
```

Ni jedan od ovih servisa ne smije biti zaobiđen direktnim Git/ORM pozivom iz View/route/CLI sloja.

---

# C. Dopuna §5 — Engineering method

U preporučenom toku rada između `Implementation` i `Independent review`, odnosno nakon svake korekcije koja mijenja kod/contract/verification surface, primjenjuje se:

```text
Implementation
        ↓
Actual Git scope verification
        │
        ├─ changed paths unutar Task Contracta
        │      → nastavi
        │
        └─ out-of-scope / forbidden path
               ↓
          SCOPE_VIOLATION
               ↓
          STOP workflow transition
          → human correction / contract decision
        ↓
Required verification na trenutnom snapshotu
        ↓
Independent review
        ↓
Finding → Fix → Re-review
        ↓
ako je kod/contract/verification surface promijenjen
        ↓
required verification mora ponovo biti fresh
        ↓
Human decision
```

Agentov završni odgovor nije zamjena ni za scope verification ni za fresh verification.

## C.1 — Operating Level / Evidence-backed Escalation Rule

FlowOS engineering method koristi najviši nivo apstrakcije za koji još postoji dovoljno **razumijevanja, kontrole i dokazivosti**.

Ovo nije novi workflow status, canonical fact niti novi FLOW task. To je metodološko pravilo za čovjeka i eksternog agenta.

### MOVE UP — povećaj leverage kada

```text
- domen i relevantni dio codebase-a su dovoljno poznati
- posao je poznat ili ponovljiv
- Task Contract i acceptance kriteriji su jasni
- postoji pouzdana fitness/verifikaciona funkcija
- prethodni slični Taskovi imaju dovoljno dobar evidence
- agent/harness može raditi na višem nivou bez gubitka potrebne kontrole
```

Primjeri višeg nivoa rada:

```text
plan
repo/module
reusable skill
agent workflow
eksterni ADW/software factory
```

FlowOS i dalje ne orkestrira te sisteme; samo posmatra i provjerava njihove posljedice.

### MOVE DOWN — povećaj kontrolu kada

```text
- domen ili relevantni dio sistema nije dovoljno poznat
- codebase je nov ili ponašanje nije dovoljno razumljivo
- agenti daju kontradiktorne rezultate
- debugging/verification evidence je slab, nedostaje ili je stale
- Task je visokog rizika ili visokog uticaja
- arhitektura, sigurnost, podaci ili performance zahtijevaju detaljnu kontrolu
- implementation assumption se pokaže pogrešnom
- nije moguće jasno razlikovati dobar od lošeg ishoda
```

MOVE DOWN ne znači povratak na ručno programiranje.

Znači da čovjek + agent rade na nižem nivou apstrakcije dok se ne uspostave razumijevanje i dokaz:

```text
product/repo
→ modul
→ direktorij/fajl
→ tip/klasa
→ funkcija
→ konkretan execution/data path
→ linija koda samo kada je stvarno potrebna
```

### Pravilo povratka prema leverage-u

Kada se ponovo uspostave:

```text
razumijevanje
+ jasan Task Contract
+ pouzdan verifier
+ fresh evidence
```

rad se može vratiti na viši nivo apstrakcije.

### Automatizacija ponovljivog rada

Ponovljeni posao je signal za veću automatizaciju, ali sam broj ponavljanja nije authority.

Kandidat za skill/agent workflow/ADW postoji kada su dovoljno stabilni:

```text
ulazi
+ očekivani izlazi
+ acceptance kriteriji
+ verification/fitness funkcija
+ failure granice
```

Ne uvoditi tvrdo pravilo tipa `tri ponavljanja = automatizuj`.

### Veza sa FlowOS evidence pravilima

FlowOS ne pokušava da izračuna ili canonicalno skladišti "agentic operating level".

Umjesto toga koristi mehanički dokazive signale koji mogu zahtijevati spuštanje nivoa rada:

```text
SCOPE_VIOLATION
MISSING verification
STALE_FOR_CURRENT_SNAPSHOT
POTENTIALLY_STALE evidence
kontradiktorni review nalazi
neispunjeni acceptance kriteriji
nepoznata ili nedovoljno jaka atribucija
```

Ovi signali ne znače automatski da je implementacija pogrešna. Znače da **trenutni nivo leverage-a više nema dovoljno dokazive kontrole** i da čovjek/agent treba detaljnije pregledati problem prije nastavka.

Canonical princip:

> **Leverage se povećava samo tamo gdje postoje dovoljno razumijevanja i dokazivosti. Kada dokaz oslabi, rad se spušta na niži nivo dok se kontrola ponovo ne uspostavi.**

---

# D. Dopuna §7.1 — Tri sloja provođenja

U `MEHANIČKI PROVODIVO` dodati:

```text
stvarni Git changed paths moraju biti unutar allowed_paths i van forbidden_paths
required verification mora biti fresh za trenutni code/contract snapshot prije ACCEPTED
promjena verification-sensitive fajla koji nije eksplicitno u allowed_paths je scope violation
mechanical gate PASS mora imati provenance/snapshot; checks[] gdje verifier može izložiti pojedinačne provjere
```

U `SAMO BILJEŽIVO` zadržati kvalitet reviewa/testa kao ljudsku procjenu. FlowOS može dokazati da je test pokrenut i čemu je bio vezan, ali ne tvrdi automatski da je test semantički dobar.

---

# E. Dopuna §7.2 — reuse postojeće arhitekture

Dodati/izmijeniti redove reuse tabele:

| Postojeći element | Odluka u dopunjenom v5 | FLOW |
|---|---|---|
| `services/evidence.py` | **Proširiti**, ne duplirati: uz postojeći evidence bundle/read-model podržati structured mechanical gate podatke i freshness status koji dolaze iz canonical verification/staleness servisa. | 1112, 1168, 1203, 1905 |
| `services/verification/service.py` | **Proširiti**, ne praviti paralelni test runner: verification rezultat veže se za snapshot/provenance i, gdje je moguće, izlaže `checks[]`. | 1112, 1167, 1168 |
| `services/reports/ingestion.py` | Zadržati kao jedini podržani AgentReport ingestion put; proširiti na versioned structured envelope i idempotentni source hash. | 1150, 1172 |

---

# F. Izmjena §7.4 — Blueprint mapping

U postojećoj tabeli promijeniti samo relevantna pokrića:

```text
§4 Task Contract
1160 + 1164 + 1168
- contract postoji prije koda
- stvarni Git scope se provjerava poslije rada
- required verification mora odgovarati trenutnom contract/code snapshotu

§7 Pipeline po tasku
1160–1168, 1305, 1401–1403; report ingestion 1172

§10 Paralelizacija / scope
1164
- pre-work allowed_paths overlap
- post-work actual Git scope verification

§12 Evidence/report precision
1112, 1150, 1172, 1303; 1905 za broad staleness
- machine-readable report fields nisu izvedeni iz slobodne proze
- agent changed_files ostaje CLAIM
- mechanical PASS je objašnjiv

§14 Post-merge gate
1167 + 1168
- post-merge verify mora biti na stvarnom main snapshotu
- rezultat mora biti fresh za taj snapshot

§16 Anti-patterns
1160–1168, 1305, 1155
- zabranjen retro contract
- zabranjen self-review authority
- zabranjen stale verification kao current VERIFIED
- agentov changed_files claim nije zamjena za Git diff
- agent ne može neprimjetno promijeniti verification surface van ugovorenog scope-a
```

---

# G. Izmjena FLOW-1112 — Evidence Semantics Contract `[M]`

Postojeći sadržaj ostaje. Dodati sljedeći pododjeljak.

## Mechanical evidence envelope

`proof_kind=MECHANICAL` mora, kada je relevantno i dostupno, moći izložiti:

```text
gate_id / gate_name
passed
observed_at
snapshot_ref
command nullable
exit_code nullable
artifact_ref/hash nullable
checks[] nullable
```

`checks[]`:

```text
item
ok
note nullable
```

Primjer:

```json
{
  "gate_name": "contract_scope",
  "passed": false,
  "snapshot_ref": "git:abc123",
  "checks": [
    {"item": "src/flowos/service/a.py in allowed_paths", "ok": true},
    {"item": "src/flowos/service/database.py in allowed_paths", "ok": false, "note": "out of contract scope"}
  ]
}
```

Pravila:

```text
- checks[] nije nova semantic class
- PASS/FAIL ostaje SOURCE_FACT kada je deterministički izveden
- checks[] se ne izmišlja gdje verifier nema stvarnu pojedinačnu provjeru
- nema LLM-generated checks
- provenance i snapshot ostaju vidljivi
```

Ne uvoditi novu globalnu evidence tabelu samo radi ovog oblika ako postojeći verification/evidence storage može biti proširen bez dupliranja source of truth-a.

---

# H. Izmjena FLOW-1160 — Task Contract v1 `[M]`

Postojeći model ostaje:

```text
goal
risk
scope
out_of_scope
allowed_paths
forbidden_paths
acceptance
implementer
reviewers
verification_commands
```

Dodati invariant:

```text
Task Contract ima stabilan revision/hash identitet.
Svaka promjena authoritative contract granice proizvodi novu revision/hash vrijednost.
Verification evidence mora navesti contract revision/hash na kojem je nastao.
```

Ne dodavati poseban `protected_grader` model.

Za testove, guardove, verify skripte i CI konfiguraciju važi isto pravilo kao za svaki drugi fajl: moraju biti eksplicitno unutar contract scope-a da bi njihova izmjena bila dozvoljena.

---

# I. ZAMIJENITI FLOW-1164 ovim tekstom

## FLOW-1164 — Task scope policy: pre-work overlap + post-work Git scope verification `[M]`

FLOW-1164 ima dvije odvojene determinističke provjere.

### 1. Pre-work parallelization check

```text
Task A.allowed_paths ∩ Task B.allowed_paths
```

Ako postoji preklapanje aktivnih writer Taskova:

```text
→ BLOCK / zahtijevaj promjenu ugovora ili serijalizaciju
```

Ovo ne pokušava semantički dokazati sve dependency konflikte.

### 2. Post-work actual scope verification

Nakon implementacije, prije workflow tranzicije koja može voditi prema `VERIFIED/ACCEPTED`:

```text
Task Contract.allowed_paths
Task Contract.forbidden_paths
        +
Git actual changed paths
        ↓
TaskScopePolicyService
```

Pravila:

```text
actual_changed_paths ⊆ allowed_paths
actual_changed_paths ∩ forbidden_paths = ∅
```

Ako nije ispunjeno:

```text
SCOPE_VIOLATION
→ mechanical evidence
→ workflow transition blokiran
→ nema auto rollbacka
→ čovjek ili koriguje kod ili eksplicitno mijenja contract
```

Posebno:

```text
AgentReport.changed_files je CLAIM.
Ne može zadovoljiti scope gate.
FlowOS ga može uporediti sa Git changed paths i prikazati mismatch.
```

Verification-sensitive fajlovi:

```text
- ako nisu u allowed_paths → običan SCOPE_VIOLATION
- ako jesu u allowed_paths → izmjena je dozvoljena, ali prethodni relevantni verification više nije fresh
- FLOW-1305 ostaje obavezan gdje njegova pravila važe
```

### Architecture path / guard

```text
Task/Workflow Controller
→ TaskScopePolicyService
→ TaskContractService + GitStateReader
```

Pre-work overlap dio može koristiti aktivne Task Contracte; post-work dio mora koristiti stvarni Git source fact.

### Acceptance

```text
[ ] pre-work overlap i dalje blokira konkurentne writer scopeove
[ ] Git diff potpuno unutar allowed_paths → PASS
[ ] jedan out-of-scope fajl → SCOPE_VIOLATION
[ ] forbidden path promjena → SCOPE_VIOLATION
[ ] AgentReport kaže "2 fajla", Git pokazuje 3 → Git pobjeđuje; mismatch je vidljiv
[ ] scope violation ne rollbackuje fajl niti pokreće agenta
[ ] test/guard/verify fajl van allowed_paths se tretira isto kao drugi scope violation
```

---

# J. Dopuna FLOW-1167 — Post-merge integration gate `[M]`

Postojeći sadržaj ostaje. Dodati:

Mechanical evidence post-merge gatea mora biti vezan za tačan `main` snapshot i koristiti envelope iz `FLOW-1112`.

Gdje verifier može deterministički navesti pojedinačne provjere, persistuje:

```text
checks[]
```

Post-merge gate rezultat ne može ostati `fresh` ako se relevantni `main` snapshot promijeni poslije provjere.

`FLOW-1168` je canonical freshness authority za required verification.

---

# K. NOVI TASK — FLOW-1168

## FLOW-1168 — Verification Freshness Gate `[M]`

### Problem

Zeleni test ili verify rezultat nije dokaz za kod koji je promijenjen **nakon** te provjere.

Primjer:

```text
verify GREEN na snapshotu A
        ↓
reviewer traži korekciju
        ↓
kod postane snapshot B
        ↓
stari GREEN nije verification snapshota B
```

Ovo nije tvrdnja da je snapshot B pogrešan. To je samo dokaziva činjenica da prethodni verification nije dokaz za trenutni snapshot.

### Cilj

Prije `ACCEPTED` FlowOS mora moći deterministički odgovoriti:

```text
Da li required verification pripada trenutnom code/contract snapshotu?
```

### Minimalni snapshot binding

Required mechanical verification vezuje se najmanje za:

```text
project/task
Task Contract revision/hash
Git HEAD / verified commit ili ekvivalentni immutable snapshot ref
worktree/branch relation gdje je relevantno
verification command identity
observed_at
```

Gdje verification nije commit-based, implementation može koristiti deterministički content/path digest, ali ne smije izmišljati jednakost snapshotova heuristikom.

### Freshness pravilo

```text
verification snapshot == current required snapshot
→ FRESH

relevant code/contract snapshot se promijenio
→ STALE_FOR_CURRENT_SNAPSHOT
→ required verification mora ponovo biti pokrenut
```

`STALE_FOR_CURRENT_SNAPSHOT` znači samo:

> ovaj dokaz ne pripada trenutnom snapshotu.

Ne znači:

> trenutni kod je neispravan.

### Acceptance gate

`WorkflowDecisionService` ne smije dozvoliti `ACCEPTED` kada Task Contract zahtijeva verification, a required verification je:

```text
MISSING
ili
STALE_FOR_CURRENT_SNAPSHOT
```

Ljudska odluka i dalje ostaje authority za acceptance, ali FlowOS mora mehanički spriječiti da UI/API predstavi stale verification kao ispunjen required gate.

Ako product policy kasnije želi eksplicitni override, to mora biti zasebna `HUMAN_DECISION` sa audit trailom; ne uvoditi silent bypass.

### Šta invalidira required verification

Najmanje:

```text
relevant code snapshot/promijenjeni fajl
Task Contract authoritative revision
verification-sensitive fajl koji utiče na isti gate
worktree/branch relation kada mijenja snapshot identity
```

Promjena samo report proze bez promjene relevantnog snapshota ne smije automatski invalidirati verification.

### Architecture path / guard

```text
WorkflowDecision / Verification Controller
→ VerificationFreshnessService
→ VerificationService + GitStateReader + TaskContractService
```

Freshness logika ne smije biti kopirana u GUI, MCP ili HTTP rute.

### Acceptance

```text
[ ] GREEN verify na snapshotu A je FRESH za A
[ ] kod se promijeni A → B: prethodni verify je STALE_FOR_CURRENT_SNAPSHOT
[ ] reviewer fix poslije GREEN verify-a zahtijeva novi verify
[ ] novi verify na B vraća FRESH
[ ] relevantna Task Contract revision invalidira prethodni required verify
[ ] nerelevantna report/prose promjena ne invalidira code verification
[ ] ACCEPTED je blokiran kada required verification nije fresh
[ ] status ne tvrdi da je novi kod pogrešan; tvrdi samo da stari dokaz nije current
```

---

# L. Gate B — zamijeniti postojećom dopunjenom listom

```text
[ ] Task Contract postoji kao model, ne samo Markdown konvencija
[ ] prije implementacionog commita postoji Task Contract sa stabilnim revision/hash identitetom
[ ] implementer i reviewer su odvojene uloge
[ ] HIGH risk ne može do ACCEPTED bez 2 nezavisna reviewera
[ ] claim nad aktivno claimovanim fajlom drugog Taska se odbija
[ ] allowed_paths overlap blokira nekonzistentnu paralelnu dodjelu
[ ] stvarni Git changed paths prolaze post-work Contract Scope Verification
[ ] AgentReport.changed_files se ne koristi kao Git authority
[ ] forbidden/out-of-scope promjena blokira workflow tranziciju bez auto rollbacka
[ ] stale claim je vidljiv
[ ] dependent Task ne ide dalje dok dependency nije dokazivo u main
[ ] post-merge gate proizvodi mechanical evidence na stvarnom main snapshotu
[ ] mechanical gate može objasniti pojedinačne checks gdje ih verifier deterministički poznaje
[ ] required verification je fresh za trenutni code/contract snapshot prije ACCEPTED
[ ] review/fix nakon verificationa invalidira stari required verification ako je snapshot promijenjen
[ ] claim mora biti releaseovan prije zatvaranja Taska
[ ] velocity uzorak postoji za najmanje 5 stvarnih Taskova
```

---

# M. Dopuna FLOW-1170 — Read-only agentska površina

Postojeći query use-caseovi ostaju.

Dodati obavezni **FlowOS Agent Integration Pack** kao dio isporuke ovog taska, bez novog backend subsystema.

Canonical, tool-neutral sadržaj:

```text
docs/agent-integration/
    README.md                  # canonical protocol i pravila
    agent-report-v2.schema.*   # machine-readable schema ili ekvivalentni formalni contract
    examples/
        minimal-read-flow.md
        minimal-report.md
```

Tačna ekstenzija schema fajla je implementation odluka (`json`, `yaml`, Pydantic-exported JSON schema...), ali mora postojati samo jedan canonical contract.

Guide mora objasniti:

```text
- FlowOS je READ/pull za agente
- ne bulk-loadovati cijeli projekat kada postoji task-scoped query
- koristiti get_task_contract prije implementacije
- koristiti get_task_evidence/get_handoff po potrebi
- SOURCE_FACT ≠ CLAIM
- AgentReport.changed_files nije Git fact
- HUMAN_DECISION je acceptance authority
- stale evidence mora ostati označen
- kako generisati AgentReport v2
```

Tool-specific Claude/Codex/Pi/Crush skill/prompt adapteri, ako se dodaju, moraju biti tanki potrošači ovog canonical guide/schema sloja. Ne smiju postati zasebni izvori workflow pravila.

### Dodatni acceptance

```text
[ ] jedan tool-neutral agent integration guide postoji
[ ] schema AgentReporta je machine-readable
[ ] eksterni agent može dobiti samo Task-scoped context bez učitavanja punog projekta
[ ] najmanje jedan stvarni fresh-agent dogfood koristi guide bez prethodnog chata
```

---

# N. Dopuna FLOW-1171 — agentski read DTO

Postojeći semantic class/provenance ostaje.

Kada odgovor uključuje mechanical verification/gate, DTO može uključiti:

```json
{
  "value": "...",
  "semantic_class": "SOURCE_FACT",
  "proof_kind": "MECHANICAL",
  "freshness": "FRESH",
  "snapshot_ref": "git:abc123",
  "source_type": "verification_artifact",
  "source_id": "...",
  "checks": [
    {"item": "pytest tests/unit", "ok": true}
  ],
  "observed_at": "..."
}
```

`checks` i `freshness` se izlažu samo ako postoji canonical source; ruta ih ne izračunava sama.

---

# O. ZAMIJENITI FLOW-1172 ovim tekstom

## FLOW-1172 — AgentReport v2: structured envelope + podržani ingestion ugovor `[M]`

Postojeći `reports/ingestion.py` ostaje jedini podržani ingestion put za report fajlove.

Direction ostaje:

```text
external agent/human writes structured report file
→ FlowOS observes/ingests
→ validates versioned schema/front matter
→ stores source identity/hash
→ normalizes machine-readable fields
```

Ne dodavati FlowOS→agent write/control kanal.

### Source format

Markdown ostaje podržan i ljudski čitljiv.

Machine-relevant polja moraju biti u **versioned structured envelope-u**; FlowOS ih ne smije zaključivati iz slobodne proze.

Minimalni AgentReport v2 canonical payload uključuje postojeći identity/front-matter contract i, gdje je relevantno:

```text
flowos_report_version
report_id
session_id
report_type
tasks
created_at
work_status
agent/model metadata
risk/implementer/reviewers gdje pripada report tipu
commits
Task Contract reference/revision
changed_files_claim
artifacts
verification_claims
findings
out_of_scope_findings
notes_for_next
```

Source file hash se persistuje radi idempotency/provenance.

### Semantika

```text
changed_files_claim = CLAIM
verification_claims = CLAIM dok FlowOS ne poveže stvarni mechanical source
findings = CLAIM/structured reviewer data prema source tipu
notes_for_next = CLAIM/context, nikad authority
```

FlowOS upoređuje `changed_files_claim` sa stvarnim Git changed paths kroz `FLOW-1164` kada su oba dostupna.

Mismatch se prikazuje; agentov claim ne prepisuje Git.

### Parser pravilo

```text
structured field nedostaje
→ UNKNOWN/MISSING prema contractu
→ ne pokušavati LLM/NLP ekstrakciju iz proze
```

Human-readable Markdown body može imati dodatno objašnjenje, ali nije skriveni machine authority.

### Architecture path / guard

```text
Watcher/HTTP import Controller
→ AgentReportIngestionService
→ ReportEnvelopeValidator/normalizer
→ report persistence
```

### Acceptance

```text
[ ] v2 envelope ima versioned schema
[ ] isti report ingestovan dva puta ne duplira canonical zapis
[ ] source hash/provenance se čuva
[ ] changed_files_claim ostaje CLAIM
[ ] Git/report mismatch je vidljiv
[ ] nedostajuće structured polje se ne izvlači iz proze heuristikom
[ ] unknown schema version fail-closed ili ide u eksplicitni unsupported status
[ ] postojeći validni v1 reporti imaju eksplicitnu backward-compat/migration odluku
```

---

# P. ZAMIJENITI FLOW-1905 ovim razgraničenim tekstom

## FLOW-1905 — General Evidence Staleness Projection `[L]` — Faza D

`FLOW-1168` već rješava uski i obavezni **required verification freshness gate** prije acceptancea.

`FLOW-1905` ostaje širi read/projection problem za sve vrste evidencea koje FlowOS prikazuje čovjeku ili eksternom agentu.

Ako se dokazivo promijeni relevantni:

```text
base commit
file/content hash
Task Contract revision
worktree/branch relation
evidence dependency/reference
```

FlowOS deterministički izlaže freshness/staleness status.

Za mechanical verification gdje snapshot binding daje jasan mismatch može se koristiti:

```text
STALE_FOR_CURRENT_SNAPSHOT
```

Za šire evidence vrste gdje promjena samo ukazuje da dokaz možda više nije dovoljan:

```text
POTENTIALLY_STALE
```

Ni jedan status ne znači automatski da je sadržaj dokaza netačan.

### Cilj

Agent, GUI i Handoff ne smiju prikazati stari dokaz kao neoznačeno current stanje.

### Architecture path / guard

```text
EvidenceService / ProjectStateService
→ StalenessService
→ canonical read DTO
```

MCP/HTTP/GUI ne sadrže sopstvenu staleness logiku.

### Acceptance

```text
[ ] broad evidence dobija objašnjiv freshness status
[ ] mechanical verification koristi FLOW-1168 kao authority za required gate freshness
[ ] POTENTIALLY_STALE nije predstavljen kao FAILED
[ ] stale oznaka nosi razlog/provenance
[ ] agentska read površina nikad ne sakriva poznatu stale oznaku
```

---

# Q. Gate D — dopuna

Postojeću Gate D listu proširiti sa:

```text
[ ] Agent Integration Pack postoji kao tool-neutral canonical guide/schema
[ ] AgentReport v2 koristi versioned structured envelope
[ ] machine-relevant report podaci se ne izvlače iz slobodne proze
[ ] changed_files_claim je jasno odvojen od Git SOURCE_FACT-a
[ ] mechanical evidence iz read površine nosi snapshot/freshness kada postoji canonical podatak
[ ] fresh eksterni agent može koristiti task-scoped queries bez bulk učitavanja cijelog projekta
```

Postojeće Gate D stavke ostaju.

---

# R. Dodatna test matrica za ovu integraciju

Postojeći §33 ostaje nepromijenjen. Neposredno prije njega dodati novi pododjeljak:

## 32.1 — Obavezni testovi determinističke harness integracije

### Contract scope

```text
- actual Git diff potpuno u allowed_paths → PASS
- jedan Git changed path van allowed_paths → SCOPE_VIOLATION
- forbidden path → SCOPE_VIOLATION
- AgentReport.changed_files mismatch sa Gitom → Git ostaje authority
- scope violation ne radi rollback niti agent retry
- test/guard/verify fajl van allowed_paths → scope violation
```

### Verification freshness

```text
- verify GREEN na snapshotu A → FRESH
- relevantna code promjena A→B → STALE_FOR_CURRENT_SNAPSHOT
- reviewer fix poslije GREEN-a → novi verify obavezan
- rerun na B → FRESH
- relevantna Task Contract revision → prethodni required verify stale
- nerelevantna report proza ne invalidira code verification
- ACCEPTED blokiran kada required verification nije fresh
```

### Mechanical gate explanation

```text
- gate PASS/FAIL nosi snapshot/provenance
- checks[] round-trip kroz persistence/API gdje ih verifier proizvodi
- checks[] se ne generiše heuristički kada ne postoji izvor
```

### AgentReport v2

```text
- validan v2 envelope se parsira
- unknown version fail-closed/unsupported
- source hash omogućava idempotent ingestion
- structured field se ne izvlači iz slobodne proze
- changed_files_claim ostaje CLAIM
```

### Agent read integration

```text
- task-scoped query ne vraća nepotreban full-project dump
- read surface nema write/launch/prompt alat
- stale status se ne gubi kroz DTO/API/MCP renderer
```

---

# S. Izmjena §29 — Sizing

U Fazi B promijeniti:

```text
FLOW-1164 — Task scope policy / actual Git scope verification | M
FLOW-1168 — Verification Freshness Gate                         | M
```

Ostali B taskovi ostaju isti.

U Fazi D promijeniti:

```text
FLOW-1172 — AgentReport v2 structured envelope + ingestion | M
```

`FLOW-1905` ostaje `L`.

---

# T. Izmjena §31 — Prioriteti

Faza B postaje:

```text
1160–1168
1505
```

Redoslijed unutar B:

```text
1160 Task Contract
→ 1161 Roles
→ 1162 Risk gate
→ 1163 Claims
→ 1164 Scope policy + actual Git scope verification
→ 1165 Stale claim
→ 1166 Dependency in main
→ 1167 Post-merge gate
→ 1168 Verification Freshness Gate
→ 1505 Velocity calibration
```

Napomena: `1168` mora biti završen prije nego što `ACCEPTED` workflow postane oslonjen na required verification gateove u realnom dogfoodingu.

Faza D ostaje numerički:

```text
1170–1172
1905
1604–1605
```

ali `1172` sada ima size `M`.

---

# U. Izmjena mape novih FLOW brojeva

Gdje v5 trenutno kaže:

```text
Faza B: 1160–1167
```

zamijeniti sa:

```text
Faza B: 1160–1168
```

`FLOW-1168` koristi isti rezervisani opseg `1150–1199`; nijedan stari broj se ne prenamjenjuje.

---

# V. Izmjena §36 — Konačna razvojna mapa

Faza B postaje:

```text
FAZA B — BLUEPRINT JEZGRO
│
├─ FLOW-1160  Task Contract v1 + contract revision/hash
├─ FLOW-1161  Roles
├─ FLOW-1162  Risk/reviewer gate
├─ FLOW-1163  File claims
├─ FLOW-1164  Scope policy: pre-work overlap + post-work Git scope verification
├─ FLOW-1165  Stale claim
├─ FLOW-1166  Dependency really in main
├─ FLOW-1167  Post-merge integration gate
├─ FLOW-1168  Verification Freshness Gate
└─ FLOW-1505  Velocity calibration
```

Faza D opisno precizirati:

```text
FAZA D — AGENTSKA READ POVRŠINA / STRUCTURED HANDOFF
│
├─ FLOW-1170  Read-only canonical agent surface + Agent Integration Pack
├─ FLOW-1171  Semantic class/provenance + snapshot/freshness DTO
├─ FLOW-1172  AgentReport v2 structured envelope + ingestion
├─ FLOW-1905  General Evidence Staleness Projection
├─ FLOW-1604  Handoff State
└─ FLOW-1605  Handoff rendereri
```

---

# W. Šta se namjerno NE preuzima iz Software Factory pristupa

Ovo ostaje eksplicitno van FlowOS core-a i **ne dodavati taskove** za to:

```text
FlowOS pokreće agente
FlowOS bira model
FlowOS vodi agent DAG
FlowOS šalje correction prompt
FlowOS retry-a agent
FlowOS pravi agent-to-agent mrežu
FlowOS upravlja VM/sandbox fleetom
FlowOS automatski commit/merge/pushuje
FlowOS koristi broj tool callova kao KPI
FlowOS smatra više agenata dokazom većeg kvaliteta
```

Ako eksterni harness/software factory radi bilo šta od navedenog, FlowOS ga može posmatrati kao još jedan **eksterni izvor rada** i ingestovati/provjeravati posljedice kroz iste Task/Git/Evidence ugovore.

---

# X. Konačni minimalni set promjena

Nakon ove integracije ne nastaje nova arhitektura. Promjene su:

```text
PROŠIRENO  FLOW-1112  mechanical evidence envelope + checks[]
PROŠIRENO  FLOW-1160  contract revision/hash
PROŠIRENO  FLOW-1164  pre-work overlap + post-work actual Git scope verification
PROŠIRENO  FLOW-1167  snapshot-bound post-merge evidence
NOVO       FLOW-1168  Verification Freshness Gate
PROŠIRENO  FLOW-1170  Agent Integration Pack
PROŠIRENO  FLOW-1171  freshness/snapshot read DTO
PROŠIRENO  FLOW-1172  AgentReport v2 structured envelope
RAZGRANIČ. FLOW-1905  broad evidence staleness; ne duplira 1168
METODOLOGIJA         Evidence-backed Operating Level / Escalation Rule; bez novog FLOW taska
```

Bez novih subsystema za:

```text
agent orchestration
protected grader engine
novi evidence storage
novi test runner
novi Git engine
novi LLM sloj
```

## Konačna odluka

Najvažnije dvije zaštite koje se sada pomjeraju u Blueprint jezgro su:

```text
1. stvarni Git diff mora odgovarati Task Contract scope-u
2. required verification mora odgovarati trenutnom code/contract snapshotu
```

Time FlowOS dobija dvije provjerljive osobine koje postojeći v5 još nema dovoljno rano:

> **agent ne može samo tvrditi da je ostao u scope-u — Git to provjerava.**

> **zeleni test ne može ostati “current VERIFIED” nakon što se kod promijenio — freshness gate to provjerava.**

Sve ostalo iz ove dopune služi da ta dva pravila imaju jasan evidence, machine-readable handoff i praktičnu upotrebu sa eksternim agentima bez promjene FlowOS identiteta.
