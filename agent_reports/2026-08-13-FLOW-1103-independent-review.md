---
flowos_report_version: 1
report_id: c5af0822-af4b-4688-b6b2-864b73a9fbe9
agent: claude
model: claude-sonnet-5
session_id: unknown
report_type: review
work_status: completed
tasks:
  - FLOW-1103
commits: []
created_at: 2026-08-13T15:55:38+02:00
---

# FLOW-1103 — supported LIVE launch, independent review

## Scope

READ ONLY. Nije mijenjan kod, nisu mijenjani testovi, nije pravljen commit,
nije pushovano. FLOW-1104/1105/1106 nisu dirnuti.

## 1. Scope / diff

```
git status --short
 M src/flowos/gui/composition_root.py
?? tests/gui/test_live_launch.py
(plus nepovezani untracked docs/agent_reports fajlovi)
```
```
git diff --stat
 src/flowos/gui/composition_root.py | 107 ++++++++++++++++++++++++-----------
```

Napomena: `bcc6107 fix: correct GUI API signal dispatch` (FLOW-1102) je u
međuvremenu commitovan — baseline se pomjerio, ali to ne utiče na FLOW-1103
scope. Jedini izmijenjen produkcijski fajl je `composition_root.py` (GUI),
plus novi test fajl. Nema izmjene van očekivanog scope-a.

## 2. Canonical mode

`src/flowos/gui/app.py` (nepromijenjen ovim diff-om, pročitan u cjelini):
```python
live = "--live" in sys.argv
...
gui = create_gui(use_live=live)
```
Jedna provjera, jedan poziv. `create_gui(use_live=False)` (plain `flowos-gui`)
u potpunosti preskače `if use_live:` blok (`composition_root.py:489-492`) —
`ensure_service_running()` se NE poziva, `api`/`controller` ostaju `None`.
Potvrđeno testom `test_mock_mode_does_not_launch_backend` (svježe pokrenut,
PASS) i mojim čitanjem koda — nema drugog, konkurentnog LIVE launch puta.

**MOCK MODE PRESERVED = YES.**

## 3. Existing service reuse

```python
existing_port = _read_descriptor_port()
if existing_port is not None and _is_service_healthy(existing_port):
    return existing_port
```
Reuse se dešava SAMO ako su OBA uslova tačna: descriptor postoji i parsira se
ispravno (port u opsegu 1024-65535), I `/health` na TOM portu vraća 200.
Nedostajući/nevalidan descriptor (`_read_descriptor_port() → None`) ILI
neuspješan health check na starom portu OBA vode direktno na launch novog
servisa — nema puta gdje bi stale/nevalidan descriptor mogao lažno proći kao
"zdrav" bez stvarnog HTTP 200 odgovora na tom tačnom portu. `Popen` se poziva
samo kada reuse eksplicitno padne.

## 4. New service launch

```python
proc = subprocess.Popen(
    [sys.executable, "-m", "flowos.service.app"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
```
- Koristi `sys.executable` (trenutni Python environment), ne hardkodiran
  `flowos-service.exe` — stari kod je imao `subprocess.Popen(["flowos-
  service.exe"], ...)`, sada uklonjen u potpunosti (grep kroz cijeli diff —
  0 pojavljivanja `.exe`).
- Nema `shell=True`.
- Nema platform-specific launcher workaround-a.
- Nema DB repair poziva bilo gdje u ovom diff-u (potvrđeno čitanjem — diff
  dira isključivo GUI proces bootstrap, ne dodiruje `schema_repair`/migracije).

## 5. Port authority / stale descriptor risk — KRITIČAN DIO, provjeren detaljno

Petlja nakon `Popen`:
```python
while time.monotonic() < deadline:
    if proc.poll() is not None:
        raise ServiceStartupError(...)
    last_port = _read_descriptor_port()          # PONOVO čita descriptor SVAKI put
    if last_port is not None and _is_service_healthy(last_port):
        return last_port                          # vraća STVARNI, potvrđeni port
    time.sleep(0.5)
```
Kod NE pamti/vjeruje pre-launch portu — `last_port` se iznova čita iz
descriptor-a u SVAKOJ iteraciji petlje, nakon što je novi servis već pokrenut.
Kada novopokrenuti servis upiše svoj STVARNI port (npr. 9105, izabran preko
`RuntimeManager.find_free_port()` — potvrđeno u ranijem FLOW-1101 reviewu),
sljedeća iteracija ga pokupi i potvrdi `/health` na TOM portu prije povratka.

**Scenario iz zahtjeva (stari descriptor=9100 ili nedostaje, novi servis
port=9105) svježe testiran** preko `test_new_service_dynamic_port`
(`descriptor_ports = iter([None, 9105])`, `_is_service_healthy` tačno za
`port==9105`):
```
port == 9105  ✓ (ne fallback 9100)
Popen komanda: [sys.executable, "-m", "flowos.service.app"]  ✓
```

**Instance-identity napomena (nije blokirajuća za FLOW-1103)**: `_is_service_
healthy()` provjerava samo HTTP status 200 na `/health`, bez provjere `pid`/
`instance_id` iz `/runtime` rute naspram descriptor sadržaja. Teoretski, neki
nepovezan proces koji sluša na tom tačnom portu i vraća 200 na `/health` bi
mogao biti pogrešno prepoznat kao "zdrav FlowOS servis". Ovo NIJE regresija —
identičan obrazac (samo status-code provjera, bez identity provjere) postojao
je već u STAROM kodu prije ovog diff-a. Ne proširujem ovo u arhitektonski
zahtjev — bilježim kao LOW, ne blokira prihvatanje.

**PORT AUTHORITY / STALE DESCRIPTOR = ISPRAVNO.**

## 6. Startup process exit

```python
if proc.poll() is not None:
    raise ServiceStartupError(
        f"FlowOS servis se ugasio pri pokretanju (exit code {proc.returncode})."
    )
```
Provjerava se SVAKU iteraciju petlje — ako dijete izađe prije nego što postane
zdravo, greška je vidljiva (`ServiceStartupError` sa exit kodom u poruci), ne
guta se. Svježe potvrđeno testom `test_startup_failure_raises` (PASS).

`stdout=DEVNULL, stderr=DEVNULL` — izlaz djeteta se odbacuje, ne pipe-uje.
Ovo NE može izazvati deadlock (klasičan subprocess deadlock nastaje kada se
koristi `PIPE` bez čitanja, pa dijete blokira na punom OS pipe baferu — `DEVNULL`
tu ne postoji problem, pisanje uvijek uspijeva odmah). Cijena: nema inline
stdout/stderr teksta u `ServiceStartupError` poruci osim exit koda — ali
stvaran `flowos-service` proces piše u svoj trajni log fajl
(`%LOCALAPPDATA%\FlowOS\logs\flowos-service.log`, potvrđeno u ranijem FLOW-1101
reviewu) nezavisno od ovog redirect-a, pa dublja dijagnostika ostaje dostupna,
samo ne kroz ovaj poziv.

**Nema silent disconnected LIVE GUI — svaki neuspjeh je `ServiceStartupError`
exception, ne tih povratak.**

## 7. Bounded timeout

```python
deadline = time.monotonic() + 30.0
while time.monotonic() < deadline:
    ...
    time.sleep(0.5)
raise ServiceStartupError("FlowOS servis nije postao zdrav unutar 30 sekundi.")
```
Bound je tačno 30s, kako je prijavljeno. Nema beskonačnog polling-a — petlja
ima eksplicitan `while` uslov vezan za `time.monotonic()`. Nema silent
fallback-a na 9100 bilo gdje (stari `_get_service_port()` je imao `return
9100` kao fallback — potpuno uklonjen, `_read_descriptor_port()` sada vraća
`None` umjesto lažnog 9100). Nema uspješnog povratka bez potvrđenog `/health`
rezultata — jedini `return` unutar petlje je uslovljen sa `_is_service_
healthy(last_port)`.

Svježe potvrđeno testom `test_startup_timeout_raises` — deterministički
simulira protok vremena preko monkeypatch na `time.monotonic`/`time.sleep`
(ne stvarno čeka 30s), a i dalje izvršava STVARNU petlju logiku. PASS.

**BOUNDED STARTUP = YES.**

## 8. GUI API + WebSocket port

`create_gui()`:
```python
if use_live:
    port = ensure_service_running()
    api = GuiApiClient(base_url=f"http://127.0.0.1:{port}")
```
`_connect_ws()` (`composition_root.py:403-414`, NEPROMIJENJENO ovim diff-om):
```python
port = 9100
if self._api:
    port = int(self._api.base_url.split(":")[-1]) if ":" in self._api.base_url else 9100
self._ws.open(QUrl(f"ws://127.0.0.1:{port}/ws"))
```
WebSocket port se IZVODI iz `self._api.base_url` (koji je konstruisan sa
potvrđenim dinamičkim portom) — nije nezavisan drugi autoritet.
`_connect_ws()` se poziva samo `if controller:` (`__init__`, linija 84-87), a
`controller` je non-None samo kad je `use_live=True` — u MOCK modu se
WebSocket uopšte ne pokušava povezati.

**Nezavisno potvrđeno probe-om** (poziv `create_gui(use_live=True)` sa
monkeypatch-ovanim `ensure_service_running` → 9187):
```
gui._api.base_url = 'http://127.0.0.1:9187'
Sadrzi tacan potvrdjen port 9187? True
WebSocket bi izveo port: 9187 (isti kao API)
```
Ovaj kraj-do-kraja tok NIJE eksplicitno pokriven isporučenim test suite-om
(vidi Section 10, nalaz G) — ali funkcionalno je dokazano ispravan mojim
probe-om.

**GUI API USES CONFIRMED PORT = YES. WEBSOCKET USES SAME PORT = YES.**

## 9. Service lifecycle

`ensure_service_running()`'s `proc` (Popen handle za novopokrenuti servis) je
LOKALNA promjenljiva unutar funkcije — nikad se ne čuva na `self`, ne vraća se,
ne prati globalno. Strukturalno nemoguće da GUI kasnije pozove `.terminate()`
na tom procesu, jer referenca ne postoji van funkcije.

`MainWindow.closeEvent()` (`overview_skeleton.py:917-939`, NEDIRNUTO ovim
diff-om) eksplicitno razlikuje:
- "Zatvori samo prozor" → `event.accept()`, BEZ signala ka backend-u;
- "Zaustavi sve i ugasi FlowOS" → eksplicitan `shutdown_requested.emit()`;
- dijalog tekst: "Zatvaranje prozora ne zaustavlja pozadinski servis i
  agentske sesije."

FLOW-1103 nije mijenjao ovaj mehanizam — potvrđujem da je i dalje netaknut i
ispravan, ne ponovo otvaram kao nov nalaz.

**NORMAL GUI CLOSE PRESERVES SERVICE = YES.**

## 10. Test quality

Pročitan `tests/gui/test_live_launch.py` (5 testova). Pokrivenost naspram A-G:

- A) reuse bez Popen-a — ✓ `test_existing_healthy_service_reused`
- B) launch kad nema zdravog servisa — ✓ `test_new_service_dynamic_port`
- C) novi descriptor koristi NE-9100 port, taj tačan port se vraća — ✓
  `test_new_service_dynamic_port` (deterministički `iter([None, 9105])`)
- D) proces izađe prije zdravog stanja → vidljiv failure — ✓
  `test_startup_failure_raises`
- E) timeout → vidljiv bounded failure — ✓ `test_startup_timeout_raises`
  (determinističko ubrzavanje vremena, ne stvarno 30s čekanje)
- F) MOCK mod → nema backend launch-a — ✓
  `test_mock_mode_does_not_launch_backend`
- **G) GuiApiClient prima potvrđen dinamički port — NIJE POKRIVENO.** Nijedan
  test ne poziva `create_gui(use_live=True)` sa mock-ovanim `ensure_service_
  running()` da provjeri `gui._api.base_url`. Implementation report ne tvrdi
  eksplicitno da je G testiran (samo "DYNAMIC PORT: PASS", što se odnosi na
  `ensure_service_running()` test, ne na `create_gui()` wiring) — nema
  overclaiming-a u reportu, ali gap postoji. Funkcionalno sam ovo nezavisno
  potvrdio ispravnim probe-om (Section 8), pa ovo NIJE dokazan bug, samo
  nedostatak regresione zaštite za tu specifičnu žicu.

Testovi koriste deterministicke monkeypatch-eve (`_read_descriptor_port`,
`_is_service_healthy`, `subprocess.Popen`, `time.monotonic`/`time.sleep`) —
nijedan test ne ostavlja stvaran child proces pokrenut niti stvarno čeka
30 sekundi. `_FakeProc`/`_ExitedProc` su minimalni, precizni stub-ovi za
`Popen` rezultat (`poll()`, `returncode`).

## 11. Regression

```
python -m pytest tests/gui/test_live_launch.py -v --tb=short
5 passed in 0.64s
```
```
python -m pytest tests/gui/test_plan_import_flow.py tests/gui/test_api_client_error_path.py -v --tb=short
6 passed
```
```
python scripts/verify.py
Prošlo: 7/7
[PASS] VERIFIKACIJA PROŠLA
```

## 12. Findings

Nema BLOCKER ni HIGH nalaza.

**MEDIUM**

- **M1** — `tests/gui/test_live_launch.py` (nedostaje test). `create_gui(use_
  live=True)` → `GuiApiClient.base_url` sadrži potvrđen dinamički port nije
  eksplicitno regresiono pokriveno (zahtjev G). **Zašto je važno**: žica je
  danas jednostavna i dokazano ispravna (Section 8 probe), ali bez testa,
  buduća izmjena `create_gui()` bi mogla pokvariti ovu vezu neopaženo.
  **Minimalna ispravka**: dodati test koji monkeypatch-uje `ensure_service_
  running` da vrati npr. `9187`, poziva `create_gui(use_live=True)`, i
  provjerava `gui._api.base_url == "http://127.0.0.1:9187"`.

**LOW**

- **L1** — `_is_service_healthy()` provjerava samo HTTP status 200 na
  `/health`, bez identity provjere (`pid`/`instance_id` naspram descriptor
  sadržaja). Teoretski moguć false-positive reuse ako nepovezan proces sluša
  na istom portu i vraća 200 na `/health`. Nije regresija — identičan obrazac
  postojao je i prije FLOW-1103. Ne blokira prihvatanje.
- **L2** — `stdout=DEVNULL, stderr=DEVNULL` znači da `ServiceStartupError`
  poruka sadrži samo exit code, ne i stderr tekst djeteta. Dublja dijagnostika
  ostaje dostupna kroz trajni `flowos-service.log`, ali nije inline u
  exception poruci. Namjeran trade-off (izbjegava PIPE deadlock rizik), ne
  bug.

## 13. Finalni verdict

```
CANONICAL LIVE COMMAND:              ACCEPT
MOCK MODE PRESERVED:                 YES
EXISTING SERVICE REUSE:              ACCEPT
SERVICE LAUNCH METHOD:               ACCEPT
DYNAMIC PORT DISCOVERY:              ACCEPT
STALE DESCRIPTOR HANDLING:           ACCEPT
VISIBLE STARTUP FAILURE:             ACCEPT
BOUNDED STARTUP:                     YES
GUI API USES CONFIRMED PORT:         YES
WEBSOCKET USES SAME PORT:            YES
NORMAL GUI CLOSE PRESERVES SERVICE:  YES
TEST QUALITY:                        ACCEPT (uz M1 napomenu, ne blokira)

scripts/verify.py: 7/7
```

**FLOW-1103 = ACCEPT**

Razlog: svih 9 materijalnih zahtjeva (canonical mode, reuse, launch metoda,
dynamic port authority, stale descriptor otpornost, vidljiv failure, bounded
timeout, single port authority za API+WebSocket, GUI close ne ubija servis) su
potvrđeni — kroz čitanje koda, svježe pokretanje isporučenih testova, I
nezavisne probe-ove koji repliciraju tačan zahtijevani scenario (stari/
nedostajući descriptor → novi servis na drugom portu → taj tačan port
vraćen i korišćen). Jedini nalaz (M1, test coverage gap za `create_gui()` →
`GuiApiClient` žicu) je funkcionalno already-verified-correct preko mog
probe-a, i ne predstavlja dokazan bug — preporučen kao follow-up, ne kao
uslov za prihvatanje.
