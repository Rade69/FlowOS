# FlowOS — sigurnosni uvidi i preporuke

## Status dokumenta

- Datum pregleda: 2026-08-14
- Vrsta: read-only sigurnosni pregled i hardening preporuke
- Scope: trenutno implementirane lokalne API, runtime, putanje, Git/worktree, agentske i artefaktne granice
- Van scope-a: penetracioni test, audit svake zavisnosti, izmjena produkcijskog koda i tvrdnja da je aplikacija formalno bezbjedna

Ovaj dokument dopunjava sigurnosne odluke iz `docs/FlowOS-novi-detaljan-plan-PySide6.md` i `docs/FlowOS-kompletan-plan.md`. Ne mijenja fazni plan. Preporuke se uvode u odgovarajućoj fazi i tek nakon posebnog task contracta, impact analize i testova.

## Sažetak

FlowOS već ima dobru sigurnosnu osnovu:

- servis sluša samo na `127.0.0.1`;
- nema `shell=True` niti `os.system` u pregledanim produkcijskim izvršnim tokovima;
- subprocess komande koriste liste argumenata;
- Git ostaje autoritet, a integracija je korisnička akcija;
- nema automatskog mergea;
- agent report parser koristi safe YAML loader i stabilni SHA-256/source identity;
- worktree cleanup ima osnovne provjere i retention model;
- SQLite repair koristi backup-first i transakcione provjere;
- logovi i verification artefakti imaju ograničenje veličine i rotaciju.

Najvažniji otvoreni rizici nisu vezani za Python kao jezik, nego za lokalnu granicu povjerenja:

1. HTTP i WebSocket API trenutno nemaju autentikaciju.
2. Agent environment politika propušta potencijalne tajne i ne odgovara komentaru u kodu.
3. Job Object process-tree ownership još nije stvarno implementiran, iako dio koda to tvrdi.
4. Repo/worktree putanje nisu dovoljno strogo kanonizovane i provjerene prije osjetljivih operacija.
5. Worktree cleanup i Git integracijski preflight imaju konkretne sigurnosne nedostatke.
6. Verification servis bi, ako se direktno izloži kroz API, mogao postati arbitrary Python execution granica.
7. Logovi i trajni artefakti nemaju centralnu redakciju tajni.

## Model prijetnji

Primarni model je lokalna single-user Windows aplikacija. FlowOS ne treba pretpostaviti da je svaki lokalni proces pouzdan. Potencijalni izvori rizika su:

- kompromitovan ili zlonamjeran lokalni proces;
- kompromitovan agentski CLI ili MCP alat;
- projekat koji sadrži zlonamjernu verify skriptu, Git hook ili konfiguraciju;
- neispravna, symlinkovana ili junction putanja;
- prompt koji navede agenta na rizičnu akciju;
- tajna ispisana u stdout/stderr, exception ili agent report;
- proces koji ostane živ poslije prividnog cancela;
- lokalna web stranica ili drugi program koji pokušava koristiti loopback API;
- supply-chain kompromitacija Python paketa, build alata ili instalera.

Sigurnosne granice moraju biti sprovedene kodom i OS mehanizmima. Prompt, naziv taska, agentski self-report i sama činjenica da je saobraćaj na loopbacku nisu sigurnosne granice.

---

## P0 — zatvoriti prije šire svakodnevne upotrebe

### 1. Autentikacija lokalnog HTTP i WebSocket API-ja

**Dokaz iz trenutnog koda**

- `src/flowos/service/app.py` binduje Uvicorn na `127.0.0.1`.
- Rute u `src/flowos/service/controllers/http/` nemaju zajedničku auth dependency/middleware provjeru.
- `POST /shutdown` u `controllers/http/system.py` može ugasiti servis bez tokena.
- `controllers/websocket/events.py` prihvata WebSocket konekciju bez autentikacije i Origin provjere.
- `RuntimeManager` već generiše `instance_id`, ali on nije tajna niti se koristi za autorizaciju.

**Rizik**

Svaki lokalni proces koji pronađe port može čitati ili mijenjati FlowOS stanje i ugasiti servis. Loopback smanjuje mrežnu površinu, ali ne razdvaja FlowOS GUI/CLI od drugih lokalnih procesa.

**Preporuka**

- Pri svakom startupu generisati kriptografski nasumičan per-instance bearer token.
- Token čuvati u runtime descriptoru ili posebnom runtime fajlu sa Windows ACL-om samo za trenutnog korisnika.
- GUI i CLI šalju `Authorization: Bearer <token>`.
- Zaštititi sve rute osim minimalnog `/health`; procijeniti da li `/version` može ostati javan.
- WebSocket autentikovati prije `accept()`; token ne stavljati u log ili trajni URL.
- Validirati `Host` i `Origin` za browser/WebSocket scenarije.
- Token rotirati pri svakom restartu i ukloniti pri graceful shutdownu.
- Koristiti constant-time poređenje tokena.

**Acceptance kriteriji**

- Neautentikovan GET/POST/WebSocket zahtjev je odbijen.
- Token prethodne instance ne radi nakon restarta.
- GUI i CLI rade samo s descriptorom trenutne instance.
- Token se ne pojavljuje u logovima, exceptionima, bazi ni test snapshotima.
- Test postoji za shutdown bez tokena i WebSocket bez tokena.

### 2. Windows ACL za runtime, bazu, logove, backup i artefakte

**Dokaz iz trenutnog koda**

Runtime descriptor, SQLite baza, logovi, backup i verification artefakti nalaze se u lokalnim direktorijumima, ali pregledani kod ne postavlja eksplicitne Windows ACL-ove.

**Rizik**

Drugi lokalni korisnik ili proces s nepravilno naslijeđenim pravima može čitati runtime token, privatne putanje, logove, bazu ili backup.

**Preporuka**

- Pri kreiranju FlowOS data root direktorijuma postaviti per-user ACL.
- Nasljeđivanje prava provjeriti za `runtime/`, `data/`, `logs/`, `backups/` i `artifacts/`.
- GUI prije korištenja descriptora provjerava da fajl pripada očekivanom Windows korisniku.
- Razmotriti `Local\\FlowOS_Service_Mutex` umjesto globalnog mutexa ako cross-session single-instance ponašanje nije namjerno.
- Ne spremati secret token u world-readable temp direktorijum.

**Acceptance kriteriji**

- Drugi standardni Windows korisnik ne može pročitati runtime token ni bazu.
- Upgrade ne proširuje postojeća prava pristupa.
- Security test ili instalacijski smoke provjerava ACL ključnih direktorijuma.

### 3. Centralna redakcija tajni

**Dokaz iz trenutnog koda**

- `services/infrastructure/logging.py` rotira logove, ali nema redaction filter.
- `services/verification/service.py` trajno zapisuje stdout i stderr bez redakcije.
- Watcher, Git, parser i subprocess greške mogu završiti u exception logovima.

**Rizik**

API ključevi, bearer tokeni, connection stringovi, privatni ključevi ili osjetljive putanje mogu ostati u logovima i artefaktima duže od agentske sesije.

**Preporuka**

- Uvesti jedan centralni `SecretRedactionFilter` kroz koji prolaze svi trajni logovi i stdout/stderr artefakti.
- Redigovati poznate obrasce i vrijednosti aktivnih secret referencea.
- Redakciju izvršiti prije upisa na disk i prije WebSocket emitovanja.
- Support bundle graditi allowlistom, ne kopiranjem cijelog FlowOS data direktorijuma.
- Definisati retention cleanup za stdout/stderr i velike artefakte.
- Sirovi adapter transport uključivati samo opt-in, vremenski ograničeno i uz upozorenje.

**Acceptance kriteriji**

- Test fixturei s lažnim OpenAI/Anthropic/GitHub tokenima ne ostavljaju original u logu ili artefaktu.
- Stack trace ostaje koristan nakon redakcije.
- Support bundle ne sadrži bazu, runtime token, credential fajlove ni sirove private promptove.

### 4. Ispraviti agent environment politiku

**Dokaz iz trenutnog koda**

`ClaudeCodeAdapter.get_environment()` tvrdi da uklanja API ključeve i tajne, ali propušta sve varijable sa prefiksima `CLAUDE_` i `ANTHROPIC_`. `request.env` takođe prihvata gotovo sve ključeve osim malog blocklista.

**Rizik**

Managed proces može dobiti više tajni i privilegija nego što UI i korisnik očekuju. Blocklist pristup ne može pouzdano prepoznati buduća imena tajni.

**Preporuka**

- Koristiti eksplicitnu allowlistu environment ključeva po adapteru.
- Secret vrijednosti dobavljati iz Windows Credential Managera samo za konkretan launch.
- `request.env` zamijeniti tipiziranim, ograničenim profilom; ne izlagati proizvoljan dict javnom API-ju.
- U audit zapis staviti naziv secret referencea, nikada vrijednost.
- UI mora prikazati kategorije dozvola koje launch dobija.

**Acceptance kriteriji**

- Nasumično postavljena `ANTHROPIC_API_KEY` nije naslijeđena bez eksplicitnog credential bindinga.
- `PATH`, `SYSTEMROOT`, `COMSPEC` i drugi kritični ključevi se ne mogu prepisati zahtjevom.
- Testovi pokrivaju case-insensitive Windows environment nazive.

---

## P1 — zatvoriti prije Managed Executiona

### 5. Stvarni Windows Job Object i iskrene capability vrijednosti

**Dokaz iz trenutnog koda**

`AgentProcessLauncher` koristi `CREATE_NEW_PROCESS_GROUP`, a `kill_process_tree()` poziva `TerminateProcess` nad jednim PID-om. Ne kreira Job Object niti dokazuje ownership cijelog process treeja, iako docstring to tvrdi. Adapter vraća `can_cancel=True`.

**Rizik**

Child ili grandchild proces može ostati živ poslije prikazanog cancela. PID sam nije dovoljan identitet nakon restarta.

**Preporuka**

- Za FlowOS-managed procese kreirati Job Object i odmah vezati child proces.
- Čuvati PID, process creation time i vrstu ownershipa.
- Razdvojiti `cancel_requested`, `termination_in_progress` i `process_exit_confirmed`.
- Dok Job Object nije implementiran, ne prikazivati cancel kao potvrđenu process-tree kontrolu.
- `EXTERNAL_TRACKED` nikad ne dobija ovu capability.

**Acceptance kriteriji**

- Fault-injection test pokreće child i grandchild proces i potvrđuje njihovo gašenje.
- Restart recovery ne preuzima novi proces koji je reciklirao isti PID.
- GUI razlikuje prihvaćen cancel od potvrđenog izlaza.

### 6. Zabraniti sirove `extra_args` na javnoj granici

**Dokaz iz trenutnog koda**

`AgentRequest.extra_args` se bez validacije dodaje agentskoj komandi. Korištenje argument liste sprečava shell injection, ali ne sprečava agent-CLI option injection.

**Rizik**

Budući API ili workflow može uključiti permission-bypass, drugi working directory, mrežne opcije ili druge rizične agent-specifične flagove.

**Preporuka**

- Javni ugovor treba nuditi imenovane i tipizirane opcije.
- Adapter jedini prevodi te opcije u CLI argumente.
- Standardni profil odbija permission-bypass flagove.
- Rizični profil mora biti eksplicitno označen i zahtijevati approval.

**Acceptance kriteriji**

- Nepoznata opcija se odbija prije launch-a.
- Test dokazuje da task tekst ostaje jedan argument i ne postaje shell komanda.
- Effective capability zavisi od adaptera, session moda, runtime handlea i trenutnog stanja.

### 7. Zaključati verification execution granicu

**Dokaz iz trenutnog koda**

HTTP endpoint trenutno ne pokreće verifikaciju, ali `VerificationService.run_verify()` prihvata `repo_path` i opcioni `verify_path`, zatim pokreće taj Python fajl preko `sys.executable`.

**Rizik**

Ako se servis direktno izloži kroz API, može postati arbitrary Python execution mehanizam.

**Preporuka**

- Dozvoliti samo registrovani projekat.
- Podrazumijevana skripta mora biti tačno `<canonical_repo>/scripts/verify.py`.
- Ne izlagati custom verify path u prvom API ugovoru.
- Odbiti symlink/junction izlazak iz repozitorijuma.
- Prije izvršenja zabilježiti Git commit SHA i SHA-256 skripte.
- Prvi put za nepoznatu skriptu zahtijevati korisnički approval.
- Koristiti filtriran environment, timeout, output limit i Job Object.

**Acceptance kriteriji**

- Skripta izvan repozitorijuma i symlink prema vani su odbijeni.
- Verification artefakt sadrži commit SHA, script SHA-256, exit code i trajanje.
- Timeout gasi cijelo managed process stablo.

### 8. Stroga validacija repo i worktree putanja

**Dokaz iz trenutnog koda**

`ProjectCreate.repo_path` provjerava samo da je putanja apsolutna. `WorktreeService` koristi normalizaciju u konstruktoru, ali ne postoji jedinstvena sigurnosna funkcija koja potvrđuje Git root, managed root i reparse-point granice.

**Rizik**

Može se registrovati filesystem root, profil korisnika, osjetljiv direktorijum ili junction prema neočekivanoj lokaciji. Watcher i kasnije izvršne operacije tada dobijaju preširok scope.

**Preporuka**

- Centralizovati `canonicalize_and_validate_repo_path()` u backend infrastructure sloju.
- Potvrditi postojanje direktorijuma, Git working tree i stvarni Git root.
- Odbiti filesystem root i kritične sistemske direktorijume.
- Detektovati junction/reparse-point promjene granice.
- Korisniku prije registracije prikazati kanonizovanu finalnu putanju.
- Watcher dobija eksplicitni project root i nikad ne prati njegovog roditelja.

**Acceptance kriteriji**

- `C:\\`, `%USERPROFILE%` bez konkretnog repoa i sistemski direktorijumi su odbijeni.
- Validan repo kroz dozvoljenu normalizaciju radi.
- Junction iz registrovanog repoa prema osjetljivom direktorijumu ne proširuje watcher ili artifact scope.

### 9. Siguran worktree identitet i cleanup

**Dokaz iz trenutnog koda**

`WorktreeService._find_worktree()` koristi `wt.path == path or wt.path.startswith(path)`. Prefix nije dokaz identiteta; npr. `...\\a` i `...\\ab` mogu se pogrešno povezati. `force=True` može zaobići dio cleanup provjera.

**Rizik**

Pogrešan ili dirty worktree može biti uklonjen, uključujući djelimičan korisnički rad.

**Preporuka**

- Koristiti tačnu jednakost kanonizovanih putanja.
- Potvrditi da je cilj u aktuelnom `git worktree list --porcelain` rezultatu.
- Potvrditi da je unutar FlowOS-managed worktree root direktorijuma.
- Prije cleanupa ponovo očitati Git status, aktivne sesije i žive managed procese.
- Force cleanup zahtijeva eksplicitni approval i prikaz dirty/untracked fajlova.
- Prije destruktivne akcije sačuvati patch ili drugi recovery artefakt kada je moguće.
- Cleanup, archive i release writer lock ostaju odvojene operacije.

**Acceptance kriteriji**

- Prefix-kolizija putanja ne može izabrati drugi worktree.
- Main worktree, aktivan writer, živ proces i worktree izvan managed roota se ne mogu obrisati.
- Force akcija je auditirana i ne može se pozvati običnim background tokom.

### 10. Validacija Git refova i uklanjanje skrivenih mrežnih akcija

**Dokaz iz trenutnog koda**

- Branch se gradi iz `task_id` i minimalno očišćenog sluga.
- `base_branch` prolazi prema Git komandama bez `git check-ref-format` validacije.
- `get_diff_to_base()` pokušava `git fetch origin <base_branch>` i potiskuje grešku, iako operacija izgleda kao read-only integracijski preflight.

**Rizik**

Nevalidni ili zlonamjerno oblikovani Git refovi mogu promijeniti značenje komande. Skriveni fetch uvodi mrežni side effect bez approvala i može korisniku dati nejasnu informaciju o svježini rezultata.

**Preporuka**

- Validirati sve branch/ref vrijednosti preko `git check-ref-format --branch` i dodatne aplikacijske allowliste.
- Ograničiti task ID i slug na kontrolisan skup znakova.
- Koristiti `--` separator gdje ga Git komanda podržava.
- Integracijski preflight podrazumijevano koristi lokalne refove.
- “Osvježi sa origin-a” treba biti posebna, korisnički potvrđena mrežna akcija.
- Rezultat prikazuje tačan base SHA i da li je remote osvježen.

**Acceptance kriteriji**

- Ref sa newlineom, kontrolnim znakom ili option-like vrijednošću je odbijen.
- Read-only prepare ne pristupa mreži.
- Fetch failure nije predstavljen kao svjež remote rezultat.

---

## P2 — hardening prije distribucije

### 11. Tipizirani API ugovori i resource limiti

Neki kontroleri primaju slobodne `dict` payloadove. Potrebno je:

- Pydantic model za svaki mutirajući endpoint;
- maksimalna dužina stringova, lista i Markdown sadržaja;
- globalni HTTP body-size limit;
- maksimalna veličina WebSocket poruke;
- limit broja WebSocket klijenata;
- bounded event queue;
- concurrency limit za Git scan, process scan, verification i budući agent launch;
- timeout za svaku subprocess operaciju.

### 12. Sigurniji AgentReport ingestion

Postojeći ingestion je konzervativan i ne nagađa identitet, ali treba dodati:

- maksimalnu veličinu fajla prije `read_bytes()`;
- odbranu od symlink/junction racea između provjere putanje i čitanja;
- potvrdu finalne otvorene putanje;
- ograničenje YAML front matter veličine i dubine;
- izbjegavanje punog osjetljivog sadržaja u parser greškama i logovima.

### 13. Supply-chain i release sigurnost

- Pinovati direktne i tranzitivne Python zavisnosti uz hashove.
- Generisati SBOM za svaki release.
- Pokretati dependency vulnerability scan i secret scan.
- Dokumentovati provenance build alata i verzija.
- Potpisati `flowos-service.exe`, `flowos-gui.exe`, `flowos.exe` i installer.
- Objaviti SHA-256 release artefakata.
- Updater, ako se uvede, mora provjeravati potpis i ne smije izvršavati nepotpisan payload.
- Build i installer ne smiju uključiti `.env`, bazu, logove, backup, artefakte ni lokalne credential fajlove.

### 14. Backup, restore i incident recovery

- Nastaviti koristiti SQLite backup API ili drugi konzistentan SQLite mehanizam, ne raw kopiju aktivne WAL baze.
- Svaki backup treba manifest: metod, timestamp, source DB hash gdje je primjenjivo, aplikacijska i schema verzija.
- Periodično testirati otvaranje i restore kopije.
- Destruktivna DB operacija se prekida ako backup ili preflight ne uspije.
- Dokumentovati recovery postupak za oštećen runtime descriptor, bazu i napuštene worktreeje.

### 15. Security regression suite

Minimalni sigurnosni test paket treba obuhvatiti:

- HTTP i WebSocket auth bypass pokušaje;
- stale instance token;
- log/artifact secret redaction;
- environment secret inheritance;
- repo/worktree path traversal, prefix collision, symlink i junction slučajeve;
- dirty/active worktree cleanup refusal;
- Git ref/argument injection;
- verification skriptu izvan repozitorijuma;
- child/grandchild cancel kroz Job Object;
- oversized request, report i WebSocket poruku;
- SQLite backup/restore;
- startup recovery poslije nasilnog prekida servisa.

Za sigurnosne promjene obavezni su nezavisni review i pokušaj obaranja zaštite, ne samo happy-path test.

---

## Pozitivni obrasci koje treba sačuvati

1. Backend ostaje jedini vlasnik baze, Git operacija, watchera i agentskih procesa.
2. GUI ostaje View → Controller → Services i ne dobija subprocess/Git/DB logiku.
3. Servis ostaje loopback-only.
4. Nema proizvoljnog shell alata iz Corea.
5. Subprocess koristi argument listu, nikada shell string.
6. `EXTERNAL_TRACKED` ne dobija lažne process-control capabilityje.
7. Jedan writable worktree ima najviše jednu writer sesiju.
8. Git ostaje autoritet, bez automatskog mergea.
9. Filesystem/Git događaji ostaju dokaz aktivnosti, a ownership je samo hint.
10. Managed, Durable, Observability i verifier ostaju odvojeni i fazno uvedeni.
11. Ne čuva se privatno rezonovanje modela niti token-by-token replay.
12. Ne uvode se remote workeri, containeri, broker ili multi-user sigurnosne tvrdnje prije stvarne potrebe.

## Predloženi redoslijed realizacije

### Sigurnosni paket A — lokalna kontrolna granica

1. Per-instance API token.
2. HTTP/WebSocket auth middleware.
3. Runtime/data ACL.
4. Centralna redakcija tajni.
5. Tipizirani i ograničeni API payloadovi.

Ovaj paket treba završiti prije nego što se broj mutirajućih endpointa i svakodnevnih korisničkih podataka značajno poveća.

### Sigurnosni paket B — putanje i Git/worktree

1. Centralna canonical path validacija.
2. Exact worktree identity.
3. Managed-root i reparse-point provjere.
4. Force-cleanup approval i recovery artefakt.
5. Git ref validacija.
6. Uklanjanje implicitnog fetcha iz read-only preflighta.

### Sigurnosni paket C — Managed Execution gate

1. Stvarni Windows Job Object.
2. PID + creation-time identity.
3. Iskrene effective capability vrijednosti.
4. Environment allowlista i Credential Manager.
5. Tipizirane agent opcije bez sirovih `extra_args`.
6. Zaključan verification execution.
7. Fault-injection process-tree testovi.

### Sigurnosni paket D — distribucija

1. Dependency lock + hashovi.
2. SBOM i vulnerability scan.
3. Potpisani EXE/installer artefakti.
4. Release hashovi i provenance.
5. Backup/restore i incident runbook.

## Sigurnosna pozicija proizvoda

Tehnički precizna javna tvrdnja može biti:

> FlowOS je local-first, single-user Windows aplikacija bez obaveznog cloud control planea i bez cloud telemetrije. Projektni podaci ostaju lokalno, servis sluša samo na loopbacku, Git ostaje autoritet, a rizične i spoljašnje akcije zahtijevaju eksplicitnu kontrolu korisnika.

Ne treba tvrditi da FlowOS “nema trećih strana” ili da je automatski bezbjedan zato što je napisan u Pythonu. FlowOS koristi third-party biblioteke i spoljašnje agentske CLI-jeve. Njegova realna sigurnosna prednost treba da proizlazi iz:

- male i eksplicitne mrežne površine;
- lokalnog čuvanja podataka;
- stroge kontrole putanja, procesa i capabilityja;
- odsustva automatskog mergea i skrivenih side effecta;
- redakcije i minimalnog zadržavanja osjetljivih podataka;
- provjerljivih Git i test dokaza;
- potpisanog i auditabilnog release procesa.

## Zaključak

Najvažniji naredni sigurnosni posao je zatvaranje lokalnog API-ja per-instance autentikacijom, zatim redakcija tajni i stroga validacija repo/worktree putanja. Prije Managed Executiona moraju biti dokazani Job Object process-tree ownership, filtriran environment, zaključan verification tok i iskrene capability vrijednosti.

Ove mjere ne zahtijevaju promjenu FlowOS arhitekture. Naprotiv, direktno jačaju postojeći PySide6 → Controller → GUI Services → loopback FastAPI → backend Services model i zadržavaju fokus na lokalnom, jednostavnom i pouzdanom alatu za samostalnog developera.
