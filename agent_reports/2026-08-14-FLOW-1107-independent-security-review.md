---
flowos_report_version: 1
report_id: 64d2c37f-6b25-4d0c-a37f-1c90f808432b
agent: claude
model: claude-sonnet-5
session_id: unknown
report_type: review
work_status: completed
tasks:
  - FLOW-1107
commits: []
created_at: 2026-08-14T15:16:08+02:00
---

# FLOW-1107 — Zaštita lokalnog FlowOS API-ja — nezavisni adversarial security review

READ ONLY. Nije mijenjan kod, nisu mijenjani testovi, nije pravljen commit, nije pushovano.

## 1. Scope i baseline

```
git rev-parse HEAD → b5de4c395bfe3bd5d16f3d8ad5fd31618e5c274b
```

Zadatak je očekivao HEAD `4b3295ba865e08300d8c79b3ac1ce4f8ff40575c`. Stvarni HEAD je dva
commita dalje jer su u međuvremenu, na eksplicitan korisnički zahtjev ("Pogledaj i očisti
ovo" — čišćenje Source Control panela), napravljena dva ČISTO docs/agent_reports commita:

```
git log 4b3295b..b5de4c3 --oneline
b5de4c3 docs: add dogfooding plan, security analysis, and context planning docs
187dbc4 docs: add live GUI runtime review evidence (2026-08-12)
```

Nezavisno potvrđeno (`git diff 4b3295b b5de4c3 --name-only`) da ta dva commita dodiruju
ISKLJUČIVO `agent_reports/*.md`, `agent_reports/gui_runtime_2026-08-12/*.png` i `docs/*.md`
— nijedan FLOW-1107 source/test fajl. Working-tree diff (`git diff --stat` protiv trenutnog
HEAD-a) je bajt-za-bajt identičan onome iz implementation reporta (9 fajlova, 404
insertions/45 deletions) — nema neočekivane mutacije izvornog koda.

```
git diff --name-only
scripts/verify.py
src/flowos/gui/composition_root.py
src/flowos/gui/services/client.py
src/flowos/service/composition_root.py
src/flowos/service/controllers/websocket/events.py
src/flowos/service/services/infrastructure/runtime.py
tests/gui/test_live_launch.py
tests/integration/test_composition_root.py
tests/integration/test_service_runtime.py

+ untracked: agent_reports/2026-08-14-FLOW-1107-local-api-auth.md,
  tests/gui/test_api_client_auth.py, tests/integration/test_websocket_auth.py
```

Svih 9+3 fajlova se poklapa tačno sa listom navedenom u zadatku. `scripts/verify.py` je
inspektovan i klasifikovan ODVOJENO (vidi §21).

## 2. Threat model — potvrđen i primijenjen

Precizna granica koju sam koristio tokom cijelog reviewa: FLOW-1107 NE brani od napadača
koji već ima proizvoljan file-read pristup kao isti Windows korisnik. FLOW-1107 SPREČAVA
da lokalni proces/browser/zahtjev kontroliše/čita FlowOS API ili WebSocket SAMO na osnovu
otkrivanja loopback porta. Sve nalaze niže sam klasifikovao u odnosu na OVU granicu, ne
protiv šireg (out-of-scope) modela.

## 3. TOKEN GENERATION

`secrets.token_urlsafe(32)` u `RuntimeManager.__init__` — kriptografski CSPRNG, nezavisan
od PID-a/porta/instance_id/vremena (potvrđeno čitanjem koda: token se generiše PRIJE nego
što je port poznat).

**Stvarni lifecycle** (ne samo unit test) — pročitan `src/flowos/service/app.py::main()`:

```python
runtime = RuntimeManager()      # JEDNA instanca po procesu, cijeli poziv main()
runtime.acquire_lock()
port = runtime.find_free_port()
runtime.write_descriptor(port)  # token već postoji od __init__
...
app = create_app(runtime)       # ISTA instanca prosleđena dalje
uvicorn.run(app, ...)
```

`RuntimeManager()` se konstruiše TAČNO JEDNOM po pokretanju `flowos-service.exe`. Nema
koda koji bi kreirao drugu `RuntimeManager` instancu unutar istog service lifecycle-a —
nema rizika od neočekivane rotacije tokena unutar žive instance. Token je konstantan za
cijeli vijek trajanja procesa.

Testom `TestRuntimeManager::test_token_is_new_per_instance` (fresh run, PASSED) potvrđeno
da DVIJE odvojene `RuntimeManager()` instance dobiju različite tokene.

**Verdikt: ACCEPT.**

## 4. DESCRIPTOR PORT+TOKEN CONSISTENCY

`ServiceConnection(port, token)` frozen dataclass osigurava da GUI UVIJEK čita oba polja
iz JEDNOG `_read_descriptor()` poziva — strukturno onemogućava mješavinu porta jedne
instance sa tokenom druge unutar te funkcije.

Descriptor write je atomski (`tmp.write_text(...)` → `tmp.replace(DESCRIPTOR_FILE)`, što je
na NTFS-u atomičan rename) — čitalac nikad ne vidi djelimično upisan JSON.

**Analizirana race putanja (A: stari descriptor postoji / B: novi servis starta / C: GUI
vidi mješavinu):** `ensure_service_running()` čita descriptor JEDNOM (`_read_descriptor()`),
pa ODMAH provjerava `_is_service_healthy(candidate.port)` NA TOM ISTOM pročitanom portu.
Pošto `RuntimeManager.acquire_lock()` koristi sistemski mutex (`Global\FlowOS_Service_Mutex`
na Windowsu), DRUGA instanca ne može upisati SVOJ descriptor dok je prva živa — mutex mora
biti oslobođen (proces mora umrijeti) prije nego iko drugi može ponovo `write_descriptor()`.

Postoji uzak teorijski prozor: ako instanca B umre i NEKO DRUGO (potpuno odvojeno, ne iz
iste `ensure_service_running()` petlje — ta petlja pokreće SAMO JEDAN `subprocess.Popen()`
na početku) pokrene instancu C na ISTOM portu unutar par stotina milisekundi između čitanja
descriptora i health-check odgovora, GUI bi mogao upariti STARI token (B) sa health-check
odgovorom koji je zapravo od C (jer `/health` ne zahtijeva auth i ne identifikuje koja
instanca odgovara). **Posljedica nije neovlašćen pristup** — GUI bi zatim slao token B na
instancu C, koja bi ga ODBILA (401), jer C očekuje token C. Ovo je fail-CLOSED ishod
(GUI ostaje "zaglavljen" bez pristupa dok se ne restartuje), ne bypass. Takođe zahtijeva da
napadač već ima lokalnu sposobnost pokretanja `flowos-service.exe` procesa — što je izvan
navedenog threat modela (isti-korisnik file-read/process-launch je eksplicitno isključen).

**Verdikt: ACCEPT** (LOW finding dokumentovan u §24, nije blocker).

## 5. DESCRIPTOR FAILURE MODES — fail-closed potvrđeno čitanjem koda

```python
def _read_descriptor() -> ServiceConnection | None:
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None                                    # malformed JSON / missing file → None
    port = data.get("port")
    token = data.get("token")
    if not (isinstance(port, int) and 1024 <= port <= 65535):
        return None                                    # missing/malformed port → None
    if not (isinstance(token, str) and token):
        return None                                    # missing/EMPTY token → None
    return ServiceConnection(port=port, token=token)
```

`isinstance("", str) and ""` → `False` → prazan string token se TRETIRA kao nevalidan
(Python truthiness), ne kao validan prazan kredencijal. Kad `_read_descriptor()` vrati
`None`, `ensure_service_running()` NIKAD ne konstruiše `GuiApiClient` sa praznim/lažnim
tokenom — umjesto toga pokušava `subprocess.Popen(...)` (novi servis) i čeka NOVI, validan
descriptor prije nego vrati bilo šta pozivaocu. Nema koda puta koji bi tiho napravio
neautentifikovan LIVE klijent.

**Scenario "descriptor promijenjen između health-check i GUI client construction":**
`ensure_service_running()` vraća JEDAN `ServiceConnection` objekat (iz JEDNOG čitanja),
i `create_gui()` odmah, sinhrono, konstruiše `GuiApiClient(port=connection.port,
token=connection.token)` iz TE ISTE vrijednosti — nema drugog čitanja descriptora između
health-check-a i client construction-a unutar `create_gui()`. Provjereno čitanjem koda
(`src/flowos/gui/composition_root.py:501-503`).

**Verdikt: ACCEPT.**

## 6. HTTP AUTH BOUNDARY — adversarial probe (real ASGI requests, ne pretpostavka iz layout-a)

Napisan i pokrenut nezavisan probe (`TestClient` protiv stvarno konstruisanog `create_app()`)
koji šalje prave ASGI zahtjeve kroz middleware stack:

| Zahtjev | Rezultat | Analiza |
|---|---|---|
| `GET /projects/` (trailing slash, valid token) | 200 | Router prihvata obje varijante, OBJE zahtijevaju isti token — nema bypass-a |
| `GET /health/` (trailing slash, NO token) | 401 | Nije exact match za `/health` — middleware zahtijeva auth, router zatim 404. Konzervativnije od očekivanog, ne slabije |
| `GET /%68ealth` (percent-encoded, NO token) | 200 | ASGI server (uvicorn) dekodira path PRIJE nego stigne do middleware-a I do router-a — ISTI string se koristi za oba, pa nema raskoraka. Dekodira se u `/health`, koji je legitimno javan i ne nosi osjetljive podatke — nije bypass zaštićene rute |
| `GET /./health` (dot-segment, NO token) | 200 | Isto obrazloženje — normalizuje se u `/health` prije oba provjere |
| `GET //health` (double slash, NO token) | 401 | Ne normalizuje se u `/health` — tretirano kao nepoznata/zaštićena putanja |
| `GET /Health` (case-different, NO token) | 401 | Case-sensitive path match, nema bypass-a |
| `HEAD /projects` (NO token) | 401 | HEAD je zaštićen isto kao GET |
| `OPTIONS /projects` (NO token) | 401 | CORS preflight OPTIONS je TAKOĐE zaštićen — vidi §14 zašto je ovo dodatna, ne manjkava, zaštita |
| `HEAD /health` (NO token) | 405 | Nema HEAD handlera za `/health` — REST kompletnost nedostatak, NE sigurnosni nalaz (FLOW-1103 polling koristi GET, ne HEAD) |
| `GET /does-not-exist` (NO token) | 401 | Auth middleware izvršava se PRIJE routing-a |
| `GET /does-not-exist` (valid token) | 404 | Potvrđuje da middleware zaista prethodi router-u, ne obrnuto |

**Ključan arhitektonski nalaz (pozitivan):** middleware (`request.url.path`) i router
koriste TAČNO ISTI dekodirani path string iz ASGI scope-a — ASGI server (uvicorn) radi
percent-decode/normalizaciju JEDNOM, prije nego Starlette bilo šta vidi. Zato je STRUKTURNO
nemoguće da middleware i router "vide" različite reprezentacije iste putanje (tzv. path
confusion / parser differential napad) — nema odvojenog parsing koraka između auth provjere
i route matchinga.

Provjereno da nema `app.mount(...)` sub-app-ova (`grep` na `.mount(`, `add_middleware`,
`StaticFiles` u `src/flowos/service` — 0 rezultata) — nema alternativnog ASGI puta koji
bi zaobišao middleware.

`PUBLIC_PATHS == frozenset({"/health"})` — potvrđeno da sadrži TAČNO i SAMO namjeravanu
rutu.

**Verdikt: ACCEPT.**

## 7. /health PUBLICNESS

```python
@router.get("/health")
async def health():
    return {"status": "ok", "uptime": time.time() - _start_time}
```

Payload sadrži ISKLJUČIVO status string i uptime broj. Ne curi token, descriptor sadržaj,
repo putanje, project podatke niti runtime internals. `/version` i `/runtime` (koji DO
otkrivaju pid/port/data_directory) NISU u `PUBLIC_PATHS` — zaštićeni su, potvrđeno testom
`test_version_without_token_rejected` (fresh run, PASSED) i probom iznad.

**Verdikt: ACCEPT.**

## 8. SHUTDOWN PROTECTION

Sve četiri rute (`/shutdown`, `/shutdown/prepare`, `/shutdown/confirm`, `/shutdown/status`)
definisane u `system.py` bez `/system` prefiksa, nijedna nije u `PUBLIC_PATHS` — sve
zahtijevaju auth. Probom potvrđeno: `POST /shutdown/prepare` i `GET /shutdown/status` bez
tokena → 401. Testovima potvrđeno (`test_shutdown_without_token_rejected`,
`test_shutdown_with_valid_token_works`, fresh run, PASSED).

**GUI shutdown routing bug — nezavisno potvrđeno, CONFIRMED:**

```
src/flowos/gui/composition_root.py:168 → f"{base_url}/system/shutdown/prepare"
src/flowos/gui/composition_root.py:216 → "/system/shutdown/confirm"
src/flowos/service/controllers/http/system.py:53,59,81,87 → router bez /system prefiksa:
    /shutdown, /shutdown/prepare, /shutdown/confirm, /shutdown/status
```

GUI "Zaustavi sve i ugasi FlowOS" dugme trenutno pogađa nepostojeću rutu (bilo bi 404,
nezavisno od auth statusa). Ovo je FUNKCIONALNI bug, NE sigurnosni propust — 401 i 404 oba
fail-closed, nema neovlašćenog pristupa ni u jednom slučaju. Potvrđeno nezavisno (nisam se
oslonio na implementation report), nije popravljeno (ispravno van scope-a).

**Verdikt shutdown auth: ACCEPT. GUI shutdown routing: CONFIRMED (pre-existing, future-task).**

## 9. BEARER PARSING

```python
def verify_bearer_token(expected, header_value) -> bool:
    if not expected or not header_value:
        return False
    scheme, _, received = header_value.partition(" ")
    if scheme.lower() != "bearer" or not received:
        return False
    return hmac.compare_digest(received, expected)
```

Probom potvrđeno ponašanje za SVAKI traženi slučaj:

| Ulaz | Rezultat |
|---|---|
| bez header-a | 401 |
| `Basic real-token` | 401 (pogrešna šema) |
| `Bearer` (bez razmaka/tokena) | 401 (`received` prazan) |
| `Bearer ` (razmak, prazan token) | 401 |
| pogrešan token | 401 |
| `Bearer real-token   ` (trailing spaces) | 401 (`compare_digest` exact match, whitespace je dio poređenog stringa) |
| `Bearer  real-token` (dvostruki razmak) | 401 (`partition(" ")` dijeli na PRVI razmak, pa `received` sadrži vodeći razmak) |
| `bearer real-token` (lowercase scheme) | **200** — `scheme.lower()` čini shemu case-insensitive |
| `BEARER real-token` (uppercase scheme) | **200** — isto |
| `Bearer REAL-TOKEN` (token drugog case-a) | 401 — sam TOKEN ostaje case-sensitive (`compare_digest` exact byte match) |
| ispravan | 200 |

Case-insensitive SCHEME (Bearer/bearer/BEARER) je RFC 7235-kompatibilno ponašanje (auth
scheme nazivi su case-insensitive po HTTP spec-u) — ne slabi sigurnost, jer sam TOKEN
poređenje ostaje strogo case-sensitive i constant-time (`hmac.compare_digest`).

**Duplicate Authorization header:**

```
[wrong, real]: 401   (koristi se PRVI header — "wrong")
[real, wrong]: 200   (koristi se PRVI header — "real")
```

`request.headers.get("authorization")` (Starlette) vraća PRVU vrijednost kad je header
dupliran. Ovo NIJE iskoristiva ranjivost — poredak zavisi isključivo od onoga ko šalje
zahtjev, a napadač MORA već posjedovati ispravan token da bi konstruisao BILO KOJI
prihvaćen poredak. Nema privilege escalation bez prethodnog posjedovanja tajne.

**401 body leak check:** `{"detail":"Unauthorized"}` — ne otkriva očekivani token, dužinu,
niti djelimično poklapanje. Potvrđeno probom i testom
`test_401_body_does_not_leak_expected_token`.

**Verdikt: ACCEPT.**

## 10. WEBSOCKET AUTH BOUNDARY — CRITICAL, potvrđeno čitanjem stvarnog izvršnog toka

```python
async def ws_endpoint(ws: WebSocket):
    if not _is_authorized(ws):
        await ws.close(code=4401)
        return
    await event_bus.connect(ws)   # accept() se dešava OVDJE
    ...
```

`event_bus.connect()` interno poziva `await ws.accept()`. Auth provjera (`_is_authorized`)
se izvršava PRIJE bilo kakvog poziva `accept()`, PRIJE registracije kao aktivan klijent, i
PRIJE bilo kakve emisije podataka. `ws.close(code=4401)` prije `accept()` je framework-valid
Starlette/ASGI ponašanje — zatvara handshake bez икада prihvatanja WS konekcije; potvrđeno
empirijski (test i probe): klijent dobija `WebSocketDisconnect`, nikad ne uspije primiti
poruku.

Klijent koristi header (`Authorization`), NE query string — potvrđeno testom
`test_token_not_in_url` (token SAMO u URL-u, bez header-a → odbijen) i sirovim TCP capture-om
(§11).

FastAPI middleware (`@app.middleware("http")`) se NE primjenjuje na WebSocket ASGI scope —
zato je WS auth implementirana ODVOJENO unutar `ws_endpoint`, ali dijeli ISTI
`verify_bearer_token()` primitiv sa HTTP stranom (potvrđeno čitanjem `events.py:19,89-97`)
— nema dvije divergentne implementacije iste provjere.

**Verdikt: ACCEPT.**

## 11. QWEBSOCKET CLIENT REALITY — definitivan dokaz, ne ad-hoc probe

Instalirana verzija: **PySide6 6.11.1**. Umjesto da se oslonim na raniji ad-hoc dev probe,
napravljen je nov, rigorozniji test: sirov TCP server koji hvata DOSLOVNE bajtove
WebSocket handshake zahtjeva koje šalje `QWebSocket.open(QNetworkRequest)`:

```
=== RAW CAPTURED HANDSHAKE REQUEST (stvarni bajtovi sa žice) ===
GET /ws HTTP/1.1
Host: 127.0.0.1:50095
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: by5POpLaWSANXWmHLCFPDg==
Sec-WebSocket-Version: 13
authorization: Bearer probe-token-xyz
```

**Definitivno potvrđeno**: `QNetworkRequest.setRawHeader(b"Authorization", ...)` +
`QWebSocket.open(QNetworkRequest)` STVARNO stavlja `Authorization` header na handshake
zahtjev kod instalirane PySide6 6.11.1 verzije. Header ime stiže kao `authorization`
(lowercase) na žici — ovo je HTTP-spec-kompatibilno (header imena su case-insensitive po
RFC 7230), i FastAPI/Starlette `request.headers.get("authorization")` (odn. WS ekvivalent
`ws.headers.get("authorization")`) je already case-insensitive dict, pa se ispravno poklapa
sa server-side provjerom. Token se NE pojavljuje u request liniji (`GET /ws HTTP/1.1`) —
nema URL leaka.

Ovo ponašanje je specifično za instaliranu Qt/PySide6 verziju (6.11.1) i može se razlikovati
na drugim verzijama — vrijedno napomene za buduće Qt upgrade-ove, ali TRENUTNO potvrđeno
tačno na verziji koju FlowOS zapravo koristi.

**Verdikt: ACCEPT.**

## 12. GUI HTTP CLIENT AUTH — iscrpna enumeracija

```
grep "QNetworkRequest(" src/flowos/gui → tačno 5 pojavljivanja:
  composition_root.py:169  (_on_shutdown_requested)     → _apply_auth_header na liniji 170
  composition_root.py:419  (_connect_ws, WS handshake)  → conditional header na liniji 420-421
  client.py:115  (_get)     → _apply_auth_header na liniji 118
  client.py:124  (_post)    → _apply_auth_header na liniji 127
  client.py:134  (_delete)  → _apply_auth_header na liniji 136

grep "_nam.(get|post|deleteResource)" src/flowos/gui → tačno 4 pojavljivanja,
  sva odgovaraju gornjim request-construction mjestima (WS ne ide preko _nam).
```

Svih 5 mjesta gdje se konstruiše `QNetworkRequest` u cijelom GUI paketu primjenjuje auth
header prije slanja. Nema alternativnog/sekundarnog request helper-a, nema "report
download" metode (trenutno ne postoji u `GuiApiClient`), nema direktne konstrukcije koja
zaobilazi `_apply_auth_header`.

**Verdikt: ACCEPT.**

## 13. TOKEN LEAKAGE

Ciljani `grep` za `logger.\|logging.\|print(` u kombinaciji sa "token" u svim FLOW-1107
izmijenjenim fajlovima → **0 rezultata**. Nijedan log/print poziv ne referencira token
vrijednost.

`event_bus.emit()/emit_sync()` pozivaoci (reconciliation, plan_progress, conflicts,
sessions, worktrees servisi) — nijedan od njih prima `runtime` objekat niti ima pristup
tokenu; emituju isključivo business podatke (session_id, project_id, itd.). Nepromijenjeni
FLOW-1107 diff-om, van scope-a curenja.

**Nalaz (LOW, latentan, trenutno NE okinut nijednim pozivom):**
`ServiceConnection` je `@dataclass(frozen=True)` sa poljima `port: int, token: str` BEZ
`field(repr=False)` na `token`. Python-ov auto-generisan `__repr__` bi ispisao
`ServiceConnection(port=9100, token='stvarni-token...')` da se objekat ikad proslijedi
`logger.*()`/`print()`/f-string interpolaciji. Provjereno (`grep` na "connection\|candidate\|
existing" u `composition_root.py`) da TRENUTNO nijedno mjesto ne printa/loguje sam objekat —
pristupa mu se isključivo preko `.port`/`.token` atributa eksplicitno. Nije trenutno
exploitable, ali je footgun za bilo koji budući debug/log poziv koji doda ceo objekat.
Minimalna korekcija: `token: str = field(repr=False)`.

**Verdikt: ACCEPT** (LOW finding, nije blocker — vidi §24).

## 14. LOCAL BROWSER / CROSS-ORIGIN REALITY

Potvrđeno (`grep` na `CORSMiddleware\|Access-Control` u `src/flowos/service` → 0 rezultata):
**nema CORS middleware-a konfigurisanog uopšte.**

Analiza (bez zahtijevanja Host/Origin rada kao blocker-a):

- Browser fetch/XHR sa custom `Authorization` header-om ka cross-origin loopback serveru
  OKIDA CORS preflight (`OPTIONS`). Probom potvrđeno: `OPTIONS` na zaštićenu rutu BEZ
  tokena → 401 (nema CORS response header-a koji bi dozvolio browser-u da nastavi). Browser
  NIKAD ne šalje stvarni zahtjev sa Authorization header-om jer preflight ne uspije — server
  ne mora ni da vidi token da bi zaštita "radila" na ovom nivou, browser sam blokira.
- Browser `WebSocket` JavaScript API STRUKTURNO ne dozvoljava postavljanje custom header-a
  (poznato ograničenje browser platforme, ne FlowOS specifično) — zlonamjerna web stranica
  NE MOŽE prikačiti `Authorization` header na WS handshake iz JS-a, nezavisno od CORS-a.
- Autentikacija je isključivo bearer-token-u-header-u, NE cookie-bazirana — klasičan CSRF
  (koji zavisi od browser-a koji AUTOMATSKI prikači ambient kredencijal poput kolačića na
  zahtjeve koje inicira napadačeva stranica) ovdje NEMA primjenu, jer ne postoji ambient
  kredencijal koji bi browser sam prikačio (nema kolačića, custom header se ne može postaviti
  bez JS-a koji bi opet udario o CORS/WS ograničenja iznad).

**Rezidualni rizik: NEGLIGIBLE za definisani threat model.** Zaštita ovdje dolazi
DJELIMIČNO iz namjernog dizajna (header-based, ne cookie-based auth) i DJELIMIČNO iz
incidentalnih browser platform ograničenja (CORS default-deny, WS API bez custom header-a)
— vrijedno napomene da je DIO ove zaštite "besplatan" zbog platforme, ne zbog eksplicitnog
FlowOS Host/Origin koda. Ne zahtijeva se Host/Origin rad kao blocker — nema stvarnog
bypass-a bearer-token granice pronađenog.

**Verdikt: ACCEPT (INFO, ne blocker).**

## 15. TOKEN STORAGE SECURITY

Descriptor lokacija: `%LOCALAPPDATA%/FlowOS/runtime/service.json` (potvrđeno čitanjem
`app_paths.py::get_runtime_dir()`). Ovo je standardna per-user Windows lokacija —
`mkdir(parents=True, exist_ok=True)` ne postavlja nikakav custom ACL, oslanja se na
default NTFS nasljeđene dozvole `%LOCALAPPDATA%` direktorijuma, koje su na standardnoj
Windows instalaciji ograničene na vlasnika profila + Administrators/SYSTEM — NIJE
world-readable, NIJE u dijeljenom/public temp direktorijumu.

Pošto je threat model eksplicitno isključio "attacker sa arbitrary file-read pristupom kao
isti Windows korisnik", plain-text token u user-private direktorijumu NE čini auth granicu
efektivno besmislenom ZA definisani threat model — dosljedno je sa granicom, ne krši je.
Nema dokaza da je lokacija/dozvole šire nego što FLOW-1108 (ACL ownership) treba da
adresira; nema konkretnog dokaza koji bi zahtijevao FLOW-1107 fix ovdje.

**Verdikt: ACCEPT** (opis kao limitation, ne defekt — potvrđeno tačno).

## 16. SERVICE RESTART / STALE TOKEN

HTTP: `test_previous_instance_token_rejected_on_new_instance` (fresh run, PASSED) —
konstruiše `_RuntimeA`/`_RuntimeB` sa RAZLIČITIM tokenima, dokazuje token A odbijen na
instanci B, token B prihvaćen na B.

WebSocket: `test_websocket_stale_token_rejected` (fresh run, PASSED).

**GUI konektovan na A, restart na B:** analizirano u §4 — fail-CLOSED (401 na sve naredne
zahtjeve dok se GUI ne restartuje/ponovo pročita descriptor), nije bezbjednosni bypass,
dokumentovano kao LOW robustness nalaz, ne proširujem u auto-reconnect arhitekturu jer ne
otvara sigurnosni bypass.

**Verdikt: ACCEPT.**

## 17. FAIL-CLOSED STARTUP

`ServiceConnection(port, token="")` scenario ANALIZIRAN kroz kod (§5): `_read_descriptor()`
eksplicitno tretira prazan token kao nevalidan (`isinstance(token, str) and token` — prazan
string je falsy) i vraća `None` — nikad ne konstruiše `ServiceConnection` sa praznim
tokenom. `ensure_service_running()` na `None` descriptor pokušava pokrenuti NOVI servis
(koji uvijek generiše pravi kriptografski token u `__init__`), ne nastavlja tiho sa
praznim/nevalidnim kredencijalom.

Ako je descriptor manuelno pokvaren (prazan/nedostajući token polje) DOK je servis stvaran
i zdrav, `ensure_service_running()` bi tretirao "postojeći" descriptor kao nevalidan i
pokušao pokrenuti NOVU instancu — koja bi odmah pala na `acquire_lock()`
(`InstanceAlreadyRunningError`, mutex već drži živa instanca) → `ServiceStartupError` se
podiže GUI-ju VIDLJIVO, umjesto tihog neautentifikovanog rada.

**Verdikt: ACCEPT.**

## 18. TEST QUALITY

Testovi REALNO vježbaju granice, ne samo helper funkcije:

- `TestInstanceAuth` (test_composition_root.py) šalje prave ASGI zahtjeve preko
  `TestClient.get/post(...)` protiv PRAVOG middleware stack-a iz `create_app()` — NE poziva
  `verify_bearer_token()` direktno.
- `TestWebSocketAuth` koristi `client.websocket_connect(...)` — pravi ASGI WebSocket
  protokol test preko Starlette TestClient-a, NE direktan poziv `_is_authorized()`.
- `TestGuiApiClientAuthPropagation` presreće `client._nam.get/post/deleteResource` na
  INSTANCA nivou i inspektuje STVARNO konstruisan `QNetworkRequest` objekat (bijela kutija
  na posljednjoj tački prije mrežnog I/O) — vježba pravi `_get/_post/_delete/
  _apply_auth_header` kod put, ne mock koji zaobilazi konstrukciju.

**`app.state.runtime` injection provjera:** `test_service_runtime.py`'s `runtime` fixture
koristi PRAVU `RuntimeManager` klasu (samo sa test-direktorijumom override-om za
`DESCRIPTOR_DIR`), pa je token generisan pravim `secrets.token_urlsafe(32)` kodom — nije
divergentan stub. `test_composition_root.py`/`test_websocket_auth.py` koriste STUB
`NoOpRuntimeManager`/`_NoOpRuntimeManager` sa fiksnim test-tokenom — ovo je NAMJERNA i
ispravna slojevita separacija (test middleware/WS auth LOGIKE odvojeno od test TOKEN
GENERATION logike, koja je pokrivena drugdje sa pravom klasom). `app.state.runtime =
runtime` se dešava kroz ISTI produkcijski `lifespan()` handler u oba slučaja (`with
TestClient(app) as client:` okida ASGI lifespan startup) — mehanizam wiring-a je identičan
produkciji, samo je KLASA runtime objekta (stub vs pravi) namjerno različita gdje je to
ispravno.

Nije pronađen slučaj gdje test injektuje `app.state.runtime` DRUGAČIJE nego stvarni startup
na način koji bi sakrio lifecycle bug.

**Verdikt: ACCEPT.**

## 19. FLOW-1103 REGRESSION — fresh run

```
python -m pytest tests/gui/test_live_launch.py -v --tb=short
7 passed in 1.07s
```

Svi originalni scenariji prolaze: MOCK mod nepromijenjen (`test_mock_mode_does_not_launch_
backend`), zdrav postojeći servis se ponovo koristi, nov servis se pokreće sa dinamičkim
portom, startup failure vidljivo baca `ServiceStartupError`, startup timeout bounded (30s).

Dodatno provjereno čitanjem `src/flowos/gui/views/overview_skeleton.py::closeEvent`
(NEPROMIJENJEN FLOW-1107 diff-om) — normalno zatvaranje prozora daje eksplicitan izbor
("Zatvori samo prozor" vs "Zaustavi sve i ugasi FlowOS"); samo eksplicitna druga opcija
emituje `shutdown_requested`. FLOW-1103 garancija da normalno zatvaranje ne gasi servis
implicitno OSTAJE VAŽEĆA.

Credential discovery (novi `ServiceConnection`/`_read_descriptor` ugovor) NIJE oslabio
nijednu od ovih garancija — potvrđeno testom i čitanjem koda.

**Verdikt: ACCEPT.**

## 20. SECURITY REGRESSION RUN — fresh run

```
python -m pytest tests/gui/test_live_launch.py tests/gui/test_api_client_auth.py \
  tests/gui/test_api_client_error_path.py tests/integration/test_composition_root.py \
  tests/integration/test_service_runtime.py tests/integration/test_websocket_auth.py \
  -v --tb=short
→ 60 passed, 1 warning in 37.78s
```

```
python scripts/verify.py
→ 7/7 PASS
```

**Napomena tražena eksplicitno:** `verify.py` rezultat OVDJE zavisi od uncommitted timeout
promjene (120s→240s) — sa STARIM 120s limitom, korak "5. Unit tests" bi bio na ivici/preko
granice (vidi §21, izmjereno 108.83s / 1m51s wall-clock za tačno taj korak). Sa 240s
trenutno u working tree-u, 7/7 je stabilno reprodukovano.

## 21. scripts/verify.py TIMEOUT PROMJENA — odvojena analiza

```
diff --git a/scripts/verify.py b/scripts/verify.py
-            timeout=120,
+            timeout=240,
-        result.output = "Timeout (120s)"
+        result.output = "Timeout (240s)"
```

**A) Da li je prijavljeni timeout problem stvaran?** DA — nezavisno izmjereno:
```
python -m pytest tests/unit/ tests/integration/ tests/contract/ --tb=short --no-header -q
499 passed, 1 warning in 108.83s (real 1m51.348s)
```
109-135s izmjereno trajanje (zavisno od verbosity/machine load) je DIREKTNO na ivici starog
120s limita — genuine, timing-zavisan flaky-fail rizik, ne izmišljen problem.

**B) Da li je 240s razuman minimalan fix?** DA — daje ~2x rezervu iznad izmjerenog
najgoreg slučaja, bez da je pretjerano velikodušan (ne 600s, ne beskonačan).

**C) Mijenja li promjena bilo koju drugu verifikacionu semantiku osim timeout budžeta?**
NE — diff je TAČNO dvije linije: numerička vrijednost `timeout=` parametra i string u
error poruci koji ga opisuje. Isti koraci, iste komande, isti pass/fail kriterijum
(`proc.returncode == 0`), isti redoslijed. Primjenjuje se uniformno na SVIH 7 koraka (dijele
istu `run_step()` funkciju) — za brze korake (ruff, mypy, migracije) ovo je bezopasna
dodatna rezerva, ne slabljenje.

**D) ACCEPT AS SEPARATE INFRASTRUCTURE FIX** (ne "remove from FLOW-1107", ne "fixes
required"). Promjena je nezavisno tačna i potrebna, ALI **mora biti commitovana u
ODVOJENOM commit-u** od FLOW-1107 sigurnosnog diff-a — nije auth-logika, ne pripada
sigurnosnom scope-u, i miješanje bi zamaglilo šta je stvarno sigurnosna izmjena. Ovo je već
identifikovano kao nalaz L1 u prethodnom FLOW-1104 re-review izvještaju ove sesije — treći
put se potvrđuje isti root cause.

## 22. PERFORMANCE

HTTP hot path (middleware): `getattr(request.app.state, "runtime", None)` (in-memory),
`request.headers.get("authorization")` (već parsiran ASGI header), `hmac.compare_digest`
(string poređenje, O(43) po dužini tokena). Nema `await` na I/O bilo gdje u auth putanji —
potvrđeno čitanjem koda, nema DB upita, nema filesystem čitanja descriptora PO ZAHTJEVU
(descriptor se čita SAMO jednom od strane GUI-ja pri startup-u, server ga nikad ne čita
nazad sa diska).

WebSocket: auth provjera se izvršava TAČNO JEDNOM, na handshake-u, prije `accept()` — ne po
poruci (potvrđeno čitanjem `ws_endpoint`).

**Klasifikacija: NEGLIGIBLE**, sa dokazom (kod, ne benchmark — nema I/O sloja koji bi
benchmark uopšte imao šta da mjeri).

## 23. SECURITY SELF-ATTACK — rezultat

Svi traženi minimalni slučajevi su testirani/probani (vidi §6, §9 tabele iznad za potpune
rezultate): no header (401), Basic umjesto Bearer (401), "Bearer" (401), "Bearer " (401),
wrong token (401), token+trailing spaces (401), lowercase bearer (200 — RFC-compatible,
NE slabost), duplicated Authorization (koristi prvi header, nije exploitable), query-string
token only (401 — ignorisan), stale token (401), unknown route (401 bez tokena / 404 sa
tokenom), trailing slash (401 na /health/, 200 na /projects/ sa tokenom), URL encoding
(dekodira se prije oba provjere, /health ostaje minimalan pa nije bypass), WebSocket missing
auth (odbijen prije accept), WebSocket wrong auth (odbijen), WebSocket stale auth (odbijen).

Nijedan pokušaj nije uspio zaobići granicu bez prethodnog posjedovanja ispravnog,
trenutnog tokena.

## 24. FINDINGS

### A. FLOW-1107 acceptance findings

| ID | Severity | Fajl/funkcija | Dokaz | Impact | Minimalna korekcija |
|---|---|---|---|---|---|
| F1107-A1 | LOW | `src/flowos/gui/composition_root.py` — `ServiceConnection` dataclass | Auto-generisan `__repr__` uključuje `token` polje u plain textu; trenutno nijedno mjesto ga ne printa/loguje (grep potvrđen), ali je latentan footgun | Ako se ikad doda `logger.debug(f"{connection}")` ili sličan poziv, token bi ušao u log | `token: str = field(repr=False)` (uz `from dataclasses import field`) |
| F1107-A2 | LOW | `src/flowos/gui/composition_root.py::ensure_service_running` | Uzak race: instanca B umre + potpuno odvojena instanca C zauzme isti port unutar ~0.5-2s prozora health-check-a → GUI upari stari token sa health-check odgovorom nove instance | Ishod je fail-closed (401 na sve naredne zahtjeve), NE neovlašćen pristup; zahtijeva lokalnu sposobnost pokretanja servisa, van threat modela | Dokumentovati kao poznato ograničenje; nije neophodna promjena koda za FLOW-1107 accept |
| F1107-A3 | INFO | `scripts/verify.py` | 120s→240s je stvaran, minimalan, tačan fix (§21) | Nema sigurnosnog uticaja; mora biti u ODVOJENOM commit-u od FLOW-1107 diff-a | Commitovati zasebno, van FLOW-1107 security commit-a |

Nema BLOCKER, HIGH ni MEDIUM nalaza u FLOW-1107 acceptance kategoriji.

### B. Pre-existing / future-task findings

| ID | Severity | Fajl/funkcija | Dokaz | Klasifikacija |
|---|---|---|---|---|
| F1107-B1 | LOW (funkcionalni, ne sigurnosni) | `src/flowos/gui/composition_root.py:168,216` vs `src/flowos/service/controllers/http/system.py:53-87` | GUI poziva `/system/shutdown/prepare`\|`/confirm`, backend ima `/shutdown/prepare`\|`/confirm` (bez `/system` prefiksa) — nezavisno potvrđeno | CONFIRMED, pre-existing, future-task (routing fix, ne FLOW-1107) |
| F1107-B2 | INFO | `tests/integration/test_service_runtime.py::test_cors_headers` | Pre-existing test (NIJE u FLOW-1107 diff-u), ne asertuje stvarne CORS header-e; nema CORS middleware-a u aplikaciji uopšte | Informativno, ne utiče na FLOW-1107 verdikt |
| F1107-B3 | INFO | Token storage lokacija | Plain text u `%LOCALAPPDATA%/FlowOS/runtime/service.json`, per-user NTFS ACL, dosljedno sa threat modelom | Vlasništvo FLOW-1108 (ACL hardening), ne FLOW-1107 defekt |

## 25. FINAL VERDICT

```
FLOW-1107 — Zaštita lokalnog FlowOS API-ja

PER-INSTANCE TOKEN:
ACCEPT

TOKEN ROTATION:
ACCEPT

DESCRIPTOR PORT+TOKEN CONSISTENCY:
ACCEPT

FAIL-CLOSED DESCRIPTOR HANDLING:
ACCEPT

HTTP AUTH:
ACCEPT

PUBLIC /health:
ACCEPT

SHUTDOWN AUTH:
ACCEPT

WEBSOCKET AUTH:
ACCEPT

GUI HTTP AUTH PROPAGATION:
ACCEPT

GUI WEBSOCKET AUTH PROPAGATION:
ACCEPT

STALE TOKEN REJECTION:
ACCEPT

TOKEN URL LEAK:
CLOSED

TOKEN LOG LEAK:
CLOSED

FLOW-1103 REGRESSION:
ACCEPT

SECURITY TEST QUALITY:
ACCEPT

PERFORMANCE IMPACT:
NEGLIGIBLE

scripts/verify.py TIMEOUT FIX:
ACCEPT SEPARATELY

GUI SHUTDOWN ROUTING BUG:
CONFIRMED

scripts/verify.py:
7/7
```

Nema BLOCKER/HIGH/MEDIUM acceptance nalaza.

```
FLOW-1107 — Zaštita lokalnog FlowOS API-ja
= ACCEPT
```

## Napomena za commit workflow

Kada FLOW-1107 bude commitovan: `scripts/verify.py` (F1107-A3) treba u SVOJ, odvojen
commit — nije dio sigurnosnog scope-a i njegovo miješanje u isti commit kao auth kod bi
zamaglilo šta je stvarno pregledana/prihvaćena sigurnosna izmjena. Preostalih 9 FLOW-1107
fajlova (+ 2 nova testa + implementation report) čine koherentnu, ACCEPT-ovanu security
cjelinu.

Odstupanja od prompta: NONE
