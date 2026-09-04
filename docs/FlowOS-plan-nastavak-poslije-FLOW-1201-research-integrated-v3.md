# FlowOS — nastavak razvoja nakon FLOW-1201 (research-integrated v3)

**Datum:** 2026-09-04  
**Status:** prijedlog novog ACTIVE plana nakon zatvaranja FLOW-1201  
**Polazna tačka:** FLOW-1201 mora biti Human ACCEPTED, mergeovan u `main`, remote verificiran i CLOSED prije aktivacije ovog plana.

Ovaj plan ne prepisuje istoriju Faze 11 niti FLOW-1201. Prethodni plan ostaje istorijski dokaz i nakon aktivacije ovog plana treba postati `SUPERSEDED`.

Cilj je nastaviti produktni razvoj bez zaustavljanja zbog teorijskih rizika, ali ugraditi istraživane tehničke zaštite tačno na mjestima gdje postaju relevantne.

## Način razvoja

1. **Jedan aktivni razvojni task.** Ne miješati implementaciju tekućeg taska sa istraživačkim ili budućim hardening taskovima.
2. **Task contract prije koda.** Za svaki FLOW item prvo zaključati cilj, scope, acceptance testove i eksplicitno `Ne raditi`.
3. **Najjeftiniji dovoljan implementer.**
   - Pi / Crush: uski backend/GUI/test taskovi i rutinska implementacija.
   - Claude / MinMax: arhitektura, cross-layer HIGH rizik, migration/data-integrity ili veći refactor.
4. **Implementer ne radi finalni acceptance review.** Završni review radi svježa, nezavisna sesija/agent.
5. **Dokaz prije odluke.** Commit SHA, stvarni diff, test output, verification artifact i review nalaz imaju prednost nad tvrdnjom agenta.
6. **Human Owner daje ACCEPT / NEEDS_WORK / REJECT.**
7. **Tek nakon ACCEPT:** merge → post-merge test → remote verify → task CLOSED.
8. **Technical risk hardening radi se just-in-time.** Ne implementirati sve nalaze preventivno; aktivirati ih prije tačke u kojoj bi mogli ugroziti dogfooding ili korisničko povjerenje.
9. **Nema novih velikih platformskih koncepata bez dokaza potrebe.** SQLite ostaje; nema Event Sourcinga, Kafka/Outbox sistema, PostgreSQL migracije, DI frameworka ili automatskog Git self-healinga bez mjerljivog razloga.

## Globalna tehnička pravila

Ova pravila važe za sve naredne stavke:

- **Authority:** Git je autoritet za Git stanje; filesystem za postojanje/sadržaj fajla; OS za proces; FlowOS DB za canonical Task/Plan/Decision stanje; AgentReport je evidence/claim, ne authority; verification artifact je autoritet za izvršeni test.
- **Freshness:** project-scoped async GUI odgovor mora imati dovoljno identiteta da se stale rezultat ne može renderovati kao aktuelan. Koristiti postojeći `project_id + generation` obrazac kada novi ekran ulazi u isti project-data refresh.
- **Trigger ≠ truth:** watcher, WebSocket, timer i agent report samo pokreću novu opservaciju; nisu sami po sebi canonical stanje.
- **Observation failure ≠ CURRENT:** neuspjela opservacija mora biti `UNKNOWN/OBSERVATION_FAILED`, nikad lažno zdravo stanje.
- **Single transaction owner:** novi write use case mora imati jednu jasnu commit/rollback granicu.
- **Idempotency:** retry/dupli signal ne smije praviti dupli canonical događaj.
- **Ledger:** append-only evidence/audit, ne Event Store i ne canonical mutable state.
- **Human control:** FlowOS klasifikuje i dokazuje; ne radi destruktivni Git/FS self-heal po defaultu.
- **Migration gate:** svaka ozbiljna SQLite migracija mora imati backup, Alembic head provjeru, `PRAGMA integrity_check`, `PRAGMA foreign_key_check` i application invariants.
- **Ne refaktorisati za estetiku:** arhitektonski extraction samo kada postoji stvarni orchestration/testability problem.

---

## Faza 12 — Projekat i Task kao stvarna radna površina

#### FLOW-1202 — Povezati Zadaci ekran sa stvarnim `/tasks` backendom

**Rizik:** MEDIUM

Postojeći `TasksPage` prestaje biti placeholder i prikazuje stvarne `ImplementationTask` zapise.

**Obavezno:**
1. Dodati minimalni read API client tok za taskove.
2. Prikazati identitet taska, naslov, status i vezani PlanItem ako postoji.
3. Task bez PlanItem-a mora biti validan i jasno prikazan.
4. Ne tretirati PlanItem kao Task.
5. Ne uvoditi procenat završenosti bez determinističkog izvora.
6. Tasks read mora biti project-scoped i pratiti postojeći aktivni project context.
7. Async response ne smije renderovati podatke starog projekta ili starije generation pod novi context.
8. Dodati deterministički regression test za project switch i stale/out-of-order response.
9. Ako se Tasks uključuje u `_load_project_data()` batch, mora koristiti isti project generation ugovor kao ostali project-scoped readovi.

**Dokaz:** LIVE `Zadaci` ekran prikazuje stvarne Task zapise iz baze; A→B switch i same-project out-of-order response ne mogu prikazati stale Task podatke.

**Ne raditi:** Ne praviti kanban, prioritization engine, AI task manager niti novi async framework ako postojeći generation obrazac rješava problem.

---

#### FLOW-1203 — Napraviti minimalni Task Detail read model

**Rizik:** HIGH

Kreirati read-only backend prikaz jednog Taska koji objedinjuje samo postojeće i dokazive činjenice potrebne GUI-ju.

Završiti FLOW-1202 prije FLOW-1203.

**Obavezno:**
1. Task identity i canonical trenutni status iz FlowOS DB.
2. Povezani PlanItem ili jasno `unassigned`.
3. Aktivne i istorijske `SessionTaskBinding` veze relevantne za Task.
4. Povezane AgentReport metapodatke samo kada je veza dokaziva.
5. Workflow Ledger događaje za logical Task.
6. Ne spajati sirove agent telemetrijske događaje u canonical workflow istoriju.
7. Read model mora jasno razlikovati canonical stanje, evidence i derived informacije.
8. Ne čitati live `Task.plan_item_id` kao zamjenu za istorijske binding snapshotove.
9. Svako polje koje zavisi od observation-derived stanja mora imati jasnu freshness semantiku ili biti izostavljeno iz ovog MVP read modela.
10. Ne uvoditi novu transaction ownership semantiku u read-only use case.

**Dokaz:** Jedan endpoint/service vraća konzistentan Task Detail bez AI zaključivanja i bez authority drift-a.

**Ne raditi:** Ne mijenjati postojeću authority semantiku Task/PlanItem/Binding/Report/Ledger modela.

---

#### FLOW-1204 — Napraviti prvi funkcionalni Task Detail GUI

**Rizik:** MEDIUM

Klik na Task otvara ekran ili panel koji čovjeku pokazuje šta je task, gdje pripada i šta se sa njim do sada desilo.

Završiti FLOW-1203 prije FLOW-1204.

**Obavezno:**
1. Prikaz Task naziva i statusa.
2. Prikaz veze sa PlanItem-om ili `Nije vezano za plan`.
3. Prikaz trenutno relevantne sesije ako postoji.
4. Prazna stanja moraju biti jasna.
5. GUI ne smije prikazivati tehničke ID-e kao glavnu informaciju ako postoji čitljiv naziv.
6. Project/task context promjena mora očistiti ili zaštititi Task Detail od stale async rezultata.
7. GUI prikazuje backend-confirmed state; ne pretpostavlja lokalno authority promjene.

**Dokaz:** Korisnik može otvoriti stvarni Task i razumjeti osnovni kontekst bez gledanja baze ili report fajlova.

**Ne raditi:** Ne implementirati workflow odluke u ovoj stavci.

---

#### FLOW-1205 — Hardenovati Git observation i reconciliation correctness

**Rizik:** HIGH

Prije nego se Current State / Resume / reconciliation koriste kao dokaz u stvarnom dogfoodingu, zatvoriti konkretne correctness probleme pronađene istraživanjem.

Završiti FLOW-1204 prije FLOW-1205. FLOW-1202–1204 ne moraju čekati ovaj task jer ne zavise od Git reconciliation authority-ja.

**Obavezno:**
1. `GitStateReader` ne smije pretvarati neuspjelu Git komandu u prividno prazno zdravo stanje.
2. Git observation failure mora završiti kao eksplicitni `UNKNOWN` / `OBSERVATION_FAILED` ekvivalent; ne smije postaviti lažni `CURRENT`.
3. Implementirati ispravan parser za `git status --porcelain=v2 -z`.
4. Testirati najmanje: modified, staged, deleted, renamed, untracked, filename sa razmakom; unmerged/copy ako ih trenutni parser podržava.
5. Dirty/reconciliation odluka mora porediti snapshot/fingerprint N sa N-1, ne samo činjenicu da trenutno postoji dirty file.
6. Stabilno nepromijenjeno dirty stanje ne smije svaka 120s proizvoditi novi `EXTERNAL_CHANGES` event.
7. `last_observed_at` mora značiti uspješnu opservaciju; `last_reconciled_at` pokušaj/rezultat reconciliation-a. Ne spajati semantiku.
8. Watcher event ostaje trigger/hint; reconciliation mora ponovo čitati autoritativno Git stanje.
9. Ne raditi destruktivni Git self-heal.
10. Dodati test sa stvarnim privremenim Git repozitorijumom, ne samo hardkodiranim parser stringovima.
11. Ne širiti task na SQLite pool, process scanner ili GUI redizajn.

**Dokaz:** kontrolisani Git failure daje UNKNOWN, porcelain fixture-i se parsiraju tačno, a identičan dirty snapshot u dva uzastopna reconciliation ciklusa ne pravi drugi lažni change event.

**Ne raditi:** Ne uvoditi GitPython, Event Sourcing, file watcher kao source of truth niti automatski reset/checkout.

---

## Faza 13 — Workflow Ledger postaje vidljiv korisniku

#### FLOW-1301 — Izložiti Task workflow history kao read-only tok

**Rizik:** HIGH

Napraviti deterministički Task history prikaz zasnovan na postojećem Workflow Ledgeru.

Završiti FLOW-1203 prije FLOW-1301. Za završni acceptance ove faze FLOW-1205 mora biti CLOSED prije prelaska u Phase 14 dogfooding.

**Obavezno:**
1. Podržati `IMPLEMENTATION_COMPLETED`.
2. Podržati `TEST_RESULT`.
3. Podržati `REVIEW_COMPLETED`.
4. Podržati `TASK_DECISION`.
5. Događaji moraju biti sortirani po stvarnom vremenu događaja uz stabilan tie-break.
6. Ne pretvarati commit, file change ili session close u workflow completion event.
7. Postojeći `idempotency_key` ostaje mehanizam za duplikate; ne uvoditi event sequence bez dokaza da causal ordering to zahtijeva.
8. Ledger ostaje audit/evidence read source za istoriju, ne mutable Task state authority.

**Dokaz:** Task sa postojećim Ledger događajima vraća tačnu append-only workflow istoriju bez duplih logical događaja.

**Ne raditi:** Ne uvoditi FINDING_DECIDED, FIX_COMPLETED, VERIFICATION_COMPLETED ili USER_VALIDATION ovdje.

---

#### FLOW-1302 — Prikazati Workflow History na Task Detail ekranu

**Rizik:** MEDIUM

Na Task Detail GUI-ju prikazati ljudski razumljivu vremensku liniju rada.

Završiti FLOW-1301 prije FLOW-1302.

**Obavezno:**
1. `IMPLEMENTATION_COMPLETED` prikazati kao završetak implementacione jedinice, ne kao `Task završen`.
2. `TEST_RESULT` prikazati sa PASS/FAIL/TIMEOUT stanjem.
3. `REVIEW_COMPLETED` prikazati kao završen review, ne prihvatanje.
4. `TASK_DECISION` prikazati kao korisničku odluku.
5. Razlikovati agenta, sistem/mehanički dokaz i korisnika.
6. Tehnički nazivi eventa mogu biti sekundarni.
7. Async reload Task Detail/history mora poštovati aktivni project/task context.

**Dokaz:** Čovjek može redom vidjeti šta je implementirano, testirano, pregledano i odlučeno.

**Ne raditi:** Ne uvoditi AI sažetak kao canonical istoriju.

---

#### FLOW-1303 — Otvaranje reporta i test dokaza iz Task istorije

**Rizik:** MEDIUM

Omogućiti da se iz odgovarajućeg history reda otvori postojeći dokaz bez nove authority semantike.

Završiti FLOW-1302 prije FLOW-1303.

**Obavezno:**
1. `IMPLEMENTATION_COMPLETED` može otvoriti povezani implementation report ako postoji.
2. `REVIEW_COMPLETED` može otvoriti review report.
3. `TEST_RESULT` može otvoriti/prikazati metadata verification artifacta.
4. Nedostajući artifact prikazati kao nedostupan, ne izmišljen.
5. Report body ostaje evidence, ne Task status authority.

**Dokaz:** Iz Task timeline-a korisnik dolazi do stvarnog reporta ili verification dokaza.

**Ne raditi:** Ne parsirati findings iz Markdown body-ja u ovoj stavci.

---

#### FLOW-1304 — Razdvojiti workflow istoriju od tehničke aktivnosti

**Rizik:** MEDIUM

Jasno razdvojiti Workflow Ledger događaje od `ProjectTimelineService` / file / Git aktivnosti.

Završiti FLOW-1302 prije FLOW-1304.

**Obavezno:**
1. Task workflow history ne sadrži obične file watcher događaje.
2. Project `Aktivnost` može i dalje prikazivati Git/file/session tragove.
3. UI jasno pokazuje razliku.
4. Ne brisati tehničku aktivnost ako je korisna za dijagnostiku.
5. Watcher event se ne predstavlja kao dokaz da je kompletno filesystem stanje opaženo.

**Dokaz:** Korisnik razlikuje workflow istoriju Taska od tehničke projektne aktivnosti.

**Ne raditi:** Ne spajati obje liste u jednu neoznačenu timeline listu.

---

#### FLOW-1305 — Izmjeriti SQLite concurrency i transaction boundaries prije dogfooding write faze

**Rizik:** MEDIUM-HIGH

Ovo je **evidence task**, ne unaprijed izabrana DB migracija.

Završiti FLOW-1304 prije FLOW-1305.

**Obavezno:**
1. Zadržati trenutni SQLite/WAL/pool model tokom mjerenja.
2. Simulirati GUI read fan-out: Plan, Resume, Sessions, Timeline, Worktrees, Tasks.
3. Simulirati watcher/report ingestion burst.
4. Simulirati reconciliation dok readovi rade.
5. Simulirati najmanje jednu Human write operaciju pod background loadom.
6. Mjeriti pool checkout wait, transaction duration, HTTP latency, QueuePool timeout, `SQLITE_BUSY`, rollback count.
7. Provjeriti postojeće transaction ownership granice i evidentirati mjesta gdje controller i dependency oba djeluju kao transaction owner.
8. FAIL ako postoji izgubljen/parcijalan canonical write, deadlock ili QueuePool timeout pod realnim lokalnim loadom.
9. Ako testovi prođu, eksplicitna odluka je **KEEP SQLITE / KEEP CURRENT POOL**.
10. Ako ne prođu, otvoriti novi zaseban fix task sa dokazanim uzrokom. Ne popravljati arhitekturu unutar ovog evidence taska.

**Dokaz:** reproducibilan concurrency report i mjerljiva odluka KEEP ili zaseban dokazani follow-up.

**Ne raditi:** Ne povećavati pool naslijepo, ne uvoditi PostgreSQL, ne praviti per-SQL-statement write queue.

---

## Faza 14 — Korisnička odluka u GUI-ju i prvi pravi dogfooding tok

#### FLOW-1401 — Dodati TASK_DECISION kontrole na Task Detail

**Rizik:** HIGH

Izložiti postojeći authority tok kroz minimalni GUI.

Završiti FLOW-1302 prije FLOW-1401.
Završiti FLOW-1305 prije FLOW-1401.
Završiti FLOW-1205 prije FLOW-1401.

**Obavezno:**
1. `Prihvati rezultat` → `ACCEPTED`.
2. `Vrati u doradu` → `NEEDS_WORK`.
3. `Odbaci rezultat` → `REJECTED`.
4. Korisnik jasno vidi nad kojim Taskom/report contextom odlučuje.
5. Dupli klik/retry ne smije proizvesti duplu decision istoriju.
6. `ACCEPTED` ne smije automatski postaviti PlanItem na DONE/VERIFIED ako backend contract to ne radi.
7. GUI ne smije prikazati odluku prije potvrđenog backend response-a.
8. Decision write use case mora imati jednu jasnu transaction boundary; canonical state i pripadajući audit event moraju biti atomarni kada contract zahtijeva oba.

**Dokaz:** jedna stvarna GUI odluka kreira tačno jedan očekivani `TASK_DECISION` događaj i osvježen Task timeline.

**Ne raditi:** Ne implementirati USER_VALIDATION pod drugim imenom.

---

#### FLOW-1402 — Prikazati posljedicu NEEDS_WORK/REJECTED bez skrivene magije

**Rizik:** MEDIUM

GUI nakon odluke pokazuje stvarno backend stanje.

Završiti FLOW-1401 prije FLOW-1402.

**Obavezno:**
1. Ako historical PlanItem consequence vrati status u `IN_PROGRESS`, GUI ga osvježava iz backenda.
2. GUI ne pretpostavlja status lokalno.
3. Ako decision transakcija padne, prikazati grešku bez lažnog uspjeha.
4. Timeline nakon refresh-a mora odgovarati Ledgeru.
5. Retry mora biti idempotentan prema canonical decision contractu.

**Dokaz:** NEEDS_WORK/REJECTED i pripadajući statusi odgovaraju stvarnom backend rezultatu.

**Ne raditi:** Ne replicirati workflow authority u GUI kodu.

---

#### FLOW-1403 — Proći jedan kompletan stvarni FlowOS razvojni tok kroz FlowOS

**Rizik:** HIGH

Izabrati jedan mali realni razvojni Task i pratiti ga kroz postojeće mehanizme.

Završiti FLOW-1402 prije FLOW-1403.

**Obavezno:**
1. Task postoji u FlowOS-u.
2. Sesija je dokazivo vezana za Task.
3. Implementation report je ingestovan.
4. Verification artifact proizvodi `TEST_RESULT`.
5. Independent review report proizvodi `REVIEW_COMPLETED`.
6. Korisnik iz GUI-ja daje `TASK_DECISION`.
7. Task Detail timeline prikazuje kompletan niz bez ručnog fabrikovanja događaja.
8. Tok koristi stvarni authority/freshness model; watcher ili agent claim ne smiju zamijeniti verifikaciju.

**Dokaz:** stvarni posao prolazi `IMPLEMENTATION_COMPLETED → TEST_RESULT → REVIEW_COMPLETED → TASK_DECISION`.

**Ne raditi:** Ne simulirati tok hardkodiranim demo podacima.

---

#### FLOW-1404 — Provjeriti SessionTaskBinding promjenu u stvarnom radu

**Rizik:** HIGH

Namjerno provjeriti da jedna AgentSession može tokom rada promijeniti Task binding.

Završiti FLOW-1403 prije FLOW-1404.

**Obavezno:**
1. Session ima najmanje A→B→A ili A→B→UNASSIGNED istoriju.
2. Binding segmenti ostaju istorijski vidljivi.
3. Report povezivanje ne prepisuje user binding authority.
4. Task history prikazuje samo dokazivo vezane događaje.
5. Ne uvoditi AI guess za binding.

**Dokaz:** binding istorija se prati bez pogrešne Task/PlanItem atribucije.

**Ne raditi:** Ne vraćati model `jedna sesija = jedan task`.

---

## Faza 15 — GUI pojednostavljenje na osnovu stvarnog korištenja

#### FLOW-1501 — Evidentirati stvarne UX odluke nakon dogfoodinga

**Rizik:** LOW

Završiti FLOW-1404 prije FLOW-1501.

**Obavezno:**
1. Zapisati probleme stvarno uočene u korištenju.
2. Razdvojiti bug, UX problem i novu funkcionalnu ideju.
3. Ne pretvarati svaku želju odmah u implementaciju.
4. Prioritet dati svakodnevnom Task toku.

**Dokaz:** kratka lista odluka zasnovana na LIVE korištenju.

**Ne raditi:** Ne uvoditi analytics samo radi ovog taska.

---

#### FLOW-1502 — Pojednostaviti glavnu navigaciju

**Rizik:** MEDIUM

Završiti FLOW-1501 prije FLOW-1502.

**Obavezno:**
1. Procijeniti `Pregled`, `Zadaci`, `Plan`, `Aktivnost` kao primarne površine.
2. Procijeniti `Sesije`, `Agenti`, `Radna stabla` kao tehnički nivo.
3. Procijeniti `Konflikti`, `Izvještaji`, `Projekti` kao stalne ili contextualne stavke.
4. Promjena mora proizaći iz stvarnog dogfooding iskustva.
5. Ne uklanjati funkcionalnost bez alternativnog pristupa ako je potrebna.

**Dokaz:** Sidebar/TopBar odražavaju stvarni svakodnevni tok.

**Ne raditi:** Ne redizajnirati samo zbog estetike.

---

#### FLOW-1503 — Ukloniti ili jasno označiti stare mock/placeholder pretpostavke

**Rizik:** MEDIUM

Završiti FLOW-1502 prije FLOW-1503.

**Obavezno:**
1. Nema hardkodiranih statistika koje izgledaju kao live podaci.
2. Placeholder je jasno prazan/demo.
3. Stari mock widget ne smije zbunjivati composition root održavanje.
4. Ne brisati dokazni/test kod bez provjere.
5. Ono što je prikazano kao stvarno stanje mora imati stvarni read model/authority.

**Dokaz:** GUI više ne predstavlja mock podatke kao realno stanje.

**Ne raditi:** Ne raditi veliki unrelated refactor.

---

#### FLOW-1504 — Zamrznuti prvi dogfood GUI baseline i odrediti narednu fazu

**Rizik:** LOW

Završiti FLOW-1503 prije FLOW-1504.

**Obavezno:**
1. Snimiti screenshotove glavnih LIVE ekrana.
2. Dokumentovati šta stvarno radi.
3. Dokumentovati šta je namjerno odgođeno.
4. Odlučiti da li je sljedeći prioritet structured Findings/FINDING_DECIDED, USER_VALIDATION, napredniji Session prikaz ili druga funkcija.
5. Novi veliki backend događaj ne uvoditi bez ove korisničke procjene.
6. Ponovo procijeniti odgođene rizike: process identity, deterministic Qt transport harness i eventualna DB arhitektura — samo na osnovu stvarnog dogfooding dokaza.

**Dokaz:** prihvaćen dogfood baseline iz kojeg se sljedeća faza bira na osnovu stvarnog korištenja.

**Ne raditi:** Ne proglašavati proizvod završenim samo zato što jedan dogfood tok radi.

---

## Odgođeni rizici — ne blokiraju ovaj plan

Sljedeće je svjesno evidentirano, ali se ne implementira bez konkretnog triggera:

1. **Process identity hardening (`PID + process creation time`)** — aktivirati prije automatskog kill/reconnect/session-liveness lifecyclea.
2. **Deterministički fake Qt network transport** — aktivirati ako project-scoped async testovi postanu teški za kontrolisati postojećim injection seamovima.
3. **PostgreSQL / druga DB arhitektura** — samo ako FLOW-1305 dokaže da SQLite više nije dovoljan.
4. **Causal event sequence/version** — samo ako consumer correctness počne zavisiti od strogog causal ordera.
5. **Transactional Outbox** — samo ako FlowOS dobije durable eksternog event consumera/brokera.
6. **CompositionRoot extraction** — samo kada orchestration postane stvarni testability/maintenance bottleneck.

## Redoslijed od ove tačke

`FLOW-1201 merge/remote verify/CLOSED`
→ aktivirati ovaj continuation plan
→ `FLOW-1202`
→ `FLOW-1203`
→ `FLOW-1204`
→ `FLOW-1205`
→ `FLOW-1301`
→ `FLOW-1302`
→ `FLOW-1303`
→ `FLOW-1304`
→ `FLOW-1305`
→ `FLOW-1401`
→ `FLOW-1402`
→ `FLOW-1403`
→ `FLOW-1404`
→ `FLOW-1501`
→ `FLOW-1502`
→ `FLOW-1503`
→ `FLOW-1504`

**Napomena o paralelizmu:** istraživanje može teći paralelno, ali samo jedan implementation task treba biti aktivan po istom code-area/authority domenu. Ne otvarati paralelne implementacije koje mogu mijenjati isti canonical contract.
