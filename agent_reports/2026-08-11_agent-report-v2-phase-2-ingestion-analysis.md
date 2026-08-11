---
flowos_report_version: 1
agent: codex
model: gpt-5
session_id: unknown
report_type: analysis
tasks:
  - unassigned
commits: []
created_at: 2026-08-11T14:44:09.8651299+02:00
---

# AgentReport v2 — Phase 2 — read-only ingestion analiza

## Scope i zaključak

Ovo je read-only arhitektonska analiza determinističkog učitavanja `agent_reports/*.md` u postojeći `AgentReport` sistem. Nisu mijenjani kod, migracije, watcher, parser ni Workflow Ledger; nije napravljen commit.

Preporučeni dizajn je namjerno konzervativan: report bez pouzdanog `session_id` ne ulazi u bazu, svaki novi report dobija eksplicitni YAML `report_id`, a session/binding rezolucija se radi samo exact-match pravilima. Nepouzdan slučaj ostaje na filesystemu i dobija postojeći FileActivity/log trag, bez izmišljene atribucije i bez trećeg report sistema.

## Pregledani kod i dokazno stanje

Pregledani su:

- `src/flowos/service/services/infrastructure/watcher.py`
- `src/flowos/service/composition_root.py`
- `src/flowos/service/services/activity/service.py`
- `src/flowos/service/services/infrastructure/persistence/activity_models.py`
- `src/flowos/service/services/infrastructure/persistence/report_models.py`
- `src/flowos/service/services/reports/service.py`
- `src/flowos/service/services/sessions/completion.py`
- `src/flowos/service/services/evidence.py`
- `src/flowos/service/services/sessions/timeline.py`
- `src/flowos/service/controllers/http/reports.py`
- `src/flowos/service/services/infrastructure/persistence/models.py`
- `src/flowos/service/services/infrastructure/persistence/plan_models.py`
- postojeći unit/integration watcher, activity, report, session completion i persistence testovi
- postojeći `agent_reports/*.md`, `pyproject.toml`, relevantni planovi i Phase 1 reporti

GitNexus indeks je svjež za prihvaćeni baseline `c777c0e058baf446431f3a20dba7798b3566ec73`: 7.187 simbola, 11.494 relacije i 175 flowova. GitNexus FTS query je prijavio da indeksi za keyword search nedostaju, pa su zaključci zasnovani na graph context/impact rezultatima i direktnom čitanju izvora. Working tree je prije analize imao samo postojeće izmjene u `AGENTS.md` i `CLAUDE.md`; nijedan od ta dva fajla nije diran.

## 1. Postojeći watcher — potvrda hipoteze

Hipoteza je tačna uz jednu važnu granicu.

`WatcherPipeline.start()` poziva `Observer.schedule(..., recursive=True)` na projektu registrovanom kroz `Project.repo_path`. `DEFAULT_IGNORE` ne sadrži `agent_reports`, a `_should_ignore()` ignoriše samo navedene foldere po komponentama putanje. Zato direktni fajlovi `repo_path/agent_reports/*.md` ulaze u isti watcher tok kao i svaki drugi fajl.

To nije poseban watcher za sve worktreeje: startup u `composition_root._make_lifespan()` kreira jedan watcher po `Project.repo_path`. Fajl u odvojenom worktreeju biće viđen samo ako fizički leži ispod tog rekurzivno praćenog root-a.

Svaki događaj ide u `_create_watcher_callback()`, koji kreira `ActivityService`, poziva `record_file_event()` i commit-uje `FileActivity`. Atribucija koristi aktivne sesije, ali za report ingestion ne smije biti autoritet: `session_id` se mora uzeti iz validiranog YAML-a. `FileActivity.session_id` može biti `NULL` i pogodna je samo za audit događaja.

### Preporučeni hook

Ne uvoditi drugi filesystem watcher. U postojećem callbacku, nakon normalnog `ActivityService` zapisa, dodati samo budući path predicate:

```text
repo_path/agent_reports/*.md
```

Za `CREATED` i `MODIFIED` događaj predati isti događaj budućem `AgentReportIngestionService`. `DELETED` ne pokušava parsirati; ostaje FileActivity događaj. Ingestion grešku uhvatiti u posebnom `try/except` nakon commita FileActivity-a, tako da ne rollbackuje aktivnost i ne može srušiti watcher. Nema drugog observera ni drugog activity toka.

## 2. `session_id: unknown` — preporučena opcija

### Stvarno ograničenje

`AgentReport.session_id` je trenutno obavezan FK prema `agent_sessions.id`. `ReportService._reopen_plan_item()`, `TimelineService`, `EvidenceService` i `SessionCompletionService` svi rade sa reportima vezanim za sesiju. `EvidenceService` i timeline report query eksplicitno filtriraju `AgentReport.session_id`; report HTTP ruta je trenutno samo stub. `SessionCompletionService` uvijek kreira report sa poznatim session ID-jem.

### Procjena opcija

| Opcija | Posljedica |
|---|---|
| A — odgoditi DB unos | Čuva postojeći NOT NULL/FK ugovor, nema lažne sesije, nema migracije i nema null-branch promjena u potrošačima. Artifact ostaje na disku i može se ponovo obraditi kada se pojavi pouzdan ID. |
| B — `session_id NULL` | Traži migraciju i promjene svih session-based queryja, `ReportService` verdict/link toka, Evidence/timeline/API/GUI pretpostavki i pravila brisanja. Uvodio bi detached AgentReport stanje koje Phase 1 nije modelovala. |
| C — nova pending tabela/model | Bio bi treći report/pending sistem i duplirao bi source artifact konvenciju. |

### Preporuka

**Opcija A — ne unositi report u `AgentReport` dok session nije pouzdan.**

`unknown`, prazan ili nepostojeći session ID znači `NEEDS_LINK`: nema `AgentReport` reda, nema binding linka i nema pokušaja izbora „jedine aktivne sesije“. Fajl ostaje source artifact. Budući callback može u postojeći `FileActivity.metadata_json` dodati dijagnostički rezultat (`report_candidate`, `ingestion_outcome: NEEDS_LINK`) i warning log; to nije nova report tabela niti source of truth. Ponovni CREATED/MODIFIED događaj ili eksplicitni rescan može pokušati isti artifact nakon što front matter dobije pravi ID.

Ovo je jedini izbor koji ne širi Phase 1 NOT NULL ugovor i ne pravi treći sistem. `AgentReport.session_id` ostaje obavezan.

## 3. Identitet i idempotencija

Pregledani postojeći reporti ne sadrže pouzdan YAML identitet: stariji reporti uopšte nemaju front matter, a noviji koriste `session_id: unknown` i nemaju `report_id`. `AgentReport.id` je interni UUID koji generiše ORM i nije identitet Markdown artefakta. `FileActivity.event_id` je nasumičan za svaki događaj, a `ActivityService` trenutno postavlja `idempotency_key=None`; nije pogodan za report dedupe.

### Preporuka identiteta

U Phase 2 contract uvesti obavezni:

```yaml
report_id: <UUID>
```

Na postojeći `AgentReport` dodati samo:

- `source_report_id`: nullable `String(36)`, unique/index; `NULL` za legacy DB redove;
- `source_path`: nullable normalizovana apsolutna putanja artefakta za provenance/debug, bez unique constrainta.

`source_report_id` je stabilan identity; `source_path` nije identity. Ne koristiti hash, mtime ili slučajno generisani UUID pri ingestionu.

Deterministička pravila:

- isti `report_id` + isti source path + već ingestovan report → idempotentni no-op;
- isti `report_id` na drugom pathu → identity conflict, ne praviti drugi red;
- isti path sa MODIFIED i istim `report_id` nakon uspješnog ingestiona → report je immutable, samo warning/no-op;
- kopija sa istim `report_id` → conflict, jer ne može dokazati da je isti artefakt;
- preimenovanje sa istim `report_id` → bez hash/version sistema ne razlikuje se pouzdano od kopije; fail-safe conflict i potreban novi report ID ili eksplicitna buduća rename politika;
- legacy fajl bez `report_id` → ne unositi automatski, označiti `NEEDS_IDENTITY` i zahtijevati dopunu front mattera.

Ne koristiti `source_path` kao jedini ključ: preimenovanje i kopiranje bi ili pogrešno napravili novi red ili tiho spojili dva artefakta.

## 4. Minimalni YAML front-matter contract

Parser prihvata samo front matter koji počinje delimiterom `---` na prvoj liniji i završava sljedećim samostalnim `---`. Markdown tijelo se nikada ne parsira radi poslovnih zaključaka.

### Obavezno za novi ingestible report

```yaml
flowos_report_version: 1
report_id: <UUID>
report_type: implementation | analysis | review | fix
tasks: [<string>, ...]
created_at: <timezone-aware ISO-8601>
```

`session_id` mora postojati kao scalar ako report cilja sesiju, ali vrijednost `unknown` je eksplicitno dozvoljena samo kao `NEEDS_LINK` i tada nema DB insertiona. U Phase 2 može biti obavezan za `INGESTED` ishod, ali nije razlog da se izmišlja vrijednost kada ga artifact nema.

`work_status` je obavezan kada je `report_type: implementation`, a ako se navede za bilo koji tip mora biti tačno `completed`, `partial` ili `blocked`. Backend ga nikada ne zaključuje iz summaryja, commita, changed files, exit codea ili Markdown tijela.

### Opciono

- `session_id`: stvarni AgentSession UUID ili `unknown`;
- `agent`, `model`: provenance stringovi;
- `commits`: lista nepraznih SHA stringova; ne koristi se za session rezoluciju;
- ostala postojeća metadata polja mogu se čuvati kao poznata opciona polja kada ih `ReportService` može deterministički mapirati.

`tasks` mora biti neprazna lista stringova. `unassigned` je specijalni token i smije biti jedini element. Kombinacija `unassigned` sa drugim taskovima je invalidna. Task tokeni se ne tumače fuzzy po naslovu.

Nepoznata dodatna YAML polja ne ruše v1 parser: ignorišu se uz warning, jer je front matter naprijed kompatibilan; ne kopiraju se u nove poslovne kolone. Duplikat poznatog ključa, root koji nije mapping, pogrešan tip, nevalidna enum vrijednost ili neispravan YAML znači `INVALID` bez DB mutationa.

`created_at` mora biti parsabilan timezone-aware ISO-8601. Naive timestamp, neparsabilan timestamp ili nedostatak polja odbija se; parser nikada ne koristi filesystem mtime ili trenutno vrijeme kao zamjenu. Syntactically valid timestamp je samo deklarisano authored vrijeme — ne treba ga predstavljati kao dokaz stvarnog vremena pisanja.

Repo trenutno nema YAML dependency (`pyproject.toml` ne navodi PyYAML/ruamel). Buduća implementacija treba jednu standardnu `PyYAML` zavisnost sa `safe_load` loaderom koji odbija duplicate keys; ne treba ručno pisati parcijalni YAML parser.

## 5. SessionTaskBinding rezolucija

Phase 1 binding istorija je autoritet; `AgentSession.task_id` i `AgentSession.plan_item_id` se ne koriste za istorijsku rezoluciju.

Ingestion za poznati `session_id` prvo provjerava da `AgentSession` postoji i pripada watcher projektu. Zatim za svaki `tasks` token radi samo exact-match preko istorijskih bindinga sesije:

1. `SessionTaskBinding.task_id` prema tačnom Task ID-ju;
2. `SessionTaskBinding.plan_item_id` prema tačnom PlanItem ID-ju;
3. za čitljiv konvencijski token poput `FLOW-017`, bindingov PlanItem `item_key` iz stvarnog povezanog PlanItem-a.

Ne pretražuju se task naslovi, trenutni session pointeri, vrijeme reporta ni „najbliži“ binding.

Ako jedan token mapira na jedan logički PlanItem/Task target, svi istorijski binding segmenti tog istog exact targeta mogu se uključiti; to je deterministički način da se obuhvati switch A → B → A. Ako isti token mapira na više različitih PlanItem ID-jeva ili više nepovezanih Task targeta, rezolucija je `NEEDS_LINK` i ne pravi se nijedan link. Cijela rezolucija mora biti završena prije mutationa, ili u jednoj transakciji, da ne ostanu parcijalni linkovi.

Primjer `tasks: [FLOW-017, FLOW-018]` može povezati više jedinstvenih targeta i više njihovih historijskih segmenata. Ako sesija ima još bindinga koji nisu navedeni, oni se ne dodaju implicitno.

`tasks: [unassigned]` znači poznata sesija bez task-scoped dokaza: kreira se session-scoped `AgentReport` bez binding linkova. `session_id: unknown` i `unassigned` zajedno i dalje čekaju pouzdanu sesiju; `unassigned` nije dozvola za izmišljanje session konteksta.

Za svaki link ingestion poziva postojeći `ReportService.link_report_to_binding()`, koji u trenutku linkovanja snapshotuje `resolved_plan_item_id`. Time Phase 2 ne zaobilazi Phase 1 sigurnosni ugovor.

## 6. Naknadni MODIFIED događaji i immutable reporti

Filesystem MODIFIED je samo signal, ne dozvola za prepisivanje reporta. Nakon prvog uspješnog ingestiona `source_report_id` je immutable:

- isti ID i isti artifact → no-op;
- sadržaj promijenjen pod istim ID-jem → warning `IMMUTABLE_CONFLICT`, postojeći DB report ostaje netaknut;
- korekcija se piše kao novi Markdown report sa novim `report_id`.

Ako je prvi pokušaj bio `INVALID`, `NEEDS_IDENTITY` ili `NEEDS_LINK`, nema AgentReport reda i kasniji MODIFIED može pokušati ponovo. Ne uvoditi versioning, hash pipeline ni draft/final ingestion state da bi se riješio ovaj slučaj.

## 7. Greške i watcher izolacija

`WatcherPipeline._safe_callback()` već hvata callback izuzetke i loguje ih, a `_create_watcher_callback()` rollbackuje/close-uje svoju DB sesiju na grešci. Buduća ingestion grana treba imati dodatni lokalni boundary:

```text
FileActivity commit
try: parse → validate → resolve → create/link
except: warning + ingestion_outcome, bez propagacije u watcher
```

Ne koristiti `AgentReport.status` za ingestion stanje: `DRAFT/FINAL` je report review status. Ne dodavati `ingest_status` kolonu ili novu pending tabelu u Phase 2. Za audit se može koristiti postojeći `FileActivity.metadata_json` uz `report_candidate`, `source_report_id` i outcome (`INGESTED`, `INVALID`, `NEEDS_IDENTITY`, `NEEDS_LINK`, `IMMUTABLE_CONFLICT`), plus strukturisani warning log. To je metadata postojećeg activity toka, ne treći report sistem.

## 8. Preporučeni tok (jedna arhitektura)

```text
WatcherPipeline (postojeći, recursive project repo watcher)
  ↓
_create_watcher_callback()
  ↓
ActivityService → FileActivity (uvijek, normalni audit)
  ↓ samo repo_path/agent_reports/*.md i CREATED/MODIFIED
AgentReportIngestionService
  ↓
AgentReportFrontMatterParser (safe YAML, bez Markdown interpretacije)
  ↓
identity check: report_id + source path conflict/no-op
  ↓
session resolution (stvarni ID; unknown = NEEDS_LINK, bez DB reda)
  ↓
exact SessionTaskBinding resolution (ambiguous = bez mutationa)
  ↓
ReportService.create_draft(..., source metadata)
  ↓
ReportService.link_report_to_binding(...) za svaki potvrđeni segment
  ↓ jedna transakcija → postojeći AgentReport + Phase 1 BindingLinks
```

## 9. Minimalne izmjene baze za buduću implementaciju

Na postojeći `AgentReport` dodati samo:

| Polje | Zašto | Nullable/pravilo |
|---|---|---|
| `source_report_id` | stabilni identity iz YAML-a i idempotentni dedupe bez hash sistema | nullable radi legacy DB redova; unique/index kada nije NULL |
| `source_path` | provenance i dijagnostika konflikta/ponovljenog fajla | nullable radi postojećih i session-end reporta; nije identity |

Ne mijenjati `session_id` u nullable u ovoj fazi. Ne dodavati `ingest_status`, `ingested_at`, `source_modified_at`, `source_content_sha256`, report versioning ni novu pending tabelu. `report_type`, `work_status` i `AgentReportBindingLink.resolved_plan_item_id` već postoje iz Phase 1.

## 10. Minimalne nove klase/servisi

Samo dvije nove odgovornosti:

1. `AgentReportFrontMatterParser` — pure parser/validator koji vraća typed mapping i validacione greške.
2. `AgentReportIngestionService` — path candidate filter, identity check, session/binding rezolucija, atomicno pozivanje postojećeg `ReportService` i outcome logging/metadata.

Ne treba novi ORM report model, novi HTTP endpoint, novi watcher, novi event broker ni LLM adapter. Binding resolver može ostati privatna metoda ingestion servisa dok se ne dokaže reuse potreba.

## 11. Pravila za nejasne slučajeve

| Slučaj | Ishod |
|---|---|
| nema front matter / stari legacy Markdown | `LEGACY_NO_FRONT_MATTER`; ne ingestuje se |
| neispravan YAML ili poznato polje pogrešnog tipa | `INVALID`; nema DB mutationa |
| nema `report_id` | `NEEDS_IDENTITY`; nema DB mutationa |
| `session_id: unknown`/nepoznat ID | `NEEDS_LINK`; nema AgentReport reda |
| cross-project session ID | `NEEDS_LINK`/warning; nema mutationa |
| tasks token bez exact bindinga | `NEEDS_LINK`; nema parcijalnih linkova |
| ambiguous token ili više različitih targeta | `NEEDS_LINK`; ne pogađati |
| `tasks: [unassigned]` sa poznatom sesijom | ingest session reporta bez binding linkova |
| isti ID i već ingestovan isti artifact | idempotentni no-op |
| isti ID na drugom pathu ili MODIFIED nakon ingest-a | immutable conflict; postojeći red ostaje |
| `DELETED` | samo FileActivity; ne briše DB report automatski |

## 12. Šta ne treba praviti

- drugi watcher ili poseban observer za `agent_reports`;
- nullable/detached `AgentReport` samo radi `unknown` sessiona;
- treću report/pending tabelu;
- hash/dedupe pipeline, content versioning i mtime heuristiku;
- fuzzy task/session matching, izbor „najbližeg“ bindinga ili current-pointer fallback;
- LLM zaključivanje `work_status` ili report tipa;
- HTTP endpoint, SessionCompletionService wiring i Workflow Ledger;
- implementacijske zaključke (`IMPLEMENTATION_COMPLETED`, test/review događaje) u ovoj fazi.

## 13. Najmanji Phase 2 implementation scope

Nezavisno testabilan vertikalni komad treba obuhvatiti:

1. `PyYAML` runtime dependency i strict front-matter parser fixtures (valid, legacy/no-frontmatter, duplicate key, invalid YAML, unknown fields, naive timestamp, unknown session);
2. nullable `source_report_id` unique i nullable `source_path` na postojećem `AgentReport` + Alembic upgrade/downgrade;
3. `AgentReportIngestionService` sa atomicnim identity/session/binding pravilima;
4. mali hook u postojeći `_create_watcher_callback()` samo za `agent_reports/*.md`, bez drugog watchera;
5. testove za CREATED/MODIFIED debounce, idempotentni no-op, immutable conflict, rename/copy conflict, multi-binding, `unassigned`, `unknown` session i cross-project odbijanje;
6. dokaz da postojeći FileActivity, SessionCompletionService, EvidenceService, timeline i Phase 1 report/verdict tokovi ostaju zeleni.

## 14. Rizik i nezavisna verifikacija

GitNexus impact je pokazao:

- `WatcherPipeline`: LOW, jedan direktni importer (`composition_root.py`);
- `_create_watcher_callback`: LOW, jedan direktni caller i lifespan flow;
- `ActivityService`: LOW, dva direktna importera (`composition_root.py`, `project_timeline.py`);
- persistence `AgentReport`: MEDIUM, 5 direktnih importera uključujući `EvidenceService`, timeline, report service, persistence models i app; širi graf 27 pogođenih simbola.

Zbog toga će stvarna Phase 2 implementacija tražiti migracioni plan, parser fixture testove i punu `scripts/verify.py` provjeru. Ovaj report ne tvrdi da je bilo šta od toga implementirano.

## Završni verdict

RECOMMENDED DESIGN

Opcija A (`unknown` report čeka pouzdanu sesiju izvan DB `AgentReport` reda), stabilni YAML `report_id` kao identity, postojeći recursive watcher + poseban callback hook, strict deterministic parser i exact historical binding resolution je najmanji bezbjedan dizajn bez trećeg report sistema.
