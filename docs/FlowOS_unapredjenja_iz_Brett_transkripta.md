# FlowOS unapređenja izvedena iz Brettovog transkripta

**Status dokumenta:** izvedena produktno-arhitektonska analiza  
**Jezik:** srpski, latinica  
**Namjena:** preporuke za preciziranje postojećeg FlowOS roadmapa, bez stvaranja novog izvora istine  
**Osnovna granica:** AI može pomagati u tehničkom izvršenju i objašnjenju, ali ne dobija authority nad workflowom, scope-om, verifikacijom, prihvatanjem ni integracijom.

## 1. Izvršni sažetak

Brettov transkript nije dokaz da AI kodiranje treba odbaciti. On je vrijedan kao kvalitativni opis neuspjeha koji nastaju kada brzina generisanja nadmaši ljudsku sposobnost da razumije, pregleda i preuzme odgovornost za promjenu.

Najvažnija poruka za FlowOS je:

> **Ograničavajući resurs agentskog razvoja nije broj generisanih linija, nego ljudski budžet razumijevanja, pažnje i odgovornosti.**

FlowOS zato ne treba optimizovati za maksimalni output ili broj paralelnih agenata. Treba optimizovati za to da čovjek može brzo i pouzdano odgovoriti:

- šta je promijenjeno i zašto;
- koji diff je relevantan;
- koji dokaz podržava koju tvrdnju;
- šta je samo implementirano, šta je verificirano, a šta je prihvaćeno;
- gdje postoji rizik, nejasnoća ili odluka;
- koliko rada korisnik zaista razumije prije nego što ga prihvati.

Većina ovoga nije novi pravac. Transkript uglavnom potvrđuje postojeće FlowOS odluke: deterministički observer, evidence ledger, odvojeni implementer i verifier, korisnički authority, Task Detail read-model, workflow history, otvaranje dokaza, dogfooding i naknadno pojednostavljenje GUI-ja.

Najvažnija preporuka za MVP glasi:

> **Ne širiti roadmap. U postojećim FLOW-1203, FLOW-1204, FLOW-1301–1304, FLOW-1401–1403 i FLOW-1501–1504 zaoštriti acceptance prema razumljivosti, evidence navigaciji i ljudskoj odluci.**

## 2. Relevantnost transkripta i granice zaključivanja

Transkript je lično iskustvo jednog iskusnog developera. Njegove tvrdnje o emocionalnom stanju, uživanju u radu, učenju i osjećaju otuđenja treba tretirati kao kvalitativni signal, ne kao univerzalnu empirijsku činjenicu.

Ipak, opisuje nekoliko konkretnih i provjerljivih produktnih rizika:

1. Agent može proizvesti više koda nego što čovjek može ozbiljno pregledati.
2. Površan review postaje vjerovatniji kako diff raste i kako korisnik gubi mentalni model.
3. Lako generisanje ohrabruje funkcije koje nisu dovoljno važne da bi ih čovjek ručno opravdao.
4. Uklanjanje svakog „dosadnog“ koraka može sakriti ponovljeni dizajnerski bol koji bi inače doveo do bolje apstrakcije.
5. Gotov odgovor može smanjiti dubinu učenja ako korisnik ne mora rekonstruisati razlog, ograničenja i primjenu.
6. Produktivnost mjerena količinom outputa može pogoršati kvalitet proizvoda i iskustvo developera.

FlowOS ne treba pokušati dokazati ili osporiti Brettovu etičku odluku. Relevantan zadatak je da sistem omogući korisniku da koristi agente bez gubitka kontrole, razumijevanja i jasnog vlasništva nad rezultatom.

## 3. (1) Potvrda postojećih FlowOS ideja

### 3.1. Human comprehension/attention budget je stvarni sistemski limit

Postojeći FlowOS pravac već prepoznaje da čovjeku treba prikaz „Gdje si stao“, „Zahtijeva pažnju“, Task Detail i dokazni paket. Brettov opis potvrđuje da to nije samo UX pogodnost nego sigurnosna i kvalitativna granica.

FlowOS treba tretirati ljudsku pažnju kao ograničen budžet:

```text
agentski output
→ deterministička atribucija i grupisanje po Tasku
→ relevantni diff i evidence
→ mali broj jasnih odluka
→ ljudsko prihvatanje
```

Ne treba uvoditi novu baznu tabelu ili globalni „attention score“. Za MVP je dovoljno da postojeći read-model izvede listu konkretnih stavki koje traže pažnju: neprovjeren rezultat, pali test, review nalaz, nedostajući artefakt, scope drift, konflikt ili odluka koja čeka korisnika.

### 3.2. Razdvajanje `IMPLEMENTED / VERIFIED / ACCEPTED`

Ovo je direktna potvrda već prihvaćene FlowOS filozofije:

- **IMPLEMENTED**: postoji konkretna promjena i implementer tvrdi da je rad završen; diff/report je dokaz postojanja rada, ne kvaliteta.
- **VERIFIED**: definisana provjera je izvršena i rezultat je potkrijepljen dokazom; za rizičan rad implementerov self-check nije dovoljan.
- **ACCEPTED**: korisnik je donio authority odluku da rezultat zadovoljava namjeru i produktni standard.

Ova stanja ne smiju biti svedena na jednu zelenu oznaku „Done“. Posebno:

```text
IMPLEMENTED ≠ VERIFIED ≠ ACCEPTED
```

Test koji je pokrenuo implementer jeste evidence, ali ne mora biti nezavisna verifikacija. Uspješan review nije automatski produktno prihvatanje. `ACCEPTED` ne smije lažirati `VERIFIED` niti automatski značiti integraciju.

### 3.3. Evidence i relevantni diff umjesto agentskog uvjeravanja

Brettov problem nije riješen dužim AI sažetkom. Čovjek mora moći preći od tvrdnje do primarnog dokaza:

```text
tvrdnja/status
→ konkretan workflow događaj
→ povezani diff/commit/report/test artefakt
→ relevantni segment, uz mogućnost otvaranja cjeline
```

To potvrđuje `FLOW-1303` i pravilo da report ostaje evidence, a ne authority. FlowOS treba da usmjeri korisnika na promjenu koja je bitna za odluku, ali ne smije sakriti puni diff.

Minimalni prikaz uz svaku odluku treba pokazati:

- Task i scope;
- šta se promijenilo;
- veličinu i pogođene komponente diffa;
- verifikacije i stvarne rezultate;
- review nalaze i njihov status;
- šta nije provjereno;
- linkove ka punom diffu, reportu i artefaktu.

### 3.4. Progressive context shaping kao deterministička projekcija

Postojeći koncept je ispravan: agent ne treba cijeli transcript i sve stare izvještaje. Treba mali, svjež kontekst izveden iz trenutnog canonical stanja, sa referencama ka dubljim izvorima.

```text
canonical podaci + Git + ledger + evidence
→ deterministički read-model
→ fokusiran prikaz za čovjeka ili agenta
→ otvaranje detalja po potrebi
```

Stara tvrdnja ostaje istorija, ali ne ostaje aktivna samo zato što se nalazi u starijem dokumentu. To smanjuje context overload i rizik da agent nastavi po zastarjeloj odluci.

### 3.5. Agent context dokument je projekcija, ne source of truth

`AGENTS.md` i kanonski plan definišu trajna pravila i authority. Event Ledger, baza, Git, testovi i korisničke odluke nose stvarno stanje. Generisani `AGENT_CONTEXT`/`CURRENT_WORK_STATE` dokument smije biti samo regenerabilan izlaz.

Obavezne osobine:

- brisanje dokumenta ne smije izgubiti stanje;
- ručna izmjena dokumenta ne smije promijeniti workflow;
- dokument sadrži aktivni cilj, scope, status, relevantnu odluku, evidence stanje, blocker i reference;
- puna istorija se ne kopira u dokument;
- kontradikcija se prikazuje kao problem za razrješenje, ne „rješava“ LLM nagađanjem.

Ovo treba uklopiti u postojeći `FLOW-1203` read-model i kasnije renderovati kroz postojeće površine. Konceptualni naziv „Phase 3E“ iz arhivske analize ne treba pretvarati u novu roadmap fazu ili novi izvor statusa.

### 3.6. Ograničena autonomija već odgovara pravom modelu

ADR-001 već postavlja dobru granicu:

```text
čovjek odlučuje šta i zašto
FlowOS kontroliše kada, gdje i pod kojim pravilima
agent odlučuje kako da izvrši dodijeljeni tehnički zadatak
```

Brettov opis „full agentic“ otuđenja potvrđuje vrijednost režima `Scoped Write / Managed Execution`, odvojenog worktreeja, determinističke verifikacije i završetka u `READY_FOR_REVIEW`, bez automatskog prihvatanja ili mergea.

### 3.7. Humanist/product-quality fokus

FlowOS već zabranjuje izmišljene procente napretka i zahtijeva dokaz. To treba proširiti na produktnu interpretaciju uspjeha:

- manje vremena za rekonstrukciju stanja;
- manje nepročitanog ili nerazumljivog diffa;
- veći udio verificiranog rada koji korisnik razumije i prihvata;
- manje reworka izazvanog scope driftom ili feature bloatom;
- kvalitet odluke, ne broj agentskih sesija ili generisanih linija.

Ovo ne zahtijeva novu telemetrijsku infrastrukturu. Dogfooding bilješke iz `FLOW-1501` mogu prvo dati dovoljan kvalitativni dokaz.

## 4. (2) Male korekcije postojeće filozofije

### 4.1. Autonomiju ograničiti i razumljivošću, ne samo tehničkim rizikom

Postojeći model dobro ograničava agente prema scope-u, side effectima i tehničkom riziku. Mala, ali važna korekcija je da dozvoljeni obim autonomnog rada zavisi i od toga koliko rezultat čovjek može smisleno pregledati.

Praktično pravilo:

- **nizak rizik + mali, lokalni i lako verificiran diff:** agent može samostalno izvršiti puni tehnički korak unutar TaskContracta;
- **srednji rizik ili širok diff:** rad se dijeli na pregledive cjeline/checkpointove;
- **visok rizik, slab evidence ili diff koji korisnik ne može razumjeti u razumnom pregledu:** agent staje prije sljedeće cjeline i vraća kontrolu;
- **promjena scope-a, acceptance kriterija ili arhitekture:** uvijek ljudska odluka.

Ne treba praviti opštu numeričku risk matricu, što je već namjerno odgođeno. Dovoljni su jasni scope/evidence gateovi i mogućnost da korisnik smanji veličinu narednog koraka.

### 4.2. Review overload rješavati smanjenjem i usmjeravanjem, ne AI presudom

FlowOS ne treba „riješiti“ hiljade linija diffa tako što drugi model kaže da je sve u redu. Bolji tok je:

1. grupisati promjene po Tasku i namjeri;
2. označiti files/komponente van deklarisanog scope-a;
3. prvo pokazati rizične i behavior-changing dijelove;
4. vezati svaki acceptance kriterij za evidence;
5. omogućiti otvaranje punog diffa;
6. kada je diff prevelik, tražiti podjelu rada ili dodatni review, ne automatsko odobrenje.

AI može opcionalno objasniti diff nakon determinističkog grupisanja, ali njegovo objašnjenje nije dokaz niti verdict.

### 4.3. Feature bloat tretirati kao scope drift

AI čini dodatne funkcije jeftinim za generisanje, ali ne i jeftinim za održavanje, testiranje i razumijevanje. FlowOS zato treba da učini neplanirani rad vidljivim.

Bez novog event sistema, postojeći TaskContract i diff mogu podržati tri jasna ishoda:

- promjena je unutar scope-a;
- promjena je potrebna da bi acceptance kriterij radio, ali zahtijeva objašnjenje;
- promjena je dodatna funkcija i vraća se korisniku kao prijedlog, ne ulazi prećutno u rezultat.

Agent ne smije proširiti scope zato što je dodatak „lak“. `FLOW-1501` treba bilježiti da li je tokom dogfoodinga korisnik mogao prepoznati i odbiti nepotreban output.

### 4.4. „Tedious“ rad sačuvati kao signal za apstrakciju

Brettov važan uvid je da ponavljanje i trenje ponekad otkrivaju loš dizajn. Ako AI stalno generiše isti boilerplate, bol nestaje iz korisnikovog iskustva, ali tehnički dug ostaje.

FlowOS ne treba zabraniti automatizaciju dosadnog rada. Treba razlikovati:

- **mehaničko ponavljanje sa stabilnim pravilom** — kandidat za deterministički alat, generator ili refactor;
- **ponavljanje koje zahtijeva stalne izuzetke** — signal da apstrakcija ili granica domena nije dobra;
- **jednokratni dosadan korak** — vjerovatno nije dovoljan razlog za novu infrastrukturu.

Mala korekcija workflowa: report/review može evidentirati „ponovljeni rad / kandidat za apstrakciju“ kao običan finding ili follow-up prijedlog. Ne treba novi FLOW broj, event ni automatsko refaktorisanje. Odluku donosi korisnik nakon najmanje nekoliko stvarnih ponavljanja.

### 4.5. Sprječavanje deskillinga i otuđenja od koda

FlowOS ne treba paternalistički prisiljavati korisnika da ručno piše kod. Treba omogućiti način rada koji čuva aktivno razumijevanje:

- prije prihvatanja pokazati „šta se ponašajno promijenilo“ i „zašto je ovo rješenje izabrano“;
- uz evidence pokazati i ograničenja/neprovjerene pretpostavke;
- ponuditi korisniku da označi dio diffa koji želi sam implementirati ili detaljno pregledati;
- za novi/ključni modul zahtijevati kraći korak i jači handoff;
- omogućiti da agent objašnjava kroz reference na stvarni kod i dokumentaciju, ne samo kroz gotov odgovor;
- ne skrivati originalnu dokumentaciju, source i puni diff iza AI sažetka.

Najbolji antidot otuđenju nije još jedan dashboard, nego kratka putanja od namjere do konkretnog koda i dokaza.

### 4.6. Attention Projection ne smije postati novi veliki podsistem

Koncept „Human Attention State“ je koristan, ali u MVP-u treba biti samo drugi prikaz podataka koje `FLOW-1203`, `FLOW-1301` i `FLOW-1303` već daju.

Minimalna pravila prioriteta mogu biti deterministička:

1. blokirajuća/rizična odluka;
2. pali ili nedostajući dokaz;
3. review nalaz koji čeka korisnika;
4. implementirano ali nije verificirano;
5. verificirano ali nije prihvaćeno;
6. informativna tehnička aktivnost.

Ne uvoditi AI prioritization engine niti zasebnu ručno održavanu attention listu.

## 5. Konkretno roadmap mapiranje bez novih izvora istine

| Postojeća stavka | Kako Brettovi uvidi preciziraju postojeći scope | Prioritet |
|---|---|---|
| `FLOW-1203` Minimalni Task Detail read model | Read-model treba eksplicitno izložiti trenutni workflow status, vezu ka relevantnom diff/report/test evidenceu, nejasnoće i posljednju authority odluku. Ako `IMPLEMENTED/VERIFIED/ACCEPTED` nisu svi već canonical dostupni, ne izmišljati ih; prikazati dokazive komponente i praznine. | P0 |
| `FLOW-1204` Task Detail GUI | Prvi ekran treba odgovoriti „šta je ovo, šta se promijenilo, šta je dokazano i šta traži moju pažnju“, uz progressive disclosure. Ne zatrpavati korisnika svim eventima i tehničkim ID-jevima. | P0 |
| `FLOW-1301` Workflow history read-only | Zadržati strogu semantiku događaja. Ne pretvarati activity, commit ili agentovu tvrdnju u completion/acceptance. Stabilna istorija omogućava da current prikaz bude projekcija, ne novi zapis. | P0 |
| `FLOW-1302` Workflow History GUI | Vizuelno i jezički razdvojiti implementaciju, mehanički dokaz, review i korisničku odluku. Timeline treba voditi razumijevanje, ne slaviti količinu outputa. | P0 |
| `FLOW-1303` Otvaranje reporta i test dokaza | Dodati najkraću navigacionu putanju od tvrdnje do relevantnog evidencea i punog izvora. Nedostajući dokaz mora biti vidljiv. Report ne postaje authority. | P0 |
| `FLOW-1304` Workflow vs tehnička aktivnost | Ovo je ključna zaštita attention budgeta: workflow događaji ostaju primarni za odluke, dok su file/git/session detalji sekundarni dijagnostički nivo. | P0 |
| `FLOW-1401` TASK_DECISION kontrole | Prije odluke prikazati kontekst: Task, rezultat, verification/review stanje, relevantni diff/evidence i šta nije provjereno. Korisnik ostaje authority. | P0 |
| `FLOW-1402` Posljedice odluke | Backend-confirmed state sprečava da UI ili AI izmisli uspjeh. Posebno jasno prikazati da `ACCEPTED` nije zamjena za nedostajući `VERIFIED`. | P0 |
| `FLOW-1403` Kompletan dogfooding tok | Dogfood test treba mjeriti razumljivost: može li korisnik bez ručne rekonstrukcije objasniti promjenu, pronaći dokaz, razlikovati tri stanja i donijeti odluku. | P0 |
| `FLOW-1404` SessionTaskBinding | Istorijska atribucija čuva vezu između koda i stvarne namjere. Bez nje relevantni diff/context može biti pogrešno usmjeren. | P1 |
| `FLOW-1501` Stvarne UX odluke | Evidentirati review overload, nejasan evidence, nepotrebne prikaze, feature bloat i trenutke gubitka mentalnog modela. Bez analytics podsistema; kratke kvalitativne bilješke su dovoljne. | P0 nakon dogfoodinga |
| `FLOW-1502` Navigacija | Primarne površine organizovati oko Taska, pažnje i odluke; tehničke površine ostaviti dostupne kao drugi nivo. | P1 |
| `FLOW-1503` Placeholder čišćenje | Svaki prikaz koji izgleda autoritativno mora dolaziti iz stvarnog read-modela ili biti jasno označen. Ovo uključuje AI sažetke i procente bez determinističkog izvora. | P1 |
| `FLOW-1504` Dogfood baseline | Prije novih Ledger događaja ili većeg GUI rada odlučiti, na osnovu korištenja, da li je sljedeći problem findings, validation ili razumljivost/evidence navigacija. | P0 gate |

### Roadmap pravilo

Ovaj dokument ne mijenja redoslijed roadmapa i ne proglašava nove stavke. Ako neka preporuka zahtijeva promjenu acceptance kriterija, ona treba biti unesena samo u kanonski roadmap/tracker kroz postojeću proceduru i korisničku odluku. Ovaj fajl ostaje obrazloženje i input za tu odluku.

## 6. Minimalni P0 acceptance dodatak za dogfooding

Bez novih modela i eventova, `FLOW-1403` se može smatrati uspješnim sa aspekta Brettovih rizika ako korisnik može:

1. otvoriti jedan stvarni Task;
2. u kratkom pregledu reći koja je namjera i scope;
3. pronaći relevantni diff ili povezani report;
4. pronaći stvarni test/review evidence;
5. jasno razlikovati implementirano, verificirano i prihvaćeno;
6. vidjeti šta nije provjereno ili šta nedostaje;
7. donijeti `ACCEPTED / NEEDS_WORK / REJECTED` odluku bez oslanjanja na agentsko uvjeravanje;
8. nakon odluke vidjeti backend-confirmed current state;
9. nastaviti novom sesijom iz malog, svježeg konteksta bez čitanja cijele istorije;
10. prepoznati promjenu van scope-a ili nepotrebnu funkcionalnost.

Ako je za ovo potrebno ručno otvarati bazu, pretraživati deset reportova ili vjerovati AI sažetku, tok još nije ispunio svoju glavnu produktnu svrhu.

## 7. (3) Buduće ideje van MVP-a

Sljedeće ideje imaju smisla tek nakon faza 11–15 i stvarnog dogfooding dokaza. Ne treba ih sada pretvarati u roadmap obaveze.

### 7.1. Review budget i promjenjivi autonomy envelope

FlowOS bi kasnije mogao preporučiti manji checkpoint kada kombinacija diffa, pogođenih komponenti, slabog evidencea i rizika pređe korisnikov deklarisani review kapacitet. To mora ostati preporuka/policy, ne AI authority.

### 7.2. Comprehension checkpoint

Za visoko rizične promjene korisnik bi mogao eksplicitno potvrditi da je pregledao ključni diff/evidence prije acceptancea. Ovo ne treba postati birokratski klik za svaki mali Task.

### 7.3. Learning/craft režim

Opcioni režim bi mogao tražiti da agent prvo pokaže dokumentaciju, relevantni source i trag zaključivanja kroz provjerljive korake, ili da prepusti korisniku dio implementacije. Režim mora biti korisnički izbor, ne moralna procjena sistema.

### 7.4. Detekcija ponovljenog „tedious“ obrasca

Iz više stvarnih taskova sistem bi mogao prikazati da se isti boilerplate ili isti review finding ponavlja i predložiti poseban refactor Task. Ne smije automatski napraviti apstrakciju ili proširiti trenutni scope.

### 7.5. Opciono AI objašnjenje nakon determinističkog read-modela

AI može sažeti diff, objasniti vezu evidencea i acceptance kriterija ili prilagoditi dubinu prikaza korisniku. Uvijek mora biti jasno označeno kao objašnjenje, uz linkove ka primarnim izvorima. Ne smije mijenjati status ili skrivati kontradikcije.

### 7.6. Lokalna mjerenja kvaliteta bez throughput kulta

Tek kada postoji konkretan konzument, mogu se razmotriti lokalno izvedene metrike:

- vrijeme od otvaranja Taska do pronalaska relevantnog evidencea;
- broj vraćanja u doradu zbog scope drifta;
- veličina pregledanih cjelina prije acceptancea;
- udio `IMPLEMENTED` rada koji dobije stvarnu verifikaciju;
- udio `VERIFIED` rada koji korisnik prihvati bez reworka.

Ne uvoditi OpenTelemetry ili cloud analytics radi ovoga. Prvo dokazati vrijednost kvalitativnim dogfooding bilješkama.

## 8. Antipatterni koje FlowOS treba eksplicitno izbjeći

- „Više sesija“ kao glavna metrika uspjeha.
- Broj generisanih linija, commitova ili taskova kao zamjena za kvalitet.
- Jedna oznaka `DONE` koja spaja implementaciju, verifikaciju i acceptance.
- AI sažetak kao canonical istorija ili current state.
- Drugi model kao automatski pečat da je veliki diff siguran.
- Skriveni puni diff iza „relevantnog“ AI izbora.
- Ručni `current.md`, `progress.md` i `decisions.md` koji dupliciraju bazu/ledger.
- Automatsko proširenje scope-a zato što je funkcija laka za generisanje.
- Automatski refactor samo zato što je detektovano ponavljanje.
- Opšta risk matrica i novi attention subsystem prije stvarne potrebe.
- Produktni dizajn koji maksimizira output na štetu razumijevanja, zadovoljstva, održivosti i kvaliteta.

## 9. Prioriteti

### P0 — sada, unutar postojećeg roadmapa

1. `FLOW-1203/1204`: napraviti Task Detail kao mali current-state i attention ulaz, bez AI zaključivanja.
2. `FLOW-1301–1304`: razdvojiti workflow od aktivnosti i omogućiti putanju od statusa do relevantnog/punog evidencea.
3. `FLOW-1401–1403`: odluku zasnovati na vidljivom diff/evidence kontekstu i dokazati kompletan human-controlled tok.
4. Sačuvati strogu razliku `IMPLEMENTED / VERIFIED / ACCEPTED` svuda u jeziku, modelu i GUI-ju.
5. Agent context tretirati isključivo kao regenerabilnu projekciju iz istog read-modela.

### P1 — nakon prvog pravog dogfooding toka

1. `FLOW-1501`: zabilježiti gdje je korisnik izgubio razumijevanje ili bio preopterećen.
2. `FLOW-1502/1503`: smanjiti primarnu navigaciju i ukloniti lažno autoritativne/placeholder prikaze.
3. Uobličiti deterministički Attention prikaz iz već dostupnih statusa i evidence praznina.
4. U report/follow-up praksu uključiti feature-bloat i repeated-tedium signale bez novih workflow eventova.

### P2 — van MVP-a, samo uz dokazanu potrebu

1. Dinamički autonomy/review budget.
2. Comprehension checkpoint za visoki rizik.
3. Learning/craft režim.
4. Detekcija ponovljenih obrazaca i prijedlog apstrakcije.
5. Opciono AI objašnjenje deterministički izabranog konteksta.
6. Lokalne metrike kvaliteta sa konkretnim konzumentom.

## 10. Konačna preporuka

Brettov transkript ne traži da FlowOS postane anti-AI proizvod. Traži da FlowOS odbije pretpostavku da je više agentskog outputa automatski bolje.

Najzdravija produktna teza je:

> **FlowOS povećava količinu rada koju čovjek može razumjeti, provjeriti i odgovorno prihvatiti — ne samo količinu rada koju agent može proizvesti.**

To se može postići bez davanja AI-u authority nad workflowom i bez novog paralelnog plana. Potrebno je završiti postojeće read-model, evidence-navigation, user-decision i dogfooding stavke tako da ljudsko razumijevanje bude acceptance kriterij, a ne naknadna nada.

## 11. Kanonski izvori korišteni za mapiranje

- `AGENTS.md` — obavezne arhitektonske i authority granice.
- `CLAUDE.md` — izvori istine, verifikacija, podjela odgovornosti i context disciplina.
- `docs/FlowOS-novi-detaljan-plan-PySide6.md` — glavni arhitektonski i fazni plan.
- `docs/FlowOS-plan-faze-11-15-dogfooding-v2.md` — postojeće FLOW-1203–1504 stavke korištene za praktično mapiranje.
- `arhitektura/ADR-001 — Granica odgovornosti između korisnika, FlowOS-a i AI agenata.md` — ljudski authority i ograničena autonomija.
- `arhitektura/ADR-005 — FlowOS kao deterministički observer, evidence ledger i human-controlled workflow.md` — evidence, review i decision model.
- `docs/FlowOS_agent_context_current_work_state.md` — konceptualna analiza projekcije; korištena kao izvedeni materijal, ne kao roadmap/source of truth.
- Brettov dostavljeni transkript — kvalitativni signal i predmet ove analize.

---

**Napomena o authority-ju ovog dokumenta:** Ovaj dokument ne mijenja roadmap, status implementacije niti acceptance kriterije samim postojanjem. Svaka prihvaćena promjena treba biti unesena u odgovarajući kanonski plan/tracker kroz postojeći FlowOS proces i korisničku odluku.
