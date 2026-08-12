---
flowos_report_version: 1
report_id: 3bbbcc10-8ef4-4714-afac-011c8f4f9ad2
agent: claude
model: claude-sonnet-5
session_id: unknown
report_type: analysis
tasks:
  - unassigned
commits: []
created_at: 2026-08-12T06:46:13+02:00
---

# FlowOS — Workflow Ledger Phase 3B — TEST_RESULT — read-only analiza

## Datum

2026-08-11 / 2026-08-12

## Agent / model / sesija

- Agent: Claude (Claude Code)
- Model: claude-sonnet-5
- Sesija: unknown

Napomena: nalog je tražio `agent: codex` u front matteru kao dio šablona
preuzetog iz prethodnih Codex izvještaja. Ovaj report je stvarno napisao
Claude, pa front matter navodi tačnog autora — netačna atribucija agenta bi
bila isti tip problema (fabrikovan metapodatak) koji je ova cijela Ledger
inicijativa eksplicitno napravljena da spriječi.

## Scope

Read-only arhitektonska analiza za "Workflow Ledger Phase 3B — TEST_RESULT".
Cilj je zaključati najmanji ispravan contract PRIJE implementacije. Nije
mijenjan kod, nije pravljena migracija, nije implementiran TEST_RESULT, nije
napravljen commit. Postojeći Ledger (Phase 3A) nije redizajniran.

Provjereno je stvarno stanje `main` HEAD-a `58771dbd6ce2e48ee2d481a71b5e4db099e14453`
(`git status --short --branch` potvrđuje čist working tree, `git rev-parse HEAD`
potvrđuje tačno navedeni commit).

## Pregledani izvori

- `src/flowos/service/services/verification/service.py` (kompletan fajl)
- svi stvarni pozivaoci `VerificationService.run_verify()` (grep nad `src/`):
  `src/flowos/service/services/sessions/completion.py`,
  `src/flowos/service/controllers/http/worktrees.py`
- `src/flowos/service/services/workflow/ledger.py`
- `src/flowos/service/services/infrastructure/persistence/workflow_ledger_models.py`
- `src/flowos/service/services/infrastructure/persistence/models.py`
  (`SessionEvent` model)
- `agent_reports/2026-08-11_workflow-ledger-phase-3a-implementation.md`,
  `agent_reports/2026-08-11_workflow-ledger-phase-3a-analysis.md`,
  `agent_reports/2026-08-11_workflow-ledger-phase-3a-independent-review.md`

---

## 1. Šta TEST_RESULT znači

Zaključano: `TEST_RESULT` znači SAMO da je konkretna mehanička/verifikaciona
komanda (`scripts/verify.py`) stvarno pokrenuta i proizvela konkretan
PASS/FAIL/TIMEOUT ishod. Ne znači da je implementacija ispravna, da je review
prošao, da je task VERIFIED ili DONE, niti da je korisnik prihvatio rezultat.
Ovo je simetrično sa `IMPLEMENTATION_COMPLETED` iz Phase 3A: oba su evidence
eventi jedne konkretne authority klase ("implementer tvrdi" vs. "mašina je
izmjerila"), nijedan nije workflow odluka.

---

## 2. `VerificationService` — stvarno stanje

`src/flowos/service/services/verification/service.py` pregledan u cjelosti.

### `run_verify()` potpis (VEĆ postoji, VEĆ prima session/project)

```python
def run_verify(
    self,
    repo_path: str,
    verify_path: str | None = None,
    session_id: str | None = None,
    project_id: str | None = None,
) -> VerificationResult:
```

**Ključna činjenica**: metoda VEĆ prima opcione `session_id`/`project_id` i
prosljeđuje ih dalje u `ArtifactStore.save()` za `metadata.json`. Problem nije
u `VerificationService` API-ju — problem je da ga postojeći pozivaoci ne
koriste.

### Stvarni pozivaoci (grep nad `src/`)

1. `src/flowos/service/services/sessions/completion.py:125-126`:
   ```python
   svc = VerificationService()
   verify_result = svc.run_verify(repo_path)
   ```
   Poziva se BEZ `session_id`/`project_id`, iako su OBA već u lokalnom scope-u
   funkcije u tom trenutku (`session_id` je parametar `complete_session()`,
   `project_id = session.project_id` je postavljen ranije u istoj funkciji).
   **Minimalna korekcija**: `svc.run_verify(repo_path, session_id=session_id,
   project_id=project_id)` — izmjena dvije linije, bez promjene potpisa
   `VerificationService`.

2. `src/flowos/service/controllers/http/worktrees.py:113-133`
   (`POST /worktrees/{worktree_id}/verify`):
   ```python
   verify_svc = VerificationService()
   result = verify_svc.run_verify(wt["worktree_path"])
   ```
   Takođe ne prosljeđuje `session_id`/`project_id`, iako `wt` (worktree
   record) vjerovatno ima `project_id` i eventualno `session_id` dostupne.
   Ovaj poziv NIJE vezan za `SessionCompletionService` tok i eksplicitno je
   van scope-a naloga ("Watcher ne učestvuje. AgentReport ingestion ne
   učestvuje." — implicitno, samo SessionCompletion wiring je u fokusu).
   Navodim ga kao POZNATU postojeću rupu, ne kao nešto što Phase 3B mora
   riješiti.

### Šta `VerificationResult` stvarno vraća

```python
@dataclass
class VerificationResult:
    artifact_id: str
    verify_path: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool
    success: bool  # exit_code == 0
    verified_at: str  # ISO timestamp
    artifact_path: str | None = None
```

`artifact_id` je `str(uuid.uuid4())`, generisan NA POČETKU `run_verify()`,
prije bilo kakvog pokušaja izvršavanja. `artifact_path` je `None` u DVA
slučaja koja nisu ista (vidi sekciju 7) — ovo je kritično za source
qualification.

### `artifact_id` kao stabilan source identity

Da — `artifact_id` je generisan jednom po `run_verify()` pozivu, nikad se ne
mijenja, i (kada je artifact stvarno sačuvan) direktno je i naziv direktorija
`artifacts/verification/<artifact_id>/`. Ovo je isti obrazac stabilnosti kao
`AgentReport.id` u Phase 3A — deterministički, jednom-dodijeljen, ne
podložan naknadnoj promjeni. Dovoljno je stabilan i deterministic za
`source_id`, POD USLOVOM da se TEST_RESULT piše samo kada `artifact_path is
not None` (vidi sekciju 7 — inače `source_id` pokazuje na artifact koji
fizički ne postoji).

---

## 3. Izvor TEST_RESULT eventa

Preporučeno i potvrđeno dovoljno:

```text
source_kind = "verification_artifact"
source_id   = VerificationResult.artifact_id
```

Ne treba nova Verification DB tabela. `ArtifactStore` već čuva raw evidence
(`command.txt`, `stdout.txt`, `stderr.txt`, `metadata.json`) na filesystem-u;
`WorkflowLedgerEvent` treba biti tanak, upitljiv snapshot činjenica iznad tog
artefakta — identičan odnos kao `AgentReport`/Markdown fajl u Phase 2. Ovo je
tačno ono što je Phase 3A analiza već predvidjela u sekciji "Kako
VerificationService kasnije ulazi u isti model" — sada potvrđeno da je taj
plan i dalje ispravan, bez potrebe za novom tabelom.

---

## 4. Ko piše TEST_RESULT

Backend-only authority ostaje. Preporuka: dodati `WorkflowLedgerService.
append_test_result(...)` kao NOVU javnu metodu pored postojeće
`append_implementation_completed_from_report(...)` — ne kao izmjena te
metode, ne kao novi framework. `VerificationService` ostaje čisto mehanička
komponenta (izvršava komandu, čuva artefakt, vraća rezultat) i ne smije
sam pisati u Ledger niti poznavati `WorkflowLedgerService`. Backend policy
(novi metod u `WorkflowLedgerService`) je taj koji `VerificationResult`
pretvara u `WorkflowLedgerEvent` — isti odvojen-odgovornosti obrazac kao
`AgentReportIngestionService` (mehanika/parsing) vs. `WorkflowLedgerService`
(policy) u Phase 3A.

Predloženi potpis:

```python
def append_test_result(
    self,
    *,
    project_id: str,
    session_id: str | None,
    result: VerificationResult,
) -> WorkflowLedgerEvent | None:
```

Vraća `None` (ne prazna lista, za razliku od `append_implementation_completed_
from_report` koji vraća listu jer može imati više targeta) ako rezultat ne
kvalifikuje za event (vidi sekciju 7) — TEST_RESULT ima uvijek najviše jedan
target (session-scoped), za razliku od `IMPLEMENTATION_COMPLETED` koji može
imati više (multi-task).

---

## 5. Scope TEST_RESULT-a — najvažnije pitanje

Analiza koda potvrđuje da `scripts/verify.py` provjerava CIJELI repo/worktree,
ne pojedinačan task. Sesija istovremeno može imati A→B→A binding istoriju
(Phase 1). Ne postoji nikakav mehanizam u `VerificationService` koji bi
mogao dokazati "ovaj verify run se odnosio TAČNO na Task X" — `verify.py`
nema svijest o taskovima, planovima ili binding segmentima.

**Preporuka: Opcija A — session/project scoped, bez task/plan_item
atribucije.**

```text
session_id = session koja je pokrenula verify
project_id = projekat sesije
task_id = NULL
plan_item_id = NULL
```

Razlog: bilo kakva task-level atribucija bi zahtijevala TVRDNJU da je verify
rezultat relevantan za trenutno aktivan (ili posljednji) binding segment
sesije — a to je upravo ista vrsta nagađanja koju je Phase 1/2/3A eksplicitno
zabranjivala (live/trenutni pokazivač kao istorijski autoritet). `verify.py`
ne zna niti izjavljuje na koji task se odnosi; FlowOS ne smije to izmišljati
u njegovo ime. Konzervativna Opcija A je jedina koja ne krši već uspostavljen
princip "ne izmišljaj atribuciju koju kod ne može dokazati" (identičan
principu iza `NEEDS_LINK` u Phase 2 i `resolved_plan_item_id` snapshot-a u
Phase 1).

Opcija B (deterministic task-target linkage) bi danas zahtijevala nagađanje
("posljednji aktivan binding u trenutku verify-ja") koje kod ne može
dokazati sa istom čvrstoćom kao AgentReportBindingLink (koji dolazi iz
eksplicitne YAML `tasks:` deklaracije agenta, ne iz nagađanja o vremenu).
Odbačeno za Phase 3B.

---

## 6. PASS i FAIL

TEST_RESULT mora nastati za OBA ishoda. `_derive`-tip logika ne smije filtrirati
samo uspješne rezultate — `payload.success` (bool) nosi informaciju, ne
odsustvo eventa. Ovo je direktno analogno tome da `IMPLEMENTATION_COMPLETED`
ne filtrira po nekom "kvalitetu" implementacije — event bilježi ČINJENICU
(mašina je izvršila, evo ishoda), ne VRIJEDNOSNI sud o ishodu.

---

## 7. Timeout i tehnički failure — precizna analiza

Pregledan `run_verify()` kod otkriva TRI različita, razdvojiva stanja, ne
dva:

### (a) Komanda se NIJE mogla izvršiti — `verify.py` ne postoji

```python
if not verify_file.is_file():
    return VerificationResult(..., exit_code=-1, ..., artifact_path=None)
```

Funkcija se vraća RANO, PRIJE bilo kakvog pokušaja `subprocess.run()` i PRIJE
`ArtifactStore.save()`. `artifact_id` JE generisan (fresh UUID), ali NIJE
sačuvan nijedan artefakt na disku za njega. `exit_code=-1` je sentinel, ne
stvaran subprocess return code.

### (b) Komanda JE izvršena i pala (uključujući TIMEOUT) — artefakt sačuvan

```python
except subprocess.TimeoutExpired:
    timed_out = True
    exit_code = -1
```

Ovdje je `subprocess.run()` STVARNO pokušan; timeout je stvaran mehanički
ishod (proces nije završio u roku), ne odsustvo pokušaja. `ArtifactStore.
save()` se poziva NORMALNO nakon ovog bloka — artefakt SE čuva, sa
`timed_out=True` u `metadata.json`. `exit_code=-1` je ovdje TAKOĐER sentinel
(subprocess nije vratio pravi kod jer je ubijen), ali za razliku od (a),
postoji stvaran `stderr` poruka i stvaran artefakt.

### (c) Komanda JE izvršena, artefakt NIJE sačuvan (save failure)

```python
try:
    store = ArtifactStore()
    artifact_path = store.save(...)
except Exception:
    logging...  # artifact_path ostaje None
```

`exit_code`/`stdout`/`stderr`/`timed_out` su SVI stvarni (subprocess je
stvarno izvršen), ali `artifact_path` ostaje `None` jer je upis na disk pao
(npr. disk pun, permission error). `VerificationResult` se i dalje vraća sa
stvarnim exit_code-om.

### Preporučeno pravilo za TEST_RESULT qualification

```text
TEST_RESULT se piše AKO I SAMO AKO:
  result.artifact_path is not None
```

Ovo ISKLJUČUJE slučaj (a) (verify.py nije pronađen — nema stvarnog izvršenja,
nema artefakta, nema šta da se referencira kao `source_id`) i slučaj (c)
(izvršeno, ali `source_id` bi pokazivao na artefakt koji fizički ne postoji —
isti princip kao "IMMUTABLE_CONFLICT ako source_path ne postoji" iz Phase 2:
Ledger event nikad ne smije referencirati artefakt koji backend ne može
garantovati da postoji). UKLJUČUJE slučaj (b): TIMEOUT je stvaran mehanički
ishod sa stvarnim artefaktom, pa TEST_RESULT MORA nastati za njega, sa
`payload.timed_out = true` i `payload.success = false`.

Postojeći `VERIFY_RESULT` `SessionEvent` (vidi sekciju 14) OSTAJE jedini
zapis za slučajeve (a) i (c) — session timeline i dalje vidi "pokušali smo,
evo šta se desilo", čak i kad Ledger namjerno ne dobija durable evidence
event jer backend ne može garantovati da artefakt postoji.

---

## 8. `occurred_at`

Preporučeno: `WorkflowLedgerEvent.occurred_at = VerificationResult.
verified_at` (parsirano u `datetime` — `verified_at` je već `finished_at`,
`datetime.now(tz=UTC).isoformat()` izračunat NAKON što je subprocess
završio/timeout-ovao, dakle stvaran, timezone-aware, backend-izmjeren
trenutak završetka provjere — ne trenutak poziva `run_verify()`, ne
filesystem mtime). Ovo je analogno `AgentReport.created_at` u Phase 3A
(backend-validated trenutak, ne authored/claimed trenutak).

`recorded_at` ostaje `datetime.now(tz=UTC)` u trenutku Ledger append-a,
identično Phase 3A obrascu.

---

## 9. Payload — preporučen minimalni sadržaj

```json
{
  "artifact_id": "...",
  "verify_path": "...",
  "exit_code": 0,
  "success": true,
  "timed_out": false,
  "duration_seconds": 12.3,
  "artifact_path": "...",
  "command": "..." 
}
```

`command` je pouzdano dostupan (`VerificationResult` ga ne vraća direktno,
ali `run_verify()` ga lokalno konstruiše kao `f"{sys.executable} {verify_file}"`
prije poziva `ArtifactStore.save()` — dostupan je bilo kroz malu izmjenu da
se doda na `VerificationResult` dataclass, bilo da payload writer prihvati
`command` kao dodatni parametar od pozivaoca). Ne stavljati `stdout`/`stderr`
sirovi tekst u payload — ostaju isključivo u `ArtifactStore` (već postoji
1MB ograničenje po fajlu tamo). `session_id`/`project_id` ne moraju biti U
payload-u jer su već prve-klase kolone na `WorkflowLedgerEvent` (isti obrazac
kao `IMPLEMENTATION_COMPLETED` gdje su `task_id`/`plan_item_id` kolone, a
payload nosi dodatne detalje).

---

## 10. Hashovi

`VerificationResult` NE vraća `stdout_sha256`/`stderr_sha256` direktno —
provjereno čitanjem dataclass-a, ta polja postoje SAMO unutar
`ArtifactStore.save()`-ovog lokalnog `metadata` dict-a, izračunata tamo i
upisana u `metadata.json`, nikad vraćena pozivaocu.

Tri opcije, ocijenjene:

1. Izračunati hash iz `result.stdout`/`result.stderr` DIREKTNO u
   `WorkflowLedgerService.append_test_result()` — `VerificationResult` VEĆ
   ima `stdout`/`stderr` kao stringove u memoriji u trenutku poziva (isti
   poziv koji je upravo završio `run_verify()`), pa je ovo `hashlib.sha256(...)`
   poziv bez ikakvog dodatnog filesystem I/O. Ovo JE najmanje rješenje.
2. Pročitati nazad `metadata.json` sa diska — dupliran filesystem read
   nepotreban kad su isti bajtovi već u memoriji u istom pozivnom stack-u.
   Odbačeno.
3. Ne uključivati hash u Phase 3B payload, ostaviti ga samo u raw artefaktu —
   validna minimalna opcija ako se želi izbjeći i najmanji dodatni kod.

**Preporuka: Opcija 1 ako se hash uopšte želi u payload-u** (izračunati iz
već-u-memoriji `result.stdout`/`result.stderr`, isti algoritam kao
`ArtifactStore`, bez čitanja diska) — ali ovo NIJE obavezno za minimalni
Phase 3B; sasvim je prihvatljivo (i jednostavnije) ostaviti hash isključivo u
`metadata.json` za Phase 3B i dodati ga u payload tek ako se pokaže stvarna
potreba (npr. budući projection sloj koji uspoređuje sadržaj bez čitanja
artefakta). Ne praviti duplo filesystem parsiranje ni u kom slučaju.

---

## 11. Idempotency

Predložen ključ:

```text
workflow-ledger:v1:TEST_RESULT:verification_artifact:{artifact_id}
```

Ovo je DIREKTNO analogno Phase 3A formatu
(`workflow-ledger:v1:IMPLEMENTATION_COMPLETED:agent_report:{report_id}:
{target_kind}:{target_id}`), samo bez `{target_kind}:{target_id}` sufiksa jer
TEST_RESULT nema multi-target grupisanje (uvijek tačno jedan
session/project-scoped event po artefaktu, vidi sekciju 5). Postojeći DB
`UniqueConstraint` na `idempotency_key` (Phase 3A migracija) je dovoljan —
nije potrebna nova migracija niti novo polje. `artifact_id` je fresh UUID po
`run_verify()` pozivu (isti obrazac kao `AgentReport.id` u Phase 3A), pa je
retry-safe iz istog razloga kao Phase 3A idempotency (vidi Phase 3A
independent review, sekcija 10, gdje je ovaj tačan obrazac probom potvrđen
ispravnim).

---

## 12. Transaction boundary — filesystem artefakt prije DB zapisa

Ovo je stvarno drugačiji problem od Phase 3A/2 ingestiona. Kod Phase 2/3A,
`AgentReport`+`AgentReportBindingLink`+`WorkflowLedgerEvent` su SVI DB redovi
u ISTOJ transakciji — rollback čisto uklanja sve. Ovdje, `ArtifactStore.save()`
je FILESYSTEM operacija koja se dešava PRIJE ijednog DB poziva i koju SQL
rollback ne može poništiti — `run_verify()` (uključujući `ArtifactStore.save()`)
se poziva PRIJE nego što se `WorkflowLedgerService.append_test_result()`
uopšte pozove.

Analiza posljedica:

```text
verify artifact uspješno sačuvan (filesystem, nepovratno)
↓
Ledger append padne (DB exception)
```

Ovo NIJE isti rizik kao "izgubljen report" u Phase 3A, jer:

- Artefakt OSTAJE na disku kao raw evidence, bez obzira na DB ishod — ovo je
  POŽELJNO, ne problem (isto kao što `agent_reports/*.md` fajl ostaje na
  disku i ako ingestion padne).
- Ako CIJELA `SessionCompletionService.complete_session()` transakcija
  rollback-uje (npr. neki KASNIJI korak u istoj funkciji baci grešku), ono
  što se gubi je DB red (`WorkflowLedgerEvent`, `SessionEvent`, `AgentSession`
  update itd.) — NE filesystem artefakt, koji je već nepovratno zapisan prije
  bilo kog DB poziva.
- `artifact_id` je stabilan i deterministic, pa je retry bezbjedan: naredni
  poziv (npr. ručni retry, ili buduća reconciliation provjera) može pozvati
  `append_test_result()` OPET sa ISTIM `artifact_id`-jem (ako se čuva negdje,
  npr. u logu ili u `SessionEvent.payload_json` koji VEĆ postoji — vidi
  sekciju 14) — idempotency_key osigurava da se ne napravi duplikat, tačno
  isti mehanizam kao Phase 3A.

**Preporučeno najmanje pouzdano ponašanje**: ne praviti nikakav
queue/broker/retry engine. Osloniti se na to da:

1. Artefakt je uvijek jeftino re-referenciran preko `artifact_id`, koji je
   VEĆ zapisan u `VERIFY_RESULT` `SessionEvent.payload_json` (postojeće
   ponašanje, nepromijenjeno).
2. Ako `append_test_result()` padne, greška se hvata lokalno (analogno
   `try/except Exception: logger.warning(...)` obrascu koji `completion.py`
   VEĆ koristi za resume regeneraciju i websocket emit-ove — vidi sekciju 13),
   NE ruši cijeli `complete_session()` poziv.
3. Deterministic retry nije potreban kao AUTOMATSKI mehanizam u Phase 3B —
   dovoljno je da je STRUKTURNO moguć (isti `artifact_id` uvijek daje isti
   `idempotency_key`, pa bilo koji budući poziv — ručni, GUI dugme,
   reconciliation job — može bezbjedno pozvati `append_test_result()` ponovo
   bez dupliranja). Ovo zadovoljava "preferiraj deterministic retry na
   osnovu stabilnog artifact_id, a ne queue/broker" iz naloga bez dodatne
   infrastrukture.

---

## 13. SessionCompletion wiring — tačno mjesto

Preporučen redoslijed (minimalna izmjena unutar postojeće funkcije, iste
transakcije, istog `db.commit()` na kraju kao i sav ostali Phase 3A
zadržani kod):

```text
VerificationService.run_verify(repo_path, session_id=session_id, project_id=project_id)
↓
VerificationResult (sa exit_code/success/timed_out/artifact_path)
↓
[NEPROMIJENJENO] emituj verification.completed websocket event
↓
[NEPROMIJENJENO] kreiraj VERIFY_RESULT SessionEvent
↓
[NOVO] WorkflowLedgerService(self._db).append_test_result(
           project_id=project_id, session_id=session_id, result=verify_result)
↓
[NEPROMIJENJENO] self._db.flush() / nastavak funkcije
```

Poziv ide TAČNO tamo gdje danas postoji blok "Emituj WebSocket događaj" +
"Zabeleži VERIFY_RESULT kao SessionEvent" (linije ~133-168 trenutnog
`completion.py`), odmah NAKON kreiranja `SessionEvent` reda, PRIJE nego što
se `session.status` izvede i `self._db.flush()` pozove. Ovo drži Ledger
append u ISTOJ DB transakciji kao ostatak completion toka (jedan
`self._db.commit()` na kraju funkcije), konzistentno sa Phase 3A obrascem
gdje je Ledger uvijek dio pozivaočeve transakcije, ne zaseban commit.

Watcher i `AgentReportIngestionService` NE učestvuju — potvrđeno da
`VerificationService` nema veze s watcher tokom (samo `completion.py` i
`worktrees.py` je pozivaju, oba HTTP/session-tok, ne filesystem-event tok).

---

## 14. Odnos `SessionEvent VERIFY_RESULT` vs. `WorkflowLedgerEvent TEST_RESULT`

Preporučen koncept (potvrđen modelima): **SessionEvent = session timeline,
WorkflowLedgerEvent = durable workflow evidence.** Ovo NIJE proizvoljna
preferencija — potvrđeno je strukturnom razlikom u samim modelima:

- `SessionEvent.session_id` je `nullable=False`, `ForeignKeyConstraint(...,
  ondelete="CASCADE")` — event NESTAJE kad sesija nestane. Nema `project_id`
  kolone niti indeksa — ne može se upitati "svi test rezultati projekta X"
  bez join-a kroz `AgentSession`.
- `WorkflowLedgerEvent.session_id` je nullable, `ondelete="SET NULL"` —
  event PREŽIVLJAVA brisanje sesije (potvrđeno probom u Phase 3A independent
  review-u). Ima `project_id` kao prvoklasnu, indeksiranu kolonu.

Preklapanje (oba bilježe "verify je urađen, evo ishoda") je OPRAVDANO, ne
duplikacija koju treba ukloniti refactor-om — isti podatak služi dvije
različite svrhe (kratkoročna dijagnostika u UI session timeline-u naspram
dugoročne, project-scoped workflow evidencije). Ne brisati `VERIFY_RESULT`
`SessionEvent`; ne pokušavati ga zamijeniti sa `WorkflowLedgerEvent` upitima
u Phase 3B.

---

## 15. Verification artifact metadata — šta ostaje gdje

`ArtifactStore.metadata.json` sadrži: `artifact_id`, `session_id`,
`project_id`, `command`, `working_directory`, `started_at`, `finished_at`,
`duration_ms`, `exit_code`, `timed_out`, `status`, `stdout_sha256`,
`stderr_sha256`, `tool_version`, `python_executable`.

Podjela:

- **Ostaje SAMO u artefaktu** (source of truth, ne kopirati u Ledger):
  `stdout.txt`/`stderr.txt` sirovi sadržaj, `working_directory`,
  `tool_version`, `python_executable`, `started_at` (Ledger koristi samo
  `finished_at`/`verified_at` kao `occurred_at`).
- **Snapshotuje se u Ledger payload** (sekcija 9): `artifact_id`,
  `verify_path`, `exit_code`, `success`, `timed_out`, `duration_seconds`,
  `artifact_path`, opciono `command`.
- Cilj — "koji test je pokrenut i kakav je rezultat" — je zadovoljen bez
  kopiranja cijelog artefakta u DB red; upit nad Ledger-om je dovoljan za
  pregled istorije, a artefakt ostaje dostupan preko `artifact_path`/
  `artifact_id` za dubinsku dijagnostiku.

---

## 16. Task attribution kasnije — bez lažnog FK-a

Ako TEST_RESULT ostane session-scoped (`task_id=NULL`, `plan_item_id=NULL`,
preporučeno u sekciji 5), budući review/projection sloj MOŽE (bez ikakve
Phase 3B implementacije sada) povezati:

```text
IMPLEMENTATION_COMPLETED.session_id == TEST_RESULT.session_id
IMPLEMENTATION_COMPLETED.occurred_at <= TEST_RESULT.occurred_at (isti session, hronologija)
```

preko UPITA (query-time join po `session_id` + vremenski prozor), NE preko
tvrdog FK-a između dva Ledger event reda. Ovo čuva razdvojenost: Ledger ne
tvrdi da zna vezu koju ne može dokazati, ali podaci postoje da BUDUĆI
read/projection sloj (eksplicitno van scope-a i Phase 3A i Phase 3B) može
prezentovati "za ovu sesiju: implementacija tvrđena u T1, test rezultat u
T2" bez izmišljanja da je T2 dokazano O tačno istom tasku kao T1. Ne
implementirati ovu projekciju sada.

---

## 17. Ne mijenjati PlanItem status

Potvrđeno kao apsolutan zahtjev, dosljedan Phase 3A cutover-u: TEST_RESULT
(bilo PASS bilo FAIL) NE smije pozvati `PlanProgressService.validate_
transition()` niti bilo koji drugi mehanizam koji mijenja `PlanItem.status`.
`WorkflowLedgerService.append_test_result()` ne treba (i ne smije) importovati
`PlanProgressService` — isti obrazac provjere kao što je Phase 3A independent
review potvrdio grep-om da `completion.py` više ne importuje taj servis.

---

## 18. `ReportService.set_verdict()` dug

Potvrđeno, nedirano, ostaje van scope-a. Isti authority-cutover dug naveden u
Phase 3A analizi i independent review-u (`NEEDS_WORK`/`REJECTED` → PlanItem
`IN_PROGRESS`) — kandidat za budući `USER_VALIDATION`/`TASK_DECISION` cutover,
ne za Phase 3B.

---

## 19. Da li treba nova migracija?

**Ne.** `WorkflowLedgerEvent` (Phase 3A) već ima sva potrebna polja:
`event_type` (proizvoljan string, app-level validacija, nema DB CHECK enum —
"TEST_RESULT" se prosto dodaje kao nova dozvoljena vrijednost u service-layer
skupu, bez schema izmjene), `session_id`/`task_id`/`plan_item_id` (svi već
nullable), `source_kind`/`source_id` (već generični stringovi, dizajnirani u
Phase 3A analizi eksplicitno da izbjegnu polymorphic FK i da mogu nositi
buduće izvore bez nove tabele), `occurred_at`/`recorded_at`, `idempotency_key`
(već `UniqueConstraint`), `payload_json` (već `NOT NULL Text`). Nema potrebe
za novom kolonom niti novom migracijom.

---

## 20. Failure/retry test plan

Preporučeni testovi (integration, stvaran ORM/SQLite, ne mock onoga što se
dokazuje — isti standard kao Phase 3A):

1. PASS verify rezultat → tačno jedan `TEST_RESULT` event, `payload.success
   == true`.
2. FAIL verify rezultat (exit_code != 0) → `TEST_RESULT` event,
   `payload.success == false`.
3. Timeout → `TEST_RESULT` event sa `payload.timed_out == true`,
   `payload.success == false`, `artifact_path` postoji.
4. `verify.py` nije pronađen → NEMA `TEST_RESULT` eventa (artifact_path je
   `None`), ali `VERIFY_RESULT` `SessionEvent` i dalje nastaje.
5. Isti `artifact_id` retry (poziv `append_test_result()` dva puta za isti
   rezultat) → nema duplikata, isti event vraćen (analogno Phase 3A F2
   nalazu — ovaj test treba postojati OD POČETKA za Phase 3B, ne dodavati ga
   naknadno kao fix).
6. `session_id`/`project_id` na eventu odgovaraju sesiji koja je pokrenula
   verify.
7. `task_id`/`plan_item_id` su `NULL` čak i kad sesija ima aktivan/istorijski
   task binding — potvrđuje da nema nagađane atribucije (direktan test
   protiv principa iz sekcije 5).
8. `source_kind == "verification_artifact"`, `source_id == artifact_id`.
9. `occurred_at == VerificationResult.verified_at` (parsirano), ne trenutna
   vremena poziva testa.
10. Payload sadrži tražena polja (sekcija 9), ne sadrži sirovi stdout/stderr.
11. Ledger append failure (monkeypatch `append_test_result` da baci grešku,
    isti obrazac kao Phase 3A `test_ledger_failure_rolls_back_report_links_
    and_events`) → DB red za `WorkflowLedgerEvent` ne postoji nakon rollback-a,
    ALI artefakt (filesystem) i `VERIFY_RESULT` `SessionEvent` (ako je već
    committed u prethodnom koraku iste transakcije — provjeriti stvaran
    redoslijed flush/commit granica u `completion.py` prije pisanja ovog
    testa) ostaju netaknuti prema stvarnom commit rasporedu.
12. Ponovni poziv nakon (11) sa istim `artifact_id`-jem uspije bez duplikata.
13. PASS ne mijenja `PlanItem.status` (direktan test, analogno Phase 3A
    `test_verify_pass_does_not_mark_plan_item_verified_but_keeps_verify_event`,
    ali sada eksplicitno provjeravajući i da TEST_RESULT event postoji).
14. FAIL ne mijenja `PlanItem.status` (isti oblik testa za FAIL granu).

---

## 21. Blast radius — očekivani fajlovi

Mali diff, isti red veličine kao Phase 3A:

- `src/flowos/service/services/workflow/ledger.py` — dodati
  `append_test_result()` (novi metod, postojeći
  `append_implementation_completed_from_report` nedirano).
- `src/flowos/service/services/sessions/completion.py` — dvije izmjene:
  (1) proslijediti `session_id`/`project_id` u postojeći `run_verify()` poziv;
  (2) dodati poziv `WorkflowLedgerService(...).append_test_result(...)` na
  mjestu opisanom u sekciji 13.
- `src/flowos/service/services/verification/service.py` — VJEROVATNO
  NEPOTREBNO mijenjati (potpis `run_verify()` VEĆ prima `session_id`/
  `project_id`); jedina moguća sitna izmjena je dodavanje `command: str` polja
  na `VerificationResult` dataclass ako se payload odluči uključiti `command`
  (sekcija 9) — opciono, ne obavezno za minimalni Phase 3B.
- `tests/integration/test_workflow_ledger_phase3b.py` (novi fajl, analogno
  Phase 3A imenovanju).
- `tests/unit/test_session_completion.py` — dopuna sa PASS/FAIL ne-mijenja-
  status testovima za TEST_RESULT granu.

`src/flowos/service/services/reports/ingestion.py` se NE dira — potvrđeno da
watcher/ingestion tok nema nikakve veze sa verification tokom.

---

## Rizici i ograničenja

- `command` polje nije direktno dostupno na `VerificationResult` danas —
  minimalna dataclass izmjena ako se payload odluči da ga uključi (sekcija 9,
  21); nije blokirajuće ako se `command` jednostavno izostavi iz Phase 3B
  payload-a.
- `worktrees.py` `POST /worktrees/{id}/verify` endpoint ostaje bez Ledger
  wiring-a u Phase 3B — poznato, namjerno ograničenje (nije session-completion
  tok), ne regresija.
- Ako se ikad odluči da TEST_RESULT treba task-level atribuciju (Opcija B iz
  sekcije 5), to zahtijeva prvo dokazivo rješenje "na koji binding segment se
  verify odnosio" koje danas ne postoji — ne graditi ga unaprijed bez
  konkretnog dokaza potrebe.

## Odbačene opcije

Opcija: task/plan_item atribucija zasnovana na trenutno aktivnom
`SessionTaskBinding` u trenutku verify-ja.
Zašto odbačeno: to bi bio isti tip nagađanja (live/trenutni pokazivač kao
istorijski dokaz) koji su Phase 1/2/3A eksplicitno uklonili; `verify.py` ne
deklariše na koji task se odnosi.
Kada ponovo otvoriti: samo ako se uvede eksplicitan, agent-deklarisan
mehanizam (npr. YAML `verify_target:` polje) koji čini atribuciju dokazivom,
ne nagađanom.

Opcija: nova `VerificationArtifact` DB tabela.
Zašto odbačeno: `ArtifactStore` filesystem + `WorkflowLedgerEvent` payload
su dovoljni; nema dokaza da upit nad filesystem artefaktima kroz
`artifact_id`/`artifact_path` nije dovoljan za Phase 3B potrebe.
Kada ponovo otvoriti: ako budući GUI/read model treba efikasno pretraživanje
po sadržaju artefakta (npr. full-text stdout search) koje filesystem ne
može ponuditi bez sken svakog fajla.

Opcija: brisanje/zamjena `VERIFY_RESULT` `SessionEvent` sa
`WorkflowLedgerEvent TEST_RESULT`.
Zašto odbačeno: različite svrhe (session timeline vs. durable project-scoped
evidence), različita FK/retention semantika, opravdano preklapanje.
Kada ponovo otvoriti: ne preporučuje se.

Opcija: queue/retry engine za Ledger append failure poslije artefakt save-a.
Zašto odbačeno: `artifact_id` je već stabilan i idempotency_key već
sprečava duplikat; deterministic retry je strukturno moguć bez dodatne
infrastrukture.
Kada ponovo otvoriti: samo ako se pokaže stvarna operativna potreba za
automatskim retry-jem, ne unaprijed.

## Konflikti/kontradiktorni izvori

Nema kontradikcije u nalogu. Jedina nijansa vrijedna eksplicitnog navođenja:
`run_verify()` VEĆ ima `session_id`/`project_id` parametre (nalog je
pretpostavio da bi to moglo biti tako i tražio da se to provjeri) — potvrđeno
DA jesu prisutni u potpisu, ali NIJESU korišteni od strane
`SessionCompletionService`. Minimalna korekcija je dvije linije, ne izmjena
`VerificationService` API-ja.

## Potreban follow-up

Implementacija Phase 3B (poslije korisničke potvrde ovog contracta):

1. `WorkflowLedgerService.append_test_result()`.
2. Dvolinijska izmjena `completion.py` da proslijedi `session_id`/`project_id`
   u `run_verify()`.
3. Wiring poziva `append_test_result()` na tačno mjesto iz sekcije 13.
4. Testovi iz sekcije 20.
5. Independent review prije commita, isti standard kao Phase 3A.

## Potrebna korisnička potvrda

Potrebna je potvrda da Phase 3B prihvata:

- TEST_RESULT je session/project-scoped, BEZ task/plan_item atribucije
  (Opcija A, sekcija 5) — ovo je najvažnija odluka u ovom dokumentu i
  jedina gdje postoji stvarna alternativa (Opcija B) koju je neko mogao
  preferirati;
- TEST_RESULT se piše samo kad `artifact_path is not None` (sekcija 7) —
  "verify.py nije pronađen" NE proizvodi Ledger event;
- nema nove migracije;
- `VERIFY_RESULT` `SessionEvent` ostaje nepromijenjen i paralelan, ne
  zamijenjen.

## Verdict

RECOMMENDED PHASE 3B DESIGN

### A. TEST_RESULT semantics

Evidence da je `scripts/verify.py` mehanički izvršen i proizveo
PASS/FAIL/TIMEOUT ishod. Nije workflow odluka, nije dokaz ispravnosti,
review-a, VERIFIED statusa niti korisničkog prihvatanja.

### B. Source identity

```text
source_kind = "verification_artifact"
source_id   = VerificationResult.artifact_id
```

Uslov: piše se samo kad `result.artifact_path is not None` (stvaran,
persistovan artefakt postoji).

### C. Scope / target attribution

Session/project-scoped. `task_id = NULL`, `plan_item_id = NULL`, uvijek, u
Phase 3B. Nema nagađane task atribucije.

### D. Writer

`WorkflowLedgerService.append_test_result(*, project_id, session_id, result)`
— nova metoda, postojeća `append_implementation_completed_from_report`
nedirana. `VerificationService` ostaje čisto mehanički, ne piše u Ledger.

### E. Payload

`artifact_id`, `verify_path`, `exit_code`, `success`, `timed_out`,
`duration_seconds`, `artifact_path`, opciono `command`. Bez sirovog
stdout/stderr; hash opcion (sekcija 10), nije obavezan za minimalni scope.

### F. Idempotency

```text
workflow-ledger:v1:TEST_RESULT:verification_artifact:{artifact_id}
```

Postojeći DB `UniqueConstraint` na `idempotency_key` dovoljan, bez nove
migracije.

### G. Transaction / retry semantics

Artefakt (filesystem) nastaje prije Ledger DB zapisa i nije rollback-ovan SQL
transakcijom — to je namjerno i ispravno (raw evidence preživljava DB
neuspjeh). Ledger append je dio iste DB transakcije kao ostatak
`complete_session()`; ako padne, hvata se lokalno (`try/except`, log
warning) bez rušenja cijele funkcije, po istom obrascu koji `completion.py`
već koristi za resume regeneraciju. Retry je strukturno besplatan
(idempotency_key + stabilan artifact_id) bez potrebe za queue/broker.

### H. SessionCompletion wiring

Poziv `append_test_result()` odmah nakon kreiranja `VERIFY_RESULT`
`SessionEvent`, unutar iste `complete_session()` transakcije, prije finalnog
`self._db.commit()`. Watcher i `AgentReportIngestionService` ne učestvuju.

### I. Test plan

14 testova iz sekcije 20, uključujući explicit PASS/FAIL/TIMEOUT/not-found
razdvajanje, idempotency retry, no-task-attribution provjeru i
transaction-rollback scenario.

### J. Files expected to change

`workflow/ledger.py`, `sessions/completion.py`, novi
`tests/integration/test_workflow_ledger_phase3b.py`, dopuna
`tests/unit/test_session_completion.py`. `verification/service.py`
vjerovatno nepotreban za dirati. `reports/ingestion.py` se ne dira.

### K. Explicit non-goals

Nema nove migracije. Nema task/plan_item atribucije za TEST_RESULT u ovoj
fazi. Nema brisanja/zamjene `VERIFY_RESULT` `SessionEvent`-a. Nema
queue/broker/retry frameworka. Nema PlanItem status promjene za PASS ni FAIL.
Nema izmjene `ReportService.set_verdict()`. Nema wiring-a za
`worktrees.py` verify endpoint. Nema projection/GUI sloja za povezivanje
`IMPLEMENTATION_COMPLETED` i `TEST_RESULT` (samo query-time mogućnost
opisana u sekciji 16, ne implementirana sada).
