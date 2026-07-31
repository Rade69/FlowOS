"""PROBE-001 zakljucak — sacuvati na main grani, prototip baciti."""

# PROBE-001: PySide6 mockup i DPI

## Pitanje

Može li odobreni ekran Pregled biti izveden u Qt Widgets bez ručnih koordinata
i bez neprihvatljivog pada performansi?

## Pretpostavka

PySide6 + Qt Widgets može da izvede ekran Pregled sa layouts, QTableView,
QStyledItemDelegate i QPainter-om, bez QML-a i bez performansnih problema
na rezolucijama 1600×900 do 2560×1440.

## Način provjere

1. Napravljen samostalni prototip `probe_pyside6_overview.py` (700+ linija)
   na throwaway grani `probe/pyside6-mockup-dpi`.
2. Prototip sadrži: sidebar, topbar, 4 stat kartice, QTableView aktivnih sesija,
   brze dokaze, konflikt kartice (custom widget), QTableView promjena,
   timeline (QPainter), sažetak zadatka sa napomenom.
3. Screenshotovi napravljeni kroz `QWidget.grab()` na 4 rezolucije:
   - 1920×1080 @ 100%
   - 1920×1080 @ 125%
   - 1600×900 @ 100%
   - 2560×1440 @ 150%
4. Izmjereno vrijeme konstrukcije `OverviewScreen` widgeta.

## Rezultat

- **Vrijeme konstrukcije OverviewScreen-a: 9.9 ms** (prosek kroz sve rezolucije)
- Svi layouti se korektno skaliraju — korišćeni su QVBoxLayout, QHBoxLayout
- Sidebar + centralni deo razdvojeni kroz layouts, bez QSplitter-a (dovoljno)
- QTableView radi sa custom modelima i delegatima
- QPainter timeline se ispravno renderuje
- Nema ručnih koordinata — ceo layout je Qt layout-based

## Dokaz

- `probe_screenshot_1920x1080_100pct.png` — 1920×1080 @ 100%
- `probe_screenshot_1920x1080_125pct.png` — 1920×1080 @ 125%
- `probe_screenshot_1600x900_100pct.png` — 1600×900 @ 100%
- `probe_screenshot_2560x1440_150pct.png` — 2560×1440 @ 150%
- Vrijeme renderovanja: 9.9 ms

## Lista potrebnih custom widgeta i delegata

| Tip | Naziv | Svrha |
|---|---|---|
| Custom widget | `StatCard` | Kartica sa brojem i labelom, border-left akcentom |
| Custom widget | `Sidebar` | Leva navigacija sa listom projekata i zadataka |
| Custom widget | `TopBar` | Gornja traka sa breadcrumb-om |
| Custom widget | `ConflictCard` | Prikaz konflikta sa nivoom rizika i opisom |
| Custom widget | `TimelineWidget` | QPainter-crtani timeline događaja |
| Delegate | `StatusDelegate` | Obojeni badgevi za status (ACTIVE/IDLE/COMPLETED) |
| Delegate | `AttributionDelegate` | Obojena atribucija prema pouzdanosti |
| Model | `SessionsTableModel` | QAbstractTableModel za aktivne sesije |
| Model | `ChangesTableModel` | QAbstractTableModel za nedavne promjene |

## Ograničenja rezultata

- Screenshotovi su u offscreen režimu (QT_QPA_PLATFORM=offscreen). Nije testiran
  stvarni DPI scaling na fizičkom monitoru.
- Nije testirano sa velikim brojem sesija (samo 4 mock sesije).
- Nije testirana interakcija (klikovi, animacije, WebSocket refresh).
- QSS stilovi su definisani inline — u produkciji treba eksterni .qss fajl.
- Emoji karakteri prave UnicodeEncodeError na Windows CP1252 terminalu —
  treba koristiti samo ASCII karaktere.

## Preporuka

**DA — PySide6 + Qt Widgets može da izvede ekran Pregled.**

Predlozi za fazu 1:
1. Izdvojiti QSS stilove u `theme/styles.qss`
2. Koristiti `QSplitter` za sidebar/centralni split
3. Design tokeni već postoje u `theme/tokens.py` — koristiti ih
4. Custom widgete prebaciti u `gui/widgets/`
5.legate u `gui/delegates/`
6. QAbstractTableModel podklase u `gui/models/`
7. TimelineWidget u `gui/widgets/`
8. Izbjegavati emoji — koristiti tekstualne labele ili SVG ikone

## Odluka koju sada možemo donijeti

**PySide6 + Qt Widgets je potvrđen kao ispravan izbor za FlowOS GUI.**
Nema prepreka za punu implementaciju ekrana Pregled (faza 1-2).