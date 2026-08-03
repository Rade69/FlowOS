# CLAUDE.md — FlowOS

> **BOOTSTRAP STATUS: ZAVRŠEN 2026-07-31 — vidi agent_reports/2026-07-31_bootstrap.md**

Ovaj fajl vodi Claude Code i druge agente kroz pravila rada specifična za FlowOS. Opšta obavezna pravila za sve agente sažeta su u [AGENTS.md](./AGENTS.md), a ciljna arhitektura, faze, gateovi i acceptance kriteriji nalaze se u [FlowOS-novi-detaljan-plan-PySide6.md](./FlowOS-novi-detaljan-plan-PySide6.md). Originalni [FlowOS-kompletan-plan.md](./FlowOS-kompletan-plan.md) ostaje kao referenca za backend arhitekturu.

## Šta je FlowOS

FlowOS je Windows-first lokalni lični operativni sistem koji prvo rješava koordinaciju postojećeg rada:

```text
VS Code / aktivni projekat
├── Claude Code
├── Codex
├── pi agent + model A
├── pi agent + model B
└── korisnik, terminali, Git i testovi
```

Prva vrijednost sistema je vidljivost: ko radi šta, u kojem treeju, koje fajlove stvarno mijenja, gdje postoji konflikt, šta je provjereno i koju odluku korisnik treba donijeti.

FlowOS se zatim modularno nadograđuje:

```text
FlowOS Core
→ Session Coordination
→ flowos CLI wrapper i watcher
→ Git/worktree koordinacija
→ Inbox, Danas i Review
→ Managed Execution
→ Observability i evaluacija
→ Durable Job Engine
→ implementator + verifier
→ distribucija i jača izolacija samo po potrebi
```

## Izvori istine

- [FlowOS-novi-detaljan-plan-PySide6.md](./FlowOS-novi-detaljan-plan-PySide6.md) je izvor istine za arhitekturu, opseg, redoslijed faza, gateove i odluke o tome šta se namjerno ne gradi.
- [FlowOS-kompletan-plan.md](./FlowOS-kompletan-plan.md) ostaje kao referenca za backend arhitekturu, podatkovni model i faze 5+.
- Kod, testovi, migracije i stvarni artefakti su izvor istine za ono što je zaista implementirano.
- Dok ne postoji poseban implementacijski tracker, status faze se utvrđuje provjerom plana, acceptance kriterija i koda. Ne oslanjati se na memoriju ili ranije poruke.
- Kada tracker bude uveden, mora se ažurirati u istom commitu kao implementacija i postaje operativni izvor statusa. Ne prepravljati arhitektonski plan samo radi označavanja napretka.
- Git je autoritet za stanje izvornog koda; FlowOS čuva namjeru, događaje, izvještaje i dokaze, ali ne zamjenjuje Git.

## Jezik

Komunikacija s korisnikom, projektna dokumentacija i agentski izvještaji pišu se na srpskom/bosanskom, latinicom. Kod, nazivi simbola, šeme, API rute i commit poruke mogu ostati na engleskom kada je to projektna konvencija.

Obrazloženja korisniku trebaju biti konkretna i provjerljiva: navesti opažene činjenice, pretpostavke, rizike i rezultate testova bez izmišljanja sigurnosti koju sistem nema.

## Token budget i context disciplina

Agent ne prenosi cijeli prethodni razgovor u novi zadatak — prenosi prihvaćen artefakt (plan, `agent_report`). Veliki fajlovi (stotine+ linija) se prvo pretraže (grep) po pojmu; cijeli se čitaju samo kad zadatak to stvarno zahtijeva. Izuzetak: HIGH/CRITICAL odluke i sigurnosni rizik — tačnost ima prednost nad štednjom konteksta.

## Evergreen napomene

Trenutno N/A — nema koda, nema poznatih bugova, zabranjenih patterna niti tribal-knowledge komentara. Ovaj odjeljak će se popuniti kako projekat bude rastao (prvi `HACK`, `WARNING`, `NOTE:`, `workaround`, `zašto` ili `ne diraj` komentari u kodu).

## Obavezno prije nego počneš kodirati

Napiši kratko (2-4 rečenice) šta si razumio iz zadatka i šta planiraš uraditi. Čekaj potvrdu korisnika ako zadatak nije jednoznačan.

### Facts vs Decisions

Agent ne pita korisnika ono što može sam provjeriti u kodu/repou. Agent ne odlučuje sam ono što je poslovna/UX/arhitektonska odluka samo zato što je usput otkrio tehničku činjenicu. Kad je pitanje stvarno za korisnika:

```markdown
## Fact found
<<< tehnička činjenica sa referencom >>
## Decision required
<<< konkretno pitanje koje samo korisnik može odlučiti >>
## Recommendation
<<< predloženi odgovor i zašto >>
## Consequence
<<< šta se dešava suprotnim putem >>
```

### Confirmation gate

Za veće/nejasne zadatke (ne za svaku sitnicu): prije implementacije prikazati kratak "Shared Understanding Check" — cilj, ključne odluke, otvorena pitanja, pretpostavke, predloženi sljedeći korak — i sačekati potvrdu.

## Reprodukcija i provjera prije rada

**Bugfix**: bug se ne popravlja dok nije reprodukovan (failing test, konkretan ulaz, log, screenshot/video, precizan ručni postupak), osim kad je zapisano zašto reprodukcija nije moguća i na kojoj se pretpostavci izmjena zasniva. Ne mijenjati kod samo zato što implementacija izgleda sumnjivo — to nije isto što i dokazan uzrok.

**Feature/enhancement**: prije prihvatanja zadatka, potvrditi da funkcionalnost već ne postoji i da postoji stvarna korisnička potreba.

**Eksterni/tuđi predlog koda**: prije usvajanja — checkout, testovi, pregled diff-a, tek onda odluka.

## PROBE — kad postoji stvarna nepoznanica

Za nepoznatu biblioteku/API, nejasne performanse, neprovjeren format, nepoznato GUI/OS ponašanje, dilemu arhitekture — `PROBE` NE proizvodi produkcionu funkcionalnost, samo odgovara na JEDNO konkretno pitanje. Rad ide na throwaway granu/worktree (`probe/<pitanje>`), NIKAD se ne mergea. Ako se pokaže vrijednim: baciti i implementirati pravilno, ili zadržati samo dokazani dio iza novog interfejsa — nikad "očvrsnuti" na licu mjesta.

```markdown
# Pitanje
# Pretpostavka
# Način provjere
# Rezultat
# Dokaz (test, screenshot, benchmark, primjer izlaza, log, mali prototip)
# Ograničenja rezultata
# Preporuka
# Odluka koju sada možemo donijeti
```

## Arhitektura — ne pregovara se bez izmjene plana

```text
PySide6 + Qt Widgets GUI (flowos-gui.exe)
        ↓ HTTP/WebSocket (127.0.0.1)
FastAPI lokalni servis (flowos-service.exe)
        ↓ subprocess / Job Objects
Claude Code | Codex | pi | CLI
        ↓
SQLite/WAL + modularni domeni
```

Tri izvršna ulaza:
- `flowos-gui.exe` — PySide6 Qt Widgets aplikacija (View → Controller → Services)
- `flowos-service.exe` — FastAPI backend, jedini vlasnik baze, watchera i procesa
- `flowos.exe` — Typer CLI wrapper za registraciju sesija

Electron, React, Node.js, npm, pnpm, yarn i QML su zabranjeni — nisu dio aplikacije ni build procesa.

### GUI — PySide6 + Qt Widgets

- View je isključivo prikaz i prikupljanje korisničkih akcija. Ne sme direktno pozivati Services.
- Controller povezuje View signale sa GUI Services pozivima. Ne sme pristupati bazi/Git-u/subprocess-u.
- GUI Services komunicira sa backendom preko HTTP/WebSocket-a (127.0.0.1).
- Poslovna, agentska, watcher, Git/worktree, storage i AI logika ne pripadaju GUI procesu.

### Python backend

Backend radi kao stalni lokalni servis iz system traya/autostarta, jer watcher i nadzor sesija moraju nastaviti kada je GUI zatvoren. Backend je vlasnik:

- Core domena: projekti, zadaci, odluke, ugovori i reporti;
- Session Registryja i SessionEventa;
- filesystem watchera i Git snapshotova;
- detekcije konflikata i atribucije;
- worktree koordinacije;
- CLI wrapper API-ja;
- agentskog gatewaya i adaptera;
- Managed Executiona od faze 6;
- observability/evaluation podataka od faze 7;
- Durable Job Enginea od faze 8.

### Granice modula

- Core ne importuje konkretne agent adaptere.
- Session Coordination radi i bez Managed Executiona.
- Managed, Durable i Observability zavise od stabilnih Core/Session ugovora, ne obrnuto.
- Razlike Claude Codea, pi-ja, Codexa i drugih alata ostaju u adapterima.
- Sistem ostaje modularni monolit dok faza 10 i stvarno mjerenje ne opravdaju izdvajanje procesa ili servisa.

## Ključne produktne odluke

### Detekcija prije deklaracije

Filesystem watcher i Git predstavljaju primarne signale o stvarnim izmjenama. `--hint` ili ownership glob služi za pomoć pri atribuciji, ali nije dokaz da je agent pročitao ili promijenio fajl.

### Wrapper kao kičma

Primarni tok je `flowos session start`. Registracija, početni snapshot, PID, aktivnost, završni snapshot i draft report moraju nastati kao nusprodukt rada. Ako wrapper stvara više od približno 30 sekundi ukupnog overhead-a ili ga manje od 80% sesija koristi nakon mjesec dana, to je prioritetni produktni problem.

Redoslijed implementacije adaptera je obavezan dok mjerenje ne opravda promjenu:

```text
Claude Code → pi → Codex → GenericCliAdapter
```

Početni capability ugovor sadrži samo:

```text
can_launch
can_stream_events
can_report_usage
can_cancel
can_use_worktree
```

Ne dodavati `can_cooperative_pause`, `can_resume_step` ili `can_request_approval` dok prvi ciljani alat ne ponudi stvarnu podršku.

### Iskreno prikazivanje confidencea

- Poseban worktree sesije: pouzdana atribucija.
- Jedna aktivna sesija u dijeljenom treeju: vjerovatna atribucija.
- Više aktivnih sesija u istom treeju: hint ili `UNATTRIBUTED`.
- Ručna sesija: FlowOS ne glumi kontrole procesa koje ne posjeduje.

### Izolacija za paralelnu implementaciju

- Isti tree koristiti za analizu, review i kratke koordinisane izmjene.
- Svaka ozbiljna paralelna implementacija dobija zaseban worktree.
- Jedan writable worktree ima jednog writer agenta.
- Integraciju i redoslijed mergea bira korisnik. Automatski merge nije dio opsega.

### Modularna buduća automatizacija

Managed Execution, Durable Job Engine i verifier nisu izbačeni. Oni se namjerno uvode tek nakon što wrapper, koordinacija i worktree tok rade u svakodnevnoj upotrebi. Ne graditi njihove prečice unutar Corea.

### Precizna pravila watchera i konflikata

- `watchdog` prati create/modify/delete događaje na registrovanim repoima i worktreejima uz debounce od 500 ms.
- Po defaultu ignoriše `.git/`, `node_modules/`, `__pycache__/`, `dist/` i konfigurisane build artefakte.
- Git polling je svakih približno 30 sekundi po aktivnom repou.
- Dvije sesije koje upisuju isti fajl u istom treeju unutar 10 minuta daju VISOKO upozorenje.
- Upis u fajl koji je druga sesija mijenjala u zadnjih 30 minuta daje SREDNJE upozorenje.
- Pragovi su konfigurabilni; nova pravila se dodaju samo iz stvarno zabilježenih konflikata.

## Rad po fazama

Redoslijed iz glavnog plana je obavezan:

1. Faza 0 — validacija stvarnog workflowa.
2. Faza 1 — baza, API i minimalni Task/Session temelj.
3. Faza 2 — wrapper, watcher, Git snapshoti i Aktivne sesije.
4. Faza 3 — konflikti, timeline, reporti i `verify.py`.
5. Faza 4 — worktree tok.
6. Faza 5 — Inbox, Danas, Review, Decision i TaskContract.
7. Faza 6 — Managed Execution.
8. Faza 7 — Observability i evaluacija.
9. Faza 8 — Durable Job Engine.
10. Faza 9 — implementator + verifier.
11. Faza 10 — distribucija i jača izolacija samo uz dokazanu potrebu.

Nova faza ne počinje samo zato što je prethodna „uglavnom završena". Provjeriti acceptance kriterij i odgovarajući vertikalni eksperiment E1–E4. Preferirati jedan mali, završiv skup promjena umjesto velikog rewritea.

## Šta se namjerno ne implementira unaprijed

Ove odluke iz §21 plana su obavezne arhitektonske granice:

- Lokalni sistem nema `WorkerLease`, poseban heartbeat ni fencing generation. Backend je jedini dodjeljivač, a PID + Windows Job Object + startup recovery pokrivaju jedan računar. Lease/fencing se vraćaju tek u fazi 10 s udaljenim workerima.
- Nema Checkpoint tabele. Checkpoint je commit SHA + `handoff.md` artefakt i `CHECKPOINT` event.
- Ownership glob je samo opcioni hint; nikada temelj atribucije.
- Nema hash-checka čitanje→upis dok adapteri ne emituju pouzdane read evente.
- Nema `ControlRequest` modela; lokalna kontrola koristi statusne kolone i PID/Job Object.
- Nema opšte approval risk matrice ni kanonskog hash sistema dok nema vanjskih approvera ili automatskih critical akcija. Approval se veže za sačuvani payload artefakt.
- Nema cooperative pause/resume procesa dok ciljani CLI alat to ne podrži. Durable pause znači „ne pokreći sljedeći korak".
- AgentSpan se ne koristi kao durable backend za eksterne CLI procese. Može se evaluirati samo za pi/SDK tok ako pi kasnije zatraži takvo izvršavanje.
- Nema DAG editora, workflow jezika, automatskog mergea, model votinga, brokera, mikroservisa ili klastera u lokalnom opsegu.
- OpenTelemetry se ne uvodi prije pojave konkretnog vanjskog konzumenta.
- VS Code ekstenzija se razmatra tek kada je wrapper stabilan i korišten najmanje mjesec dana.

## Obavezna procedura prije izmjene

### 1. Provjera zajedničkog treeja

Pokrenuti:

```text
git status --short --branch
git log -5 --oneline
```

Zabilježiti postojeće izmjene i ne pripisivati ih sebi. Ako je tree prljav:

- nastaviti samo kada se zadatak može izolovati;
- ne formatirati ili prepisivati nepovezane fajlove;
- ne koristiti destruktivne Git komande;
- ne uključivati tuđe promjene u vlastiti commit;
- za paralelnu implementaciju preferirati poseban worktree.

Pošto isti filesystem mogu koristiti Claude Code, Codex, pi i korisnik, svaki ciljni fajl treba ponovo pročitati neposredno prije upisa. Ako se sadržaj promijenio od pregleda, ponoviti analizu umjesto slijepog upisa.

### 2. Kontekst i pozivaoci

Prije promjene funkcije, klase, metode, API rute, modela baze ili javnog ugovora:

- pročitati cijeli relevantni modul;
- pronaći pozivaoce i potrošače;
- pronaći testove, migracije i dokumentaciju;
- razumjeti execution flow i persistence posljedice;
- provjeriti granice modula iz plana.

### 3. Impact analiza

Ako je GitNexus indeksiran:

- pokrenuti upstream impact prije izmjene simbola;
- korisniku prijaviti direct callers, pogođene procese i nivo rizika;
- za HIGH ili CRITICAL rizik stati i upozoriti prije editovanja;
- koristiti graph-aware rename za preimenovanja;
- prije commita pokrenuti detect changes.

Ako GitNexus nije dostupan ili repo nije indeksiran, ručno koristiti pretragu referenci i prijaviti blast radius. Nedostupan indeks nije dozvola za preskakanje impact analize.

### 4. Task contract

Za svaku netrivijalnu izmjenu definisati:

- cilj;
- scope;
- out-of-scope;
- acceptance kriterije;
- relevantne putanje;
- rizike;
- plan verifikacije;
- očekivane artefakte.

U ranim fazama contract može biti u agentskom izvještaju ili task dokumentu. Od faze 5 koristi se FlowOS `TaskContract`.

### 5. Plan prije izmjene — HIGH/CRITICAL impact

Ako je impact HIGH/CRITICAL (GitNexus impact analiza ili ručna procjena: simbol ima >10 pozivalaca, centralna poslovna logika, baza/migracije, sigurnost), PRIJE izmjene napraviti kratak plan. Kad `project_rooms/` folder postoji, zapisati ga tamo (`project_rooms/YYYY-MM-DD_naziv.md`), inače kao odjeljak u `agent_report`-u:

- **Cilj** — šta se postiže
- **Pogođeno** — moduli, funkcije, tabele, rute
- **Plan** — redoslijed koraka
- **Šta NE dirati** — scope lock
- **Plan verifikacije** — koji dokaz mora postojati (vidi Definition of Done)
- **Rollback/oporavak** — kako vratiti ako ne uspije
- **Nezavisni checker** — ko/šta potvrđuje (vidi Nezavisna provjera)
- **Odbačene opcije** — opcija/zašto razmatrana/zašto odbačena/kada ponovo otvoriti
- **Konflikti** — kontradiktorni izvori, nekompatibilni zahtjevi

Za MEDIUM ili niže se preskače — OSIM kad je odluku teško vratiti, iznenađujuća je bez konteksta, ili je stvaran kompromis (isti filter kao ADR).

### 6. Handoff visokog rizika

Kad je impact HIGH/CRITICAL, prijaviti korisniku PRIJE izmjene:

- koliko koda zavisi od pogođenog simbola;
- da li je promjena mala/velika po obimu ali visoka/niska po sistemskoj važnosti i zašto;
- šta scope NE uključuje;
- šta MORA postojati kao izlaz (tip promjene, prihvatljiv ishod/scope lock, nivo dozvole).

## Pravila tokom implementacije

- Ne mijenjati nepovezan kod „usput".
- Ne popravljati format cijelog fajla ako to skriva stvarni diff.
- Ne pretpostavljati da je prethodni agent završio posao; provjeriti kod i testove.
- Ne vjerovati samo tekstualnom izvještaju agenta; provjeriti Git i artefakte.
- Backend je jedini normalni SQLite writer; wrapper koristi API. Offline upis mora imati jasan kasniji sync i idempotency.
- Append-only događaje ne prepisivati.
- Velike diffove i logove čuvati kao artefakte, ne nekontrolisano u bazi.
- Atribuciju iz dijeljenog treeja označiti kao heurističku.
- `EXTERNAL_TRACKED`, `WRAPPED_TERMINAL`, `MANAGED` i `DURABLE` režime ne miješati.
- `EXTERNAL_TRACKED` nema poseban heartbeat; `last_activity` se izvodi iz posmatranih filesystem/Git događaja.
- Windows Job Object je predviđen za kontrolu child procesa; PID sam nije dovoljan dokaz identiteta procesa poslije restarta.
- Checkpoint je commit + `handoff.md`; ne pokušavati čuvati ili replayati interno rezonovanje modela.
- Retry je ograničen budžetom. Nejasan side effect ide u `BLOCKED`.
- Verifier je read-only, dobija dokazni paket i najviše dvije review runde.
- Preferirati Nivo 0 deterministički kod; Nivo 1 jeftini model; Nivo 2 jaki agent; Nivo 3 durable tok samo prema potrebi.
- Default: bez komentara — imena nose "šta". Komentar samo za neočigledno "zašto", kratak (jedna linija). Dugo objašnjenje ide u `agent_report`, komentar u kodu je samo link: `# Vidi agent_reports/YYYY-MM-DD_naziv.md`
- Tri slične linije > prerana apstrakcija.
- Bez error handling/validacije za scenarije koji se ne mogu desiti — validacija samo na granicama sistema.
- Ne miješati refactor i funkcionalnu izmjenu u istom zadatku/commit-u. Sitno čišćenje nastalo u istom koraku je OK; veći refactor ide u poseban zadatak.

## Sigurnost i privatnost

- Nijedan model ne dobija proizvoljni shell iz FlowOS Corea.
- Praćenje sesije ne proširuje dozvole procesa.
- Managed Execution koristi allowlist komandi, dozvoljene putanje, filtriran environment i timeout/cancel.
- Dependency instalacije, mrežne akcije, migracije i push traže approval.
- Produkcijske, finansijske i komunikacijske akcije uvijek traže eksplicitni approval.
- Tajne čuvati u Windows Credential Manageru ili drugom OS keychainu.
- Redigovati vjerovatne tajne prije pohrane stdout/stderr logova.
- Ne slati telemetriju van računara bez eksplicitne odluke korisnika.
- Git worktree nije sigurnosni sandbox. Container i mrežna ograničenja pripadaju fazi 10.
- Nikada ne commitovati tajne, `.env` fajlove sa stvarnim vrijednostima, lokalne baze, privatne logove ili korisničke artefakte.

## File header komentar

Svaki novi ili značajno izmijenjen kod fajl (`.py`, `.ts`, `.tsx`, `.cjs`, `.css` i slični) treba imati kratak komentar/docstring na vrhu koji objašnjava:

- šta fajl radi;
- koji problem rješava;
- kako se uklapa u modul ako to nije očigledno iz putanje.

Dovoljno je 2–5 linija. Postojeće fajlove bez headera ne mijenjati samo radi ovog pravila; dodati ga kada se fajl funkcionalno mijenja.

## Verifikacija i Definition of Done

### Standardna ulazna tačka

Svaki repo kojim FlowOS upravlja treba težiti jednoj standardnoj ulaznoj tački:

```text
python scripts/verify.py
```

Dok ona ne postoji, pokrenuti relevantne projektne komande pojedinačno.

### Definition of Done po tipu promjene

Promjena nije završena samo zato što se pokrenula. Dokaz zavisi od tipa:

| Tip promjene | Minimalni dokaz |
|---|---|
| **Mala** (jedan fajl, lokalna funkcija) | format/lint + ciljani unit testovi |
| **Srednja** (više fajlova, novi modul) | prethodno + typecheck + širi testovi + build smoke |
| **Velika/rizična** (baza, migracije, API, sigurnost) | prethodno + integracijski testovi + sigurnosna provjera + nezavisni review + approval |
| **GUI/frontend** | screenshot prije/poslije; offscreen render nije dovoljan za nešto što zavisi od stvarnog prikaza |
| **Parser/import** | fixture fajlovi, edge case-ovi, dokaz da stari izvori nisu pokvareni |
| **Baza/migracije** | izolovana test baza, backup prije produkcijske migracije, NIKAD prvi put na produkcijskim podacima |
| **Performanse** | mjerenje prije/poslije, funkcionalna jednakost |
| **Sigurnost** | osjetljivi podaci ne završavaju u promptu/logovima/agent_report-u |

### Hijerarhija dokaza

Od najjačeg prema najslabijem:

1. Deterministički test (unit/integration)
2. Reproducibilan benchmark
3. Build/package rezultat
4. Golden file
5. Screenshot/video
6. Ručna QA lista
7. Agentovo objašnjenje (najslabiji mogući dokaz, prihvatljiv samo kad ništa jače nije dostupno)

Za wrapper, process supervision, recovery i durability obavezni su integracijski i fault-injection testovi iz glavnog plana. Tvrdnja „preživljava restart" nije dokazana običnim unit testom.

## Podjela odgovornosti

| Ko | Šta |
|---|---|
| **Agent radi samostalno** | pretraga koda, pozivaoci, sažimanje ponašanja, failing test, mala lokalna izmjena, testovi, `agent_report` |
| **Agent samo predlaže** (korisnik odlučuje) | arhitektonska promjena, domenski model, centralna poslovna logika, bazna migracija, širi refactor, javni interfejs |
| **Nezavisan checker potvrđuje** | da diff odgovara scope-u, da testovi provjeravaju pravi problem, da nema regresije |
| **Korisnik odlučuje** | poslovna ispravnost, UX, HIGH/CRITICAL rizik, produkcijsko stanje |

## Nezavisna provjera (checker)

Obavezna ili snažno preporučena za: HIGH/CRITICAL impact, promjene baze/migracija, centralnu poslovnu logiku, sigurnost, nereprodukovane bugove, kontradiktorne izvore, veliku cijenu greške.

Checker (drugi agent, drugi model, ili korisnik) nezavisno:
- pregleda diff,
- potvrdi scope,
- provjeri pozivaoce,
- pokrene testove,
- POKUŠA OBORITI hipotezu (ne samo potvrditi),
- jasno kaže šta NIJE provjerio.

Dvije odvojene ose:
- **Standards review** — konvencije, arhitektura, error handling, sigurnost, performanse
- **Spec review** — da li kod zaista rješava zadati problem, izostavljeni slučajevi, scope creep

"Agent kaže da je gotovo" i "checker je dokazao da radi" su dvije različite tvrdnje — ne miješati ih u `agent_report`-u.

Konkretan mehanizam na ovom projektu: GitNexus impact analiza (kad je indeksiran), druga agentska sesija (kad bude dostupna), ili ljudski review.

## Format zadatka za agenta (preporučeno)

Za netrivijalne zadatke:

```markdown
**Zadatak** — šta
**Moja radna pretpostavka** — hipoteza
**Provjeri hipotezu** — agent potvrđuje/odbacuje dokazom prije izmjene
**Granice** — šta se NE dira
**Šta je dobar ishod**
**Obavezno** — impact/rizik + `agent_report`
```

Za sitne ispravke format je nepotreban overhead.

## Retention i čišćenje

- Metadata, reporti, odluke, approvali, `SessionEvent` i `GitSnapshot` čuvaju se trajno dok plan ne odredi drugačije.
- Sirovi `FileActivity` čuva se 30 dana; agregat ostaje u reportu.
- Stdout/stderr i veliki artefakti čuvaju se 30–90 dana, a hash i manifest duže.
- Neuspješan ili napušten worktree čuva se najmanje 7–30 dana i briše samo uz korisničku potvrdu.
- Integrisani worktree briše se tek poslije potvrde i retention perioda.
- Čišćenje mora biti auditirano i nikada ne smije dirati aktivnu ili blokiranu sesiju/job.

## Obavezna procedura nakon zadatka

### 1. Pregled stvarnog diffa

Provjeriti `git status`, diff i listu izmijenjenih fajlova. Odvojiti vlastite promjene od prethodnih korisničkih ili agentskih promjena.

### 2. Agent report

Napisati:

```text
agent_reports/YYYY-MM-DD_kratak-slug.md
```

Obavezne sekcije:

- Datum
- Agent / model / sesija, kada je poznato
- Scope
- Task contract / acceptance kriteriji
- GitNexus impact ili ručni blast radius
- Reprodukcija prije izmjene (za bugfix — dokaz ili razlog zašto nije moguće)
- Šta je urađeno
- Zašto je urađeno
- Kako je urađeno
- Izmijenjeni fajlovi i ponašanje
- Šta nije dirano
- Verifikacija i stvarni rezultat
- Nezavisna provjera (obavezno za HIGH/CRITICAL)
- Pronađeni problemi
- Odbačene opcije (opcija/zašto razmatrana/zašto odbačena/kada ponovo otvoriti)
- Konflikti/kontradiktorni izvori
- Commitovi
- Rizici i ograničenja
- Potreban follow-up
- Potrebna korisnička potvrda

Ne tvrditi da je test prošao ako nije pokrenut. Jasno razlikovati `nije pokrenuto`, `nije dostupno` i `palo`.

Commitovati agent report odmah nakon pisanja.

### 3. Veza odluke s kodom

Za netrivijalnu odluku ili workaround u funkcionalno značajnom mjestu dodati kratak komentar, na primjer:

```text
// Context: agent_reports/2026-07-20_session-wrapper.md
```

Ne dodavati ga svakoj funkciji niti trivijalnoj promjeni.

### 4. Status faze

Kada postoji implementation tracker, ažurirati ga u istom commitu kao kod. Fazu označiti završenom samo kada su ispunjeni acceptance kriterij i vertikalni eksperiment. Do tada je status djelimičan bez obzira na količinu napisanog koda.

### 5. GitNexus

Ako je podešen, pokrenuti detect changes prije commita i osvježiti indeks nakon relevantnih promjena.

### 6. Format outputa (obavezno na kraju svakog zadatka)

```text
STATUS: OK | PARCIJALNO | BLOKIRANO
IZMIJENJENI FAJLOVI: lista
ŠTA JE URAĐENO: kratko
ŠTA NIJE URAĐENO: (ako PARCIJALNO/BLOKIRANO)
PITANJA: (ako postoje)
```

### 7. Provjera prije predaje

- [ ] Bug je reprodukovan prije popravke (ili zapisano zašto nije mogao biti)
- [ ] Nisam mijenjao kod van scope-a zadatka
- [ ] Nisam dodao nepotrebne komentare ili docstrings
- [ ] Nisam ostavio zakomentiran kod
- [ ] Testovi prolaze
- [ ] Dokaz odgovara Definition of Done za tip promjene
- [ ] Za HIGH/CRITICAL: nezavisna provjera je urađena i navedena
- [ ] Provjerio sam `git status --short` prije staging-a
- [ ] Output format je popunjen

## Git pravila

- Ne praviti commit bez eksplicitnog korisničkog zahtjeva.
- Ne mijenjati Git identitet korisnika.
- Ne preskakati hookove.
- Ne koristiti `git reset --hard`, `git checkout --`, `git clean` ili druge destruktivne operacije bez jasnog odobrenja.
- Ne amendovati tuđi commit bez eksplicitnog zahtjeva.
- Jedan agent predaje mali, razumljiv diff ili čist commit kada je commit zatražen.
- Integracija worktreeja ostaje korisnička odluka.
- Nikad `git add -A`/`git add .` — uvijek navesti tačne fajlove.
- Prije svakog `git add`/`commit` provjeriti `git status --short`.
- Ako ima nepoznatih izmjena, utvrditi čije su prije nastavka.
- Dugotrajni/automatizovani pipeline-ovi rade u zasebnom `git worktree` gdje je to moguće.

## Memorija i dokumentacija

Izvor istine je repozitorij: plan, kod, testovi, migracije, `docs/` i `agent_reports/`. Agentska memorija i ranije poruke su samo pomoćni trag i mogu zastarjeti.

Kada postoji razlika između memorije i provjerljivog stanja repozitorija, repozitorij pobjeđuje. Prije tvrdnje o statusu uvijek provjeriti plan, kod i posljednje izvještaje.

---

## Kad ovaj fajl podijeliti na više

Znak da je vrijeme: "Evergreen napomene" odjeljak prelazi nekoliko stotina linija, ili agent počinje "preskakati" dijelove pri čitanju, ili `agent_reports/` ima desetine fajlova bez pregledne istorije.

Podjela — evergreen odvojeno od dated:

```text
CLAUDE.md                — ostaje ovaj fajl, SAMO pravila (evergreen),
                            Evergreen napomene svedene na trajno relevantno
docs/CONTEXT.md           — evergreen napomene koje ostaju, kratko
docs/context/history.md   — dated, append-only log; NE čita se cijeli,
                            pretražuje se (grep) po temi/datumu
agent_reports/            — već postoji
project_rooms/            — kreirati kad prva HIGH/CRITICAL izmjena
                            zatreba plan fajl
```

Ne raditi ovu podjelu unaprijed "za svaki slučaj". Uvesti je kad prvi put stvarno nedostaje.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **FolowOS** (4923 symbols, 7766 relationships, 90 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/FolowOS/context` | Codebase overview, check index freshness |
| `gitnexus://repo/FolowOS/clusters` | All functional areas |
| `gitnexus://repo/FolowOS/processes` | All execution flows |
| `gitnexus://repo/FolowOS/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
