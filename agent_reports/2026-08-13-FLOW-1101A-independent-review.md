---
flowos_report_version: 1
report_id: 2b782b66-cd81-419a-8599-0e0da7b21a8b
agent: claude
model: claude-sonnet-5
session_id: unknown
report_type: review
work_status: completed
tasks:
  - FLOW-1101A
commits: []
created_at: 2026-08-13T08:40:14+02:00
---

# FLOW-1101A — Explicit local DB schema repair, independent review

## Scope

READ ONLY. Nije mijenjan kod, nisu mijenjani testovi, nije pokretan repair nad
stvarnom lokalnom bazom, nije pravljen commit. Zaključana arhitektonska odluka:
**DETECT + EXPLICIT SAFE REPAIR** — normalan startup NE smije tiho mutirati bazu.

Baseline: `6c5461a`.

## 1. Git / scope review

```
git status --short
 M src/flowos/service/app.py
?? agent_reports/2026-08-13-FLOW-1101A-local-db-schema-drift-analysis.md
?? agent_reports/2026-08-13-FLOW-1101A-local-db-schema-repair-implementation.md
?? src/flowos/service/services/infrastructure/persistence/schema_repair.py
?? tests/unit/test_schema_repair.py
(plus prethodno untracked docs/dogfooding fajlovi, nevezani za ovu izmjenu)
```
```
git diff --stat
 src/flowos/service/app.py | 45 ++++++++++++++++++++++++++++++++++++++++-----
 1 file changed, 40 insertions(+), 5 deletions(-)
```

Scope tačno odgovara očekivanom. Nema drugog produkcijskog fajla izmijenjenog.
**Nema scope deviation.**

## 2. Architecture contract

Pročitan pun diff `app.py`. Potvrđeno:

- **A/B**: `main()` poziva `_run_migrations()`, koja poziva samo
  `inspect_local_schema()` (read-only introspekcija). Nema poziva
  `repair_database()` bilo gdje u `app.py` (potvrđeno grep-om — 0 pojavljivanja).
- **C**: ako `inspection.state` nije `KNOWN_REPAIRABLE_DRIFT`/`UNKNOWN_DRIFT`
  (tj. `HEALTHY`), izvršenje nastavlja na `create_sqlite_engine()` +
  `Base.metadata.create_all()` (legacy bootstrap, samo za DB bez tabela).
- **D**: `KNOWN_REPAIRABLE_DRIFT` baca `SchemaRepairRequiredError` PRIJE
  `create_sqlite_engine()`/`create_all()` poziva — nemoguće doći do
  missing-column upita.
- **E**: `UNKNOWN_DRIFT` baca `SchemaUnknownDriftError`, isti obrazac, nema DDL.
- **F**: `repair_database()` (jedino mjesto koje radi DDL mutaciju) poziva se
  isključivo iz CLI `main()` u `schema_repair.py` (`python -m ...
  schema_repair repair-db`), nikad iz `app.py` startup toka.

**ARCHITECTURE CONTRACT = ACCEPT.**

## 3. Schema detector review — **BLOCKER**

Pročitan `inspect_local_schema()` u cjelini. Detektor STVARNO provjerava fizičku
šemu (`PRAGMA table_info`, `PRAGMA index_list`), ne samo `alembic_version` —
`_unknown_schema_reasons()` poredi tipove/nullability postojećih kolona i shape
postojećih indeksa protiv target definicija, i odbija ako se ne poklapaju.

**Ali** klasifikacijski uslov (linija 256):
```python
if version in KNOWN_STALE_REVISIONS or version != ALEMBIC_HEAD:
    return SchemaState.KNOWN_REPAIRABLE_DRIFT  # (uz dodatne details)
```
`KNOWN_STALE_REVISIONS = {"03de14cbf6aa", None}` — ali `or version != ALEMBIC_HEAD`
čini prvi dio uslova suvišnim: SVAKA verzija koja nije tačno `b7c2e1d4a903`, uz
koju `_unknown_schema_reasons()` ne nađe konflikt, biva klasifikovana kao
`KNOWN_REPAIRABLE_DRIFT` — ne samo dokazano poznati FLOW-1101A hibridni slučaj.

**Dokazano probe-om**: kreirana test baza sa fizičkom šemom koja je VEĆ IDENTIČNA
target šemi (sve kolone, indeksi, CHECK constraint), ali sa izmišljenom
`alembic_version = 'z9future000x'` (ne postoji u `KNOWN_STALE_REVISIONS`, nije
`ALEMBIC_HEAD`):
```
inspect_local_schema() klasifikacija: KNOWN_REPAIRABLE_DRIFT
```
Pokrenut `repair_database()` na toj bazi:
```
repair_database() rezultat: changed=True, final_alembic_version=b7c2e1d4a903
```
**Baza koja je bila na `'z9future000x'` je nasilno stampovana na `b7c2e1d4a903`,
BEZ ikakvog upozorenja da je verzija bila nepoznata.** Ovo je tačno scenario koji
review zahtjev eksplicitno naznačava kao BLOCKER: "Ako detector može neku
nepoznatu ili inkompatibilnu bazu pogrešno klasifikovati kao
KNOWN_REPAIRABLE_DRIFT".

**Zašto je važno**: `_unknown_schema_reasons()` poredi samo kolone/indekse koji
postoje u `expected` dict-u — ne detektuje EKSTRA kolone/tabele koje bi ukazivale
na NOVIJU (buduću) šemu. Ako lokalna baza ikad bude na stvarno NOVIJOJ Alembic
reviziji od hardkodiranog `ALEMBIC_HEAD` u ovom modulu (npr. nakon buduće
migracije koja doda kolonu, a ovaj "uski compatibility bridge" modul ne bude
ažuriran), repair će je tiho vratiti na stariji `alembic_version` stamp — što je
netačno stanje metapodataka (fizička šema ostaje netaknuta, ali bookkeeping laže).
Ovo NIJE hipotetički rizik za DANAŠNJU stvarnu lokalnu bazu (koja je potvrđeno
`03de14cbf6aa`, dakle ispod head-a, ne iznad), ali je dokazano stvaran dizajn
propust u samom detektoru.

**Minimalna ispravka**: ukloniti `or version != ALEMBIC_HEAD` iz uslova na liniji
256 — zadržati samo `if version in KNOWN_STALE_REVISIONS:`. Sve ostalo (bilo koja
druga, neprepoznata verzija) treba padati u postojeći fallback `UNKNOWN_DRIFT`
return na kraju funkcije (linija 280-285), koji već postoji i radi ispravno.

**SCHEMA DETECTOR = FIXES REQUIRED.**

## 4. Target schema contract

Upoređen `AGENT_REPORT_COLUMNS`/`WORKFLOW_LEDGER_COLUMNS`/indeksi/CHECK u
`schema_repair.py` protiv:

- **ORM modela** (`report_models.py:36-117`, `workflow_ledger_models.py:26-71`) —
  svih 31 `agent_reports` kolona, CHECK constraint tekst
  (`ck_agent_reports_work_status`), sva 4 indeksa (`ix_agent_reports_session_id`,
  `ix_agent_reports_status`, `ix_agent_reports_source_report_id` unique,
  `ix_agent_reports_source_path` unique); svih 12 `workflow_ledger_events` kolona,
  unique constraint (`uq_workflow_ledger_events_idempotency_key`), svih 6
  indeksa — **potpuno se poklapaju**.
- **Stvarnih Alembic migracija** (`alembic/versions/a17e4c8f9b21_agent_report_v2_
  bindings.py`, `4f2c9a7b8d11_agent_report_source_identity.py`,
  `b7c2e1d4a903_workflow_ledger_events.py`, pročitane u cjelini) — imena
  constraint-a, tipovi kolona, FK ondelete ponašanja, imena indeksa — **potpuno
  se poklapaju**, ne samo "približno".

Napomena: `AGENT_REPORT_SOURCE_INDEXES` (detector dict) prati samo dva UNIQUE
source indeksa; dva plain indeksa (`ix_agent_reports_session_id`,
`ix_agent_reports_status`) se KREIRAJU u `_rebuild_agent_reports()` (linije
617-618) ali detektor ih ne provjerava kao dio `_target_schema_errors()`. Manji
propust — ako bi baš ta dva plain indeksa nekako nedostajala na inače
kompatibilnoj bazi, detektor to ne bi uhvatio (upiti i dalje rade, samo sporije).
Vidi Nalaz L1.

**TARGET SCHEMA CONTRACT = ACCEPT** (uz L1 napomenu).

## 5. agent_reports table rebuild — HIGH RISK review

Pročitan `_rebuild_agent_reports()` i `_agent_reports_create_sql()` u cjelini.

1. **Postojeći redovi se prenose bez gubitka**: `INSERT INTO temp (...) SELECT
   ... FROM agent_reports` — kolone koje postoje u starom se kopiraju, kolone
   koje ne postoje dobijaju eksplicitni `NULL` (ne fabrikovana vrijednost).
2. **PK `id` ostaje isti**: kopira se direktno, `DROP + RENAME` čuva iste
   vrijednosti.
3. **`session_id` i FK vrijednosti ostaju iste**: potvrđeno probe-om — link koji
   je prije repair-a referencirao `report-1` i dalje referencira `report-1`
   nakon repair-a (vidi Section 6).
4. **Svi legacy/current podaci se kopiraju**: potvrđeno testom
   `test_known_hybrid_db_repair_adds_schema_stamps_and_preserves_data` (before ==
   after snapshot na project/session/plan_item/task/report/binding/link).
5. **Nove nullable kolone ostaju NULL**: `select_parts = [name if name in
   old_columns else "NULL" ...]` — nema fabrikacije `report_type`/`work_status`/
   source identity vrijednosti za stare redove.
6. **Postojeći indeksi se rekreiraju**: `ix_agent_reports_session_id`,
   `ix_agent_reports_status` eksplicitno rekreirani (linije 617-618).
7. **Novi source identity indeksi se dodaju**: `_ensure_agent_report_indexes()`.
8. **`work_status` CHECK constraint odgovara Alembic head-u**: identičan tekst
   kao migracija `a17e4c8f9b21` (potvrđeno u Section 4).
9. **Nema fabrikovanja vrijednosti**: potvrđeno u tački 5.
10. **Tabela nije ostavljena u polu-rebuilt stanju ako korak padne**: vidi
    Section 8 — dokazano probe-om da SQLite transakciona DDL + `except Exception:
    conn.rollback()` genuinski vraćaju originalnu `agent_reports` tabelu netaknutu.

**AGENT_REPORT REBUILD = ACCEPT.**

## 6. Foreign keys / references during rebuild

Probe (`repair_database()` na `_create_known_hybrid_db()` fixtureu, koja sadrži
`agent_report_binding_links` red koji referencira `agent_reports.id='report-1'`):

```
PRAGMA foreign_key_check nakon repair-a: []  (PRAZAN)
link-1.report_id='report-1' -> agent_reports redak postoji? True
```

`DROP TABLE agent_reports; ALTER TABLE temp RENAME TO agent_reports` čuva iste PK
vrijednosti, pa FK reference (`agent_report_binding_links.report_id`) ostaju
validne bez ikakve izmjene. `PRAGMA foreign_keys=OFF` tokom DDL-a (linija 315) je
ispravno — SQLite ne dozvoljava DROP TABLE na tabeli koju referenciraju aktivni
FK-ovi ako su FK provjere uključene tokom same DDL sekvence; `PRAGMA
foreign_keys=ON` se vraća u `finally` bloku (linija 349) prije zatvaranja
konekcije.

**Napomena (test coverage gap, ne funkcionalni bug)**: postojeći test suite NE
sadrži eksplicitan `PRAGMA foreign_key_check` assert. Ovo sam nezavisno
potvrdio probe-om — stvarno ponašanje je ispravno, ali isporučeni testovi to ne
dokazuju sami. Vidi Nalaz M2.

**FOREIGN KEY INTEGRITY = ACCEPT** (funkcionalno dokazano probe-om; test
pokrivenost nedostaje — M2).

## 7. Backup review

Pročitan `create_schema_backup()`. Potvrđeno:

- Koristi pravi SQLite Online Backup API (`src.backup(dst)`, `sqlite3.
  Connection.backup()`) — dizajniran da proizvede konzistentan snapshot čak i
  kad je izvor u WAL režimu (backup API interno prolazi kroz SQLite-ov vlastiti
  mehanizam konzistentnosti, ne raw file copy).
- Izvor se otvara READ-ONLY (`?mode=ro`) — repair proces ne može slučajno pisati
  u pravu bazu tokom backup koraka.
- `repair_database()` NE nastavlja ako backup ne uspije: `backup =
  create_schema_backup(path)` je PRVI korak nakon inspection provjere, prije
  ijedne DDL operacije. Potvrđeno testom `test_backup_failure_prevents_ddl_and_
  stamp` (monkeypatch baca `SchemaBackupError`, `agent_reports` kolone i
  `alembic_version` ostaju netaknuti).
- Backup putanja je collision-safe: `backups/schema-repair-{timestamp}-{uuid4()}`
  — timestamp + UUID, `mkdir(..., exist_ok=False)` — praktično nemoguća kolizija.
- Stvarna baza se ne overwrituje — backup cilj je uvijek nova putanja pod
  `backups/`.
- WAL/SHM: `-wal`/`-shm` fajlovi se kopiraju AKO postoje, kao dodatni forenzički
  artefakti — ali backup API snapshot (`database_backup`) je sam po sebi
  kompletna, samodovoljna, restorable baza (ne zavisi od tih kopija za
  konzistentnost). `metadata.json` jasno dokumentuje metod
  (`sqlite_backup_api_plus_wal_shm_artifacts_when_present`) — nije obmanjujuće.

**Dokazano probe-om (restorability)**: backup fajl otvoren direktno kao SQLite
baza — sadrži TAČNO pre-repair šemu (27 kolona, bez `report_type`) i pre-repair
podatke (`report-1`, `'preserve-report'`). Simuliran restore (copy backup preko
nove putanje) — otvoriv, ispravan, sa istim podatkom.

**Najvažniji odgovor**: DA, backup se realno može koristiti za vraćanje baze ako
repair kasnije ne uspije.

**BACKUP = ACCEPT.**

## 8. Failure atomicity

Probe: monkeypatchovan `_rebuild_agent_reports()` da napravi temp tabelu i
kopira podatke (identično originalnoj logici), pa baci `RuntimeError` PRIJE
`DROP TABLE`/`RENAME` koraka — simulira crash nasred rebuild-a (Section 8/A).

```
PRIJE repair-a: agent_reports kolone = 27 (bez report_type)
>>> Temp tabela kreirana i podaci kopirani. Sada baca RuntimeError...
repair_database je bacio: simulirani crash nasred rebuild-a

=== STANJE BAZE NAKON CRASH-a ===
'agent_reports' postoji? True
'agent_reports__flowos_repair' (temp) ostavljen? False
agent_reports kolone NAKON crash-a: 27 (report_type prisutan? False)
alembic_version nakon crash-a: 03de14cbf6aa (nepromijenjeno)
Podaci identicni prije/poslije crash-a? True
```

**Dokazano: repair NE MOŽE ostaviti djelimično promijenjenu DB za greške koje se
dese IZMEĐU `BEGIN` i `COMMIT`.** Cijela sekvenca (`_rebuild_agent_reports`,
`_create_workflow_ledger_events`, `_stamp_head`) je unutar jedne eksplicitne
SQLite transakcije (linija 316 `BEGIN` ... linija 344 `commit()`), a SQLite
podržava punu transakcionu DDL — `except Exception: conn.rollback()` (linija
345-347) genuinski poništava CIJELU sekvencu, ne samo posljednji statement. Ovo
NIJE "backup + explicit failure čini ovo prihvatljivim" nego jača garancija —
originalna tabela se nikad ni ne dira sve dok cijela sekvenca ne uspije.

**Ali** (B/C/D iz zahtjeva — greške NAKON `commit()`): vidi Section 9 — post-commit
verifikacija (`_preserved_snapshot` re-provjera, `inspect_local_schema` re-
provjera, `_verify_orm_access`) NE MOŽE poništiti već committovanu promjenu ako
sama padne. To je odvojen, stvaran nalaz (BLOCKER, Section 9), ne kontradikcija sa
ovim dijelom.

**FAILURE SAFETY = FIXES REQUIRED** (zbog Section 9 nalaza — pre-commit dio je
odličan, post-commit dio ima gap).

## 9. Stamp safety — **BLOCKER**

Pročitan tačan redoslijed u `repair_database()`:

```python
try:
    ...
    target_errors = _target_schema_errors(conn, _table_names(conn))
    if target_errors:
        raise SchemaUnknownDriftError(...)   # ✓ PRIJE stamp-a, u transakciji
    _stamp_head(conn)                         # <- STAMP
    conn.commit()                             # <- COMMIT (nepovratno na disku)
except Exception:
    conn.rollback()
    raise
finally:
    conn.close()

after = _preserved_snapshot(path)             # NAKON commit+close
if before != after:
    raise SchemaUnknownDriftError(...)        # PREKASNO da poništi

final = inspect_local_schema(path)
if final.state != SchemaState.HEALTHY:
    raise SchemaUnknownDriftError(final)      # PREKASNO da poništi
_verify_orm_access(path)                      # PREKASNO da poništi ako padne
```

`_stamp_head()` + `conn.commit()` se dešavaju PRIJE `_verify_orm_access()`,
PRIJE finalne `inspect_local_schema()` re-provjere, i PRIJE `_preserved_snapshot`
before/after poređenja. Ovo je direktno suprotno eksplicitnom zahtjevu: "Potvrdi
da se stamp NE može desiti prije: ... successful ORM AgentReport query;
successful ORM WorkflowLedgerEvent query."

**Zašto je arhitektonski teško izbjeći trivijalno**: `_verify_orm_access()`
otvara NOVI, ODVOJEN SQLAlchemy engine/konekciju (`create_engine(f"sqlite:///
{db_path...}")`) na isti fajl. Odvojena SQLite konekcija ne vidi neuobičajenu
(uncommitted) transakciju druge konekcije — da bi ORM verifikacija stvarno
radila PRIJE commit-a, morala bi dijeliti ISTU sirovu `conn` konekciju (npr. via
`create_engine("sqlite://", creator=lambda: conn)`), što trenutna implementacija
ne radi.

**Zašto je rizik danas nizak, ali dizajn defekt stvaran**: `_target_schema_errors`
(raw SQL provjera kolona/indeksa/constraint-a) VEĆ se izvršava PRIJE stamp-a, i
danas je dokazano usklađena sa stvarnim ORM modelima i migracijama (Section 4).
Zato realni put do "stamp sa nepotpunom šemom" danas zahtijeva da se
`schema_repair.py`-jev hardkodirani target (koji se održava NEZAVISNO od pravog
ORM modela) razmimoiđe sa stvarnim ORM modelom na način koji raw SQL provjera ne
hvata, a ORM query bi. To je isti mehanizam kao BLOCKER iz Section 3 — modul je
"uski compatibility bridge" čija tačnost zavisi od budućeg održavanja u koraku
sa stvarnom šemom, bez ugrađene zaštite ako to održavanje izostane.

**Backup postoji** (Section 7) kao recovery put ako se ovo ikad desi — to
ublažava posljedicu, ali ne mijenja da je STAMP već pogrešno izvršen i da bi
service startup nakon toga vjerovao da je baza `HEALTHY` (jer `alembic_version`
sada pokazuje `ALEMBIC_HEAD`) čak i ako ORM sloj ne može upitati tabelu.

**Minimalna ispravka**: premjestiti `_preserved_snapshot` re-provjeru i
`_verify_orm_access` da rade UNUTAR iste transakcije/konekcije prije
`_stamp_head()`+`commit()` (dijeljenjem `conn` objekta sa SQLAlchemy engine-om
preko `creator=`), ili — jednostavnije — premjestiti fizičku `_target_schema_
errors()` provjeru da bude POSLJEDNJI korak prije commit-a (već jeste) I dodati
minimalnu raw-SQL ekvivalentnu ORM provjeru (npr. `SELECT * FROM agent_reports
LIMIT 1` sa svim expected kolonama eksplicitno u SELECT listi) unutar iste
transakcije, umjesto oslanjanja na odvojenu post-commit SQLAlchemy provjeru za
"zadnju liniju odbrane".

**STAMP SAFETY = FIXES REQUIRED.**

Potvrđeno kao zaseban, tačan zahtjev: repair NE pokreće `alembic upgrade head`
nad hibridnom bazom nigdje (grep kroz `schema_repair.py` — nema poziva na
`alembic`/`command.upgrade`; `_stamp_head()` direktno piše u `alembic_version`
tabelu raw SQL-om, zaobilazeći Alembic runtime u potpunosti, što je namjerno i
ispravno za ovaj uski bridge slučaj).

## 10. Idempotency review

Pročitan i pokrenut `test_repair_is_idempotent_on_already_repaired_db`:

```
result.changed == False
result.backup_path is None
result.final_state == HEALTHY
before == after (snapshot)
indeksi: tačno 1 kopija svakog (nema duplikata)
```

Drugi poziv `repair_database()` na već-HEALTHY bazi udara u najraniju granu
(`if inspection.state == SchemaState.HEALTHY: return ... changed=False ...`,
linija 296-304) — **ne pravi novi backup, ne radi nikakav DDL, ne mutira
podatke**. Ovo je jača garancija od "backup pa no-op" — nema nepotrebnog rada
uopšte. Provjereno svježim pokretanjem, PASS.

**IDEMPOTENCY = ACCEPT.**

## 11. Unknown drift refusal

Postojeći test (`test_unknown_drift_refuses_without_schema_mutation_or_stamp`)
koristi `source_path INTEGER` — tip konflikt na POSTOJEĆOJ koloni, tačno
scenario koji je zahtjev eksplicitno označio kao "lako napraviti bez izmjene
produkcijskog koda" i tražio DODATNI scenario.

**Dva nezavisna dodatna probe scenarija, pokrenuta protiv NEIZMIJENJENOG koda:**

1. `workflow_ledger_events` POSTOJI, sve kolone ispravnog tipa, ali BEZ unique
   indeksa na `idempotency_key`:
   ```
   klasifikacija: UNKNOWN_DRIFT  ✓ ispravno
   ```
2. `workflow_ledger_events` POSTOJI, ali `project_id` je `INTEGER` umjesto
   `VARCHAR(36)`:
   ```
   klasifikacija: UNKNOWN_DRIFT  ✓ ispravno
   ```

Oba scenarija su ispravno odbijena — detektor NE nagađa, NE pokušava DDL.

**Napomena**: ovi probe scenariji NISU dio isporučenog test suite-a — postojeći
test pokriva samo jedan (najlakši) oblik unknown drift-a. Funkcionalno
ponašanje je ispravno (dokazano gore), ali test pokrivenost je uža nego što bi
trebala biti za ovako rizičnu komponentu. Vidi Nalaz M2.

**UNKNOWN DRIFT REFUSAL = ACCEPT** (funkcionalno; test pokrivenost dio M2).

## 12. Fresh DB behavior

- Prazna/nepostojeća baza → `HEALTHY` (linija 213-219), bootstrap smije nastaviti.
- Baza sa 0 tabela → `HEALTHY` (linija 223-229).
- Potpuno alembic-migrirana baza (`alembic upgrade head` stvarno pokrenut u
  testu `test_fresh_alembic_head_db_is_detected_as_healthy`, subprocess, ne
  mock) → `HEALTHY`, `alembic_version == ALEMBIC_HEAD`. PASS, potvrđeno svježim
  pokretanjem.
- **Analitički identifikovan dodatni slučaj** (nije test, izvedeno čitanjem
  koda): legacy `create_all()`-bootstrapovana baza BEZ ikad pokrenutog Alembic-a
  (npr. postojeći dev checkout prije ovog FLOW-1101A patch-a, gdje je
  `alembic_version` tabela nikad nije ni postojala) — `version=None`, što JESTE
  u `KNOWN_STALE_REVISIONS`, pa se klasifikuje `KNOWN_REPAIRABLE_DRIFT` (fizička
  šema je već ispravna, treba samo stamp). Ovo znači: **svaki postojeći dev
  checkout koji je ikad pokrenuo servis PRIJE ovog patcha, a nikad nije ručno
  pokrenuo Alembic, će sada biti blokiran na sljedećem startup-u i morat će
  pokrenuti eksplicitni `repair-db`** (koji će u tom slučaju biti bezopasan —
  samo dodaje stamp, ne rebuilduje ništa, jer `_agent_reports_needs_rebuild()`
  vraća False). Ovo je namjerna, ne slučajna posljedica arhitektonske odluke
  (svaki DB koji nije dokazano HEALTHY mora proći eksplicitni repair) — ali
  vrijedi eksplicitno zabilježiti kao operativni uticaj, ne kao bug.

**FRESH DB BEHAVIOR: nema HIGH/BLOCKER nalaza.** Fresh install i potpuno
migrirana baza rade ispravno; legacy create_all-only baza je namjerno (ne
greškom) blokirana dok se ne pokrene eksplicitni repair.

## 13. Startup failure mode

`test_startup_detection_blocks_known_drift_before_legacy_bootstrap` poziva
STVARNU `_run_migrations(db_path)` funkciju iz `app.py` (ne simulaciju) protiv
poznate hibridne baze:

```python
with pytest.raises(SchemaRepairRequiredError):
    _run_migrations(db_path)
assert "report_type" not in _columns(db_path, "agent_reports")
assert "workflow_ledger_events" not in _table_names(db_path)
```

PASS — potvrđeno da drift biva detektovan PRIJE nego što legacy `create_all()`
uopšte pokuša da doda bilo šta, dakle nema prilike za "no such column:
agent_reports.report_type" ni "no such table: workflow_ledger_events" greške.

Poruka korisniku (`app.py main()`, potvrđeno čitanjem): ispisuje
`inspection.message()` (stanje + detalje) i TAČNU komandu:
```
Pokreni: python -m flowos.service.services.infrastructure.persistence.schema_repair repair-db
```
Ovo je izvršiva, tačna komanda (potvrđeno čitanjem `schema_repair.py main()` CLI
parsera — `repair-db` je validan subcommand, `--db-path` je opciono, default
je stvarna produkcijska putanja).

Za HEALTHY privremenu bazu (dokazano kroz `test_fresh_alembic_head_db_is_
detected_as_healthy`) startup nastavlja normalno.

**STARTUP DETECTION = ACCEPT.**

## 14. Real local DB — read-only

```
sqlite3.connect('file:...flowos.db?mode=ro', uri=True)
alembic_version: 03de14cbf6aa
agent_reports row count: 0
```

Otvoreno isključivo u read-only URI režimu. `repair-db` NIJE pokrenut nad
stvarnom bazom. Stanje je identično onome zabilježenom u prethodnom FLOW-1101
reviewu — **repair još nije izvršen nad stvarnom lokalnom bazom.**

**REAL LOCAL DB MODIFIED: NO.**

## 15. Fresh tests

```
python -m pytest tests/unit/test_schema_repair.py -v --tb=short
6 passed in 4.97s
```
```
python -m pytest tests/integration/test_agent_report_ingestion.py \
  tests/integration/test_workflow_ledger_phase3a.py \
  tests/integration/test_workflow_ledger_phase3c.py \
  tests/integration/test_workflow_ledger_phase3d.py -v --tb=short
93 passed  (26 + 17 + 22 + 28)
```
```
python -m pytest tests/integration/test_composition_root.py -v --tb=short
9 passed, 1 warning
```
```
python scripts/verify_roundtrip.py
[PASS] Round-trip na privremenoj bazi
```
```
python scripts/verify.py
Prošlo: 7/7
[PASS] VERIFIKACIJA PROŠLA
```

Sve zeleno, 0 failed, u svim relevantnim suite-ovima.

## 16. Review findings

**BLOCKER**

- **B1 — Schema detector prihvata bilo koju nepoznatu verziju kao repairable**
  (`schema_repair.py:256`). Uslov `if version in KNOWN_STALE_REVISIONS or
  version != ALEMBIC_HEAD:` čini `KNOWN_STALE_REVISIONS` allowlist besmislenim —
  efektivno bilo koja verzija različita od head-a prolazi u
  `KNOWN_REPAIRABLE_DRIFT` granu ako fizička šema slučajno prođe conflict
  provjeru. Dokazano probe-om: baza sa izmišljenom `alembic_version =
  'z9future000x'` i VEĆ ispravnom fizičkom šemom biva klasifikovana kao
  repairable i njen stamp se PREPISUJE na `b7c2e1d4a903`, brišući stvarnu
  (u ovom slučaju izmišljenu, ali principijelno moguću buduću) verziju. Zašto je
  važno: ovo je "uski compatibility bridge" za TAČNO JEDAN poznati slučaj — kôd
  ne smije tretovati "nepoznato" kao "vjerovatno poznato". Minimalna ispravka:
  `if version in KNOWN_STALE_REVISIONS:` (ukloniti `or version != ALEMBIC_HEAD`).

- **B2 — Stamp + commit se dešavaju prije post-commit ORM/preserved-data
  verifikacije** (`schema_repair.py:343-366`). `_stamp_head()` i `conn.commit()`
  su izvršeni i trajno zapisani na disk PRIJE `_preserved_snapshot` before/after
  poređenja, PRIJE finalne `inspect_local_schema()` provjere, i PRIJE
  `_verify_orm_access()`. Ako bilo koja od te tri post-commit provjere otkrije
  problem, DB je već stampovana kao `HEALTHY`/`ALEMBIC_HEAD` iako to možda nije
  tačno — provjera može samo baciti grešku, ne poništiti već izvršen commit.
  Zašto je važno: direktno krši eksplicitni zahtjev da stamp ne smije biti
  izvršen prije uspješne ORM provjere; backup postoji kao recovery put, ali
  sistem bi u međuvremenu vjerovao da je baza zdrava. Minimalna ispravka:
  izvršiti ORM/preserved-snapshot provjeru unutar iste otvorene transakcije
  (dijeljenjem `conn` objekta) prije `_stamp_head()`+`commit()`, umjesto u
  odvojenoj post-commit konekciji.

**MEDIUM**

- **M1 — Nepotpun bootstrap (rijedak edge case) nema repair put.** Ako
  `REQUIRED_HYBRID_TABLES` nisu sve prisutne (npr. crash usred prvog ikad
  `create_all()` bootstrap-a), detektor vraća `UNKNOWN_DRIFT` (linija 483-486), a
  `repair_database()` na `UNKNOWN_DRIFT` samo baca grešku bez ikakvog repair
  puta (linija 305-306). Rezultat: baza bi ostala trajno blokirana bez
  automatizovanog oporavka (samo ručno brisanje/recreate). Uzak scenario, ali
  vrijedan zabilježiti. Minimalna ispravka: van scope-a ovog reviewa da se
  predlaže rješenje; dovoljno je da bude poznato ograničenje.

- **M2 — Test pokrivenost uža od funkcionalnog ponašanja.** Tri svojstva koja
  sam nezavisno potvrdio TAČNIM probe-ovima (FK integritet nakon rebuild-a via
  `PRAGMA foreign_key_check`; genuinska atomarnost mid-rebuild crash-a; dva
  dodatna unknown-drift scenarija van "source_path INTEGER") NISU pokrivena
  isporučenim testovima u `test_schema_repair.py`. Ponašanje je ispravno danas,
  ali bez ovih testova regresija se ne bi automatski uhvatila. Minimalna
  ispravka: dodati `PRAGMA foreign_key_check` assert u postojeći repair test;
  dodati mid-rebuild failure-injection test; dodati bar jedan
  workflow_ledger_events-specifičan unknown-drift test.

**LOW**

- **L1 — Detector ne prati `ix_agent_reports_session_id`/`ix_agent_reports_
  status` u `_target_schema_errors()`**, iako ih `_rebuild_agent_reports()`
  kreira. Da ta dva plain indeksa nekako nedostaju na inače kompatibilnoj bazi,
  detektor to ne bi primijetio (upiti rade, samo sporije). Ne utiče na
  ispravnost podataka.

## 17. Finalni verdict

```
ARCHITECTURE CONTRACT:      ACCEPT
SCHEMA DETECTOR:             FIXES REQUIRED   (B1)
AGENT_REPORT REBUILD:        ACCEPT
DATA PRESERVATION:           ACCEPT
FOREIGN KEY INTEGRITY:       ACCEPT           (test coverage: M2)
BACKUP:                      ACCEPT
FAILURE SAFETY:               FIXES REQUIRED   (B2 — post-commit dio)
STAMP SAFETY:                 FIXES REQUIRED   (B2)
IDEMPOTENCY:                  ACCEPT
UNKNOWN DRIFT REFUSAL:        ACCEPT           (test coverage: M2)
STARTUP DETECTION:            ACCEPT

REAL LOCAL DB MODIFIED:       NO

scripts/verify.py:            7/7
```

**FLOW-1101A = FIXES REQUIRED**

Razlog: arhitektura, rebuild logika, backup, atomarnost DDL-a unutar transakcije,
idempotentnost i startup detekcija su svi dokazano ispravni — uključujući
probe-om potvrđenu genuinsku transakcionu zaštitu za mid-rebuild crash i
restorable backup. Ali dva BLOCKER nalaza (B1: detektor prihvata bilo koju
nepoznatu verziju kao "poznatu" ako fizička šema slučajno prođe; B2: stamp se
commituje prije post-commit sigurnosnih provjera) su oba DOKAZANA probe-om, ne
teoretska, i oba direktno odgovaraju scenarijima koje je sam review zahtjev
eksplicitno unaprijed označio kao BLOCKER-klasu. Oba su suzena na "uski
compatibility bridge" modul (ne diraju ORM/migracije/produkcijsku semantiku), i
oba imaju precizne, male ispravke. Kôd NIJE spreman za `repair-db` protiv
stvarne lokalne baze dok se B1 i B2 ne isprave — ne zato što bi DANAŠNJA stvarna
baza (potvrđeno `03de14cbf6aa`, ispod head-a) trenutno okinula bilo koji od ova
dva propusta, nego zato što je detektorova ispravnost sama po sebi dio onoga što
se traži da bude dokazano prije ijednog stvarnog pokretanja repair-db komande
nad produkcijskim podacima.

Real local database nije mijenjana ovim reviewom.
