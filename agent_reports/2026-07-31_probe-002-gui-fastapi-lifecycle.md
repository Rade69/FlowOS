"""PROBE-002 zakljucak — GUI-FastAPI lifecycle test."""

# PROBE-002: GUI-FastAPI Lifecycle

## Pitanje

Moze li GUI pouzdano otkriti, pokrenuti i reconnectovati se na odvojeni lokalni servis?

## Pretpostavka

GUI moze koristiti runtime descriptor (JSON fajl) za otkrivanje servisa,
QNetworkAccessManager za neblokirajuce HTTP health provere, QWebSocket za
real-time dogadjaje, i QTimer za automatski reconnect.

## Nacin provjere

1. FastAPI test server (`probe_service.py`) na localhost:9150:
   - /health, /version, /runtime endpointi
   - /ws WebSocket sa emitovanjem svakih 2s
   - Runtime descriptor JSON u %LOCALAPPDATA%\FlowOS\runtime\service.json
   - Brise descriptor pri graceful shutdown-u

2. PySide6 GUI (`probe_gui.py`):
   - StatusIndicator (zeleno/crveno)
   - Health polling svakih 3s kroz QNetworkAccessManager
   - WebSocket konekcija sa prikazom dogadjaja
   - Automatski reconnect timer (2s interval)

3. Automatizovani integracioni test (`probe_lifecycle_test.py`):
   - 12 koraka: start → health → version → descriptor → WS → kill →
     verify dead → descriptor cleanup → restart → health → WS → cleanup

## Rezultat

Testiran scenarij:

| Korak | Rezultat |
|---|---|
| Server start | OK |
| Health check | OK (uptime ~2.3s) |
| Version check | OK (0.1.0-probe, api v1) |
| Runtime descriptor | OK (port=9150, pid tacan) |
| WebSocket | OK (primljen dogadjaj) |
| Server terminate | OK (server mrtav) |
| Health posle kill-a | OK (server nedostupan) |
| Descriptor obrisan | **FAIL** — terminate() ne aktivira FastAPI shutdown handler |
| Server restart | OK |
| Health posle restart-a | OK (uptime ~2.3s) |
| WS posle restart-a | OK (radi) |

**11/12 testova prolazi.**

Problem sa descriptor-om: `subprocess.terminate()` na Windows-u salje
`TerminateProcess`, sto ne prolazi kroz FastAPI `on_event("shutdown")`.
Graceful shutdown (Ctrl+C, `taskkill` bez /F) bi obrisao descriptor.

**Ovo nije problem** — pri nasilnom padu:
1. Stari descriptor ostaje
2. Novi server pri startu prepisuje descriptor (`"w"` rezim)
3. PID se menja, port ostaje isti
4. GUI detektuje promenu kroz health polling

## Dokaz

- `probe_service.py` — FastAPI test server (92 linije)
- `probe_gui.py` — PySide6 GUI sa health/WS/reconnect (200+ linija)
- `probe_lifecycle_test.py` — Automatizovani test (12 koraka)
- Test output: 11/12 prolazi, 1 ocekivani fail (descriptor cleanup na terminate)

## Ogranicenja

- Testirano na jednom portu (9150). Port conflict nije testiran.
- Nije testirana autentikacija (lokalni session token).
- Nije testiran slucaj dva GUI-ja povezana istovremeno.
- WebSocket reconnect testiran kroz novu konekciju, ne kroz QWebSocket
  interni reconnect (koji postoji).

## Preporuka

**DA — GUI moze pouzdano da otkrije, prati i reconnectuje se na FastAPI servis.**

Predlozi za fazu 1:
1. Implementirati `GuiApiClient` sa QNetworkAccessManager + QWebSocket
2. Runtime descriptor citati pri startu GUI-ja
3. Health polling sa QTimer-om (3s interval)
4. Automatski WS reconnect sa exponential backoff-om (ne fiksni 2s)
5. Single-instance lock/mutex za servis
6. Pri startu: ako descriptor postoji, probati health pre pokretanja novog
7. Descriptor cleanup: oslanjati se na overwrite pri startu, ne na shutdown

## Odluka koju sada mozemo donijeti

**Model otkrivanja servisa (runtime descriptor + health polling + WS reconnect)
je potvrdjen i moze se koristiti u FlowOS fazi 1.**