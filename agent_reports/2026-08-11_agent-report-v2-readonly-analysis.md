---
flowos_report_version: 1
agent: codex
model: gpt-5
session_id: unknown
report_type: analysis
tasks:
  - unassigned
commits: []
created_at: 2026-08-11T00:00:00+02:00
---

# AgentReport v2 — read-only arhitektonska analiza

## Scope

Ovo je samo read-only analiza postojećeg `AgentReport` sistema radi pripreme za budući Workflow Ledger.

Nije mijenjan kod. Nije pravljena migracija. Nije napravljen commit. Nije implementiran YAML parser. Nije implementiran Workflow Ledger.

Usvojeni ciljni tok:

```text
Agent
  ↓
agent_reports/*.md
  ↓
deterministički YAML front-matter ingestion
  ↓
DB AgentReport
  ↓
Workflow Ledger
```

Markdown tijelo ostaje čovjeku čitljiv artefakt. Backend ne koristi LLM za zaključivanje `work_status`; Ledger koristi strukturisani DB `AgentReport`.

## Pregledani izvori

- `src/flowos/service/services/infrastructure/persistence/report_models.py`
- `src/flowos/service/services/reports/service.py`
- `src/flowos/service/services/sessions/completion.py`
- `src/flowos/service/controllers/http/reports.py`
- `src/flowos/service/controllers/http/sessions.py`
- `src/flowos/service/services/sessions/bindings.py`
- `src/flowos/service/services/infrastructure/persistence/models.py`
- `src/flowos/service/services/sessions/timeline.py`
- `src/flowos/service/services/evidence.py`
- `src/flowos/shared/contracts/reports.py`
- `alembic/versions/96aa6257d45c_add_phase3_tables.py`
- `alembic/versions/9b2d1f7a4c63_session_task_bindings.py`
- `tests/unit/test_reports.py`
- `tests/unit/test_session_completion.py`
- `tests/unit/test_evidence.py`
- `tests/integration/test_e2e_phase3.py`
- `tests/integration/test_session_task_bindings.py`
- `CLAUDE.md`, `AGENTS.md`, postojeći `agent_reports/*.md`

## 1. Trenutna DB šema `AgentReport`

ORM klasa je `AgentReport` u tabeli `agent_reports`.

Trenutna polja:

- `id`: `String(36)`, primary key, UUID default.
- `session_id`: `String(36)`, `ForeignKey("agent_sessions.id", ondelete="CASCADE")`, `nullable=False`.
- `agent_job_id`: `String(36)`, nullable.
- `status`: `String(20)`, `nullable=False`, default `DRAFT`; komentar navodi `DRAFT, FINAL`.
- sadržajne tekstualne sekcije:
  - `scope`
  - `impact_summary`
  - `reproduction_summary`
  - `context_used`
  - `summary`
  - `rationale`
  - `implementation_summary`
  - `untouched_scope`
  - `verification_summary`
  - `independent_review_summary`
  - `found_issues`
  - `rejected_options`
  - `conflicting_sources`
- JSON-as-text reference:
  - `commit_shas_json`
  - `changed_files_json`
- rizici/follow-up:
  - `open_risks`
  - `follow_up`
- korisnička potvrda/verdict:
  - `user_confirmation_required`: boolean, default false.
  - `user_verdict`: `String(20)`, nullable; komentar navodi `ACCEPTED, NEEDS_WORK, REJECTED`.
  - `user_notes`: text, nullable.
  - `verdict_audit_json`: text, nullable; JSON lista audit zapisa.
- timestamps:
  - `created_at`: timezone `DateTime`, not null, default UTC now.
  - `updated_at`: timezone `DateTime`, nullable, `onupdate` UTC now.

Indeksi:

- `ix_agent_reports_session_id`
- `ix_agent_reports_status`

Nema unique constraint nad `session_id`. Nema `source_path`, `source_hash`, `report_type`, `work_status`, `session_task_binding_id`, niti normalizovanu vezu na više taskova.

## 2. Kada i gdje se trenutno kreira

Postoje dva realna načina kreiranja DB reporta:

1. `ReportService.create_draft(...)`
   - javna servisna metoda;
   - kreira `AgentReport(status="DRAFT")`;
   - popunjava `session_id`, opcionalni `agent_job_id`, `scope`, `summary`, `commit_shas_json`, `changed_files_json`, `verification_summary`, `open_risks`, `created_at`;
   - poziva `self._session.add(report)` i `flush()`.

2. `SessionCompletionService.complete_session(...)`
   - nakon završetka sesije, Git čitanja, opcione verifikacije i status derivacije;
   - poziva `ReportService(self._db).create_draft(...)`;
   - summary je automatski tekst tipa `Sesija završena. Exit code: ...`;
   - commit lista sadrži samo `result_commit_sha` ako postoji;
   - verification summary uključuje `Git verification: OK/NOT_VERIFIED` i eventualni verify sažetak;
   - nakon toga emituje `report.created` WebSocket događaj.

E2E test `tests/integration/test_e2e_phase3.py` takođe direktno koristi `ReportService.create_draft()` za dodatni report u test toku.

HTTP `reports.py` trenutno ne kreira DB report; ruta `GET /reports` je stub koji vraća praznu listu.

## 3. Da li sistem pretpostavlja `1 session = 1 report`

DB šema ne pretpostavlja `1 session = 1 report`: nema unique constraint nad `session_id`, a `ReportService.list_reports(session_id=...)` vraća listu.

Servisni i read-model kod djelimično operišu kao da je najnoviji report glavni:

- `ReportService.get_report_for_session(session_id)` vraća najnoviji report po `created_at desc`.
- `EvidenceService.build(plan_item_id)` uzima najnoviji report za primarnu sesiju.
- `TimelineService.get_timeline(...)` uzima sve reportove za sesiju i za svaki report sa `verification_summary` dodaje timeline event.

Zaključak: sistem već može imati više reportova po sesiji na nivou baze i timelinea, ali postoje potrošači koji semantički biraju “najnoviji report” kao reprezentativan.

## 4. Šta bi se pokvarilo ako jedna session ima više reportova

Ne bi se pokvarila baza, jer nema unique constrainta.

Potencijalni problemi su semantički:

- `EvidenceService.build(...)` bi prikazao samo najnoviji report/verdict za primarnu sesiju. Ako postoje npr. `analysis`, `review`, `fix` i `handoff` reportovi, najnoviji možda nije report koji nosi relevantan acceptance verdict.
- `ReportService.get_report_for_session(...)` naziv sugeriše singularan report, iako vraća najnoviji.
- `ReportService.set_verdict(...)` radi nad konkretnim report ID-jem, ali `_reopen_plan_item()` koristi `report.session_id → AgentSession.plan_item_id`; kod ne zna da li je verdict dat na report koji se odnosi na raniji task binding segment ili samo na najnoviji legacy `plan_item_id`.
- `TimelineService` će prikazati više `REPORT_VERIFY_SUMMARY` eventova ako više reportova ima `verification_summary`; to je tehnički ispravno, ali može napraviti šum.
- GUI prikaz reporta je trenutno slab/indirektan; `src/flowos/gui/views/pages.py` koristi dict polje `verdict` sa fallbackom `DRAFT`, ali backend report route je stub, pa stvarni UI contract nije stabilan.

Najveći rizik nije kardinalitet `session → reports`, nego nedostatak identiteta i tipa reporta. Bez `report_type` i artifact identity, “najnoviji” postaje slučajan autoritet.

## 5. Ko koristi `status=DRAFT/FINAL`

Upotreba:

- `ReportService.create_draft()` uvijek postavlja `status="DRAFT"`.
- `ReportService.set_verdict()` postavlja `status="FINAL"`.
- `ReportService.update_report()` izričito zabranjuje promjenu `status`.
- `ReportService.to_markdown()` ispisuje status.
- `tests/unit/test_reports.py` provjerava da je create draft `DRAFT` i verdict update `FINAL`.
- `tests/integration/test_e2e_phase3.py` provjerava da ručno kreirani report ima `DRAFT`.
- `AgentReport` ORM ima indeks `ix_agent_reports_status`.

Nema pronađenog production koda koji filtrira samo `FINAL` ili samo `DRAFT`. Status je trenutno lifecycle/verdict signal, ne ingestion/work status.

## 6. Ko koristi `user_verdict`

Upotreba:

- `ReportService.set_verdict()` validira `ACCEPTED | NEEDS_WORK | REJECTED`, piše audit i postavlja `status="FINAL"`.
- `ReportService.update_report()` zabranjuje direktnu promjenu `user_verdict`, `user_notes`, `verdict_audit_json`.
- `ReportService._reopen_plan_item()` za `NEEDS_WORK` i `REJECTED` pokušava vratiti `PlanItem` u `IN_PROGRESS`.
- `ReportService.to_markdown()` ispisuje verdict.
- `EvidenceService.build()` iz najnovijeg reporta za sesiju čita `report.user_verdict`.
- `src/flowos/shared/contracts/reports.py` validira `ReportUpdate.user_verdict` kroz `UserVerdict`.
- `tests/unit/test_reports.py`, `tests/unit/test_contracts.py` i `tests/unit/test_evidence.py` eksplicitno provjeravaju `user_verdict`.

Važno: `_reopen_plan_item()` danas koristi `AgentSession.plan_item_id`, ne historijski binding. Ako report pripada ranijem binding segmentu, ovaj mehanizam može pogoditi pogrešan plan item.

## 7. Da li postoji unique constraint koji sprečava više reportova po sessionu

Ne. Postoji samo ne-unique indeks `ix_agent_reports_session_id`.

Migracija `96aa6257d45c_add_phase3_tables.py` takođe kreira samo ne-unique indeks nad `session_id`; nema `UniqueConstraint`.

## 8. Kako `SessionCompletionService` kreira report

`SessionCompletionService.complete_session()`:

1. učita `AgentSession`;
2. očita Git stanje;
3. postavi `ended_at`, `exit_code`, zatvori aktivni `SessionTaskBinding`;
4. pokrene `scripts/verify.py` ako postoji;
5. izvede `session.status`;
6. pozove `ReportService.create_draft(...)`;
7. emituje `report.created`;
8. nastavi NO_COMMIT detekciju, plan progress tranzicije, resume regeneraciju i commit DB transakcije.

Automatski report nije filesystem artifact i ne zapisuje se u `agent_reports/*.md`. On je DB draft sa sažetkom završetka sesije.

## 9. Šta uraditi s automatskim reportom na end-session

Najmanje remetilački put nije odmah ukloniti automatski report.

Sigurna evolucija:

1. Uvesti ingestion report kao primarni izvor za Workflow Ledger.
2. Automatski completion report pretvoriti u jasno označen fallback tip, npr. `report_type="completion_fallback"` ili `source_kind="AUTO_COMPLETION"`.
3. Ledger koristi ingestovane YAML reportove kada postoje za istu session/artifact/task vezu.
4. Automatski report ostaje kao minimalni tehnički dokaz završetka samo kad nema human/agent Markdown reporta.

Uklanjanje automatskog reporta odmah bi lomilo postojeće testove i timeline/evidence očekivanja:

- `tests/unit/test_session_completion.py` očekuje da završetak sesije kreira report.
- `tests/integration/test_e2e_phase3.py` očekuje `AgentReport` kao timeline origin.
- `EvidenceService` se oslanja na report/verdict kao dio evidence bundlea.

Zaključak: bezbjednije je prilagoditi ga novom ingest modelu kao fallback nego ga odmah ukloniti.

## 10. Minimalna nova polja za YAML report reprezentaciju

Predložena lista iz naloga je blizu, ali treba je malo korigovati zbog postojećeg modela i više-task reportova.

Već postoji:

- `session_id`
- `created_at`
- sadržajne sekcije;
- commit i changed files JSON;
- `user_verdict` / `status`.

Stvarno nedostaje:

- `report_type`
- `work_status`
- stabilan artifact identity (`source_path` samo nije dovoljno)
- idempotency/dedupe identitet ili hash
- veza reporta na jedan ili više task/plan/binding targeta
- opcioni `session_task_binding_id` kao snapshot tačnog vremenskog konteksta kada report ima dominantan binding segment

Ne treba dodavati samo jedno `task_id` polje, jer YAML `tasks:` može opisivati više povezanih taskova.

## 11. Kako riješiti YAML `tasks:` za više taskova

Ne koristiti jedno `AgentReport.task_id` polje kao jedini model, jer bi to izgubilo mogućnost jednog reporta za više taskova.

Minimalno ispravan model je many-to-many link tabela, npr. konceptualno:

```text
agent_report_task_links
  id
  report_id
  target_kind      TASK | PLAN_ITEM | UNASSIGNED | EXTERNAL | UNKNOWN
  target_id        nullable, FK kad je poznat lokalni target
  task_key         string iz YAML-a, za unassigned/external/historijske reference
  session_task_binding_id nullable
  role             primary | related | reviewed | blocked_by
```

Za striktni minimum, `role` može biti odgođen, ali `report_id + target_kind + target_id/task_key` treba postojati da Ledger ne izgubi multi-task informaciju.

Ako se želi izbjeći zasebna tabela u prvoj migraciji, može se privremeno koristiti `tasks_json`, ali to je slabije normalizovano i manje pogodno za Ledger upite. Pošto je cilj “normalizovana mašinski čitljiva reprezentacija”, link tabela je bolji minimalni cilj.

## 12. Kako spriječiti dupli ingestion istog Markdown reporta

Samo `source_path` nije dovoljan:

- fajl se može preimenovati;
- path može imati različite separator/case varijante na Windowsu;
- isti report se može kopirati;
- sadržaj se može promijeniti nakon prvog ingestiona.

Minimalni dedupe treba imati:

- `source_path` kao trenutnu lokaciju;
- `source_content_sha256` za sadržaj;
- `source_identity` kao stabilan identitet.

Najbolji deterministički `source_identity`:

1. ako YAML ima eksplicitni `report_id`, koristiti njega;
2. inače deterministički iz `repo identity + normalized relative path + content hash`;
3. za idempotentno re-ingestovanje iste verzije koristiti unique nad `source_content_sha256` ili kombinaciju `source_identity + source_content_sha256`.

Preporuka: unique constraint nad `source_identity` ako je identitet po report artefaktu i update-in-place je dozvoljen; ili nad `(source_identity, source_content_sha256)` ako treba čuvati verzije istog artifacta. Za Workflow Ledger je obično korisnije imati jedan trenutni DB zapis po artifactu i audit/ingestion event za promjene, ali to zavisi od budućeg Ledger retention modela.

## 13. Da li je dovoljan filesystem path

Ne. Filesystem path je potreban za traceability, ali nije dovoljan kao stabilan identity.

Path je:

- lokacijski identitet, ne sadržajni;
- promjenjiv renameom;
- osjetljiv na Windows path normalizaciju;
- nedovoljan za detekciju promjene sadržaja istog fajla.

Minimalno treba:

- `source_path`: čovjeku i alatima vidljiva lokacija;
- `source_content_sha256`: tačan sadržaj ingestovanog artefakta;
- `source_identity`: stabilni logički ID reporta.

## 14. Kako `SessionTaskBinding` pomaže s tačnim task kontekstom u vremenu

`SessionTaskBinding` uvodi historijske segmente:

- `session_id`
- `task_id` ili `plan_item_id` ili unassigned stanje;
- `started_at`
- `ended_at`
- `binding_source`

To omogućava da ingestion uporedi `AgentReport.created_at` iz YAML-a sa binding intervalima iste sesije:

```text
binding.started_at <= report.created_at < binding.ended_at
```

Za aktivni binding:

```text
binding.started_at <= report.created_at AND binding.ended_at IS NULL
```

Ako report ima više `tasks:` u YAML-u, `SessionTaskBinding` može odrediti primarni vremenski kontekst, dok link tabela čuva sve dodatne task veze.

Ovo je bolje od oslanjanja na `AgentSession.task_id` / `plan_item_id`, jer su ta polja legacy compatibility pointeri na trenutno/najnovije stanje, ne historijski dokaz.

## 15. Da li ingest report smije nastati dok je `AgentSession` još aktivna

Da, treba smjeti.

Razlozi:

- agent može pisati `analysis`, `review`, `handoff`, `blocked` ili parcijalni report prije završetka sesije;
- Workflow Ledger mora moći pratiti tok rada, ne samo finalni completion;
- `SessionTaskBinding` već može povezati report sa aktivnim binding segmentom u trenutku `created_at`.

Ograničenja:

- ingestion ne smije automatski zaključivati finalni `work_status` iz slobodnog Markdown tijela;
- `work_status` mora doći iz YAML-a ili iz determinističke mape polja;
- ako je session aktivna, report može biti `DRAFT` ili `IN_PROGRESS` semantikom, ali postojeći `status=DRAFT/FINAL` ne treba miješati sa `work_status`.

## 16. Koji modeli/testovi bi zahtijevali migraciju

Modeli:

- `AgentReport` ORM treba evolutivno proširiti novim poljima.
- Potrebna je nova link tabela za multi-task veze reporta.
- Opciona FK veza na `SessionTaskBinding` treba biti nullable zbog starih reportova i reportova bez jasnog bindinga.

Servisi:

- `ReportService.create_draft()` treba dobiti v2 polja ili imati odvojenu ingest metodu, npr. `ingest_markdown_report(...)`.
- `ReportService.get_report_for_session()` semantički treba postati “latest” metoda ili dobiti filtere za `report_type`, `work_status`, `source_kind`.
- `ReportService._reopen_plan_item()` treba koristiti report-task link ili `session_task_binding_id`, ne samo `AgentSession.plan_item_id`.
- `EvidenceService.build()` treba birati relevantan report po plan item/task linku, ne samo najnoviji report primarne sesije.
- `TimelineService` treba razlikovati report eventove po `report_type` i izbjeći šum iz fallback reportova.
- `SessionCompletionService` treba automatski report označiti kao fallback/auto-generated.
- `reports.py` HTTP rute su stub i moraće dobiti stvarnu list/read/update semantiku ako Ledger/GUI bude čitao DB reportove.

Testovi:

- `tests/unit/test_reports.py`: nova polja, idempotency, multi-task link, status/work_status razdvajanje.
- `tests/unit/test_session_completion.py`: completion report ostaje, ali kao fallback/auto-generated.
- `tests/unit/test_evidence.py`: report verdict izbor po task/plan binding linku.
- `tests/integration/test_e2e_phase3.py`: timeline i report origin treba očekivati tipizirane report eventove.
- novi ingestion testovi za YAML front-matter, dedupe, active-session ingestion i multi-task report.

## Minimalni ciljni model: `AgentReport v2`

Minimalni cilj je evoluirati postojeći `AgentReport`, ne praviti treći sistem.

### Postojeći `agent_reports` ostaje centralna tabela

Zadržati:

- `id`
- `session_id`
- `agent_job_id`
- `status`
- postojeće sadržajne sekcije
- `commit_shas_json`
- `changed_files_json`
- `user_verdict`
- `user_notes`
- `verdict_audit_json`
- `created_at`
- `updated_at`

Dodati sljedeća polja.

### Polje: `report_type`

Zašto je potrebno:
Razlikuje `analysis`, `fix`, `review`, `handoff`, `completion_fallback` i slične vrste reporta. Bez toga “najnoviji report” ostaje jedini signal i nije dovoljan za Ledger.

Izvor:
YAML front matter `report_type`; za automatski completion report deterministički `completion_fallback`.

Obavezno/opciono:
Obavezno za nove ingestovane reportove. Za postojeće DB redove može dobiti default `legacy` ili `completion_fallback` kroz migraciju/backfill.

### Polje: `work_status`

Zašto je potrebno:
Workflow Ledger treba mašinski čitljiv status rada bez LLM zaključivanja iz Markdown tijela. Postojeći `status=DRAFT/FINAL` znači lifecycle/verdict stanje reporta, ne status rada.

Izvor:
YAML front matter, npr. deterministički enum iz agent report konvencije. Za automatski completion fallback može se mapirati iz `AgentSession.status` samo kao fallback signal, jasno označen.

Obavezno/opciono:
Obavezno za Ledger-korisne reportove. Nullable za legacy/fallback reportove dok se ne uvede backfill.

### Polje: `source_kind`

Zašto je potrebno:
Razlikuje `MARKDOWN_FILE`, `AUTO_COMPLETION`, eventualno `API` ili `LEGACY_DB`. Ovo sprečava miješanje ručno/agentski pisanih artifacta i automatskih completion draftova.

Izvor:
Ingestion pipeline ili `SessionCompletionService`.

Obavezno/opciono:
Obavezno za nove reportove. Default za stare redove može biti `LEGACY_DB`.

### Polje: `source_path`

Zašto je potrebno:
Čuva vidljivu vezu na `agent_reports/*.md` artefakt i omogućava korisniku/debuggeru da otvori originalni Markdown.

Izvor:
Normalized relative path iz repo root-a, npr. `agent_reports/2026-08-11_...md`.

Obavezno/opciono:
Obavezno za `MARKDOWN_FILE`; nullable za `AUTO_COMPLETION` i legacy DB reportove.

### Polje: `source_identity`

Zašto je potrebno:
Stabilniji identitet report artefakta od samog patha; osnova za idempotentni ingestion i sprečavanje duplih DB zapisa.

Izvor:
YAML `report_id` ako postoji; inače deterministički iz repo identity + normalized relative path, uz content hash kao verzijski signal.

Obavezno/opciono:
Obavezno za `MARKDOWN_FILE`. Nullable za legacy dok se ne backfilluje.

### Polje: `source_content_sha256`

Zašto je potrebno:
Detektuje da li je isti Markdown artifact već ingestovan u istoj verziji i da li se sadržaj promijenio.

Izvor:
SHA-256 nad tačno ingestovanim Markdown sadržajem.

Obavezno/opciono:
Obavezno za `MARKDOWN_FILE`; nullable za `AUTO_COMPLETION`.

### Polje: `source_modified_at`

Zašto je potrebno:
Pomaže dijagnostici i incremental scan-u filesystema, ali ne treba biti autoritet za identitet.

Izvor:
Filesystem metadata tokom ingestiona.

Obavezno/opciono:
Opciono.

### Polje: `session_task_binding_id`

Zašto je potrebno:
Veže report za tačan vremenski task/plan context jedne sesije kada postoji dominantni binding segment. Ovo je posebno važno ako session promijeni task tokom trajanja.

Izvor:
Deterministički lookup po `session_id` + `created_at` prema `session_task_bindings.started_at/ended_at`, ili eksplicitni YAML override ako bude uveden.

Obavezno/opciono:
Opciono. Nullable jer report može pokrivati više taskova, biti unassigned, legacy, ili nemati pouzdan timestamp/session.

### Polje: `ingested_at`

Zašto je potrebno:
Razlikuje kada je report napisan (`created_at` iz YAML-a) od vremena kada ga je backend ingestovao.

Izvor:
Backend ingestion timestamp.

Obavezno/opciono:
Obavezno za `MARKDOWN_FILE`; nullable/default za legacy.

### Polje: `ingest_status`

Zašto je potrebno:
Omogućava determinističko stanje parsera bez bacanja reporta: `OK`, `PARTIAL`, `INVALID_FRONT_MATTER`, `DUPLICATE`, itd.

Izvor:
Ingestion pipeline.

Obavezno/opciono:
Obavezno za ingestion zapise. Za postojeće reportove može default `LEGACY`.

## Minimalna prateća tabela: `agent_report_task_links`

Ovo nije treći report sistem, nego normalizovana veza postojećeg `AgentReport` na više task targeta.

### Polje: `report_id`

Zašto je potrebno:
FK na `agent_reports.id`.

Izvor:
DB AgentReport.

Obavezno/opciono:
Obavezno.

### Polje: `target_kind`

Zašto je potrebno:
YAML `tasks:` može referencirati lokalni `Task`, `PlanItem`, `unassigned` ili historijski/vanjski task ključ.

Izvor:
Determinističko mapiranje iz YAML `tasks:` i lokalnog DB lookup-a.

Obavezno/opciono:
Obavezno.

### Polje: `target_id`

Zašto je potrebno:
Normalizovana FK referenca kada je lokalni `Task` ili `PlanItem` pouzdano pronađen.

Izvor:
DB lookup po YAML task identifikatoru ili preko `SessionTaskBinding`.

Obavezno/opciono:
Opciono.

### Polje: `task_key`

Zašto je potrebno:
Čuva originalnu YAML vrijednost i omogućava audit kada lokalni target ne postoji ili je `unassigned`.

Izvor:
YAML `tasks:` stavka.

Obavezno/opciono:
Obavezno ako `target_id` nije poznat; korisno i kada jeste poznat.

### Polje: `session_task_binding_id`

Zašto je potrebno:
Povezuje pojedinačnu task vezu s historijskim binding segmentom kada je moguće. Ovo preciznije rješava multi-task report od jednog report-level `session_task_binding_id`.

Izvor:
Lookup kroz `SessionTaskBinding`.

Obavezno/opciono:
Opciono.

## Da li postojeći DB AgentReport možemo evolutivno prilagoditi bez brisanja ili migriranja postojećih report podataka?

Da.

Postojeći `AgentReport` već ima dobar kostur:

- stabilan `id`;
- obavezan `session_id`;
- sadržajne sekcije koje odgovaraju čovjeku čitljivom reportu;
- commit/changed-files JSON;
- `user_verdict` i audit;
- `created_at/updated_at`;
- nema unique constrainta koji blokira više reportova po sesiji.

Najmanje remetilačka promjena je dodati nullable/defaultirana v2 polja i link tabelu, bez brisanja postojećih kolona i bez premještanja postojećih podataka. Legacy redovi mogu ostati validni sa `source_kind="LEGACY_DB"` ili nullable v2 poljima dok se ne uvede deterministički backfill.

Najvažnije je ne uvoditi paralelnu treću tabelu tipa `WorkflowReport`. Workflow Ledger treba čitati postojeći `AgentReport` v2 i njegove task linkove.

## Preporučeni evolutivni redoslijed, bez implementacije u ovom zadatku

1. Dodati v2 polja kao nullable/default bez rušenja postojećih redova.
2. Dodati `agent_report_task_links` za multi-task normalizaciju.
3. Označiti `SessionCompletionService` report kao `source_kind=AUTO_COMPLETION`, `report_type=completion_fallback`.
4. Implementirati deterministički ingestion `agent_reports/*.md → AgentReport v2`.
5. Prebaciti Evidence/Ledger čitanje na strukturisane v2 podatke i task linkove.
6. Tek poslije toga smanjiti semantičku ulogu automatskog completion drafta.

## Rizici i ograničenja

- `status=DRAFT/FINAL` se ne smije reciklirati za `work_status`; to bi pomiješalo lifecycle reporta i stanje rada.
- `user_verdict` danas utiče na `PlanItem` preko `AgentSession.plan_item_id`, što je nedovoljno nakon više binding segmenata.
- `source_path` bez hash/identity nije dovoljan za idempotentan ingestion.
- Jedan report može legitimno pokrivati više taskova; jedno `task_id` polje bi bilo arhitektonsko nazadovanje.
- Ingestion mora biti deterministički i ne smije izvlačiti zaključke iz Markdown tijela LLM-om.

## Verdict

EVOLVE EXISTING AGENTREPORT

Kratko obrazloženje: postojeći DB `AgentReport` već je centralna strukturisana report tabela, nema unique constraint koji blokira više reportova po sesiji, i već ima verdict/audit/sadržajna polja. Potrebno ga je evolutivno proširiti artifact identity poljima, `report_type`, `work_status`, ingestion metapodacima i normalizovanom multi-task link tabelom. Nema potrebe praviti treći report sistem niti brisati postojeće report podatke.
