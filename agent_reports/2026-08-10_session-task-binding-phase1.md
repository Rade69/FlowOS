---
flowos_report_version: 1
agent: codex
model: gpt-5
session_id: unknown
report_type: implementation
tasks:
  - unassigned
commits: []
created_at: 2026-08-10T21:13:51.1671968+02:00
---

# SessionTaskBinding — faza 1

## Datum

2026-08-10

## Agent / model / sesija

- Agent: codex
- Model: gpt-5
- Sesija: unknown

## Scope

Implementiran je prvi kompatibilni arhitektonski korak nakon baseline commita `0206df00e345643cb7f3ee9a49077a4b48c71d8e`: nova istorijska tabela `SessionTaskBinding` i service/API sloj koji omogućavaju da jedna agentska sesija kroz vrijeme bude vezana za više task konteksta.

Nisu uklonjeni postojeći `AgentSession.task_id` i `AgentSession.plan_item_id`.

## Task contract / acceptance kriteriji

Cilj je bio dodati pouzdan vremenski sloj:

```text
stari AgentSession.task_id / plan_item_id
        ↓
sada LEGACY COMPATIBILITY POINTERS na trenutni binding

SessionTaskBinding
        ↓
nova autoritativna istorija promjena task konteksta
```

Acceptance kriteriji iz naloga su pokriveni:

- jedna sesija može imati više vremenskih binding segmenata;
- postoji najviše jedan aktivni binding;
- `UNASSIGNED` je podržan bez fake taska;
- cross-project `Task` i `PlanItem` veze se odbijaju;
- session end zatvara aktivni binding istim završnim vremenom;
- legacy `AgentSession` polja nastavljaju raditi kao compatibility pointeri;
- postojeće istorijske sesije nisu backfillovane niti falsifikovane;
- dodani su minimalni HTTP endpointi;
- Alembic migracija prolazi upgrade/downgrade/upgrade;
- `scripts/verify.py` prolazi 7/7;
- kompletan pytest suite prolazi.

## GitNexus impact / blast radius

Prije izmjene je urađena GitNexus impact analiza:

- `AgentSession`: HIGH, jer ga direktno importuje više service/controller modula. Zbog toga je promjena ostala aditivna i kompatibilna; legacy FK polja nisu uklonjena.
- `SessionService`: LOW, direktni potrošač je session HTTP controller.
- `SessionService.create_session`: LOW, pogođen je postojeći create-session HTTP tok.
- session HTTP API: LOW prema API impactu za postojeće rute.

Nakon izmjene je pokrenut GitNexus detect changes:

- risk: HIGH;
- pogođeni tokovi: `Create_session → Disconnect` i `SessionCompletionService.complete_session` tokovi;
- nalaz odgovara očekivanom scope-u.

## Reprodukcija prije izmjene

Baseline je prvo provjeren:

- `git log -5 --oneline`: HEAD je bio `0206df0 fix: stabilize FlowOS baseline before migration`.
- `git status --short --branch`: postojao je samo prethodni necommitovani edit u `agent_reports/2026-08-10_flowos-baseline-stabilization.md`.
- `python scripts\verify.py`: 7/7 PASS prije nove migracije.

Prije ove faze nije postojao `SessionTaskBinding`; postojeća sesija je imala samo trenutne FK pointere `AgentSession.task_id` i `AgentSession.plan_item_id`, bez vremenske istorije promjena task konteksta.

## Tačna nova šema

Nova tabela: `session_task_bindings`

Kolone:

- `id` — UUID string primary key;
- `session_id` — obavezan FK na `agent_sessions.id`, `ON DELETE CASCADE`;
- `task_id` — opcioni FK na `tasks.id`, `ON DELETE SET NULL`;
- `plan_item_id` — opcioni FK na `plan_items.id`, `ON DELETE SET NULL`;
- `started_at` — obavezan početak segmenta;
- `ended_at` — opcioni kraj segmenta; `NULL` znači aktivni binding;
- `binding_source` — `USER` ili `LEGACY_DIRECT_FK`.

Constraints/indexi:

- `ck_session_task_bindings_single_target`: ne dozvoljava da isti binding ima i `task_id` i `plan_item_id`;
- `ck_session_task_bindings_time_order`: `ended_at` mora biti `NULL` ili `>= started_at`;
- `ck_session_task_bindings_source`: dozvoljene su samo `USER` i `LEGACY_DIRECT_FK`;
- `uq_session_task_bindings_active`: partial unique index nad `session_id` gdje je `ended_at IS NULL`;
- indeksi nad `session_id`, `task_id`, `plan_item_id`, `started_at`.

## Migracija

Dodana je Alembic migracija:

```text
alembic/versions/9b2d1f7a4c63_session_task_bindings.py
```

Migracija kreira samo novu tabelu, constraints i indekse. Nema agresivnog backfill-a istorijskih sesija, jer stari FK pointeri ne dokazuju kada je tokom sesije rad na određenom tasku stvarno počeo ili završio.

## Kako radi TASK / PLAN_ITEM / UNASSIGNED

`SessionTaskBinding` target pravila:

- TASK: `task_id != NULL`, `plan_item_id == NULL`;
- PLAN_ITEM: `task_id == NULL`, `plan_item_id != NULL`;
- UNASSIGNED: `task_id == NULL`, `plan_item_id == NULL`.

Kombinacija `task_id != NULL AND plan_item_id != NULL` je zabranjena na service i DB nivou.

## Kako radi switch

`SessionTaskBindingService.switch_binding()`:

1. validira da target nije istovremeno Task i PlanItem;
2. učita sesiju;
3. pronađe postojeći aktivni binding;
4. zatvori ga na `switched_at`;
5. validira da novi Task/PlanItem pripada istom projektu kao sesija;
6. kreira novi aktivni binding;
7. osvježi legacy `AgentSession.task_id/plan_item_id` pointere;
8. flushuje kao jedna transakcija u postojećem DB session dependency toku.

HTTP endpoint:

```text
POST /sessions/{session_id}/bindings/switch
```

Server uvijek postavlja `binding_source = USER`; request contract ne dozvoljava clientu da pošalje ili lažira `binding_source`.

## Kako se zatvara binding

`SessionService.end_session()` zatvara aktivni binding istim vremenom koje upiše u `AgentSession.ended_at`.

`SessionCompletionService.complete_session()` takođe zatvara aktivni binding istim `now` timestampom koji koristi za završetak sesije, jer taj background tok ne ide kroz `SessionService.end_session()`.

## Compatibility ponašanje

`AgentSession.task_id` i `AgentSession.plan_item_id` su sada:

```text
LEGACY COMPATIBILITY POINTERS
```

Oni pokazuju na trenutni aktivni binding kako bi postojeći kod nastavio raditi dok novi kod dobija istoriju.

Pravila:

- TASK binding postavlja `AgentSession.task_id = task_id`; ako taj `Task` ima pouzdan `Task.plan_item_id`, onda `AgentSession.plan_item_id` prati taj odnos, inače je `NULL`;
- PLAN_ITEM binding postavlja `AgentSession.task_id = NULL`, `AgentSession.plan_item_id = plan_item_id`;
- UNASSIGNED postavlja oba legacy pointera na `NULL`.

Kod ne nagađa plan item za task koji ga nema.

## Izmijenjeni fajlovi i ponašanje

- `src/flowos/service/services/infrastructure/persistence/models.py` — dodat ORM model `SessionTaskBinding` i relationship na `AgentSession`.
- `alembic/versions/9b2d1f7a4c63_session_task_bindings.py` — nova migracija.
- `src/flowos/shared/enums/session.py` — dodat `SessionTaskBindingSource`.
- `src/flowos/shared/contracts/sessions.py` — dodani `SessionTaskBindingResponse` i `SessionTaskBindingSwitchRequest`.
- `src/flowos/service/services/sessions/bindings.py` — novi service za istoriju i switch.
- `src/flowos/service/services/sessions/service.py` — create-session kreira početni binding; end-session zatvara aktivni binding; nekonzistentni legacy `task_id + plan_item_id` se odbijaju.
- `src/flowos/service/services/sessions/completion.py` — completion zatvara aktivni binding.
- `src/flowos/service/controllers/http/sessions.py` — dodani minimalni binding API endpointi.
- `tests/integration/test_session_task_bindings.py` — regresioni testovi A–N iz naloga.

## Šta nije dirano

Nije implementirano:

- `DecisionItem`;
- `ImplementationTask`;
- `WorkflowEvent`;
- Workflow Ledger;
- YAML parser za `agent_reports`;
- Claude/Codex/Pi/Crush observeri;
- agent telemetry;
- Context Packages;
- review/fix arhitektura;
- `ExecutionWorkspace`;
- `AgentRun`;
- `AgentContext`;
- GUI za SessionTaskBinding.

Nije uklonjeno:

- `Task`;
- `PlanItem`;
- `AgentSession.task_id`;
- `AgentSession.plan_item_id`;
- `SessionEvent`;
- `PlanProgressEvent`;
- `FileActivity`.

## Verifikacija i stvarni rezultat

Pokrenuto:

```text
python -m pytest tests\integration\test_session_task_bindings.py tests\integration\test_sessions_plan_item_api.py -q
```

Rezultat:

```text
15 passed, 1 warning
```

Pokrenuto:

```text
python scripts\verify.py
```

Rezultat:

```text
7/7 PASS
306 passed, 1 warning u unit/integration/contract koraku
migrations check PASS
Alembic round-trip PASS
```

Pokrenuto:

```text
python -m pytest -q
```

Rezultat:

```text
314 passed, 1 warning
```

Jedino upozorenje je postojeći `StarletteDeprecationWarning` iz `fastapi.testclient` dependency sloja.

## Nezavisna provjera

Nije pokrenut zaseban drugi agent/checker. Kao mehanička provjera korišteni su GitNexus impact/detect, architecture boundary testovi, mypy, Alembic roundtrip, ciljani regression testovi i kompletan pytest suite.

Zbog HIGH impacta nad `AgentSession`, preporučeni ljudski review je:

- `SessionTaskBindingService.switch_binding`;
- `SessionService.create_session`;
- `SessionCompletionService.complete_session`;
- migracija `9b2d1f7a4c63_session_task_bindings.py`;
- `tests/integration/test_session_task_bindings.py`.

## Pronađeni problemi

Tokom implementacije su uhvaćene i riješene ove stvari:

- SQLite vraća `DateTime(timezone=True)` kao naive datetime u test okruženju; service sada normalizuje poređenje u UTC za time-order validaciju.
- Controller je prvobitno importovao persistence model radi type hint-a; architecture boundary test je to odbio, pa je import uklonjen.
- `SessionCompletionService` ima poseban završni tok i morao je eksplicitno zatvoriti binding, nezavisno od `SessionService.end_session`.

## Odbačene opcije

- Nije uveden generički `work_item_type/work_item_id`, jer nalog eksplicitno traži samo privremenu kompatibilnost sa `Task` i `PlanItem`.
- Nije rađen data backfill istorijskih sesija, jer bi to izmišljalo vremensku istoriju iz legacy FK pointera.
- Nisu dodane AI/INFERRED/CONFIDENCE binding source vrijednosti, jer FlowOS ne smije nagađati koji task agent radi.
- Nije dodat redundantni `project_id` na binding tabelu; project validacija ide preko postojeće stvarne relacije.

## Konflikti / kontradiktorni izvori

Nije bilo kontradikcije u zahtjevu. Postojao je prljav working tree prije početka zbog prethodne tekstualne izmjene baseline reporta:

```text
agent_reports/2026-08-10_flowos-baseline-stabilization.md
```

Taj fajl nije dio funkcionalne SessionTaskBinding implementacije, ali ostaje necommitovana izmjena u istom working treeju.

## Commitovi

Nije napravljen commit, po nalogu.

## Rizici i ograničenja

- HIGH impact je očekivan jer `AgentSession` koristi više servisa; promjena je zato aditivna i kompatibilna.
- Partial unique index je SQLite-specifično iskorišten za `ended_at IS NULL`, uz service-layer invariant i test.
- Historical sessioni prije ove migracije mogu ostati bez binding zapisa; to je namjerno da se ne falsifikuje istorija.
- `AgentSession.task_id/plan_item_id` i dalje mogu biti čitani u starom kodu, ali više nisu autoritet za istoriju rada.

## Potreban follow-up

Naredni koraci tek poslije review-a:

- eventualni GUI prikaz binding istorije;
- kasnija migracija odnosa `Task` / `PlanItem` / `DecisionItem` / `ImplementationTask`;
- eventualni kontrolisani backfill samo ako se nađe deterministički dokaz za dio istorije.

## Potrebna korisnička potvrda

Potrebna je korisnička potvrda nakon review-a da je SessionTaskBinding faza 1 prihvaćena kao prvi arhitektonski migration korak.

## Status

SESSION TASK BINDING PHASE 1 READY
