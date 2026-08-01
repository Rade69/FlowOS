# FlowOS — pojmovnik za PRD, arhitekturu, backend, testiranje i Git

## Namjena dokumenta

Ovaj dokument objašnjava stručne pojmove koji se koriste u FlowOS planu, backend implementaciji, review bundle-u i nezavisnoj analizi koda. Cilj je da svaki pojam bude razumljiv i bez formalnog softverskog obrazovanja, ali dovoljno precizan za rad sa agentima i provjeru implementacije.

---

# 1. Dokumentacija proizvoda i planiranje

## PRD — Product Requirements Document

PRD je dokument zahtjeva proizvoda. Opisuje šta se pravi, kome je namijenjeno, koji problem rješava, koje funkcije mora imati, šta ulazi u prvu verziju i kako se provjerava da je funkcija završena.

PRD govori prvenstveno **šta proizvod mora raditi**, a ne detaljno kako će kod biti napisan.

```text
PRD zahtjev:
Korisnik nakon povratka na projekat mora odmah vidjeti gdje je rad stao.

Tehničko rješenje:
ProjectResumeState tabela, API endpoint i PySide6 panel „Gdje si stao“.
```

## Tehnička specifikacija

Tehnička specifikacija opisuje **kako** će se PRD zahtjev realizovati. Sadrži arhitekturu, module, modele baze, API rute, tok podataka, pravila grešaka i testnu strategiju.

## Scope — obim zadatka

Scope određuje šta agent smije mijenjati, šta mora napraviti i šta ne smije dirati.

```text
Scope:
Implementirati API za planove.

Van scope-a:
Ne praviti GUI.
Ne mijenjati Git watcher.
```

## Out of scope — van obima

To su stvari koje namjerno nisu dio zadatka. Njih treba eksplicitno navesti da agent ne proširi rad bez odobrenja.

## Acceptance kriterijum

Konkretan, provjerljiv uslov koji mora biti ispunjen da bi zadatak bio završen.

Loše:

```text
Sistem treba dobro da radi.
```

Dobro:

```text
Nakon promjene projekta GUI prikazuje posljednju stavku plana,
posljednji commit, sljedeći korak i reconciliation status.
```

## Definition of Done

Zajednički skup pravila koji važi za svaki zadatak:

```text
- kod implementiran;
- testovi prolaze;
- Ruff prolazi;
- mypy prolazi;
- architecture test prolazi;
- agent report napisan;
- commit napravljen.
```

Acceptance kriterijumi važe za konkretan zadatak, a Definition of Done za sve zadatke.

## Plan item

Jedna konkretna stavka plana, na primjer:

```text
FLOW-103 — Service runtime
```

Sadrži ID, naziv, opis, zavisnosti, kriterijume, status, dokaze, commitove i rizike.

## Faza

Grupa povezanih plan stavki. Faza nije završena samo zato što je većina koda napisana; njen status se izvodi iz statusa svih stavki.

## Dependency — zavisnost

Jedan zadatak zavisi od drugog i ne može pravilno početi ili završiti prije njega.

## Risk level — nivo rizika

Procjena posljedica greške:

```text
LOW
MEDIUM
HIGH
CRITICAL
```

HIGH i CRITICAL zadaci obično traže dodatne testove, project room, nezavisnu provjeru i rollback plan.

---

# 2. Statusi rada

## NOT_STARTED — nije započeto

Zadatak postoji, ali rad nije počeo.

## IN_PROGRESS — u toku

Rad je aktivno započet.

## BLOCKED — blokirano

Rad ne može dalje zbog prepreke, zavisnosti, odluke ili problema sa okruženjem.

## IMPLEMENTED — implementirano

Kod je napisan, ali još nije potpuno provjeren.

```text
Implementirano ≠ provjereno
```

## VERIFIED — provjereno

Tehničke provjere potvrđuju da implementacija radi prema kriterijumima.

## ACCEPTED — prihvaćeno

Korisnik ili ovlašteni reviewer prihvatio je rezultat kao završenu cjelinu.

```text
Provjereno ≠ prihvaćeno
```

## REJECTED — odbijeno

Rezultat je pregledan i nije prihvaćen. Razlog mora biti dokumentovan.

## NEEDS_REVIEW — potreban pregled

Rad postoji, ali ima nejasnoća, otvorenih testova ili promjena koje treba potvrditi.

## SUPERSEDED — zamijenjeno novijom verzijom

Stari plan više nije aktivan jer ga je zamijenio novi.

---

# 3. Arhitektura

## Arhitektura softvera

Opisuje kako je sistem organizovan, koji slojevi postoje, ko smije zavisiti od koga i gdje se nalazi poslovna logika.

## View

Korisnički interfejs. U FlowOS-u su to PySide6 prozori i widgeti.

View treba da prikaže podatke, primi akciju i emituje signal. Ne treba direktno da pristupa bazi, Git-u ili poslovnoj logici.

## Controller

Prima korisnički ili HTTP zahtjev i koordinira tok.

```text
zahtjev
→ Controller
→ Service
→ rezultat
```

Controller ne treba direktno da piše SQL, kreira ORM modele ili vodi složene transakcije.

## Service

Sadrži poslovnu logiku.

```text
Aktiviraj plan:
1. pronađi stari aktivni plan;
2. označi ga kao superseded;
3. aktiviraj novi;
4. upiši audit događaj;
5. potvrdi transakciju.
```

## Repository

Posrednik između Service sloja i baze. Service ne mora znati detalje SQLAlchemyja.

## Persistence

Trajno čuvanje podataka: SQLite, SQLAlchemy modeli, migracije i repozitorijumi.

## ORM

Object-Relational Mapping povezuje Python objekte sa tabelama baze.

```python
class Project(Base):
    id = Column(Integer, primary_key=True)
    name = Column(String)
```

Problem nije ORM sam po sebi, već kada se koristi u pogrešnom sloju.

## Composition root

Centralno mjesto gdje se kreiraju i povezuju repository, service, controller i konfiguracione zavisnosti.

## Dependency injection

Objekat dobija zavisnosti spolja umjesto da ih sam kreira. To olakšava testiranje i zamjenu implementacija.

## Architecture boundary

Pravilo dozvoljenih zavisnosti.

```text
View → Controller → Services
```

Zabranjeno:

```text
View → baza
Controller → ORM persistence
shared → GUI
```

## Circular dependency

Kružna zavisnost nastaje kada A zavisi od B, a B od A.

## Coupling — spregnutost

Koliko su moduli međusobno vezani. Visoka spregnutost znači da mala promjena izaziva mnogo drugih promjena.

## Cohesion — kohezija

Koliko funkcije unutar modula pripadaju istoj odgovornosti. Dobar modul ima visoku koheziju.

## Separation of concerns

Razdvajanje odgovornosti:

```text
View — prikaz
Controller — koordinacija
Service — poslovna logika
Repository — pristup bazi
```

---

# 4. API i prenos podataka

## API

Definisan način komunikacije između programa. U FlowOS-u PySide6 GUI komunicira sa FastAPI backendom.

## Endpoint

Jedna konkretna API operacija:

```text
GET /projects
POST /projects
GET /projects/{id}/resume
```

## HTTP metode

```text
GET     čitanje
POST    kreiranje ili akcija
PUT     potpuna zamjena
PATCH   djelimična izmjena
DELETE  brisanje
```

## DTO

Data Transfer Object je strukturisan objekat za prenos podataka.

```python
class ProjectCreate(BaseModel):
    name: str
    repository_path: str
```

Bolje je od običnog `dict` jer daje validaciju, tipove i jasniji API contract.

## Pydantic model

Model koji validira ulazne i izlazne podatke FastAPI-ja.

## API contract

Određuje URL, metodu, ulaz, izlaz, statusne kodove i oblik grešaka.

## Request i response

Request je zahtjev klijenta, a response odgovor servera.

## HTTP status code

```text
200 OK
201 Created
204 No Content
400 Bad Request
401 Unauthorized
403 Forbidden
404 Not Found
409 Conflict
422 Validation Error
500 Internal Server Error
```

## Side effect

Promjena stanja izazvana operacijom. GET bi u pravilu trebalo samo da čita.

Loše:

```text
GET /resume → regeneriše i upisuje podatke
```

Bolje:

```text
GET /resume → čita
POST /resume/regenerate → mijenja
```

## Error contract

Sve API greške imaju isti oblik:

```json
{
  "code": "PROJECT_NOT_FOUND",
  "message": "Projekat ne postoji.",
  "details": {},
  "correlation_id": "abc-123"
}
```

## Correlation ID

Jedinstveni ID zahtjeva koji povezuje GUI log, backend log i error odgovor.

## OpenAPI

Mašinski čitljiv opis API-ja koji FastAPI generiše iz pravilnih request i response modela.

---

# 5. Baza i transakcije

## Database schema

Struktura baze: tabele, kolone, veze, indeksi i ograničenja.

## SQLAlchemy Session

Objekat preko kojeg kod učitava ORM objekte, izvršava upite, commitira i rollbackuje transakcije.

Session mora biti pravilno zatvoren.

## Transakcija

Grupa operacija koje moraju uspjeti zajedno ili se sve poništavaju.

## Commit baze

Potvrđuje promjene u bazi. Nije isto što i Git commit.

## Rollback

Poništava nepotvrđene promjene kada se desi greška.

## Migration

Kontrolisana promjena strukture baze.

## Alembic

Alat za SQLAlchemy migracije.

```bash
alembic upgrade head
alembic downgrade -1
```

## Constraint

Pravilo koje sama baza štiti.

## CheckConstraint

Ograničava dozvoljene vrijednosti, na primjer status.

## Unique constraint

Sprečava duplikate.

## Partial unique index

Jedinstveni indeks koji važi samo pod uslovom.

```sql
CREATE UNIQUE INDEX one_active_plan
ON plans(project_id)
WHERE status = 'ACTIVE';
```

## Foreign key

Veza između tabela, na primjer `plan.project_id → projects.id`.

## Cascade delete

Automatski briše povezane zapise. Može biti rizičan za istorijske podatke.

## Soft delete / archive

Zapis se ne briše, već dobija status `ARCHIVED`.

## SQLite WAL

Write-Ahead Logging poboljšava paralelno čitanje i pisanje i smanjuje zaključavanje SQLite baze.

---

# 6. Runtime i procesi

## Runtime

Period dok aplikacija ili servis stvarno radi.

## Lifecycle

Cijeli životni ciklus:

```text
start → init → ready → running → shutdown → cleanup
```

## Lifespan

FastAPI mehanizam za inicijalizaciju i cleanup pri pokretanju i gašenju.

## Supervisor

Proces koji pokreće, provjerava i po potrebi oporavlja backend servis.

## Runtime descriptor

Mali fajl koji GUI-ju govori gdje servis radi.

```json
{
  "pid": 5312,
  "host": "127.0.0.1",
  "port": 8765,
  "instance_id": "abc123"
}
```

## Stale descriptor

Descriptor koji je ostao iako servis više ne radi.

## Atomic write

Upis kroz privremeni fajl i `os.replace()` kako drugi proces ne bi pročitao pola JSON-a.

## Mutex

Zaključavanje koje sprečava dvije instance istog servisa.

## PID

Identifikator procesa. Nije dovoljan bez instance ID-a jer se broj može ponovo iskoristiti.

## Instance ID

Jedinstveni identifikator jednog pokretanja servisa.

## Port i bind

Port je broj na kojem servis prima zahtjeve. Bind znači zauzimanje IP adrese i porta.

## Race condition

Rezultat zavisi od trenutka izvršavanja više procesa.

## Readiness

Servis nije samo pokrenut, već je stvarno spreman da prima zahtjeve.

## Health endpoint

```text
GET /health
```

Provjerava stanje servisa i baze.

## Graceful shutdown

Kontrolisano gašenje uz zatvaranje baze, logova i runtime resursa.

## Force terminate

Nasilno gašenje procesa kada graceful shutdown ne uspije.

---

# 7. Sigurnost

## CORS

Browser pravilo o tome ko smije pozivati API. Za PySide6 obično nije potrebno.

## Local API token

Lokalna tajna kojom GUI dokazuje backendu da je legitimni klijent.

## Secret

Osjetljiva vrijednost: API ključ, token, lozinka ili privatni ključ.

## Redaction

Maskiranje osjetljivih podataka u logovima i review paketima.

## Least privilege

Svaka komponenta dobija samo minimalne dozvole koje su joj potrebne.

---

# 8. Testiranje i kvalitet

## Unit test

Provjerava malu jedinicu logike.

## Integration test

Provjerava saradnju više komponenti, na primjer Service + Repository + SQLite.

## Contract test

Provjerava da API poštuje dogovoreni oblik ulaza i izlaza.

## End-to-end test

Provjerava cijeli tok od GUI akcije do baze i nazad.

## Regression test

Sprečava povratak ranije ispravljene greške.

## Architecture test

Automatski provjerava dozvoljene i zabranjene importe.

## False positive

Test prolazi iako sistem nije ispravan.

## False negative

Test pada iako je sistem ispravan.

## Test coverage

Mjeri koliko koda testovi izvrše. Visok coverage ne znači automatski kvalitetne testove.

## Pytest

Alat za pokretanje Python testova.

## Ruff

Provjerava stil, importe i neke moguće bugove.

```bash
ruff check .
ruff format --check .
```

## mypy

Provjerava tipove bez pokretanja programa.

## Strict typing

Stroža provjera tipova, sa manje implicitnih `Any` vrijednosti.

## Lint

Automatska provjera programskih i stilskih problema.

## Formatter

Automatski uređuje izgled koda.

## Verify script

Jedna komanda koja pokreće glavne provjere.

```bash
python scripts/verify.py
```

## Exit code

```text
0 = uspjeh
1 = greška
```

## Smoke test

Brza osnovna provjera da se servis pokreće i `/health` radi.

## Flaky test

Test koji ponekad prolazi, a ponekad pada bez promjene koda.

---

# 9. Git i praćenje rada

## Git repository

Direktorijum sa verzionisanom istorijom projekta.

## Commit

Sačuvana tačka Git istorije.

## Commit hash

Jedinstveni identifikator commita, na primjer `a8f19d2`.

## Branch

Paralelna linija razvoja.

## Worktree

Odvojeni radni direktorijum iz istog repozitorija. Koristan je za paralelne agente.

## Dirty tree

Postoje necommitovane promjene.

## Staged change

Promjena pripremljena za commit.

## Unstaged change

Promjena postoji, ali nije dodata u staging.

## Untracked file

Fajl koji Git još ne prati.

## Diff

Prikazuje razlike između verzija.

## Merge

Spaja promjene iz jednog brancha u drugi.

## Conflict

Git ne može automatski spojiti promjene.

## Rebase

Premješta commitove na novu baznu istoriju.

## Reconciliation

Poredi posljednje Git stanje koje FlowOS pamti sa trenutnim stvarnim stanjem.

## External activity

Rad napravljen van FlowOS praćenja.

## Attribution

Pripisivanje promjene određenom agentu ili korisniku. Ne smije biti automatsko bez dokaza.

## Confidence

Pouzdanost sažetka „Gdje si stao“:

```text
HIGH
MEDIUM
LOW
```

To nije ocjena kvaliteta koda.

---

# 10. Review i izvještavanje

## Code review

Nezavisni pregled funkcionalnosti, arhitekture, testova, rizika i održivosti.

## Independent verification

Rezultat provjerava drugi agent ili reviewer, a ne samo autor koda.

## Self-grading

Agent sam proglasi svoj rad uspješnim bez nezavisnog dokaza.

## Evidence — dokaz

Commit, diff, test rezultat, screenshot, log ili API odgovor.

## Review bundle

Paket sa reportom, diffom, punim fajlovima, testovima, lintom, mypy rezultatom i Git stanjem.

## Agent report

Dokumentuje šta je urađeno, kako, šta nije urađeno, rizike i sljedeći korak.

## Project room

Dokument za rizične zadatke sa ciljem, scope-om, odlukama, rizicima i handoff-om.

## Handoff

Strukturisano predavanje rada drugom agentu ili revieweru.

## Audit trail

Istorija važnih promjena i odluka: ko, šta, kada i zašto.

---

# 11. GUI i prikaz stanja

## ViewState

Pripremljen skup podataka koji View treba da prikaže.

## Loading state

Stanje dok se podaci učitavaju.

## Empty state

Stanje kada nema podataka.

## Error state

Stanje kada operacija nije uspjela.

## Offline state

Backend nije dostupan, ali GUI prikazuje posljednje poznato stanje.

## Non-blocking GUI

Git, mreža, disk i testovi ne smiju blokirati GUI thread.

## GUI thread

Glavni thread koji crta prozor i obrađuje korisničke događaje.

## Signal i slot

PySide6 mehanizam za povezivanje korisničkih događaja i Controller akcija.

---

# 12. Dodatni važni pojmovi

## MVP

Minimum Viable Product je najmanja upotrebljiva verzija proizvoda koja već donosi vrijednost.

## Technical debt

Tehnički dug nastaje izborom brzog, ali slabijeg rješenja koje kasnije traži popravku.

## Refactor

Promjena strukture koda bez promjene ponašanja.

## Regression

Kvar funkcije koja je ranije radila.

## Idempotency

Ponovljena ista operacija daje isti rezultat i ne stvara duplikate.

## Deterministic behavior

Isti ulaz daje isti rezultat.

## Observability

Mogućnost razumijevanja sistema kroz logove, metrike, health i audit događaje.

## Structured logging

Log sa jasnim poljima umjesto neorganizovanog teksta.

## Log rotation

Ograničava rast log fajlova i čuva nekoliko prethodnih verzija.

## Backward compatibility

Nova verzija ne prekida postojeće klijente i podatke.

## Breaking change

Promjena koja prekida postojeći API ili format podataka.

## Schema version

Verzija strukture fajla, descriptor-a ili baze.

## Serialization

Pretvaranje objekta u JSON ili tekst.

## Deserialization

Pretvaranje JSON-a ili teksta u objekat.

## Validation

Provjera da li su podaci ispravni i dozvoljeni.

## Normalization

Organizovanje baze radi smanjenja dupliranja i nelogičnosti.

## Denormalized state

Unaprijed izračunat sažetak podataka radi bržeg čitanja.

## Materialized state

Sažetak koji je stvarno sačuvan u bazi.

## Source of truth

Autoritativni izvor podatka. Git je izvor istine za commitove, baza za plan state, a report za deklarisani handoff.

## Reproducibility

Drugi reviewer može ponoviti test i dobiti isti rezultat.

---

# 13. Tok kroz FlowOS

## Kreiranje plana

```text
Korisnik uveze Markdown plan
→ PlanController
→ PlanService
→ PlanRepository
→ SQLite
→ plan dobija status DRAFT
```

## Aktivacija plana

```text
stari ACTIVE plan → SUPERSEDED
novi plan → ACTIVE
audit događaj → upisan
transakcija → potvrđena
```

## Povratak na projekat

```text
korisnik izabere projekat
→ GUI učita ProjectResumeState
→ prikaže posljednje poznato stanje
→ backend pokrene reconciliation
→ Git stanje se uporedi
→ resume se osvježi ili označi za pregled
```

## Rad agenta

```text
agent dobije PlanItem
→ radi u worktree-u
→ pravi commit
→ pokreće verify
→ piše report
→ pravi review bundle
→ nezavisni reviewer provjerava
→ IMPLEMENTED prelazi u VERIFIED
→ korisnik prihvata
→ status prelazi u ACCEPTED
```

---

# 14. Najvažnije razlike

```text
PRD
šta proizvod treba da radi

Tehnička specifikacija
kako će se napraviti
```

```text
Acceptance kriterijum
uslov za konkretan zadatak

Definition of Done
opšti standard za sve zadatke
```

```text
IMPLEMENTED
kod napisan

VERIFIED
tehnički provjeren

ACCEPTED
korisnik prihvatio
```

```text
Controller
koordinira

Service
sadrži poslovnu logiku

Repository
pristupa bazi

ORM
mapira objekte na tabele
```

```text
Git commit
tačka istorije koda

Commit baze
potvrda SQL transakcije
```

```text
Health
servis radi

Readiness
servis je spreman za rad
```

```text
External activity
promjena van FlowOS-a

Attribution
potvrđeno kome promjena pripada
```

```text
Coverage
koliko koda testovi izvrše

Kvalitet testa
da li test provjerava pravo ponašanje
```

---

# 15. Preporučeni srpski nazivi u GUI-ju

```text
Overview            → Pregled
Projects            → Projekti
Plan                → Plan
Sessions            → Sesije
Tasks               → Zadaci
Agents              → Agenti
Worktrees           → Radna stabla
Conflicts           → Konflikti
Reports             → Izvještaji
Settings            → Postavke

NOT_STARTED         → Nije započeto
IN_PROGRESS         → U toku
BLOCKED             → Blokirano
IMPLEMENTED         → Implementirano
VERIFIED            → Provjereno
ACCEPTED            → Prihvaćeno
REJECTED            → Odbijeno
NEEDS_REVIEW        → Potreban pregled
SUPERSEDED          → Zamijenjeno novijom verzijom

Resume              → Nastavak rada
Where you stopped   → Gdje si stao
Next step           → Sljedeći korak
Reconciliation      → Usklađivanje stanja
External activity   → Vanjska aktivnost
Confidence          → Pouzdanost
Evidence            → Dokazi
Acceptance criteria → Kriterijumi prihvatanja
Service runtime     → Rad servisnog procesa
Health              → Stanje servisa
Readiness           → Spremnost servisa
```

---

# 16. Završno pravilo

Najvažnije pravilo pri radu sa agentima:

```text
Tvrdnja nije dokaz.
Kod nije završen zato što agent kaže da je završen.
```

Završeno znači:

```text
scope ispoštovan
→ kod implementiran
→ testovi validni
→ arhitektura provjerena
→ rezultati reproducibilni
→ nezavisni reviewer potvrdio
→ korisnik prihvatio
```
