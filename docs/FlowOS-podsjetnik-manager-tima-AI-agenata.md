# FlowOS — podsjetnik: čovjek kao manager tima AI agenata

**Datum bilješke:** 2026-08-18  
**Izvor inspiracije:** transkript intervjua o budućnosti softverskog inženjerstva i radu sa AI agentima  
**Svrha:** interni arhivski podsjetnik za razvoj i pozicioniranje FlowOS-a

---

## Kratka ideja

Jedna od najvažnijih poruka iz transkripta je da se vrijednost softverskog inženjera pomjera sa samog „pisanja koda po ticketu“ prema:

- razlaganju složenih problema;
- upravljanju kontekstom;
- koordinaciji više agenata;
- definisanju zahtjeva i zavisnosti;
- provjeri rezultata;
- donošenju konačnih odluka;
- održavanju development okruženja u kojem agenti mogu pouzdano raditi.

U tom modelu čovjek postaje svojevrsni **manager tima AI agenata**.

Za FlowOS je najvažniji zaključak:

> **FlowOS ne treba da bude manager umjesto čovjeka.  
> FlowOS treba da čovjeku omogući da upravlja radom više agenata bez gubljenja konteksta, kontrole i dokaza.**

---

## 1. Dekompozicija rada je osnovna ljudska odgovornost

U transkriptu se naglašava da najbolji inženjeri znaju uzeti složen problem i razbiti ga na manje, razumljive dijelove sa jasnim zavisnostima.

To direktno podržava FlowOS model:

**Plan → Task → Session / Execution → Evidence → Review → Decision**

FlowOS ne treba samovoljno određivati šta treba graditi.

Njegova uloga je da:

- prikaže plan;
- poveže task sa stvarnim izvršenjem;
- zabilježi ko ili šta je radilo;
- prikaže dokaz;
- prikaže review;
- sačuva odluku korisnika.

Čovjek i dalje odlučuje **šta**, **zašto** i **da li se rezultat prihvata**.

---

## 2. Najveći problem multi-agent rada je gubitak konteksta

Kada više agenata radi paralelno, čovjek mora pratiti:

- koji agent radi koji task;
- šta je već završeno;
- gdje je agent zaglavio;
- koji nalaz još nije riješen;
- koji rezultat je pregledan;
- koji commit pripada kojem tasku;
- šta je samo prijavljeno, a šta stvarno dokazano;
- šta je prihvaćeno, a šta vraćeno na doradu;
- u kojem branchu/worktree-u je rad izveden;
- koji je sljedeći siguran korak.

Bez sistema, veliki dio ovog stanja ostaje u glavi korisnika ili rasut po terminalima, chatovima, reportima i Git istoriji.

**FlowOS treba da bude spoljašnja memorija tog procesa.**

Ne da zamijeni čovjekovo razmišljanje, nego da ukloni nepotreban mentalni teret pamćenja trenutnog stanja.

---

## 3. Task, agent session i execution nisu ista stvar

Transkript dodatno potvrđuje da isti problem može biti podijeljen između više agenata i više pokušaja izvršenja.

Zato FlowOS mora zadržati jasnu razliku između:

- **Taska** — šta treba postići;
- **Sessiona** — konkretne interakcije sa agentom;
- **Execution Attempta** — stvarnog pokušaja izvršenja;
- **Worktree-a / workspace-a** — gdje se rad fizički izvodi;
- **Reporta / Evidence-a** — šta je agent prijavio ili šta je sistem izmjerio;
- **Reviewa** — nezavisne procjene rezultata;
- **Decisiona** — odluke korisnika.

Ove stvari ne smiju biti spojene u jedan status tipa „agent finished = task done“.

---

## 4. Agent rezultat nije isto što i prihvaćen rezultat

AI agenti mogu biti veoma sposobni, ali i dalje trebaju nadzor.

Zato FlowOS ne smije zaključivati da je task završen samo zato što:

- agent kaže da je završio;
- testovi su prošli;
- postoji commit;
- session je zatvoren;
- report ima pozitivan verdict.

FlowOS treba razlikovati:

**izvršeno → testirano → pregledano → nalaz riješen → verifikovano → korisnik prihvatio**

Konačna odluka ostaje kod čovjeka.

---

## 5. FlowOS treba smanjiti cijenu „context switchinga“

U multi-agent radu čovjek često prelazi:

Claude → Crush → terminal → Git → report → drugi agent → GUI → nazad na task.

Problem nije samo količina rada.

Problem je ponovno učitavanje konteksta:

> „Gdje smo bili?“  
> „Šta je ovaj agent već uradio?“  
> „Šta je ostalo otvoreno?“  
> „Je li ovo commitovano?“  
> „Koji nalaz je bio HIGH?“  
> „Ko je to nezavisno pregledao?“

Jedna od najvećih vrijednosti FlowOS-a treba biti:

> **Brzo vraćanje čovjeka u tačno trenutno stanje rada.**

To znači da Task Detail treba moći pokazati relevantnu istoriju i trenutno stanje bez potrebe da korisnik ponovo čita pet chatova i deset Git commitova.

---

## 6. Agent-friendly codebase je dio infrastrukture

Transkript naglašava da agenti rade bolje kada projekat već ima:

- jake testove;
- pouzdan build sistem;
- jasne granice;
- dobro definisane razvojne procedure;
- predvidljivo okruženje.

To je važna smjernica za FlowOS.

FlowOS ne treba samo pokazivati „pokreni agenta“.

Vremenom može deterministički prikazivati **Project Readiness**, na primjer:

- postoji li verify komanda;
- prolazi li build;
- postoje li testovi;
- je li Git stanje poznato;
- postoji li aktivni worktree;
- postoje li agent instructions;
- je li migration stanje poznato;
- postoje li unresolved findings;
- postoji li čist execution baseline.

FlowOS ne mora automatski popravljati ove stvari.

Dovoljno je da ih **pouzdano posmatra, poveže i prikaže**.

---

## 7. End-to-end odgovornost postaje važnija od samog kodiranja

U transkriptu se naglašava vrijednost ljudi koji povezuju više disciplina:

- engineering;
- product;
- design;
- customer context;
- planiranje;
- AI agente.

To je bitno za pozicioniranje FlowOS-a.

FlowOS ne treba postati:

> „Jira gdje AI automatski rješava tickete.“

Takav model je previše uzak.

FlowOS treba pratiti širi razvojni tok:

**namjera → plan → kontekst → izvršenje → dokaz → review → odluka**

To je nivo na kojem čovjek i dalje ima najveću vrijednost.

---

## 8. Važna granica: FlowOS nije autonomni swarm manager

Metafora „manager tima agenata“ može lako odvesti proizvod u pogrešnom smjeru.

FlowOS ne treba automatski:

- izmišljati strategiju;
- pokretati agente bez jasne korisničke namjere;
- delegirati rad u beskonačnost;
- prihvatati rezultate;
- mergeovati promjene;
- donositi konačne produktne odluke.

To bi čovjeka pretvorilo u posmatrača sistema.

Naš princip je obrnut:

> **Čovjek upravlja razvojem. FlowOS upravlja stanjem, dokazima i kontrolnim tačkama tog procesa.**

---

## 9. Ključni FlowOS principi koje ovaj transkript podržava

1. **Čovjek definiše cilj, prioritete i konačne odluke.**
2. **AI agenti mogu preuzeti veliki dio taktičkog izvršenja.**
3. **Plan mora biti razložen na jasne taskove i zavisnosti.**
4. **Task ≠ Session ≠ Execution ≠ Worktree.**
5. **Agentov report nije dovoljan dokaz završetka.**
6. **Review i evidence moraju biti povezani sa taskom.**
7. **FlowOS mora smanjiti mentalni trošak prebacivanja između agenata.**
8. **Development environment mora biti agent-friendly i deterministički provjerljiv.**
9. **Automatizovati ono što je pouzdano i determinističko.**
10. **Kada je potreban sud, odluka ostaje korisniku.**

---

## 10. Šta ovo znači za UX

Najvažniji ekran nije „Agent“.

Najvažniji ekran je **Task**.

Agent je samo jedan od načina na koji je task mogao biti izvršavan.

Task Detail treba vremenom odgovoriti na pitanja:

- Šta pokušavamo postići?
- Zašto?
- Šta je trenutno stanje?
- Ko je radio na tome?
- Gdje je radio?
- Šta je promijenjeno?
- Koji testovi su pokrenuti?
- Koji dokaz postoji?
- Ko je pregledao rezultat?
- Postoje li otvoreni findings?
- Šta korisnik sada treba odlučiti?

To je važnije od prikaza „AI agent je online“.

---

## 11. Pozicioniranje FlowOS-a

Dobar interni opis razlike je:

> **FlowOS nije alat koji pokušava zamijeniti developera kao managera AI agenata.  
> FlowOS je human control plane koji developeru daje memoriju, dokaze, stanje i kontrolu potrebnu da pouzdano vodi više ljudi i AI agenata kroz dugotrajan razvojni proces.**

Još kraće:

> **AI radi. FlowOS pamti, povezuje i dokazuje. Čovjek odlučuje.**

---

## 12. Podsjetnik za buduće odluke

Kada razmatramo novu FlowOS funkciju, pitati:

1. Da li ova funkcija smanjuje gubitak konteksta?
2. Da li povezuje task sa stvarnim dokazom?
3. Da li povećava kontrolu korisnika?
4. Da li je deterministička i pouzdana?
5. Da li razdvaja observation od judgment-a?
6. Da li pomaže više agenata bez pretvaranja FlowOS-a u autonomnog managera?
7. Da li čovjek i dalje ostaje konačni autoritet?

Ako je odgovor uglavnom **da**, funkcija je vjerovatno u skladu sa FlowOS pravcem.

Ako funkcija pokušava da sakrije razvojni proces iza „AI će sve sam“, vjerovatno idemo u pogrešnom smjeru.

---

## Završna misao

Najrelevantnija poruka transkripta za FlowOS nije da će AI „zamijeniti programere“.

Relevantnija poruka je da se razvoj softvera mijenja iz:

> **čovjek direktno izvršava svaki korak**

u:

> **čovjek razlaže problem, koordinira izvršenje, održava kontekst, provjerava dokaze i donosi odluke.**

FlowOS treba biti infrastruktura koja taj novi način rada čini **preglednim, dokazivim i kontrolisanim**.
