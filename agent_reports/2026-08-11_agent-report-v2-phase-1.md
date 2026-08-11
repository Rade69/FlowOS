---
flowos_report_version: 1
agent: codex
model: gpt-5
session_id: unknown
report_type: implementation
work_status: completed
tasks:
  - unassigned
commits: []
created_at: 2026-08-11T00:00:00+02:00
---

# AgentReport v2 — Phase 1

## Scope

Implementirana je samo pouzdana veza postojećeg `AgentReport` zapisa sa jednom ili više istorijskih `SessionTaskBinding` segmenata, osnovna implementer semantika i sigurno reopenovanje PlanItem-a nakon `NEEDS_WORK` ili `REJECTED` verdicta.

Nije napravljen commit, prema izričitom nalogu.

## Task contract i acceptance kriteriji

Cilj je ukloniti pogrešnu atribuciju iz `_reopen_plan_item()`: report više ne koristi trenutni `AgentSession.plan_item_id` kao autoritet. Report sada može eksplicitno referencirati više istorijskih bindinga iste sesije. Legacy reporti ostaju podržani samo kada sesija ima tačno jedan relevantni istorijski binding.

Izvan scope-a su Workflow Ledger, YAML/Markdown ingestion, watcher, hash/dedupe polja, HTTP endpoint, redizajn `SessionCompletionService` i promjena `EvidenceService` legacy session lookupa.

## Impact / blast radius

GitNexus indeks je osvježen na trenutni `HEAD`, ali se MCP servis prekinuo prije vraćanja context/impact rezultata. Ručno su pregledani svi pozivaoci i potrošači `AgentReport`, `ReportService`, `SessionTaskBinding`, `SessionCompletionService`, `EvidenceService`, timeline servis i postojeći testovi.

Rizik je visok zbog Alembic migracije i centralne statusne tranzicije. Direktno pogođeni su ORM metadata, `ReportService.set_verdict()` tok i `PlanProgressService`. `EvidenceService` i `SessionCompletionService` nisu izmijenjeni.

## Reprodukcija prije izmjene

Dokazan uzrok: `_reopen_plan_item()` je išao preko `report.session_id → AgentSession.plan_item_id`. Nakon switcha sa PlanItem A na B taj pointer pokazuje B, pa verdict reporta koji pripada ranijem bindingu A može reopenovati pogrešan target.

Tok je reprodukovan regresionim testom: session prvo radi task/PlanItem A, zatim se prebaci na B, report se eksplicitno veže za binding A, a `NEEDS_WORK` vraća samo A u `IN_PROGRESS`.

## Šta je urađeno

- `AgentReport` je evolutivno dobio nullable `report_type` i `work_status`; postojeći redovi ostaju nepromijenjeni sa `NULL` vrijednostima.
- `ReportService.create_draft()` prihvata opciona polja bez promjene postojećih pozivalaca. `work_status` se validira isključivo prema `completed`, `partial`, `blocked`; status se ne zaključuje iz proze, commita, testova ili session statusa.
- Dodan je `AgentReportBindingLink` između reporta i `SessionTaskBinding` sa FK pravilima `report → CASCADE`, `binding → RESTRICT` i unique zaštitom para report/binding.
- Dodan je `link_report_to_binding(report_id, session_task_binding_id)`. Operacija odbija nepostojeći report/binding, binding druge sesije i dupli link prije mutationa.
- `_reopen_plan_item()` koristi eksplicitne linkove reporta. Direktni `binding.plan_item_id` ima prednost; za `binding.task_id` koristi se `Task.plan_item_id`. Jedinstveni PlanItem ID-jevi obrađuju se deterministički.
- UNASSIGNED binding ne daje PlanItem target.
- Legacy fallback koristi tačno jedan relevantni istorijski binding. Za nula ili više od jednog relevantnog bindinga ne radi se reopen i piše se warning; trenutni `AgentSession.plan_item_id` se nikad ne koristi kao fallback.
- Minimalno je proširena postojeća `PlanProgressService` matrica da omogući `IMPLEMENTED/VERIFIED → IN_PROGRESS`, što je nužno da obavezni reopen tok stvarno može izvršiti centralnu validiranu tranziciju umjesto zaobilaženja servisa.

## ORM i migraciona odluka

Nova migracija `a17e4c8f9b21_agent_report_v2_bindings.py` dodaje samo nullable kolone i novu link tabelu. Ne radi backfill ni nagađanje o postojećim reportima. Downgrade uklanja samo v2 strukturu.

Link tabela ne duplicira `task_id` ni `plan_item_id`: binding istorija ostaje jedini autoritativni izvor tog konteksta.

## Testovi

Dodani su `tests/integration/test_agent_report_v2.py` testovi za:

- legacy nullable polja i `implementation/completed` semantiku;
- jedan i više binding linkova, duplicate i cross-session odbijanje;
- CASCADE brisanje linkova pri brisanju reporta i RESTRICT zaštitu bindinga;
- ključni A → B regression tok gdje report vezan za A ne smije pogoditi B;
- više bindinga sa više jedinstvenih PlanItem-a;
- UNASSIGNED binding;
- legacy fallback sa tačno jednim bindingom i sigurno odbijanje fallbacka kod više bindinga.

## Verifikacija

- `python -m pytest tests/integration/test_agent_report_v2.py tests/unit/test_reports.py -v --tb=short` → PASS, 15 passed.
- `python scripts/verify.py` → PASS, 7/7.
- Širi unit/integration/contract suite unutar standardne provjere → PASS, 323 passed; 1 postojeće dependency upozorenje `StarletteDeprecationWarning`.
- Alembic upgrade na praznoj privremenoj SQLite bazi i complete upgrade/downgrade/upgrade round-trip → PASS.

## Šta nije dirano

Nisu implementirani Workflow Ledger, YAML/Markdown ingestion, filesystem watcher, artifact identity/hash/dedupe pipeline, nova report tabela, HTTP link endpoint, `SessionCompletionService` semantika, automatski session-end report ni `EvidenceService` legacy lookup.

## Follow-up i ograničenja

`EvidenceService` i dalje pronalazi report preko trenutnog `AgentSession.plan_item_id`; to je poznata odvojena migraciona tačka i nije dirana u ovoj fazi. `SessionCompletionService` i `/sessions/{id}/end` integracija takođe ostaju izvan scope-a.

Nezavisni checker još nije izvršio review. Prije prihvatanja predlaže se pregled migracije, `ReportService._reopen_plan_item()`, proširene statusne matrice i ključnog A → B regresionog testa.

## Commitovi

Nema. Rad je namjerno ostavljen necommitovan.

## Verdict

READY FOR INDEPENDENT REVIEW
