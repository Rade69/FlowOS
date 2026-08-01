# FlowOS — stroge instrukcije za popravku trenutnog GUI-ja

## Status dokumenta

Ovo je **obavezni korektivni zadatak** za trenutni PySide6 GUI.

Agent ne treba uvoditi nove funkcionalnosti, mijenjati arhitekturu niti raditi širi refaktor. Potrebno je ispraviti postojeći prikaz prema tačno definisanim pravilima ispod.

---

# 1. Glavni cilj

Popraviti trenutni ekran „Pregled“ tako da:

1. svi korisnički vidljivi pojmovi budu na srpskom jeziku;
2. desni panel bude potpuno čitljiv;
3. nijedan važan tekst ne bude odsječen;
4. sadržaj pravilno reaguje na promjenu veličine prozora;
5. aktivne sesije prikazuju stvarno stanje;
6. prazne ili nedovršene komponente ne budu vidljive;
7. statusi budu dosljedni u cijeloj aplikaciji.

---

# 2. Najvažnije pravilo — obavezan prevod svih engleskih pojmova

## 2.1 Obavezno

**Svaki engleski pojam koji korisnik vidi u GUI-ju mora biti zamijenjen srpskim nazivom.**

Ovo se odnosi na:

- statuse;
- naslove;
- nazive sekcija;
- opise;
- dugmad;
- tooltip tekstove;
- badge oznake;
- kolone tabela;
- prazna stanja;
- greške;
- potvrde;
- footer;
- sidebar;
- detalje plana;
- opise Git stanja;
- opise testova;
- tekst u panelu „Gdje si stao“.

## 2.2 Posebno obavezna zamjena

```text
IMPLEMENTED → Implementirano
```

Ne koristiti:

```text
VERIFAJDOVANO
IMPLEMENTED
VERIFIED
ACCEPTED
IN PROGRESS
NOT STARTED
NEEDS REVIEW
ACTIVE
BLOCKED
READY
DONE
```

u korisničkom interfejsu.

Interni enum nazivi mogu ostati na engleskom u kodu i bazi, ali se u GUI-ju moraju prikazivati kroz centralnu mapu prevoda.

---

# 3. Obavezna centralna mapa prevoda

Ne prevoditi pojmove ručno po pojedinačnim widgetima.

Kreirati jednu centralnu mapu, na primjer:

```python
STATUS_LABELS = {
    "NOT_STARTED": "Nije započeto",
    "IN_PROGRESS": "U toku",
    "BLOCKED": "Blokirano",
    "IMPLEMENTED": "Implementirano",
    "VERIFIED": "Provjereno",
    "ACCEPTED": "Prihvaćeno",
    "REJECTED": "Odbijeno",
    "NEEDS_REVIEW": "Potreban pregled",
    "ACTIVE": "Aktivna",
    "COMPLETED": "Završena",
    "INTERRUPTED": "Prekinuta",
    "READY": "Spremno",
    "UNKNOWN": "Nepoznato stanje",
}
```

Dodati centralne mape i za druge pojmove:

```python
UI_LABELS = {
    "overview": "Pregled",
    "projects": "Projekti",
    "sessions": "Sesije",
    "tasks": "Zadaci",
    "agents": "Agenti",
    "worktrees": "Radna stabla",
    "conflicts": "Konflikti",
    "reports": "Izvještaji",
    "settings": "Postavke",
    "resume": "Nastavak rada",
    "external_activity": "Vanjska aktivnost",
    "reconciliation": "Usklađivanje stanja",
    "evidence": "Dokazi",
    "acceptance_criteria": "Kriterijumi prihvatanja",
}
```

Svi widgeti moraju koristiti iste mape.

---

# 4. Obavezni prevodi postojećih pojmova

Koristiti sljedeće prevode:

```text
Overview                    → Pregled
Projects                    → Projekti
Plan                        → Plan
Sessions                    → Sesije
Tasks                       → Zadaci
Agents                      → Agenti
Worktrees                   → Radna stabla
Conflicts                   → Konflikti
Reports                     → Izvještaji
Settings                    → Postavke

ACCEPTED                    → Prihvaćeno
VERIFIED                    → Provjereno
IMPLEMENTED                 → Implementirano
IN_PROGRESS                 → U toku
NOT_STARTED                 → Nije započeto
BLOCKED                     → Blokirano
NEEDS_REVIEW                → Potreban pregled
ACTIVE                      → Aktivna
COMPLETED                   → Završena
READY                       → Spremno
REJECTED                    → Odbijeno

Shared contracts            → Zajednički ugovori
Service runtime             → Rad servisnog procesa
Projects/Tasks API          → API za projekte i zadatke
Wrapper                     → Omotač procesa
Watcher                     → Posmatrač promjena
External activity           → Vanjska aktivnost
Reconciliation              → Usklađivanje stanja
Dirty tree                  → Radno stablo sa neupisanim promjenama
Failing test                → Neuspješan test
Lifecycle test              → Test životnog ciklusa
Acceptance criteria         → Kriterijumi prihvatanja
Evidence                    → Dokazi
Resume                      → Nastavak rada
Where you stopped           → Gdje si stao
Next concrete step          → Sljedeći konkretan korak
Confidence                  → Pouzdanost
Timeline                    → Vremenska linija
Commit                      → Commit
Branch                      → Grana
```

Napomena:

- `Commit` može ostati kao tehnički termin.
- `Branch` u GUI-ju treba prikazivati kao `Grana`.
- `Worktree` u GUI-ju prikazivati kao `Radno stablo`.
- ID-jevi poput `FLOW-103`, `SESSION-42` i Git hash ostaju nepromijenjeni.

---

# 5. Popravka desnog panela

## 5.1 Problem

Trenutno su tekstovi u panelu „Gdje si stao“ i „Detalji stavke plana“ odsječeni.

Primjeri problema:

```text
Force term...
Implementirati supervisor cleanup nakon hard ter...
```

Ovo nije prihvatljivo.

## 5.2 Obavezna struktura

Desni panel mora biti jedan vertikalni `QScrollArea`.

Unutra redom:

```text
Gdje si stao
Detalji stavke plana
Usklađivanje stanja
```

Ne koristiti tri odvojena fiksna panela koji moraju stati u visinu prozora.

## 5.3 Obavezno ponašanje

- minimalna širina desnog panela: 390 px;
- preporučena širina: 410–430 px;
- tekst mora koristiti `wordWrap`;
- kartice ne smiju imati fiksnu visinu;
- sadržaj mora biti dostupan vertikalnim skrolovanjem;
- nijedan važan tekst ne smije biti skraćen elipsom;
- dugmad ne smiju izlaziti van panela;
- scrollbar ne smije prekrivati sadržaj.

---

# 6. Popravka centralne tabele plana

## 6.1 Problem

Nazivi faza i stavki su previše skraćeni.

Primjeri:

```text
Faza 1 — Temelji i prvi vertikalni t...
FLOW-104 Pro...
```

## 6.2 Obavezna korekcija širina

Prioritet širine kolona:

1. naziv faze/stavke — najveća širina;
2. status;
3. agent/sesija;
4. kriterijumi;
5. stanje nastavka.

Kolona naziva ne smije biti žrtvovana zbog preširokih tehničkih kolona.

## 6.3 Prikaz statusa

Statusi moraju biti prikazani kao srpske badge oznake:

```text
Prihvaćeno
Provjereno
Implementirano
U toku
Nije započeto
Blokirano
Potreban pregled
```

Ne prikazivati raw enum vrijednosti.

---

# 7. Sažetak napretka po planu

Trenutni red:

```text
3 ACCEPTED 1 VERIFIED 1 IMPLEMENTED 1 IN PROGRESS 3 NOT STARTED
```

zamijeniti sa:

```text
3 prihvaćene · 1 provjerena · 1 implementirana · 1 u toku · 3 nisu započete
```

Alternativno koristiti male badge oznake, ali isključivo na srpskom.

Ne koristiti velika engleska slova.

---

# 8. Panel „Gdje si stao“

## 8.1 Obavezna hijerarhija

Prikazati ovim redom:

```text
GDJE SI STAO

FLOW-103 — Rad servisnog procesa

Implementirano
Nije provjereno

Posljednji rad
pi · SESSION-42 · juče 18:20

Gdje je rad stao
...

Sljedeći konkretan korak
...

Prije nastavka provjeriti
...

Pouzdanost: Srednja
```

## 8.2 Obavezni uslovi

- statusi moraju biti na srpskom;
- tekst mora biti potpuno vidljiv;
- „Sljedeći konkretan korak“ mora biti vizuelno najistaknutija radna informacija;
- tehnički detalji smiju ostati tehnički samo gdje je potrebno;
- ne koristiti `NEEDS_REVIEW`, `IMPLEMENTED`, `VERIFIED` kao vidljivi tekst.

---

# 9. Aktivne sesije

## 9.1 Problem

Panel prikazuje dvije sesije sa statusom `ACTIVE`, iako jedna može biti završena ili zastarjela.

## 9.2 Obavezno

Panel „Aktivne sesije“ smije prikazivati samo sesije koje su stvarno aktivne.

Podržani prikazi:

```text
Aktivna
Završena
Prekinuta
Nepoznato stanje
```

Ako je sesija završena, ukloniti je iz panela „Aktivne sesije“ i prikazati u istoriji ili nedavnoj aktivnosti.

Ne koristiti `ACTIVE` kao korisnički vidljiv tekst.

---

# 10. Kartica „Aktivni projekat“

## 10.1 Problem

Kartica je trenutno prazna.

## 10.2 Obavezna odluka

Uradi jedno od sljedećeg:

### Opcija A — popuni karticu

```text
AKTIVNI PROJEKAT

FlowOS Core
Plan: FlowOS v3
Stanje: Potreban pregled
Posljednji rad: juče 18:20
```

### Opcija B — privremeno sakrij karticu

Ako podaci još nisu povezani, karticu ne prikazivati.

Prazna kartica nije dozvoljena.

---

# 11. Footer i tehnički statusi

Trenutne engleske pojmove zamijeniti:

```text
Watcher: aktivan
Reconciliation: prije 2 min
```

sa:

```text
Posmatrač: aktivan
Usklađivanje stanja: prije 2 min
```

Preporučeni footer:

```text
Servis: aktivan
API: v1
Baza: flowos.db · u redu
Posmatrač: aktivan
Usklađivanje stanja: prije 2 min
```

Ne koristiti engleske nazive osim tehničkih identifikatora koje nije razumno prevoditi.

---

# 12. Resize i prilagodljivost

GUI mora biti provjeren najmanje na:

```text
1600 × 900
1920 × 1080
```

Obavezno:

- nema horizontalnog skrolovanja cijelog prozora;
- desni panel ostaje čitljiv;
- tabela plana ne odsijeca ključne podatke;
- sidebar ostaje stabilan;
- statusna traka ostaje vidljiva;
- tekst koristi prelamanje;
- ne koristiti apsolutne koordinate;
- koristiti layoute i `QSplitter`.

---

# 13. Zabrane

Agent ne smije:

- uvoditi nove funkcionalnosti;
- mijenjati backend contract bez potrebe;
- mijenjati bazu;
- raditi širi refaktor;
- uvoditi novi framework;
- prevoditi enum vrijednosti u bazi;
- mijenjati ID-jeve;
- koristiti ručne prevode po widgetima;
- ostavljati engleske pojmove u korisničkom interfejsu;
- ostaviti prazne kartice;
- skraćivati ključni tekst elipsom;
- označiti zadatak završenim bez screenshot dokaza.

---

# 14. Obavezni testovi

Dodati ili ažurirati testove koji potvrđuju:

1. `IMPLEMENTED` se prikazuje kao `Implementirano`;
2. `VERIFIED` se prikazuje kao `Provjereno`;
3. `ACCEPTED` se prikazuje kao `Prihvaćeno`;
4. `NEEDS_REVIEW` se prikazuje kao `Potreban pregled`;
5. `ACTIVE` sesija se prikazuje kao `Aktivna`;
6. završena sesija nije u panelu „Aktivne sesije“;
7. prazna kartica aktivnog projekta se ne prikazuje;
8. desni panel koristi scroll area;
9. tekst u „Gdje si stao“ koristi word wrap;
10. centralna mapa prevoda se koristi u svim relevantnim widgetima.

---

# 15. Obavezni screenshot dokazi

Nakon popravke dostaviti stvarne screenshotove aplikacije:

```text
screenshots/
├── overview-1920x1080.png
├── overview-1600x900.png
├── right-panel-scrolled.png
├── translated-statuses.png
└── active-project-card.png
```

Screenshot mora pokazati:

- sve statuse na srpskom;
- `Implementirano`, ne `IMPLEMENTED`;
- čitljiv desni panel;
- puni tekst sljedećeg koraka;
- pravilnu aktivnu sesiju;
- popunjenu ili uklonjenu karticu aktivnog projekta.

---

# 16. Acceptance kriterijumi

Zadatak se može označiti kao završen tek kada su svi uslovi ispunjeni:

```text
[ ] Nijedan korisnički vidljiv status nije na engleskom.
[ ] IMPLEMENTED se svuda prikazuje kao Implementirano.
[ ] VERIFIED se svuda prikazuje kao Provjereno.
[ ] ACCEPTED se svuda prikazuje kao Prihvaćeno.
[ ] IN_PROGRESS se svuda prikazuje kao U toku.
[ ] NOT_STARTED se svuda prikazuje kao Nije započeto.
[ ] NEEDS_REVIEW se svuda prikazuje kao Potreban pregled.
[ ] ACTIVE se svuda prikazuje kao Aktivna.
[ ] Worktrees se prikazuje kao Radna stabla.
[ ] Reconciliation se prikazuje kao Usklađivanje stanja.
[ ] Watcher se prikazuje kao Posmatrač.
[ ] Desni panel je potpuno čitljiv.
[ ] Nijedan važan tekst nije odsječen.
[ ] Desni panel ima vertikalni scroll.
[ ] Prazna kartica aktivnog projekta ne postoji.
[ ] Aktivne sesije prikazuju samo stvarno aktivne sesije.
[ ] GUI radi na 1600×900.
[ ] GUI radi na 1920×1080.
[ ] Testovi prevoda prolaze.
[ ] Screenshot dokazi su priloženi.
```

---

# 17. Završni izvještaj agenta

Agent mora na kraju napisati:

```text
STATUS: OK | PARCIJALNO | BLOKIRANO

IZMIJENJENI FAJLOVI:
- ...

PREVEDENI POJMOVI:
- ...

STATUS IMPLEMENTED:
Prikazuje se kao „Implementirano“: DA/NE

DESNI PANEL:
Potpuno čitljiv: DA/NE

AKTIVNE SESIJE:
Prikazuju stvarno stanje: DA/NE

PRAZNA KARTICA:
Uklonjena ili popunjena: DA/NE

TESTOVI:
- ...

SCREENSHOTOVI:
- ...

OTVORENI PROBLEMI:
- Nema
ili
- ...
```

Ne označavati zadatak kao `OK` ako je ostao makar jedan engleski korisnički pojam u ovom ekranu.
