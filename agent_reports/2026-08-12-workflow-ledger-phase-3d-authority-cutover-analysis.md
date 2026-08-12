---
flowos_report_version: 1
report_id: 1812603f-3285-43b0-80ac-6e605302ac5d
agent: codex
model: gpt-5
session_id: unknown
report_type: analysis
tasks:
  - unassigned
commits: []
created_at: 2026-08-12T15:37:33+02:00
---

# RECOMMENDED PHASE 3D DESIGN

## A. Current state

Repo je na:

```text
3dae174c9873e8fec32925f1b95303958986c278
feat: add workflow ledger review completed
```

Rad je read-only. Kod nije mijenjan, migracija nije pravljena, commit nije
napravljen.

Pregledani izvori:

- `src/flowos/service/services/reports/service.py`
- `src/flowos/service/services/infrastructure/persistence/report_models.py`
- `src/flowos/service/services/workflow/ledger.py`
- `src/flowos/service/services/infrastructure/persistence/workflow_ledger_models.py`
- `src/flowos/service/services/plan_progress.py`
- `src/flowos/shared/contracts/reports.py`
- `src/flowos/shared/enums/report.py`
- `src/flowos/service/services/evidence.py`
- testovi za `set_verdict`, `user_verdict`, `verdict_audit_json`,
  `allow_verdict_reopen`, `NEEDS_WORK`, `REJECTED`, `ACCEPTED`.

GitNexus je dostupan, ali FlowOS indeks je stale 5 commitova iza HEAD-a, pa je
korišten samo kao signal staleness-a, ne kao autoritet.

Stvarno stanje:

- `ReportService.set_verdict()` nema production caller-a u `src/` osim same
  definicije.
- `src/flowos/service/controllers/http/reports.py` je stub i ne poziva
  `set_verdict()`.
- `ReportUpdate` contract i `UserVerdict` enum već poznaju
  `ACCEPTED | NEEDS_WORK | REJECTED`.
- `EvidenceService` čita `AgentReport.user_verdict` kao read-model
  `report_verdict`.

## B. Authority problem

Današnji tok:

```text
ReportService.set_verdict(report_id, verdict, notes)
↓
AgentReport.user_verdict
AgentReport.user_notes
AgentReport.status = FINAL
AgentReport.verdict_audit_json append
↓
NEEDS_WORK / REJECTED
↓
_reopen_plan_item()
↓
PlanProgressService.validate_transition(..., IN_PROGRESS, allow_verdict_reopen=True)
↓
PlanItem → IN_PROGRESS
```

Problem nije samo upis `user_verdict`. Problem je da `ReportService` danas
direktno posjeduje workflow authority i status consequence. Još gore,
`_reopen_plan_item()` hvata sve exceptione interno i samo loguje warning.
Zbog toga `user_verdict/status/verdict_audit_json` mogu ostati upisani čak i
ako se PlanItem consequence nije primijenio.

To je split-brain rizik:

```text
report kaže NEEDS_WORK
ali target PlanItem možda nije vraćen u IN_PROGRESS
```

## C. Event choice

Preporučeni event za Phase 3D:

```text
TASK_DECISION
```

Ne `USER_VALIDATION`.

Razlog: postojeći `set_verdict()` nije mehanička korisnička validacija
funkcionalnosti. On znači korisničku odluku o report/work targetu:

- prihvati ovaj rezultat;
- vrati povezani work target u rad;
- odbaci rezultat.

To je workflow decision nad targetom, ne dokaz da je korisnik ručno testirao
funkcionalnost.

Ne treba uvoditi novi event type. Postojeća zaključana lista već ima
`TASK_DECISION` i on objektivno najbolje izražava ovu semantiku.

## D. Verdict semantics

### ACCEPTED

Buduća semantika:

```text
korisnik prihvata report/work rezultat za dokazivo povezani logical target
```

`ACCEPTED` ne znači automatski:

- Task DONE;
- PlanItem `ACCEPTED`;
- PlanItem `VERIFIED`;
- testovi su prošli.

Postojeći kod potvrđuje da `ACCEPTED` samo postavlja report verdict/status/audit;
ne zove `_reopen_plan_item()` i ne mijenja PlanItem.

### NEEDS_WORK

Buduća semantika:

```text
korisnik odlučuje da povezani work target treba vratiti u rad
```

Današnja deterministic consequence:

```text
ako je povezani PlanItem u IMPLEMENTED ili VERIFIED
→ IN_PROGRESS
```

### REJECTED

Buduća semantika:

```text
korisnik odbija konkretan report/work rezultat za target
```

Danas ima isti status side-effect kao `NEEDS_WORK`: reopen u `IN_PROGRESS` za
`IMPLEMENTED` i `VERIFIED`.

`NEEDS_WORK` i `REJECTED` treba da ostanu različite decision vrijednosti u
Ledgeru, iako dijele istu Phase 3D deterministic consequence. Razlika je
semantička i korisnička; repo nema dokaz da treba uvesti drugačiji status
consequence za `REJECTED`.

## E. TASK_DECISION vs USER_VALIDATION

Granica:

```text
TASK_DECISION
= korisnik donosi workflow odluku o work/report targetu
```

Primjeri:

- `ACCEPTED`;
- `NEEDS_WORK`;
- `REJECTED`.

```text
USER_VALIDATION
= korisnik ručno validira ponašanje/funkcionalnost
```

Primjeri za buduću fazu:

- "ručno sam testirao i radi";
- "ručno sam testirao i ne radi";
- "korisnički scenario nije zadovoljen".

Postojeći `set_verdict()` ima `actor="user"`, ali to ga ne čini
`USER_VALIDATION`. Actor je user; event semantika je task/workflow decision.

## F. Target model

Preporuka:

```text
jedan TASK_DECISION event po logical targetu
```

Isti grouping model kao:

- `IMPLEMENTATION_COMPLETED`;
- `REVIEW_COMPLETED`.

Ako report pokriva Task A i Task B:

```text
set_verdict(report_id, NEEDS_WORK)
→ TASK_DECISION za A
→ TASK_DECISION za B
```

Zašto ne jedan report-level event: budući read model mora moći odgovoriti:

```text
koja je posljednja korisnička odluka za Task X?
```

bez parsiranja report istorije i bez naknadnog razvezivanja multi-target
reporta.

## G. Multi-target / A-B-A

Ako report pokriva:

```text
Task A
Task B
Task A
```

Phase 3D treba emitovati:

```text
1 TASK_DECISION za A
1 TASK_DECISION za B
```

Ne dva eventa za isti Task A u istoj user akciji.

Postojeća `_build_target_groups(report)` u `WorkflowLedgerService` već radi
logical target dedupe po `(target_kind, target_id)` i sakuplja sve
`binding_link_ids`, `session_task_binding_ids` i `resolved_plan_item_ids`.
Treba je ponovo koristiti ili malo generalizovati, bez novog frameworka.

## H. Historical PlanItem attribution

PlanItem attribution mora ostati istorijska:

```text
AgentReportBindingLink.resolved_plan_item_id
```

Ne koristiti:

```text
Task.plan_item_id
```

kao live authority.

Pravila ostaju ista kao Phase 3A/3C:

- ako target direktno ima `plan_item_id`, event kolona `plan_item_id` je taj ID;
- ako target ima Task i tačno jedan distinct `resolved_plan_item_id`,
  event kolona `plan_item_id` dobija taj snapshot;
- ako ima više distinct snapshotova, event kolona `plan_item_id = NULL`, a svi
  snapshotovi idu u payload;
- ako nema snapshotova, `plan_item_id = NULL`.

## I. Unassigned

Preporuka:

```text
unassigned report smije dobiti AgentReport.user_verdict compatibility snapshot,
ali ne proizvodi TASK_DECISION event
```

Ne praviti project/session-scoped decision event u Phase 3D.

Razlog: `TASK_DECISION` mora biti upitljiv po task/plan targetu. Ako report
nema dokaziv target, ne treba izmišljati target. Compatibility polja mogu i
dalje prikazati da je korisnik verdictovao report kao objekat.

## J. Repeated decisions

User decision nije evidence event tipa "jedan source → jedan event".

Legitimna istorija:

```text
10:00 NEEDS_WORK
11:00 ACCEPTED
```

Ledger mora čuvati oba eventa. Projection/current view može reći da je
trenutna odluka `ACCEPTED`, ali history mora ostati append-only.

Zato idempotency ne smije biti:

```text
report_id + target_kind + target_id
```

jer bi to trajno blokiralo kasniju validnu odluku.

## K. Idempotency

Preporučeni identitet jedne user decision akcije:

```text
decision_id
```

To je UUID jedne korisničke command akcije. Može biti generisan backendom ako
caller ne pošalje idempotency key, ali za pouzdan retry API kasnije treba
dozvoliti caller-provided `decision_id` ili `idempotency_key`.

Preporučeni key:

```text
workflow-ledger:v1:TASK_DECISION:user_decision:{decision_id}:{target_kind}:{target_id}
```

Efekat:

- retry iste akcije sa istim `decision_id` → nema duplikata;
- nova odluka na istom reportu/targetu sa novim `decision_id` → novi event;
- multi-target akcija ima jedan `decision_id`, ali po jedan idempotency key po
  targetu.

Postojeći `set_verdict(report_id, verdict, notes)` nema takav identitet. Phase
3D implementation treba minimalno proširiti service contract opcionim
`decision_id: str | None = None` ili uvesti mali decision service koji ga
generiše/validira.

## L. Source identity

Preporuka:

```text
source_kind = "user_decision"
source_id = decision_id
```

Ne:

```text
source_kind = "agent_report"
source_id = report.id
```

Razlog: isti report može kroz vrijeme imati više user decision akcija. Ako je
source report, source identity bi conflatuje report artefakt sa promjenjivom
user decision history.

Report reference ide u payload.

## M. Payload

Minimalni payload po targetu:

```json
{
  "decision_id": "...",
  "decision": "NEEDS_WORK",
  "previous_decision": "ACCEPTED",
  "notes": "kratka korisnička napomena ili null",
  "actor_kind": "user",
  "report_id": "...",
  "source_report_id": "...",
  "source_path": "...",
  "source_content_sha256": "...",
  "target_kind": "task",
  "target_id": "...",
  "binding_link_ids": ["..."],
  "session_task_binding_ids": ["..."],
  "resolved_plan_item_ids": ["..."]
}
```

Ako postoji Task:

```json
{ "task_id": "..." }
```

Ako postoji jednoznačan historical PlanItem:

```json
{ "plan_item_id": "..." }
```

Ne stavljati Markdown body. Ne parsirati findings. `notes` smiju biti u
payloadu jer su user-authored decision rationale, ne raw agent transcript.

## N. Report projection fields

Nakon cutovera:

```text
AgentReport.user_verdict
AgentReport.user_notes
AgentReport.status
```

ne treba da budu canonical authority. Treba da postanu compatibility/latest
projection snapshot za postojeće read modele i UI/API contract.

Preporučena Phase 3D kompatibilnost:

- `user_verdict` = najnovija decision vrijednost za report-level prikaz;
- `user_notes` = najnovije notes;
- `status = FINAL` = report lifecycle signal da je korisnik donio bar jednu
  odluku/verdict na report;
- `updated_at` ostaje projection timestamp.

Canonical decision history je Ledger.

## O. verdict_audit_json

Najbezbjedniji minimalni Phase 3D pristup:

```text
nastaviti appendovati verdict_audit_json radi backward compatibility,
ali ga proglasiti compatibility projectionom, ne authority istorijom
```

Ne brisati ga i ne migrirati u ovoj fazi.

Razlog: postojeći testovi i korisničko iskustvo očekuju audit JSON. Odmah ga
ukloniti bi tražilo širi migration/read-model posao bez koristi za prvi
authority cutover.

Novi canonical history je `WorkflowLedgerEvent(TASK_DECISION)`.

## P. Report status FINAL

`AgentReport.status = FINAL` danas znači report lifecycle/verdict stanje.
Nema production query-ja koji filtrira workflow po `FINAL`. `ReportService`
ga ispisuje u Markdown export, a testovi očekuju da `set_verdict()` iz
`DRAFT` pređe u `FINAL`.

Preporuka:

- `FINAL` može ostati kao compatibility lifecycle signal;
- ne smije biti workflow acceptance signal;
- ne koristiti ga za `TASK_DECISION` projection osim kao "report ima user
  decision/verdict".

## Q. PlanItem consequence

Preporuka za Phase 3D:

```text
decision writer zapisuje TASK_DECISION
zatim sync/local deterministic consequence service primjenjuje PlanItem transition
```

Ne uvoditi async queue/event bus.

Minimalno:

- novi mali `WorkflowDecisionService`, ili
- `ReportService.set_verdict()` kao facade koji delegira na helper u
  `WorkflowLedgerService` i consequence helper.

Preporuka arhitekture:

```text
WorkflowDecisionService
```

jer `ReportService` ne treba više biti authority owner. `ReportService` može
ostati public compatibility entrypoint, ali treba delegirati.

`NEEDS_WORK` i `REJECTED` consequence:

```text
IMPLEMENTED/VERIFIED → IN_PROGRESS
```

`ACCEPTED` consequence:

```text
nema automatskog PlanItem status advance-a
```

Ne praviti `ACCEPTED → DONE`, `ACCEPTED → VERIFIED` niti
`ACCEPTED → PlanItem.ACCEPTED` u Phase 3D.

## R. Transaction boundary

Preporučena atomic boundary:

```text
user decision request
↓
validate report/verdict/targets
↓
append TASK_DECISION evente
↓
update compatibility projection fields
↓
apply deterministic consequence
↓
single DB transaction / commit
```

Ako deterministic consequence ne uspije, preporuka je:

```text
rollbackovati decision event i compatibility fields
```

Zašto ne zadržati decision kao činjenicu? Zato što trenutni lokalni sync model
nema structured "decision accepted but consequence failed" event/projection.
Zadržavanje eventa bez consequence bi formalizovalo split-brain koji Phase 3D
upravo želi ukloniti.

Kada se kasnije uvede durable projector/error event, može se razmotriti
drugačiji model. U Phase 3D minimalni sigurni model je all-or-nothing.

## S. Legacy compatibility

`ReportService.set_verdict()` treba ostati public entrypoint zbog postojećih
testova i budućih API/GUI poziva, ali treba prestati biti authority writer.

Preporučeno:

```text
ReportService.set_verdict(...)
↓ delegira
WorkflowDecisionService.record_report_decision(...)
```

`ReportService` može ostati facade za:

- signature kompatibilnost;
- validaciju stare forme;
- vraćanje ažuriranog `AgentReport`.

Canonical authority i consequences idu kroz decision service + Ledger.

Legacy report fallback:

- privremeno zadržati ponašanje za reporte bez `AgentReportBindingLink` samo
  ako postoji tačno jedan istorijski binding, jer to testovi već očekuju;
- u payloadu jasno označiti fallback, npr. `target_resolution: "legacy_single_binding"`;
- ako nema dokaziv target ili ih ima više, ne praviti `TASK_DECISION`.

## T. Cross-project protection

Koristiti postojeća pravila:

- `ReportService.link_report_to_binding()` već zabranjuje link druge sesije;
- `WorkflowLedgerService._build_target_groups()` vraća no-op ako binding
  ne pripada `report.session_id`;
- `_project_id_for_report()` izvodi project iz `AgentSession`.

Phase 3D testovi moraju pokriti korumpirani cross-session/cross-project link
kao no-op ili rollback, ne kao djelimičan decision.

## U. Test plan

Phase 3D implementation treba testirati:

1. `ACCEPTED` → `TASK_DECISION` event.
2. `NEEDS_WORK` → `TASK_DECISION` event.
3. `REJECTED` → `TASK_DECISION` event.
4. `ACCEPTED` ne auto-advance PlanItem.
5. `NEEDS_WORK` deterministic reopen za `IMPLEMENTED`.
6. `NEEDS_WORK` deterministic reopen za `VERIFIED`.
7. `REJECTED` deterministic reopen za `IMPLEMENTED`.
8. `REJECTED` deterministic reopen za `VERIFIED`.
9. Multi-target report → jedan event po logical targetu.
10. A-B-A dedupe po logical targetu.
11. Historical PlanItem snapshot drift.
12. Više PlanItem snapshotova → event `plan_item_id=NULL`, payload lista.
13. `tasks: unassigned` / unlinked report → compatibility verdict update,
    nema `TASK_DECISION`.
14. Repeated decisions: `NEEDS_WORK → ACCEPTED` ostaju dva Ledger eventa.
15. Retry iste `decision_id` ne pravi duplikat.
16. Nova `decision_id` na istom report/targetu pravi novi event.
17. `notes` snapshot u payloadu.
18. `previous_decision` snapshot u payloadu.
19. Invalid verdict baca grešku i nema mutacije.
20. Cross-project/session corruption protection.
21. Consequence failure rollback: nema Ledger eventa, nema projection updatea.
22. Ne pravi `FINDING_DECIDED`.
23. Ne pravi `USER_VALIDATION`.
24. Ne pravi `ACCEPTED → DONE/VERIFIED/PlanItem.ACCEPTED`.
25. Legacy single-binding fallback ako se zadržava.
26. Legacy multi-binding bez linkova ne mijenja target.
27. Phase 3A/3B/3C regresije ostaju zelene.

Postojeći testovi koje treba očuvati:

- `tests/unit/test_reports.py::test_create_draft`
- `test_set_verdict_with_audit`
- `test_set_verdict_chaining`
- `test_update_report_cannot_change_verdict`
- `test_update_report_cannot_change_verdict_audit_json`
- `test_invalid_verdict_raises`
- contracts testovi za `ReportUpdate.user_verdict`
- EvidenceService read-model test za `report_verdict`.

Testovi koji predstavljaju legacy authority i treba ih prepisati, ne samo
slijepo očuvati:

- AgentReport v2 reopen testovi koji očekuju direktan `ReportService`
  side-effect, naročito multi-binding, snapshot drift, governed reopen i
  legacy fallback. Očekivano ponašanje treba ostati korisnički isto, ali dokaz
  treba uključiti `TASK_DECISION` Ledger event kao canonical authority.

## V. Expected changed files

Minimalni implementation scope:

```text
src/flowos/service/services/reports/service.py
src/flowos/service/services/workflow/ledger.py
src/flowos/service/services/workflow/decisions.py   # samo ako se uvede mali decision service
src/flowos/service/services/workflow/__init__.py    # samo ako treba export
tests/integration/test_workflow_ledger_phase3d.py
tests/unit/test_reports.py
tests/integration/test_agent_report_v2.py
agent_reports/2026-08-12-workflow-ledger-phase-3d-authority-cutover-implementation.md
```

Ne dirati za Phase 3D:

- `SessionCompletionService`;
- `VerificationService`;
- report Markdown parser;
- review ingestion;
- GUI;
- HTTP route, osim ako se kasnije eksplicitno traži API;
- finding parser.

## W. Migration decision

Nova DB migracija nije potrebna.

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
- unique `idempotency_key`.

`decision_id` može biti:

- `source_id`;
- dio `idempotency_key`;
- dio payloada.

Nema potrebe za novom tabelom ili kolonom u minimalnoj Phase 3D fazi.

## X. Explicit non-goals

Phase 3D ne treba raditi:

- `FINDING_DECIDED`;
- `FIX_COMPLETED`;
- `VERIFICATION_COMPLETED`;
- `USER_VALIDATION` implementaciju;
- GUI;
- notifications;
- LLM;
- Markdown finding parsing;
- review orchestration;
- multi-user;
- queue/broker;
- event sourcing framework;
- automatic DONE;
- automatic VERIFIED;
- new planning model.

## Y. Recommended next phase

Nakon Phase 3D:

1. `FINDING_DECIDED` — tek kada postoji structured Finding model ili minimalni
   finding identity contract. Ne parsirati Markdown F1/F2 kao shortcut.
2. `FIX_COMPLETED` — kada fix report/work_status i target mapping može
   zatvoriti konkretan finding ili target.
3. `VERIFICATION_COMPLETED` ili širi verification projection — zavisi od toga
   da li `TEST_RESULT` treba agregirati u korisnički razumljiv validation
   state.
4. `USER_VALIDATION` — za ručne korisničke testove/scenarije, odvojeno od
   task/work decisiona.
5. Task completion/projection work — tek kad postoje
   implementation/review/test/user decision event tokovi dovoljno stabilni.

## Z. Final recommendation

Phase 3D treba pretvoriti `ReportService.set_verdict()` u compatibility facade
nad canonical `TASK_DECISION` Ledger writerom.

Minimalna arhitektura:

```text
ReportService.set_verdict(...)
↓
WorkflowDecisionService.record_report_decision(...)
↓
WorkflowLedgerEvent(event_type="TASK_DECISION")
↓
compatibility projection fields on AgentReport
↓
sync deterministic PlanItem consequence
```

Sve u jednoj DB transakciji. Ako consequence ne može biti primijenjena,
rollbackovati decision event i compatibility polja.

## Eksplicitni odgovori

### 1. Da li set_verdict semantički postaje TASK_DECISION?

Da. Semantički postojeći `set_verdict()` je korisnička workflow odluka nad
report/work targetom. To je `TASK_DECISION`, ne `USER_VALIDATION`.

### 2. Da li AgentReport.user_verdict ostaje authority ili postaje projection?

Postaje projection/compatibility snapshot najnovije odluke. Canonical history
i authority treba biti `WorkflowLedgerEvent(TASK_DECISION)`.

### 3. Da li NEEDS_WORK/REJECTED i dalje smiju direktno mijenjati PlanItem?

Ne direktno iz `ReportService`. Smiju proizvesti isti korisnički vidljiv
consequence (`IMPLEMENTED/VERIFIED → IN_PROGRESS`), ali kroz deterministic
consequence korak poslije canonical `TASK_DECISION` eventa, u istoj transakciji.

### 4. Kako čuvamo više odluka kroz vrijeme?

Svaka user decision akcija dobija novi `decision_id` i proizvodi novi
`TASK_DECISION` event po logical targetu. Projection računa current/latest
decision, ali Ledger čuva punu istoriju.

### 5. Koji je idempotency identitet jedne user decision akcije?

`decision_id` UUID jedne command akcije.

Preporučeni key:

```text
workflow-ledger:v1:TASK_DECISION:user_decision:{decision_id}:{target_kind}:{target_id}
```

### 6. Šta radimo sa unassigned reportom?

Dozvoliti compatibility update `AgentReport.user_verdict/user_notes/status`, ali
ne praviti `TASK_DECISION` jer nema dokaziv target. Ne izmišljati
project/session-scoped task decision u Phase 3D.

### 7. Da li je potrebna DB migracija?

Ne. Postojeća `workflow_ledger_events` šema može nositi `TASK_DECISION` preko
`event_type`, target kolona, `source_kind/source_id`, `idempotency_key` i
`payload_json`.
