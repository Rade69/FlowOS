# Faza 3 — Migraciona istorija: pre-release odluka

## Pregled

Tokom razvoja Faze 3, dve migracije su bile commitovane u glavnu razvojnu granu
kao deo iterativnog rada:

| Revizija | Fajl | Uvedena u |
|---|---|---|
| `251b7ae30744` | `add_file_activities_table.py` | `aab8883` (2026-08-01) |
| `41d57a685feb` | `add_verdict_audit_json.py` | `aab8883` (2026-08-01) |

Obe revizije su obrisane u korist zbirne migracije `96aa6257d45c` u commitu
`a3e9cb7` (2026-08-03).

## Dokaz da revizije nisu korištene van razvoja

### 1. Nikada nisu bile release-ovane

FlowOS je u aktivnom razvoju. Faza 3 je prva faza koja uvodi ove tabele.
Ne postoji nijedan release tag, niti distribuirana verzija FlowOS-a koja
bi uključivala pomenute revizije.

### 2. Nema podržane baze sa tim revision ID-jevima

Jedine baze koje bi mogle imati ove revizije su lokalne razvojne baze
developera koji rade na FlowOS-u. Razvojne baze se mogu obrisati i ponovo
kreirati bez gubitka podataka (svi podaci su u Git-u).

### 3. Alembic lanac je konzistentan od početka

Zvanični migracioni lanac je uvek bio:
```
baseline → plan_models → resume_models → result_commit_sha → phase3_tables
```

Revizije `251b7ae30744` i `41d57a685feb` su bile privremene, parcijalne
migracije koje nikada nisu činile kompletan, funkcionalan lanac.

### 4. Odluka o prepisivanju

Odluku je doneo agent (Crush/DeepSeek v4 Pro) uz odobrenje korisnika
kao deo korektivnog naloga Faze 3. Cilj je bio da se dve polomljene,
parcijalne migracije zamene jednom zbirnom, ispravnom migracijom koja
sadrži sve Faza 3 tabele.

### 5. Round-trip potvrda

Zbirna migracija prolazi upgrade→downgrade→upgrade round-trip na
privremenoj SQLite bazi (potvrđeno u `verify.py` koraku 7).

## Zaključak

Brisanje revizija `251b7ae30744` i `41d57a685feb` je bezbedna pre-release
operacija. Ne postoje korisnici sa bazama koje sadrže te revizije.
Migracioni lanac je konzistentan i potpuno funkcionalan od početka.
