# FlowOS — nezavisni pregled Phase 1 backenda

## Konačna ocjena

**Status:** PARCIJALNO — dobra osnova, ali još nije spremno za prihvatanje kao završena Faza 1.

Kod pokazuje dobru namjeru i solidnu početnu organizaciju, ali nekoliko važnih tvrdnji iz review bundle-a nije potvrđeno stvarnim dokazima:

- `Ruff` ne prolazi;
- `mypy` nije pokrenut;
- arhitektonski testovi daju lažno pozitivan rezultat;
- dio API kontrolera direktno koristi ORM i persistence;
- postoje konkretne greške u statusnoj mašini i lifecycle dizajnu.

Zbog toga tvrdnju „Svi acceptance kriterijumi ispunjeni“ treba povući dok se problemi ispod ne isprave.

---

# 1. Šta je urađeno dobro

## 1.1 Dobra modularna početna struktura

Razdvajanje na:

```text
shared/
service/controllers/
service/services/
service/services/infrastructure/
```

je dobar pravac i odgovara planiranoj arhitekturi.

Posebno su korisni:

- izdvojeni `composition_root.py`;
- zasebni plan modeli;
- zasebni resume modeli;
- Alembic migracije;
- centralni `PlanProgressService`;
- strukturisan runtime manager;
- relativno širok testni skup.

## 1.2 Plan i „Gdje si stao“ nisu ostali samo dokumentacija

Agent je stvarno uveo:

- `Plan`;
- `PlanPhase`;
- `PlanItem`;
- acceptance kriterijume;
- zavisnosti;
- audit događaje;
- `ProjectResumeState`;
- workspace/reconciliation modele;
- vanjsku aktivnost.

To je važno jer FlowOS dobija stvarnu osnovu za kasniji GUI, a ne samo statične Markdown izvještaje.

## 1.3 Testni obim je dobar za ovu fazu

`166 passed` je dobar signal da je uložen ozbiljan trud u testiranje.

Međutim, broj testova nije dovoljan dokaz kada:

- alati nisu pokrenuti u ciljnom okruženju;
- architecture test ne skenira stvarne module;
- testovi potvrđuju pogrešno implementirano pravilo.

---

# 2. Kritični problemi

## 2.1 Architecture testovi praktično ne provjeravaju stvarni kod

U:

```text
tests/architecture/test_boundaries.py
```

`SRC` već pokazuje na:

```text
src/flowos
```

ali `_collect_module_paths()` za paket:

```text
flowos.service.controllers
```

gradi putanju:

```text
src/flowos/flowos/service/controllers
```

Ta putanja ne postoji.

Posljedica:

```text
_collect_module_paths(...)
→ vraća praznu listu
→ nema pronađenih prekršaja
→ test prolazi
```

Zato rezultat:

```text
7/7 architecture testova prolazi
```

nije validan dokaz.

Ovo je posebno ozbiljno jer stvarni prekršaji već postoje, a test ih nije pronašao.

### Potrebna korekcija

Ili:

```python
SRC = repo_root / "src"
```

uz pakete `flowos.service...`, ili:

```python
SRC = repo_root / "src" / "flowos"
```

uz pakete `service.controllers`, `shared`, itd.

Dodati obavezan guard:

```python
assert paths, f"Nijedan modul nije pronađen za {source}"
```

Architecture test mora pasti ako nije pronašao nijedan fajl.

---

## 2.2 API Controlleri direktno koriste persistence modele i SQLAlchemy upite

Plan eksplicitno zabranjuje:

```text
API Controller → persistence implementacije direktno
```

Ali:

```text
service/controllers/http/plan_progress.py
service/controllers/http/project_resume.py
```

direktno importuju ORM modele iz:

```text
service/services/infrastructure/persistence/
```

i izvršavaju:

```python
session.query(...)
session.get(...)
session.add(...)
session.commit()
```

`project_resume.py` čak direktno kreira `ExternalActivity` ORM objekat.

To znači da kontroleri nisu tanki transportni sloj. Oni trenutno sadrže:

- persistence logiku;
- mapiranje ORM modela;
- transakcione odluke;
- dio poslovnog toka.

### Potrebna korekcija

Kontroleri treba da rade samo:

```text
request DTO
→ Service metoda
→ response DTO
```

Primjer:

```python
result = project_resume_service.create_external_activity(command)
return ExternalActivityResponse.model_validate(result)
```

SQLAlchemy `Session` i ORM modeli ne treba da se pojavljuju u API Controller fajlovima.

---

## 2.3 Bundle tvrdi da je verifikacija prošla, ali Ruff stvarno pada

`lint_results.txt` pokazuje šest grešaka:

- unused import;
- E402 import order;
- nesortirani importi;
- unused local variable.

Zbog toga status:

```text
OK
```

nije opravdan.

`verify.py` po vlastitim pravilima mora vratiti exit code 1 ako Ruff ne prolazi.

### Potrebna korekcija

Promijeniti završni status bundle-a u:

```text
PARCIJALNO
```

dok:

```bash
ruff format --check .
ruff check .
mypy src
python scripts/verify.py
```

ne prođu bez greške.

---

## 2.4 `mypy` nije pokrenut

Plan propisuje `mypy` kao dio Definition of Done, a `pyproject.toml` koristi:

```text
strict = true
```

Review navodi da mypy nije pokrenut jer zahtijeva zavisnosti. To nije prihvatljivo obrazloženje:

- FastAPI i SQLAlchemy su već instalirani jer su API testovi pokrenuti;
- razvojno okruženje treba instalirati iz `pyproject.toml`;
- ciljna provjera tipova je dio faze, ne opcioni dodatak.

### Potrebna korekcija

Pokrenuti u čistom Python 3.12 okruženju:

```bash
pip install -e ".[dev]"
mypy src
```

Sve greške ili opravdani `ignore` zapisi moraju biti dokumentovani.

---

# 3. Visoki rizici

## 3.1 Testovi su pokrenuti na Pythonu 3.14, a projekat cilja Python 3.12

Plan i `pyproject.toml` određuju Python 3.12, ali testni izlaz pokazuje:

```text
Python 3.14.1
```

To ne dokazuje kompatibilnost sa ciljnim runtimeom.

Dodatno se pojavljuje:

```text
Unknown config option: asyncio_mode
```

što vjerovatno znači da `pytest-asyncio` nije instaliran u okruženju koje je korišteno.

### Preporuka

Kreirati čisto okruženje sa Python 3.12 i ponoviti:

```bash
python -m pip install -e ".[dev]"
python scripts/verify.py
```

Python 3.14 može ostati dodatna kompatibilnosna provjera, ali ne smije zamijeniti ciljnu 3.12 provjeru.

---

## 3.2 SQLAlchemy sesije se ne zatvaraju

Dependency trenutno vraća:

```python
return request.app.state.session_factory()
```

ali nema `yield`, `close()` ni pouzdan rollback.

To može dovesti do:

- curenja konekcija;
- zadržavanja transakcija;
- zaključavanja SQLite baze;
- teško reproduktivnih problema nakon većeg broja zahtjeva.

### Ispravan pattern

```python
def get_session(request: Request):
    session = request.app.state.session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

Još bolje: commit/rollback treba imati jedno jasno vlasništvo, umjesto da svaki controller ručno radi `commit()`.

---

## 3.3 Poslovna logika transakcije je u Controlleru

Kontroleri odlučuju kada se radi:

```python
session.commit()
```

To otežava:

- testiranje servisa;
- atomske operacije kroz više repozitorija;
- centralni rollback;
- kasnije uvođenje Unit of Work obrasca.

Za FlowOS ne treba težak framework, ali treba jasan transakcioni boundary.

### Preporuka

Jedna od dvije opcije:

1. Service metoda upravlja kompletnom transakcijom;
2. request-scoped Unit of Work dependency commitira samo nakon uspješne Service operacije.

Ne miješati oba pristupa.

---

## 3.4 Status faze ima logičku grešku

U `PlanProgressService.derive_phase_status()` provjera:

```python
statuses.issubset({"IMPLEMENTED", "VERIFIED", "ACCEPTED"})
→ IMPLEMENTED
```

dolazi prije:

```python
statuses.issubset({"VERIFIED", "ACCEPTED"})
→ VERIFIED
```

Zbog toga faza čije su sve stavke `VERIFIED` ili `ACCEPTED` vraća:

```text
IMPLEMENTED
```

a ne `VERIFIED`.

### Korekcija

Specifičniji uslov mora doći prije šireg:

```python
if statuses.issubset({"VERIFIED", "ACCEPTED"}):
    return "VERIFIED"

if statuses.issubset({"IMPLEMENTED", "VERIFIED", "ACCEPTED"}):
    return "IMPLEMENTED"
```

Dodati test za:

```text
VERIFIED + ACCEPTED → VERIFIED
```

---

## 3.5 „Jedan aktivni plan po projektu“ nije sproveden

Plan zahtijeva samo jedan `ACTIVE` plan po projektu.

Trenutna aktivacija samo postavlja:

```python
plan.status = "ACTIVE"
```

ali:

- ne prebacuje prethodni aktivni plan u `SUPERSEDED`;
- nema database constrainta ili transakcione provjere;
- model čak nema jasno implementiran `SUPERSEDED` tok;
- progress query bira najnoviji `ACTIVE` ili čak `DRAFT`.

To može dati više aktivnih planova i pogrešan plan na GUI-ju.

### Preporuka

`PlanService.activate_plan()` mora u jednoj transakciji:

1. zaključati relevantne planove projekta;
2. prethodni `ACTIVE` postaviti na `SUPERSEDED`;
3. novi `DRAFT` postaviti na `ACTIVE`;
4. upisati audit događaj;
5. potvrditi da postoji tačno jedan aktivan plan.

Za SQLite se može dodati partial unique index:

```sql
CREATE UNIQUE INDEX ...
ON plans(project_id)
WHERE status = 'ACTIVE';
```

---

## 3.6 `GET resume` mijenja bazu

Endpoint:

```text
GET /projects/{id}/resume
```

poziva `regenerate()` i zatim `commit()`.

GET zahtjev bi trebalo da bude read-only. Trenutno čitanje resume-a ima side effect.

### Preporuka

Razdvojiti:

```text
GET  /projects/{id}/resume
POST /projects/{id}/resume/regenerate
```

`GET` čita postojeći materijalizovani sažetak.

`POST regenerate` ga ponovo izračunava i upisuje.

---

# 4. Runtime i sigurnosni problemi

## 4.1 Runtime modul nije stvarno prenosiv

`runtime.py` radi:

```python
from ctypes import windll, wintypes
kernel32 = windll.kernel32
```

prije provjere platforme.

Na sistemu koji nije Windows import modula može pasti prije nego što dođe do:

```python
if sys.platform != "win32":
```

Iako je Windows primarna platforma, kod ima Unix granu i testni/razvojni alati mogu importovati modul na drugoj platformi.

### Preporuka

Windows import staviti unutar:

```python
if sys.platform == "win32":
```

ili eksplicitno proglasiti modul Windows-only i ukloniti lažnu Unix podršku.

---

## 4.2 Runtime descriptor se ne upisuje atomski

Trenutno se koristi direktan:

```python
Path.write_text(...)
```

GUI može pročitati djelimično zapisan JSON ako pogodi trenutak upisa ili proces padne tokom pisanja.

### Preporuka

```text
service.json.tmp
→ flush/fsync
→ os.replace(tmp, service.json)
```

Dodati:

- `instance_id`;
- schema version;
- token/control ID ako se koristi lokalna autentikacija.

---

## 4.3 Postoji race condition između nalaženja porta i Uvicorn bind-a

Tok je:

```text
find_free_port()
→ zatvori test socket
→ write_descriptor()
→ uvicorn bind()
```

Između provjere i Uvicorn bind-a drugi proces može zauzeti port.

### Preporuka

Najmanje:

- descriptor upisati tek nakon što je server stvarno spreman;
- health/readiness potvrditi prije nego GUI vjeruje descriptoru;
- ako bind ne uspije, obrisati descriptor i osloboditi lock.

---

## 4.4 Lock i descriptor lifecycle su duplirani

`app.main()` radi cleanup u `finally`, a FastAPI lifespan takođe:

```text
delete_descriptor
release_lock
```

Dvostruki cleanup vjerovatno neće uvijek srušiti sistem, ali pokazuje nejasno vlasništvo.

### Preporuka

Odrediti jednog vlasnika:

- launcher/main posjeduje mutex i descriptor; ili
- lifespan posjeduje cijeli runtime lifecycle.

Za ovaj servis je čišće da `main()` bude supervisor, a lifespan upravlja aplikativnim resursima. Descriptor treba označiti „ready“ tek kada je FastAPI stvarno spreman.

---

## 4.5 CORS konfiguracija nije ispravna niti vjerovatno potrebna

```python
allow_origins=["http://127.0.0.1:*", "http://localhost:*"]
```

Starlette ne tretira ove vrijednosti kao wildcard port pattern.

PySide6 `QNetworkAccessManager` nije browser i CORS mu uglavnom nije potreban.

### Preporuka

Za MVP:

- ukloniti CORS;
- ili koristiti `allow_origin_regex` ako kasnije postoji stvaran browser klijent.

Važnija je lokalna autentikacija/session token, koja trenutno nije vidljiva u implementaciji.

---

## 4.6 Data direktorij ne koristi pouzdano `%LOCALAPPDATA%`

`get_data_directory()` koristi:

```python
Path.home() / "AppData" / "Local"
```

dok runtime descriptor koristi `LOCALAPPDATA`.

Ta dva izvora mogu odstupati.

### Preporuka

Napraviti jedan centralni `AppPaths` servis/objekat:

```text
runtime_dir
data_dir
logs_dir
artifacts_dir
spool_dir
backups_dir
```

Svi moduli moraju koristiti isti izvor.

---

# 5. API i contract problemi

## 5.1 Endpointi prihvataju i vraćaju generičke dict objekte

Mnoge rute koriste:

```python
data: dict
body: dict[str, Any]
```

i ručno prave response dict.

To potkopava svrhu Pydantic contract sloja:

- OpenAPI schema je slabija;
- validacija nije centralna;
- response oblik nije statički provjeren;
- mypy ne može pomoći;
- greške nisu uniformne.

### Preporuka

Koristiti:

```python
def create_project(command: ProjectCreate) -> ProjectResponse:
```

i response modele za sve rute.

Ne hvatati generički `Exception` oko Pydantic validacije. FastAPI već daje standardnu 422 validacionu grešku, ili se ona može mapirati centralnim exception handlerom.

---

## 5.2 Uniformni API error contract nije primijenjen

Plan traži:

```json
{
  "code": "...",
  "message": "...",
  "details": {},
  "correlation_id": "..."
}
```

Ali rute trenutno vraćaju:

```python
HTTPException(detail="...")
```

To ne koristi `ApiErrorResponse` koji je implementiran.

### Preporuka

Uvesti globalne exception handlere za:

- domain/service errors;
- not found;
- conflict;
- validation;
- unexpected error.

Svaka greška mora dobiti correlation ID i strukturisan oblik.

---

## 5.3 Route struktura odstupa od plana

Zbog `APIRouter(prefix="/plans")`, ruta:

```python
@router.get("/projects/{project_id}/plan-progress")
```

postaje:

```text
/plans/projects/{project_id}/plan-progress
```

Plan predviđa:

```text
/projects/{project_id}/plan-progress
```

Isto važi za import plana.

Ovo nije nužno funkcionalni kvar, ali je contract drift prije nego što je GUI uopšte napravljen.

### Preporuka

Sada uskladiti API putanje sa planom, dok nema klijenata koji zavise od njih.

---

# 6. Model i baza

## 6.1 Statusi su slobodni stringovi bez DB ograničenja

Većina statusa je:

```python
String(...)
```

bez `CheckConstraint`.

Servis može validirati normalne tokove, ali:

- direktna migracija;
- bug;
- test fixture;
- budući servis

mogu upisati nevalidnu vrijednost.

### Preporuka

Za ključne statusne kolone koristiti:

- SQLAlchemy Enum sa kontrolisanim native ponašanjem; ili
- `CheckConstraint`.

Najmanje za:

- plan status;
- plan item status;
- criterion status;
- resume status;
- reconciliation status.

---

## 6.2 JSON podaci se čuvaju kao Text

Polja sa sufiksom `_json` su tekst.

Za SQLite je to prihvatljivo u MVP-u, ali treba imati centralne serializer/deserializer funkcije i validaciju sheme. Ne dozvoliti proizvoljne stringove.

---

## 6.3 Brisanje projekta je hard delete

API već ima:

```text
DELETE /projects/{id}
```

Plan nije jasno tražio hard delete.

Zbog cascade odnosa to može ukloniti:

- taskove;
- planove;
- sesije;
- istoriju.

Za FlowOS, čija je vrijednost dugoročna memorija, hard delete je rizičan.

### Preporuka

U MVP-u koristiti:

```text
ARCHIVED
```

Hard delete dozvoliti samo kroz eksplicitnu administratorsku akciju sa backupom i potvrdom.

---

# 7. Review bundle i agent report problemi

## 7.1 Bundle nije čist

`git_status.txt` pokazuje:

```text
?? PI_AGENT_REVIEW_BUNDLE_INSTRUCTIONS.md
?? file
?? review_bundles/
```

To znači da working tree nije čist, a nepoznati fajl nazvan `file` je posebno sumnjiv.

Prije prihvatanja treba objasniti:

- šta je `file`;
- zašto su review artefakti untracked;
- da li pripadaju zadatku;
- da li ih treba ignorisati ili commitovati.

## 7.2 Agent report je nekonzistentan

U jednom dijelu se navodi da strukturisani logovi imaju rotaciju, a u drugom:

```text
Log fajlovi se ne rotiraju automatski
```

Kod koristi `RotatingFileHandler`, pa izvještaj nije ažuriran ili su spojeni reporti iz više trenutaka.

Završni report mora predstavljati trenutno stanje, a ne istorijski zbir kontradiktornih tvrdnji.

---

# 8. Preporučeni redoslijed popravki

## Blok 1 — dokaz i arhitektura

1. Popraviti architecture test path.
2. Dodati fail ako nije pronađen nijedan modul.
3. Pokrenuti test i evidentirati stvarne prekršaje.
4. Premjestiti ORM/query/commit logiku iz kontrolera u Services.
5. Ponovo pokrenuti architecture test.

## Blok 2 — verifikacija

1. Napraviti čisto Python 3.12 okruženje.
2. Instalirati `.[dev]`.
3. Popraviti Ruff greške.
4. Pokrenuti mypy strict.
5. Ukloniti pytest config warning.
6. Pokrenuti puni `scripts/verify.py`.

## Blok 3 — poznati funkcionalni kvarovi

1. Popraviti `derive_phase_status`.
2. Implementirati tačno jedan aktivni plan.
3. Razdvojiti GET resume od regenerate write operacije.
4. Uvesti session close/rollback lifecycle.
5. Uskladiti API putanje.

## Blok 4 — runtime pouzdanost

1. Centralni AppPaths.
2. Atomski descriptor.
3. `instance_id`.
4. Jedan vlasnik lifecycle cleanup-a.
5. Descriptor tek nakon readiness-a.
6. Ukloniti ili ispraviti CORS.
7. Dodati lokalni API token prije rizičnih write endpointa.

## Blok 5 — API contracts

1. Request/response Pydantic modeli.
2. Globalni error handler.
3. Bez ručnih dict mappera gdje već postoji contract.
4. Bez generic `Exception` validacije.

---

# 9. Predloženi status planiranih stavki

Na osnovu dostavljenog paketa:

```text
FLOW-101  IMPLEMENTED, nije još VERIFIED
FLOW-102  IMPLEMENTED, nije još VERIFIED
FLOW-103  IMPLEMENTED, NEEDS_REVIEW
FLOW-103A IMPLEMENTED, ima funkcionalni bug
FLOW-103B IMPLEMENTED, potreban contract i parser edge-case review
FLOW-103C PARCIJALNO, Controller krši arhitekturu
FLOW-103D IMPLEMENTED, ali API tok nije čist
FLOW-104  PARCIJALNO, Controller/persistence granica nije poštovana
FLOW-104A PARCIJALNO, GET ima side effect i Controller koristi ORM
```

Ne bih nijednu od ovih stavki još označio kao `VERIFIED` ili `ACCEPTED`.

---

# 10. Konačni zaključak

Ovo nije promašena implementacija. Naprotiv, postoji dobra baza i vidi se ozbiljan rad.

Ali najvažniji problem je što je paket sam sebe ocijenio kao potpuno ispravan, dok su ključni provjerivači:

- ili pali;
- ili nisu pokrenuti;
- ili nisu stvarno provjeravali kod.

To je upravo vrsta problema koju FlowOS treba da spriječi.

Moja preporuka je da se **ne prelazi na GUI još odmah**. Prvo napraviti jednu ograničenu korektivnu rundu za backend temelj. Ako se GUI počne graditi preko ovih API i arhitektonskih problema, kasnije će se morati popravljati i backend i GUI klijent istovremeno.

Nakon popravki treba poslati novi bundle sa:

```text
Ruff: PASS
mypy: PASS
architecture: stvarno skenirani moduli, PASS
pytest na Python 3.12: PASS
git status: čist ili objašnjen
API controlleri: bez ORM/persistence importa
```
