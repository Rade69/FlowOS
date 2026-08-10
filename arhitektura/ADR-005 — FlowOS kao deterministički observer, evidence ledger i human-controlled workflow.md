# ADR-005 — FlowOS kao deterministički observer, evidence ledger i human-controlled workflow

**Status:** Accepted  
**Datum:** 2026-08-09

## 1. Kontekst

FlowOS je prvobitno zamišljen kao lični alat za praćenje rada više AI coding agenata tokom realizacije unaprijed pripremljenog razvojnog plana.

Tokom razrade arhitekture pojavila se mogućnost da FlowOS preraste u sistem koji sam pokreće, raspoređuje i kontroliše agente. Takav pravac je tehnički moguć, ali bi nepotrebno povećao kompleksnost i udaljio projekat od osnovnog problema koji FlowOS treba da riješi.

Korisnik već ima funkcionalan razvojni workflow:

- Claude Code uglavnom kroz VSCode ekstenziju;
- Codex uglavnom kroz VSCode ekstenziju;
- Pi kroz CLI/terminal;
- Crush kroz CLI/terminal;
- korisnik neposredno prati njihov rad i aktivno učestvuje u razvoju;
- detaljni planovi se pripremaju prije početka implementacije;
- agenti nakon sesija ostavljaju izvještaje u projektnom `agent_reports` direktorijumu;
- kod jednog agenta poželjno je pregledati drugim agentom;
- konačnu procjenu funkcionalnosti vrši korisnik kroz stvarno pokretanje i korištenje aplikacije.

FlowOS zato ne treba da zamijeni postojeći workflow, nego da ga objedini, prati i dokumentuje.

---

# 2. Osnovna odluka

FlowOS je prvenstveno:

> **lokalni, deterministički kontrolni i evidencioni sistem koji prati kompletan razvoj projekta i povezuje rad korisnika i AI agenata sa unaprijed definisanim planom, taskovima, Git stanjem, izvještajima, reviewima i korisničkim odlukama.**

FlowOS nije AI manager.

FlowOS ne koristi LLM da bi odlučivao:

- šta treba implementirati;
- koji je task završen;
- da li je implementacija dobra;
- da li je finding validan;
- da li se plan treba promijeniti;
- koji reviewer mora biti korišten;
- da li se kod smije prihvatiti.

Kada je potrebna semantička, produktna ili arhitektonska procjena, kontrola pripada korisniku.

FlowOS automatizuje samo ono što se može pouzdano zaključiti iz strukturiranih podataka, događaja i unaprijed definisanih pravila.

---

# 3. Personal-first, product-capable

FlowOS se razvija prvenstveno za stvarni workflow jednog developera.

Ne uvode se unaprijed funkcionalnosti potrebne samo za potencijalni budući SaaS ili timski proizvod, kao što su:

- organizacije;
- timovi;
- cloud sinhronizacija;
- billing;
- role-based permissions;
- multi-user collaboration.

Arhitektura ipak ne treba nepotrebno zatvoriti mogućnost da FlowOS kasnije postane proizvod za druge developere sa sličnim multi-agent workflowom.

Princip je:

> **Personal-first, product-capable.**

---

# 4. Planiranje se odvija prije FlowOS-a

FlowOS nije prvenstveno alat za AI generisanje plana.

Detaljna analiza, arhitektonske odluke, ADR-ovi, specifikacije i razlaganje rada na dovoljno male i jasne taskove mogu biti urađeni prije uvoza projekta u FlowOS.

Tipičan tok je:

```text
Korisnik + alat za strateško planiranje
        ↓
analiza problema
        ↓
ADR / odluke
        ↓
detaljan plan
        ↓
jasni taskovi i acceptance kriterijumi
        ↓
──────── granica ────────
        ↓
FlowOS
        ↓
realizacija i evidencija
```

FlowOS ne koristi interni model da ponovo razlaže već dovoljno dobro definisane taskove.

Ako plan već sadrži:

- task ID;
- opis;
- cilj;
- acceptance kriterijume;
- zavisnosti;
- relevantne ADR-ove;
- ograničenja;

FlowOS te podatke tretira kao ulaznu istinu plana.

---

# 5. Plan je referenca, ne zatvor

FlowOS zna:

- učitani plan;
- prethodno realizovane taskove;
- posljednji rad;
- trenutno aktivne taskove;
- zavisnosti;
- očekivani sljedeći rad prema planu.

Međutim, korisnik tokom razvoja može:

- promijeniti redoslijed rada;
- privremeno raditi drugi task;
- otvoriti novi neplanirani posao;
- izmijeniti dio plana;
- potpuno odbaciti raniju odluku.

FlowOS ne smije sam mijenjati plan zato što je detektovao odstupanje.

Kada determinističke činjenice pokažu neusklađenost, FlowOS prikazuje korisniku odgovarajući **Decision Gate**.

Primjeri mogućih akcija:

- nastavi očekivani task;
- poveži rad sa drugim postojećim taskom;
- kreiraj novi task;
- označi rad kao neplanirani;
- izmijeni plan;
- samo nastavi praćenje i odluči kasnije.

Korisnik donosi odluku.

FlowOS je evidentira i nastavlja praćenje.

---

# 6. FlowOS prati i agente i korisnika

FlowOS ne prati samo AI agente.

On prati sav relevantan rad na projektu čiji je plan učitan.

To uključuje:

- Claude Code;
- Codex;
- Pi;
- Crush;
- buduće agente;
- ručne izmjene korisnika;
- Git događaje;
- commitove;
- testove;
- build komande;
- promjene fajlova;
- agent reports;
- review rezultate;
- korisničke odluke.

Ako korisnik sam izmijeni fajlove ili napravi commit na aktivnom tasku, i taj rad ulazi u istoriju projekta.

---

# 7. Primarni način rada je external interactive

FlowOS ne zahtijeva da agenti budu pokrenuti kroz FlowOS.

Primarni workflow je postojeći interaktivni rad korisnika:

```text
VSCode
├── Claude Code
└── Codex

Terminal
├── Pi
└── Crush
```

Korisnik bira agenta i neposredno prati njegov rad.

FlowOS taj rad posmatra i evidentira koliko mu tehnički dostupni signali omogućavaju.

Managed AFK execution može biti dodat kasnije, ali nije uslov da bi osnovni FlowOS bio koristan.

Agent i površina preko koje se koristi nisu isti koncept.

Primjeri:

- Claude + VSCode;
- Claude + CLI;
- Codex + VSCode;
- Pi + terminal;
- Pi + RPC;
- Crush + terminal.

FlowOS domain model ne smije biti vezan za jednu konkretnu IDE ekstenziju ili CLI.

---

# 8. FlowOS ne zaključuje da je nešto završeno

Ovo je osnovno pravilo.

FlowOS može evidentirati činjenice poput:

```text
Pi je prijavio završetak rada.
Agent report je kreiran.
Commit postoji.
Testovi prolaze.
Terminalska sesija je zatvorena.
```

Ali nijedna od tih činjenica sama po sebi ne znači:

```text
TASK = ZAVRŠEN
```

Razlikuju se:

```text
agent je završio trenutni rad
```

i:

```text
task je prihvaćen kao završen
```

FlowOS ne donosi drugu odluku.

Korisnik pokreće aplikaciju, pregleda rezultat i odlučuje šta dalje.

---

# 9. Human-controlled workflow gates

Kada jedan implementacioni ciklus dođe do tačke na kojoj je potrebna odluka, FlowOS prikazuje jednostavne akcije koje ne remete stvarni razvojni rad.

Primjer:

```text
[ Radi — pošalji na review ]

[ Treba dorada — nastavi task ]

[ Prihvati bez dodatnog reviewa ]
```

Korisnik jednim klikom bira sljedeći pravac.

FlowOS nakon toga deterministički evidentira odluku i priprema odgovarajući naredni korak.

Cilj nije potpuna automatizacija.

Cilj je:

> **minimalan broj korisničkih odluka na mjestima gdje su one stvarno potrebne.**

---

# 10. Cross-agent review je osnovni workflow

Agent koji je implementirao kod ne treba biti jedini verifier vlastitog rada.

Primjer:

```text
Pi → implementacija
Codex → review
Claude → dodatni review
Korisnik → finalna provjera
```

Moguće su i druge kombinacije.

Korisnik bira reviewera.

FlowOS ne određuje automatski:

```text
Pi uvijek → Codex
Claude uvijek → Pi
```

Razlog je što dostupnost agenata i modela može zavisiti od:

- rate limita;
- potrošenih tokena;
- kredita;
- trenutne dostupnosti providera;
- korisničkog izbora;
- vrste problema.

FlowOS prikazuje dostupne agente i poznata ograničenja, a korisnik bira.

---

# 11. Availability je evidencija, ne predviđanje

FlowOS može evidentirati pouzdano detektovane probleme kao što su:

- rate limit;
- authentication failure;
- insufficient credits;
- provider error;
- trenutno zauzet agent.

Ne pokušava unaprijed predvidjeti buduću raspoloživost.

Stanje treba biti vezano za posljednji poznati signal.

Primjer:

```text
Claude      AVAILABLE
Codex       AVAILABLE
Pi          RATE LIMITED
Crush       UNKNOWN
```

Ako je moguće pouzdano detektovati aktivni model, FlowOS ga može prikazati:

```text
Pi / Kimi
Crush / GLM
```

ali naziv modela nije obavezan za osnovni workflow.

Kod Pi i Crush agenata korisnik može ručno promijeniti model i nastaviti rad.

---

# 12. Context Package umjesto nepotrebne automatizacije

FlowOS ne treba automatski otvarati agente, upravljati VSCode chatom ili slati promptove ako jedan copy/paste rješava problem pouzdanije.

Za implementaciju, review ili fix FlowOS može pripremiti **Context Package** iz već poznatih podataka.

Primjer Review Context Package-a:

```text
Task
Cilj
Acceptance kriterijumi
Relevantni ADR-ovi
Autor implementacije
Base commit
Result commit
Changed files
Diff
Poznati test rezultati
Relevantni agent reports
Instrukcije za review
```

FlowOS zatim nudi:

```text
[ Kopiraj review paket ]
```

Korisnik ga zalijepi u izabranog agenta.

Time se smanjuje količina tokena koju novi agent troši na ponovno istraživanje projekta i prethodnog rada.

FlowOS ne generiše novi semantički kontekst.

On deterministički prikuplja već postojeći kontekst.

---

# 13. Strukturirani agent outputs

Kada FlowOS od agenta očekuje rezultat koji treba dalje obraditi, agentu se unaprijed daje format odgovora.

Cilj je izbjeći potrebu da FlowOS koristi LLM za razumijevanje proizvoljnog slobodnog teksta.

Primjeri strukturiranih rezultata:

- Implementation Result;
- Review Result;
- Fix Update;
- Verification Result;
- Research Result.

Agent može vratiti ljudski čitljiv Markdown uz mali strukturirani dio koji FlowOS može parsirati.

Parser i schema validation imaju prednost nad semantičkim AI parsiranjem.

Ako strukturirani dio nije validan:

- originalni odgovor se ne gubi;
- FlowOS ga sačuva kao običan report;
- korisniku se može ponuditi ponovno formatiranje ili ručno povezivanje.

---

# 14. Review findings

Svaki reviewer ima svoj zaseban `ReviewRun`.

Nalazi različitih reviewera se ne spajaju semantički automatski.

Primjer:

```text
CODEX REVIEW
C-01 HIGH
C-02 MEDIUM

CLAUDE REVIEW
A-01 HIGH
A-02 LOW
```

FlowOS ne pokušava bez AI-a zaključiti da li su `C-01` i `A-01` zapravo isti problem.

Korisnik pregleda findings i bira koje prihvata.

Review finding može biti najmanje:

- kandidat za popravku;
- prijedlog koji zahtijeva korisničku odluku;
- odbačen;
- ostavljen za kasnije.

Nalaz reviewera nije automatska instrukcija implementeru.

---

# 15. Fix Package i fix lifecycle

FlowOS od korisnički prihvaćenih findings priprema `Fix Package`.

Fix Package može sadržati:

- originalni task;
- acceptance kriterijume;
- originalnog implementera;
- reviewera;
- prihvaćene findings;
- prijedloge rješenja reviewera;
- relevantne fajlove;
- trenutno Git stanje;
- relevantne reports.

Implementer dobija samo findings koje je korisnik odobrio za dalji rad.

Ako implementer utvrdi da fix zahtijeva:

- promjenu arhitekture;
- proširenje scopea;
- promjenu acceptance kriterijuma;
- promjenu plana;

ne treba samostalno donositi takvu odluku.

Takav slučaj se vraća korisniku.

---

# 16. Fix se prati pojedinačno, ali se rad ne prekida administracijom

Ako Fix Package sadrži više findings, implementer prijavljuje napredak pojedinačno.

Primjer:

```text
C-01 → FIXED
C-02 → IN_PROGRESS
A-02 → NOT_STARTED
```

To omogućava FlowOS-u da precizno zna stanje rada čak i ako se sesija prekine.

Međutim, implementer ne treba prekidati prirodan radni proces nakon svake male izmjene samo da bi kreirao novi agent report.

Mali povezani taskovi i popravke mogu biti obrađeni u jednoj logičnoj radnoj sesiji.

---

# 17. Implementer nije verifier

Ako Pi implementira ili popravlja kod:

```text
Pi → FIXED
```

to znači samo:

> implementer prijavljuje da je svoj rad završio.

To nije isto što i:

```text
VERIFIED
```

Testovi koje implementer pokrene predstavljaju evidence, ali ne zamjenjuju nezavisni review/verifikaciju kada je ona potrebna.

Nezavisni verifier je drugi agent.

Finalnu funkcionalnu procjenu vrši korisnik.

Osnovni princip je:

> **generator ne ocjenjuje sam sebe.**

---

# 18. Više nezavisnih reviewera je podržano

FlowOS ne ograničava task na jednog reviewera.

Za značajnije promjene korisnik može koristiti:

```text
Pi implementation
        ↓
Codex review
        ↓
Pi fix
        ↓
Claude verification
        ↓
User acceptance
```

ili:

```text
Pi implementation
       ↓
Codex review
       +
Claude review
       ↓
user selection of findings
```

FlowOS prikazuje svaki review kao zaseban izvor dokaza.

Ne pokušava automatski proizvesti „konsenzus agenata“.

---

# 19. Agent Report je prvoklasni artefakt

Svaka značajna agentska sesija ostavlja svoj zaseban `agent_report`.

Report pripada sesiji, a ne jednom pojedinačnom tasku.

Jedna sesija može obuhvatiti:

- jedan task;
- više povezanih taskova;
- nekoliko manjih popravki;
- review;
- fix cycle;
- verifikaciju.

Svaka sesija dobija svoj zaseban report.

Prethodni report se ne prepisuje novim.

Primjer:

```text
FLOW-017

AR-001 Pi      Implementation Report
AR-002 Pi      Refinement Report
AR-003 Codex   Review Report
AR-004 Pi      Fix Report
AR-005 Claude  Verification Report
```

Time se čuva kompletna istorija handoffa između agenata.

---

# 20. `agent_reports` direktorijum

Standardna lokacija je:

```text
<project_root>/agent_reports/
```

Pri prvom učitavanju projekta FlowOS provjerava postoji li direktorijum.

Ako postoji, automatski se registruje kao agent report lokacija.

Ako ne postoji, korisniku se može ponuditi:

- izbor postojećeg foldera;
- kreiranje `agent_reports`;
- rad bez agent reports funkcije.

Putanja se trajno čuva u konfiguraciji projekta.

FlowOS može pratiti direktorijum i evidentirati pojavu novih reportova.

---

# 21. Report mora navesti stanje svih obuhvaćenih taskova

Jedna sesija može raditi više taskova.

Zato nije dozvoljena pretpostavka:

```text
1 session = 1 task
```

Report mora moći eksplicitno navesti:

```text
TASK-001 → agent work completed
TASK-003 → agent work completed
TASK-005 → in progress
```

Time FlowOS zna stvarno stanje pojedinačnih taskova bez prekidanja prirodne radne sesije.

---

# 22. Strukturirani metadata header za reports

Preporučeni format agent reporta je Markdown sa malim strukturiranim metadata zaglavljem.

Primjer:

```yaml
---
flowos_report: 1
session_id: AR-0042
agent: pi
role: implementation
tasks:
  - TASK-001
  - TASK-003
  - TASK-005
created: 2026-08-09T13:00:00+02:00
---
```

Ispod zaglavlja ostaje normalan ljudski čitljiv izvještaj:

```markdown
# Sažetak

# Šta je urađeno

# Zašto je urađeno

# Kako je urađeno

# Kreirani/izmijenjeni fajlovi

# Šta nije urađeno

# Provjera i testovi

# Rizici i napomene

# Preporučeni sljedeći korak
```

FlowOS parsira metadata.

Korisnik i drugi agenti čitaju Markdown sadržaj.

---

# 23. Activity / Event Ledger je centralna evidencija

FlowOS treba imati hronološki zapis stvarnih događaja.

Primjeri:

```text
Agent session detected
Task selected
File modified
Git commit created
Test command executed
Test passed
Agent reported fix
Agent report created
User manually modified code
User selected review
Review report imported
Finding accepted
Fix package created
User accepted functionality
```

Event Ledger ne predstavlja AI interpretaciju.

On predstavlja činjenice koje FlowOS može dokazati ili koje je korisnik eksplicitno unio.

Iz Event Ledgera FlowOS može rekonstruisati:

- ko je radio;
- kada je radio;
- nad kojim taskom;
- koje fajlove je mijenjao;
- šta je testirano;
- ko je pregledao;
- koje primjedbe su nastale;
- koje su prihvaćene;
- šta je popravljeno;
- gdje je projekat stao.

---

# 24. „Gdje si stao“ mora biti zasnovan na dokazima

FlowOS može koristiti Event Ledger za prikaz:

```text
Posljednji aktivni task
Posljednji agent
Posljednji report
Posljednji commit
Posljednji review
Otvoreni findings
Posljednja korisnička odluka
```

FlowOS ne prikazuje izmišljene procente poput:

```text
72% završeno
```

ako za taj broj nema pouzdan izvor.

Bolje je prikazati:

```text
14 od 22 taska korisnik prihvatio
3 taska imaju aktivan rad
2 reviewa čekaju odluku
1 task je blokiran zavisnošću
```

---

# 25. Decision Inbox

Nenametljive odluke ne trebaju prekidati rad modalnim prozorima.

FlowOS može imati `Decision Inbox` ili ekvivalentan pregled.

Primjer:

```text
Odluke (2)
```

Tu mogu čekati stvari poput:

- nova sesija nije povezana sa taskom;
- reviewer findings čekaju izbor;
- detektovan je konflikt između aktivnog taska i brancha;
- postoji neplanirani rad;
- plan drift zahtijeva odluku.

Samo stvarno rizična ili blokirajuća situacija treba koristiti jaču notifikaciju.

---

# 26. Lokalni AI je opciona mogućnost

FlowOS Core mora potpuno funkcionisati:

- bez interneta;
- bez cloud LLM-a;
- bez lokalnog AI modela.

Formalni arhitektonski zahtjev je:

> **Ako iz FlowOS-a uklonimo svaki LLM, osnovni project tracking, agent tracking, reports, review/fix workflow, Event Ledger i korisničke decision gate funkcije i dalje moraju raditi.**

Lokalni model može kasnije biti opcionalni capability.

Primjeri budućih funkcija:

- semantičko detektovanje plan drifta;
- sažimanje vrlo dugih sesija;
- klasifikovanje neurednog slobodnog teksta;
- detekcija sličnih findings više reviewera;
- preporuka relevantnog konteksta;
- pomoćni lokalni review;
- manji coding zadaci.

Za svaku takvu funkciju prvo se postavlja pitanje:

> Može li ovo pouzdano biti riješeno pravilom, Git informacijom, parserom ili strukturiranim protokolom?

Ako može, determinističko rješenje ima prednost.

---

# 27. FlowOS ne pokušava čitati skriveno razmišljanje agenata

FlowOS prati ono što agent eksterno radi i prijavljuje:

- poruke;
- tool pozive;
- fajlove;
- komande;
- testove;
- reports;
- rezultate;
- dostupne telemetry događaje.

Arhitektura ne zavisi od pristupa skrivenom internom chain-of-thoughtu pojedinačnih modela.

---

# 28. Granica automatizacije

Osnovni princip automatizacije FlowOS-a je:

> **Automatizuj ono što je determinističko i pouzdano.  
> Prikaži ono što je opaženo.  
> Pitaj korisnika kada je potrebna procjena.  
> Ne uvodi LLM samo da bi uklonio jedan jednostavan klik.**

Primjer:

FlowOS treba automatski:

- pronaći `agent_reports`;
- pratiti Git;
- evidentirati commit;
- parsirati strukturirani report;
- pripremiti Review Context Package;
- pripremiti Fix Package;
- prikazati dostupnost agenta ako je signal poznat.

FlowOS ne treba automatski:

- birati reviewera;
- prihvatiti finding;
- proglasiti funkcionalnost završenom;
- mijenjati plan;
- otvarati VSCode chat i slati prompt ako običan copy/paste rješava problem;
- semantički spajati nalaze bez eksplicitno uključenog AI capabilityja.

---

# 29. Odnos prema ADR-001–004

Ovaj ADR ne zamjenjuje ranije prihvaćene odluke.

Posebno potvrđuje ADR-001 princip:

> **Čovjek odlučuje šta i zašto.  
> FlowOS kontroliše i evidentira ono što se može pouzdano kontrolisati.  
> AI agent izvršava konkretan dodijeljen posao.**

ADR-002 razdvajanje DecisionItem i ImplementationTask ostaje validno.

ADR-003 razdvajanje ExecutionWorkspace, AgentRun i AgentContext ostaje validno za managed execution funkcije.

ADR-004 Git ownership i dedicated worktree pravila ostaju validni za FlowOS-managed execution.

Međutim, ADR-003 i ADR-004 ne znače da svaki interaktivni rad korisnika mora biti FlowOS-managed.

FlowOS mora podržavati i external interactive rad koji samo prati i evidentira.

---

# 30. Odgođene tehničke odluke

Ovim ADR-om se namjerno ne zaključuju:

- konačan format importovanog plana;
- puna baza/schema Event Ledgera;
- konkretni adapteri za Claude, Codex, Pi i Crush;
- tačan način detekcije svih IDE događaja;
- potpuni task status state machine;
- finalni GUI Decision Inboxa;
- detalji process lifecyclea;
- Docker;
- HOST execution provider;
- remote execution;
- scheduler;
- automatsko AFK raspoređivanje;
- multi-workspace paralelizacija;
- semantički lokalni AI sloj.

Te odluke se donose naknadno i ne smiju mijenjati osnovne principe ovog ADR-a bez novog eksplicitnog ADR-a.

---

# 31. Sažetak odluke

FlowOS treba da bude:

```text
DETALJAN PLAN
      ↓
   FLOWOS
      ↓
┌───────────────────────────────┐
│ prati korisnika               │
│ prati agente                  │
│ prati Git                     │
│ prati reports                 │
│ prati reviews                 │
│ prati findings                │
│ prati fixeve                  │
│ čuva evidence                 │
│ čuva odluke                   │
│ čuva kompletnu istoriju       │
└───────────────────────────────┘
      ↓
KORISNIK ODLUČUJE
kada je potrebna procjena
```

FlowOS nije zamišljen da zamijeni developera niti da uvede još jedan AI sloj između developera i coding agenata.

Njegova vrijednost je u tome da:

> **developer može koristiti više različitih AI agenata na stvarnom projektu, a da u svakom trenutku ima jedno pouzdano mjesto koje zna šta se desilo, ko je šta radio, gdje je projekat stao, šta je provjereno, šta još nije riješeno i na osnovu kojih odluka je razvoj nastavljen.**