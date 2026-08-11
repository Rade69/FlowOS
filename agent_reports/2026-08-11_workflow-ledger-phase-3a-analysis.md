---
flowos_report_version: 1
report_id: 071a74ea-51f6-4651-9082-b32ffbc98321
agent: codex
model: gpt-5
session_id: unknown
report_type: analysis
tasks:
  - unassigned
commits: []
created_at: 2026-08-11T18:29:44.9112998+02:00
---

# FlowOS — Workflow Ledger Phase 3A readonly analiza

## Datum

2026-08-11

## Agent / model / sesija

- Agent: Codex
- Model: gpt-5
- Sesija: unknown

## Scope

Read-only arhitektonska analiza za `Workflow Ledger Phase 3A — Authority Cutover + IMPLEMENTATION_COMPLETED`.

Cilj je definisati najmanji stabilan contract prije implementacije:

- šta se mora ukloniti ili promijeniti u `SessionCompletionService`;
- minimalni ORM model za Workflow Ledger;
- prvi backend writer za `IMPLEMENTATION_COMPLETED`;
- idempotency i multi-task/A-B-A pravila;
- transakcioni boundary;
- test plan;
- očekivani fajlovi koji bi se mijenjali u implementacionoj fazi;
- eksplicitni non-goals.

Nije implementiran kod, migracija, parser, API, commit niti Workflow Ledger.

## Task contract / acceptance kriteriji

Acceptance kriteriji za ovu analizu:

- provjeriti stvarni kod, ne pretpostaviti željeni dizajn;
- ne mijenjati postojeći kod;
- napraviti samo ovaj analysis report;
- predložiti samo jedan minimalni ciljni dizajn za Phase 3A;
- jasno razdvojiti činjenice sesije/verifikacije od statusnog authority-ja;
- završiti verdictom `RECOMMENDED PHASE 3A DESIGN`.

## GitNexus impact ili ručni blast radius

GitNexus je korišten za početni kontekst `SessionCompletionService`, ali query indeks je prijavio degradaciju: `FTS indexes missing — keyword search degraded`. Zato je analiza dopunjena direktnim čitanjem source fajlova i testova.

Direktno pregledani blast radius:

- `src/flowos/service/services/sessions/completion.py`
- `src/flowos/service/services/reports/ingestion.py`
- `src/flowos/service/services/reports/service.py`
- `src/flowos/service/services/reports/front_matter.py`
- `src/flowos/service/services/infrastructure/persistence/report_models.py`
- `src/flowos/service/services/infrastructure/persistence/models.py`
- `src/flowos/service/services/infrastructure/persistence/plan_models.py`
- `src/flowos/service/services/verification/service.py`
- `src/flowos/service/composition_root.py`
- `src/flowos/service/services/evidence.py`
- `src/flowos/service/services/sessions/timeline.py`
- relevantni testovi u `tests/unit/test_session_completion.py`, `tests/integration/test_agent_report_ingestion.py`, `tests/integration/test_agent_report_v2.py`, `tests/integration/test_plan_progress_api.py`

Najveći rizik implementacije nije nova tabela, nego authority cutover: postojeći kod i mentalni model još dozvoljavaju da session completion i user verdict direktno mijenjaju `PlanItem.status`.

## Reprodukcija prije izmjene

Nije bugfix reprodukcija nego read-only arhitektonska analiza.

Stvarno stanje koda:

- `SessionCompletionService.complete_session()` završava sesiju, čita Git stanje, zatvara aktivni `SessionTaskBinding`, opcionalno pokreće `scripts/verify.py`, zapisuje `VERIFY_RESULT` u `SessionEvent`, kreira draft `AgentReport`, detektuje `NO_COMMIT`, a zatim automatski mijenja `PlanItem.status`.
- Auto-promocija u `IMPLEMENTED` se desi kada postoji rezultat commit različit od base commita ili dirty files i nema blocking critical konflikta.
- Auto-promocija u `VERIFIED` se desi kada `verify.py` prođe i `PlanItem` je već `IMPLEMENTED`.
- `AgentReportIngestionService.ingest_file()` već validira deterministic YAML front matter, stabilni `source_report_id`, `source_path`, `source_content_sha256`, stvarnu `AgentSession` i `SessionTaskBinding` linkove.
- `ReportService.link_report_to_binding()` čuva `resolved_plan_item_id` kao snapshot u `AgentReportBindingLink`.
- `front_matter.py` dozvoljava `report_type` vrijednosti `implementation`, `fix`, `review`, `analysis`; `work_status` vrijednosti `completed`, `partial`, `blocked`; i zahtijeva `work_status` za `implementation` i `fix`.
- `VerificationService` već proizvodi `VerificationResult` i trajni artefakt sa `artifact_id`, `exit_code`, `success`, timestampima i metadata fajlovima, što je dovoljno da budući `TEST_RESULT` koristi isti Ledger model bez nove arhitekture.

## A. Authority cutover u SessionCompletionService

Phase 3A treba ukloniti statusni authority iz `SessionCompletionService`.

Promijeniti:

- ukloniti ili trajno deaktivirati blok `IN_PROGRESS → IMPLEMENTED` koji koristi commit/dirty files kao dokaz implementacije;
- ukloniti ili trajno deaktivirati blok `IMPLEMENTED → VERIFIED` koji koristi `verify.py PASS` kao dokaz verifikacije;
- ukloniti emitovanje `plan_progress.updated` iz completion toka ako više nema stvarne promjene `PlanItem.status`;
- ostaviti zapis stvarnih činjenica: `ended_at`, `exit_code`, `result_commit_sha`, izvedeni `AgentSession.status`, `VERIFY_RESULT` `SessionEvent`, verification WebSocket event, legacy draft report, `NO_COMMIT` conflict detection i resume regeneraciju.

Ne mijenjati značenje:

- commit SHA ostaje dokaz da je commit naveden, ne dokaz da je task implementiran;
- dirty files ostaju Git činjenica, ne dokaz implementacije;
- `verify.py PASS` ostaje test/verification činjenica, ne dokaz da je rad prihvaćen ili finalno verifikovan;
- session status `COMPLETED` ostaje procesni ishod, ne task outcome.

Legacy draft `AgentReport` iz completion servisa može ostati fallback/audit artefakt jer nema `source_report_id`, nema canonical YAML identity, nema `report_type=implementation`, nema `work_status=completed` i nema deterministic `AgentReportBindingLink` iz ingestiona. Phase 3A policy ga ne smije retroaktivno pretvarati u `IMPLEMENTATION_COMPLETED`.

## B. Minimalni Ledger ORM model

Predloženi model: `WorkflowLedgerEvent` u novoj tabeli `workflow_ledger_events`.

Tabela je append-only evidencijski log. Ne zamjenjuje `AgentReport`, `SessionEvent`, `PlanProgressEvent` niti `VerificationResult`; povezuje ih u mašinski čitljiv workflow history.

### Polja

Polje: `id`
Zašto je potrebno: stabilni primarni ključ eventa.
Izvor: aplikativni UUID.
Obavezno/opciono: obavezno, PK.

Polje: `project_id`
Zašto je potrebno: osnovni query scope za Ledger i budući GUI/Workflow prikaz.
Izvor: `AgentSession.project_id` validiran tokom ingestiona.
Obavezno/opciono: obavezno, FK prema `projects.id`. Preporučeno `ondelete=CASCADE`, usklađeno s postojećim projektnim modelom; append-only garancija važi unutar životnog vijeka projekta.

Polje: `event_type`
Zašto je potrebno: jedna tabela mora nositi sadašnji i buduće Ledger evente.
Izvor: backend policy, za Phase 3A samo `IMPLEMENTATION_COMPLETED`.
Obavezno/opciono: obavezno, string. Preporuka je aplikativna enum validacija za poznate vrijednosti: `IMPLEMENTATION_COMPLETED`, `TEST_RESULT`, `REVIEW_COMPLETED`, `FINDING_DECIDED`, `FIX_COMPLETED`, `VERIFICATION_COMPLETED`, `USER_VALIDATION`, `TASK_DECISION`.

Polje: `session_id`
Zašto je potrebno: vezuje event za konkretnu agentsku sesiju koja je proizvela izvorni report.
Izvor: `AgentReport.session_id`.
Obavezno/opciono: obavezno za Phase 3A, FK prema `agent_sessions.id`, preporučeno `ondelete=CASCADE` radi usklađenja sa postojećim cascade semantikama sesije/reporta.

Polje: `task_id`
Zašto je potrebno: čuva konkretni Task kada je report bio vezan za task. Ne smije se izgubiti u korist samog `plan_item_id`.
Izvor: `SessionTaskBinding.task_id` preko `AgentReportBindingLink.session_task_binding_id`.
Obavezno/opciono: opciono, FK prema `tasks.id`, preporučeno `ondelete=RESTRICT` jer `SessionTaskBinding.task_id` već koristi RESTRICT i zato je ovo sigurnije za historijsku atribuciju.

Polje: `plan_item_id`
Zašto je potrebno: povezuje event sa plan stavkom za plan/ledger prikaze i kasniji status projection.
Izvor: primarno `AgentReportBindingLink.resolved_plan_item_id`; fallback samo ako event target direktno dolazi iz `SessionTaskBinding.plan_item_id`.
Obavezno/opciono: opciono, FK prema `plan_items.id`, preporučeno `ondelete=RESTRICT`, usklađeno sa `SessionTaskBinding.plan_item_id` i `AgentReportBindingLink.resolved_plan_item_id`.

Polje: `source_kind`
Zašto je potrebno: omogućava da jedna tabela kasnije nosi evente iz reporta, verification artefakta ili korisničke odluke bez nove arhitekture.
Izvor: backend writer. Za Phase 3A vrijednost je `agent_report`.
Obavezno/opciono: obavezno.

Polje: `source_id`
Zašto je potrebno: identitet izvornog artefakta iz kojeg je event deterministički izveden.
Izvor: za Phase 3A `AgentReport.id`.
Obavezno/opciono: obavezno. Preporuka: ne praviti polymorphic FK na DB nivou; servis mora validirati da `source_kind=agent_report` pokazuje na postojeći `AgentReport`. Time se izbjegava krhki FK dizajn kada dođu `TEST_RESULT` i korisničke odluke.

Polje: `occurred_at`
Zašto je potrebno: vrijeme događaja u workflow smislu, stabilno i nezavisno od retry-ja.
Izvor: za Phase 3A `AgentReport.created_at` iz DB ingestiona; ako se kasnije sačuva authored YAML `created_at`, može ići u payload, ali Ledger event treba ostati vezan za backend-validated ingestion trenutak.
Obavezno/opciono: obavezno.

Polje: `recorded_at`
Zašto je potrebno: vrijeme kada je Ledger red zapisan.
Izvor: backend UTC timestamp u momentu append-a.
Obavezno/opciono: obavezno.

Polje: `idempotency_key`
Zašto je potrebno: sprečava dupli append istog logičkog eventa iz istog izvora, nezavisno od AgentReport ingestion idempotency-ja.
Izvor: deterministički string iz backend policy-ja.
Obavezno/opciono: obavezno, unique.

Polje: `payload_json`
Zašto je potrebno: čuva event-specific snapshot bez migracije za svaku novu vrstu eventa.
Izvor: backend policy. Za Phase 3A minimalno: `source_report_id`, `source_path`, `source_content_sha256`, `report_type`, `work_status`, `binding_link_ids`, `session_task_binding_ids`, `target_kind`, `target_id`, i po potrebi `plan_item_id`.
Obavezno/opciono: obavezno, JSON object kao text, default `{}`.

### Constraints i indeksi

Minimalno:

- PK: `id`
- unique: `idempotency_key`
- index: `(project_id, recorded_at)`
- index: `(project_id, event_type, recorded_at)`
- index: `(session_id, recorded_at)`
- index: `(task_id, recorded_at)`
- index: `(plan_item_id, recorded_at)`
- index: `(source_kind, source_id)`
- check: `event_type != ''`
- check: `source_kind != ''`
- check: `idempotency_key != ''`

Ne preporučujem CHECK constraint koji zaključava cijelu buduću enum listu na DB nivou. Aplikativna validacija je dovoljna za Phase 3A i manje remeti buduće dodavanje event tipova.

## C. Prvi writer: IMPLEMENTATION_COMPLETED

Prvi writer treba biti backend policy servis pozvan iz `AgentReportIngestionService` nakon što postoje:

- validan DB `AgentReport`;
- validna `AgentSession`;
- validni `AgentReportBindingLink` redovi;
- validni `SessionTaskBinding` segmenti.

Predloženi servis:

- `WorkflowLedgerService.append_implementation_completed_from_report(report_id)` ili
- `AgentReportWorkflowPolicy.append_events_for_ingested_report(report)`.

Policy za Phase 3A:

- `report.report_type == "implementation"`
- `report.work_status == "completed"`
- `report.source_report_id IS NOT NULL`
- `report.source_path IS NOT NULL`
- report mora imati najmanje jedan `AgentReportBindingLink`
- svaki link mora pokazivati na stvarni `SessionTaskBinding`
- ne emitovati event za `tasks: unassigned`
- ne emitovati event za `NEEDS_LINK`
- ne emitovati event za legacy report bez front mattera
- ne emitovati event za `analysis`, `review`, `fix`
- ne emitovati event za `partial` ili `blocked`

Značenje eventa:

`IMPLEMENTATION_COMPLETED` znači samo: implementer je kroz canonical ingested YAML report deklarisao završenu implementacionu jedinicu za konkretni target.

Ne znači:

- testovi su prošli;
- reviewer je prihvatio;
- korisnik je prihvatio;
- PlanItem smije automatski postati `IMPLEMENTED`;
- task je završen.

## D. Multi-task i A-B-A pravilo

Pravilo: jedan Ledger event po logičkom targetu u jednom reportu, ne po binding segmentu.

Target grouping:

- ako binding ima `task_id`, logički target je `task:{task_id}`;
- ako binding nema `task_id`, ali ima direktni ili resolved `plan_item_id`, logički target je `plan_item:{plan_item_id}`;
- ne miješati `task:{id}` i `plan_item:{id}` u isti target jer bi se izgubila precizna Task atribucija;
- ako isti task ima više binding segmenata u istom reportu zbog A-B-A toka, emitovati jedan `IMPLEMENTATION_COMPLETED` event za taj task;
- payload mora sadržati sve `AgentReportBindingLink.id` i `SessionTaskBinding.id` vrijednosti koje su grupisane u taj event, sortirane stabilno;
- za report koji pokriva dva različita taska emitovati dva eventa;
- za report koji pokriva dva različita plan item targeta emitovati dva eventa.

Ovo čuva postojeću mogućnost da jedan Markdown report pokriva više taskova bez uvođenja jednog `task_id` polja koje bi gubilo podatke.

## E. Idempotency key

Idempotency key mora biti nezavisan od AgentReport source identity unique constrainta.

Preporučeni format:

```text
workflow-ledger:v1:IMPLEMENTATION_COMPLETED:agent_report:{agent_report_id}:{target_kind}:{target_id}
```

Primjeri:

```text
workflow-ledger:v1:IMPLEMENTATION_COMPLETED:agent_report:rep-123:task:task-456
workflow-ledger:v1:IMPLEMENTATION_COMPLETED:agent_report:rep-123:plan_item:item-789
```

Zašto DB `AgentReport.id`, a ne filesystem path:

- `AgentReport.id` je stabilan nakon deterministic ingestiona;
- `source_report_id` i `source_path` već imaju vlastite unique/index guardove;
- `AgentReport.id` razdvaja Ledger idempotency od immutable Markdown identity-ja;
- payload i source fields i dalje čuvaju originalni YAML `report_id`, `source_path` i content hash.

Ako ingestion bude retry-ovan i report je već ingested, Phase 3A policy može sigurno pokušati append opet: unique `idempotency_key` vraća postojeći event ili no-op.

## F. Transaction boundary

Preporučeni boundary:

1. `AgentReportIngestionService.ingest_file()` validira front matter i source identity.
2. Kreira `AgentReport`.
3. Kreira `AgentReportBindingLink` redove.
4. Flush.
5. Poziva backend Workflow Ledger policy za `IMPLEMENTATION_COMPLETED`.
6. Policy appenduje Ledger evente ili radi no-op.
7. Caller radi postojeći `db.commit()`.

To znači:

- watcher ne sadrži workflow business logiku;
- startup scan i watcher koriste isti ingestion path;
- `AgentReport`, binding linkovi i ledger eventi ulaze u isti DB commit kada je moguće;
- ako ledger append padne, pada cijeli ingestion commit i nema stanja “report ingested, ledger izgubljen”;
- ako unique idempotency uhvati duplikat, to nije failure nego no-op.

Postojeći watcher prvo commit-uje `FileActivity`, pa zatim radi ingestion u odvojenom commit-u. To je prihvatljivo: FileActivity je audit o filesystem događaju; workflow state počinje tek u ingestion transakciji.

## G. Test plan

Minimalni Phase 3A testovi:

1. `SessionCompletionService` više ne mijenja `PlanItem.status` u `IMPLEMENTED` kada postoji commit.
2. `SessionCompletionService` više ne mijenja `PlanItem.status` u `IMPLEMENTED` kada postoje dirty files bez commita.
3. `SessionCompletionService` više ne mijenja `PlanItem.status` u `VERIFIED` kada `verify.py` prođe.
4. `SessionCompletionService` i dalje zapisuje session end facts: `ended_at`, `exit_code`, `result_commit_sha`, `AgentSession.status`.
5. `SessionCompletionService` i dalje kreira `VERIFY_RESULT` `SessionEvent` kada postoji `verify.py`.
6. `SessionCompletionService` i dalje kreira legacy draft `AgentReport`, ali taj report ne emituje `IMPLEMENTATION_COMPLETED`.
7. Ingested report `report_type=implementation`, `work_status=completed`, validna sesija, jedan task binding: kreira jedan `WorkflowLedgerEvent`.
8. Isti report re-ingested: ne kreira drugi event.
9. Isti report sa A-B-A binding segmentima za isti task: kreira jedan event, payload sadrži sve relevantne linkove/bindinge.
10. Jedan report sa dva task targeta: kreira dva eventa.
11. Jedan report sa `tasks: unassigned`: ne kreira event.
12. `report_type=analysis`, `review`, ili `fix`: ne kreira `IMPLEMENTATION_COMPLETED`.
13. `work_status=partial` ili `blocked`: ne kreira event.
14. `NEEDS_LINK` ingestion outcome: ne kreira event.
15. Legacy report bez `source_report_id`: ne kreira event.
16. `resolved_plan_item_id` iz `AgentReportBindingLink` se koristi kao snapshot; ne čitati live `Task.plan_item_id` kao historical authority kada snapshot postoji.
17. Unique `idempotency_key` sprečava dupli append i pri direktnom servisnom retry-ju.
18. Transaction rollback test: ako ledger append digne grešku poslije report/link flush-a, nema ni reporta ni ledger eventa nakon rollback-a.

Test fajlovi koji će vjerovatno trebati:

- novi `tests/integration/test_workflow_ledger_phase3a.py`;
- dopuna `tests/unit/test_session_completion.py`;
- dopuna `tests/integration/test_agent_report_ingestion.py`;
- po potrebi dopuna DB migration smoke testova ako postoje.

## H. Očekivani fajlovi za implementacionu fazu

Očekivani minimalni implementation diff:

- novi ORM model, npr. `src/flowos/service/services/infrastructure/persistence/workflow_ledger_models.py`;
- import modela u persistence init/import path koji Alembic koristi;
- nova Alembic migracija za `workflow_ledger_events`;
- novi servis, npr. `src/flowos/service/services/workflow/ledger.py`;
- mali policy/wiring dodatak u `src/flowos/service/services/reports/ingestion.py`;
- authority cutover u `src/flowos/service/services/sessions/completion.py`;
- relevantni testovi.

Nije neophodan HTTP API u Phase 3A. Dovoljan je service/query layer i DB zapis. HTTP/GUI read model može doći poslije kada postoje i `TEST_RESULT`/review/user decision eventovi.

## I. Eksplicitni non-goals za Phase 3A

Ne implementirati:

- automatsku promjenu `PlanItem.status` iz Ledger eventa;
- `TEST_RESULT`;
- `REVIEW_COMPLETED`;
- `FINDING_DECIDED`;
- `FIX_COMPLETED`;
- `VERIFICATION_COMPLETED`;
- `USER_VALIDATION`;
- `TASK_DECISION`;
- HTTP rute za Ledger osim ako implementation review naknadno traži najtanji read endpoint;
- GUI prikaz Ledgera;
- YAML parser izmjene;
- backfill starih reportova;
- LLM zaključivanje `work_status`;
- watcher business policy;
- queue/broker/retry engine;
- treći report sistem;
- promjenu `PlanProgressService` tranzicionog modela osim uklanjanja automatskog poziva iz completion toka.

## Posebna napomena o ReportService verdict toku

`ReportService.set_verdict()` trenutno direktno vraća povezane `PlanItem` zapise u `IN_PROGRESS` za `NEEDS_WORK` i `REJECTED`. To nije dio prvog `IMPLEMENTATION_COMPLETED` writer-a, ali jeste isti tip authority problema.

Preporuka:

- Phase 3A može ostaviti ovaj tok netaknut ako scope mora ostati minimalan;
- report treba označiti da je to sljedeći cutover kandidat za budući `USER_VALIDATION` ili `TASK_DECISION` event;
- ne miješati ga u prvi Phase 3A commit da se ne proširi blast radius.

## Kako VerificationService kasnije ulazi u isti model

`VerificationService` već vraća `VerificationResult` sa:

- `artifact_id`;
- `verify_path`;
- `exit_code`;
- `success`;
- `timed_out`;
- `verified_at`;
- `artifact_path`.

Budući `TEST_RESULT` može koristiti isti `WorkflowLedgerEvent` model:

- `event_type = TEST_RESULT`;
- `source_kind = verification_artifact`;
- `source_id = artifact_id`;
- `session_id = VerificationResult session_id ako je poznat`;
- `payload_json` sa exit code, success, path, duration, hashes i artifact path.

Zato Phase 3A ne treba dodatna verification tabela.

## Rizici i ograničenja

- GitNexus indeks je bio degradiran za query, pa je analiza oslonjena na direktni source pregled.
- Ako se u Phase 3A koristi `ondelete=RESTRICT` za `task_id`/`plan_item_id`, treba testirati postojeće delete tokove, ali taj izbor je usklađen sa `SessionTaskBinding` i bolji za historijski evidence.
- Ako se `WorkflowLedgerEvent.session_id` veže `CASCADE`, brisanje sesije briše i Ledger evente. To je usklađeno s postojećim `AgentReport`/`SessionEvent` ponašanjem, ali nije apsolutno append-only van životnog vijeka sesije/projekta.
- Ako proizvod želi “nikad ne briši ledger evente čak ni pri brisanju projekta/sesije”, treba poseban retention/soft-delete policy. To je veće od Phase 3A.

## Odbačene opcije

Opcija: koristiti postojeći `PlanProgressEvent` kao Workflow Ledger.
Zašto odbačeno: `PlanProgressEvent` je vezan za status tranzicije PlanItem-a; Phase 3A eksplicitno ne smije automatski mijenjati PlanItem status.
Kada ponovo otvoriti: ako se kasnije napravi projection sloj koji iz Ledgera generiše statusne događaje, ali ne kao source of truth za sve workflow evente.

Opcija: dodati jedno `task_id` polje na `AgentReport`.
Zašto odbačeno: jedan Markdown report može pokriti više taskova i A-B-A segmenata; jedno polje bi izgubilo postojeću multi-binding semantiku.
Kada ponovo otvoriti: ne preporučuje se; multi-target link tabela već postoji.

Opcija: append Ledger evente u watcher callback-u.
Zašto odbačeno: watcher smije detektovati filesystem događaj, ali ne treba sadržati workflow business policy.
Kada ponovo otvoriti: ne preporučuje se; watcher neka ostane samo trigger za ingestion.

Opcija: izvoditi `IMPLEMENTATION_COMPLETED` iz commit SHA, dirty files ili verify PASS.
Zašto odbačeno: upravo to je authority bug koji Phase 3A ispravlja.
Kada ponovo otvoriti: ne otvarati bez eksplicitne promjene workflow semantics.

Opcija: DB CHECK constraint sa svim budućim event tipovima.
Zašto odbačeno: lista poznatih eventa postoji, ali aplikativna validacija je manje remetilačka i ne traži migraciju za svaki novi tip.
Kada ponovo otvoriti: ako se uvede stroga centralna enum migraciona politika.

## Konflikti/kontradiktorni izvori

Nema kontradikcije u user zahtjevu. Postoji kontradikcija u trenutnom sistemu:

- AgentReport v2 ingestion već uspostavlja deterministic authority iz Markdown front mattera;
- `SessionCompletionService` i dalje izvodi PlanItem status iz procesnih/Git/test činjenica.

Phase 3A treba riješiti upravo taj preostali authority split.

## Commitovi

Nema novih commitova u ovoj analizi.

Kontekst koji je naveden u zadatku:

- `6763bb8586d20ddc0be095fce14aaecdeeca3c7f` — AgentReport v2 Phase 2
- `ca5074d62a6f09baffa41cb369262cf45cc7ae5f` — GitNexus workspace metadata

## Verifikacija i stvarni rezultat

Pokrenuto:

- `git status --short --branch` — početno stanje je bilo čisto: `## main...origin/main`
- read-only GitNexus context za `SessionCompletionService`
- read-only source/test pregled kroz `rg` i `Get-Content`

Nije pokrenuto:

- unit/integration testovi, jer nije mijenjan funkcionalni kod;
- migracije, jer nisu kreirane;
- aplikacija, jer zadatak traži read-only analizu.

## Nezavisna provjera

Nije rađena nezavisna provjera. Ovo je architectural analysis report koji treba biti review-an prije Phase 3A implementacije.

## Pronađeni problemi

1. `SessionCompletionService` je preširok authority: procesni/Git/test signali automatski mijenjaju `PlanItem.status`.
2. `ReportService.set_verdict()` takođe direktno mijenja PlanItem status za NEEDS_WORK/REJECTED; ne treba ga rješavati u prvom Phase 3A cutover-u, ali treba ga označiti za budući Ledger decision flow.
3. `EvidenceService` i dalje bira najnoviji report po sesiji, što je prihvatljivo kao evidence snapshot, ali nije dovoljan kao budući workflow authority.

## Potreban follow-up

Implementirati Phase 3A u zasebnom malom commit-u prema ovom contractu:

1. dodati `WorkflowLedgerEvent` model i migraciju;
2. dodati `WorkflowLedgerService`/policy;
3. povezati policy sa `AgentReportIngestionService`;
4. ukloniti PlanItem auto-promociju iz `SessionCompletionService`;
5. dodati testove iz test plana.

## Potrebna korisnička potvrda

Potrebna je potvrda da Phase 3A prihvata ovaj authority model:

- `SessionCompletionService` više ne mijenja PlanItem status;
- `IMPLEMENTATION_COMPLETED` je Ledger evidence event, ne statusna tranzicija;
- samo canonical ingested `implementation + completed` AgentReport sa validnim bindingima može proizvesti prvi Ledger event.

## Verdict

RECOMMENDED PHASE 3A DESIGN
