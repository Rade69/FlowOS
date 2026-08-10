# FlowOS — detaljan plan unapređenja GUI-ja za Crush agenta

## Dokument

**Projekat:** FlowOS  
**Ulazni bundle:** `FlowOS-source-v0.1.0.zip`  
**Cilj:** unaprijediti postojeći PySide6 GUI bez rušenja trenutne arhitekture i bez širenja scope-a na nove backend faze  
**Primarni ekran:** `Pregled`  
**Arhitektura:** View → Controller → GUI Services → Backend API  
**Jezik GUI-ja:** srpski latinica  
**Statusi:** `Prihvaćeno`, `Provjereno`, `Implementirano`, `U toku`, `Blokirano`, `Nije započeto`

---

# 1. Šta je trenutno implementirano

Postojeći GUI već ima:

- `MainWindow` sa topbarom, sidebarom, centralnim i desnim panelom;
- `PlanProgressView`;
- `ProjectResumeView`;
- `PlanItemDetailsView`;
- `SessionsView`;
- `WorktreesView`;
- `RecentActivityWidget`;
- `GuiApiClient`;
- `OverviewController`;
- automatsko osvježavanje na 10 sekundi;
- prikaz aktivnog projekta;
- osnovnu tamnu temu;
- centralne prevode statusa;
- backend API za:
  - projekte;
  - plan progress;
  - project resume;
  - aktivne sesije;
  - worktree podatke;
  - plan item detalje i kriterijume;
  - progress events;
  - session timeline.

Postojeći GUI nije potrebno ponovo graditi od nule.

---

# 2. Stvarni problemi u trenutnom kodu

## 2.1 `Gdje si stao` postoji, ali nije centralni element

`ProjectResumeView` se prikazuje u desnom panelu i često dobija `NO_HISTORY`.

Početni ekran zato ne odgovara dovoljno jasno:

- šta trenutno radi;
- gdje je rad stao;
- koji je sljedeći potez;
- šta blokira nastavak.

Podaci za taj prikaz djelimično već postoje u `/projects/{project_id}/resume`.

---

## 2.2 Početni ekran daje previše prostora cijelom planu

`PlanProgressView` prikazuje veliku hijerarhijsku tabelu sa svim fazama i stavkama.

To je dobro za posebnu stranicu `Plan`, ali na `Pregled` ekranu:

- zauzima najviše prostora;
- ima horizontalni i vertikalni scrollbar;
- potiskuje informacije o nastavku rada;
- dugi naslovi se sijeku.

---

## 2.3 Veliki prazan prostor iznad sadržaja

U `MainWindow` i page wrapper layoutima postoje veliki margini i neiskorišten prostor.

Na screenshotu najvažniji sadržaj počinje prenisko.

---

## 2.4 Desni panel je često prazan

`ProjectResumeView` prikazuje samo poruku:

```text
Nema prethodne istorije.
```

`PlanItemDetailsView` čeka ručni izbor stavke, ali trenutno nema kompletno povezivanje selekcije plana sa API učitavanjem detalja.

---

## 2.5 Plan tabela vizuelno izgleda kao višestruka selekcija

Tamno plava pozadina više redova stvara utisak da su svi selektovani.

Treba jasno razlikovati:

- normalni red;
- hover;
- selektovani red;
- blokiran red;
- aktivnu stavku;
- završenu stavku.

---

## 2.6 Aktivne sesije prikazuju tehnički ID, ali ne ključni kontekst

`SessionsView` trenutno prikazuje:

```text
Sesija
Agent
Plan stavka
Grana/Worktree
Status
```

Skraćeni session ID ima malu vrijednost za korisnika.

Nedostaju:

- trajanje;
- posljednja aktivnost;
- razumljiv naziv plan stavke;
- signal da sesija zahtijeva pažnju;
- akcija za otvaranje detalja.

---

## 2.7 Nedavna aktivnost je hardkodovana

`RecentActivityWidget` sadrži statičke vrijednosti:

```text
Commit a8f19d2
Testovi: 18/19 prolazi
Sesija pokrenuta
```

Widget nije povezan sa backend timeline API-jem.

---

## 2.8 Status servisa se prikazuje tri puta

Trenutno postoje:

- status u topbaru;
- status pri dnu sidebara;
- status u footeru.

To je vizuelno ponavljanje.

---

## 2.9 Navigacija je ravna i duga

Sve stavke su u jednoj listi bez grupa:

- Pregled;
- Projekti;
- Plan;
- Sesije;
- Zadaci;
- Agenti;
- Radna stabla;
- Konflikti;
- Izvještaji;
- Postavke.

---

## 2.10 Aktivni projekat u sidebaru se siječe

Naziv plana ili aktivne stavke ne staje u postojeću karticu.

Nema:

- word wrap;
- elide ponašanja;
- tooltippa;
- stabilne visine za dvije linije.

---

## 2.11 GUI composition root nije stvarno implementiran

`src/flowos/gui/composition_root.py` je još placeholder i baca:

```python
NotImplementedError("GUI nije implementiran u fazi 0")
```

Stvarno povezivanje svih GUI zavisnosti trenutno se radi direktno u:

```text
src/flowos/gui/app.py
```

To je suprotno deklarisanoj arhitekturi.

---

## 2.12 Greške se ignorišu

U `FlowOsGui._on_error()` trenutno stoji:

```python
pass
```

Korisnik zato ne vidi:

- mrežnu grešku;
- backend 409;
- neispravan JSON;
- prekid servisa;
- neuspjelo učitavanje dijela ekrana.

---

# 3. Ciljno ponašanje početnog ekrana

Početni ekran mora u prvih 5–10 sekundi odgovoriti na tri pitanja:

```text
Šta trenutno radi?
Gdje je posljednji rad stao?
Šta treba uraditi sljedeće?
```

Preporučeni redoslijed sadržaja:

```text
1. Gdje si stao / Sljedeći korak
2. Aktivne sesije
3. Blokatori i upozorenja
4. Trenutna faza plana
5. Nedavna aktivnost
```

Puna tabela plana treba ostati na stranici `Plan`.

---

# 4. Pravila za Crush agenta

## 4.1 Ne rušiti postojeći GUI

Ne praviti novi GUI framework.

Ostati na:

- PySide6;
- Qt Widgets;
- postojećim theme tokenima;
- postojećoj arhitekturi;
- postojećim backend endpointima gdje su dovoljni.

---

## 4.2 Ne uvoditi backend izmjene bez potrebe

Prvo iskoristiti postojeće endpointove:

```text
GET /projects
GET /projects/{project_id}/plan-progress
GET /projects/{project_id}/resume
GET /sessions/active
GET /plan-items/{item_id}
GET /plan-items/{item_id}/criteria
GET /plan-items/{item_id}/progress-events
GET /sessions/{session_id}/timeline
GET /worktrees
```

Backend proširenje dozvoljeno je samo kada GUI podatak stvarno ne postoji.

---

## 4.3 Ne koristiti hardkodovane mock podatke u live modu

U live modu svi prikazi moraju dolaziti iz API-ja ili pokazati jasno prazno stanje.

Mock podaci smiju postojati samo u zasebnom demo/test fixture-u.

---

## 4.4 Zadržati postojeću terminologiju

Obavezni prevodi:

```text
VERIFIED → Provjereno
ACCEPTED → Prihvaćeno
IMPLEMENTED → Implementirano
IN_PROGRESS → U toku
BLOCKED → Blokirano
NOT_STARTED → Nije započeto
```

Ne koristiti mješavinu engleskih i srpskih statusa u korisničkom prikazu.

---

# 5. Plan rada po koracima

# KORAK 1 — urediti GUI composition root

## Cilj

Premjestiti konstrukciju i povezivanje GUI objekata iz `app.py` u pravi composition root.

## Fajlovi

```text
src/flowos/gui/composition_root.py
src/flowos/gui/app.py
```

## Implementacija

Napraviti funkciju:

```python
def create_gui(use_live: bool = True) -> FlowOsGui:
    ...
```

ili:

```python
def create_main_window(use_live: bool = True) -> MainWindow:
    ...
```

Composition root treba konstruisati:

- `MainWindow`;
- `GuiApiClient`;
- `OverviewController`;
- View instance;
- signal veze;
- auto refresh timer;
- page wiring.

`app.py` treba ostati samo executable bootstrap:

```python
app = QApplication(sys.argv)
apply_dark_theme(app)
gui = create_gui(use_live=...)
gui.show()
sys.exit(app.exec())
```

## Acceptance kriterijumi

```text
[ ] composition_root.py više nije placeholder
[ ] app.py nema veliki dependency wiring blok
[ ] View ne konstruiše Controller
[ ] Controller ne konstruiše API klijent
[ ] GUI se pokreće kao ranije
```

---

# KORAK 2 — napraviti novi Overview layout

## Cilj

Pomjeriti fokus sa kompletne tabele plana na nastavak rada.

## Novi raspored

```text
┌─────────────────────────────────────────────────────────────┐
│ GDJE SI STAO                                [Nastavi rad]   │
│ Aktivna stavka · agent · posljednja aktivnost               │
│ Sljedeći konkretan korak                                    │
│ Blokatori / provjera                                        │
└─────────────────────────────────────────────────────────────┘

┌ AKTIVNE SESIJE ──────────────────┬ PAŽNJA ─────────────────┐
│ sesije                           │ blokatori/test/konflikt │
└──────────────────────────────────┴──────────────────────────┘

┌ TRENUTNA FAZA ───────────────────┬ DETALJI STAVKE ─────────┐
│ relevantne stavke                │ kriterijumi i status    │
└──────────────────────────────────┴──────────────────────────┘

┌ NEDAVNA AKTIVNOST ─────────────────────────────────────────┐
│ timeline                                                    │
└─────────────────────────────────────────────────────────────┘
```

## Fajlovi

```text
src/flowos/gui/views/overview_skeleton.py
src/flowos/gui/app.py
src/flowos/gui/views/project_resume.py
```

## Implementacija

Napraviti novi widget:

```python
class ResumeHeroView(QFrame):
    continue_requested = Signal()
    report_requested = Signal(str)
```

Prikazuje:

- aktivnu plan stavku;
- agenta/sesiju;
- posljednju aktivnost;
- gdje je rad stao;
- sljedeći korak;
- preconditions;
- confidence;
- blokatore;
- dugme `Nastavi rad`.

`ProjectResumeView` se može:

- preraditi u hero komponentu;
- ili ostaviti kao detaljni prikaz, a napraviti novi sažeti widget.

## Prazno stanje

Ako `NO_HISTORY`, ne prikazivati samo praznu poruku.

Prikazati:

```text
Još nema završene sesije za ovaj projekat.

Aktivne sesije: 1
Posljednja aktivnost: prije 4 minute

Sažetak će biti kreiran nakon završetka sesije.
```

Ako postoji aktivna sesija, koristiti sesijske podatke kao fallback.

## Acceptance kriterijumi

```text
[ ] početni ekran prvo prikazuje nastavak rada
[ ] nema velikog praznog prostora iznad sadržaja
[ ] NO_HISTORY stanje je informativno
[ ] aktivna sesija se koristi kao fallback
[ ] dugme Nastavi rad emituje signal
```

---

# KORAK 3 — zamijeniti punu plan tabelu sažetkom aktivne faze

## Cilj

Na `Pregled` ekranu prikazati samo trenutno relevantne plan stavke.

## Novi widget

```python
class CurrentPhaseView(QFrame):
    item_selected = Signal(str)
    open_full_plan_requested = Signal()
```

## Prikaz

Najviše:

- jedna stavka `U toku`;
- sve blokirane stavke;
- dvije sljedeće `Nije započeto`;
- posljednja `Implementirano` ili `Provjereno`.

Primjer:

```text
FAZA 4 — Worktree tok

U TOKU
FLOW-403 Guided integration

BLOKIRANO
FLOW-404 Cleanup i retention

SLJEDEĆE
FLOW-405 Status worktree-a u GUI-ju
FLOW-406 Build i distribucija
```

Na dnu:

```text
[Otvori cijeli plan]
```

## Puna tabela

Postojeći `PlanProgressView` ostaviti za stranicu `Plan`.

Ne brisati ga.

## Potrebne promjene podataka

`OverviewController._on_plan_progress()` trenutno vraća:

```text
plan_title
plan_status
phases
total
completed
blocked
```

Provjeriti strukturu `phases`.

Ako endpoint već vraća grupisane stavke, filtrirati ih u GUI Controlleru.

Ako ne vraća, koristiti:

```text
GET /plans/{plan_id}/items
```

i dodati odgovarajući API metod.

## Acceptance kriterijumi

```text
[ ] Pregled ne prikazuje cijeli plan
[ ] prikazuje aktivnu fazu
[ ] prikazuje stavku u toku
[ ] prikazuje blokirane stavke
[ ] prikazuje sljedeće stavke
[ ] puna tabela ostaje na Plan stranici
```

---

# KORAK 4 — statusni sažetak pretvoriti u klikabilne badge elemente

## Cilj

Poboljšati skeniranje statusa bez SaaS kartica.

## Novi widget

```python
class StatusSummaryBar(QFrame):
    status_selected = Signal(str)
```

Prikaz:

```text
[3 Prihvaćeno]
[1 Provjereno]
[1 Implementirano]
[1 U toku]
[1 Blokirano]
[23 Nije započeto]
```

## Vizuelna pravila

- mala visina;
- suptilna pozadina;
- statusna boja samo na broju, tački ili lijevoj liniji;
- bez velikih obojenih površina;
- klik filtrira trenutni phase prikaz ili otvara Plan stranicu sa filterom.

## Acceptance kriterijumi

```text
[ ] statusi se lako skeniraju
[ ] boje odgovaraju statusima
[ ] klik emituje tačan status
[ ] nema prikaza neizračunatog procenta
```

---

# KORAK 5 — povezati izbor plan stavke sa detaljima

## Cilj

Desni panel ne smije ostati prazan kada postoji aktivna ili selektovana stavka.

## API metode za dodavanje

U `GuiApiClient` dodati:

```python
plan_item_received = Signal(dict)
criteria_received = Signal(list)
progress_events_received = Signal(list)

def get_plan_item(item_id: str)
def get_plan_item_criteria(item_id: str)
def get_plan_item_progress_events(item_id: str)
```

## Controller

Dodati `PlanItemController` ili proširiti `OverviewController`:

```python
plan_item_details_loaded = Signal(dict)
```

Controller treba spojiti:

- plan item;
- criteria;
- recent progress events;
- povezanu sesiju ako postoji.

## View

`PlanItemDetailsView` treba prikazati:

```text
FLOW-403 — Guided integration
Status: U toku
Agent: Claude Code
Sesija: SESSION-42
Worktree: ...
Kriterijumi: 4/5
Posljednja promjena: ...
```

Kriterijume prikazati sa:

```text
✓ passed
○ pending
! failed
```

## Automatska selekcija

Redoslijed:

1. stavka `IN_PROGRESS`;
2. blokirana stavka;
3. posljednje promijenjena;
4. prva stavka aktivne faze.

## Acceptance kriterijumi

```text
[ ] aktivna stavka automatski je selektovana
[ ] klik na stavku učitava detalje
[ ] kriterijumi se prikazuju
[ ] desni panel nije prazan bez opravdanog razloga
```

---

# KORAK 6 — unaprijediti SessionsView

## Cilj

Sesije trebaju biti operativne, ne samo tehnički popis.

## Nove kolone

```text
Agent
Plan stavka
Radno stablo
Trajanje
Posljednja aktivnost
Status
```

Session ID ukloniti iz glavne tabele.

Puni ID staviti u:

- tooltip;
- data role;
- detaljni panel.

## Potrebni podaci

`SessionResponse` već ima:

```text
started_at
last_activity_at
worktree_path
branch_name
status
```

Controller trenutno ne prosljeđuje `last_activity_at`.

Dodati:

```python
"last_activity_at": s.get("last_activity_at")
```

Izračunavanje trajanja i relativnog vremena raditi u GUI presentation helperu.

## Novi signal

```python
session_selected = Signal(str)
```

Klik treba otvoriti session detalje ili vremensku liniju.

## Acceptance kriterijumi

```text
[ ] nema dominantnog session ID-a
[ ] prikazano trajanje
[ ] prikazana posljednja aktivnost
[ ] worktree je razumljivo skraćen
[ ] puni podaci su u tooltipu
[ ] klik emituje session ID
```

---

# KORAK 7 — povezati RecentActivityWidget sa timeline API-jem

## Cilj

Ukloniti hardkodovane aktivnosti.

## API

Provjeriti postojeći endpoint za session timeline.

Ako postoji:

```text
GET /sessions/{session_id}/timeline
```

dodati u `GuiApiClient`:

```python
timeline_received = Signal(dict)

def get_session_timeline(session_id: str, page: int = 1, page_size: int = 20)
```

Ako je potreban project timeline, koristiti aktivnu sesiju kao početni izvor za MVP.

## View model

Svaki događaj mapirati na:

```text
id
type
label
summary
relative_time
severity
source
```

## Vizuelni tipovi

```text
GIT
TEST
SESIJA
PLAN
KONFLIKT
IZVJEŠTAJ
AKTIVNOST
```

Ne koristiti emoji koji zavise od fonta.

Koristiti kratke tekstualne badge oznake.

## Primjer

```text
TEST      18/19 testova prolazi          prije 2 min
GIT       Commit a8f19d2                 prije 12 min
SESIJA    Claude Code pokrenut           prije 42 min
PLAN      FLOW-102 → Provjereno          juče
```

## Acceptance kriterijumi

```text
[ ] nema hardkodovanih aktivnosti u live modu
[ ] timeline se učitava iz API-ja
[ ] prikazana vrsta događaja
[ ] relativno vrijeme
[ ] tačno vrijeme u tooltipu
[ ] dugme otvara punu vremensku liniju
```

---

# KORAK 8 — dodati blokatore i upozorenja

## Cilj

Na početnom ekranu odmah prikazati ono što zahtijeva pažnju.

## Novi widget

```python
class AttentionPanel(QFrame):
    item_activated = Signal(str, str)
```

Prikazuje najviše 3–5 stavki:

- otvoren konflikt;
- failed verification;
- blokirana plan stavka;
- stale session;
- Git vanjske promjene;
- dirty worktree;
- backend offline.

## Izvori

Za MVP koristiti:

- `resume.open_blockers_json`;
- reconciliation podatke;
- plan blocked count;
- session status;
- worktree dirty/conflict status.

Ako konkretni detalji nisu dostupni, prikazati sažetak, ne izmišljati.

## Acceptance kriterijumi

```text
[ ] upozorenja su vidljiva bez skrolovanja
[ ] nema lažnih blokatora
[ ] klik vodi na relevantni ekran
[ ] prazno stanje glasi „Nema otvorenih blokatora“
```

---

# KORAK 9 — urediti topbar

## Cilj

Prikazati kontekst projekta bez dupliranja statusa.

## Promjene

Trenutno se prikazuje:

```text
FlowOS | Projekat: FlowOS Core | Ažurno
```

Cilj:

```text
FlowOS Core
Faza 4 · Worktree tok
1 aktivna sesija · Git čist
```

## Topbar treba imati

- naziv projekta;
- aktivnu fazu;
- broj aktivnih sesija;
- Git/reconciliation status;
- jedan status servisa;
- refresh dugme sa tooltipom.

## Ukloniti

- status servisa iz sidebara;
- duplu status poruku ako footer već sadrži detalje.

## Acceptance kriterijumi

```text
[ ] status servisa nije prikazan tri puta
[ ] projekat je jasno vidljiv
[ ] aktivna faza je vidljiva
[ ] refresh ima tooltip
[ ] refresh pokazuje loading stanje
```

---

# KORAK 10 — grupisati sidebar navigaciju

## Cilj

Poboljšati preglednost bez promjene ruta.

## Grupe

```text
RAD
Pregled
Plan
Zadaci
Sesije

NADZOR
Agenti
Radna stabla
Konflikti
Izvještaji

SISTEM
Projekti
Postavke
```

## Aktivni projekat

Kartica treba prikazati:

```text
FlowOS Core
Novi detaljan plan realizacije

Faza 4 · 1 aktivna sesija
```

## Tehničke korekcije

- `QLabel.setWordWrap(True)`;
- maksimalno dvije linije;
- tooltip sa punim tekstom;
- izbjegavati fiksnu prenisku visinu;
- ne prikazivati status servisa u ovoj kartici.

## Acceptance kriterijumi

```text
[ ] navigacija ima tri grupe
[ ] aktivni projekat se ne siječe
[ ] puni naziv je dostupan u tooltipu
[ ] aktivna stavka ostaje jasno označena
```

---

# KORAK 11 — popraviti vizuelno stanje plan tabele

## Cilj

Jasno razlikovati stanje reda.

## Pravila

### Normalni red

```text
neutralna pozadina
```

### Hover

```text
blago svjetlija neutralna
```

### Selekcija

```text
tanka plava lijeva linija
vrlo blaga plava pozadina
```

### U toku

```text
žuta tačka ili status badge
```

### Blokirano

```text
crvena tačka ili tanka crvena linija
```

### Provjereno/Prihvaćeno

```text
tirkizna/zelena statusna oznaka
```

Ne bojiti cijeli red jakom statusnom bojom.

## Fajlovi

```text
src/flowos/gui/views/plan_progress.py
src/flowos/gui/theme/tokens.py
```

## Acceptance kriterijumi

```text
[ ] samo jedan red izgleda selektovano
[ ] status se vidi bez bojenja cijelog reda
[ ] kontrast ostaje čitljiv
[ ] disabled i hover stanja su jasna
```

---

# KORAK 12 — smanjiti prazne margine i poboljšati resize

## Cilj

Iskoristiti prostor efikasnije na 1600×900 i 1920×1080.

## Promjene

- smanjiti top margin centralnog sadržaja;
- pregledati `SPACING_XXL` u page wrapperima;
- koristiti `QSplitter` stretch faktore;
- omogućiti da desni panel pamti širinu;
- minimalna širina desnog panela 320–340 px;
- centralni panel ne smije dobiti horizontalni scrollbar zbog loših fiksnih kolona.

## Acceptance kriterijumi

Testirati na:

```text
1366×768
1600×900
1920×1080
```

Na 1366×768:

- ključni resume sadržaj mora biti vidljiv;
- UI ne smije biti neupotrebljiv;
- horizontalni scrollbar smije postojati samo gdje je stvarno potreban.

---

# KORAK 13 — implementirati korisnički prikaz grešaka

## Cilj

Zamijeniti:

```python
def _on_error(self, msg: str):
    pass
```

## Novi widget

```python
class NotificationBanner(QFrame):
    retry_requested = Signal()
```

Podržati:

```text
INFO
WARNING
ERROR
OFFLINE
```

## Ponašanje

- mrežna greška: prikaz `Servis nije dostupan`;
- backend 409: prikaz poslovne poruke;
- ponovni uspješan health check: ukloniti offline banner;
- ne koristiti modal za svaku refresh grešku;
- modal koristiti samo za destruktivne akcije.

## Acceptance kriterijumi

```text
[ ] greške nisu ignorisane
[ ] korisnik vidi offline stanje
[ ] automatski refresh ne otvara beskonačne modale
[ ] retry je moguć
```

---

# KORAK 14 — uvesti prezentacione helpere

## Cilj

Ne rasipati formatiranje po View klasama.

## Novi fajl

```text
src/flowos/gui/presentation.py
```

## Funkcije

```python
def format_relative_time(value: str | datetime | None) -> str
def format_duration(started_at, ended_at=None) -> str
def short_sha(value: str | None) -> str
def short_path(value: str | None, max_length: int = 40) -> str
def safe_text(value, fallback="—") -> str
def status_badge_text(status: str) -> str
```

## Pravila

- bez poslovne logike;
- bez API poziva;
- bez baze;
- potpuno testabilno.

---

# KORAK 15 — testovi

## Obavezni testovi za View/Controller tok

Dodati `tests/gui/`.

### Overview

```text
test_resume_hero_renders_resume_data
test_resume_hero_uses_active_session_fallback
test_no_history_state_is_informative
test_current_phase_selects_in_progress_item
test_current_phase_shows_blocked_and_next_items
```

### Plan detalji

```text
test_plan_item_selection_requests_details
test_plan_item_details_renders_criteria
test_active_item_is_auto_selected
```

### Sesije

```text
test_sessions_view_shows_duration
test_sessions_view_shows_last_activity
test_session_row_emits_full_session_id
```

### Timeline

```text
test_recent_activity_uses_api_data
test_activity_type_is_mapped
test_relative_time_is_rendered
```

### Sidebar/Topbar

```text
test_sidebar_groups_exist
test_project_name_wraps_or_elides
test_service_status_not_duplicated
```

### Greške

```text
test_error_banner_is_shown
test_offline_banner_clears_after_health_success
```

### Arhitektura

Proširiti architecture test:

```text
GUI View ne importuje QNetworkAccessManager
GUI View ne importuje backend service
Controller ne importuje PySide6 widget klase
presentation helper ne importuje API ili ORM
```

---

# 6. Preporučeni commit redoslijed

Crush agent treba praviti male commitove.

```text
refactor(gui): implement GUI composition root
feat(gui): add resume hero and overview layout
feat(gui): add current phase summary
feat(gui): connect plan item details
feat(gui): improve active sessions presentation
feat(gui): load recent activity from timeline
feat(gui): add attention panel and error banner
refactor(gui): group sidebar and simplify service status
style(gui): improve row states spacing and responsive layout
test(gui): cover overview presentation and controller wiring
```

Ne raditi sve u jednom commitu.

---

# 7. Verifikacija poslije svakog većeg koraka

Pokrenuti:

```bash
ruff format --check src/ tests/ scripts/
ruff check src/ tests/ scripts/
python -m mypy src --explicit-package-bases
pytest -q
python scripts/verify.py
```

Pored automatizovanih testova obavezno ručno provjeriti:

```text
GUI startuje bez servisa
GUI startuje sa servisom
projekat se učitava
resume se prikazuje
aktivna sesija se prikazuje
plan item detalji se učitavaju
timeline se učitava
resize radi
offline stanje je vidljivo
```

---

# 8. Definicija završetka

Ovaj GUI zadatak je završen kada:

```text
[ ] početni ekran prvo prikazuje Gdje si stao
[ ] korisnik vidi sljedeći konkretan korak
[ ] aktivna sesija je vidljiva i razumljiva
[ ] blokatori su vidljivi bez skrolovanja
[ ] početni ekran ne prikazuje cijeli plan kao dominantni sadržaj
[ ] aktivna plan stavka automatski otvara detalje
[ ] recent activity dolazi iz API-ja
[ ] nema hardkodovanih live podataka
[ ] status servisa nije dupliran
[ ] projekat i plan se ne sijeku
[ ] greške se prikazuju korisniku
[ ] GUI wiring je u composition_root.py
[ ] svi postojeći testovi prolaze
[ ] novi GUI testovi prolaze
[ ] nije započeta nova backend faza
```

---

# 9. Šta ne raditi u ovom zadatku

Ne implementirati:

- novi task management sistem;
- automatsko pokretanje agenata;
- novi conflict engine;
- novi worktree backend;
- automatski Git merge;
- cloud sync;
- timske funkcije;
- avatare;
- notification centar;
- veliki dizajn sistem od nule;
- kompletnu novu bazu;
- Fazu 5 funkcionalnosti.

Ovaj zadatak je isključivo:

```text
unapređenje postojećeg FlowOS GUI-ja
na osnovu već postojećih podataka i endpointa
```

---

# 10. Završni izvještaj Crush agenta

Na kraju napraviti:

```text
agent_reports/YYYY-MM-DD_flowos-gui-overview-unapredjenje.md
```

Izvještaj mora sadržati:

- šta je urađeno;
- koje fajlove je mijenjao;
- koje endpointove je koristio;
- da li je bilo backend izmjena;
- screenshot prije i poslije;
- test rezultate;
- poznata ograničenja;
- sljedeći preporučeni korak.

Završni status koristiti samo ako je tačan:

```text
IMPLEMENTIRANO
```

Nakon nezavisnog pregleda može preći u:

```text
PROVJERENO
```
