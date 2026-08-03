# FlowOS — nezavisni pregled `FLOW-PHASE3(1).zip`

## Konačna ocjena

**Status: NIJE PROVJERENO.**

Paket pokazuje stvaran napredak i `verify.py` u dostavljenom radnom stanju prijavljuje 6/6 prolaza sa 293 testa. Međutim, bundle nije reproducibilan iz čistog Git stanja, sadrži rad kasnijih faza, a nekoliko ključnih acceptance zahtjeva je samo djelimično implementirano ili nije stvarno dokazano.

Zbog toga tvrdnja iz `README_REVIEW.md`:

```text
Status: OK
Nezavršeni kriterijumi: Nema
Faza 3 kompletirana
```

nije podržana sadržajem paketa.

---

# 1. Git i reproducibilnost — blokirajuće

`git_status.txt` nije čist. Postoje izmijenjeni, obrisani i brojni untracked fajlovi.

Posebno:

```text
?? file
?? src/artifacts/
?? phase5_models.py
?? phase6_models.py
?? phase7_models.py
?? test_phase5.py
?? test_phase6.py
?? test_phase7.py
```

Tu su i rekonstruisani adapteri, dodatni testovi i agent report.

To znači da ne postoji dokaz da je:

```text
testirani kod = commitovani kod = source/ u bundle-u
```

`environment.txt` navodi samo:

```text
Commit before: 51da407
```

Nema završnog HEAD commita Faze 3.

## Obavezno

- izdvojiti samo Fazu 3;
- commitovati sav potreban kod;
- ukloniti kasnije faze iz branch-a/bundle-a;
- `git status --short` mora biti prazan;
- bundle mora biti generisan iz završnog commita.

---

# 2. Scope Faze 3 je prekršen

Bundle sadrži:

```text
phase5_models.py
phase6_models.py
phase7_models.py
test_phase5.py
test_phase6.py
test_phase7.py
test_worktree.py
```

Agent report dodatno priznaje:

```text
Phase 5-7 modeli/servisi — kreirani skeleton-i
WorktreeService, JobExecution — skeleton-i
```

To direktno krši nalog da se ne započinju faze 4–7.

Činjenica da su neki od tih fajlova untracked ne rješava problem; upravo potvrđuje da je radno stablo pomiješano.

---

# 3. Alembic provjera nije dovoljna

`verify.py` pokreće samo:

```bash
alembic upgrade head
```

Ne pokreće traženi round-trip:

```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

Agent je obrisao migracije:

```text
251b7ae30744_add_file_activities_table.py
41d57a685feb_add_verdict_audit_json.py
```

To je posebno rizično jer Faza 3 tvrdi da koristi:

- trajni `FileActivity`;
- `verdict_audit_json`.

Prolazak `upgrade head` nad postojećom lokalnom bazom ne dokazuje da potpuno nova baza dobija sve potrebne tabele i kolone.

## Obavezno

- dokazati migraciju na potpuno praznoj bazi;
- provjeriti da postoje `file_activities` i verdict audit struktura;
- izvršiti upgrade/downgrade/upgrade;
- ne brisati migracije samo da graf postane zelen.

---

# 4. ArtifactStore koristi pogrešan podrazumijevani direktorijum

U `verification/service.py` root se računa sa pet `parent` nivoa:

```python
Path(__file__).resolve().parent.parent.parent.parent.parent / "artifacts"
```

Za fajl:

```text
src/flowos/service/services/verification/service.py
```

to završava u:

```text
src/artifacts/
```

`git_status.txt` upravo potvrđuje:

```text
?? src/artifacts/
```

Dakle prethodno prijavljeni problem nije riješen.

Runtime artefakti ne smiju biti zapisivani unutar `src/`.

## Obavezno

Koristiti:

```text
<project-root>/artifacts/
```

ili korisnički AppData direktorijum, uz eksplicitno konfigurisan root.

Dodati test koji potvrđuje da putanja nije ispod `src/`.

---

# 5. Artifact zapis nije stvarno atomski

Docstring tvrdi:

```text
Atomski čuva verify artefakt
```

ali kod direktno radi `write_text()` u finalni direktorijum.

Ako proces padne između zapisa, ostaje parcijalan artefakt.

## Obavezno

- pisati u privremeni direktorijum;
- završiti sve fajlove;
- zatim atomski rename u finalni direktorijum;
- testirati prekid/parcijalni zapis.

---

# 6. STALE_SESSION nije završena

Kod kaže:

```python
# PID provera je skupa — preskačemo je za sada
pid = session.pid
```

Dakle PID se samo zapisuje u evidence, ali se ne provjerava da li je proces živ.

Heartbeat se takođe ne provjerava, iako docstring tvrdi suprotno.

Sesija se može označiti stale samo na osnovu starog `last_activity_at`.

To ne ispunjava acceptance kriterijum:

```text
STALE_SESSION koristi process/heartbeat signal
```

## Obavezno

U procjenu uključiti stvarni:

- process alive status;
- heartbeat;
- session status;
- timeout politiku.

---

# 7. SessionCompletion i dalje prima spoljašnji `repo_path`

Potpis je i dalje:

```python
complete_session(session_id, repo_path, ...)
```

Kasnije ga prepisuje sa:

```python
repo_path = session.worktree_path or session.repo_path
```

To je zbunjujući i nepotreban API.

Još važnije, kada `project_id` nedostaje, kod postavlja:

```python
project_id = ""
```

Agent report tvrdi da koristi `"UNKNOWN"`, ali dostavljeni source koristi prazan string.

To je direktna kontradikcija između izvještaja i koda.

## Obavezno

- ukloniti spoljašnji `repo_path` ako nije potreban;
- ne koristiti `project_id=""`;
- nedostajući projekt tretirati kao validacionu grešku ili eksplicitno neprovjereno stanje.

---

# 8. Git greška se i dalje samo loguje

Ako Git čitanje padne:

```python
except Exception:
    logger.exception(...)
```

tok se nastavlja i report se ipak kreira.

Nema eksplicitnog stanja:

```text
GIT_NOT_VERIFIED
```

niti se sprječava pogrešan zaključak o NO_COMMIT.

## Obavezno

- sačuvati Git verification status;
- report mora jasno navesti da Git nije provjeren;
- NO_COMMIT se ne smije pouzdano zaključivati bez Git stanja.

---

# 9. Report audit nije dovoljno robustan

`set_verdict()` čuva audit kao JSON listu u istom report redu.

To je bolje od prepisivanja bez istorije, ali:

- nema zasebnog audit entiteta;
- nema identiteta aktora;
- nema prethodnog i novog statusa;
- nema dokaza da nova baza dobija audit kolonu jer je migracija obrisana;
- konkurentni update može prepisati istoriju.

Korektivni nalog je tražio audit zapis sa:

```text
report_id
previous_verdict
new_verdict
previous_status
new_status
actor
notes
created_at
```

Dostavljeni zapis nema sve to.

---

# 10. Timeline nije potpuno objedinjen

Docstring tvrdi da objedinjuje:

```text
SessionEvent, FileActivity, Conflict, Verification, AgentReport
```

Kod uključuje:

- SessionEvent;
- FileActivity;
- Conflict;
- AgentReport.

Ne postoji stvarni Verification izvor.

Takođe nema standardizovana polja za svaki događaj:

```text
level
project_id
session_id
metadata
```

Sortiranje je samo:

```python
all_events.sort(key=lambda e: e["occurred_at"] or "")
```

Nema determinističkog sekundarnog ključa, pa pagination može biti nestabilna kada više događaja ima isti timestamp.

---

# 11. E2E test nije puni vertikalni dokaz

Naziv i komentar tvrde puni tok, ali sam test kaže:

```text
WRITE_WRITE detaljno testiran u test_conflicts.py
```

To znači da E2E ne potvrđuje stvarni lanac:

```text
watcher → activity → atribucija → WRITE_WRITE
```

kao jednu cjelinu.

Timeline provjera je samo:

```python
assert tl["total"] >= 1
```

To ne dokazuje da su u timeline-u prisutni:

- activity;
- konflikt;
- verification;
- report;
- completion događaj.

Pored toga, verification se u testu pokreće direktno servisom, a ne nužno kroz stvarni `SessionCompletionService` tok.

## Obavezno

Napraviti jedan pravi vertikalni test koji provjerava svaki konkretan rezultat i ID veze između koraka.

---

# 12. Watcher konflikt integracija je duplirana umjesto callback registracije

`ActivityService.record_file_event()` već ima sistem conflict callbackova.

Međutim composition root nakon upisa aktivnosti ručno kreira novi `ConflictDetectionService` i poziva:

```python
conflict_svc.on_file_activity(_activity, active)
```

To radi, ali zaobilazi vlastiti callback mehanizam ActivityService-a.

Time ostaju dva moguća modela integracije:

- registrovani callback;
- ručni poziv iz composition root-a.

Treba izabrati jedan autoritativni tok da se izbjegne duplo procesiranje.

---

# 13. Conflict evidence je djelimičan

WRITE_WRITE ima event ID-jeve i conflict key, što je napredak.

Ali Conflict ORM, prema dostavljenom kodu, ne pokazuje trajna posebna polja:

```text
first_seen_at
last_seen_at
detector_version
confidence
conflict_key
```

Većina podataka je samo unutar JSON evidence.

Postojeći konflikt se samo preskače:

```python
if self._find_existing_conflict(...):
    continue
```

Ne ažurira se `last_seen_at` niti evidence novim događajem.

To ne ispunjava zahtjev za deduplikaciju uz ažuriranje postojećeg otvorenog konflikta.

---

# 14. Verify rezultat i test broj nisu dosljedno dokumentovani

Dokumenti navode različite rezultate:

- `README_REVIEW.md`: 293 testa;
- `agent_report.md`: na jednom mjestu 293, u završnom bloku 265;
- `plan_item.md`: 293.

Takva nedosljednost umanjuje pouzdanost izvještaja.

`README_REVIEW.md` tvrdi da nema nezavršenih kriterijuma, dok `agent_report.md` priznaje:

- GitNexus nije pokrenut;
- fajlovi rekonstruisani iz PYC;
- skeleton-i kasnijih faza;
- izgubljeni untracked fajlovi.

---

# 15. Rekonstrukcija iz PYC nije prihvatljiv dokaz izvornog koda

Agent navodi da su neki Python fajlovi rekonstruisani iz `.pyc` keša nakon gubitka untracked fajlova.

To je visok rizik jer dekompajlirani kod može:

- izgubiti komentare i tipove;
- promijeniti strukturu;
- biti drugačiji od originala;
- ne odgovarati namjeri autora.

Takvi fajlovi moraju biti:

- posebno navedeni;
- ručno pregledani;
- pokriveni testovima;
- commitovani;
- odvojeni od scope-a Faze 3 ako pripadaju kasnijim fazama.

---

# Šta je stvarno dobro

Sljedeće popravke djeluju stvarno prisutno:

- `check_untyped_defs = true`;
- `verify.py` koristi cijeli `src`;
- Ruff i mypy prijavljuju prolaz;
- `tree_identity` koristi worktree prije repo putanje;
- Conflict servis koristi `FileActivity` ORM;
- watcher zapisuje aktivnosti i pokreće konflikt detekciju;
- WRITE_WRITE evidence uključuje activity event ID-jeve;
- javni `GitStateReader.read_state()` se koristi;
- `exit_code=None` daje `NEEDS_REVIEW`;
- Verification koristi `sys.executable`;
- ArtifactStore zapisuje command/stdout/stderr/metadata i hash;
- report update koristi eksplicitnu allowlistu;
- Timeline ima enum i pagination validaciju;
- postoje pozitivni i negativni E2E testovi;
- ukupno 293 testa u dostavljenom radnom stanju prolazi.

To je značajan napredak, ali nije dovoljno za status **Provjereno**.

---

# Prioritetni redoslijed popravke

## P0 — prije bilo kakvog novog funkcionalnog rada

1. Očistiti Git i napraviti završni commit.
2. Izbaciti faze 4–7 iz scope-a i bundle-a.
3. Popraviti migracioni lanac na praznoj bazi.
4. Premjestiti ArtifactStore van `src/`.
5. Napraviti reproducibilan bundle iz commita.

## P1 — funkcionalni blokatori

6. Završiti STALE_SESSION sa proces/heartbeat provjerom.
7. Popraviti SessionCompletion `project_id` i Git-not-verified stanje.
8. Dovršiti audit model.
9. Dodati Verification događaje u Timeline.
10. Ažurirati postojeći konflikt umjesto samo preskakanja.

## P2 — dokaz

11. Napraviti stvarni puni vertikalni E2E test.
12. Dodati Alembic round-trip test.
13. Dodati test da artifact root nije unutar `src/`.
14. Pokrenuti čistu verifikaciju iz završnog commita.
15. Generisati novi `FLOW-PHASE3-VERIFIED.zip`.

---

# Završna matrica

```text
Git status čist: NE
Scope samo Faza 3: NE
Ruff format: DA
Ruff lint: DA
Mypy cijelog src: DA
GUI tijela provjerena: DA
Pytest: DA, 293 testa
Architecture testovi: DA
Alembic upgrade: DA
Alembic round-trip na praznoj bazi: NIJE DOKAZANO
FileActivity migracija na praznoj bazi: NIJE DOKAZANA
tree_identity: DA
Watcher → activity: DA
Watcher → WRITE_WRITE puni E2E: NIJE DOKAZANO
STALE process/heartbeat: NE
SessionCompletion stvarni kontekst: PARCIJALNO
Git failure stanje: NE
Verification sys.executable: DA
Verification artefakti: PARCIJALNO
Artifact root van src: NE
Artifact atomski zapis: NE
Report allowlista: DA
Verdict audit: PARCIJALNO
Timeline validacija: DA
Timeline svi izvori: NE
Puni vertikalni E2E: NE
Reproducibilan završni bundle: NE
```

## Preporučeni status

```text
FAZA 3: IMPLEMENTIRANA DJELIMIČNO — NIJE PROVJERENA
```
