# Prijedlozi za unapređenje sadašnjeg načina rada prije punog FlowOS-a

## Svrha

Ovaj dokument ne opisuje budući FlowOS niti novu arhitekturu.

Cilj je da odmah poboljša postojeći način rada sa:

- Claude Code
- Codex
- Pi
- Crush
- GitNexus
- Git worktreeovima
- Task Contractima
- agent reportima
- nezavisnim reviewom

Osnovni princip:

> Ne čekati da FlowOS implementira pravila koja već sada možemo primjenjivati ručno ili kroz male determinističke skripte.

---

# 1. Operating Level prije svakog ozbiljnijeg Taska

Prije implementacije odrediti koliko duboko agent treba da ide.

Predložena tri nivoa:

```text
LEAN
- poznat problem
- poznat subsystem
- mali scope
- dobri postojeći testovi

NORMAL
- feature ili bug koji dira više dijelova
- potreban impact pregled
- nekoliko relevantnih fajlova/modula

DEEP
- nepoznat subsystem
- arhitektura ili veći refaktor
- DB/schema
- security
- performance
- slab ili kontradiktoran evidence
```

Praktično:

```text
LEAN
→ Task Contract
→ relevantni fajlovi
→ test
→ implementacija

NORMAL
→ Task Contract
→ GitNexus impact
→ relevantni modul/testovi
→ implementacija
→ nezavisni review

DEEP
→ source audit
→ arhitektura/dependency pregled
→ pretpostavke i rizici
→ plan
→ implementacija tek nakon razumijevanja
```

Pravilo:

> Idi na viši nivo apstrakcije kada je sistem dovoljno poznat i dokaziv. Spusti se niže kada je domen nepoznat, rizik visok ili evidence slab.

MOVE DOWN ne znači ručno programiranje. Znači da čovjek i agent rade na nižem nivou: repo → modul → fajl → tip → funkcija → konkretan execution path.

---

# 2. Prime Context umjesto velikog zajedničkog konteksta

Svaki agent ne treba automatski dobijati cijeli projekat, stare planove i sve izvještaje.

Za svaki tip posla koristiti mali context profile.

Primjeri:

```text
BUG PROFILE
- Task Contract
- pogođeni source
- relevantni test
- stack trace/log
- GitNexus impact za pogođeni simbol

FEATURE PROFILE
- Task Contract
- acceptance criteria
- relevantni modul
- susjedni contracts/types
- relevantni testovi

REVIEW PROFILE
- Task Contract
- Git diff
- relevantni source
- relevantni testovi
- verification rezultat

ARCHITECTURE PROFILE
- Task Contract
- architecture docs
- dependency/impact analiza
- ključni moduli
- postojeći constraints
```

Ne učitavati unaprijed:

```text
- cijeli docs/
- sve stare planove
- nepovezane agent_reports
- punu istoriju projekta
- sve memorijske fajlove
```

Princip:

> Agent treba dobiti najmanji kontekst dovoljan da pouzdano završi zadatak.

---

# 3. Context Bundle / Fresh Handoff

Nakon implementacije napraviti kratak strukturisan handoff umjesto predavanja cijele istorije prethodne sesije.

Minimalni sadržaj:

```text
Task
branch/worktree
current status
changed files
git diff reference
verification rezultat
važne odluke
poznati rizik
šta nije provjereno
sljedeći korak
```

Primjer:

```markdown
## HANDOFF

Task:
FLOW-XXXX

State:
IMPLEMENTATION_COMPLETE
VERIFICATION_PENDING

Changed:
- src/...
- tests/...

Verification:
- pytest tests/... → PASS

Important decision:
- ...

Known risk:
- ...

Not verified:
- ...

Next:
- fresh Codex review
```

Cilj:

> Sljedeći agent dobija trenutno stanje rada, ne reasoning istoriju prethodnog agenta.

---

# 4. Fresh verifier mora biti stvarno nezavisan

Implementatorov izvještaj služi revieweru za navigaciju, ne kao dokaz da je implementacija dobra.

Reviewer standardno dobija:

```text
Task Contract
+
acceptance criteria
+
Git diff
+
relevantni source
+
relevantne testove
+
kratak handoff
```

Ne treba mu automatski davati:

```text
- implementatorov reasoning
- dugo objašnjenje zašto implementator misli da je rješenje dobro
- njegovu interpretaciju spornih dijelova kao činjenicu
```

Reviewer treba sam provjeriti kod.

Pravilo:

> Implementer objašnjava šta je radio. Reviewer samostalno utvrđuje da li je to ispravno.

---

# 5. Obavezni Scope Gate prije reviewa

Task Contract već definiše šta agent smije mijenjati.

Na kraju implementacije uvijek provjeriti stvarni Git diff:

```bash
git diff --name-only <base>...HEAD
```

Zatim porediti sa:

```text
allowed_paths
forbidden_paths
```

Pravilo:

```text
AgentReport.changed_files = CLAIM
Git changed paths          = SOURCE FACT
```

Ako agent kaže da je promijenio dva fajla, a Git pokazuje tri, Git je authority.

Obavezno provjeriti:

```text
actual_changed_paths ⊆ allowed_paths
actual_changed_paths ∩ forbidden_paths = ∅
```

Ako nije:

```text
SCOPE VIOLATION
→ review se zaustavlja
→ ili se kod vraća u scope
→ ili čovjek eksplicitno mijenja Task Contract
```

Ne raditi automatski rollback.

---

# 6. Verification Freshness kao tvrdo pravilo

Zeleni test vrijedi samo za kod koji je postojao kada je test pokrenut.

Primjer:

```text
implementacija
→ pytest PASS
→ Codex nađe problem
→ Pi popravi kod
```

Prethodni `pytest PASS` više nije dokaz za novi kod.

Pravilo:

> Svaka relevantna promjena koda nakon posljednjeg GREEN verificationa poništava taj GREEN za trenutni snapshot.

Tok treba biti:

```text
implementacija
→ verify
→ review
→ fix
→ verify ponovo
→ re-review gdje je potreban
→ human acceptance
```

Ovo pravilo treba primjenjivati odmah, bez čekanja FlowOS-a.

---

# 7. Testovi i verifieri su review-sensitive fajlovi

Ako je Task:

```text
popravi production kod
```

a agent mijenja:

```text
tests/
scripts/verify.py
architecture guards
CI konfiguraciju
```

to zahtijeva dodatnu pažnju.

Promjena nije automatski pogrešna, ali agent ne smije neprimjetno mijenjati ono što ga provjerava.

Pravila:

```text
- verifier/test van allowed_paths → scope violation
- verifier/test unutar allowed_paths → dozvoljeno, ali zahtijeva dodatni review
- prethodni verification postaje stale ako je relevantni verifier promijenjen
```

Za bugfix ili guard promjenu koristiti adversarial proof:

```text
novi test + stari bug
→ MORA FAIL

novi test + novi kod
→ MORA PASS
```

---

# 8. Skills samo za dokazane ponovljive obrasce

Kada se isti postupak ponavlja i pokazao se dobrim, pretvoriti ga u skill.

Dobri kandidati:

```text
bug investigation
architecture review
parser creation
PySide View/Controller/Service review
adversarial regression verification
GitHub PR review
Task Contract preparation
```

Ne uvoditi skill samo zato što je nešto urađeno jednom.

Pravilo:

```text
ponavljanje
→ stabilna procedura
→ dokazano radi
→ skill
```

Ne:

```text
jedan uspješan zadatak
→ novi framework
```

---

# 9. Multi-model / Fusion koristiti selektivno

Ne treba Claude, Codex, Pi i Crush da nezavisno rješavaju svaki mali bug.

Fusion ima smisla kada postoji stvarna neizvjesnost:

```text
- velika arhitektonska odluka
- ozbiljan refaktor
- izbor između dvije tehničke strategije
- Claude i Codex daju suprotne zaključke
- premortem / red-team
- problem sa visokim rizikom
```

Tok:

```text
Claude → nezavisna analiza
Codex  → nezavisna analiza
eventualno treći model
        ↓
uporediti razlike
        ↓
čovjek odlučuje
```

Za običnu implementaciju koristiti jednog implementatora i nezavisnog reviewera.

---

# 10. Mali deterministički `verify_task` alat prije FlowOS-a

Prije nego FlowOS implementira sve gateove, može se napraviti mali lokalni alat:

```text
verify_task TASK-ID
```

Bez LLM-a.

Minimalno bi radio:

```text
1. pročitaj Task Contract
2. utvrdi base/current Git snapshot
3. izvuci changed files
4. provjeri allowed/forbidden scope
5. pokreni verification_commands
6. zapiši exit code i snapshot
7. napravi mali verification report
```

Primjer rezultata:

```text
TASK: FLOW-XXXX
SNAPSHOT: abc123

Scope:
PASS

Verification:
pytest tests/unit/test_x.py
exit: 0
PASS

Freshness:
CURRENT
```

Ovo je dobar kandidat za ranu automatizaciju jer je determinističko i ne zahtijeva inteligenciju modela.

---

# 11. Šta ne mijenjati u sadašnjem workflowu

Zadržati:

```text
- čovjek je konačni acceptance authority
- implementer != reviewer
- Codex/Claude rade nezavisni review
- reviewer čita stvarni kod
- worktrees izoluju paralelni rad
- file claims sprečavaju kolizije
- poslije mergea ide nova provjera na main
- agent_reports ostavljaju trajni trag
```

Ne uvoditi sada:

```text
- veliki centralni multi-agent orchestrator
- automatsko agent-to-agent dopisivanje
- model router za svaki Task
- software factory za male zadatke
- automatski retry agent loop bez jasnog verifiera
```

---

# 12. Redoslijed primjene

## Odmah

```text
D1 — Operating Level: LEAN / NORMAL / DEEP
D2 — Prime Context po tipu zadatka
D3 — Fresh Handoff / Context Bundle
D4 — eksplicitni Git Scope Gate
D5 — Verification Freshness
```

Ovih pet ne zahtijevaju novu infrastrukturu.

## Nakon toga

```text
D6 — review-sensitive verifier/test policy
D7 — standardni reusable skills
D8 — selektivni multi-model review/fusion
```

## Mali alat

```text
D9 — verify_task deterministička skripta
```

Tek nakon dovoljno stvarnih zadataka procijeniti koje dijelove vrijedi formalno preseliti u FlowOS.

---

# Završni princip

Sadašnji workflow ne treba pokušavati odmah pretvoriti u software factory.

Prvo treba učiniti postojeći način rada:

```text
jasnijim
→ ograničenijim
→ provjerljivijim
→ ponovljivijim
```

Tek ono što se kroz stvarne zadatke pokaže stabilnim i korisnim treba automatizovati i kasnije formalizovati u FlowOS-u.

Najvažnija praktična pravila su:

> **Agent dobija samo potreban kontekst.**

> **Git, test i stvarni artefakti imaju veću dokaznu vrijednost od agentove tvrdnje.**

> **Svaka izmjena poslije GREEN verificationa zahtijeva novi relevantni verification.**

> **Veći leverage koristi se tek kada razumijevanje i dokazivost to dozvoljavaju.**
