# FlowOS — GUI specifikacija novog Overview ekrana

**Status:** Implementaciona specifikacija za pi agenta  
**Namjena:** PySide6 + Qt Widgets implementacija bez oslanjanja na sliku  
**Arhitektura:** View → Controller → Services  
**Primarni ekran:** Pregled / Overview  
**Osnova:** raniji FlowOS mockup + plan v3 sa napretkom po planu, „Gdje si stao“ i Git reconciliation tokom

---

# 1. Svrha ekrana

Overview ekran mora korisniku za manje od 10 sekundi odgovoriti:

1. Koji je projekat trenutno otvoren?
2. Koja verzija plana je aktivna?
3. Koja stavka plana je trenutno u radu?
4. Gdje je rad stao posljednji put?
5. Koji agent i sesija trenutno rade?
6. Koji acceptance kriterijumi su završeni?
7. Šta je implementirano, verifikovano i prihvaćeno?
8. Postoje li vanjske Git promjene koje FlowOS nije pratio?
9. Koji je sljedeći konkretan korak?
10. Šta mora biti provjereno prije nastavka?

Ovaj ekran nije samo dashboard aktivnosti. On je centralni ekran za povratak na projekat i nastavak rada bez čitanja prethodnih razgovora.

---

# 2. Opšti vizuelni raspored

Koristiti tamnu temu, bez SaaS ukrasa i bez dekorativnih elemenata koji nemaju funkciju.

Glavni raspored:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ TOPBAR                                                                      │
├──────────────┬───────────────────────────────────────┬──────────────────────┤
│ SIDEBAR      │ CENTRALNI SADRŽAJ                     │ DESNI PANEL          │
│              │                                       │                      │
│ Navigacija   │ Napredak po planu                     │ Gdje si stao         │
│              │                                       │                      │
│ Aktivni      │ Aktivne sesije                        │ Detalji stavke       │
│ projekat     │                                       │                      │
│              │ Nedavna aktivnost                     │ Reconciliation       │
│ Brze akcije  │                                       │                      │
├──────────────┴───────────────────────────────────────┴──────────────────────┤
│ FOOTER / STATUS BAR                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

Preporučeni odnos širina na 1920×1080:

```text
Sidebar: 220–250 px
Centralni sadržaj: fleksibilno, približno 60–65%
Desni panel: 360–420 px
```

Ne koristiti ručno pozicioniranje koordinatama. Koristiti `QSplitter` i layoute.

---

# 3. Topbar

Topbar je visok približno 52–60 px.

Sadrži, slijeva nadesno:

1. FlowOS logo i naziv;
2. selector projekta;
3. status projekta;
4. glavna navigacija ili breadcrumb;
5. status lokalnog servisa;
6. dugme za osvježavanje;
7. sistemska dugmad prozora.

## 3.1 Selector projekta

Primjer:

```text
Projekat:
FlowOS Core ▼
```

Promjena projekta mora:

- odmah prikazati posljednje poznato stanje iz baze;
- u pozadini pokrenuti Git reconciliation;
- ne blokirati GUI;
- prikazati timestamp posljednjeg poznatog stanja dok reconciliation traje.

## 3.2 Status projekta u topbaru

Moguća stanja:

```text
● Ažurno
⚠ Vanjske promjene
■ Blokirano
◐ Treba pregled
○ Bez istorije
```

Primjer:

```text
⚠ Projekat je mijenjan van FlowOS-a
3 nova commita · 2 nekomitovana fajla
```

Ako je reconciliation u toku:

```text
Provjera Git stanja...
```

---

# 4. Sidebar

Sidebar ima četiri cjeline.

## 4.1 Glavna navigacija

Redoslijed:

```text
Pregled
Projekti
Plan
Sesije
Zadaci
Agenti
Worktrees
Konflikti
Izvještaji
Postavke
```

Aktivna stavka ima plavu ili ljubičastu pozadinu i jasnu lijevu indikatorsku liniju.

## 4.2 Sažetak aktivnog projekta

Umjesto stare kartice „Aktivna stavka plana“, prikazati kompaktnu karticu:

```text
AKTIVNI PROJEKAT

FlowOS Core
Plan v3 · ACTIVE

FLOW-103
Service runtime

Status:
IMPLEMENTED
nije VERIFIED

Posljednji rad:
juče 18:20
```

Dugme:

```text
[Otvori projekat]
```

Ova kartica je samo kratak sažetak. Detaljni handoff je u desnom panelu.

## 4.3 Brze akcije

```text
Nova sesija
Dodaj zadatak
Uvezi plan
Pregledaj vanjske promjene
Otvori dnevnik
```

„Pregledaj vanjske promjene“ prikazati samo kada postoji neriješen reconciliation događaj.

## 4.4 Status veze

Na dnu sidebara:

```text
● Povezano sa servisom
```

ili:

```text
● Offline — prikaz posljednjeg poznatog stanja
```

---

# 5. Centralni panel — Napredak po planu

Ovo je najveći panel na ekranu.

Naslov:

```text
NAPREDAK PO PLANU
Aktivni plan: FlowOS v3
```

Ne prikazivati jedan procenat bez jasnog pravila računanja.

Umjesto toga prikazati statusni sažetak:

```text
3 ACCEPTED · 1 VERIFIED · 1 IMPLEMENTED · 1 IN_PROGRESS · 3 NOT_STARTED
```

Ako se ipak koristi progress bar, pored njega mora pisati:

```text
Računanje: 3 od 7 stavki ACCEPTED
```

## 5.1 Tabela plana

Kolone:

```text
Faza / stavka
Status
Agent / sesija
Kriterijumi
Stanje nastavka
Zavisnosti
```

Primjer redova:

```text
FLOW-101  Shared contracts i error model
VERIFIED
—
6/6
Spremno za prihvatanje
—

FLOW-102  SQLite i migracije
ACCEPTED
—
8/8
Završeno
—

FLOW-103  Service runtime
IMPLEMENTED
pi / SESSION-42
5/7
NEEDS_REVIEW
FLOW-101, FLOW-102

FLOW-104  Projects/Tasks Services i API
NOT_STARTED
—
0/6
BLOCKED
FLOW-103
```

## 5.2 Vizuelni statusi

```text
NOT_STARTED  sivo
IN_PROGRESS  žuto
BLOCKED      crveno
IMPLEMENTED  ljubičasto
VERIFIED     plavo-zeleno
ACCEPTED     zeleno
REJECTED     tamnocrveno
```

`IMPLEMENTED`, `VERIFIED` i `ACCEPTED` moraju biti vizuelno jasno različiti.

## 5.3 Faze

Faze su expandable/collapsible redovi.

Primjer:

```text
▼ Faza 1 — Temelj i prvi vertikalni tok
▶ Faza 2 — Wrapper, watcher i Aktivne sesije
▶ Faza 3 — Konflikti, timeline, verify i reporti
▶ Faza 4 — Worktree tok i prva korisna verzija
```

Faza prikazuje broj stavki po statusu, ne samo procenat.

---

# 6. Centralni panel — Aktivne sesije

Nalazi se ispod plana.

Naslov:

```text
AKTIVNE SESIJE (2)
```

Kolone:

```text
Sesija
Agent
Plan stavka
Worktree / branch
Početak
Status
Zadnja aktivnost
```

Primjer:

```text
SESSION-42
pi
FLOW-103 Service runtime
flow/FLOW-103-service-runtime
16:40
ACTIVE
prije 1 min
```

Sesija mora jasno pokazivati na kojoj PlanItem stavci radi.

Završena sesija može biti prikazana samo u sažetku ili posebnom tabu, ne kao „aktivna“.

---

# 7. Centralni panel — Nedavna aktivnost

Naslov:

```text
NEDAVNA AKTIVNOST
```

Prikazati samo poslovno relevantne događaje:

```text
17:22  pi / SESSION-42  Commit a8f19d2
17:10  pi / SESSION-42  Testovi: 18/19 prolazi
16:40  Sesija pokrenuta za FLOW-103
15:55  FLOW-102 prešao u VERIFIED
```

Ne prikazivati svaki raw filesystem događaj.

Dugme:

```text
[Otvori cijeli timeline]
```

---

# 8. Desni panel — „Gdje si stao“

Ovo je prvi i najvažniji panel desno.

Naslov:

```text
GDJE SI STAO
```

Sadržaj:

```text
Plan:
FlowOS v3

Posljednja stavka:
FLOW-103 — Service runtime

Stanje:
IMPLEMENTED
nije VERIFIED

Posljednja sesija:
pi · SESSION-42
završena juče u 18:20

Posljednji dokaz:
commit a8f19d2
18/19 testova prolazi
```

Zatim tri obavezne sekcije:

## 8.1 Gdje je rad stao

```text
Runtime servis i dijagnostički endpointi su implementirani.
Force terminate na Windowsu ostavlja runtime descriptor.
```

## 8.2 Sljedeći konkretan korak

```text
Implementirati supervisor cleanup nakon hard terminate-a.
```

## 8.3 Prije nastavka provjeriti

```text
- trenutni HEAD
- dirty tree
- failing Windows lifecycle test
```

## 8.4 Pouzdanost sažetka

```text
Pouzdanost: SREDNJA
Posljednji reconciliation: prije 2 min
```

Moguće vrijednosti:

```text
HIGH
MEDIUM
LOW
```

Ako postoji neriješen reconciliation događaj, confidence ne može biti HIGH.

Dugmad:

```text
[Nastavi rad]
[Otvori report]
```

„Nastavi rad“ otvara dijalog sa unaprijed izabranim projektom, taskom i PlanItem stavkom.

---

# 9. Desni panel — Detalji aktivne stavke plana

Naslov:

```text
DETALJI STAVKE PLANA
```

Sadržaj:

```text
FLOW-103
Service runtime

Faza:
Faza 1 — Temelj i prvi vertikalni tok

Status:
IMPLEMENTED

Agent:
pi

Sesija:
SESSION-42

Početak:
31.07.2026. 16:40
```

## 9.1 Acceptance kriterijumi

Primjer:

```text
✓ FastAPI app sa lifespan-om
✓ Single-instance lock / mutex
✓ Runtime descriptor upis / čitanje
✓ /health, /version, /runtime endpointi
◐ Graceful shutdown — 1 test ne prolazi
○ Lokalni strukturisani logovi
○ Rotacija logova
```

Legenda:

```text
✓ PASSED
◐ IN_PROGRESS / NEEDS_REVIEW
✕ FAILED
○ PENDING
— NOT_APPLICABLE
```

## 9.2 Dokazi

```text
Commit:
a8f19d2

Testovi:
18/19 prolazi

Agent report:
2026-07-31_FLOW-103.md

Worktree:
flow/FLOW-103-service-runtime
```

Dugmad:

```text
[Otvori stavku]
[Otvori report]
[Promijeni status]
```

`Promijeni status` mora ići kroz Controller i PlanProgressService, ne direktno mijenjati bazu.

---

# 10. Desni panel — Git reconciliation

Ovaj panel je vidljiv samo kada postoje vanjske promjene ili nejasno stanje.

Naslov:

```text
PROMJENE VAN FLOWOS-A
```

Sadržaj:

```text
⚠ Projekat je mijenjan van FlowOS-a.

3 nova commita
2 nekomitovana fajla
Branch:
main → feature/runtime-fix

Autor nije potvrđen.
Promjene nisu pripisane agentu ni planiranoj stavci.
```

Dugmad:

```text
[Pregledaj promjene]
[Uvezi kao vanjsku aktivnost]
[Poveži sa FLOW-103]
[Napravi novi task]
[Pregledaj kasnije]
```

Ne koristiti „Ignoriši“ bez razloga. Ako postoji ta akcija, mora otvoriti dijalog za obrazloženje.

Dok je događaj neriješen:

- „Gdje si stao“ confidence je MEDIUM ili LOW;
- PlanItem status se ne mijenja automatski;
- promjene se ne pripisuju agentu;
- topbar pokazuje upozorenje.

Ako nema vanjskih promjena, prikazati mali zeleni status:

```text
Git stanje odgovara posljednjem FlowOS snapshotu.
```

---

# 11. Footer / status bar

Footer prikazuje samo tehnički korisne informacije:

```text
Servis: aktivan
API: v1
Baza: flowos.db · OK
Watcher: aktivan
Git reconciliation: prije 2 min
```

Ne prikazivati avatar korisnika, trošak ili uptime ako nemaju neposrednu vrijednost na ovom ekranu.

Uptime može biti u detaljima sistema, ne mora biti stalno vidljiv.

---

# 12. Ponašanje pri promjeni projekta

Tok:

```text
korisnik izabere projekat
→ GUI odmah učita posljednji ProjectResumeState iz baze
→ prikazuje timestamp i confidence
→ u pozadini poziva reconciliation
→ ako je CURRENT, status postaje Ažurno
→ ako postoje vanjske promjene, prikazuje upozorenje
→ korisnik rješava reconciliation događaj
→ regeneriše se Gdje si stao
```

GUI ne smije izgledati zamrznuto dok traje Git provjera.

Loading stanje:

```text
Učitano posljednje poznato stanje.
Provjera trenutnog Git stanja...
```

---

# 13. Empty, error i offline stanja

## 13.1 Projekat bez plana

```text
Ovaj projekat nema aktivan plan.
[Uvezi plan]
```

## 13.2 Projekat bez istorije

```text
Nema prethodno praćenog rada.
Pokreni prvu sesiju ili uvezi postojeće Git stanje.
```

## 13.3 Repo nije dostupan

```text
Repozitorij nije pronađen na sačuvanoj putanji.
[Pronađi novu lokaciju]
```

## 13.4 Backend offline

```text
FlowOS servis nije dostupan.
Prikazuje se posljednje poznato stanje.
[Pokušaj ponovo]
```

## 13.5 Neuspjeli reconciliation

```text
Git stanje nije moglo biti provjereno.
Sažetak možda nije ažuran.
[Ponovi provjeru]
```

---

# 14. PySide6 komponente

Preporučena struktura:

```text
OverviewView
├── ProjectHeaderWidget
├── PlanProgressWidget
│   ├── PlanPhaseTreeView
│   └── PlanItemDelegate
├── ActiveSessionsWidget
├── RecentActivityWidget
├── ProjectResumeWidget
├── PlanItemDetailsWidget
├── ReconciliationWidget
└── ServiceStatusBar
```

Controlleri:

```text
OverviewController
ProjectResumeController
PlanProgressController
ReconciliationController
SessionsController
```

GUI Services:

```text
OverviewClientService
ProjectResumeClientService
PlanClientService
ReconciliationClientService
SessionClientService
```

View ne poziva Services direktno.

---

# 15. ViewState modeli

Minimalni ViewState objekti:

```text
OverviewViewState
ProjectHeaderViewState
PlanProgressViewState
PlanPhaseViewState
PlanItemViewState
ActiveSessionViewState
ProjectResumeViewState
ReconciliationViewState
ServiceStatusViewState
```

`ProjectResumeViewState` treba sadržavati:

```text
project_name
active_plan_title
last_plan_item_key
last_plan_item_title
plan_item_status
last_session_label
last_activity_at
last_commit_sha
verification_summary
where_stopped
next_concrete_step
resume_preconditions
open_blockers
confidence
last_reconciled_at
```

---

# 16. Akcije i sigurnosne potvrde

Akcije koje traže potvrdu:

```text
Promijeni PlanItem status
Poveži vanjske promjene sa PlanItem stavkom
Uvezi vanjsku aktivnost
Napravi task iz vanjskih promjena
Ignoriši reconciliation uz razlog
Nastavi rad ako postoji dirty tree
```

View samo emituje signal. Controller otvara confirmation flow i poziva odgovarajući Service.

---

# 17. Acceptance kriterijumi GUI implementacije

1. Korisnik vidi gdje je projekat stao bez otvaranja reporta.
2. Korisnik vidi sljedeći konkretan korak.
3. Korisnik vidi šta mora provjeriti prije nastavka.
4. Neriješene vanjske promjene su jasno vidljive.
5. Vanjske promjene nisu pripisane agentu.
6. IMPLEMENTED, VERIFIED i ACCEPTED su jasno različiti.
7. Projekat se može promijeniti bez blokiranja GUI-ja.
8. Posljednje poznato stanje se prikazuje prije završetka reconciliation-a.
9. Confidence resume sažetka je vidljiv.
10. Ekran radi na 1600×900 i 1920×1080 bez horizontalnog skrolovanja cijelog prozora.
11. Centralne tabele koriste model/view, ne widget po ćeliji.
12. Nijedna Git, API ili disk operacija ne blokira GUI thread.
13. Screenshot implementacije vizuelno odgovara ovoj specifikaciji.
14. View ne importuje GUI Services niti backend module.
15. Controller testovi pokrivaju promjenu projekta, reconciliation warning i korisničko rješavanje događaja.

---

# 18. Šta ne implementirati u ovom ekranu

Ne prikazivati:

- procenat napretka bez objašnjenog pravila;
- avatar korisnika;
- generičko zvono sa notifikacijama;
- procijenjeni trošak bez pouzdanog izvora;
- automatski „DONE“ status;
- automatsku atribuciju vanjskih commitova;
- automatsku promjenu PlanItem statusa na osnovu samog Git diffa;
- token-by-token agent activity;
- sve raw filesystem događaje;
- kontrolu „pauziraj“ za wrapped terminal sesiju.

---

# 19. Redoslijed implementacije

1. Statični View skeleton sa lažnim ViewState podacima.
2. Screenshot provjera rasporeda na 1920×1080.
3. ProjectResumeWidget.
4. ReconciliationWidget.
5. PlanProgressWidget.
6. ActiveSessionsWidget.
7. RecentActivityWidget.
8. OverviewController.
9. GUI Services integracija.
10. WebSocket refresh.
11. Loading/empty/error/offline stanja.
12. DPI i resize provjera.
13. Controller i GUI testovi.
14. Završni screenshot i agent report.

Ne počinjati pixel-poliranje prije nego svi podaci i stanja rade kroz View → Controller → Services tok.
