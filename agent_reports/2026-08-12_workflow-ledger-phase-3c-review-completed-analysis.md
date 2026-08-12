---
flowos_report_version: 1
report_id: 49dd2216-ecbc-45c4-84df-c60ed1e7f840
agent: codex
model: gpt-5
session_id: unknown
report_type: analysis
tasks:
  - unassigned
commits: []
created_at: 2026-08-12T10:28:15+02:00
---

# Workflow Ledger Phase 3C — REVIEW_COMPLETED — read-only analiza

## Datum

2026-08-12

## Agent / model / sesija

- Agent: codex
- Model: gpt-5
- Sesija: unknown

## Scope

Urađena je read-only arhitektonska analiza za sljedeći Workflow Ledger event:

```text
REVIEW_COMPLETED
```

Kod nije mijenjan. Migracija nije napravljena. `REVIEW_COMPLETED` nije
implementiran. Commit nije napravljen.

Trenutni repo status na početku:

```text
## main...origin/main
```

Relevantni HEAD:

```text
010f841 feat: add workflow ledger test results
58771db feat: add workflow ledger phase 3a
ca5074d chore: update gitnexus workspace metadata
```

Pregledani stvarni fajlovi:

- `src/flowos/service/services/infrastructure/persistence/report_models.py`
- `src/flowos/service/services/reports/service.py`
- `src/flowos/service/services/reports/front_matter.py`
- `src/flowos/service/services/reports/ingestion.py`
- `src/flowos/service/services/workflow/ledger.py`
- `src/flowos/service/services/infrastructure/persistence/workflow_ledger_models.py`
- `src/flowos/service/services/infrastructure/persistence/models.py`
- `src/flowos/service/composition_root.py`
- `src/flowos/shared/contracts/reports.py`
- relevantni testovi za ingestion, report verdict i Workflow Ledger Phase 3A/3B.

GitNexus je provjeren kao pomoćni signal, ali FlowOS indeks je stale 4 commita
iza HEAD-a. Zato je ova analiza zasnovana na stvarnom source kodu.

## Stvarno stanje AgentReport modela

`AgentReport` DB model ima:

- `report_type`: nullable string; canonical ingestion ga popunjava iz YAML-a.
- `work_status`: nullable string; DB check dopušta samo `completed`, `partial`,
  `blocked` ili `NULL`.
- `source_report_id`: nullable string; unique index; canonical YAML `report_id`.
- `source_path`: nullable string; unique index; normalizovana apsolutna putanja
  do `agent_reports/*.md`.
- `source_content_sha256`: nullable string; hash sadržaja Markdown artefakta.
- `session_id`: obavezna FK veza na `AgentSession`.
- `user_verdict`: user/workflow verdict, ne reviewer verdict.
- `status`: `DRAFT`/`FINAL`; trenutno report lifecycle/verdict signal, ne
  `work_status`.

`AgentReportBindingLink` ima:

- `report_id`;
- `session_task_binding_id`;
- `resolved_plan_item_id` kao snapshot plan itema u trenutku linkovanja.

Ovo je isti dokazni model koji već koristi `IMPLEMENTATION_COMPLETED`.

## Stvarno stanje front matter parsera

`AgentReportFrontMatterParser` dozvoljava:

```text
report_type = implementation | fix | review | analysis
work_status = completed | partial | blocked
```

`work_status` je obavezan samo za:

```text
implementation
fix
```

`review` bez `work_status` je eksplicitno validan i testiran u
`tests/unit/test_agent_report_front_matter.py`.

Parser dozvoljava YAML `agent` i `model` kao optional keys, ali ih ne vraća u
`AgentReportFrontMatter` dataclass i ingestion ih ne sprema u DB. Prema
trenutnom kodu, YAML `agent/model` su authored metadata, ne canonical DB
identity.

`created_at` iz YAML-a se validira kao timezone-aware timestamp, ali se ne
sprema u `AgentReport.created_at`. DB `created_at` dolazi iz
`ReportService.create_draft()`, tj. iz backend ingestion vremena.

## Stvarno stanje ingestion toka

`AgentReportIngestionService.ingest_file()` radi:

```text
agent_reports/*.md path filter
↓
read bytes + content sha256
↓
strict YAML front matter parse
↓
source identity/idempotency check
↓
session resolve
↓
tasks resolve → historical SessionTaskBinding ids
↓
ReportService.create_draft(...)
↓
ReportService.link_report_to_binding(...)
↓
WorkflowLedgerService.append_implementation_completed_from_report(report.id)
```

Za `report_type=review` trenutni
`append_implementation_completed_from_report()` radi no-op jer kvalifikuje samo:

```text
report_type == implementation
work_status == completed
source_report_id/path/hash != NULL
session_id != NULL
```

Watcher wiring i startup scan oba koriste isti `AgentReportIngestionService`.
Watcher reaguje na `CREATED`/`MODIFIED` za direktne `agent_reports/*.md`
fajlove, a startup scan prolazi postojeće `agent_reports/*.md` fajlove
sortirano i ingestuje ih istom metodom.

Ne postoji dodatni file-complete marker u watcheru. Immutable source identity
štiti od naknadnog mijenjanja već ingested fajla, ali ne dokazuje da fajl nije
bio djelimično napisan ako je već imao validan front matter. To je opšti
ingestion/write-convention rizik, nije specifičan samo za review.

## Stvarno stanje ReportService.set_verdict()

`ReportService.set_verdict(report_id, verdict, notes)`:

- dozvoljava samo `ACCEPTED`, `NEEDS_WORK`, `REJECTED`;
- dohvata konkretan `AgentReport`;
- pravi audit entry sa `actor: "user"`;
- postavlja `report.user_verdict`;
- postavlja `report.user_notes`;
- postavlja `report.status = "FINAL"`;
- flushuje DB;
- za `NEEDS_WORK` ili `REJECTED` poziva `_reopen_plan_item(report)`;
- `_reopen_plan_item()` koristi `AgentReportBindingLink.resolved_plan_item_id`
  kada linkovi postoje;
- legacy fallback radi samo ako postoji tačno jedan istorijski binding.

`ACCEPTED` ne mijenja PlanItem. `NEEDS_WORK` i `REJECTED` mogu vratiti
`IMPLEMENTED` ili `VERIFIED` PlanItem u `IN_PROGRESS` kroz
`PlanProgressService.validate_transition(..., allow_verdict_reopen=True)`.

Ne postoji production HTTP route koja danas poziva `set_verdict()`; report HTTP
kontroler je stub koji vraća praznu listu. Ipak servis i testovi jasno
pokazuju semantiku: ovo je korisnička/workflow odluka, ne reviewer evidence.

Zaključak: Phase 3C ne smije koristiti postojeći `user_verdict` kao reviewer
outcome za `REVIEW_COMPLETED`.

## Findings model

Nije pronađena `Finding` tabela, structured findings model, service ili API.
Postoji samo tekstualno report polje `found_issues` i Markdown body. Zato
Phase 3C ne smije parsirati nalaze iz body-ja niti uvoditi
`FINDING_DECIDED` shortcut.

## RECOMMENDED PHASE 3C DESIGN

### A. REVIEW_COMPLETED semantics

`REVIEW_COMPLETED` znači:

```text
konkretna reviewer session je predala canonical ingested review report kao
evidence za konkretan dokazivo povezan target
```

Ne znači:

- review je pozitivan;
- findings su prihvaćeni;
- implementacija je ispravna;
- testovi su prošli;
- PlanItem je `VERIFIED`;
- task je `DONE`;
- korisnik je prihvatio rad.

Ovo je evidence event, analogno:

- `IMPLEMENTATION_COMPLETED`: implementer tvrdi završetak;
- `TEST_RESULT`: mašina je izvršila provjeru;
- `REVIEW_COMPLETED`: reviewer je završio pregled i predao review artefakt.

### B. Source qualification

Qualifying source:

```text
canonical ingested AgentReport
report.report_type == "review"
report.source_report_id is not None
report.source_path is not None
report.source_content_sha256 is not None
report.session_id points to valid AgentSession
report has at least one valid AgentReportBindingLink
```

`work_status` ne treba biti uslov za Phase 3C review report zato što trenutni
parser eksplicitno dozvoljava `review` bez `work_status`, a postojeće
immutable review report konvencije u repou već koriste taj oblik. Za review
artefakt, `report_type=review` sam po sebi treba da znači da je reviewer
predao završeni review report.

Rizik djelimičnog file write-a postoji, jer watcher nema file-complete marker.
Ali isti rizik postoji za sve canonical report artefakte i ne treba ga u Phase
3C rješavati novim YAML poljem. Ispravan containment je postojeći immutable
artifact convention: agent piše canonical report tek kada ga završava.

### C. Reviewer identity

Canonical DB identity:

- `WorkflowLedgerEvent.session_id = report.session_id`;
- `AgentSession.agent_type`;
- `AgentSession.model_name`.

Authored metadata:

- YAML `agent`;
- YAML `model`.

Trenutni parser dozvoljava YAML `agent/model`, ali ih ne sprema u DB. Phase 3C
ne smije izmišljati reviewer identity iz Markdown body-ja ili front mattera
koji DB ne čuva. Minimalni payload može snapshotovati:

```json
{
  "reviewer_session_id": "...",
  "reviewer_agent_type": "codex",
  "reviewer_model_name": "gpt-5"
}
```

`reviewer_model_name` je nullable jer `AgentSession.model_name` već jeste
nullable.

### D. Independence semantics

`REVIEW_COMPLETED` treba nastati i kada reviewer nije dokazivo nezavisan.

Scenariji:

- Session A/Codex implementira, Session B/Claude reviewa: event postoji; iz
  Ledger projekcije se može dokazati jaka cross-session/cross-agent
  independence.
- Session A/Codex implementira i kasnije u istoj session piše review: event
  postoji, ali ne smije biti označen kao independent review.
- Ne postoji raniji `IMPLEMENTATION_COMPLETED`, ali canonical review report sa
  validnim target linkovima postoji: event smije nastati jer Ledger bilježi
  review evidence, ne zavisnost od prethodnog implementation eventa.

Independence je zaseban dokazivi atribut/projection, ne uslov za postojanje
`REVIEW_COMPLETED`.

### E. Target attribution

Phase 3C treba koristiti isti dokazani grouping model kao Phase 3A:

```text
jedan REVIEW_COMPLETED event po logičkom targetu
```

Target resolution:

- ako binding ima `task_id`: target je `task:<task_id>`;
- ako nema Task, ali ima `plan_item_id`: target je `plan_item:<plan_item_id>`;
- ako link ima samo `resolved_plan_item_id`: target je
  `plan_item:<resolved_plan_item_id>`;
- ne koristiti live `Task.plan_item_id` kao istorijski authority.

Ovo se može implementirati ponovnim korištenjem postojeće `_build_target_groups`
logike ili malim shared helperom iz `WorkflowLedgerService`, bez novog event
frameworka.

### F. Multi-task / A-B-A

Multi-task report:

```text
1 review report
→ N REVIEW_COMPLETED eventa, po jedan za svaki logički target
```

A-B-A isti Task:

```text
više binding segmenata za isti task
→ jedan REVIEW_COMPLETED event za task
→ payload sadrži sve binding_link_ids i session_task_binding_ids
```

PlanItem snapshot pravilo ostaje kao Phase 3A:

- 1 distinct `resolved_plan_item_id` → event kolona `plan_item_id` dobija taj
  snapshot;
- 0 snapshotova → `plan_item_id = NULL`;
- više različitih snapshotova → `plan_item_id = NULL`, a svi snapshotovi idu u
  payload `resolved_plan_item_ids`.

`tasks: unassigned` treba ingestovati kao AgentReport, ali ne treba praviti
`REVIEW_COMPLETED` event, jer nema dokazivog targeta. Ne praviti ni
session/project-scoped review event u Phase 3C; držati model konzistentan sa
Phase 3A target-scoped Ledger događajima iz AgentReport-a.

### G. Findings boundary

`REVIEW_COMPLETED` znači da je reviewer predao nalaze/evidence u canonical
review reportu. Ne znači da je bilo koji nalaz prihvaćen, odbijen ili
pretvoren u rad.

Ne parsirati:

- `F1 HIGH`;
- `F2 MEDIUM`;
- `FIXES REQUIRED`;
- `ACCEPT`;
- Markdown body sekcije.

Strukturisani findings nisu dio trenutnog modela, pa ne treba uvoditi body
parser/regex kao Phase 3C shortcut.

### H. Existing verdict boundary

Postojeći `ReportService.set_verdict()` je user/workflow decision tok:

```text
ACCEPTED / NEEDS_WORK / REJECTED
actor = user
status = FINAL
NEEDS_WORK / REJECTED → mogu vratiti PlanItem u IN_PROGRESS
```

Phase 3C ga ne smije koristiti kao `REVIEW_COMPLETED` rezultat.

`REVIEW_COMPLETED` ne smije mijenjati `AgentReport.user_verdict`,
`AgentReport.status`, `PlanItem.status` niti `PlanProgressEvent`.

### I. Payload

Minimalni payload:

```json
{
  "source_report_id": "...",
  "source_path": "...",
  "source_content_sha256": "...",
  "report_type": "review",
  "target_kind": "task",
  "target_id": "...",
  "binding_link_ids": ["..."],
  "session_task_binding_ids": ["..."],
  "resolved_plan_item_ids": ["..."],
  "reviewer_session_id": "...",
  "reviewer_agent_type": "codex",
  "reviewer_model_name": "gpt-5"
}
```

Ako target ima Task:

```json
{ "task_id": "..." }
```

Ako ima pouzdan jednoznačan PlanItem snapshot:

```json
{ "plan_item_id": "..." }
```

Ne kopirati Markdown body u Ledger payload. Ne parsirati findings u payload.
Ne koristiti YAML `agent/model` kao DB authority.

### J. Idempotency

Predloženi key:

```text
workflow-ledger:v1:REVIEW_COMPLETED:agent_report:{AgentReport.id}:{target_kind}:{target_id}
```

Ovo je isti format kao Phase 3A, samo sa `REVIEW_COMPLETED` event tipom.
Postojeći DB `UNIQUE(idempotency_key)` je dovoljan. Nova migracija nije
potrebna.

Watcher retry, startup scan i direktni service retry ne prave duplikat jer:

- ingestion je idempotent preko `source_report_id/source_path/hash`;
- Ledger event je idempotent preko target-scoped key-a;
- DB unique constraint je zadnja zaštita.

### K. Transaction boundary

Koristiti isti DB transaction obrazac kao Phase 3A:

```text
canonical review Markdown
↓
AgentReport
↓
AgentReportBindingLink
↓
REVIEW_COMPLETED
↓
isti DB commit
```

Ako `append_review_completed_from_report()` padne za qualifying review report,
ingestion treba rollbackovati AgentReport, linkove i Ledger evente zajedno.
Ne koristiti Phase 3B SAVEPOINT obrazac jer ovdje nema nepovratnog filesystem
artifact write-a između source i Ledger zapisa; sve bitno poslije čitanja
Markdown fajla je DB state.

### L. Migration decision

Nova migracija nije potrebna.

`WorkflowLedgerEvent` već ima:

- `event_type`;
- `project_id`;
- `session_id`;
- `task_id`;
- `plan_item_id`;
- `source_kind`;
- `source_id`;
- `occurred_at`;
- `recorded_at`;
- `idempotency_key`;
- `payload_json`;
- unique constraint na `idempotency_key`.

To je dovoljno za `REVIEW_COMPLETED`.

### M. Test plan

Predloženi Phase 3C testovi:

1. canonical `report_type=review` + validan Task binding → jedan
   `REVIEW_COMPLETED`.
2. Review za dva Task targeta → dva eventa.
3. A-B-A isti Task → jedan event sa svim binding/link id-jevima.
4. Direct PlanItem review → jedan event bez `task_id`.
5. `tasks: unassigned` → AgentReport se ingestuje, nema Ledger eventa.
6. `analysis` report → nema review eventa.
7. `implementation` report → nema review eventa iz review writer-a.
8. `fix` report → nema review eventa.
9. Retry ingestion/service call → nema duplikata.
10. DB unique idempotency constraint odbija duplikat.
11. Snapshot drift: promjena `Task.plan_item_id` poslije linkovanja ne mijenja
    event target snapshot.
12. Više različitih PlanItem snapshotova za isti Task → event
    `plan_item_id=NULL`, svi snapshotovi u payloadu.
13. Session/project cross-link zaštita ostaje ista: cross-project session ne
    ingestuje report.
14. Transaction rollback ako review Ledger append padne.
15. `REVIEW_COMPLETED` ne mijenja `PlanItem.status`.
16. Body `ACCEPT`/`FIXES REQUIRED` ne proizvodi workflow decision.
17. Existing Phase 3A/3B testovi ostaju zeleni.
18. Review bez `work_status` kvalifikuje za `REVIEW_COMPLETED`.

### N. Expected changed files

Minimalni očekivani implementation scope:

```text
src/flowos/service/services/workflow/ledger.py
src/flowos/service/services/reports/ingestion.py
tests/integration/test_workflow_ledger_phase3c.py
agent_reports/2026-08-12_workflow-ledger-phase-3c-review-completed-implementation.md
```

Ne očekuje se promjena:

- Alembic migracija;
- `SessionCompletionService`;
- `VerificationService`;
- `ReportService.set_verdict()`;
- GUI;
- HTTP routes;
- `WorkflowLedgerEvent` ORM model.

Parser/front-matter testovi nisu potrebni osim ako se namjerno mijenja
contract. Preporuka ove analize je da se contract ne mijenja.

### O. Explicit non-goals

Phase 3C ne treba implementirati:

- `FINDING_DECIDED`;
- `FIX_COMPLETED`;
- `VERIFICATION_COMPLETED`;
- `USER_VALIDATION`;
- `TASK_DECISION`;
- GUI;
- notification system;
- LLM parsing review body-ja;
- regex extraction findings;
- automatske task status promjene;
- automatsko prihvatanje;
- review orchestration;
- reviewer scheduling;
- agent availability;
- multi-user;
- queue/broker;
- event-sourcing framework.

### P. Recommended next phase after 3C

Preporučeni sljedeći korak nakon 3C:

```text
authority cutover postojećeg ReportService.set_verdict() toka u Ledger decision event
```

Razlog: structured findings još ne postoje, pa `FINDING_DECIDED` nema stabilan
target model. Postojeći `set_verdict()` već sada direktno mijenja PlanItem
status za `NEEDS_WORK/REJECTED`; to je aktivniji authority dug od parsiranja
review findings. Prije `FINDING_DECIDED` treba odvojiti user/workflow decision
od legacy direct mutation toka.

## Tri eksplicitna odgovora

### 1. Da li `report_type=review` bez `work_status` dovoljno pouzdano znači da je review završen?

Da, za Phase 3C, ali samo kada je report canonical ingested artefakt sa
validnim source identityjem, validnom session vezom i validnim target linkom.

Trenutni parser eksplicitno podržava `review` bez `work_status`, postojeći
repo već ima takve immutable review reportove, a `work_status` je trenutno
implementer/fix completion signal. Ne treba uvoditi novo mandatory polje za
review u Phase 3C.

### 2. Da li `REVIEW_COMPLETED` treba postojati čak i kada reviewer nije dokazivo nezavisan od implementera?

Da. Event treba značiti da je review završen i predat kao evidence, ne da je
nezavisan. Independence treba računati kao zaseban dokazivi projection iz
reviewer sessiona, implementation eventa i agent/session metadata.

### 3. Da li Phase 3C smije koristiti postojeći `ReportService.verdict` ili body `ACCEPT/FIXES REQUIRED` kao workflow odluku?

Ne. `ReportService.set_verdict()` je user/workflow decision tok i danas može
mijenjati PlanItem status. Markdown body `ACCEPT/FIXES REQUIRED` je ljudski
tekst, bez structured parser contracta. Phase 3C smije bilježiti samo
`REVIEW_COMPLETED` evidence, ne workflow odluku.

## Završni verdict

RECOMMENDED PHASE 3C DESIGN: implementirati `REVIEW_COMPLETED` kao target-scoped
Ledger event izveden iz canonical ingested `AgentReport(report_type="review")`,
bez migracije, bez status promjena, bez `ReportService.set_verdict()` i bez
parsiranja Markdown body-ja.
