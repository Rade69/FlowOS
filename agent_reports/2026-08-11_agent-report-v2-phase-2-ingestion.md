---
flowos_report_version: 1
report_id: d24e51d3-ba93-478c-ba24-ed821b6c20af
agent: codex
model: gpt-5
session_id: unknown
report_type: implementation
work_status: completed
tasks:
  - unassigned
commits: []
created_at: 2026-08-11T16:22:08+02:00
---

# AgentReport v2 - Phase 2 ingestion

## Scope

Implementiran je deterministicki ingestion za `agent_reports/*.md` kao Phase 2 AgentReport v2 vertikala. Nije implementiran Workflow Ledger, HTTP ingestion endpoint, SessionCompletionService wiring, EvidenceService rewrite, drugi watcher, pending tabela, LLM parser niti bilo kakav fuzzy matching.

## DB promjene

Na postojeci `AgentReport` dodata su nullable source polja:

- `source_report_id`
- `source_path`
- `source_content_sha256`

Dodata je Alembic migracija `4f2c9a7b8d11_agent_report_source_identity.py` sa upgrade/downgrade tokom i bez legacy backfill nagadjanja. `AgentReport.session_id` nije mijenjan u nullable.

## Parser

Dodat je `AgentReportFrontMatterParser` kao pure komponenta. Parser cita samo YAML front matter na pocetku Markdown fajla, koristi PyYAML SafeLoader, odbija duplicate YAML kljuceve i validira canonical contract:

- `flowos_report_version: 1`
- validan UUID `report_id`
- validan UUID `session_id` ili `unknown`
- dozvoljen `report_type`
- conditional `work_status`
- neprazan `tasks`
- timezone-aware ISO `created_at`

Markdown body se ne koristi za zakljucivanje report tipa, work statusa, taska ili sesije.

## Identity i hash pravila

Ingestion racuna SHA-256 sirovih Markdown bytes prije mutationa. `source_report_id` je stabilni identitet artefakta, a `source_path` je provenance. Implementirana su pravila:

- novi `report_id` moze biti ingestovan
- isti `report_id` + ista putanja + isti SHA je idempotentni no-op
- isti `report_id` + ista putanja + drugi SHA je `IMMUTABLE_CONFLICT`
- isti `report_id` + druga putanja je `IMMUTABLE_CONFLICT`
- drugi `report_id` na vec zauzetoj putanji je `IMMUTABLE_CONFLICT`
- legacy report bez front mattera ili bez identiteta ne kreira DB `AgentReport`

## Session resolution

Autoritet za sesiju dolazi iskljucivo iz validiranog YAML `session_id`. `session_id: unknown`, nepostojeca sesija i cross-project sesija vracaju `NEEDS_LINK` bez DB report reda. Nije koristen fallback na jedinu aktivnu sesiju, FileActivity atribuciju, trenutni `AgentSession.task_id`, trenutni `AgentSession.plan_item_id` ili timestamp heuristiku.

## Binding resolution

Binding rezolucija koristi samo istorijske `SessionTaskBinding` segmente date sesije. Podrzani su exact tokeni za:

- `Task.id`
- `PlanItem.id`
- `PlanItem.item_key`

Ako bilo koji token nije jednoznacno dokaziv, cijeli ingestion vraca `NEEDS_LINK` bez parcijalnog reporta ili linkova. `tasks: [unassigned]` kreira session-scoped AgentReport bez `AgentReportBindingLink`. Linkovanje ide kroz postojeci `ReportService.link_report_to_binding()`, tako da `resolved_plan_item_id` snapshot ostaje centralizovan u Phase 1 ugovoru.

## Startup scan

Pri startupu se za svaki registrovani projekat skenira postojeci `<repo_path>/agent_reports/*.md` folder i svaki kandidat ide kroz isti `AgentReportIngestionService` koji koristi watcher hook. Ako folder ne postoji, nema greske i folder se ne kreira automatski. Idempotency pravila pokrivaju race izmedju startup scan-a i watcher dogadjaja.

## Watcher hook

Postojeci `WatcherPipeline` nije dupliran. U produkcijski watcher callback dodat je mali hook za `CREATED` i `MODIFIED` dogadjaje direktno ispod `<repo_path>/agent_reports/*.md`. `DELETED` ostaje samo FileActivity audit. Transakciona granica je:

1. sacuvaj i commituj `FileActivity`
2. pokusaj ingestion
3. upisi outcome u `FileActivity.metadata_json` kada je dostupno

Parser/DB/neocekivane ingestion greske ne rollbackuju vec sacuvan FileActivity i ne ruse watcher callback.

## Testovi

Dodati su:

- `tests/unit/test_agent_report_front_matter.py`
- `tests/integration/test_agent_report_ingestion.py`

Pokriveni su parser validacije, duplicate key rejection, identity/idempotency/immutable konflikti, session resolution, exact binding resolution, multi-task i A-B-A istorija, `unassigned`, current pointer anti-fallback, startup scan i watcher isolation.

## Verifikacija

Pokrenuto:

- `python -m pytest tests/unit/test_agent_report_front_matter.py tests/integration/test_agent_report_ingestion.py -q` - 35 passed
- relevantne regresije za SessionTaskBinding, AgentReport v2 Phase 1, ReportService, SessionCompletionService, watcher/activity/evidence/composition - passed
- `python scripts/guard_architecture.py` - prijavio postojece service->websocket imports, ali `pytest tests/architecture/` u standardnom verify toku prolazi
- `python scripts/verify.py` - PASS 7/7

Zavrsni verify rezultat:

- Ruff format: PASS
- Ruff lint: PASS
- mypy: PASS
- architecture boundaries: PASS
- unit/integration/contract tests: 366 passed, 1 warning
- migrations check: PASS
- Alembic round-trip: PASS

## Poznata ogranicenja

Postojeci watcher prati `Project.repo_path`. Fajlovi u odvojenim worktree rootovima koji nisu ispod tog rekurzivno pracenog root-a nisu rijeseni ovom fazom, po nalogu. To ostaje poznato ogranicenje za kasniju worktree watcher arhitekturu.

## Nije implementirano

Nije implementiran Workflow Ledger, Verification Ledger, HTTP ingestion endpoint, drugi watcher, pending/report tabela, LLM parsing, fuzzy matching, EvidenceService migracija, SessionCompletionService wiring, custom report folder konfiguracija niti managed worktree watcher redesign.

READY FOR INDEPENDENT REVIEW
