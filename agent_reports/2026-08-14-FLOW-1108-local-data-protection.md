---
flowos_report_version: 1
report_id: 637b7008-735c-46e5-9c32-21919616e192
agent: claude
model: claude-sonnet-5
session_id: unknown
report_type: implementation
work_status: completed
tasks:
  - FLOW-1108
commits: []
created_at: 2026-08-14T17:05:33+02:00
---

# FLOW-1108 — Zaštita lokalnih FlowOS podataka

**Nije commitovano. Nije pushovano.** (eksplicitan zahtjev zadatka)

## BASELINE HEAD

```
d059ffc8ed4c9e0367776ee1f50a24bf1850b95a
```

Working tree je bio čist na početku, potvrđeno prije bilo kakve izmjene.

## FLOWOS DATA ROOT

```
%LOCALAPPDATA%/FlowOS  (app_paths.get_flowos_root(), novi export)
```

Rekognosciranje je pronašlo REALNU (ne aspiracionu) upotrebu sljedećih putanja:

| Namjena | Stvarna putanja | Modul |
|---|---|---|
| RUNTIME DIR | `%LOCALAPPDATA%/FlowOS/runtime/` | `runtime.py::RuntimeManager.DESCRIPTOR_DIR` (`app_paths.get_runtime_dir()`) |
| DATABASE DIR | `%LOCALAPPDATA%/FlowOS/data/` | `persistence/engine.py::get_data_directory()` |
| LOG DIR | `%LOCALAPPDATA%/FlowOS/logs/` | `logging.py::setup_logging()` default |
| BACKUP DIR | `%LOCALAPPDATA%/FlowOS/data/backups/schema-repair-{stamp}-{uuid}/` | `persistence/schema_repair.py::create_schema_backup()` |
| ARTIFACT DIR | — | `app_paths.get_artifacts_dir()` je deklarisan, ali NEMA nijednog pozivaoca u cijelom kodu (grep potvrđen) |

Otkriveno tokom rekognosciranja (ne mijenjano, dokumentovano kao future-task nalaz):
`app_paths.py::ensure_directories()` nikad se ne poziva iz produkcijskog koda; `get_data_directory()`
u `persistence/engine.py` i default `log_dir` u `logging.py` računaju istu efektivnu putanju
NEZAVISNO od `app_paths.py` (dvije paralelne, u praksi identične kalkulacije `%LOCALAPPDATA%`).
Objedinjavanje ovih kalkulacija je van scope-a FLOW-1108 — hardening je vezan direktno za
STVARNE `.mkdir()` pozive u svakom modulu, ne za neiskorišćeni `ensure_directories()`.

## WINDOWS ACL APPROACH

Novi modul: `src/flowos/service/services/infrastructure/dir_security.py`

- Koristi VEĆ postojeću `pywin32` zavisnost (`pyproject.toml:35`, nije dodana nova) za
  stabilan SID trenutnog korisnika (`win32security.GetTokenInformation(token, TokenUser)`
  → `ConvertSidToStringSid`) — NE lokalizovano korisničko ime.
- ACL izmjena ide preko strogo kontrolisanog `icacls` subprocess poziva: argument-list
  (nikad shell string), `shell=False` (default, nikad eksplicitno True), path je JEDAN
  element liste.
- Dozvoljeni principal-i: trenutni korisnik (SID), `S-1-5-18` (SYSTEM), `S-1-5-32-544`
  (Administrators) — svi well-known, locale-nezavisni SID-ovi.
- Eksplicitno uklonjeni: `S-1-1-0` (Everyone), `S-1-5-32-545` (Users), `S-1-5-11`
  (Authenticated Users).
- **Dvokoračan mehanizam** (kritično, vidi FINDINGS #F1108-CRIT ispod za razlog):
  1. `path` sam se hardenuje eksplicitno (bez `/T`) — `/inheritance:r` + `/grant:r` sa
     `(OI)(CI)F` (container-inherit, za buduću djecu) + `/remove:g` širokih principala.
  2. Postojeća djeca (`path\*` wildcard, BEZ da dirne `path` sam) se resetuju
     (`/reset /T /L`) da nasljede TEK postavljen ACL sa koraka 1.
- `/L` flag sprečava da `/T` rekurzija prati eventualni directory junction unutar `path`
  u njegov cilj — empirijski potvrđeno (§ FINDINGS).
- Fail-closed: `DirectoryHardeningError` se NIKAD ne guta; SID lookup failure, icacls
  nonzero exit i subprocess greška svi eksplicitno raise-uju.

## RUNTIME PROTECTION

**PASS.** `RuntimeManager.write_descriptor()` poziva `ensure_private_directory(self.DESCRIPTOR_DIR)`
UMJESTO bare `mkdir()`, PRIJE bilo kakvog upisa descriptor JSON-a (koji od FLOW-1107 nosi
API bearer token). Redoslijed dokazan testom
`TestRuntimeWiring::test_descriptor_not_written_if_hardening_fails` — kad hardening baci,
`DESCRIPTOR_FILE` nikad ne postoji na disku.

## DATABASE DIRECTORY PROTECTION

**PASS.** `persistence/engine.py::get_data_directory()` poziva `ensure_private_directory(base)`
umjesto bare `mkdir()`. Štiti CIJELI direktorijum (ne samo `.db` fajl), pa `.db`/`-wal`/`-shm`
fajlovi koje SQLite kreira nasljeđuju istu privatnu granicu (dokazano
`TestDatabaseDirectoryWiring::test_get_data_directory_invokes_hardening`).
`create_sqlite_engine()`-ov drugi, generički `db_path.parent.mkdir(...)` (za eksplicitno
prosleđene/test putanje) je namjerno NEDIRAN — sprečava da testovi sa proizvoljnim temp
putanjama slučajno udare o FlowOS-root validaciju.

## LOG DIRECTORY PROTECTION

**PASS.** `logging.py::setup_logging()` poziva `ensure_private_directory(log_dir)` SAMO kad
je `log_dir` default (nije eksplicitno prosleđen) — budući custom `log_dir` pozivalac
zadržava plain `mkdir()` ponašanje. Dokazano
`TestLogsDirectoryWiring::test_setup_logging_default_invokes_hardening` i
`test_setup_logging_custom_dir_skips_hardening`.

## BACKUP DIRECTORY PROTECTION

**PASS.** `persistence/schema_repair.py::create_schema_backup()` poziva
`harden_existing_directory(backup_dir)` ODMAH nakon `backup_dir.mkdir(parents=True,
exist_ok=False)` — collision-safe `exist_ok=False` semantika je NEDIRANA (koristi se
`harden_existing_directory`, ne `ensure_private_directory`, upravo zato da se ne mora
mijenjati mkdir poziv). Backup direktorijum sadrži punu kopiju SQLite baze (`.db` + `-wal`/
`-shm` + `metadata.json`) — sada nasljeđuje istu privatnu granicu. Dokazano
`TestBackupDirectoryWiring::test_create_schema_backup_invokes_hardening` (stvarna SQLite
baza, stvaran `create_schema_backup()` poziv).

## ARTIFACT DIRECTORY PROTECTION

```
NOT PRESENT
```

`app_paths.get_artifacts_dir()` je deklarisan, ali nema nijednog pozivaoca bilo gdje u
`src/` (potvrđeno `grep`-om). Nema centralnog FlowOS-owned artifact storage-a da se
zaštiti — nije kreirana prazna arhitektura samo radi acceptance liste, u skladu sa
eksplicitnom instrukcijom zadatka.

## EXISTING INSTALLATION HARDENING

**PASS.** `ensure_private_directory`/`harden_existing_directory` se izvršavaju PRI SVAKOM
stvarnom pozivu (svaki service startup, svaki `get_data_directory()`, svaki
`setup_logging()`, svaki `create_schema_backup()`) — bezuslovno, bez provjere "da li je
ovo prvi put". To znači da instalacije koje su POSTOJALE prije FLOW-1108 (npr. korisnikov
stvaran `%LOCALAPPDATA%\FlowOS\logs\flowos-service.log` od 2.4MB, kreiran prije ove
sesije) bivaju hardenovane pri SLJEDEĆEM pokretanju servisa, ne samo novokreirani
direktorijumi. Dokazano `TestExistingDirectoryHardened` klasom (dva testa) i EMPIRIJSKI
protiv stvarnog korisničkog `%LOCALAPPDATA%\FlowOS\logs\` direktorijuma (vidi FINDINGS).

## PERMISSION FAILURE

```
FAIL-CLOSED
```

- Runtime: `write_descriptor()` nikad ne piše descriptor ako hardening padne (dokazano
  testom).
- SID lookup failure, icacls nonzero exit, subprocess greška: svi eksplicitno
  `DirectoryHardeningError`, nikad tiho ignorisani (`TestFailClosed` klasa, 3 testa).
- Read-only/deny-write parent (self-attack probe, § FINDINGS): `mkdir()`-ova prirodna
  `PermissionError` propagira nepresretnuta — nije uhvaćena i sakrivena.
- Exception poruke sadrže putanju i icacls izlaz, NIKAD sadržaj tokena/descriptor-a
  (token se ne prosleđuje ACL sloju uopšte — hardening radi na nivou direktorijuma, prije
  nego što se descriptor sadržaj i piše).

## REAL WINDOWS ACL PROBE

```
PASS
```

Ova sesija je zaista Windows okruženje. `TestRealWindowsAclProbe` (2 testa,
`@pytest.mark.skipif(not WIN, ...)`) radi na PRIVREMENOM `tmp_path` direktorijumu:

- `test_real_hardening_restricts_to_expected_principals` — stvaran `icacls` upit nakon
  hardeninga, potvrđuje trenutni korisnik zadržava pristup, `Everyone`/`BUILTIN\Users`/
  `Authenticated Users` odsutni iz izlaza.
- `test_real_hardening_is_idempotent` — dva uzastopna hardening poziva daju identičan
  `icacls` izlaz.

Dodatno, EMPIRIJSKI probano (ad-hoc, van trajnog test fajla) protiv stvarnog
`%LOCALAPPDATA%\FlowOS\logs\` — vidi FINDINGS za kritičan bag otkriven i popravljen tokom
ovog probanja.

## FLOW-1107 REGRESSION

Fresh run:

```
python -m pytest tests/gui/test_live_launch.py tests/gui/test_api_client_auth.py \
  tests/integration/test_composition_root.py tests/integration/test_service_runtime.py \
  tests/integration/test_websocket_auth.py -v --tb=short
→ 55 passed, 1 warning in 31.47s
```

Prvi pokušaj ove regresije je PAO (24 testa, `PermissionError` na stvarnom
`flowos-service.log`) — to je otkrilo kritičan bag u prvobitnoj implementaciji (vidi
FINDINGS), popravljeno, PA ponovljeno sa gornjim rezultatom. Token generation, rotation,
descriptor token, HTTP auth, WS auth, dynamic port, MOCK mode — svi FLOW-1107 zahtjevi i
dalje prolaze nepromijenjeni.

## ACL TARGETED TESTS

```
python -m pytest tests/unit/test_dir_security.py -v --tb=short
→ 24 passed, 1 warning in 2.11s
```

Pokriva zahtijevanu matricu A–L (E izostavljeno — artifact storage ne postoji), plus
dodatni junction-safety par testova i namjenski regresioni test za otkriveni bag.

## scripts/verify.py

```
Prošlo: 7/7
[PASS] 1. Ruff format check
[PASS] 2. Ruff lint
[PASS] 3. mypy
[PASS] 4. Architecture boundaries
[PASS] 5. Unit tests
[PASS] 6. Migrations check
[PASS] 7. Alembic round-trip

[PASS] VERIFIKACIJA PROŠLA
```

Koristi se već-committovan 240s timeout (bez workaround-a). Usput otkriven i popravljen
`mypy` gap: `pyproject.toml`-ov postojeći `pywin32.*` override ne pokriva stvarna imena
modula (`win32api`, `win32security`) — dodana dva reda u istu override listu
(`ignore_missing_imports = true`), nikakva druga mypy pravila nisu mijenjana.

## PERFORMANCE IMPACT

```
NEGLIGIBLE
```

Hardening se poziva ISKLJUČIVO na startup/init granici:
- Runtime: jednom po service pokretanju (`write_descriptor`, poziva se jednom u `main()`).
- Data dir: jednom po `create_sqlite_engine()`/`get_data_directory()` pozivu (jednom po
  service pokretanju, ne po upitu).
- Logs: jednom po `setup_logging()` pozivu (jednom u lifespan startup-u).
- Backup: samo kad se DDL repair stvarno pokreće (rijedak, eksplicitan
  korisnički/developerski put, nikad automatski na svakom startup-u).

Dokazano testom `TestHotPathNotInvoked::test_repeated_requests_do_not_reinvoke_hardening`
— realan `create_app()` + `TestClient`, spy na `ensure_private_directory` pokazuje TAČNO
jedan poziv na lifespan startup, ZATIM 5 iteracija × 2 HTTP zahtjeva (`/health` i
`/projects`) BEZ ijednog dodatnog poziva. `icacls` subprocess (typically <100ms po pozivu)
se nikad ne izvršava po requestu/DB upitu/watcher eventu/WS eventu.

## FILES CHANGED

```
 pyproject.toml                                              |  2 ++
 src/flowos/service/services/infrastructure/app_paths.py     |  5 +++++
 src/flowos/service/services/infrastructure/logging.py       | 12 +++++++++++-
 .../service/services/infrastructure/persistence/engine.py   | 10 ++++++++--
 .../services/infrastructure/persistence/schema_repair.py    |  6 ++++++
 src/flowos/service/services/infrastructure/runtime.py       | 13 +++++++++++--
 6 files changed, 43 insertions(+), 5 deletions(-)

 NOVI: src/flowos/service/services/infrastructure/dir_security.py (198 linija)
 NOVI: tests/unit/test_dir_security.py (24 testa)
```

## OUT OF SCOPE LEFT UNTOUCHED

- FLOW-1109 (redakcija tajni iz logova/artefakata) — nije implementirano.
- FLOW-1110 (siguran worktree identitet i cleanup) — nije implementirano.
- Agent environment allowlist, Job Objects, `extra_args` hardening, verification
  execution boundary, repo registration validation, Git ref validation, implicit fetch
  fix, Host/Origin hardening, DPAPI, Credential Manager, database encryption,
  installer/signing — ništa od ovoga nije dirano.
- FLOW-1107 auth semantika (token generation/rotation/HTTP/WS auth) — potpuno nedirana,
  regresija to potvrđuje.
- DB modeli, Alembic migracije, plan parser, Ledger, Task UI, Git/worktree kod, agent
  execution, verification command semantika — nedirano.
- `app_paths.py::ensure_directories()` i njeni neiskorišćeni getteri (`get_backups_dir()`,
  `get_artifacts_dir()`, `get_spool_dir()`, `get_settings_dir()`) — nisu pozvani niti
  mijenjani; hardening je vezan direktno za stvarne `.mkdir()` pozive, ne za mrtav kod.
- Objedinjavanje dvije paralelne `%LOCALAPPDATA%/FlowOS` kalkulacija (`app_paths.py` vs
  `persistence/engine.py`/`logging.py`) — dokumentovano kao future-task nalaz, nije
  refaktorisano.

## FINDINGS

### A. FLOW-1108 acceptance findings

**F1108-CRIT (otkriveno i POPRAVLJENO tokom ovog zadatka, nije preostao nalaz) — prvobitna
implementacija je pravila fajlove nedostupnim čak i vlasniku.**

Prvi dizajn je primjenjivao `(OI)(CI)F` grant flagove DIREKTNO na sve objekte (direktorijum
+ fajlove) preko JEDNOG `icacls <dir> /inheritance:r /grant:r ...(OI)(CI)F... /T` poziva.
`(OI)(CI)` (Object Inherit / Container Inherit) flagovi su namijenjeni KONTEJNERIMA
(propagacija na buduću djecu) — kad se `/T` rekurzija primjeni i NA FAJLOVE sa tim istim
flagovima, icacls prijavljuje uspjeh (`exit=0`, "Successfully processed N files"), ali
rezultujući ACL na fajlu je PRAZAN (nula ACE-ova) — fajl postaje nedostupan ČAK I vlasniku.

Ovo je otkriveno kada je fresh FLOW-1107 regresija PALA sa 24 `PermissionError`-a na
stvarnom korisničkom `C:\Users\...\AppData\Local\FlowOS\logs\flowos-service.log` (2.4MB,
pravi produkcijski log od prije ove sesije) — reprodukovano izolovano, potvrđen tačan
mehanizam, popravljeno DVOKORAČNIM pristupom (direktorijum eksplicitno, djeca preko
`/reset /T` wildcard-a koji NE dira sam direktorijum), REGRESIJA PONOVLJENA ČISTA.

Neposredna posljedica prije popravke: da je ovaj bag stigao do stvarnog korisnika,
`flowos-service.exe` bi na SLJEDEĆEM pokretanju hardenovao svoj `logs/` direktorijum i
odmah zatim PAO pri pokušaju upisa u sopstveni log fajl (`PermissionError` na
`RotatingFileHandler` open) — servis se ne bi ni pokrenuo. Popravljeno prije predaje;
dodat namjenski regresioni test
(`TestExistingDirectoryHardened::test_existing_files_remain_openable_after_hardening`)
koji dokazuje da se ovo NE ponavlja — stvaran `open()`/append na postojeće fajlove nakon
hardeninga, ne samo `icacls` tekstualni izlaz.

**F1108-L1 — dvije nezavisne kalkulacije `%LOCALAPPDATA%/FlowOS` putanje.**

`app_paths.py::_get_local_appdata()` čita `LOCALAPPDATA` env var (sa `Path.home()`
fallback-om); `persistence/engine.py::get_data_directory()` i `logging.py`'s default
koriste `Path.home() / "AppData" / "Local"` bez čitanja `LOCALAPPDATA` uopšte. U praksi
identično na standardnoj Windows instalaciji, ali teorijski mogu divergirati (redirected
profile). `dir_security.py::_hardenable_roots()` prihvata OBA kandidata umjesto da ih
objedini — objedinjavanje je namjerno van scope-a FLOW-1108 (arhitektonski refaktor, nije
sigurnosni fix). Future-task.

### B. Future-task findings

**F1108-B1 — `app_paths.py::ensure_directories()` i njegovi getteri za backup/artifacts/
spool/settings su mrtav kod.**

`ensure_directories()` se nigdje ne poziva; `get_backups_dir()`/`get_artifacts_dir()`/
`get_spool_dir()`/`get_settings_dir()` nemaju pozivaoce. Stvarni backup put je
`data/backups/schema-repair-.../` (računat ad-hoc u `schema_repair.py`, ne preko
`app_paths.py`). Ako se ovi getteri ikad povežu sa stvarnim kodom (npr. buduća `spool`
funkcionalnost za offline CLI wrapper), trebaju proći kroz `ensure_private_directory()`
na isti način kao i ostatak FLOW-1108. Nije FLOW-1108 defekt (ne postoji kod koji bi
trebalo zaštititi), samo napomena za buduće proširenje.

**F1108-B2 — Junction-safety (`/L` flag) je odbrambena mjera, ne dio originalnog zahtjeva.**

Tokom self-attack probe (§16) potvrđeno je da BEZ `/L`, `/T` rekurzija PRATI directory
junction u njegov cilj i mijenja ACL TAMO. Pošto bi plasiranje junction-a unutar
FlowOS-owned direktorijuma zahtijevalo da napadač VEĆ ima write pristup toj lokaciji (isti
Windows korisnik — eksplicitno izvan threat modela), ovo nije bio blocker, ali je jeftina,
niskorizična dodatna zaštita pa je uključena u implementaciju (`/L` flag + dva testa).

## FINAL SELF-CHECK

| Pitanje | Očekivano | Stvarno |
|---|---|---|
| runtime directory protected? | YES | YES |
| database directory protected? | YES | YES |
| logs directory protected? | YES | YES |
| backup directory protected where present? | YES/N/A | YES |
| artifacts protected where present? | YES/N/A | N/A (ne postoji) |
| existing directories hardened? | YES | YES |
| runtime ACL established before token write? | YES | YES |
| current API token still works? | YES | YES (FLOW-1107 regresija 55/55) |
| FLOW-1107 auth semantics changed? | NO | NO |
| ACL runs in hot path? | NO | NO |
| repo/worktree recursively modified? | NO | NO |
| shell=True introduced? | NO | NO |
| DB/migrations changed? | NO | NO |
| secret redaction implemented accidentally? | NO | NO |
| verify.py 7/7? | YES | YES |

## STOP

Ne commitovano. Ne pushovano.

**FLOW-1108 — Zaštita lokalnih FlowOS podataka = READY FOR SECURITY REVIEW**

Odstupanja od prompta: NONE
