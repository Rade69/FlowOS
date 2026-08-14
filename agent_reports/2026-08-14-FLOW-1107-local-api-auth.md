---
flowos_report_version: 1
report_id: 7e60e09a-4418-4ccf-806f-e6852d44e6bf
agent: claude
model: claude-sonnet-5
session_id: unknown
report_type: implementation
work_status: completed
tasks:
  - FLOW-1107
commits: []
created_at: 2026-08-14T14:02:39+02:00
---

# FLOW-1107 — Zaštita lokalnog FlowOS API-ja

**Nije commitovano. Nije pushovano.** (eksplicitan zahtjev zadatka)

## BASELINE HEAD

```
git rev-parse HEAD → 3f22a4f101761918069e9e793aa3c3d6e1db6622
git log -1 --oneline → 3f22a4f fix: support reliable live GUI launch
```

Prije početka rada, tree je već sadržao neuklonjene izmjene iz prethodnog
zadatka u ovoj sesiji (FLOW-1104): `src/flowos/service/services/plan_import.py`
i `tests/unit/test_plan_import.py`. Te izmjene nisu moje, nisu dirane, i
namjerno su ostavljene netaknute u ovom zadatku (vidi `git status` ispod).

## THREAT CLOSED

Prije ovog zadatka, `flowos-service.exe` je na `127.0.0.1` slušao potpuno bez
autentikacije. Svaki lokalni proces (bilo koji korisnik ili malware na istoj
mašini) je mogao:
- čitati/mijenjati sve projekte, zadatke, sesije, konflikte preko REST API-ja,
- pozvati `/shutdown` i ugasiti servis,
- povezati se na `/ws` i primati sve real-time događaje (uključujući sadržaj
  plana, imena projekata, putanje repoa).

Poslije ovog zadatka: svaka ruta osim `/health` zahtijeva
`Authorization: Bearer <trenutni-instance-token>`; token je nasumičan,
nov pri svakom pokretanju servisa, i nikad se ne čuva trajno niti dijeli
preko URL-a.

## TOKEN GENERATION

`src/flowos/service/services/infrastructure/runtime.py`, `RuntimeManager.__init__`:

```python
self._token: str = secrets.token_urlsafe(32)
```

- `secrets.token_urlsafe(32)` — kriptografski siguran generator (CSPRNG),
  ne `random`, ne UUID, ne hash od PID-a/porta/vremena.
- Generiše se JEDNOM po `RuntimeManager` instanci, u `__init__`, prije nego
  što je port ili descriptor poznat.
- Odvojen od `instance_id` (koji je `uuid.uuid4()` upisan u descriptor kao
  neosjetljiv identifikator, nikad korišten za autorizaciju).

## TOKEN STORAGE/DISCOVERY

- Token se NE čuva u SQLite, NE čuva se u odvojenom fajlu pored descriptor-a.
- Živi samo u memoriji procesa (`RuntimeManager._token`) i u runtime
  descriptor JSON-u (`service.json`) koji GUI/CLI već čita da bi saznao
  port — polje `"token"` je dodano uz postojeće `pid`, `port`, `instance_id`.
- Descriptor fajl je u istom runtime direktorijumu kao i prije (lokalni
  filesystem, isti trust boundary kao i sam port-discovery mehanizam iz
  FLOW-1103 — nije uveden novi kanal niti novo mrežno izlaganje).
- GUI čita `port` i `token` iz ISTOG `_read_descriptor()` poziva, u jednom
  atomskom snapshotu (`ServiceConnection(port, token)` frozen dataclass) —
  eliminiše klasu bugova gdje bi GUI zadržao stari port ili stari token iz
  prethodnog čitanja.

## TOKEN ROTATION

- Nov token pri SVAKOM pokretanju `flowos-service.exe` (novi `RuntimeManager()`
  → nov `secrets.token_urlsafe(32)`) — dokazano testom
  `TestRuntimeManager::test_token_is_new_per_instance` (dvije instance,
  `token != token`).
- Token prethodne instance se odbija na novoj instanci — dokazano testom
  `TestInstanceAuth::test_previous_instance_token_rejected_on_new_instance`
  (instanca A i instanca B sa različitim tokenima; token A odbijen na B,
  token B prihvaćen na B) i
  `TestWebSocketAuth::test_websocket_stale_token_rejected` (WS strana).
- Nema perzistencije tokena između restartova — restart uvijek znači novi
  token, stari legitimno prestaje da radi.

## PUBLIC ROUTES

```python
PUBLIC_PATHS = frozenset({"/health"})
```

Samo `/health` ostaje bez auth zahtjeva — potrebno jer FLOW-1103 GUI bootstrap
(`_is_service_healthy()`) provjerava da je servis živ PRIJE nego što GUI ima
priliku pročitati token iz descriptor-a. Svaka druga ruta, uključujući
`/shutdown*`, `/ws`, i sve iz svih 10 controller fajlova, je iza auth
middleware-a po default-u — whitelist pristup (eksplicitna dozvola), ne
blacklist.

## PROTECTED HTTP ROUTES

Centralna provjera je FastAPI `@app.middleware("http")` u
`composition_root.py::create_app()`, PRIJE `app.include_router(...)` poziva —
pokriva SVE rute svih 10 controller fajlova (system, projects, tasks,
sessions, conflicts, plan_progress, project_resume, reports, verification,
worktrees) iz jednog mjesta, bez copy-paste `Depends()` po ruti (~50+ ruta).

```python
@app.middleware("http")
async def _instance_auth_middleware(request: Request, call_next):
    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)
    runtime_mgr = getattr(request.app.state, "runtime", None)
    expected = getattr(runtime_mgr, "token", None) if runtime_mgr is not None else None
    if not verify_bearer_token(expected, request.headers.get("authorization")):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)
```

Dokazano da auth radi PRIJE routing-a (401 na nepostojeću rutu bez tokena,
ne 404) — `TestInstanceAuth::test_unknown_path_without_token_also_rejected`.

## SHUTDOWN AUTH

`/shutdown`, `/shutdown/prepare`, `/shutdown/confirm`, `/shutdown/status` nisu
u `PUBLIC_PATHS` — isti middleware ih štiti kao i sve ostalo. Dokazano:
`TestInstanceAuth::test_shutdown_without_token_rejected` (401) i
`test_shutdown_with_valid_token_works` (200, ispravan tok).

GUI strana: `_do_shutdown_confirm()` šalje kroz `self._api._post(...)`, koji
interno poziva `_apply_auth_header()` na svaki zahtjev — shutdown je
automatski autentifikovan bez posebnog koda po pozivu.

## GUI AUTH PROPAGATION

`GuiApiClient` prima `token` u konstruktoru, `_apply_auth_header()` dodaje
`Authorization: Bearer <token>` na SVAKI zahtjev (`_get`, `_post`, `_delete`)
prije slanja preko `QNetworkAccessManager`.

`create_gui()` u GUI `composition_root.py`:

```python
connection = ensure_service_running()  # ServiceConnection(port, token) - JEDAN snapshot
api = GuiApiClient(base_url=f"http://127.0.0.1:{connection.port}", token=connection.token)
```

`port` i `token` dolaze iz ISTOG `ServiceConnection` objekta — struktura
sprječava mješavinu porta jedne instance sa tokenom druge. Dokazano testom
`TestGuiCredentialPropagation::test_create_gui_live_propagates_confirmed_token`
i setom `TestGuiApiClientAuthPropagation` (5 testova nad stvarnim
`QNetworkRequest` objektima presretnutim na `QNetworkAccessManager` nivou).

## WEBSOCKET AUTH

FastAPI/Starlette HTTP middleware se NE primjenjuje na WebSocket ASGI scope
(potvrđeno tokom rekognosciranja) — auth za `/ws` je implementirana odvojeno,
unutar samog endpointa, ali dijeli ISTI `verify_bearer_token()` primitiv sa
HTTP stranom (nema dvije divergentne implementacije iste provjere):

```python
async def ws_endpoint(ws: WebSocket):
    if not _is_authorized(ws):
        await ws.close(code=4401)
        return
    await event_bus.connect(ws)  # accept() se dešava OVDJE, tek poslije provjere
    ...
```

Konekcija se NIKAD ne pretvara u aktivan FlowOS event klijent (nikad ne stiže
do `event_bus.connect()` → `ws.accept()`) bez validnog trenutnog tokena.
GUI strana šalje token kroz `QNetworkRequest` header pri `QWebSocket.open(req)`
pozivu (empirijski potvrđeno probom da PySide6 `QWebSocket.open(QNetworkRequest)`
podržava custom header-e preko `setRawHeader()`), nikad kroz `QWebSocket.open(QUrl)`.

Dokazano setom `TestWebSocketAuth` (5 testova): bez tokena odbijen, pogrešan
token odbijen, token druge/stare instance odbijen, ispravan token prihvaćen,
token u URL-u bez header-a odbijen.

## TOKEN IN URL

Token se NIGDJE ne pojavljuje u URL-u — ni HTTP ni WebSocket:
- HTTP: isključivo `Authorization` header (GUI klijent, testovi).
- WebSocket: isključivo `Authorization` header na `QNetworkRequest`/handshake,
  nikad query string.
- Backend NIKAD ne čita token iz query stringa — dokazano eksplicitno
  `TestWebSocketAuth::test_token_not_in_url` (token samo u URL-u, bez
  header-a → odbijen).

## STALE TOKEN REJECTED

Pokriveno u TOKEN ROTATION i WEBSOCKET AUTH iznad: token prethodne (ugašene
ili restartovane) instance se odbija i na HTTP i na WebSocket strani, jer se
svaka provjera radi protiv `runtime.token` TRENUTNE, žive instance
(`request.app.state.runtime.token` / `ws.app.state.runtime.token`), nikad
protiv trajno sačuvane vrijednosti.

## SECRET LEAK CHECK

Ciljana `grep` provjera preko svih izmijenjenih fajlova: token vrijednost se
NIGDJE ne prosljeđuje u `logger.*()` ili `print()` poziv. Logovi u
`_make_lifespan` i `_instance_auth_middleware` referenciraju `pid`, `port`,
`project_id`, `repo_path`, brojeve događaja — nikad `token` ili `Authorization`
header sadržaj.

401 odgovor middleware-a vraća samo `{"detail": "Unauthorized"}` — ne
otkriva očekivani token, ne otkriva dužinu tokena, ne otkriva djelimično
podudaranje. Dokazano testom
`TestInstanceAuth::test_401_body_does_not_leak_expected_token`.

Testovi koriste isključivo lažne, hardkodovane test-tokene
(`"noop-test-token"`, `"ws-test-token"`, `"confirmed-token-b"`, itd.) — nijedan
test ne loguje niti snimi stvarno generisan `secrets.token_urlsafe(32)` token.

## FLOW-1103 REGRESSION

`tests/gui/test_live_launch.py` (postojeći FLOW-1103 test fajl) ažuriran da
koristi novi `ServiceConnection(port, token)` ugovor umjesto bare `int` porta.
Svi originalni scenariji i dalje prolaze nepromijenjeni u suštini:
- postojeći zdrav servis se ponovo koristi (bez novog Popen-a),
- nov servis se pokreće i njegov (dinamički) port/token se čita iz NOVOG
  descriptora, ne starog 9100,
- startup failure (proces odmah izašao) baca `ServiceStartupError`,
- startup timeout (servis nikad ne postane zdrav) baca `ServiceStartupError`.

MOCK mod (`create_gui(use_live=False)`) ostaje potpuno nepromijenjen —
`gui._api is None`, nema Popen poziva, nema pokušaja auth-a
(`TestMockMode::test_mock_mode_requires_no_token`).

## SECURITY TARGETED TESTS

Novi/ažurirani testovi po zahtijevanoj matrici:

**HTTP (`TestInstanceAuth`, `tests/integration/test_composition_root.py`, 13 testova):**
`/health` bez tokena prolazi · zaštićen GET bez tokena odbijen · zaštićen GET
sa pogrešnim tokenom odbijen · zaštićen GET sa ispravnim tokenom prolazi ·
mutating POST bez tokena odbijen · shutdown bez tokena odbijen · shutdown sa
ispravnim tokenom radi · token prethodne instance odbijen na novoj instanci ·
nedostaje Authorization header · pogrešna shema (ne "Bearer") odbijena ·
prazan bearer token odbijen · token sa dodatnim whitespace odbijen · 401 tijelo
ne otkriva očekivani token · nepoznata ruta bez tokena takođe 401 (ne 404).

**GUI klijent (`TestGuiApiClientAuthPropagation` + `TestGuiCredentialPropagation`,
6 testova):** GET/POST/DELETE šalju Bearer token · bez tokena nema
Authorization header-a · token se nikad ne pojavljuje u URL-u · `create_gui()`
provlači TAČAN (port, token) par bez mješanja.

**WebSocket (`TestWebSocketAuth`, 5 testova):** bez tokena odbijen · pogrešan
token odbijen · token stare/druge instance odbijen · ispravan token prihvaćen
· token u URL-u bez header-a odbijen (dokaz da handshake ne zavisi od query
stringa).

**Token rotation (`TestRuntimeManager`, 2 testa):** nov token po instanci ·
token upisan u descriptor i različit od `instance_id`.

**Self-attack (ad-hoc probe, nije trajni test fajl):** duplirani
`Authorization` header — httpx/Starlette koristi PRVU vrijednost; ispitano oba
redoslijeda (`[wrong, real]` → odbijen jer se koristi "wrong" prvi;
`[real, wrong]` → prihvaćen jer se koristi "real" prvi). Zaključak: nije
iskoristivo kao ranjivost — napadač i dalje mora VEĆ posjedovati ispravan
token da bi konstruisao bilo koji prihvaćen poredak; nema privilege escalation
bez prethodnog posjedovanja tajne.

## scripts/verify.py rezultat

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

Kombinovani finalni test run svih FLOW-1107-relevantnih fajlova zasebno (radi
preciznije potvrde nakon posljednje izmjene — QTimer cross-test fix):

```
pytest tests/gui/test_live_launch.py tests/gui/test_api_client_auth.py \
       tests/gui/test_api_client_error_path.py \
       tests/integration/test_composition_root.py \
       tests/integration/test_service_runtime.py \
       tests/integration/test_websocket_auth.py
→ 60 passed, 1 warning in 36.91s
```

## PERFORMANCE IMPACT

Kako je zahtijevano — bez DB/Redis/JWT lookup-a po zahtjevu:
- HTTP: jedan in-memory `getattr()` + `hmac.compare_digest()` po zahtjevu
  (constant-time string poređenje, O(n) po dužini tokena — 43 karaktera).
  Nema I/O, nema baze, nema deserializacije potpisa.
- WebSocket: provjera se radi JEDNOM, na handshake-u, prije `accept()` —
  ne po poruci.
- Middleware dodaje jedan `if path in frozenset` (O(1) hash lookup) plus
  header read prije poziva stvarnog handlera — zanemarljivo u odnosu na
  SQLite upit koji svaka ruta ionako radi.

Nema mjerljivog očekivanog uticaja; nije rađen poseban benchmark jer promjena
ne dodaje nikakav sloj sa O(n) nad podacima ili mrežni poziv — dokaz je sama
implementacija (Hijerarhija dokaza: kod je dovoljan dokaz za "nema dodatnog
I/O", benchmark bi mjerio šum).

## FILES CHANGED

```
 scripts/verify.py                                  |   4 +-
 src/flowos/gui/composition_root.py                 |  70 +++++++----
 src/flowos/gui/services/client.py                  |  22 +++-
 src/flowos/service/composition_root.py             |  21 +++-
 src/flowos/service/controllers/websocket/events.py |  23 +++-
 src/flowos/service/services/infrastructure/runtime.py |  38 ++++++
 tests/gui/test_live_launch.py                      |  97 +++++++++++++--
 tests/integration/test_composition_root.py         | 138 +++++++++++++++++++++
 tests/integration/test_service_runtime.py          |  36 +++++-
 tests/gui/test_api_client_auth.py                  | NOV FAJL
 tests/integration/test_websocket_auth.py           | NOV FAJL
```

`scripts/verify.py` promjena je isključivo infrastrukturna (timeout
120s→240s, jer je unit+integration+contract suita narasla preko cijele
sesije na ~135s) — nije auth logika, ali je bila blokirajuća za obavezan
"verify.py 7/7" ishod ovog zadatka, i istovremeno je isti root cause koji sam
već prijavio kao nalaz L1 u prethodnom FLOW-1104 re-review izvještaju.

`src/flowos/service/services/plan_import.py` i `tests/unit/test_plan_import.py`
NISU moje izmjene (postojale su u tree-u prije početka ovog zadatka, iz
FLOW-1104) — namjerno netaknute.

## OUT OF SCOPE LEFT UNTOUCHED

Kako je eksplicitno traženo, sljedeće NIJE rađeno u ovom zadatku:
- DB modeli, Alembic migracije, plan parser, Task UI, Ledger, Git/worktree
  logika, agent execution/environment, verification execution, ACL, centralna
  secret redakcija, Managed Execution — nijedan od ovih fajlova nije
  dodirnut.
- FLOW-1108/1109/1110 nisu rađeni.
- Host/Origin header hardening nije implementiran (sekundarno po
  specifikaciji zadatka) — trenutna zaštita je isključivo bearer token; ako
  se ikad doda drugi trust boundary (npr. mrežni bind van loopback-a), Host/
  Origin provjera treba biti razmotrena tada, ne sada.
- ACL/role-based dozvole nisu implementirane — token je binaran (ima
  pristup / nema pristup), nema nivoa privilegija, u skladu sa zahtjevom.
- Centralna redakcija tajni u logovima/agent_report-ima nije implementirana
  kao opšti mehanizam — provjereno ručno (grep) da OVA promjena ne curi
  token, ali opšti redaction sistem ostaje van scope-a.

## FINDINGS

Klasifikacija po traženom formatu; nijedan nije BLOCKER za ovaj zadatak.

**LOW — GUI shutdown ruta ne odgovara stvarnoj backend ruti (pre-existing,
NIJE uveden ovim zadatkom).**
`src/flowos/gui/composition_root.py:168` i `:216` pozivaju
`f"{base_url}/system/shutdown/prepare"` i `"/system/shutdown/confirm"`, dok
stvarne rute u `src/flowos/service/controllers/http/system.py:53-87` su
`/shutdown`, `/shutdown/prepare`, `/shutdown/confirm`, `/shutdown/status`
(bez `/system` prefiksa). Ovo znači da GUI "Zaustavi sve i ugasi FlowOS" dugme
trenutno pogađa nepostojeću rutu (404) nezavisno od auth-a — pre-existing bug,
nije sigurnosni propust (401/404 oba blokiraju), ne pripada FLOW-1107 scope-u
(routing bug, ne auth bug). Nije popravljeno ovdje — dokumentovano kao nalaz
za budući zadatak.

**LOW — `scripts/verify.py` timeout 120s→240s (infrastrukturna izmjena, u
scope-u ovog zadatka jer je blokirala obavezan ishod).**
Test suita je narasla preko sesije; već prijavljeno kao L1 u prethodnom
FLOW-1104 re-review izvještaju. Popravljeno ovdje jer je bilo neophodno za
"verify.py 7/7" acceptance kriterij ovog zadatka.

**INFO — dupli `Authorization` header nije iskoristiva ranjivost.**
Vidi SECURITY TARGETED TESTS / self-attack odjeljak iznad — probano, nije
exploit, samo dokumentovano ponašanje (koristi se prvi header u listi).

## Nezavisna provjera

Nije rađena od strane drugog agenta/modela u ovom zadatku (out of scope
zadatka je bio implementacija + samostalna self-attack provjera, ne
dvostruki review). Preporučuje se GitNexus impact/detect_changes i/ili
ljudski review prije merge-a, u skladu sa CLAUDE.md pravilom za
HIGH/CRITICAL sigurnosne izmjene.

## Rizici i ograničenja

- Token je vidljiv u plain-textu u runtime descriptor JSON fajlu na disku —
  isti trust boundary kao postojeći port-discovery mehanizam iz FLOW-1103
  (lokalni filesystem, isti korisnik). Nije novo izlaganje, ali vrijedi
  eksplicitno navesti: bilo koji proces sa čitanjem tog fajla dobija pun
  pristup API-ju dok je instanca živa.
- Nema Host/Origin provjere — CSRF-stil napad sa lokalnog browsera (da
  browser ima i dalje pristup fajlu sa tokenom je druga priča) nije
  eksplicitno adresiran, po dizajnu ovog zadatka (sekundarno, ne blokira).
- Middleware pristup (umjesto `Depends()`) znači da svaka BUDUĆA nova ruta
  je AUTOMATSKI zaštićena po default-u (whitelist) — ovo je namjerna
  odluka radi sigurnosti-po-defaultu, ali znači da svaka buduća javna ruta
  mora biti eksplicitno dodata u `PUBLIC_PATHS`, inače će GUI/klijent dobiti
  401 dok se to ne uradi.

## Potreban follow-up

- Popraviti GUI shutdown rutu (`/system/shutdown/prepare` → `/shutdown/prepare`)
  u zasebnom, malom zadatku — nije auth propust, ali je funkcionalni bug.
- Razmotriti Host/Origin hardening ako se ikad doda mrežni bind van
  loopback-a (trenutno nije potrebno).
- FLOW-1108/1109/1110 (izvan scope-a ovog zadatka) mogu sada graditi na ovom
  auth sloju.

## Potrebna korisnička potvrda

Nijedna HIGH/CRITICAL arhitektonska odluka nije zahtijevala odstupanje od
specifikacije zadatka — implementacija prati sve navedene zahtjeve tačno kako
je traženo (middleware umjesto per-route Depends, header umjesto URL, jedan
`verify_bearer_token()` umjesto dvije implementacije). Korisnik treba
potvrditi da je GUI shutdown ruta nalaz (LOW) prihvatljiv kao zaseban
follow-up, ne blocker za ovaj zadatak.

## FINAL SELF-CHECK

| Pitanje | Očekivano | Stvarno | Dokaz |
|---|---|---|---|
| Servis i dalje samo loopback (127.0.0.1)? | YES | YES | `find_free_port`/`_port_is_free` binduju na `"127.0.0.1"`; nedirano ovim zadatkom |
| `/health` ostaje javan? | YES | YES | `PUBLIC_PATHS = frozenset({"/health"})`, test `test_health_without_token_passes` |
| Mutating rute zaštićene? | YES | YES | `test_mutating_post_without_token_rejected` |
| Shutdown zaštićen? | YES | YES | `test_shutdown_without_token_rejected`, `test_shutdown_with_valid_token_works` |
| WebSocket zaštićen? | YES | YES | `TestWebSocketAuth` (5 testova), `close(code=4401)` prije `accept()` |
| Trenutni token generisan po instanci? | YES | YES | `secrets.token_urlsafe(32)` u `__init__`, `test_token_is_new_per_instance` |
| Stari token odbijen poslije restarta? | YES | YES | `test_previous_instance_token_rejected_on_new_instance`, `test_websocket_stale_token_rejected` |
| `instance_id` ponovo korišten kao tajna? | NO | NO | `instance_id` (uuid4) i `token` (token_urlsafe) su odvojena polja; auth koristi isključivo `token` |
| Token čuvan u SQLite? | NO | NO | Živi samo u memoriji + descriptor JSON, nema DB modela/kolone |
| Token se pojavljuje u URL-u? | NO | NO | `test_token_never_appears_in_url`, `test_token_not_in_url` |
| Token se pojavljuje u logovima? | NO | NO | Ciljani grep — nijedan `logger.*`/`print` poziv ne referencira token vrijednost |
| MOCK mod sačuvan? | YES | YES | `test_mock_mode_does_not_launch_backend`, `test_mock_mode_requires_no_token` |
| FLOW-1103 ponašanje sačuvano? | YES | YES | `test_live_launch.py` regresija — svi originalni scenariji prolaze |
| DB/migracije mijenjane? | NO | NO | `git status` — nijedan model/migracioni fajl u diff-u |
| ACL slučajno implementiran? | NO | NO | Token je binaran (ima/nema pristup), nema rola/permisija |
| Centralna redakcija slučajno implementirana? | NO | NO | Nema novog redaction mehanizma; samo ciljana provjera da OVA promjena ne curi |
| `scripts/verify.py` 7/7? | YES | YES | Vidi odjeljak iznad — 7/7 PASS |

## STOP CONDITION

**FLOW-1107 — Zaštita lokalnog FlowOS API-ja = READY FOR SECURITY REVIEW**

Do NOT commit. Do NOT push. (poštovano — nijedan `git add`/`git commit` nije
izvršen tokom ovog zadatka.)
