# Kako radim — stvarni radni tok sa AI modelima i agentima

**Namjena:** ovaj dokument opisuje moj stvarni način rada kada razvijam softver uz pomoć više AI modela i agenata: kako dijelim uloge, kako definišem zadatak, kako radim paralelno bez sudara, kako dokazujem da promjena stvarno radi, kako nezavisno pregledam rezultat, kako prenosim kontekst između sesija i modela, i gdje čovjek zadržava konačnu kontrolu.

Dokument nije generički AI workflow i nije marketinški opis. To je lični, praktični opis procesa koji je nastajao kroz stvaran rad, uključujući greške i lekcije iz njih.

---

## 1. Filozofija u jednoj rečenici

> **Ništa se ne prihvata na riječ — svaka tvrdnja da nešto radi, da su testovi prošli ili da je zadatak gotov mora imati dokaz koji se može nezavisno provjeriti prije prihvatanja i integracije.**

Još kraće:

> **Model radi. Dokaz potvrđuje. Nezavisni reviewer pokušava oboriti rezultat. Čovjek odlučuje.**

Ovaj pristup je namjerno disciplinovaniji od „daj agentu feature i vjeruj mu“. AI agenti mogu riješiti veoma složene probleme, ali i dalje mogu:

- pogrešno razumjeti zahtjev;
- implementirati ispravan rezultat na pogrešan način;
- napisati test koji zapravo ništa ne štiti;
- propustiti rubni slučaj;
- prešutno proširiti scope;
- zaključiti da je nešto završeno samo zato što njihov vlastiti test prolazi;
- dati uvjerljiv izvještaj koji nije u skladu sa stvarnim Git stanjem.

Zato se proces ne zasniva na povjerenju u agenta nego na **provjerljivom evidenceu**.

---

## 2. Uloge su stabilne, modeli su zamjenjivi

Najvažnija stvar u mom načinu rada nije koji model koristim, nego **koju ulogu taj agent ima u tom trenutku**.

Osnovne uloge su:

| Uloga | Odgovornost |
|---|---|
| **Ja — human authority** | Definišem cilj, prioritet, scope i konačnu odluku. Odobravam rizične promjene i integraciju. |
| **Planner / coordinator** | Razjašnjava problem, istražuje repo, piše Task Contract, definiše acceptance i razbija rad na pregledive korake. |
| **Implementer** | Piše stvarni kod unutar dozvoljenog scope-a i proizvodi evidence. |
| **Reviewer** | Nezavisno čita stvarni diff/kod i traži greške koje implementer možda nije vidio. |
| **Verifier** | Pokreće objektivne provjere i pokušava dokazati da test/evidence zaista nešto dokazuje. |
| **Integrator** | Tek nakon odobrenja priprema merge/push i potvrđuje stanje na ciljnoj grani. |

### Kako to trenutno izgleda u praksi

Najčešće:

- **Claude Code** koristim kao planner/coordinator i dubinskog arhitektonskog reviewera;
- **Crush** ili **Pi** kao precizne implementatore za jasno ograničene taskove;
- **Codex** kao nezavisnog, adversarial reviewera, posebno za test kvalitet, blast radius i pokušaje da se nova zaštita „prevari“;
- ja ostajem konačni authority.

Ali ovo nije tvrda veza:

```text
Claude ≠ zauvijek planner
Codex ≠ zauvijek reviewer
Crush/Pi ≠ zauvijek implementer
```

Model je zamjenjiv. **Proces i uloge moraju preživjeti promjenu modela.**

To je važno i iz praktičnog razloga: različiti modeli imaju različite jačine, cijene i ponašanja, ali projekt ne smije izgubiti smisao kada promijenim model ili harness.

---

## 3. Zašto koristim više modela umjesto jednog „superagenta“

Ne koristim više modela samo zato što mogu.

Glavna vrijednost je **nezavisnost perspektive**.

Ako isti agent:

```text
napiše plan
→ implementira plan
→ napiše test
→ pregleda vlastiti kod
→ zaključi da je sve dobro
```

onda postoji veliki rizik self-confirmationa. Agent koji je već izabrao određenu putanju prirodno je sklon da nastavi braniti tu putanju.

Zato preferiram:

```text
Agent A implementira
        ↓
Agent B pokušava oboriti rezultat
        ↓
Agent C ili čovjek provjerava drugi aspekt
        ↓
Ja odlučujem da li prihvatam
```

Ne mora svaki mali task imati dva puna review kruga. Dubina reviewa zavisi od:

- rizika;
- blast radiusa;
- širine diffa;
- kvaliteta verifikacije;
- security/DB/architecture uticaja;
- reverzibilnosti promjene.

Za mali, lokalni i lako reverzibilan fix dovoljan je lakši tok. Za security, persistence, migration ili arhitektonsku promjenu review je namjerno dublji i nezavisniji.

---

## 4. Alati — šta stvarno koristim

### Osnovni razvojni alati

- **Git / GitHub** — verzionisanje, stvarni dokaz diffa, commita i stanja grane.
- **Git worktree** — fizička izolacija paralelnog agentskog rada.
- **Terminal (PowerShell/Bash)** — Git, testovi, verifikacija, agent CLI alati.
- **VS Code** — glavno razvojno okruženje.

### Vlastiti pomoćni alati

#### `coordination.py`

Registar zauzeća fajlova. Prije početka rada agent deklarativno rezerviše planirane fajlove. Ako drugi paralelni task želi isti fajl, konflikt se vidi prije implementacije.

Ovo nije potpuna zaštita od svih konflikata, ali uklanja najopasniju klasu: dva writera nad istim fajlom.

#### `agent_sensors.py`

Deterministički senzori za poznate klase arhitektonskih grešaka.

Ideja je nastala iz stvarnog rada: kada reviewer dva puta na različitim taskovima pronađe isti tip greške, više nema smisla očekivati da je čovjek ili AI ručno hvata treći put.

Tada pokušavam pretvoriti:

```text
ponovljeni manual finding
        ↓
poznata kategorija greške
        ↓
pytest / architecture test / static rule / sensor
        ↓
budući agent dobija automatski feedback
```

To je jedan od ključnih principa procesa: **ručno naučena lekcija treba, gdje je moguće, postati deterministička zaštita.**

### Standardna verifikacija

- **pytest** — ponašajni i regresioni testovi;
- **ruff** — stil i statička provjera;
- **mypy** — type safety;
- project-specific `verify.py` — objedinjeni reproducibilni verification tok gdje postoji.

### GitNexus

Koristim ga kao graf znanja nad kodom kada treba:

- blast-radius analiza;
- ko poziva funkciju i koga ona poziva;
- pronaći veze između API-ja, modela i klijenata;
- razumjeti veći/nepoznat dio repoa;
- procijeniti rizik refactora ili rename-a.

Ako je task već potpuno bounded i dolazi sa preciznim fajlovima, testovima i call pathom, GitNexus je manje potreban.

### Skills

Skill je unaprijed definisana procedura za ponovljiv tip posla, npr.:

- bug reproduction;
- code review;
- impact check;
- verification;
- dokumentovanje;
- određeni tip implementacije.

Princip:

> **Skills encode the method; projektni state i evidence ostaju odvojeni od metode.**

---

## 5. Task Contract — šta se zaključava prije koda

Za netrivijalan zadatak prije implementacije pišem **Task Contract**.

On tipično sadrži:

- cilj;
- zašto task postoji;
- dozvoljeni scope;
- out-of-scope;
- relevantne fajlove;
- acceptance / Definition of Done;
- testove ili komande koje moraju proći;
- rizike;
- po potrebi predloženu implementacionu putanju.

Ali ovdje postoji važna nijansa:

> **Task Contract zaključava namjeru i granice, ne tvrdi da je čovjekov tehnički recept nepogrešiv.**

### Authority boundary

Agent ne smije sam promijeniti:

```text
goal
scope / out-of-scope
acceptance kriterije
security/risk odluku
human-approved architecture boundary
```

### Implementation assumption

Predloženi:

```text
fajl
konkretna helper funkcija
signature
call path
tehnički recept
```

može se pokazati pogrešnim tek kada se kod pokrene ili testira.

Ako implementer reproducibilno dokaže da je takva pretpostavka pogrešna, dozvoljen je **evidence-backed contract deviation** samo ako:

```text
isti goal
isti scope
isti acceptance
risk nije povećan
odstupanje je eksplicitno dokumentovano
postoji dokaz zašto originalni pristup ne radi
```

Ako odstupanje mijenja arhitekturu, scope, risk ili business ponašanje:

```text
STOP
→ vrati meni odluku
→ tek onda nastavak
```

To je važna razlika između zdravog tehničkog prilagođavanja i tihog scope drifta.

---

## 6. Program Design prije većeg implementationa

Za veće ili rizičnije taskove ne idem odmah iz zahtjeva u kod.

Prvo pokušavam zaključati nekoliko jeftinih odluka dok još nema velikog diffa:

```text
Koji fajlovi se mijenjaju?
Koji tipovi/signature nastaju?
Kako izgleda call/data flow?
Koji testovi dokazuju ponašanje?
Koje odluke su najmanje sigurne?
Može li se posao razbiti na vertikalne sliceove?
```

Razlog je jednostavan: odluku je mnogo jeftinije promijeniti dok je još tekst u planu nego poslije 800–2000 linija novog koda.

Ne radim ovo za svaki trivialni tweak. Dubina planiranja je proporcionalna riziku.

---

## 7. Pisani trag — ništa važno ne živi samo u chatu

Conversation history je privremena.

Ako fresh agent mora znati neku činjenicu da bi nastavio ispravno, ta činjenica ne smije postojati samo u starom razgovoru.

Trajni trag trenutno čine:

1. **Task Contract / specifikacija** — prije koda;
2. **implementation report** — šta je stvarno promijenjeno i koji evidence postoji;
3. **review reporti** — nezavisni nalazi i verdikt;
4. **Git history** — stvarni kod, diff i commitovi;
5. projektna dokumentacija / ADR-ovi — trajne odluke i pravila.

U `agent_reports/` ostaju Markdown izvještaji tako da se kasnije može rekonstruisati:

```text
šta smo pokušali
zašto
ko je implementirao
šta je dokazano
šta je reviewer pronašao
šta je popravljeno
zašto je rezultat prihvaćen
```

Agent report nije automatski istina. On je **claim + evidence container**.

---

## 8. Kako prenosim kontekst između agenata i modela

Ne pokušavam novom agentu dati cijeli stari chat.

Bolji handoff je mali i eksplicitan:

```text
Goal
Current state
Relevant files
Constraints
Definition of Done
Checks to run
References
```

Po potrebi dodam:

- posljednje važeće odluke;
- aktivne nalaze;
- poznat propali pristup koji ne treba ponavljati;
- branch/worktree/base commit.

Mentalni model je:

```text
MODEL = zamjenjiv
HARNESS = zamjenjiv
SESSION = privremena

PROJECT RULES + CURRENT STATE + DECISIONS + EVIDENCE
= moraju preživjeti sve njih
```

Zato je granica Taska ili završeni checkpoint prirodno mjesto za promjenu modela/sessiona.

---

## 9. Pun tok jednog zadatka

Tipičan netrivijalan task izgleda ovako:

```text
1.  Pojavi se potreba: plan, bug, review nalaz ili moj zahtjev.
2.  Planner/Claude istraži relevantni kod i napiše Task Contract.
3.  Ako je task rizičan: Program Design / blast-radius / test plan.
4.  Provjeri se moguć paralelizam i rezervišu planirani fajlovi.
5.  Kreira se izolovan branch/worktree.
6.  Implementer (često Crush/Pi) piše kod unutar scope-a.
7.  Implementer pokreće targeted testove i piše evidence/report.
8.  Provjeravam stvarni diff/Git state — ne samo agentov opis.
9.  Nezavisni reviewer čita stvarni kod i pokušava pronaći kvar.
10. Po potrebi drugi reviewer/verifier provjerava drugi aspekt.
11. Ako postoji finding: ide uski fix → re-review.
12. Ja dajem konačnu odluku o prihvatanju.
13. Tek zatim ide commit/integration korak prema dogovorenoj politici.
14. Na ciljnoj/main grani ponovo se pokreće relevantna verifikacija.
15. Potvrđuje se Git/remote stanje i zatvara se radni scope.
```

Za mali, niskorizični task neke faze se mogu skratiti. Za HIGH/security/persistence/architecture task review i verification se pojačavaju.

---

## 10. Pet različitih „zelenih svjetala“

Jedna od stvari koje namjerno ne miješam je značenje riječi „gotovo“.

Postoji najmanje pet različitih stvari:

```text
IMPLEMENTIRANO
→ kod postoji

TESTIRANO / VERIFIKOVANO
→ postoje objektivni dokazi

REVIEWANO
→ nezavisna osoba/model je pokušao pronaći problem

PRIHVAĆENO
→ ja prihvatam rezultat i trade-off

INTEGRISANO
→ promjena je stvarno spojena u target/main
```

I nakon integracije postoji još jedna provjera:

```text
main + drugi integrisani rad
→ ponovni test
```

jer dva potpuno ispravna taska na dvije izolovane grane mogu zajedno napraviti problem.

Zato:

> **Commit nije acceptance. Review nije acceptance. Acceptance nije merge. Merge nije dokaz da integrisana cjelina radi.**

---

## 11. Kako radim paralelno bez sudaranja

### Prvi nivo: write overlap

Provjerava se da li se `allowed_paths` / planirani changed-files skupovi preklapaju.

Ako se preklapaju, taskovi se uglavnom ne puštaju paralelno ili se redefiniše granica posla.

### Drugi nivo: worktree izolacija

Čak i kada nema overlap-a, svaki writer radi u svom worktreeju, tako da ne dijele isti fizički working tree.

### Treći nivo: dependency i assumption conflict

Naučena važna lekcija:

> **Nulto preklapanje fajlova ne znači da su taskovi stvarno nezavisni.**

Primjer:

```text
Task A mijenja module.py

Task B mijenja samo test_module_contract.py
ali taj test pretpostavlja staro ponašanje module.py
```

Nema write overlapa, ali Task A može invalidirati pretpostavku Taska B.

Zato razlikujem najmanje:

```text
WRITE CONFLICT
DEPENDENCY CONFLICT
STALE-BASE CONFLICT
ASSUMPTION CONFLICT
```

Trenutno se dio ovoga provjerava ručno kroz razumijevanje dependencyja, GitNexus, imports i review. Dugoročno je to jedna od stvari koje FlowOS treba pomoći detektovati.

---

## 12. Regression Proof — test mora dokazati da hvata problem

Test koji samo prolazi poslije fixa nije uvijek dovoljan.

Ako je cilj zadatka promijeniti arhitektonski put ili popraviti regresiju, snažniji dokaz je:

```text
STARI / POGREŠNI KOD
+ NOVI TEST
→ FAIL

NOVI / ISPRAVNI KOD
+ ISTI TEST
→ PASS
```

Tako dokazujem da test stvarno razlikuje staro loše ponašanje od novog dobrog ponašanja.

Ovo je posebno važno kada test može slučajno provjeriti samo krajnji rezultat, a ne put kojim se do njega došlo.

---

## 13. Historical replay mora biti read-only

Ovo pravilo je nastalo iz stvarne greške.

Tokom jedne adversarial provjere korištena je Git komanda za vraćanje privremene test-mutacije. Pošto implementerov rad tada još nije bio commitovan, operacija je izbrisala i pravi necommitovani rad.

Rad je srećom rekonstruisan iz ranije pročitanog diffa i byte-identično potvrđen, ali lekcija je jasna:

> **Reviewer/verifier ne smije mijenjati aktivni implementation worktree samo da bi rekonstruisao istorijsko/pre-change stanje.**

Za historical replay koristim:

```text
git show
git ls-tree
git cat-file
```

ili zaseban privremeni/detached worktree.

Izbjegavam historical:

```text
git checkout
git reset
git restore
```

nad treejem koji može sadržavati necommitovan rad druge sesije.

Ovo je posebno važno za Regression Proof i budući Managed Execution.

---

## 14. Kako tretiram grešku u samom procesu

Greške ne krijem samo zato što nisu završile u finalnom kodu.

Ako agent ili ja napravimo proceduralnu grešku:

```text
1. odmah priznati šta se desilo;
2. zaustaviti normalan tok;
3. utvrditi stvarno stanje;
4. vratiti/rekonstruisati podatke ako je potrebno;
5. nezavisno provjeriti da je recovery tačan;
6. tek onda nastaviti;
7. iz incidenta izvući trajno pravilo ili guard ako vrijedi.
```

To je dio evidence-first kulture: proces nije vjerodostojan ako skriva vlastite greške.

---

## 15. Kako proces uči — Finding → Guard

Jedna od najvažnijih stvari koje su se razvile organski je pretvaranje ponovljenih review nalaza u automatske zaštite.

Praktično pravilo:

> **Ako se ista kategorija materijalnog nalaza pojavi na dva nezavisna taska, to je signal da možda više nije incident nego obrazac.**

Tada razmatram:

```text
regression test
architecture test
lint/static rule
agent sensor
verify rule
repo guideline
reusable skill
poseban refactor task
```

Ali se ništa ne automatizuje samo zato što se pojavilo dva puta. Dva slučaja su **signal za razmatranje**, ne automatski authority.

Ovo je vrlo bitan dio mog pristupa jer tako manualni review postepeno postaje sistemska zaštita.

---

## 16. Kako biram koji model dobija koji zadatak

Ne biram model samo po cijeni tokena ili benchmarku.

Gledam oblik taska.

Dobar kandidat za užeg/jeftinijeg workera:

```text
jasan cilj
jasan scope
jasni allowed paths
jasan DoD
jaki objektivni testovi
mali hidden-state rizik
```

Zadatak za jači model / više ljudskog nadzora:

```text
root-cause investigation
konfliktni dokazi
arhitektonska odluka
slab verifier
velik blast radius
security/DB/migration rizik
nejasan scope
```

Pravi trošak nije samo cijena modela:

```text
model cost
+ context transfer
+ retries
+ failed attempts
+ review time
+ verification
+ rework
```

Zato skuplji model ponekad bude jeftiniji po stvarno prihvaćenom tasku.

---

## 17. Šta namjerno NE prepuštam AI-u

AI ne dobija finalni authority nad:

- poslovnim ciljem;
- scope promjenom;
- acceptance kriterijima;
- prihvatanjem security/risk trade-offa;
- finalnom task odlukom;
- integracijom u protected target;
- odlukom da je contradicting evidence „nebitan“.

Agent može predložiti.

FlowOS ili Git/test može deterministički utvrditi činjenice.

Ali kada je potrebna vrijednosna, produktna ili rizična odluka — ja odlučujem.

---

## 18. Šta FlowOS treba automatizovati iz ovog procesa

Danas veliki dio ovog operating modela još koordiniram ručno kroz chat, terminal, Git, worktree i report fajlove.

FlowOS gradim upravo zato da automatizuje **mehanički dio**, ne da preuzme authority.

FlowOS treba da sam poveže:

```text
Plan / Task
Agent Session
Worktree / branch
Git diff
Verification evidence
AgentReport
Independent review
Finding / fix
Human decision
```

i da čovjeku odgovori:

```text
Šta trenutno važi?
Ko radi šta?
Šta se stvarno promijenilo?
Šta je dokazano?
Šta još nije dokazano?
Koji finding je otvoren?
Gdje sam stao?
Šta zahtijeva moju odluku?
```

Drugim riječima:

> **Ne želim da FlowOS izmisli novi proces. Želim da pouzdano razumije, prati i olakša proces koji već koristim.**

---

## 19. Kako bih ovo objasnio nekome za 30 sekundi

> Koristim više AI agenata sa jasno odvojenim ulogama. Jedan može pomoći da precizno definišemo problem, drugi implementira, a drugi nezavisno pokušava oboriti rezultat. Git, testovi i stvarni kod imaju veći autoritet od onoga što agent kaže da je uradio. Za rizične promjene tražim reproducibilan dokaz, a često i da novi regression test padne na starom kodu i prođe na novom. Paralelan rad izolujem worktree-jima i ograničenim scope-om. Ako se ista vrsta greške ponovi, pokušavam je pretvoriti u deterministički guard da je više ne lovimo ručno. AI odlučuje kako da izvrši jasno ograničen tehnički zadatak; ja zadržavam cilj, scope, rizik i konačno prihvatanje.

---

## 20. Kako bih ovo objasnio CTO-u ili engineering manageru

> Moj pristup nije „više agenata = više produktivnosti“. Tretiram modele kao zamjenjive executore unutar kontrolisanog engineering procesa. Rad se razlaže u bounded taskove, implementer i reviewer su odvojeni, svaki task ostavlja trajni evidence, paralelni writeri su izolovani worktree-jima, a acceptance je odvojen od implementacije i testova. Najvažnije, pokušavam ponovljene ljudske review nalaze pretvoriti u determinističke guardove, tako da sistem s vremenom postaje sigurniji umjesto da samo generiše više koda. FlowOS gradim kao human control plane koji će taj proces učiniti vidljivim, dokazivim i prenosivim između agenata bez davanja AI-u finalnog authority-ja.

---

## 21. Kako bih ovo objasnio tehnički, bez marketinga

```text
Intent / Task Contract
        ↓
Bounded implementation scope
        ↓
Isolated worktree
        ↓
Implementation + reproducible evidence
        ↓
Independent adversarial review
        ↓
Finding → narrow fix → re-review
        ↓
Human acceptance
        ↓
Integration
        ↓
Post-integration verification
```

Stabilna pravila i odluke ostaju u repou/evidenceu. Session je privremena. Model je zamjenjiv. Git i verification daju objektivne činjenice. Human ostaje authority za ono što se ne može deterministički zaključiti.

---

## 22. Najvažniji principi koje bih branio kao dio ovog načina rada

1. **Evidence over assertion** — agentovo „gotovo“ nije dokaz.
2. **Implementer ≠ jedini reviewer.**
3. **Human authority ostaje za goal/scope/risk/acceptance.**
4. **Git je dokaz stanja koda, ne dokaz poslovne ispravnosti.**
5. **Commit ≠ acceptance ≠ integration.**
6. **Task, Session, Worktree i Decision nisu ista stvar.**
7. **Model je zamjenjiv; durable context mora preživjeti session.**
8. **Nema paralelnog writera bez izolacije i prethodne conflict provjere.**
9. **Nema historical replaya koji mutira aktivni implementation worktree.**
10. **Test mora dokazivati relevantnu osobinu, ne samo slučajno prolaziti.**
11. **Ponovljeni finding treba, gdje ima smisla, pretvoriti u deterministic guard.**
12. **Proces se prilagođava riziku — ne uvoditi punu ceremoniju za svaki trivijalni tweak.**
13. **Greška u procesu se priznaje i postaje input za poboljšanje procesa.**
14. **Ne optimizujem za broj agenata ili tokena nego za pouzdano prihvaćen rezultat po jedinici ljudske pažnje.**

---

## 23. Razlika između ovog dokumenta i generičkog blueprinta

Ovaj fajl opisuje **moj stvarni rad**, sa konkretnim alatima i obrascima koje zaista koristim.

Nije univerzalni recept i nije dokaz da svaki tim treba identičan broj reviewera, iste modele ili isti tooling.

Generički blueprint treba izvući samo prenosive principe:

```text
role separation
evidence-first
bounded scope
independent review
human authority
isolated execution
portable handoff
repeat-finding → guard
risk-based depth
```

Ovdje, nasuprot tome, ostaju i stvarni alati:

```text
Claude Code
Codex
Crush
Pi
Git/GitHub
worktrees
coordination.py
agent_sensors.py
GitNexus
pytest / ruff / mypy
FlowOS
```

---

## 24. Konačna formulacija

Najpreciznije:

> **Radim sa više AI modela kao sa timom specijalizovanih, zamjenjivih izvršilaca unutar evidence-first engineering procesa. Svaki netrivijalan posao ima jasan cilj i scope, implementaciju odvojenu od reviewa, reproducibilne provjere, izolovan Git/worktree kontekst i trajni pisani trag. Model može birati kako da riješi bounded tehnički problem, ali ne može tiho promijeniti poslovni cilj, scope, risk ili finalnu odluku. Kada se ista greška ponavlja, pokušavam je pretvoriti u deterministički guard. FlowOS gradim da taj proces automatski poveže i učini vidljivim, bez oduzimanja konačne kontrole čovjeku.**

Najkraće:

> **Modeli rade. Evidence gradi povjerenje. Nezavisni review pokušava oboriti rezultat. Čovjek odlučuje.**
