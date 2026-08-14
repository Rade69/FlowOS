# FlowOS — plan dogfooding faza 11–15

Ovaj plan počinje nakon `main` commit-a `33d2f32415e3866d6b55186416b840ad10c9162a`.
Cilj nije odmah završiti kompletan FlowOS, nego dovesti postojeći sistem do tačke u kojoj može pratiti vlastiti dalji razvoj.

Princip:
FlowOS prvo mora pouzdano da se pokrene u LIVE režimu, zatim Task mora postati glavna jedinica rada u GUI-ju, zatim postojeći Workflow Ledger mora postati vidljiv, a tek onda korisničke odluke i dogfooding tok treba koristiti u svakodnevnom razvoju.

Namjerno se NE uvode novi veliki backend koncepti dok ne prođemo jedan stvarni end-to-end tok kroz postojeće mehanizme.

Pre-import provjera 2026-08-12 potvrdila je arhitektonski sadržaj i redoslijed plana, ali je otkrila parser reporting edge case i GUI/backend PlanImport request drift. Zato Faza 11 u ovoj v2 verziji eksplicitno prati i zatvara ta dva preduvjeta prije stvarnog uvoza plana.

## Faza 11 — Stabilan LIVE runtime i uvoz plana

#### FLOW-1101 — Popraviti backend startup blokadu

**Rizik:** HIGH

Otkloniti stvarni startup problem zbog kojeg servis trenutno ne postaje dostupan na runtime descriptor portu. Polazni dokaz iz runtime pregleda je `sqlalchemy.exc.TimeoutError: QueuePool limit of size 1 overflow 0 reached` tokom startup AgentReport ingestion-a.

Obavezno:
1. Reprodukovati kvar na čistom `main` baseline-u prije izmjene.
2. Utvrditi tačan uzrok zadržavanja ili konkurentnog korištenja DB konekcije tokom startup ingestion-a.
3. Popravka ne smije mijenjati zaključanu AgentReport ingestion ni Workflow Ledger semantiku.
4. Nakon popravke `flowos-service` mora stvarno slušati na portu iz runtime descriptora.
5. Pokrenuti relevantne ingestion, Workflow Ledger i full verification testove.

**Dokaz:** LIVE servis se pokreće bez QueuePool timeout-a, `/health` odgovara, runtime descriptor pokazuje stvarno slušajući port i `scripts/verify.py` prolazi 7/7.

**Ne raditi:** Ne povećavati pool naslijepo samo da se simptom sakrije. Ne uvoditi novu DB arhitekturu u ovoj stavci.

#### FLOW-1102 — Popraviti GUI API error path

**Rizik:** MEDIUM

Ispraviti `GuiApiClient._handle_response` put koji pri backend grešci trenutno može baciti `TypeError` jer Qt signal tretira kao običnu funkciju.

Završiti FLOW-1101 prije FLOW-1102.

Obavezno:
1. Reprodukovati postojeći error path testom ili kontrolisanom greškom.
2. Greška backend konekcije mora završiti u predviđenom Qt signal/error prikazu bez sekundarnog exception-a.
3. Ne mijenjati uspješni response tok bez potrebe.
4. Dodati regresioni test za ovaj konkretan slučaj.

**Dokaz:** Kontrolisani connection/error response više ne baca `TypeError`, GUI ostaje živ i prikazuje smislen status greške.

**Ne raditi:** Ne redizajnirati kompletan `GuiApiClient`.

#### FLOW-1103 — Potvrditi jedan podržani LIVE launch tok

**Rizik:** MEDIUM

Napraviti i dokazati jedan jasan razvojni način pokretanja FlowOS-a u LIVE režimu. Postojeći `scripts/run_gui.py` i `scripts/run_service.py` ne smiju se dokumentovati kao podržani runneri ako su samo docstring placeholderi.

Završiti FLOW-1101 prije FLOW-1103.
Završiti FLOW-1102 prije FLOW-1103.

Obavezno:
1. Dokumentovati tačnu komandu za servis.
2. Dokumentovati tačnu komandu za GUI LIVE režim.
3. GUI mora povezati service health bez ručne intervencije u kodu.
4. Zatvaranje i ponovno pokretanje mora dati predvidljivo stanje.
5. Snimiti stvarni screenshot LIVE Pregled ekrana sa zdravim servisom.

**Dokaz:** Čist lokalni start vodi do otvorenog GUI-ja sa `Servis: povezan` i stvarnim odgovorom backenda.

**Ne raditi:** Ne praviti installer niti packaging redesign u ovoj fazi.

#### FLOW-1104 — Stabilizovati PlanMarkdownParser import reporting

**Rizik:** MEDIUM

Ispraviti dva deterministički reprodukovana parser problema otkrivena pre-import provjerom: direktni `PlanMarkdownParser.parse()` pogrešno prijavljuje svaku validnu FLOW stavku kao `unclear_section`, a numerisani kriterijum koji počinje inline-code tokenom može izgubiti početni backtick.

Završiti FLOW-1103 prije FLOW-1104.

Obavezno:
1. Direktni parser za ovaj plan mora vratiti 5 faza i sve FLOW stavke bez lažnih `unclear_sections`.
2. Validni `#### FLOW-...` heading ne smije biti klasifikovan kao nejasna `##` sekcija.
3. Tekst kriterijuma mora biti očuvan bez oštećenja inline-code tokena.
4. Postojeći deterministički parser contract i import semantika ne smiju biti prošireni AI/LLM zaključivanjem.
5. Dodati regresione testove za oba konkretna parser problema.

**Dokaz:** Direktni `PlanMarkdownParser.parse()` i `PlanImportService` daju konzistentan rezultat za ovaj plan, bez lažnih unclear sekcija i bez oštećenih criterion tekstova.

**Ne raditi:** Ne redizajnirati Markdown format plana niti uvoditi heurističko AI tumačenje.

#### FLOW-1105 — Uskladiti GUI i backend PlanImport contract

**Rizik:** MEDIUM

Ispraviti postojeći mismatch u kojem GUI šalje `markdown`, a backend ruta `/projects/{project_id}/import-plan` očekuje `markdown_text`.

Završiti FLOW-1104 prije FLOW-1105.

Obavezno:
1. Utvrditi canonical request field iz stvarnog shared/backend contracta.
2. GUI mora slati tačno canonical request payload.
3. Backend ne smije prihvatati više paralelnih polja samo radi skrivanja drift-a bez eksplicitne odluke.
4. Dodati regresioni test za GUI/API import request contract.
5. Ne mijenjati samu PlanImport semantiku van potrebnog contract usklađenja.

**Dokaz:** `Uvezi plan` iz LIVE GUI-ja šalje validan request koji backend prihvata i obrađuje bez 400 greške zbog naziva polja.

**Ne raditi:** Ne praviti novi import sistem niti novi format plana.

#### FLOW-1106 — Uvesti ovaj plan u FlowOS i potvrditi PlanImport tok

**Rizik:** MEDIUM

Nakon stabilnog LIVE starta i usklađenog parser/import contracta uvesti ovaj Markdown plan kroz postojeći PlanImport tok i koristiti ga kao osnovu za naredne faze.

Završiti FLOW-1105 prije FLOW-1106.

Obavezno:
1. FlowOS projekat mora biti registrovan ili postojeći projekat mora biti pouzdano učitan.
2. Uvesti ovaj Markdown bez ručnog prepisivanja njegovih faza i FLOW stavki.
3. Potvrditi broj parsiranih faza i PlanItem-a.
4. Provjeriti da rizici i kriterijumi prihvatanja dolaze iz Markdown-a.
5. Nejasne sekcije, ako postoje, moraju biti prikazane korisniku umjesto tiho pogađane.
6. FLOW-1101 do FLOW-1105, ako su već završeni prije stvarnog uvoza, uskladiti sa stvarnim stanjem samo na osnovu postojećih commitova, testova, reportova i korisničke potvrde.
7. Ne stvarati retroaktivne Workflow Ledger događaje samo da bi istorija izgledala potpuna; jasno razlikovati prethodni dokazani rad od događaja koje je FlowOS direktno zabilježio nakon uvoza.

**Dokaz:** Plan faza 11–15 je vidljiv u LIVE FlowOS-u, prethodno završene Faza 11 stavke su istinito usklađene bez fabrikovane istorije i plan se može koristiti za praćenje narednog rada.

**Ne raditi:** Ne koristiti AI/LLM da popravlja ili interpretira import.

## Faza 12 — Projekat i Task kao stvarna radna površina

#### FLOW-1201 — Minimalni izbor i registracija projekta

**Rizik:** MEDIUM

Omogućiti korisniku da eksplicitno vidi aktivni projekat, izabere postojeći projekat i doda novi lokalni projekat bez oslanjanja na trenutno ponašanje "uzmi prvi projekat".

Završiti FLOW-1106 prije FLOW-1201.

Obavezno:
1. TopBar mora jasno prikazati aktivni projekat.
2. Mora postojati minimalna akcija `Dodaj projekat`.
3. Izbor projekta mora promijeniti podatke koje učitavaju Plan, Tasks, Sessions i Resume.
4. Ne smije se automatski izvršiti `git init`.
5. Ne smije se izmišljati repo path.

**Dokaz:** Korisnik može dodati ili izabrati FlowOS projekat i nakon izbora dobiti njegove stvarne podatke.

**Ne raditi:** Ne praviti multi-user ili cloud projektnu administraciju.

#### FLOW-1202 — Povezati Zadaci ekran sa stvarnim `/tasks` backendom

**Rizik:** MEDIUM

Postojeći `TasksPage` prestaje biti placeholder i prikazuje stvarne ImplementationTask zapise.

Završiti FLOW-1201 prije FLOW-1202.

Obavezno:
1. Dodati minimalni read API client tok za taskove.
2. Prikazati identitet taska, naslov, status i vezani PlanItem ako postoji.
3. Task bez PlanItem-a mora biti validan i jasno prikazan.
4. Ne tretirati PlanItem kao Task.
5. Ne uvoditi procenat završenosti bez determinističkog izvora.

**Dokaz:** LIVE `Zadaci` ekran prikazuje stvarne Task zapise iz baze i jasno razlikuje Task od PlanItem-a.

**Ne raditi:** Ne praviti kompleksni kanban, prioritization engine ili AI task manager.

#### FLOW-1203 — Napraviti minimalni Task Detail read model

**Rizik:** HIGH

Kreirati read-only backend prikaz jednog Taska koji objedinjuje samo već postojeće i dokazive činjenice potrebne GUI-ju.

Završiti FLOW-1202 prije FLOW-1203.

Obavezno:
1. Task identity i trenutni status.
2. Povezani PlanItem ili jasno `unassigned`.
3. Aktivne i istorijske SessionTaskBinding veze koje su relevantne za Task.
4. Povezane AgentReport metapodatke koji se mogu dokazivo vezati.
5. Workflow Ledger događaje za taj logical Task.
6. Ne spajati sirove agent telemetrijske događaje u canonical workflow istoriju.

**Dokaz:** Jedan read endpoint/service može vratiti konzistentan Task Detail bez AI zaključivanja i bez čitanja live `Task.plan_item_id` kao zamjene za istorijske snapshotove.

**Ne raditi:** Ne mijenjati authority semantiku Phase 3A–3D.

#### FLOW-1204 — Napraviti prvi funkcionalni Task Detail GUI

**Rizik:** MEDIUM

Klik na Task otvara ekran ili panel koji čovjeku pokazuje šta je task, gdje pripada i šta se sa njim do sada desilo.

Završiti FLOW-1203 prije FLOW-1204.

Obavezno:
1. Prikaz Task naziva i statusa.
2. Prikaz veze sa PlanItem-om ili `Nije vezano za plan`.
3. Prikaz trenutno relevantne sesije ako postoji.
4. Prazna stanja moraju biti jasna.
5. GUI ne smije prikazivati tehničke ID-e kao glavnu informaciju ako postoji čitljiv naziv.

**Dokaz:** Korisnik može otvoriti stvarni Task iz `Zadaci` ekrana i razumjeti osnovni kontekst bez gledanja baze ili report fajlova.

**Ne raditi:** Ne implementirati još korisničke workflow odluke u ovoj stavci.

## Faza 13 — Workflow Ledger postaje vidljiv korisniku

#### FLOW-1301 — Izložiti Task workflow history kao read-only tok

**Rizik:** HIGH

Napraviti deterministički Task history prikaz zasnovan na postojećem Workflow Ledgeru.

Završiti FLOW-1203 prije FLOW-1301.

Obavezno:
1. Podržati `IMPLEMENTATION_COMPLETED`.
2. Podržati `TEST_RESULT`.
3. Podržati `REVIEW_COMPLETED`.
4. Podržati `TASK_DECISION`.
5. Događaji moraju biti sortirani po stvarnom vremenu događaja uz stabilan tie-break.
6. Ne pretvarati običan commit, file change ili session close u workflow completion event.

**Dokaz:** Za Task sa postojećim Ledger događajima read model vraća tačnu append-only workflow istoriju.

**Ne raditi:** Ne implementirati FINDING_DECIDED, FIX_COMPLETED, VERIFICATION_COMPLETED ili USER_VALIDATION u ovoj stavci.

#### FLOW-1302 — Prikazati Workflow History na Task Detail ekranu

**Rizik:** MEDIUM

Na Task Detail GUI-ju prikazati ljudski razumljivu vremensku liniju rada.

Završiti FLOW-1301 prije FLOW-1302.

Obavezno:
1. Događaj `IMPLEMENTATION_COMPLETED` prikazati kao završetak implementacione jedinice, ne kao "Task završen".
2. Događaj `TEST_RESULT` prikazati sa PASS/FAIL/TIMEOUT stanjem.
3. Događaj `REVIEW_COMPLETED` prikazati kao završen review, ne kao prihvatanje.
4. Događaj `TASK_DECISION` prikazati kao korisničku odluku.
5. Razlikovati agenta, sistem/mehanički dokaz i korisnika.
6. Tehnički nazivi eventa mogu biti sekundarni, ne glavni tekst.

**Dokaz:** Čovjek može pogledati jedan Task i redom vidjeti šta je implementirano, testirano, pregledano i odlučeno.

**Ne raditi:** Ne uvoditi AI sažetak kao canonical istoriju.

#### FLOW-1303 — Otvaranje reporta i test dokaza iz Task istorije

**Rizik:** MEDIUM

Omogućiti da se iz odgovarajućeg history reda otvori postojeći dokaz bez pravljenja nove authority semantike.

Završiti FLOW-1302 prije FLOW-1303.

Obavezno:
1. Događaj `IMPLEMENTATION_COMPLETED` može otvoriti povezani implementation report ako postoji.
2. Događaj `REVIEW_COMPLETED` može otvoriti povezani review report ako postoji.
3. Događaj `TEST_RESULT` može otvoriti ili prikazati metadata verification artifacta.
4. Nedostajući artifact mora biti prikazan kao nedostupan, ne izmišljen.
5. Report body ostaje evidence, ne Task status authority.

**Dokaz:** Iz Task timeline-a korisnik može doći do stvarnog reporta ili verification dokaza koji stoji iza događaja.

**Ne raditi:** Ne parsirati findings iz Markdown body-ja u ovoj stavci.

#### FLOW-1304 — Razdvojiti workflow istoriju od tehničke aktivnosti

**Rizik:** MEDIUM

Jasno razdvojiti Workflow Ledger događaje od postojećeg `ProjectTimelineService`/file/git aktivnosti.

Završiti FLOW-1302 prije FLOW-1304.

Obavezno:
1. Task workflow history ne smije sadržati obične file watcher događaje.
2. Project-level `Aktivnost` može i dalje prikazivati Git/file/session tragove.
3. UI mora nazivom ili kontekstom jasno pokazati razliku.
4. Ne brisati postojeću tehničku aktivnost ako je korisna za dijagnostiku.

**Dokaz:** Korisnik može razlikovati "šta se workflow-om desilo sa taskom" od "šta se tehnički promijenilo u projektu".

**Ne raditi:** Ne spajati dvije vrste događaja u jednu neoznačenu listu.

## Faza 14 — Korisnička odluka u GUI-ju i prvi pravi dogfooding tok

#### FLOW-1401 — Dodati TASK_DECISION kontrole na Task Detail

**Rizik:** HIGH

Izložiti postojeći Phase 3D authority tok kroz minimalni GUI.

Završiti FLOW-1302 prije FLOW-1401.

Obavezno:
1. Akcija `Prihvati rezultat` mapira se na `ACCEPTED`.
2. Akcija `Vrati u doradu` mapira se na `NEEDS_WORK`.
3. Akcija `Odbaci rezultat` mapira se na `REJECTED`.
4. Korisnik mora jasno vidjeti nad kojim Taskom/report kontekstom donosi odluku.
5. Dupli klik ili retry ne smije proizvesti duplu decision istoriju.
6. Verdict `ACCEPTED` ne smije automatski postaviti PlanItem na DONE/VERIFIED ako backend contract to ne radi.

**Dokaz:** Jedna stvarna korisnička odluka iz GUI-ja kreira tačno očekivani `TASK_DECISION` događaj i osvježen Task timeline.

**Ne raditi:** Ne implementirati USER_VALIDATION pod drugim imenom.

#### FLOW-1402 — Prikazati posljedicu NEEDS_WORK/REJECTED bez skrivene magije

**Rizik:** MEDIUM

GUI mora nakon odluke pokazati stvarno stanje koje je backend deterministički primijenio.

Završiti FLOW-1401 prije FLOW-1402.

Obavezno:
1. Ako historical PlanItem consequence vrati status u `IN_PROGRESS`, GUI to mora osvježiti iz backenda.
2. GUI ne smije lokalno pretpostaviti status prije potvrđenog response-a.
3. Ako decision transakcija padne, korisniku prikazati grešku i ne prikazati lažnu uspješnu odluku.
4. Timeline nakon refresh-a mora odgovarati Ledgeru.

**Dokaz:** NEEDS_WORK i REJECTED se vide kao korisničke odluke, a povezani PlanItem status pokazuje stvarni backend rezultat.

**Ne raditi:** Ne replicirati workflow authority u GUI kodu.

#### FLOW-1403 — Proći jedan kompletan stvarni FlowOS razvojni tok kroz FlowOS

**Rizik:** HIGH

Izabrati jedan mali realni naredni razvojni Task i pratiti ga kroz postojeće mehanizme umjesto kroz ručno rekonstruisanu priču.

Završiti FLOW-1402 prije FLOW-1403.

Obavezno:
1. Task postoji u FlowOS-u.
2. Agentska ili ručna sesija je dokazivo vezana za Task.
3. Implementacioni report je ingestovan.
4. Stvarni verification artifact proizvodi `TEST_RESULT`.
5. Nezavisni review report proizvodi `REVIEW_COMPLETED`.
6. Korisnik iz GUI-ja donosi `TASK_DECISION`.
7. Task Detail timeline prikazuje kompletan niz bez ručnog upisivanja događaja.

**Dokaz:** Jedan stvarni razvojni posao prolazi kroz `IMPLEMENTATION_COMPLETED → TEST_RESULT → REVIEW_COMPLETED → TASK_DECISION` i cijeli tok je vidljiv korisniku u FlowOS GUI-ju.

**Ne raditi:** Ne simulirati cijeli tok hardkodiranim demo podacima.

#### FLOW-1404 — Provjeriti SessionTaskBinding promjenu u stvarnom radu

**Rizik:** HIGH

Namjerno provjeriti ranije izgrađen model gdje jedna AgentSession može tokom rada promijeniti Task binding.

Završiti FLOW-1403 prije FLOW-1404.

Obavezno:
1. Jedna stvarna ili kontrolisana session ima najmanje A → B → A ili A → B → UNASSIGNED istoriju.
2. Binding segmenti moraju ostati istorijski vidljivi.
3. Report povezivanje ne smije prepisati user binding authority.
4. Task history mora pokazati samo događaje koji su dokazivo vezani za odgovarajući logical target.
5. Ne uvoditi AI guess za binding.

**Dokaz:** SessionTaskBinding istorija se može pratiti i ne proizvodi pogrešnu Task/PlanItem atribuciju.

**Ne raditi:** Ne vraćati model "jedna sesija = jedan task".

## Faza 15 — GUI pojednostavljenje na osnovu stvarnog korištenja

#### FLOW-1501 — Evidentirati stvarne UX odluke nakon dogfoodinga

**Rizik:** LOW

Nakon što je Faza 14 stvarno korištena, zapisati šta je korisniku bilo jasno, šta nepotrebno i šta je nedostajalo.

Završiti FLOW-1404 prije FLOW-1501.

Obavezno:
1. Zapisati probleme koji su stvarno uočeni u korištenju.
2. Razdvojiti bug, UX problem i novu funkcionalnu ideju.
3. Ne pretvarati svaku želju odmah u implementaciju.
4. Prioritet dati svakodnevnom Task toku.

**Dokaz:** Postoji kratka lista stvarnih korisničkih odluka zasnovanih na radu sa LIVE aplikacijom, ne samo na mockupu.

**Ne raditi:** Ne uvoditi analytics ili automatsko praćenje ponašanja korisnika.

#### FLOW-1502 — Pojednostaviti glavnu navigaciju

**Rizik:** MEDIUM

Na osnovu stvarnog korištenja odlučiti koje stranice ostaju primarne, a koje postaju sekundarne ili contextualne.

Završiti FLOW-1501 prije FLOW-1502.

Obavezno:
1. Procijeniti `Pregled`, `Zadaci`, `Plan` i `Aktivnost` kao primarne radne površine.
2. Procijeniti `Sesije`, `Agenti` i `Radna stabla` kao tehnički nivo.
3. Procijeniti da li `Konflikti`, `Izvještaji` i `Projekti` trebaju ostati stalne sidebar stavke.
4. Promjena mora proizaći iz stvarnog dogfooding iskustva.
5. Ne uklanjati funkcionalnost bez alternativnog pristupa ako je još potrebna.

**Dokaz:** Sidebar i TopBar odražavaju stvarni svakodnevni tok korisnika i imaju manje nepotrebnih primarnih destinacija.

**Ne raditi:** Ne redizajnirati samo zbog estetike.

#### FLOW-1503 — Ukloniti ili jasno označiti stare mock/placeholder pretpostavke

**Rizik:** MEDIUM

Očistiti GUI mjesta koja korisniku mogu predstavljati hardkodirani ili nepovezani sadržaj kao stvarno stanje sistema.

Završiti FLOW-1502 prije FLOW-1503.

Obavezno:
1. Nema hardkodiranih statistika koje izgledaju kao live podaci.
2. Placeholder ekran mora biti jasno prazan ili označen.
3. Stari mock widget koji nije dio stvarnog composition root toka ne smije zbunjivati održavanje.
4. Ne brisati koristan dokazni/demo kod bez provjere da nije potreban testovima.

**Dokaz:** Ono što GUI prikazuje kao stvarno stanje dolazi iz stvarnog read modela ili je jasno označeno kao prazno/demo stanje.

**Ne raditi:** Ne raditi veliki refactor nevezan za vidljivu konfuziju.

#### FLOW-1504 — Zamrznuti prvi dogfood GUI baseline i odrediti narednu fazu

**Rizik:** LOW

Nakon faza 11–15 napraviti kontrolnu tačku prije novih Workflow Ledger događaja ili većeg GUI razvoja.

Završiti FLOW-1503 prije FLOW-1504.

Obavezno:
1. Snimiti screenshotove glavnih LIVE ekrana.
2. Dokumentovati šta sada stvarno radi.
3. Dokumentovati šta je namjerno odgođeno.
4. Posebno odlučiti da li je sljedeći prioritet structured Findings/FINDING_DECIDED, USER_VALIDATION, napredniji Session prikaz ili druga funkcija.
5. Novi veliki backend događaj ne uvoditi bez ove korisničke procjene.

**Dokaz:** Postoji prihvaćen FlowOS dogfood baseline iz kojeg se može donijeti sljedeća razvojna odluka na osnovu stvarnog korištenja.

**Ne raditi:** Ne proglašavati proizvod završenim samo zato što jedan dogfood tok radi.
