# FlowOS — strogi korektivni nalog za Fazu 2

## Status dokumenta

Ovo je **obavezni korektivni zadatak** za implementaciju iz paketa:

```text
phase2-wrapper.zip
```

Trenutna Faza 2 se ne smatra završenom.

Dozvoljeni status prije popravke:

```text
IMPLEMENTIRANO — POTREBAN PREGLED
```

Nije dozvoljeno označiti Fazu 2 kao:

```text
PROVJERENO
PRIHVAĆENO
ZAVRŠENO
OK
```

dok svi kriterijumi iz ovog dokumenta ne budu ispunjeni.

---

# 1. Glavni cilj

Popraviti implementaciju Faze 2 tako da:

1. agentski procesi pravilno prijavljuju exit code;
2. Git promjene budu stvarno detektovane;
3. untracked fajlovi budu uključeni u Git stanje;
4. Git polling bude stvarni periodični servis ili jasno preimenovana komponenta;
5. watcher bude integrisan u runtime;
6. watcher greške ne budu tiho izgubljene;
7. atribucija promjena bude sigurna;
8. sesijski API koristi stroge Pydantic ugovore;
9. statusi sesija budu validirani;
10. transakcije imaju jedno jasno vlasništvo;
11. početni i završni commit sesije budu odvojeni;
12. Windows procesno stablo bude pouzdano ugašeno;
13. CLI radi bez import grešaka;
14. CLI koristi validirani runtime descriptor;
15. dokumentacija ne tvrdi funkcije koje ne postoje;
16. Ruff, mypy, pytest i architecture provjere prođu;
17. review bundle bude potpun i međusobno dosljedan.

---

# 2. Zabrane

Agent ne smije:

- počinjati Fazu 3;
- uvoditi nove funkcionalnosti koje nisu direktno potrebne za ove ispravke;
- skrivati greške izmjenom testova;
- uklanjati test samo zato što pada;
- ručno mijenjati očekivani rezultat tako da odgovara pogrešnom kodu;
- ostaviti lažnu ili zastarjelu dokumentaciju;
- tvrditi da je Job Object implementiran ako nije;
- tvrditi da offline spool postoji ako nije implementiran;
- tvrditi da je watcher integrisan ako samo postoji klasa;
- označiti Ruff kao PASS ako postoji ijedna Ruff greška;
- označiti Git stanje kao čisto ako `git status --short` nije prazan;
- koristiti screenshot sa nečitljivim fontovima kao dokaz GUI-ja;
- početi Fazu 3 prije nezavisne provjere novog review bundle-a.

---

# 3. Prioritet P0 — obavezne blokirajuće popravke

## 3.1 Ispraviti pogrešan exit code uspješnog procesa

### Fajl

```text
src/flowos/service/services/infrastructure/agent_adapters/claude_code.py
```

### Trenutni problem

Kod koristi:

```python
exit_code = proc.returncode or -1
```

Kada proces uspješno završi:

```python
proc.returncode == 0
```

Pošto je `0` falsy vrijednost, rezultat postaje:

```text
-1
```

To znači da uspješno završen proces može biti evidentiran kao neuspješan.

### Obavezna ispravka

Koristiti:

```python
exit_code = proc.returncode if proc.returncode is not None else -1
```

### Obavezni testovi

Dodati testove:

```text
returncode 0  → exit_code 0
returncode 1  → exit_code 1
returncode 137 → exit_code 137
returncode None → exit_code -1
```

Ne koristiti mock koji zaobilazi stvarnu granu koda.

---

## 3.2 Redizajnirati GitPoller tok

### Fajl

```text
src/flowos/service/services/infrastructure/git_poller.py
```

### Trenutni problem

`poll()` upisuje:

```python
self._last_state = state
```

prije nego što `detect_changes(fresh)` pročita prethodno stanje.

Normalni tok:

```python
fresh = poller.poll()
changes = poller.detect_changes(fresh)
```

poredi stanje sa samim sobom.

### Obavezna ispravka

Implementirati jedan jasan javni tok, na primjer:

```python
def poll_and_detect(self) -> tuple[GitState, GitChangeSet]:
    previous = self._last_state
    fresh = self._read_state()
    changes = self._compare(previous, fresh)
    self._last_state = fresh
    return fresh, changes
```

Dozvoljeno je zadržati pomoćne metode:

```text
_read_state()
_compare()
```

Ali nije dozvoljeno da pozivalac mora ručno mijenjati privatno polje `_last_state`.

### Obavezni model rezultata

Ne vraćati proizvoljni `dict`.

Uvesti strukturisan tip, na primjer:

```python
@dataclass(frozen=True)
class GitChangeSet:
    first_observation: bool
    commit_changed: bool
    branch_changed: bool
    dirty_state_changed: bool
    new_untracked_files: tuple[str, ...]
    changed_files: tuple[str, ...]
    previous_commit_sha: str | None
    current_commit_sha: str | None
    previous_branch: str | None
    current_branch: str | None
```

### Obavezni testovi

Testirati sa stvarnim privremenim Git repozitorijumom:

1. prvo očitavanje;
2. nema promjene;
3. novi commit;
4. promjena grane;
5. čist → dirty;
6. dirty → čist;
7. novi untracked fajl;
8. izmijenjen tracked fajl;
9. obrisan fajl;
10. repo bez commita;
11. putanja nije Git repo;
12. Git komanda vraća grešku.

---

## 3.3 Uključiti untracked fajlove

### Trenutni problem

Kod koristi:

```bash
git diff --name-only HEAD
```

Ova komanda ne prikazuje:

```text
?? novi_fajl.py
```

### Obavezna ispravka

Koristiti:

```bash
git status --porcelain=v2 -z
```

ili drugi stabilan parser koji uključuje:

- tracked izmjene;
- staged izmjene;
- obrisane fajlove;
- rename;
- untracked fajlove.

Ne parsirati samo čovjeku namijenjen `git status` tekst.

### Obavezni rezultat

`GitState.changed_files` mora sadržavati i untracked fajlove.

Dodati odvojeno polje ako je korisno:

```python
untracked_files: list[str]
```

---

## 3.4 Implementirati stvarni periodični Git polling

### Trenutni problem

Klasa se zove `GitPoller` i ima:

```text
interval
_running
```

ali nema stvarni periodični rad.

### Obavezna odluka

Izabrati jednu od dvije opcije.

### Opcija A — stvarni servis

Implementirati:

```python
start()
stop()
is_running
poll_once()
```

Za periodični rad koristiti kontrolisan thread, timer ili servisni scheduler.

Obavezno:

- nema blokiranja glavnog FastAPI thread-a;
- `stop()` pouzdano zaustavlja loop;
- nema duplog pokretanja;
- greške se loguju;
- interval se može podesiti;
- callback dobija strukturisan rezultat;
- test ne čeka stvarnih 30 sekundi.

### Opcija B — preimenovanje

Ako periodični servis nije dio ove korektivne runde, preimenovati klasu u:

```text
GitStateReader
```

i ukloniti lažne tvrdnje o periodičnom pollingu iz:

- docstringa;
- plana;
- reporta;
- README-a.

Faza 2 se tada ne smije tvrditi kao potpuno završena ako plan eksplicitno zahtijeva periodični polling.

Preporučena je Opcija A.

---

# 4. Prioritet P0 — watcher

## 4.1 Integrisati WatcherPipeline u stvarni runtime

### Fajlovi

Najmanje pregledati i izmijeniti:

```text
src/flowos/service/composition_root.py
src/flowos/service/services/infrastructure/watcher.py
src/flowos/service/app.py ili odgovarajući lifespan modul
```

### Trenutni problem

`WatcherPipeline` postoji, ali se ne vidi da ga runtime:

- kreira;
- pokreće;
- zaustavlja;
- povezuje sa projektima;
- povezuje sa activity servisom.

### Obavezna ispravka

Watcher mora imati jasno vlasništvo.

Primjer toka:

```text
service startup
→ učitaj aktivne projekte/repozitorijume
→ kreiraj watcher instance
→ pokreni ih
→ događaje pošalji u ActivityService
→ pri shutdown-u zaustavi sve watchere
```

Ako MVP prati samo trenutno aktivni projekat, to mora biti eksplicitno napisano i testirano.

### Nije dovoljno

Nije dovoljno da:

```text
WatcherPipeline klasa postoji
```

Mora postojati dokaz da se koristi u stvarnom toku.

---

## 4.2 Ne gutati callback greške

### Trenutni problem

Kod koristi:

```python
except Exception:
    pass
```

### Obavezna ispravka

Minimalno:

```python
except Exception:
    logger.exception(
        "Watcher callback nije uspio",
        extra={...},
    )
```

Poželjno:

- broj neuspjelih callbackova;
- retry za privremene greške;
- dead-letter ili error event za trajne greške;
- correlation/event ID.

Nije dozvoljeno da događaj nestane bez ikakvog traga.

---

## 4.3 Popraviti stop lifecycle

### Obavezno

`stop()` mora:

1. spriječiti prijem novih događaja;
2. zaustaviti observer;
3. otkazati pending timer;
4. pod lockom preuzeti pending događaje;
5. prema dokumentovanom pravilu:
   - flushovati ih, ili
   - odbaciti ih uz log;
6. joinovati observer;
7. postaviti interno stanje na zaustavljeno;
8. biti idempotentan.

Dodati:

```python
@property
def is_running(self) -> bool:
    ...
```

### Obavezni testovi

- start na nepostojećoj putanji;
- dupli start;
- stop prije starta;
- dupli stop;
- stop dok postoji pending debounce timer;
- callback greška;
- create događaj;
- modify događaj;
- delete događaj;
- ignored folder;
- debounce spaja više događaja istog fajla;
- događaji različitih fajlova se ne izgube.

Koristiti stvarni privremeni direktorijum gdje je moguće.

---

# 5. Prioritet P0 — atribucija promjena

## 5.1 Zamijeniti nesigurni `startswith`

### Fajl

```text
src/flowos/service/services/attribution/service.py
```

### Trenutni problem

Kod koristi:

```python
str(fp).startswith(str(wt))
```

To može pogrešno pripisati:

```text
C:\worktree-12-other\file.py
```

worktree-u:

```text
C:\worktree-12
```

### Obavezna ispravka

Na Pythonu 3.12 koristiti:

```python
fp.is_relative_to(wt)
```

uz:

```python
resolve(strict=False)
```

i pažljivo rukovanje Windows case-insensitive putanjama.

Napraviti jednu centralnu pomoćnu funkciju za provjeru pripadnosti putanje.

### Obavezni testovi

- fajl direktno u worktree-u;
- fajl u podfolderu;
- putanja sa sličnim tekstualnim prefiksom;
- relativna putanja;
- različita slova diska;
- nepostojeća putanja;
- Windows separator;
- Unix separator u testnom okruženju.

---

## 5.2 Ograničiti SOLE_ACTIVE atribuciju

### Trenutni problem

Ako postoji jedna aktivna sesija, bilo koji fajl joj se pripisuje.

### Obavezna ispravka

`SOLE_ACTIVE` je dozvoljen samo kada je fajl unutar:

```text
session.repo_path
```

ili unutar odgovarajućeg worktree-a.

Ako fajl nije unutar projekta sesije:

```text
UNATTRIBUTED
```

ili:

```text
USER
```

prema jasno dokumentovanom pravilu.

### Obavezna pravila prioriteta

Preporučeni redoslijed:

```text
1. WORKTREE      — fajl je unutar tačnog worktree-a
2. REPO_MATCH    — fajl je unutar repo-a jedine aktivne sesije
3. HINT          — samo ako je stvarno implementiran i dokaziv
4. UNATTRIBUTED  — više mogućih sesija ili nema dovoljno dokaza
5. USER          — nema aktivnih sesija i fajl pripada poznatom projektu
```

Ne koristiti termin `HINT` u dokumentaciji ako nema implementacije.

### Obavezna odluka za HINT

Jedno od:

- implementirati HINT sa jasnim pravilima i testovima;
- potpuno ga ukloniti iz docstringa, modela, plana i reporta.

---

# 6. Prioritet P0 — sesijski API

## 6.1 Uvesti Pydantic request/response modele

### Fajl

```text
src/flowos/service/controllers/http/sessions.py
```

### Trenutni problem

Koristi se:

```python
data: dict
```

i ručno mapiranje u dict.

### Obavezna ispravka

U shared contracts ili odgovarajućem contract modulu dodati:

```python
class SessionCreateRequest(BaseModel):
    project_id: str
    agent_type: str
    repo_path: str
    task_id: str | None = None
    model_name: str | None = None
    execution_mode: ExecutionMode = ExecutionMode.WRAPPED_TERMINAL
    branch_name: str | None = None
    worktree_path: str | None = None
    plan_item_id: str | None = None
    base_commit_sha: str | None = None
    pid: int | None = None
```

```python
class SessionEndRequest(BaseModel):
    exit_code: int | None = None
    result_commit_sha: str | None = None
    status: SessionEndStatus = SessionEndStatus.COMPLETED
```

```python
class SessionResponse(BaseModel):
    ...
```

Koristiti `response_model`.

---

## 6.2 Ukloniti mutable default argument

Nije dozvoljeno:

```python
data: dict = {}
```

Mora biti Pydantic model ili `None`.

---

## 6.3 Validirati statusnu mašinu sesije

Definisati dozvoljene statuse.

Primjer:

```text
CREATED
STARTING
ACTIVE
COMPLETED
FAILED
INTERRUPTED
TIMED_OUT
UNKNOWN
```

Definisati dozvoljene prelaze.

Primjer:

```text
CREATED → STARTING
STARTING → ACTIVE
ACTIVE → COMPLETED
ACTIVE → FAILED
ACTIVE → INTERRUPTED
ACTIVE → TIMED_OUT
```

Nije dozvoljeno:

```text
COMPLETED → ACTIVE
FAILED → ACTIVE
```

bez eksplicitne nove sesije.

Status se ne smije direktno upisivati iz proizvoljnog korisničkog stringa.

---

## 6.4 Jedno vlasništvo nad transakcijom

### Trenutni problem

Dependency commitira nakon `yield`, a endpointi ponovo rade `commit()`.

### Obavezna ispravka

Izabrati jedan model.

Preporuka:

```text
request-scoped Unit of Work
```

ili:

```text
Service metoda upravlja transakcijom
```

Za ovu fazu je prihvatljivo:

```python
def get_db_session(...):
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

Tada endpointi i servisi ne rade dodatni `commit()` osim kada postoji jasno dokumentovan poseban razlog.

Ne smiju ostati dupli commit pozivi.

---

## 6.5 Odvojiti početni i završni commit

`base_commit_sha` predstavlja commit na početku sesije i ne smije se prepisivati.

Dodati:

```text
result_commit_sha
```

ili:

```text
end_commit_sha
```

Migracija mora biti uključena.

Testirati:

```text
base_commit_sha ostaje isti
result_commit_sha se upisuje pri završetku
```

---

## 6.6 Tanke API kontrolere

Controller treba da radi:

```text
request model
→ SessionService
→ response model
```

Ne treba da sadrži poslovna pravila niti ručno mapiranje velikih dict struktura.

Mapiranje staviti u contract adapter ili koristiti `model_validate(..., from_attributes=True)`.

---

# 7. Prioritet P0 — agentski proces i Windows lifecycle

## 7.1 Ispraviti lažnu tvrdnju o Job Object-u

### Trenutni problem

Kod koristi:

```text
CREATE_NEW_PROCESS_GROUP
TerminateProcess
```

To nije Windows Job Object.

### Obavezna odluka

Jedno od:

### Opcija A — implementirati pravi Windows Job Object

Potrebno:

- `CreateJobObject`;
- `SetInformationJobObject`;
- `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`;
- `AssignProcessToJobObject`;
- čuvanje handle-a;
- cleanup handle-a;
- test da se gase i potomci procesa.

### Opcija B — ukloniti tvrdnju

Ako se koristi `taskkill /T /F` ili druga tehnika, dokumentacija mora tačno reći šta se radi.

Ne koristiti naziv:

```text
Job Object kontrola
```

ako nije stvarno implementirana.

Preporučena je Opcija A ako je plan eksplicitno zahtijeva.

---

## 7.2 Timeout mora ugasiti cijelo stablo

Nije dovoljno:

```python
proc.kill()
```

Obavezno:

- prvo pokušati graceful signal;
- sačekati definisani timeout;
- zatim ugasiti procesno stablo;
- sačuvati stvarni status `TIMED_OUT`;
- sačuvati exit code i razlog;
- logovati cleanup rezultat.

---

## 7.3 Sigurna environment politika

### Trenutni problem

Nakon allowliste radi se:

```python
env.update(request.env)
```

### Obavezna ispravka

Definisati:

```text
ALLOWED_ENV_KEYS
BLOCKED_ENV_PATTERNS
SENSITIVE_ENV_PATTERNS
```

Ne dozvoliti da pozivalac bez provjere prepiše:

- `PATH`;
- `SYSTEMROOT`;
- `COMSPEC`;
- sigurnosne tokene;
- interne FlowOS varijable.

Ako su dodatne varijable potrebne agentu, koristiti eksplicitnu allowlistu.

Logovi ne smiju sadržati vrijednosti osjetljivih varijabli.

---

## 7.4 Stvarni Claude Code smoke test

Pošto adapter nije potvrđen stvarnim alatom, dodati ručni ili integracioni smoke test:

1. pronađi CLI izvršni fajl;
2. pokreni bezopasnu komandu;
3. potvrdi stdout/stderr;
4. potvrdi exit code;
5. potvrdi working directory;
6. potvrdi timeout;
7. potvrdi prekid;
8. potvrdi gašenje child procesa.

Dok to ne prođe:

```text
FLOW-203 = IMPLEMENTIRANO, NIJE PROVJERENO
```

---

# 8. Prioritet P1 — CLI

## 8.1 Ispraviti `Optional` greške

### Fajl

```text
src/flowos/cli/app.py
```

Na Pythonu 3.12 koristiti:

```python
str | None
int | None
```

Ne uvoditi `Optional` samo da bi se zadržao zastarjeli stil.

---

## 8.2 Riješiti Ruff B008 za Typer

Koristiti projektno prihvaćen Typer pattern.

Dozvoljene opcije:

- `Annotated` sa `typer.Option`;
- ciljano Ruff pravilo samo ako postoji opravdanje i dokumentacija.

Preporučeno:

```python
from typing import Annotated

task: Annotated[str | None, typer.Option("--task", "-t")] = None
```

Ne globalno gasiti `B008` bez obrazloženja.

---

## 8.3 Validirati runtime descriptor

CLI trenutno čita JSON i port, ali mora potvrditi:

- schema version;
- host;
- port;
- PID;
- instance_id;
- `/health`;
- da health vraća isti instance_id.

Ako descriptor nije validan:

- ne koristiti ga slijepo;
- prijaviti jasnu grešku;
- eventualno pokrenuti recovery tok.

Ne koristiti hardkodovani port kao tihu zamjenu osim ako je to eksplicitna razvojna konfiguracija.

---

## 8.4 Offline spool — implementirati ili ukloniti tvrdnju

### Trenutni problem

Docstring tvrdi da spool postoji, ali kod ga nema.

### Obavezna odluka

#### Opcija A — implementirati spool

Potrebno:

```text
%LOCALAPPDATA%\FlowOS\spool\<session-id>.jsonl
```

Svaki događaj mora imati:

- event_id;
- idempotency_key;
- session_id;
- event_type;
- payload;
- occurred_at;
- schema_version.

Potrebno je:

- atomski append;
- replay;
- idempotency;
- označavanje uspješno uvezenih događaja;
- zaštita od korumpirane linije;
- test prekida backenda.

#### Opcija B — ukloniti tvrdnju

Ukloniti iz:

- CLI docstringa;
- plana;
- reporta;
- README-a.

Ako plan Faze 2 zahtijeva offline spool, onda Opcija B znači da Faza 2 nije potpuna.

---

# 9. Prioritet P1 — GUI i prevodi

## 9.1 Očistiti Ruff greške

Posebno:

```text
src/flowos/gui/controllers/overview.py
src/flowos/gui/services/client.py
src/flowos/gui/theme/labels.py
src/flowos/gui/views/overview_skeleton.py
src/flowos/gui/app.py
```

Nije dozvoljeno:

```python
if condition: action(); return
```

Koristiti čitljive višelinijske blokove.

Ukloniti:

- neiskorištene importe;
- višestruke naredbe u redu;
- nedostajuće završne nove redove;
- neformatirane dict izraze.

---

## 9.2 Testirati stvarni prikaz prevoda

Nije dovoljno testirati samo mapu:

```python
status_label("IMPLEMENTED") == "Implementirano"
```

Potrebno je testirati stvarni ViewState → widget tok.

Dodati test koji:

1. ubaci raw enum vrijednosti;
2. renderuje relevantne widgete;
3. provjeri da korisnički tekst sadrži:
   - Implementirano;
   - Provjereno;
   - Prihvaćeno;
   - Potreban pregled;
4. provjeri da ne sadrži:
   - IMPLEMENTED;
   - VERIFIED;
   - ACCEPTED;
   - NEEDS_REVIEW;
   - ACTIVE;
   - NOT_STARTED.

---

## 9.3 Stvarni Windows screenshotovi

Offscreen screenshot sa kvadratićima nije validan dokaz.

Obavezno dostaviti screenshot stvarno pokrenute Windows aplikacije:

```text
overview-1600x900-windows.png
overview-1920x1080-windows.png
right-panel-scrolled-windows.png
translated-statuses-windows.png
```

Screenshot mora pokazati čitljiv tekst.

---

# 10. Prioritet P1 — dokumentacija i izvještaj

## 10.1 Uskladiti tvrdnje sa stvarnim kodom

Pregledati i ispraviti:

```text
README_REVIEW.md
agent_report.md
plan_item.md
docstringove
komentare
```

Nije dozvoljeno tvrditi:

```text
Ruff prolazi
Git je čist
watcher je integrisan
Job Object je implementiran
offline spool radi
svi acceptance kriterijumi su ispunjeni
```

ako dokazi to ne potvrđuju.

---

## 10.2 Terminologija statusa

U izvještajima koristiti:

```text
Implementirano
Provjereno
Prihvaćeno
Potreban pregled
Blokirano
```

Ne miješati:

```text
IMPLEMENTED
DONE
OK
VERIFIED
ACCEPTED
```

bez objašnjenja nivoa.

---

# 11. Obavezni novi i izmijenjeni testovi

Minimalno dodati:

```text
tests/unit/test_agent_adapter_exit_codes.py
tests/unit/test_agent_adapter_process_tree.py
tests/unit/test_git_poller.py
tests/integration/test_git_poller_real_repo.py
tests/unit/test_watcher.py
tests/integration/test_watcher_real_directory.py
tests/unit/test_attribution.py
tests/unit/test_session_state_machine.py
tests/integration/test_sessions_api_contract.py
tests/unit/test_runtime_descriptor_client.py
tests/unit/test_cli_spool.py                 # samo ako se spool implementira
tests/gui/test_overview_translations.py
```

Testovi moraju pokriti probleme iz ovog dokumenta, ne samo happy path.

---

# 12. Obavezna verifikacija

Pokrenuti na Pythonu 3.12 u čistom okruženju:

```bash
python -m pip install -e ".[dev]"
ruff format --check .
ruff check .
mypy src
pytest -q
python scripts/verify.py
```

Ako postoji architecture test:

```bash
pytest tests/architecture -q
```

Ako postoji migration check:

```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

Za Windows procesne testove pokrenuti na stvarnom Windows sistemu.

---

# 13. Obavezni acceptance kriterijumi

Faza 2 se može označiti kao ponovo spremna za pregled tek kada je sve ispod ispunjeno:

```text
[ ] Uspješan proces vraća exit code 0.
[ ] GitPoller poredi prethodno i novo stanje.
[ ] GitPoller detektuje novi commit.
[ ] GitPoller detektuje promjenu grane.
[ ] GitPoller detektuje dirty promjenu.
[ ] GitPoller uključuje untracked fajlove.
[ ] Periodični polling stvarno radi ili je komponenta tačno preimenovana.
[ ] Watcher je integrisan u runtime.
[ ] Watcher stop gasi observer i timer.
[ ] Watcher callback greške se loguju.
[ ] Watcher ima stvarne integration testove.
[ ] Atribucija koristi sigurnu provjeru putanje.
[ ] SOLE_ACTIVE ne pripisuje fajl iz drugog projekta.
[ ] HINT je implementiran ili uklonjen iz dokumentacije.
[ ] Sesijski API koristi Pydantic modele.
[ ] Mutable default dict je uklonjen.
[ ] Statusi sesije su validirani.
[ ] Ne postoje dupli commit pozivi.
[ ] base_commit_sha se ne prepisuje.
[ ] result_commit_sha ili end_commit_sha postoji.
[ ] Procesno stablo se pouzdano gasi.
[ ] Dokumentacija tačno opisuje Job Object ili drugu tehniku.
[ ] Timeout ne ostavlja child procese.
[ ] Environment dodatne vrijednosti su kontrolisane.
[ ] Claude Code adapter ima stvarni smoke test ili ostaje NEPROVJEREN.
[ ] CLI nema Optional import grešku.
[ ] Ruff B008 je riješen.
[ ] CLI validira runtime descriptor i health.
[ ] Offline spool je implementiran ili tvrdnja uklonjena.
[ ] GUI nema raw engleske statuse.
[ ] Windows screenshotovi su čitljivi.
[ ] Ruff prolazi.
[ ] mypy prolazi.
[ ] pytest prolazi.
[ ] verify.py prolazi.
[ ] Git status je čist ili potpuno objašnjen.
[ ] Review bundle je potpun.
```

---

# 14. Statusi FLOW stavki poslije popravke

Agent ne smije sam dodijeliti `Prihvaćeno`.

Dozvoljeni najviši status nakon sopstvene implementacije:

```text
Implementirano
```

Nakon uspješne tehničke provjere:

```text
Provjereno
```

Tek korisnik ili nezavisni reviewer može dati:

```text
Prihvaćeno
```

Za pojedinačne stavke:

```text
FLOW-201 — najviše Provjereno nakon CLI testova
FLOW-202 — najviše Provjereno nakon API contract i state-machine testova
FLOW-203 — najviše Implementirano dok nema stvarnog Claude Code testa
FLOW-204 — najviše Provjereno nakon runtime integracije watcher-a
FLOW-205 — najviše Provjereno nakon real Git repo testova
FLOW-206 — najviše Provjereno nakon path i cross-project testova
FLOW-207 — najviše Provjereno nakon stvarnog Windows GUI prikaza
FLOW-208 — najviše Provjereno nakon punog verify toka
```

---

# 15. Obavezna struktura novog review bundle-a

Kreirati:

```text
review_bundles/FLOW-PHASE2-CORRECTION/
```

Struktura:

```text
FLOW-PHASE2-CORRECTION/
├── README_REVIEW.md
├── agent_report.md
├── plan_item.md
├── git_status.txt
├── git_log.txt
├── commits.txt
├── changed_files.txt
├── changes.diff
├── verify_results.txt
├── test_results.txt
├── lint_results.txt
├── mypy_results.txt
├── architecture_check.txt
├── architecture_tree.txt
├── migration_results.txt
├── source/
│   └── svi relevantni puni fajlovi
├── screenshots/
│   └── stvarni Windows screenshotovi
└── metadata/
    ├── environment.txt
    ├── commands_run.txt
    └── bundle_manifest.txt
```

`bundle_manifest.txt` mora sadržati:

- relativnu putanju;
- veličinu;
- SHA-256 hash.

---

# 16. Završni odgovor pi agenta

Pi agent mora odgovoriti tačno ovim formatom:

```text
STATUS: IMPLEMENTIRANO | PARCIJALNO | BLOKIRANO

POPRAVLJENI BLOKIRAJUĆI PROBLEMI:
- ...

NEPOPRAVLJENI PROBLEMI:
- Nema
ili
- ...

GIT POLLER:
- prethodno/novo stanje: DA/NE
- untracked fajlovi: DA/NE
- periodični rad: DA/NE

WATCHER:
- runtime integracija: DA/NE
- siguran stop: DA/NE
- callback greške se loguju: DA/NE

ATRIBUCIJA:
- sigurna path provjera: DA/NE
- cross-project zaštita: DA/NE

SESIJSKI API:
- Pydantic ugovori: DA/NE
- statusna mašina: DA/NE
- jedno vlasništvo transakcije: DA/NE
- odvojeni početni/završni commit: DA/NE

AGENT ADAPTER:
- exit code 0 ispravan: DA/NE
- procesno stablo se gasi: DA/NE
- stvarni Claude Code smoke test: DA/NE

CLI:
- Ruff greške uklonjene: DA/NE
- runtime descriptor validiran: DA/NE
- offline spool: IMPLEMENTIRAN / UKLONJENA TVRDNJA / NIJE RIJEŠENO

GUI:
- svi statusi na srpskom: DA/NE
- stvarni Windows screenshotovi: DA/NE

VERIFIKACIJA:
- Ruff:
- mypy:
- pytest:
- architecture:
- verify.py:
- migracije:

GIT STATUS:
- čist: DA/NE
- objašnjenje ako nije čist:

REVIEW BUNDLE:
- putanja:

PREPORUČENI STATUS FAZE 2:
- Implementirano
- Provjereno
- Potreban pregled

Agent ne smije napisati „Prihvaćeno“.
```

---

# 17. Završna naredba

Ne prelaziti na Fazu 3.

Prvo:

```text
popraviti Fazu 2
→ pokrenuti sve provjere
→ napraviti potpun review bundle
→ predati na nezavisni pregled
→ tek nakon potvrde nastaviti dalje
```
