---
flowos_report_version: 1
report_id: 5e8b4d4c-714d-4840-b361-8477aa8a464c
agent: claude
model: claude-sonnet-5
session_id: unknown
report_type: review
work_status: completed
tasks:
  - FLOW-1101A
commits: []
created_at: 2026-08-13T09:17:16+02:00
---

# FLOW-1101A — Focused re-review B1 + B2 popravki

## Scope

READ ONLY. Nije mijenjan kod, nisu mijenjani testovi, nije pokretan repair nad
stvarnom lokalnom bazom, nije pravljen commit. Fokusiran re-review isključivo
prethodnih BLOCKER nalaza B1 i B2 iz
`agent_reports/2026-08-13-FLOW-1101A-independent-review.md`. Arhitektura,
rebuild logika, backup i idempotentnost nisu ponovo otvarani osim gdje ih novi
diff direktno dira.

Baseline: `6c5461a`.

## 1. Scope

```
git diff --stat
 src/flowos/service/app.py | 45 ++++++++++++++++++++++++++++++++++++++++-----
```

Identično prethodnom reviewu — `app.py` diff nepromijenjen. Provjereni mtime-ovi:
`app.py` = 08:12:33 (prije prethodnog reviewa u 08:43:24) — **nije ponovo
dirano**. `schema_repair.py` (08:58:56) i `test_schema_repair.py` (08:58:07)
mijenjani NAKON prethodnog reviewa — očekivano, B1/B2 popravka. Fix report
(09:09:09) takođe nakon.

**Nema scope deviation. `app.py` nema novo, nepovezano ponašanje.**

## 2. B1 — Unknown Alembic version

Pročitan `inspect_local_schema()`. Ključna izmjena (linija 256):
```python
# PRIJE (BLOCKER):
if version in KNOWN_STALE_REVISIONS or version != ALEMBIC_HEAD:
# SADA:
if version in KNOWN_STALE_REVISIONS:
```
Opasni `or version != ALEMBIC_HEAD` je uklonjen. Sada SAMO verzije eksplicitno u
`KNOWN_STALE_REVISIONS = {"03de14cbf6aa", None}` mogu ući u
`KNOWN_REPAIRABLE_DRIFT` granu (podložno fizičkoj provjeri šeme). Sve ostalo
pada u fallback na kraju funkcije (linija 280-286), koji sada eksplicitno
uključuje jasnu poruku: `f"Alembic version nije poznata za FLOW-1101A repair:
{version!r}."` kada `target_errors` prazan.

**Svježe testirano, sva četiri tražena scenarija, direktno protiv koda:**

```
[A] version=03de14cbf6aa hybrid -> KNOWN_REPAIRABLE_DRIFT   ✓
[B] version=None hybrid -> KNOWN_REPAIRABLE_DRIFT            ✓
[C] version=head (b7c2e1d4a903) valid schema -> HEALTHY      ✓
[D] version=z9future000x valid/current-looking schema -> UNKNOWN_DRIFT   ✓
```

Za D, pozvan `repair_database()`:
```
[D] repair_database odbio sa: SchemaUnknownDriftError
[D] alembic_version NAKON pokusaja repair-a: 'z9future000x' (nepromijenjeno)
[D] backups/ direktorij kreiran? False
```

**Repair je odbijen, nema DDL-a, nema stamp rewrite-a, `z9future000x` ostaje
netaknuto.** Ovo je TAČNO isti scenario koji je prethodni review dokazao kao
BLOCKER (probe sa izmišljenom budućom verzijom čija fizička šema slučajno
zadovoljava target) — sada se ispravno odbija.

**B1 UNKNOWN VERSION ALLOWLIST = CLOSED.**

## 3. B1 regression test quality

Novi test `test_unknown_alembic_version_with_valid_target_schema_is_unknown_and_
refused` (koristi PRAVI `alembic upgrade head` za fizičku šemu, zatim ručno
postavlja `alembic_version = 'z9future000x'`) dokazuje više od samog enum
outputa:

```python
assert inspection.state == SchemaState.UNKNOWN_DRIFT
assert inspection.alembic_version == "z9future000x"
with pytest.raises(SchemaUnknownDriftError):
    repair_database(db_path)
assert _fetch_one(...)[0] == "z9future000x"       # verzija nepromijenjena
assert _columns(db_path, "agent_reports") == before_columns   # šema nepromijenjena
assert _snapshot(db_path) == before_snapshot                   # podaci nepromijenjeni
assert not backups_dir.exists()                                # NEMA backup-a uopšte
```

Posljednja asercija (`not backups_dir.exists()`) je posebno vrijedna — dokazuje
da se odbijanje dešava PRIJE `create_schema_backup()` poziva (rana provjera
`if inspection.state == SchemaState.UNKNOWN_DRIFT: raise ...` u
`repair_database()`, prije bilo kakvog DDL-pripremnog koraka), ne samo da je
DDL odbijen nakon što je backup već napravljen.

**Test dokazuje mutation safety, ne samo detector output.**

**B1 MUTATION SAFETY = ACCEPT.**

## 4. B2 — Stvarni repair redoslijed

Pročitan `repair_database()` red-po-red. Stvarni redoslijed:

```
backup = create_schema_backup(path)                    # prije BEGIN
conn.execute("BEGIN")
before = _preserved_snapshot_from_connection(conn)      # UNUTAR transakcije
  → agent_reports rebuild (ako treba)
  → workflow_ledger_events kreiranje (ako treba)
_verify_pre_stamp_repair(conn, path, before):
  → _target_schema_errors(conn, ...)                    # fizička šema
  → _preserved_snapshot_from_connection(conn) == before  # podaci
  → _verify_required_column_selects(conn)                # ORM-ekvivalent SELECT
_stamp_head(conn)
conn.commit()
except Exception: conn.rollback()
```

Ovo TAČNO odgovara traženom redoslijedu. `_stamp_head()` se poziva SAMO nakon
što su sve tri pre-stamp provjere prošle unutar iste, još otvorene transakcije.

**B2 PRE-STAMP ORDER = CLOSED.**

## 5. Pre-stamp data preservation

`_preserved_snapshot_from_connection(conn)` (nova funkcija) prima POSTOJEĆU
`conn` — nema otvaranja nove konekcije. Poziva se DVA PUTA sa ISTOM `conn`:
jednom odmah nakon `BEGIN` (linija 317, prije bilo kakvog DDL-a) i jednom unutar
`_verify_pre_stamp_repair` (linija 743, nakon DDL-a, prije stamp-a) — obje
unutar iste, još-neuvezane transakcije. Poređenje `before == after` se dešava
PRIJE `_stamp_head()` i PRIJE `conn.commit()`.

Provjerava reprezentativne podatke iz `PRESERVED_TABLES` (projects, agent_
sessions, plan_items, tasks, agent_reports, session_task_bindings, agent_report_
binding_links) — dovoljno da uhvati vrstu korupcije koju bi loš rebuild mogao
unijeti (npr. izgubljen/promijenjen `id`, `session_id`, FK vezu).

Post-commit `_preserved_snapshot(path)` re-provjera (linija 344) i dalje postoji
kao dodatni sloj, ali VIŠE NIJE JEDINA odbrana — pre-commit provjera je sada
primarna i genuinski blokira stamp/commit ako se podaci promijene.

**B2 DATA PRESERVATION BEFORE STAMP = ACCEPT.**

## 6. Pre-stamp ORM-shape verification

`_verify_required_column_selects(conn)` (nova funkcija):
```python
conn.execute("SELECT " + ", ".join(AGENT_REPORT_COLUMNS) + " FROM agent_reports ORDER BY id LIMIT 1").fetchall()
conn.execute("SELECT " + ", ".join(WORKFLOW_LEDGER_COLUMNS) + " FROM workflow_ledger_events ORDER BY id LIMIT 1").fetchall()
```
Izvršava se na ISTOJ `conn` (proslijeđenoj kao parametar), unutar iste
transakcije, prije `_stamp_head()`. Ovo rješava problem iz prethodnog reviewa
gdje je `_verify_orm_access()` otvarao ODVOJENU SQLAlchemy konekciju koja
strukturalno ne može vidjeti neuvezanu transakciju druge konekcije — sada je
provjera raw SQL SELECT unutar ISTE konekcije, pa greška (npr. `no such column`)
biva uhvaćena PRIJE stamp-a, ne poslije.

`AGENT_REPORT_COLUMNS` (32 kolone) i `WORKFLOW_LEDGER_COLUMNS` (12 kolona) su
iste dict definicije koje sam u prethodnom reviewu potvrdio kolona-po-kolona
protiv stvarnih ORM modela (`report_models.py:36-117`,
`workflow_ledger_models.py:26-71`) i protiv stvarnih Alembic migracija
(`a17e4c8f9b21_agent_report_v2_bindings.py`,
`4f2c9a7b8d11_agent_report_source_identity.py`,
`b7c2e1d4a903_workflow_ledger_events.py`) — nisu mijenjane u ovom diff-u, i dalje
se potpuno poklapaju. Explicit SELECT lista sadrži SVAKU kolonu iz oba dict-a —
nema izostavljene ORM kolone.

Ova funkcija ne instancira SQLAlchemy ORM objekte, ali eksplicitni SELECT sa
punom kolonskom listom daje ekvivalentnu zaštitu od nedostajuće kolone —
zadovoljava eksplicitno dozvoljenu alternativu iz zahtjeva.

**B2 REQUIRED-COLUMN SELECTS = ACCEPT.**

## 7. Stamp / commit safety

Potvrđeno (Section 4-6): `_stamp_head(conn)` se izvršava tek nakon što
`_verify_pre_stamp_repair()` (sve tri provjere) prođe bez izuzetka. Ako bilo
koja baci: `except Exception: conn.rollback()` (linija 337-338) hvata sve,
uključujući `SchemaUnknownDriftError` iz `_verify_pre_stamp_repair` i bilo koji
drugi `Exception`. Stamp/version ostaje stale/original — dokazano u Section 8.

**Potvrđeno.**

## 8. Failure-injection proof

Novi test `test_prestamp_failure_rolls_back_schema_data_and_version`
(`test_schema_repair.py:618-638`): monkeypatch `_verify_required_column_selects`
da odmah baci `RuntimeError`. Pošto je ovo POSLJEDNJI korak unutar
`_verify_pre_stamp_repair` (nakon `_target_schema_errors` i preserved-snapshot
provjere, koje obje MORAJU proći prije nego što se dođe do ovog poziva), a
`_verify_pre_stamp_repair` se poziva NAKON `_rebuild_agent_reports`/`_create_
workflow_ledger_events` DDL-a — greška se dešava GENUINSKI nakon stvarnog DDL-a,
prije stamp-a. Provjereno svježim pokretanjem — PASS.

**Dodatna nezavisna provjera** (moj probe, identičan monkeypatch obrazac, sa
dodatnom provjerom koju isporučeni test eksplicitno ne radi — da li ostaje temp
tabela):
```
Tabele nakon crash-a: [agent_report_binding_links, agent_reports, agent_sessions,
  alembic_version, plan_items, plan_phases, plans, projects, session_events,
  session_task_bindings, tasks]
'agent_reports__flowos_repair' temp tabela ostavljena? False
'agent_reports' postoji (original)? True
```

Isporučeni test već provjerava: `agent_reports` kolone == before (dakle STARA
hibridna šema, ne rebuild-ovana), `workflow_ledger_events` NE postoji, puni
snapshot nepromijenjen, `alembic_version` i dalje `03de14cbf6aa`. Moj probe
dodatno potvrđuje da `agent_reports__flowos_repair` temp tabela NIJE ostavljena
— cijela SQLite transakciona DDL sekvenca je genuinski poništena.

Test NIJE nedovoljan — greška se dešava nakon stvarnog DDL-a, ne prije njega.

**B2 ROLLBACK PROOF = ACCEPT.**

## 9. Foreign key check

`test_known_hybrid_db_repair_adds_schema_stamps_and_preserves_data` sada sadrži:
```python
assert _foreign_key_check(db_path) == []
```
gdje `_foreign_key_check()` poziva `PRAGMA foreign_key_check`. Test svježe
pokrenut — PASS. Prethodni review je ovo dokazao samo probe-om (nezavisno,
izvan test suite-a); sada je i formalno u regresionom test suite-u.

**FOREIGN KEY TEST = ACCEPT.**

## 10. Additional unknown-drift test

Novi test `test_workflow_ledger_without_idempotency_unique_is_unknown_drift`
(`test_schema_repair.py:559-596`): `workflow_ledger_events` tabela postoji, sve
kolone ispravnog tipa, ali BEZ unique constraint-a na `idempotency_key`.
```python
assert inspection.state == SchemaState.UNKNOWN_DRIFT
assert any("idempotency" in reason for reason in inspection.unknown_reasons)
with pytest.raises(SchemaUnknownDriftError):
    repair_database(db_path)
assert _table_names(db_path) == before_tables
assert _fetch_one(...)[0] == before_version
```
Ovo je TAČNO scenario koji je prethodni review zahtijevao kao dodatni,
ne-trivijalan unknown-drift test (izvan "source_path INTEGER"). Svježe
pokrenut — PASS.

**ADDITIONAL UNKNOWN DRIFT TEST = ACCEPT.**

## 11. Nisu ponovo otvarani deferred nalazi

M1 (partial first-bootstrap recovery) i L1 (plain performance index detection
coverage) iz prethodnog reviewa nisu dio B1/B2 diff-a — `REQUIRED_HYBRID_TABLES`
logika i `AGENT_REPORT_SOURCE_INDEXES` detector dict su nepromijenjeni. Nisu
pogoršani, ostaju deferred kao prije.

## 12. Real local DB safety

```
sqlite3.connect('file:...flowos.db?mode=ro', uri=True)
alembic_version: 03de14cbf6aa
workflow_ledger_events present: False
report_type present: False
work_status present: False
```

Otvoreno isključivo read-only. `repair-db` NIJE pokrenut nad stvarnom bazom.
Stanje identično prethodnom reviewu.

**REAL LOCAL DB MODIFIED: NO.**

## 13. Fresh tests

```
python -m pytest tests/unit/test_schema_repair.py -v --tb=short
10 passed in 8.63s
```
```
python -m pytest tests/integration/test_agent_report_ingestion.py \
  tests/integration/test_workflow_ledger_phase3a.py \
  tests/integration/test_workflow_ledger_phase3c.py \
  tests/integration/test_workflow_ledger_phase3d.py -v --tb=short
93 passed
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

Sve zeleno, 0 failed.

## 14. Finalni verdict

```
B1 UNKNOWN VERSION ALLOWLIST:          CLOSED
B1 MUTATION SAFETY:                     ACCEPT
B2 PRE-STAMP ORDER:                     CLOSED
B2 DATA PRESERVATION BEFORE STAMP:      ACCEPT
B2 REQUIRED-COLUMN SELECTS:             ACCEPT
B2 ROLLBACK PROOF:                      ACCEPT
FOREIGN KEY TEST:                       ACCEPT
ADDITIONAL UNKNOWN DRIFT TEST:          ACCEPT

REAL LOCAL DB MODIFIED:                 NO

scripts/verify.py:                      7/7
```

**FLOW-1101A = ACCEPT**

**FLOW-1101A CODE ACCEPTED — REAL LOCAL DATABASE REPAIR HAS NOT YET BEEN
EXECUTED**

Oba prethodna BLOCKER nalaza (B1: detektor prihvatao bilo koju nepoznatu verziju
kao repairable; B2: stamp/commit prije post-commit verifikacije) su ispravljena
sa preciznim, malim izmjenama tačno na mjestu koje je prethodni review
identifikovao, i oba su dokazana ne samo isporučenim regresionim testovima nego
i mojim nezavisnim, svježim probe-ovima koji direktno repliciraju scenarije iz
prethodnog BLOCKER nalaza protiv trenutnog koda. Nema novih nalaza. M1 i L1
ostaju namjerno odgođeni, nepogoršani ovim diff-om. Stvarna lokalna baza nije
mijenjana.
