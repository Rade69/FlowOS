---
flowos_report_version: 1
report_id: 32b0519b-883a-4279-b4e6-ef044d894843
agent: claude
model: claude-sonnet-5
session_id: unknown
report_type: review
work_status: completed
tasks:
  - unassigned
commits: []
created_at: 2026-08-12T14:17:04+02:00
---

# Workflow Ledger Phase 3C — kratki re-review popravki F1–F8

## Scope

READ ONLY re-review. Nije mijenjan kod, nije popravljan implementation report,
nije pravljen commit. Cilj: provjeriti F1–F8 popravke iz
`agent_reports/2026-08-12_workflow-ledger-phase-3c-independent-review.md` i dati
finalnu ocjenu spremnosti za commit.

Baseline: commit `010f841`. Provjereni izvori:
`src/flowos/service/services/workflow/ledger.py`,
`tests/integration/test_workflow_ledger_phase3c.py`,
`agent_reports/2026-08-12_workflow-ledger-phase-3c-review-completed-implementation.md`.

## F1 — cross_session_ok uklonjen

**Dokaz**: `_build_target_groups(self, report: AgentReport) -> list[_TargetGroup]` nema
`cross_session_ok` parametar. Provjera unutra: `if binding is None or binding.session_id
!= report.session_id: return []`. I `append_implementation_completed_from_report()` i
`append_review_completed_from_report()` pozivaju `self._build_target_groups(report)` bez
dodatnog argumenta — identična stroga logika.

`test_corrupted_cross_project_link_produces_zero_events` i
`test_normal_same_session_review_still_works` prolaze (vidi F6).

**F1 = CLOSED.**

## F2 — duplirani return uklonjen

**Dokaz**: `_test_result_idempotency_key()` ima tačno jedan `return
f"workflow-ledger:v1:TEST_RESULT:verification_artifact:{artifact_id}"`. Nema
nedostižnog koda. `mypy` dio `scripts/verify.py` prolazi (vidi F3/Sekcija 11).

**F2 = CLOSED.**

## F3 — Ruff format/lint

**Dokaz**: `python scripts/verify.py` → koraci 1 (Ruff format check) i 2 (Ruff lint)
oba `[PASS]`. Cijeli verify.py 7/7 (vidi Sekciju 11).

**F3 = CLOSED.**

## F4 — stvarni DB UNIQUE constraint test

**Dokaz**: `test_db_unique_constraint_prevents_duplicate` konstruiše duplikat
`WorkflowLedgerEvent` sa istim `idempotency_key`, upisuje ga unutar
`db_session.begin_nested()`, očekuje `IntegrityError` (`pytest.fail` ako se ne baci),
i na kraju potvrđuje da originalni event i dalje postoji (`len(...) == 1`). Ovo je
stvaran test DB constrainta, ne placeholder.

**F4 = CLOSED.**

## F5 — multiple historical snapshots test

**Provjera hipoteze prije zaključka**: pokrenut direktan probe koji replicira test
scenario (`test_multiple_resolved_plan_item_ids`) — kreira Task sa jednim bindingom,
zatim mijenja `Task.plan_item_id` NAKON binding-a (isti obrazac kao test), pa ingestuje
review report.

**Rezultat probe-a**:
```
Broj eventa: 1
event.plan_item_id = 'item-b'
payload['resolved_plan_item_ids'] = ['item-b']
Broj distinct snapshotova = 1
```

Test kreira samo JEDAN `SessionTaskBinding` (sesija je kreirana jednom sa
`task_id=task.id`, nikad nije pozvan `switch_binding` da napravi drugi historical
segment). Mijenjanje `Task.plan_item_id` mijenja samo live pokazivač, ne stvara drugi
`AgentReportBindingLink` snapshot. Rezultat je 1 (ne 2) distinct
`resolved_plan_item_id`, i `event.plan_item_id` NIJE null (jer je dokumentovano
pravilo "1 snapshot → event.plan_item_id", što je tehnički tačno, ali test ne
dokazuje traženi "više snapshotova → NULL" scenario).

Test asercije su preslabe da bi ovo uhvatile: `len(...) >= 1` (umjesto `== 2`) i
`e.plan_item_id is not None or payload["task_id"] == task.id` (OR klauzula je skoro
uvijek tačna nezavisno od stvarnog ponašanja).

Ovo je tačno scenario koji je korisnik unaprijed identifikovao: *"Ako samo mijenja
live Task.plan_item_id bez dva stvarna historical snapshota: F5 NIJE CLOSED."*

**F5 = OPEN.** Test prolazi, ali ne dokazuje multi-snapshot→NULL ponašanje jer
nikad ne postoje dva stvarna binding segmenta.

## F6 — cross-project/session corruption test

**Dokaz**: `test_corrupted_cross_project_link_produces_zero_events` kreira
`AgentReportBindingLink` DIREKTNOM ORM konstrukcijom
(`db_session.add(corrupt_link); db_session.flush()`), zaobilazeći
`ReportService.link_report_to_binding()` validaciju. Binding pripada `other_project`
(zaseban `Project` objekat), report pripada `project` — stvaran cross-project
scenario. `append_review_completed_from_report()` se poziva direktno na Ledger
servisu i vraća 0 eventa. `test_normal_same_session_review_still_works` potvrđuje da
normalan tok i dalje radi (1 event, tačan `task_id`).

Ovo tačno testira defense-in-depth Ledger writer-a, ne servisni sloj — u skladu sa
zahtjevom da se ne prihvata test koji se oslanja na to da servis već odbija
cross-session prije nego što Ledger writer bude testiran.

**F6 = CLOSED.**

## F7 — transaction rollback test

**Provjera hipoteze prije zaključka**: pokrenuta dva probe-a koji repliciraju
`test_ledger_failure_rolls_back_report_and_links` tačno (isti kod, isti filter).

**Rezultat probe-a** (`probe_f7_exact.py`, tačna replika test koda):
```
pytest.raises kontekst zadovoljen (RuntimeError je bacen)

Test-ov TACAN filter (source_path == str(report_path)): 0 redova
SVI AgentReport redovi (bez filtera): 1
  - id=0be5f794 source_path='c:\\users\\38765\\appdata\\local\\temp\\...\\report.md'

str(report_path) koji test koristi u filteru = 'C:\\Users\\...\\report.md'

WorkflowLedgerEvent broj: 0
```

**Dvije nezavisne mane u testu, obje potvrđene**:

1. **Filter na `AgentReport` nikad ne može pogoditi.** `source_path` se čuva
   normalizovano preko `normalize_source_path()` (`os.path.normcase(...)`), što na
   Windowsu pretvara putanju u mala slova i rezolviše je. Test filtrira po
   `str(report_path)` — originalnoj, ne-normalizovanoj putanji sa velikim slovima.
   String poređenje NIKAD ne može uspjeti, pa `len(reports) == 0` prolazi bez obzira
   da li je red stvarno rollback-ovan ili ne. Neposredna provjera bez filtera
   pokazuje da `AgentReport` red **stvarno postoji** (flush-ovan, ne commit-ovan)
   nakon exception-a.
2. **`WorkflowLedgerEvent` asercija je trivijalna.** `_failing_append` baca
   `RuntimeError` PRIJE nego što bilo šta upiše u bazu, pa nikad nije ni postojao red
   za brisanje — `len(_ledger_events(...)) == 0` je tačno nezavisno od rollback
   ponašanja.
3. Test **nikad ne poziva `db_session.rollback()`** eksplicitno, niti provjerava
   `AgentReportBindingLink`. Za poređenje, analogni test iz Phase 3A
   (`test_ledger_failure_rolls_back_report_links_and_events`,
   `test_workflow_ledger_phase3a.py:428-453`) EKSPLICITNO zove `db_session.rollback()`
   (linija 449) i onda provjerava sva tri modela nefiltriranim `.count()` upitima
   (`AgentReport`, `AgentReportBindingLink`, `WorkflowLedgerEvent`) — ispravan obrazac
   koji Phase 3C test ne prati.

**Zaključak o koda**: `AgentReportIngestionService.ingest_file()` hvata samo
`except IntegrityError`; generička exception (npr. `RuntimeError` iz Ledger writera)
NIJE uhvaćena unutra i NE izaziva rollback unutar `ingest_file()` samog. To znači
flush-ovano-ali-ne-commit-ovano stanje ostaje u sesiji dok pozivalac eksplicitno ne
pozove rollback.

U produkciji, oba stvarna pozivaoca (`composition_root.py` — watcher callback linija
~231-242 i startup scan linija ~294-308) obavijaju `ingest_file()` sa
`except Exception: db.rollback()`, što je isti obrazac ranije provjeren u Phase
2/3A. To čini vjerovatnim da je STVARNO produkcijsko ponašanje ispravno — ali ovaj
konkretan test to ne dokazuje jer poziva `ingest_file()` direktno, zaobilazeći
wrapper, i njegove asercije prolaze bez obzira na rollback zbog gore navedenih bug-ova.

**F7 = OPEN.** Test daje lažan osjećaj sigurnosti (PASS bez ikakvog dokaza) — ne
zadovoljava zahtjev "DB transaction/rollback ne smije biti mockovan" u smislu
stvarnog dokaza, jer suštinski ne testira rollback nikako. Postojeći caller-level
rollback net (watcher/startup scan) vjerovatno pokriva scenario, ali to nije isto
što i dokazan, dedicated integration test za Ledger writer specifično.

## F8 — implementation report integritet

Provjerene su tačno kontradikcije koje je korisnik unaprijed identifikovao — sve
potvrđene čitanjem trenutnog sadržaja
`2026-08-12_workflow-ledger-phase-3c-review-completed-implementation.md`:

**A) Target grouping (linije 63-67)** i dalje tvrdi: *"Koristi istu
`_build_target_groups()` logiku kao Phase 3A `IMPLEMENTATION_COMPLETED`, sa
`cross_session_ok=True`..."* — direktno kontradiktorno sa F1 sekcijom (linije
161-164) koja tvrdi da je parametar uklonjen. **Kod potvrđuje da je F1 sekcija
tačna, a "Target grouping" sekcija zastarjela/pogrešna.**

**B) "Known limitations" (linije 204-206)** i dalje tvrdi: *"`_build_target_groups`
za review sa `cross_session_ok=True` preskače session_id proveru..."* — ista
kontradikcija ponovljena drugi put u istom dokumentu.

**C) DB UNIQUE test kontradikcija.** F4 sekcija (linije 173-176) tvrdi da test
postoji i koristi `begin_nested()`. "Known limitations" (linije 207-209) tvrdi
suprotno: *"DB unique constraint test nije implementiran kao zaseban pytest test..."*
Kod (`test_db_unique_constraint_prevents_duplicate`) potvrđuje da F4 sekcija tačno
opisuje stanje, a "Known limitations" tvrdnja je zastarjela.

**D) Aritmetička greška u regresionoj tabeli.** Claimed: 35+15+16+22+22 = navedeno
kao **118**. Stvaran zbir navedenih brojki je **110**, ne 118. Bez obzira na to,
navedeni pojedinačni brojevi su i sami netačni (vidi E).

**E) Stvarni brojevi testova, dobijeni direktnim pokretanjem** (ne iz izvještaja):

| Test skup | Report tvrdi | Stvarno (ovaj re-review) |
|---|---|---|
| Phase 3A (IMPLEMENTATION_COMPLETED) | 35 passed | **17 passed** |
| Phase 3B (TEST_RESULT) | 15 passed | **19 passed** |
| AgentReport Ingestion | 16 passed | **26 passed** |
| AgentReport v2 | 22 passed | **12 passed** |
| Session Task Bindings | 22 passed | **22 passed** (jedini tačan) |
| Phase 3C (novi) | 22 passed | **22 passed** (tačan) |
| **Zbir regresija (bez 3C)** | 110 (aritmetički) / 118 (navedeno) | **96 passed** |
| **Ukupno sve (regresije + 3C)** | 118 | **118 passed** (slučajno se poklapa) |

Napomena: ukupan zbir (118) se slučajno poklapa sa pogrešno navedenim brojem u
izvještaju, ali isključivo zato što se greške u pojedinačnim brojkama međusobno
poništavaju (npr. 3A precijenjen za +18, ingestion podcijenjen za -10, v2 precijenjen
za +10). Pojedinačna tabela je netačna čak i kad je ukupan zbir slučajno tačan.

**F8 = OPEN.** Report i dalje sadrži najmanje 4 potvrđene kontradikcije/greške (A,
B, C, D/E) koje odražavaju stariju verziju stanja, ne trenutni kod.

## Sekcija 9 — Puni Phase 3C test suite

```
python -m pytest tests/integration/test_workflow_ledger_phase3c.py -v --tb=short
```
Rezultat: **22 passed** (collected 22, svi PASSED, 0 failed).

## Sekcija 10 — Regresioni suite

```
python -m pytest tests/integration/test_workflow_ledger_phase3a.py \
  tests/integration/test_workflow_ledger_phase3b.py \
  tests/integration/test_workflow_ledger_phase3c.py -q
→ 58 passed (17 + 19 + 22)

python -m pytest tests/integration/test_agent_report_ingestion.py \
  tests/integration/test_agent_report_v2.py \
  tests/integration/test_session_task_bindings.py -q
→ 60 passed (26 + 12 + 22)
```

Ukupno: **118 passed**, 0 failed, kad se svi relevantni fajlovi pokrenu zajedno.

(Napomena: `test_session_task_bindings.py` pokrenut IZOLOVANO sam za sebe puca sa
`KeyError: 'AgentReportBindingLink'` — SQLAlchemy declarative registry import-order
artefakt, ne stvarna regresija; kada se `report_models` modul učita zajedno sa
ostalim test fajlovima ili preko punog `scripts/verify.py` running-a, svi testovi
prolaze. Ovo je potvrđeno punim verify.py run-om ispod, gdje isti fajl prolazi bez
greške kao dio od 433 passed.)

## Sekcija 11 — python scripts/verify.py

```
[PASS] 1. Ruff format check
[PASS] 2. Ruff lint
[PASS] 3. mypy
[PASS] 4. Architecture boundaries
[PASS] 5. Unit tests   (433 passed, 1 warning, 85.79s)
[PASS] 6. Migrations check
[PASS] 7. Alembic round-trip

Prošlo: 7/7
[PASS] VERIFIKACIJA PROŠLA
```

**Sekcija 11 = 7/7 PASS**, potvrđeno.

## Sekcija 12 — Finalni rezultat

| Fix | Status |
|---|---|
| F1 — cross_session_ok uklonjen | **CLOSED** |
| F2 — duplirani return uklonjen | **CLOSED** |
| F3 — Ruff format/lint | **CLOSED** |
| F4 — stvaran DB UNIQUE test | **CLOSED** |
| F5 — multiple historical snapshots test | **OPEN** — test ne kreira dva stvarna binding segmenta, asercije preslabe |
| F6 — cross-project corruption test | **CLOSED** |
| F7 — transaction rollback test | **OPEN** — test lažno prolazi (path-casing mismatch + trivijalna asercija), ne dokazuje rollback nikako |
| F8 — implementation report integritet | **OPEN** — 4 potvrđene kontradikcije/greške i dalje prisutne u izvještaju |

**VERDICT: FIXES REQUIRED**

Razlog: F5 i F7 nisu samo problem izvještaja — to su stvarni nedostaci u DOSTAVLJENIM
TESTOVIMA koji ne dokazuju tvrđeno ponašanje (F5 nikad ne kreira dva snapshot-a; F7
lažno prolazi zbog dva nezavisna bug-a u testu, bez ijednog stvarnog dokaza rollback-a).
Kod za F1, F2, F3, F4, F6 je stvarno ispravan i dokazan. Produkcijsko ponašanje za F7
je vjerovatno ispravno (zbog postojećeg caller-level rollback wrapper-a u
`composition_root.py`, isti obrazac kao Phase 2/3A), ali to nije isto što i dokazan,
dedicated test za Ledger writer specifično — pa se F7 ne može proglasiti CLOSED samo
na osnovu "test je zelen".

Potrebno prije commit-a:
1. F5: dodati stvaran drugi `SessionTaskBinding` segment (npr. preko
   `SessionTaskBindingService.switch_binding()`) prije review ingestion-a, tako da
   postoje dva stvarna `AgentReportBindingLink` snapshot-a sa različitim
   `resolved_plan_item_id`, i pojačati asercije na `== 2` i `event.plan_item_id is None`.
2. F7: dodati eksplicitan `db_session.rollback()` poziv nakon `pytest.raises` bloka
   (kao u Phase 3A analognom testu), zamijeniti filtrirani upit sa nefiltriranim
   `.count()`/`.all()` na `AgentReport`, dodati provjeru `AgentReportBindingLink`, i
   po mogućnosti dodati scenario gdje Ledger writer baca EXCEPTION NAKON što je nešto
   već upisano (ne odmah na ulazu), da asercija na `WorkflowLedgerEvent` bude
   netrivijalna.
3. F8: uskladiti implementation report sa stvarnim stanjem koda — ukloniti
   kontradiktorne "Target grouping" i "Known limitations" pasuse (A, B, C), i
   ispraviti regresionu tabelu na stvarne brojeve (E).

Nakon toga: nezavisan checker treba ponovo provjeriti F5 i F7 testove prije commit-a.
