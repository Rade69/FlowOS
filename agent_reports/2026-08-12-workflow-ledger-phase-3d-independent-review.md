---
flowos_report_version: 1
report_id: d35d5760-a612-4e33-aee2-775726f0cf12
agent: claude
model: claude-sonnet-5
session_id: unknown
report_type: review
work_status: completed
tasks:
  - unassigned
commits: []
created_at: 2026-08-12T17:09:44+02:00
---

# Workflow Ledger Phase 3D — Authority Cutover, independent review

## Scope

READ ONLY. Nije mijenjan kod, nisu popravljani testovi, nije popravljan report,
nije pravljen commit. Provjerava se da li implementacija tačno prati zaključani
arhitektonski contract iz analize, ne ponavlja se arhitektonska analiza od nule.

Baseline: `3dae174` (feat: add workflow ledger review completed).

## 1. Scope i diff

```
git status --short
```
```
 M src/flowos/service/services/reports/service.py
 M tests/unit/test_reports.py
?? agent_reports/2026-08-12-workflow-ledger-phase-3d-authority-cutover-analysis.md
?? agent_reports/2026-08-12-workflow-ledger-phase-3d-authority-cutover-implementation.md
?? src/flowos/service/services/workflow/decisions.py
?? tests/integration/test_workflow_ledger_phase3d.py
```
```
git diff --stat
 src/flowos/service/services/reports/service.py | 53 ++++++--------------------
 tests/unit/test_reports.py                     |  1 +
 2 files changed, 13 insertions(+), 41 deletions(-)
```

Scope tačno odgovara "Expected changed files" iz analize (§V), minus
`test_agent_report_v2.py` koji NIJE dirnut (vidi Nalaz M2 niže — analiza je to
eksplicitno preporučila).

**Nema produkcijske izmjene van zaključanog scope-a.**

## 2. Authority cutover

`ReportService.set_verdict()` (`service.py:178-210`) sada isključivo poziva:
```python
return WorkflowDecisionService(self._session).record_report_decision(
    report_id=report_id, verdict=verdict, notes=notes, decision_id=decision_id,
)
```
Stari tok (upis `user_verdict/status/verdict_audit_json` direktno + poziv
`self._reopen_plan_item(report)`) je u potpunosti uklonjen iz `set_verdict()`.

Provjereno grep-om kroz `src/`: `_reopen_plan_item` se više NIGDJE ne poziva —
metoda ostaje definisana (`service.py:216`) ali je **mrtav kod** (vidi Nalaz M3).

**Authority cutover je stvaran, ne kozmetički.**

## 3. Canonical authority

`WorkflowLedgerEvent(event_type="TASK_DECISION")` je jedini put kroz koji nastaje
target-level PlanItem consequence (`_apply_plan_item_consequences`,
`decisions.py:252-282`) — poziva se isključivo iz `record_report_decision()`,
nakon što su TASK_DECISION eventi kreirani. Nema paralelnog puta: jedini poziv
`PlanProgressService.validate_transition(..., allow_verdict_reopen=True)` u cijelom
diff-u je unutar `_apply_plan_item_consequences`.

`AgentReport.user_verdict/user_notes/verdict_audit_json/status` se ažuriraju
isključivo kroz `_apply_compatibility_projection()` — eksplicitno označeno kao
"compatibility projection", nikad kao izvor PlanItem odluke.

**Potvrđeno: nema drugog paralelnog target-level authority toka.**

## 4. Verdict semantics

- **ACCEPTED**: `if verdict in ("NEEDS_WORK", "REJECTED"):` (`decisions.py:213`) —
  ACCEPTED nikad ne ulazi u `_apply_plan_item_consequences`. Test
  `test_accepted_does_not_change_plan_item` i `test_accepted_no_done_no_verified`
  potvrđuju status ostaje nepromijenjen. **Potvrđeno.**
- **NEEDS_WORK**: `test_needs_work_reopens_implemented`,
  `test_needs_work_reopens_verified` — oba PASS, item.status prelazi u IN_PROGRESS
  polazeći od IMPLEMENTED odn. VERIFIED (ne-trivijalna početna stanja). **Potvrđeno.**
- **REJECTED**: `test_rejected_reopens_implemented`, `test_rejected_reopens_verified`
  — identičan obrazac, PASS. Payload `decision` polje ostaje `"REJECTED"` (različito
  od `"NEEDS_WORK"`), dok je consequence kod identičan (`verdict in ("NEEDS_WORK",
  "REJECTED")`). **Potvrđeno — REJECTED ostaje distinktna decision vrijednost sa
  istim consequence-om, tačno kako analiza traži.**

## 5. decision_id contract — idempotentnost

`record_report_decision()` (`decisions.py:84-98`): ako `decision_id` već ima
postojeće evente, poredi `payload["decision"]`, `payload["notes"]`,
`payload["report_id"]` sa trenutnim pozivom. Ako se sve poklapa → **rani `return
report` BEZ ikakvog upisa** (nema novog eventa, nema `_apply_compatibility_projection`
poziva, nema `_apply_plan_item_consequences` poziva) — čime se garantuje da retry
ne mijenja `updated_at`, ne appenduje audit, ne ponovo primjenjuje consequence.

`test_same_decision_id_retry_no_duplicate` — PASS, potvrđuje `len(events) == 1`
nakon dva identična poziva.

Ovo je dokazano ČITANJEM KODA (linearna kontrola toka: provjera je najranija stvar
u funkciji, prije ijednog `session.add`/`flush`), ne samo event countom — kod
strukturalno ne može doći do drugog upisa nakon match-a.

**Blaga praznina u test pokrivenosti** (ne bug): test ne provjerava eksplicitno da
`report.updated_at` i `verdict_audit_json` dužina ostaju nepromijenjeni između r1 i
r2 (vidi Nalaz L1).

## 6. decision_id conflict

Tri tražena scenarija su sva pokrivena zasebnim testovima:
- isti D1 + drugi verdict → `test_same_decision_id_different_verdict_raises` PASS
- isti D1 + druge notes → `test_conflict_notes` PASS
- isti D1 + drugi report → `test_conflict_report` PASS

Provjera (`decisions.py:88-92`) poredi sva tri polja
(`decision`, `notes`, `report_id`), ne samo verdict — potvrđeno čitanjem koda.

`ValueError` se baca PRIJE ijednog `session.add`/`flush` za taj poziv → 0 DB
mutacija je garantovano kontrolom toka. Testovi ne provjeravaju ovo eksplicitno
nakon raise-a (vidi Nalaz L2), ali kod to strukturalno ne dozvoljava drugačije.

## 7. Source identity i idempotency

```python
source_kind=USER_DECISION_SOURCE,  # "user_decision"
source_id=decision_id,
```
Idempotency key: `workflow-ledger:v1:TASK_DECISION:user_decision:{decision_id}:
{target_kind}:{target_id}` (`decisions.py:296-301`) — tačno odgovara zaključanom
formatu iz analize (§K). `TestTaskDecisionChaining::test_needs_work_then_accepted_
keeps_both` potvrđuje da nova `decision_id` na istom report/targetu proizvodi novi
event (2 eventa nakon NEEDS_WORK pa ACCEPTED).

**Potvrđeno.**

## 8. Multi-target i A-B-A

`test_two_targets_produce_two_events` (2 taska, 2 eventa) i
`test_aba_produces_one_event_per_logical_target` (A-B-A na task nivou, 2 eventa —
1 za A, 1 za B, ne 3) — oba PASS. Koristi se postojeći
`WorkflowLedgerService._build_target_groups()` bez izmjene (poziva se direktno,
`decisions.py:106`), bez ikakvog `cross_session_ok` ili ekvivalentnog parametra —
potvrđeno da `_build_target_groups()` u `ledger.py` nije dirana u ovom diff-u.

**Potvrđeno — nema opasne generalizacije, nema bypass-a.**

## 9. Historical PlanItem authority — **NALAZ (HIGH)**

Kod (`_apply_plan_item_consequences`, `decisions.py:252-282`) čita isključivo
`group.resolved_plan_item_ids` (izvedeno iz `AgentReportBindingLink.resolved_plan_
item_id`) — nikad `Task.plan_item_id` direktno. Ovaj dio zahtjeva je **kodom
zadovoljen**.

Ali test koji treba to DOKAZATI, `test_historical_plan_item_drift`
(`test_workflow_ledger_phase3d.py:449-468`), ima strukturnu grešku suprotnu Phase
3A obrascu:

```python
task = _task(db_session, project, item_p1, "drift")   # task.plan_item_id = item_p1
ses = _session(db_session, project, task_id=task.id)
task.plan_item_id = item_p2.id                          # DRIFT PRIJE linka
db_session.flush()
report = _make_report(db_session, ses.id)
ReportService(db_session).link_report_to_binding(...)   # link NAKON drift-a
```

Za poređenje, Phase 3A-ov ISPRAVAN obrazac (`test_workflow_ledger_phase3a.py:358-385`,
`test_task_event_uses_binding_link_snapshot_not_live_task_plan_item`) radi
suprotnim redoslijedom: `link_report_to_binding()` PRIJE `task.plan_item_id =
item_b.id`.

**Provjera probe-om** (replika tačnog Phase 3D testa uz ispis stanja):
```
PRIJE drift-a: task.plan_item_id = 'item-p1'
NAKON drift-a: task.plan_item_id = 'item-p2'

link.resolved_plan_item_id = 'item-p2'
  == item_p1.id (OCEKIVANI historical snapshot)? False
  == item_p2.id (live/drifted vrednost)? True

TASK_DECISION event.plan_item_id = 'item-p2'
payload.resolved_plan_item_ids = ['item-p2']

item_p1.status = 'IN_PROGRESS'
item_p2.status = 'IN_PROGRESS'
```

Zato što `link_report_to_binding()` (postojeća, nepromijenjena metoda iz Phase 1/2)
čita `task.plan_item_id` U TRENUTKU KREIRANJA LINKA (ne u trenutku kreiranja
binding-a), test koji prvo drift-uje pa tek onda linkuje zapravo hvata NOVU
(drift-ovanu) vrijednost kao "snapshot" — potpuno suprotno onome što test tvrdi da
dokazuje. Uz to, `item_p1` nikad nije postavljen na `IMPLEMENTED`/`VERIFIED` (ostaje
default `IN_PROGRESS` od kreiranja), pa asercija `item_p1.status == "IN_PROGRESS"`
prolazi TRIVIJALNO nezavisno od toga koji je PlanItem stvarno dobio consequence.

**Zaključak**: test NE dokazuje Section 9 zahtjev ("Historical drift test mora
stvarno dokazati da live Task pokazivač može biti drugačiji, a decision ostaje
vezan za historical snapshot"). Ovo je test-only defekt — sama produkcijska logika
(`_apply_plan_item_consequences`) je ispravna i dijeli mehanizam sa već dokazanim
Phase 3A testom — ali Phase 3D specifično NE dokazuje ovo svojstvo za
`WorkflowDecisionService` put.

## 10. Multiple historical snapshots

`test_multiple_snapshots_null_plan_item_id` (`test_workflow_ledger_phase3d.py:472-506`)
— za razliku od testa iz sekcije 9, ovaj test JE ispravno konstruisan: `link1.
resolved_plan_item_id = item_a.id`, `link2.resolved_plan_item_id = item_c.id`
(direktno na stvarnim, već kreiranim link redovima preko dva stvarna binding
segmenta — isti obrazac validiran u Phase 3C F5 fix-u), zatim EKSPLICITNO postavlja
`item_a.status = "IMPLEMENTED"` i `item_c.status = "VERIFIED"` PRIJE `set_verdict()`
poziva — netrivijalna početna stanja.

Asercije:
```python
assert events[0].plan_item_id is None
assert len(payload["resolved_plan_item_ids"]) == 2
...
assert item_a.status == "IN_PROGRESS"
assert item_c.status == "IN_PROGRESS"
```
Sve PASS, i asercija je netrivijalna (oba item-a su stvarno promijenila status).

**Potvrđeno — `plan_item_id=NULL` ovdje ne znači "bez consequence-a": oba
historical PlanItem-a stvarno dobijaju IN_PROGRESS tranziciju.** Section 10 zahtjev
je zadovoljen, za razliku od Section 9 testa.

## 11. Unassigned

`test_unassigned_updates_compatibility_no_ledger_event` — session bez task/plan_item
(prava unassigned binding), report bez linkova → `_build_target_groups()` vraća [],
legacy-fallback upit ne pronalazi kvalifikovan binding (filter zahtijeva
`task_id IS NOT NULL OR plan_item_id IS NOT NULL`, a unassigned binding ima oba
NULL) → pada u "0 groups" granu → samo compatibility projection, 0 TASK_DECISION.
PASS. **Potvrđeno — nema project/session/report-scoped fallback eventa.**

## 12. Legacy fallback

- **Tačno jedan binding**: `test_single_binding_legacy_creates_task_decision` —
  report bez `AgentReportBindingLink`, tačno jedan historical binding → 1
  TASK_DECISION, `payload["target_resolution"] == "legacy_single_binding"`. PASS.
- **2+ bindinga bez linkova**: `test_ambiguous_legacy_zero_events` — dva binding
  segmenta (switch_binding), report bez linkova → `len(bindings) == 1` je False →
  0 TASK_DECISION. PASS.
- **Korumpirani linkovi (0 validnih grupa ALI linkovi postoje)**: kod eksplicitno
  provjerava `has_links` PRIJE legacy fallback-a (`decisions.py:109-118`) — ako
  linkovi postoje ali `_build_target_groups()` ih odbacuje (npr. cross-session),
  legacy fallback se NE koristi (`groups = []` eksplicitno, komentar "Korumpirani
  linkovi (cross-session) — ne sme legacy fallback"). Ovo sprječava da se
  legacy-fallback koristi kao zaobilaznica za odbačene/korumpirane linkove.

**Potvrđeno — sve tri grane (1 binding / 0 ili 2+ / korumpirani linkovi) ispravno
razdvojene, nema nagađanja.**

## 13. Transaction atomicity

`test_consequence_failure_rollback` — monkeypatch poziva ORIGINALNI
`_apply_plan_item_consequences` (stvarna IMPLEMENTED→IN_PROGRESS tranzicija +
stvaran TASK_DECISION event, oba flush-ovana), TEK ONDA baca `RuntimeError`. Prije
poziva: `item.status = "IMPLEMENTED"` (netrivijalno), `db_session.commit()` na baznom
stanju. Nakon `pytest.raises` + `db_session.rollback()`:
```python
assert refreshed_report.user_verdict == prev_verdict
assert refreshed_report.user_notes == prev_notes
assert refreshed_item.status == prev_status         # "IMPLEMENTED", ne "IN_PROGRESS"
assert len(_ledger_events(db_session, project)) == 0
```
Asercija na `item.status` je netrivijalna: da rollback nije radio, status bi bio
"IN_PROGRESS" (jer je originalna consequence stvarno izvršena prije raise-a), pa bi
test PAO. PASS potvrđen pokretanjem.

**Ovo NIJE test koji baca exception prije stvarnog event/consequence toka — spec
zahtjev iz Section 13 je zadovoljen, za razliku od analognog Phase 3C F7 problema
koji je bio ispravljen u prethodnom ciklusu.**

## 14. Multi-target partial failure

`test_multi_target_partial_failure_rollback` — dva targeta (task A, task B), oba
`item.status = "IMPLEMENTED"` (netrivijalno). Monkeypatch primjenjuje STVARNU
consequence samo za A (`original(self, [g], verdict)` za `g.task_id == task_a.id`),
zatim BEZUSLOVNO baca `RuntimeError` (B nikad ne dobija consequence pokušaj — ovo
ispravno simulira "A uspije, B padne odmah nakon" tok). Nakon rollback-a:
```python
assert refreshed_a.status == prev_status_a   # "IMPLEMENTED", ne "IN_PROGRESS"
assert refreshed_b.status == prev_status_b   # "IMPLEMENTED" (nepromijenjeno)
assert refreshed_report.user_verdict == prev_verdict
assert len(_ledger_events(db_session, project)) == 0
```
`refreshed_a` asercija je netrivijalna (A je stvarno tranzicionisan prije raise-a,
pa rollback mora to poništiti da bi test prošao). PASS potvrđen pokretanjem.

**Potvrđeno — pravi DB rollback test, ne mock-only assertion.**

## 15. Cross-project corruption

`test_cross_project_corruption_zero_events` — direktna ORM konstrukcija
`AgentReportBindingLink` koja povezuje report iz `project` sa bindingom iz `other`
projekta (zaobilazi `link_report_to_binding()` guard). Poziva
`WorkflowDecisionService(db_session).record_report_decision(...)` direktno.
`_build_target_groups()` odbacuje binding (session mismatch) → `groups=[]` →
`has_links=True` → legacy fallback eksplicitno onemogućen → 0 TASK_DECISION, 0
PlanItem mutacija (nijedna grupa = nijedna consequence). PASS.

**Potvrđeno — nema mixed-project eventa, nema foreign PlanItem mutacije.**

## 16. Event boundary

`test_no_finding_decided_no_user_validation` — provjerava da je jedini
`event_type` u tabeli `TASK_DECISION`, eksplicitno odsustvo `FINDING_DECIDED` i
`USER_VALIDATION`. PASS. Grep kroz `decisions.py` potvrđuje da je `TASK_DECISION`
jedini `event_type` konstruisan u cijelom fajlu.

## 17. Report projection

`_apply_compatibility_projection()` ažurira `user_verdict`, `user_notes`,
`status="FINAL"`, `updated_at`, i appenduje `verdict_audit_json` — ali se poziva
SAMO nakon validne nove decision akcije (nikad na retry granu, koja se vraća prije
ovog poziva). Kod ovo garantuje strukturalno. Test pokrivenost za "audit se ne
duplira na retry" nije eksplicitna (vidi Nalaz L1), ali kod je ispravan po čitanju.

## 18. Timestamp

`decision_time = datetime.now(tz=UTC)` (`decisions.py:101`) — računa se JEDNOM na
početku `record_report_decision()`, koristi se i za `event.occurred_at`
(`decisions.py:199`) i za `_apply_compatibility_projection`'s `updated_at`/audit
timestamp (`decisions.py:220-250`) — jedan backend timezone-aware timestamp
dijeljen između eventa i projekcije, ne `report.created_at`. **Potvrđeno.**

## 19. Test coverage — stvarno stanje

```
python -m pytest tests/integration/test_workflow_ledger_phase3d.py -v --tb=short
collected 28 items
28 passed in 1.69s
```

Coverage matrica iz reporta (23 reda, jedan test naziv dupliran za dva reda —
`test_no_finding_decided_no_user_validation` pokriva i "no USER_VALIDATION" i "no
FINDING_DECIDED") stvarno odgovara podskupu od 28 testova; preostalih 5 testova
(`test_accepted_does_not_change_plan_item`, `test_needs_work_creates_task_decision`,
`test_rejected_creates_task_decision`, `test_notes_in_payload`,
`test_previous_decision_recorded`) nije eksplicitno navedeno u matrici, ali svi
postoje i prolaze. Svi traženi scenariji iz zahtjeva (REJECTED VERIFIED, A-B-A,
historical drift, multiple snapshots consequence, conflict notes, conflict report,
cross-project corruption, consequence rollback, multi-target rollback, legacy
single binding, legacy ambiguous binding, no USER_VALIDATION, no FINDING_DECIDED)
imaju odgovarajući test — ali "historical drift" test ne dokazuje ono što tvrdi
(vidi Nalaz #9/HIGH).

## 20. Relevant regressions

```
python -m pytest tests/integration/test_workflow_ledger_phase3a.py \
  tests/integration/test_workflow_ledger_phase3b.py \
  tests/integration/test_workflow_ledger_phase3c.py \
  tests/integration/test_agent_report_ingestion.py \
  tests/integration/test_agent_report_v2.py \
  tests/unit/test_reports.py -v --tb=short
→ 102 passed, 0 failed
```
(17 + 19 + 22 + 26 + 12 + 6 = 102 — odgovara report-ovoj tvrdnji.)

Napomena: `test_agent_report_v2.py` testovi i dalje prolaze nepromijenjeni — vidi
Nalaz M4 (analiza je preporučila da se prepišu da dokažu TASK_DECISION kao
canonical authority, što nije urađeno).

## 21. Full verification

```
python scripts/verify.py
[PASS] 1. Ruff format check
[PASS] 2. Ruff lint
[PASS] 3. mypy
[PASS] 4. Architecture boundaries
[PASS] 5. Unit tests
[PASS] 6. Migrations check
[PASS] 7. Alembic round-trip
Prošlo: 7/7
[PASS] VERIFIKACIJA PROŠLA
```

**7/7 PASS.**

## 22. Implementation report integrity

### A — test count kontradikcija

"Izmenjeni fajlovi" tabela (implementation report, red 42): *"Novi fajl — 14
testova"*. "Testovi (28)" header i coverage matrica kasnije u istom dokumentu.
Stvarno pokretanje: **28 collected, 28 passed** (potvrđeno u Section 19).

**"14 testova" u tabeli izmijenjenih fajlova je stale/netačno. "28" je tačno.**
Ovo je unutrašnja kontradikcija u istom dokumentu koju treba ispraviti.

### B — set_verdict() public API tvrdnja

"Explicit non-goals" (implementation report, red 167): *"Nije menjan
`ReportService.set_verdict()` public API (samo delegira)."*

Ali "Izmenjeni fajlovi" tabela (red 41) EKSPLICITNO kaže: *"`set_verdict()`
delegira na `WorkflowDecisionService`; **dodat `decision_id` parametar**"* — i diff
to potvrđuje (`decision_id: str | None = None` dodat u signature).

Dodavanje opcionog parametra sa default vrijednošću JESTE promjena signature-a
(backward-compatible extension, ne breaking change), ali tvrdnja "nije menjan
public API" je tehnički netačna — trebalo je pisati "signature backward-kompatibilno
proširen opcionim `decision_id`, bez breaking promjene", ne "nije menjan".

**Ocjena: REPORT CORRECTION REQUIRED** za ovu tačku — formulacija je
samo-kontradiktorna unutar istog dokumenta (red 41 vs red 167).

## 23. Metadata

- **Analysis report** (`...analysis.md`): `report_id: 1812603f-3285-43b0-80ac-
  6e605302ac5d` — format odgovara UUIDv4 (verzijski nibl '4', varijantni nibl '8').
  `created_at: 2026-08-12T15:37:33+02:00` — timezone-aware, nije u budućnosti
  (danas 2026-08-12), sekunde nisu okrugle (`:33`). `agent: codex, model: gpt-5`.
- **Implementation report** (`...implementation.md`): `report_id: b2643ffd-bd91-
  4eff-ba0c-a38cdf2c3865` — format odgovara UUIDv4 (verzijski nibl '4', varijantni
  nibl 'b'=1011). `created_at: 2026-08-12T16:49:58+02:00` — timezone-aware, nije
  budući, sekunde nisu okrugle (`:58`). `agent: crush, model: deepseek-v4-pro`.

Ne mogu dokazati da je `uuid.uuid4()` stvarno pozvan (ne postoji način da se to
retroaktivno potvrdi iz samog stringa) — mogu samo potvrditi da format i
raspodjela nibl-ova odgovaraju validnom UUIDv4 stringu i da nema uočljivog
artefakta fabrikacije (npr. sekvencijalnih heksadecimalnih segmenata ili okruglih
timestamp-ova) kakvi su hvatani u ranijim fazama ovog projekta.

- **Ovaj review report** (`report_id: d35d5760-a612-4e33-aee2-775726f0cf12`,
  `created_at: 2026-08-12T17:09:44+02:00`) — generisan sa `python -c "import uuid;
  print(uuid.uuid4())"` i `date +"%Y-%m-%dT%H:%M:%S%z"` neposredno prije pisanja,
  agent/model odgovaraju stvarnom checkeru (claude / claude-sonnet-5).

## 24. Final verdict

### Nalazi po ozbiljnosti

**HIGH**

- **H1** — `tests/integration/test_workflow_ledger_phase3d.py:449-468`
  (`test_historical_plan_item_drift`). Test drift-uje `task.plan_item_id` PRIJE
  poziva `link_report_to_binding()` (suprotno Phase 3A obrascu), pa
  `resolved_plan_item_id` hvata NOVU (drift-ovanu) vrijednost umjesto stare.
  Dodatno, `item_p1` nikad nije postavljen na `IMPLEMENTED`/`VERIFIED`, pa je
  asercija `item_p1.status == "IN_PROGRESS"` trivijalno tačna. Test ne dokazuje
  Section 9 zahtjev. **Zašto je važno**: ovo je isti obrazac defekta koji je već
  jednom otkriven i ispravljen u Phase 3C (F7) — test koji "PROLAZI" bez ikakvog
  stvarnog dokaza. Produkcijski kod je ispravan (potvrđeno čitanjem
  `_apply_plan_item_consequences`, koji nikad ne čita `Task.plan_item_id`), ali
  Phase 3D specifično ne dokazuje ovo svojstvo za `WorkflowDecisionService`.
  **Minimalna ispravka**: zamijeniti redoslijed (`link_report_to_binding()` PRIJE
  `task.plan_item_id = item_p2.id`, po uzoru na Phase 3A test), i postaviti
  `item_p1.status = "IMPLEMENTED"` prije `set_verdict()` da asercija bude
  netrivijalna.

**MEDIUM**

- **M2** — implementation report, red 42 vs red 113. "Izmenjeni fajlovi" tabela
  tvrdi "14 testova", "Testovi (28)" header i stvaran pytest run tvrde 28. **Zašto
  je važno**: interna kontradikcija u istom dokumentu, ista klasa greške kao u
  prethodnim fazama ovog projekta. **Minimalna ispravka**: ispraviti "14" na "28" u
  tabeli izmijenjenih fajlova.
- **M3** — `src/flowos/service/services/reports/service.py:216`. `_reopen_plan_
  item()` ostaje definisan ali je mrtav kod (nema pozivalaca u `src/` nakon
  cutovera). **Zašto je važno**: mrtav kod koji implementira STARU (pre-cutover)
  authority logiku ostavljen u istom fajlu može zbuniti budućeg čitaoca ili biti
  greškom ponovo pozvan. **Minimalna ispravka**: ukloniti metodu u zasebnom
  cleanup zadatku (van scope-a ovog reviewa da se izbjegne miješanje refactor-a i
  funkcionalne izmjene).
- **M5** — implementation report, red 41 vs red 167 (Section 22/B). Tvrdnja "Nije
  menjan `ReportService.set_verdict()` public API" je samo-kontradiktorna sa
  istom tabelom koja kaže "dodat `decision_id` parametar". **Minimalna ispravka**:
  preformulisati u "signature backward-kompatibilno proširen opcionim
  `decision_id`, bez breaking promjene".
- **M4** — `tests/integration/test_agent_report_v2.py` nije mijenjan uprkos
  eksplicitnoj preporuci iz analize (§U): "AgentReport v2 reopen testovi... treba
  ih prepisati, ne samo slijepo očuvati... dokaz treba uključiti TASK_DECISION
  Ledger event kao canonical authority." Testovi i dalje prolaze (funkcionalno
  ponašanje očuvano kroz facade), ali ne dokazuju novi authority put. **Zašto je
  važno**: regresiona zaštita za stare reopen scenarije sada posredno zavisi od
  `WorkflowDecisionService`, ali nijedan postojeći test to eksplicitno ne provjerava
  na nivou v2 test suite-a. **Minimalna ispravka**: dodati bar jednu asercija u
  postojeće v2 reopen testove da provjeri prisustvo TASK_DECISION eventa, ili
  eksplicitno dokumentovati zašto se to odgađa za kasniju fazu.

**LOW**

- **L1** — `test_same_decision_id_retry_no_duplicate` ne provjerava eksplicitno da
  `report.updated_at` i dužina `verdict_audit_json` liste ostaju nepromijenjeni
  nakon retry-a (kod to garantuje strukturalno, ali test to ne dokazuje
  empirijski).
- **L2** — Conflict testovi (`test_same_decision_id_different_verdict_raises`,
  `test_conflict_notes`, `test_conflict_report`) ne provjeravaju eksplicitno "0 DB
  mutacija" nakon `pytest.raises` (npr. da broj eventa ostaje isti kao prije
  drugog poziva). Kod to garantuje kontrolom toka (raise prije ijednog upisa), ali
  nije empirijski dokazano testom.

### Ocjena

```
CODE: FIXES REQUIRED
```
Razlog: produkcijski kod (`decisions.py`, `service.py`) je arhitektonski ispravan
i dosljedno prati zaključani contract iz analize — svih 18 provjerenih zahtjeva
(sekcije 2-18) su kodom zadovoljeni. Ali **test suite** (dio isporučenog Phase 3D
paketa) sadrži H1 — test koji tvrdi da dokazuje kritičan zahtjev (Section 9,
historical snapshot authority) a zapravo ne dokazuje ništa, zbog strukturne greške
u redoslijedu operacija. Po istom standardu primijenjenom u prethodnom Phase 3C
review ciklusu (F5/F7), test-only defekt koji lažno predstavlja "PASS" kao dokaz
kritičnog zahtjeva se tretira kao nedostatak isporuke, ne samo kao problem
izvještaja.

```
REPORT: CORRECTION REQUIRED
```
Razlog: M2 (14 vs 28 testova), M5 (samo-kontradiktorna "nije menjan public API"
tvrdnja), i implicitna precjena da coverage matrica "historical drift PASS"
dokazuje Section 9 zahtjev (vezano za H1).

```
VERDICT: FIXES REQUIRED
```

Potrebno prije commit-a:
1. Ispraviti `test_historical_plan_item_drift` (H1) — zamijeniti redoslijed
   link/drift operacija i postaviti netrivijalno početno stanje za `item_p1`.
2. Ispraviti implementation report: broj testova (M2), formulaciju o
   `set_verdict()` API-ju (M5).
3. Preporučeno, ne blokirajuće: ukloniti mrtav `_reopen_plan_item()` kod (M3) u
   zasebnom cleanup zadatku; razmotriti dopunu `test_agent_report_v2.py` testova
   TASK_DECISION asercijama (M4); dopuniti retry/conflict testove eksplicitnim
   "0 mutacija" asercijama (L1, L2).

Nakon ispravke H1 (i po mogućnosti M2/M5), Phase 3D je funkcionalno spreman za
commit — nijedan pronađeni nalaz ne ukazuje na stvarnu grešku u produkcijskoj
logici.
