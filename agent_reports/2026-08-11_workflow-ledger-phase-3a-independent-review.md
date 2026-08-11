---
flowos_report_version: 1
report_id: e8fa79c3-01d2-47ad-afda-77131ce279b1
agent: claude
model: claude-sonnet-5
session_id: unknown
report_type: review
tasks:
  - unassigned
commits: []
created_at: 2026-08-11T20:58:57+02:00
---

# Workflow Ledger Phase 3A — formalni nezavisni review

## Datum

2026-08-11

## Agent / model / sesija

- Agent: claude (Claude Code)
- Model: claude-sonnet-5
- Sesija: unknown

## Scope

Formalni nezavisni review necommitovanih izmjena "Workflow Ledger Phase 3A —
Authority Cutover + IMPLEMENTATION_COMPLETED" (codex/gpt-5, `agent_reports/
2026-08-11_workflow-ledger-phase-3a-implementation.md`, uz `agent_reports/
2026-08-11_workflow-ledger-phase-3a-analysis.md` kao kontekst). Kod NIJE
mijenjan, nalazi NISU popravljani, commit NIJE napravljen. Sve tvrdnje su
provjerene protiv stvarnog koda, stvarnih testova i, gdje je bilo potrebno,
ad-hoc probom — ne protiv teksta izvještaja.

## 1. Potvrda scope-a

```text
git status --short --branch
## main...origin/main
 M alembic/env.py
 M src/flowos/service/services/reports/ingestion.py
 M src/flowos/service/services/sessions/completion.py
 M tests/unit/test_session_completion.py
?? agent_reports/2026-08-11_workflow-ledger-phase-3a-analysis.md
?? agent_reports/2026-08-11_workflow-ledger-phase-3a-implementation.md
?? alembic/versions/b7c2e1d4a903_workflow_ledger_events.py
?? src/flowos/service/services/infrastructure/persistence/workflow_ledger_models.py
?? src/flowos/service/services/workflow/
?? tests/integration/test_workflow_ledger_phase3a.py
```

Potvrđeno čitanjem svakog diff-a: implementirano je isključivo
`WorkflowLedgerEvent`, migracija, minimalni `WorkflowLedgerService`,
`IMPLEMENTATION_COMPLETED` writer, wiring iz `AgentReportIngestionService`,
authority cutover u `SessionCompletionService` i pripadajući testovi. Nije
pronađeno: `TEST_RESULT`, `REVIEW_COMPLETED`, `FINDING_DECIDED`,
`FIX_COMPLETED`, `USER_VALIDATION`, `TASK_DECISION`, GUI, HTTP Ledger API,
event-sourcing framework, queue/broker, LLM, backfill starih reportova,
izmjena AgentReport YAML contracta niti izmjena `ReportService.set_verdict()`
(fajl `reports/service.py` uopšte nije u listi izmijenjenih fajlova — potvrđeno
`git status`). Scope je čist.

## 2. Authority cutover — SessionCompletionService (KRITIČNO)

Pročitan CIJELI trenutni fajl `sessions/completion.py` (ne samo diff), linija
po liniju.

Potvrđeno UKLONJENO (diff pokazuje čisto brisanje bloka, ne komentarisanje):

- blok `IN_PROGRESS → IMPLEMENTED` (commit/dirty-files/conflict heuristika,
  `progress_svc.validate_transition(plan_item, "IMPLEMENTED", ...)`);
- blok `IMPLEMENTED → VERIFIED` (`verify.py PASS` →
  `progress_svc.validate_transition(plan_item, "VERIFIED", ...)`);
- `plan_progress.updated` websocket emit vezan za ovaj tok.

Potvrđeno grep-om nad cijelim `src/`: nema drugog poziva
`validate_transition(..., "IMPLEMENTED")` ili `validate_transition(...,
"VERIFIED")` bilo gdje u kodu — ovaj obrisan blok je bio JEDINI izvor
automatske promocije u ta dva statusa (`_reopen_plan_item()` iz Phase 1 ide
suprotnim smjerom, IMPLEMENTED/VERIFIED → IN_PROGRESS, i eksplicitno je van
scope-a ovog reviewa po nalogu). Fajl više ne importuje `PlanProgressService`
uopšte. `PlanItem` se u fajlu koristi ISKLJUČIVO za čitanje (`plan_item.title`
za log na liniji 78-81), nikad za pisanje `.status`. Nema skrivenog/fallback
puta.

Potvrđeno ZADRŽANO (čitanjem cijelog fajla):

`ended_at`, `exit_code`, `result_commit_sha` (kad je eksplicitno proslijeđen —
vidi F4 za nijansu), zatvaranje aktivnog `SessionTaskBinding`, izveden
`AgentSession.status`, Git state read, `VerificationService`,
`verification.completed` emit, `VERIFY_RESULT` `SessionEvent`, legacy draft
`AgentReport` (bez `report_type`/`work_status`/source polja — namjerno
non-qualifying), `NO_COMMIT` conflict detection, resume regeneracija,
`session.completed` i `project.resume.updated` emit-ovi. `plan_progress.updated`
je ispravno uklonjen jer više nema stvarne PlanItem promjene koju bi
najavljivao.

**Authority cutover je stvaran i potpun.** Vidi F4 za jednu manju, nenavedenu
nuspojavu.

## 3. `WorkflowLedgerEvent` model i migracija

`alembic/versions/b7c2e1d4a903_workflow_ledger_events.py` i
`workflow_ledger_models.py` pročitani u cjelosti i upoređeni polje po polje —
potpuno usklađeni. FK pravila potvrđena TAČNO kako je traženo:

```text
project_id    → ON DELETE CASCADE
session_id    → ON DELETE SET NULL
task_id       → ON DELETE SET NULL
plan_item_id  → ON DELETE SET NULL
```

**Stvarna SQLite FK provjera** (ne samo čitanje migracije): probom je
kreirana prava Alembic-migrirana SQLite baza (`alembic upgrade head` kroz
CIJELI lanac migracija, `PRAGMA foreign_keys=ON`), upisan
`WorkflowLedgerEvent` sa svim FK popunjenim, zatim direktno (ORM-nivo,
zaobilazeći servisne RESTRICT provjere — vidi napomenu ispod) obrisan `Task` i
`AgentSession`:

```text
Prije brisanja: session_id=sess1 task_id=task1 plan_item_id=item1
Poslije brisanja Task i AgentSession:
  WorkflowLedgerEvent JOS POSTOJI: session_id=None task_id=None plan_item_id=item1
  session_id postao NULL? True
  task_id postao NULL? True
  plan_item_id NETAKNUT? True
Poslije brisanja Project (CASCADE):
  WorkflowLedgerEvent i dalje postoji? False
```

SET NULL i CASCADE rade tačno kako je deklarisano, na stvarnom SQLite
engine-u.

Napomena (nije falsifikovan test, nego stvarno ograničenje): u probi je Task
obrisan BEZ postojećeg `SessionTaskBinding` reda, jer bi u praksi
`TaskService.delete_task()` bio blokiran RESTRICT constraintom na
`session_task_bindings.task_id` (Phase 1) prije nego bi ikad stigao do
`workflow_ledger_events.task_id` FK-a — a Task koji je proizveo Ledger event
NUŽNO ima barem jedan takav binding. Dakle SET NULL putanja za `task_id` je
danas dostižna samo direktnim DB brisanjem, ne kroz postojeći servisni sloj —
ovo NIJE finding, samo tačno navedeno ograničenje kako je nalog tražio.

Ostalo potvrđeno: `idempotency_key` ima DB-level `UniqueConstraint` (i u ORM-u
i u migraciji); `payload_json` je `nullable=False` sa `server_default="{}"` u
migraciji i `default="{}"` u ORM-u; nema backfill-a (samo `create_table`);
`python -m alembic heads` prije i poslije primjene ove migracije pokazuje
JEDAN linearan head (`b7c2e1d4a903`), bez grananja.

Odstupanje od analize (LOW, vidi REPORT QUALITY): analysis report je
preporučio DB `CHECK` constraint-e za `event_type != ''`, `source_kind != ''`,
`idempotency_key != ''` — migracija ih ne sadrži. Nije exploitable danas
(servis uvijek popunjava stvarne vrijednosti), ali je nedokumentovano
odstupanje od vlastitog analiznog contracta.

## 4. Append-only contract i jedini writer

`WorkflowLedgerService` (`src/flowos/service/services/workflow/ledger.py`)
ima TAČNO tri javne metode: `append_implementation_completed_from_report()`,
`list_for_project()`, `list_for_task()` — potvrđeno čitanjem cijelog fajla,
nema `update_event`/`delete_event`/`replace_event` niti bilo kog drugog
mutating poziva. Grep nad cijelim `src/` potvrđuje da se `WorkflowLedgerEvent`
konstruiše (dodaje) SAMO unutar ovog fajla — nijedan drugi modul (watcher,
GUI, HTTP kontroler) ne piše direktno u Ledger. Watcher (`composition_root.py`)
i startup scan pozivaju isključivo `AgentReportIngestionService.ingest_file()`
— sam `WorkflowLedgerService` poziva se JEDINO iznutra `ingestion.py`, nikad
direktno iz watcher callback-a. Tok je tačno onaj traženi: watcher/startup →
`AgentReportIngestionService` → `AgentReport` + `BindingLinks` →
`WorkflowLedgerService`.

## 5. IMPLEMENTATION_COMPLETED semantika i qualification

`_is_qualifying_report()` provjerava `report_type == "implementation"`,
`work_status == "completed"`, `source_report_id/source_path/
source_content_sha256/session_id is not None` — tačno traženi skup. "Najmanje
jedan `AgentReportBindingLink`" i "deterministički rezolvljiv binding" nisu
provjereni u ovoj metodi eksplicitno, nego implicitno kroz
`_build_target_groups()`, koja vraća `[]` (dakle "bez eventa") kad nema
linkova ili kad bilo koji binding ne razrješava logički target — funkcionalno
identičan efekat, potvrđen testovima.

Testovima (real, ne mock) nezavisno pokrenuto i potvrđeno TAČNO za cijelu
traženu matricu iz sekcije 6 naloga:

```text
implementation + completed → event (test 1)
implementation + partial   → bez eventa (parametrizovan test)
implementation + blocked   → bez eventa (parametrizovan test)
analysis                    → bez eventa (parametrizovan test)
review                      → bez eventa (parametrizovan test)
fix + completed             → bez IMPLEMENTATION_COMPLETED (parametrizovan test)
unassigned                  → bez eventa (test_unassigned_creates_no_event)
legacy draft report         → bez eventa (test_legacy_report_never_creates_event,
                               poziva WorkflowLedgerService DIREKTNO nad pravim
                               legacy draft-om iz ReportService.create_draft())
NEEDS_LINK                  → bez eventa (test_needs_link_creates_no_report_or_event,
                               potvrđuje i 0 AgentReport redova)
```

## 6/7/8. Multi-task, A-B-A grouping, direct PlanItem target

`_build_target_groups()` grupiše po `(target_kind, target_id)` tuple-u —
`("task", task_id)` ili `("plan_item", plan_item_id)`. Jedan event po
jedinstvenom targetu, ne po bindingu i ne po reportu — pregledano kodom i
potvrđeno testom `test_two_task_targets_create_two_events` (2 taska → tačno 2
eventa, ispravan `task_id`/`plan_item_id` po svakom). A-B-A za isti task
kolabira u JEDAN event preko `dict.setdefault` akumulacije — potvrđeno
`test_a_b_a_same_task_creates_one_event_with_all_binding_links` (stvarna A→B→A
istorija preko `SessionTaskBindingService.switch_binding()`, 1 event, 2
`binding_link_ids`/`session_task_binding_ids`, deterministički sortirani
preko `sorted(set(...))`). Direct PlanItem binding (bez Task-a) ispravno daje
`task_id=None`, `plan_item_id=<historical>` — potvrđeno
`test_direct_plan_item_target_creates_event_without_task_id`. Nijedan Task
nije izmišljen za direct PlanItem slučaj.

## 9. PlanItem snapshot i drift

`_target_for_binding()`/`_build_target_groups()` koriste ISKLJUČIVO
`SessionTaskBinding.task_id`/`.plan_item_id` (istorijska, nepromjenjiva polja
binding segmenta) i `AgentReportBindingLink.resolved_plan_item_id` (Phase 1
snapshot uzet u trenutku linkovanja) — nigdje se ne poziva `Task.plan_item_id`
kao živi lookup unutar `ledger.py` (potvrđeno grep-om — `Task` model se uopšte
ne importuje u ovaj fajl).

Drift scenario iz sekcije 9 je EKSPLICITNO reprodukovan pravim testom
`test_task_event_uses_binding_link_snapshot_not_live_task_plan_item`: Task
vezan za `item_a`, binding+link kreiran (snapshot = item_a), zatim
`task.plan_item_id` PROMIJENJEN na `item_b` DIREKTNO (simulira drift), pa tek
onda Ledger append — rezultat: `event.plan_item_id == item_a.id` (snapshot),
NE `item_b` (živi pokazivač). Nezavisno pokrenuto, PROLAZI.

Više različitih snapshotova za isti task → `plan_item_id = NULL`, payload
čuva sve — potvrđeno
`test_task_event_with_multiple_plan_snapshots_keeps_plan_item_null` (dva
linka sa različitim `resolved_plan_item_id` vrijednostima za isti task target,
`event.plan_item_id is None`, `resolved_plan_item_ids` payload sadrži oba,
sortirano).

## 10. Idempotency

Format potvrđen tačan (`ledger.py:_idempotency_key`):
`workflow-ledger:v1:IMPLEMENTATION_COMPLETED:agent_report:{report.id}:
{target_kind}:{target_id}`. DB `UniqueConstraint` na `idempotency_key`
potvrđena i migracijom i testom
`test_idempotency_key_has_db_unique_constraint` (direktan duplikatni insert →
`IntegrityError`).

**Dva scenarija koja nalog eksplicitno traži, a nisu bila pokrivena
postojećim testovima, provjerena su ad-hoc probom u ovom review-u:**

(A) Direktan sekvencijalni servisni retry — pozvano
`append_implementation_completed_from_report(report_id)` DVA PUTA za isti
već-komitovani `report_id`:

```text
Prvi poziv: 1 event(a)
Drugi poziv (retry): 1 event(a)
Isti event ID vracen? True
Ukupno WorkflowLedgerEvent redova: 1
```

Ispravno — pre-check unutar servisa vraća postojeći event, no-op.

(B) Prava dvo-transakcijska trka — dvije odvojene sesije, obje pročitaju "nema
postojećeg eventa" PRIJE nego ijedna komituje (probom ručno rekonstruisano da
izbjegne da druga sesija slučajno vidi već-komitovano stanje prve — vidi
metodološku napomenu ispod):

```text
T1 pre-check: None
T2 pre-check: None
T1 komitovao svoj event.
T2 baca gresku na commit: IntegrityError: UNIQUE constraint failed:
workflow_ledger_events.idempotency_key
KONACNO STANJE: 1 WorkflowLedgerEvent red za taj idempotency_key
```

DB unique constraint ispravno sprečava duplikat pod pravom trkom. Rezultat
zadovoljava traženi bar iz naloga (nema parcijalnih podataka — cijela T2
transakcija je rollback-ovana; deterministic retry bi zavisio od toga da T2
retry ide kroz `_check_identity()` prvo, koji bi na ponovnom pokušaju vidio
T1-ov već postojeći `AgentReport` sa istim `source_report_id` i vratio
`ALREADY_INGESTED` prije nego ikad ponovo stigne do Ledger append-a).

Reachability napomena: pod trenutnim wiring-om, `append_implementation_
completed_from_report()` se poziva TAČNO jednom po `ingest_file()` pozivu, u
istoj transakciji kao kreiranje `AgentReport`-a čiji je `id` (svjež UUID po
pokušaju) dio idempotency ključa. Pošto Phase 2 već sprečava da dva RAZLIČITA
`AgentReport.id` nastanu za isti fajl pod trkom (unique `source_report_id`/
`source_path`), ovaj specifičan Ledger-nivo race danas nije dostižan kroz
ijedan ožičen pozivalac — DB zaštita je ispravan defense-in-depth za buduće
pozivaoce, ne aktivno dostižan bug danas. Vidi F1/F2 u TEST FINDINGS za
nedostatak automatizovanog testa za oba scenarija.

## 12. Transaction boundary (KRITIČNO)

Pregledan stvarni `ingestion.py` diff: `WorkflowLedgerService(self._session).
append_implementation_completed_from_report(report.id)` poziva se UNUTAR
ISTOG `try:` bloka kao `create_draft()`/`link_report_to_binding()`, prije
`except IntegrityError`. Caller (watcher/startup scan) radi jedini završni
`db.commit()`.

Tačna reprodukcija tražena u nalogu je već implementirana kao regresioni test
`test_ledger_failure_rolls_back_report_links_and_events` — pregledan i
nezavisno pokrenut: `WorkflowLedgerService.append_implementation_completed_
from_report` je monkeypatch-ovan da baci `RuntimeError` NAKON što bi
report/linkovi već bili kreirani u istoj transakciji; `ingest_file()`
propagira `RuntimeError` (potvrđuje da `except IntegrityError` NE hvata
generičke greške); test radi `db_session.rollback()` (simulira caller
ponašanje); rezultat:

```text
AgentReport.count() == 0
AgentReportBindingLink.count() == 0
WorkflowLedgerEvent.count() == 0
```

Nema stanja "report ingested, ledger izgubljen". Ovo NIJE HIGH/BLOCKER —
suprotno, ovo je upravo dokaz da se HIGH/BLOCKER scenario ne dešava. `FileActivity`
ostaje netaknut jer je (nepromijenjeno iz Phase 2) već zasebno komitovan prije
poziva na `ingest_file()` u watcher callback-u.

## 13. occurred_at / recorded_at

`occurred_at=report.created_at` — potvrđeno kodom i testom (`event.occurred_at
== report.created_at`, ne filesystem mtime niti YAML `created_at` direktno —
`report.created_at` je backend-validated DB polje, ne autor-tvrđeni tekst).
`recorded_at=datetime.now(tz=UTC)` — backend append trenutak. Retry (kroz
pre-check no-op putanju) vraća POSTOJEĆI event objekat nepromijenjen — njegov
`occurred_at`/`recorded_at` se ne dodiruje jer se ne radi UPDATE, samo SELECT
i rani `return`. Potvrđeno kodom (nema `setattr`/`.occurred_at =` bilo gdje u
retry grani).

## 14. Payload

Sadrži tačno traženi minimalni skup: `source_report_id`, `source_path`,
`source_content_sha256`, `report_type`, `work_status`, `target_kind`,
`target_id`, `binding_link_ids`, `session_task_binding_ids`,
`resolved_plan_item_ids`, uslovno `task_id`/`plan_item_id`. Svi podaci dolaze
iz DB redova (`report.*`, `link.*`, `binding.*`), ne iz Markdown tijela —
potvrđeno čitanjem `ledger.py`, nema pristupa Markdown sadržaju bilo gdje u
ovom servisu. ID liste su `sorted()` prije upisa u payload i `json.dumps(...,
sort_keys=True)` za sam JSON — determinizam potvrđen i kodom i testovima
(`test_a_b_a_...` eksplicitno provjerava `binding_link_ids ==
sorted(binding_link_ids)`).

## 15. Legacy report

Potvrđeno testom `test_legacy_report_never_creates_event` — koristi PRAVI
`ReportService.create_draft()` poziv identičan onome iz
`SessionCompletionService` (bez `report_type`/`work_status`/source polja),
direktan poziv `WorkflowLedgerService.append_implementation_completed_
from_report()` vraća `[]`. Bez backfill-a, bez heuristika — `_is_qualifying_
report()` odbija na prvom uslovu (`report_type == "implementation"` je
`False` jer je `None`).

## 16. SessionCompletion testovi — nova semantika

Pregledan diff `tests/unit/test_session_completion.py`. Tri nova testa su
PRAVA (mockuju samo `GitStateReader`/`VerificationService` kao eksterne
zavisnosti, PlanItem status provjere idu protiv stvarnog DB reda):

- `test_result_commit_does_not_mark_plan_item_implemented`: PlanItem
  IN_PROGRESS, commit prisutan → OSTAJE IN_PROGRESS, uz potvrdu
  `session.result_commit_sha == "def456"` kad je EKSPLICITNO proslijeđen.
- `test_dirty_files_do_not_mark_plan_item_implemented`: PlanItem IN_PROGRESS,
  dirty files bez commita → OSTAJE IN_PROGRESS, uz potvrdu da NO_COMMIT
  konflikt i dalje nastaje.
- `test_verify_pass_does_not_mark_plan_item_verified_but_keeps_verify_event`:
  PlanItem IMPLEMENTED, verify PASS → OSTAJE IMPLEMENTED, uz potvrdu da
  `VERIFY_RESULT` `SessionEvent` i dalje nastaje sa `"success": true` u
  payload-u.

Sva tri nezavisno pokrenuta, PROLAZE. Stari testovi nisu obrisani, nego
dopunjeni — provjereno da postojećih 7 osnovnih `TestSessionCompletion`
testova i dalje postoji i prolazi.

## Pokrenute provjere

```text
python -m pytest tests/integration/test_workflow_ledger_phase3a.py -v
→ 17 passed
```

```text
python -m pytest tests/unit/test_session_completion.py \
  tests/integration/test_agent_report_ingestion.py \
  tests/integration/test_agent_report_v2.py \
  tests/integration/test_session_task_bindings.py \
  tests/unit/test_plan_progress.py tests/integration/test_plan_progress_api.py -v
→ 122 passed, 1 warning
```

```text
python scripts/verify.py
→ Prošlo: 7/7
→ VERIFIKACIJA PROŠLA
```

```text
python -m alembic heads
→ b7c2e1d4a903 (head)   # jedan linearan head
```

```text
python scripts/guard_architecture.py
→ 9 prekršaja, IDENTIČNI kao prije Phase 3A (plan_progress.py,
  conflicts/service.py x2, reconciliation/service.py, sessions/completion.py
  x3, sessions/service.py, worktrees/manager.py) — svi pre-existing
  service→websocket importi. Nijedan u ingestion.py, workflow/ledger.py niti
  workflow_ledger_models.py. Standardni gate (tests/architecture/ u
  scripts/verify.py) PROLAZI. Phase 3A nije dodala novi prekršaj.
```

Dodatne ad-hoc probe (izolovane, van repoa, ne commitovane):
`probe_ledger_race2.py` (odjeljak 10B), `probe_ledger_idempotency.py`
(odjeljak 10A), `probe_ledger_fk_delete.py` (odjeljak 3, stvarna
Alembic-migrirana SQLite baza).

---

# CODE FINDINGS

```text
F4 — LOW
Tiha izmjena result_commit_sha "fact capture" ponašanja, nenavedena u izvještaju

Dokaz: Uklonjeni blok je sadržavao i ovu liniju, sada nepostojeću:
  session.result_commit_sha = result_commit_sha or (
      git_state.commit_sha if git_state else None
  )
Direktan parametar put (`if result_commit_sha: session.result_commit_sha =
result_commit_sha`) je ostao i testiran je. Izgubljen je SAMO fallback: kad
caller NE proslijedi `result_commit_sha` eksplicitno, ali Git stanje pokazuje
stvaran commit, `AgentSession.result_commit_sha` se više ne popunjava
automatski iz `git_state.commit_sha`.

Posljedica: Manji gubitak "korisne činjenice" (ne workflow authority) za
sesije gdje wrapper/agent ne šalje `result_commit_sha` eksplicitno ali je
commit ipak napravljen. Nalog eksplicitno traži da `result_commit_sha` ostane
zadržan kao činjenica — ova nijansa nije eksplicitno navedena u "šta je
urađeno"/"šta nije dirano" sekcijama implementacionog izvještaja.

Preporuka: Nije nužno blokirajuće za Phase 3A prihvatanje (fallback je bio
usko vezan za sad-uklonjenu evidence/conflict logiku, pa je razumno da je
otišao zajedno s njom), ali vrijedi eksplicitno potvrditi da je ovo namjerna,
prihvaćena posljedica, ne previd, i po potrebi zapisati kao poznato
ograničenje.
```

Nema drugih code findings. Authority cutover, Ledger model, append-only
contract, writer disciplina, qualification policy, multi-task/A-B-A grouping,
snapshot/drift zaštita, transaction boundary i occurred_at/recorded_at
semantika su svi potvrđeni ispravni kodom, testovima i probom.

---

# TEST FINDINGS

```text
F1 — MEDIUM
Nema automatizovanog testa za pravu dvo-transakcijsku trku na Ledger
idempotency nivou

Dokaz: postojeći test_idempotency_key_has_db_unique_constraint testira DB
constraint direktnim manuelnim insertom u istoj sesiji (nije race), a
test_same_report_retry_does_not_duplicate_event testira sekvencijalni retry
kroz cijeli ingest_file() (hvata se na Phase 2 ALREADY_INGESTED prije nego
ikad stigne do Ledger append-a). Nijedan ne reprodukuje pravu trku na Ledger
nivou analogno probi iz ovog review-a (probe_ledger_race2.py).

Posljedica: Ponašanje je NEZAVISNO POTVRĐENO ISPRAVNIM u ovom review-u (DB
unique constraint korektno sprečava duplikat, čist rollback, tačno 1 red) —
ovo je test-coverage gap, ne funkcionalan bug. Reachability kroz trenutni
wiring je uska (vidi odjeljak 10B) jer AgentReport.id je uvijek svjež po
pokušaju.

Preporuka: dodati regresioni test analogan probi u ovom izvještaju (dvije
odvojene sesije, oba pre-check vide "nema eventa", T1 commit, T2 commit
očekuje IntegrityError, finalno tačno 1 red) kao dokumentaciju namjere i
zaštitu od budućih izmjena koje bi mogle oslabiti DB zaštitu.
```

```text
F2 — LOW
Nema automatizovanog testa za direktan sekvencijalni servisni retry

Dokaz: nijedan postojeći test ne poziva
append_implementation_completed_from_report(SAME report_id) dva puta
direktno (izvan Phase 2 ALREADY_INGESTED putanje). Nezavisno potvrđeno ispravnim
u ovom review-u ad-hoc probom (probe_ledger_idempotency.py, dio A) — isti
event ID vraćen, bez duplikata.

Preporuka: dodati mali test koji poziva servisnu metodu dva puta zaredom nad
istim već-komitovanim report_id i provjerava da se vraća isti event bez novog
reda.
```

```text
F3 — LOW
Analysis-preporučeni DB CHECK constraint-i (event_type/source_kind/
idempotency_key != '') nisu implementirani

Dokaz: vidi odjeljak 3. Migracija ne sadrži CheckConstraint iako je analysis
report eksplicitno predložio ove tri provjere.

Posljedica: Nije exploitable danas jer je WorkflowLedgerService jedini writer
i uvijek popunjava stvarne (ne-prazne) vrijednosti. Isti tip odstupanja kao u
prethodnim fazama (npr. Phase 2 work_status CHECK je naknadno dodat na
zahtjev review-a) — jeftino za dodati kasnije bez rizika po postojeće
podatke.

Preporuka: dodati u budućoj migraciji prije nego Ledger postane šire korišten
read model.
```

Ostali pregledani testovi (qualification matrica, A-B-A, multi-task, direct
PlanItem, drift, multiple snapshots, transaction rollback, legacy report,
SessionCompletion nova semantika) su svi genuini — koriste stvaran ORM,
stvarne SQLite constraints, stvarne `AgentReportBindingLink`/
`SessionTaskBinding` redove, stvaran `WorkflowLedgerService` i stvaran
`AgentReportIngestionService`. Mock je korišten samo tamo gdje je ispravno
(prisilno bacanje greške u transaction-boundary testu; eksterne zavisnosti
`GitStateReader`/`VerificationService` u SessionCompletion testovima) — nikad
da sakrije ponašanje koje se navodno dokazuje.

---

# MIGRATION FINDINGS

Nema novih nalaza van F3 (CHECK constraints, LOW, već naveden gore). FK
pravila, unique constraint, indeksi, odsustvo backfill-a, ORM/migracija
usklađenost i linearan Alembic head su svi potvrđeni ispravni.

---

# AUTHORITY FINDINGS

Nema novih nalaza van F4 (LOW, već naveden gore). Authority cutover je
potpun i bez skrivenih puteva. `ReportService.set_verdict()` je potvrđeno
NEDIRAN (fajl nije u diff-u) — poznato, eksplicitno van-scope ograničenje
(NEEDS_WORK/REJECTED i dalje direktno vraća PlanItem u IN_PROGRESS), ispravno
NIJE tretirano kao Phase 3A finding.

---

# KNOWN/INTENTIONAL LIMITATIONS

Sve iz sekcije 15 naloga (odvojeni managed worktree root watcheri,
`session_id: unknown` čeka povezivanje, nema HTTP endpointa, nema custom
folder konfiguracije, nema Workflow Ledger GUI-ja, nema automatskog zaključka
o završetku taska, nema EvidenceService migracije, nema SessionCompletionService
wiring ka YAML ingestionu) — potvrđeno da nijedno nije slučajno implementirano
niti predstavlja regresiju postojeće funkcionalnosti.

`ReportService.set_verdict()` PlanItem→IN_PROGRESS authority dug — potvrđeno
netaknut, eksplicitno označen kao sljedeći cutover kandidat, ispravno van
Phase 3A scope-a.

---

# REPORT QUALITY

Implementacioni i analysis izvještaji imaju stvarne, punjene timestampove
(ne ponoć) i validne `report_id` UUID-ove u front matteru. F3 (nedostajući
CHECK constraint-i) je jedino odstupanje između analize i implementacije, i
navedeno je gore kao LOW finding, ne kritika kvaliteta izvještaja po sebi.

---

# Verdict

```text
ACCEPT
```

```text
Workflow Ledger Phase 3A je spreman za commit.
```

Obrazloženje: Authority cutover u `SessionCompletionService` je potvrđen
potpun i bez skrivenih puteva — grep nad cijelim `src/` potvrđuje da je
uklonjeni blok bio jedini izvor automatske IMPLEMENTED/VERIFIED promocije.
Transaction boundary (report + linkovi + Ledger event u istoj transakciji,
čist rollback pri failure-u) je potvrđen i kodom i postojećim regresionim
testom koji tačno reprodukuje traženi failure scenario. Multi-task, A-B-A
grouping i PlanItem snapshot/drift zaštita su svi potvrđeni stvarnim
(nemockovanim) testovima koji tačno reprodukuju tražene scenarije, uključujući
eksplicitnu drift reprodukciju identičnu onoj traženoj u nalogu. FK semantika
je potvrđena na stvarnoj Alembic-migriranoj SQLite bazi, ne samo migracionim
kodom. Idempotency DB zaštita je nezavisno potvrđena ispravnom kroz ad-hoc
probu za oba scenarija koja nisu bila pokrivena postojećim testovima (F1, F2)
— oba su MEDIUM/LOW test-coverage nalazi, ne funkcionalni bugovi, jer je
stvarno ponašanje već dokazano ispravnim u ovom review-u. F3 (nedostajući
CHECK constraint-i) i F4 (result_commit_sha fact-capture nijansa) su LOW i ne
ugrožavaju workflow authority garanciju koja je centralna svrha ove faze.
Nema BLOCKER/HIGH nalaza.

```bash
git status --short
```
