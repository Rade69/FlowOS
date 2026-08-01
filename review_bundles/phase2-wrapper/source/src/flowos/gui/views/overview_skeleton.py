"""FlowOS GUI — Overview ekran (preveden, popravljen desni panel).

Tamna tema, QSplitter + layouti, svi pojmovi na srpskom.
View → Controller → Services arhitektura.

Pokreni: python src/flowos/gui/views/overview_skeleton.py
"""

import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from flowos.gui.theme.labels import OTHER_LABELS, STATUS_LABELS, status_label, ui_label

# ═══════════════════════════════════════════════════════════════════
# Tamna tema — Catppuccin Mocha
# ═══════════════════════════════════════════════════════════════════

BG_PRIMARY = "#1E1E2E"
BG_SECONDARY = "#181825"
BG_TERTIARY = "#11111B"
BG_CARD = "#252536"
BG_HOVER = "#313244"
TEXT_PRIMARY = "#CDD6F4"
TEXT_SECONDARY = "#A6ADC8"
TEXT_MUTED = "#6C7086"
BORDER = "#45475A"
BLUE = "#89B4FA"
GREEN = "#A6E3A1"
YELLOW = "#F9E2AF"
RED = "#F38BA8"
PURPLE = "#CBA6F7"
TEAL = "#94E2D5"
GRAY = "#585B70"

STATUS_COLORS = {
    "NOT_STARTED": GRAY, "IN_PROGRESS": YELLOW, "BLOCKED": RED,
    "IMPLEMENTED": PURPLE, "VERIFIED": TEAL, "ACCEPTED": GREEN,
    "REJECTED": "#EBA0AC", "NEEDS_REVIEW": YELLOW,
    "ACTIVE": GREEN, "COMPLETED": GRAY, "NO_HISTORY": GRAY,
}

SIDEBAR_MIN, SIDEBAR_DEFAULT = 220, 240
RIGHT_PANEL_MIN, RIGHT_PANEL_DEFAULT = 340, 380
TOPBAR_HEIGHT, FOOTER_HEIGHT = 52, 28
FONT_XS, FONT_SM, FONT_MD, FONT_LG, FONT_XL, FONT_XXL = 10, 11, 12, 14, 16, 20
RADIUS_MD = 6
SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG, SPACING_XL, SPACING_XXL = 2, 4, 8, 12, 16, 24


def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(BG_PRIMARY))
    p.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_PRIMARY))
    p.setColor(QPalette.ColorRole.Base, QColor(BG_SECONDARY))
    p.setColor(QPalette.ColorRole.Text, QColor(TEXT_PRIMARY))
    p.setColor(QPalette.ColorRole.Button, QColor(BG_CARD))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_PRIMARY))
    p.setColor(QPalette.ColorRole.Highlight, QColor(BLUE))
    app.setPalette(p)


def _lbl(text="", fs=FONT_MD, bold=False, color=TEXT_PRIMARY):
    lbl = QLabel(text)
    f = QFont("Segoe UI", fs)
    if bold: f.setBold(True)
    lbl.setFont(f)
    lbl.setStyleSheet(f"color: {color}; border: none; background: transparent;")
    return lbl


def _sec(text=""):
    return _lbl(text.upper(), FONT_XS, True, TEXT_MUTED)


def _card(parent=None):
    f = QFrame(parent)
    f.setStyleSheet(f"background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;")
    return f


def _status_color(status: str) -> str:
    return STATUS_COLORS.get(status, GRAY)


# ═══════════════════════════════════════════════════════════════════
# TopBar
# ═══════════════════════════════════════════════════════════════════

class TopBar(QFrame):
    project_changed = Signal(str)
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(TOPBAR_HEIGHT)
        self.setStyleSheet(f"background: {BG_SECONDARY}; border-bottom: 1px solid {BORDER};")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING_XL, 0, SPACING_XL, 0)
        layout.setSpacing(SPACING_LG)
        layout.addWidget(_lbl("◆ FlowOS", FONT_LG, True, BLUE))
        sep = QLabel("|"); sep.setStyleSheet(f"color: {BORDER}; border: none;"); layout.addWidget(sep)
        layout.addWidget(_lbl("Projekat:", FONT_SM, False, TEXT_MUTED))
        layout.addWidget(_lbl("FlowOS Core ▼", FONT_MD, True))
        layout.addSpacing(SPACING_XL)
        dot = QLabel("●"); dot.setStyleSheet(f"color: {GREEN}; border: none; font-size: 14px;"); layout.addWidget(dot)
        layout.addWidget(_lbl("Ažurno", FONT_SM, False, GREEN))
        layout.addStretch()
        layout.addWidget(_lbl("● Servis aktivan", FONT_SM, False, GREEN))
        btn = QPushButton("↻"); btn.setFixedSize(32, 32)
        btn.setStyleSheet(f"background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 4px; color: {TEXT_PRIMARY};")
        btn.clicked.connect(self.refresh_requested.emit)
        layout.addWidget(btn)


# ═══════════════════════════════════════════════════════════════════
# Sidebar
# ═══════════════════════════════════════════════════════════════════

class Sidebar(QFrame):
    navigation_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(SIDEBAR_MIN); self.setMaximumWidth(300)
        self.setStyleSheet(f"background: {BG_SECONDARY}; border-right: 1px solid {BORDER};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, SPACING_MD, 0, SPACING_MD); layout.setSpacing(0)

        nav_label = _sec("Navigacija")
        nav_label.setContentsMargins(SPACING_XL, SPACING_SM, 0, SPACING_SM)
        layout.addWidget(nav_label)

        nav_keys = ["Pregled", "Projekti", "Plan", "Sesije", "Zadaci", "Agenti", "Radna stabla", "Konflikti", "Izvještaji", "Postavke"]
        for item in nav_keys:
            active = item == "Pregled"
            bg = BG_HOVER if active else "transparent"
            bl = f"border-left: 3px solid {BLUE};" if active else "border-left: 3px solid transparent;"
            btn = QPushButton(f"  {item}")
            btn.setFixedHeight(36)
            btn.setStyleSheet(f"QPushButton {{ background: {bg}; {bl} border-top:none; border-right:none; border-bottom:none; color: {TEXT_PRIMARY if active else TEXT_SECONDARY}; text-align:left; padding-left:{SPACING_XL}px; font-size:{FONT_SM}px; }} QPushButton:hover {{ background: {BG_HOVER}; color: {TEXT_PRIMARY}; }}")
            layout.addWidget(btn)

        layout.addSpacing(SPACING_XL)

        # Aktivni projekat — popunjena kartica
        proj_title = _sec("AKTIVNI PROJEKAT")
        proj_title.setContentsMargins(SPACING_XL, SPACING_SM, 0, SPACING_SM)
        layout.addWidget(proj_title)
        card = _card()
        cl = QVBoxLayout(card); cl.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG); cl.setSpacing(SPACING_SM)
        cl.addWidget(_lbl("FlowOS Core", FONT_MD, True))
        cl.addWidget(_lbl("Plan: FlowOS v3", FONT_XS, False, GREEN))
        cl.addWidget(_lbl("FLOW-103 Rad servisnog procesa", FONT_SM, True))
        cl.addWidget(_lbl("Implementirano · nije provjereno", FONT_XS, False, PURPLE))
        cl.addWidget(_lbl("Posljednji rad: juče 18:20", FONT_XS, False, TEXT_MUTED))
        layout.addWidget(card)

        layout.addSpacing(SPACING_MD)

        actions_title = _sec("Brze akcije")
        actions_title.setContentsMargins(SPACING_XL, SPACING_SM, 0, SPACING_SM)
        layout.addWidget(actions_title)
        for a in ["Nova sesija", "Dodaj zadatak", "Uvezi plan", "Pregledaj vanjske promjene", "Otvori dnevnik"]:
            btn = QPushButton(f"  {a}")
            btn.setFixedHeight(32)
            btn.setStyleSheet(f"QPushButton {{ background:transparent; border:none; color:{TEXT_SECONDARY}; text-align:left; padding-left:{SPACING_XL}px; font-size:{FONT_SM}px; }} QPushButton:hover {{ color:{TEXT_PRIMARY}; }}")
            layout.addWidget(btn)

        layout.addStretch()

        sl = QHBoxLayout(); sl.setContentsMargins(SPACING_XL, 0, SPACING_MD, 0)
        dot = QLabel("●"); dot.setStyleSheet(f"color: {GREEN}; border: none;")
        sl.addWidget(dot); sl.addWidget(_lbl("Povezano sa servisom", FONT_XS, False, GREEN)); sl.addStretch()
        layout.addLayout(sl)


# ═══════════════════════════════════════════════════════════════════
# Centralni — Plan Progress
# ═══════════════════════════════════════════════════════════════════

class PlanProgressWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(SPACING_MD)

        header = QHBoxLayout()
        header.addWidget(_lbl("NAPREDAK PO PLANU", FONT_LG, True))
        header.addStretch()
        header.addWidget(_lbl("Aktivni plan: FlowOS v3", FONT_SM, False, TEXT_MUTED))
        layout.addLayout(header)

        # Statusni sažetak na srpskom
        sr = QHBoxLayout(); sr.setSpacing(SPACING_LG)
        for n, s, c in [(3, "prihvaćene", GREEN), (1, "provjerena", TEAL), (1, "implementirana", PURPLE), (1, "u toku", YELLOW), (3, "nisu započete", GRAY)]:
            it = QLabel(f"{n} {s}"); it.setFont(QFont("Segoe UI", FONT_SM, QFont.Weight.Bold)); it.setStyleSheet(f"color: {c}; border: none;")
            sr.addWidget(it)
        sr.addStretch()
        layout.addLayout(sr)

        tree = QTreeWidget()
        tree.setHeaderLabels(["Faza / Stavka", "Status", "Agent/Sesija", "Kriterijumi", "Stanje"])
        tree.setAlternatingRowColors(True); tree.setRootIsDecorated(True); tree.setIndentation(20)
        tree.setStyleSheet(f"""QTreeWidget {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px; }}
            QTreeWidget::item {{ padding: {SPACING_SM}px; color: {TEXT_PRIMARY}; }}
            QTreeWidget::item:selected {{ background: {BG_HOVER}; }}
            QHeaderView::section {{ background: {BG_SECONDARY}; border: none; border-bottom: 1px solid {BORDER}; padding: {SPACING_SM}px; color: {TEXT_MUTED}; font-weight: bold; }}""")
        tree.setColumnWidth(0, 340); tree.setColumnWidth(1, 100); tree.setColumnWidth(2, 110); tree.setColumnWidth(3, 80); tree.setColumnWidth(4, 110)

        f1 = QTreeWidgetItem(tree, ["Faza 1 — Temelj i prvi vertikalni tok", "", "", "", ""])
        f1.setExpanded(True); f1.setFont(0, QFont("Segoe UI", FONT_MD, QFont.Weight.Bold))
        for key, status, agent, crit, ns in [
            ("FLOW-101  Zajednički ugovori", "VERIFIED", "—", "6/6", "Spremno"),
            ("FLOW-102  SQLite i migracije", "ACCEPTED", "—", "8/8", "Završeno"),
            ("FLOW-103  Rad servisnog procesa", "IMPLEMENTED", "pi / SESSION-42", "5/7", "Potreban pregled"),
            ("FLOW-104  API za projekte i zadatke", "NOT_STARTED", "—", "0/6", "Blokirano"),
        ]:
            row = QTreeWidgetItem(f1, [key, status_label(status), agent, crit, ns])
            row.setForeground(1, QColor(_status_color(status)))

        f2 = QTreeWidgetItem(tree, ["Faza 2 — Omotač, posmatrač i Aktivne sesije", "", "", "", ""])
        f2.setFont(0, QFont("Segoe UI", FONT_MD, QFont.Weight.Bold))
        QTreeWidgetItem(f2, ["FLOW-201  CLI kostur", "NOT_STARTED", "—", "0/4", "—"])

        layout.addWidget(tree)


# ═══════════════════════════════════════════════════════════════════
# Centralni — Aktivne sesije
# ═══════════════════════════════════════════════════════════════════

class ActiveSessionsWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        l = QVBoxLayout(self); l.setContentsMargins(0, 0, 0, 0); l.setSpacing(SPACING_SM)
        l.addWidget(_lbl("AKTIVNE SESIJE (1)", FONT_LG, True))

        tree = QTreeWidget()
        tree.setHeaderLabels(["Sesija", "Agent", "Plan stavka", "Grana", "Status"])
        tree.setRootIsDecorated(False); tree.setMaximumHeight(90)
        tree.setStyleSheet(f"""QTreeWidget {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px; }}
            QTreeWidget::item {{ padding: {SPACING_SM}px; color: {TEXT_PRIMARY}; }}
            QHeaderView::section {{ background: {BG_SECONDARY}; border: none; border-bottom: 1px solid {BORDER}; padding: {SPACING_SM}px; color: {TEXT_MUTED}; font-weight: bold; }}""")
        row = QTreeWidgetItem(tree, ["SESSION-42", "pi", "FLOW-103", "flow/FLOW-103", status_label("ACTIVE")])
        row.setForeground(4, QColor(GREEN))
        l.addWidget(tree)


# ═══════════════════════════════════════════════════════════════════
# Centralni — Nedavna aktivnost
# ═══════════════════════════════════════════════════════════════════

class RecentActivityWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        l = QVBoxLayout(self); l.setContentsMargins(0, 0, 0, 0); l.setSpacing(SPACING_SM)
        h = QHBoxLayout(); h.addWidget(_lbl("NEDAVNA AKTIVNOST", FONT_LG, True)); h.addStretch()
        h.addWidget(QPushButton("Otvori vremensku liniju →")); l.addLayout(h)
        for t, src, det in [("17:22", "pi / SESSION-42", "Commit a8f19d2"), ("17:10", "pi / SESSION-42", "Testovi: 18/19 prolazi"), ("16:40", "Sesija pokrenuta", "FLOW-103"), ("15:55", "FLOW-102", "Prešao u Provjereno")]:
            rl = QHBoxLayout(); rl.addWidget(_lbl(t, FONT_XS, False, TEXT_MUTED)); rl.addWidget(_lbl(src, FONT_SM, True)); rl.addWidget(_lbl(det, FONT_SM, False, TEXT_SECONDARY)); rl.addStretch(); l.addLayout(rl)


# ═══════════════════════════════════════════════════════════════════
# Desni panel — Gdje si stao (čitljiv, word wrap)
# ═══════════════════════════════════════════════════════════════════

class ProjectResumeWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;")
        l = QVBoxLayout(self); l.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL); l.setSpacing(SPACING_MD)
        l.addWidget(_lbl("GDJE SI STAO", FONT_LG, True))

        # Glavne info
        for lbl, val in [("FLOW-103 — Rad servisnog procesa", ""), ("Implementirano", PURPLE), ("Nije provjereno", YELLOW)]:
            if lbl.startswith("FLOW"):
                l.addWidget(_lbl(lbl, FONT_MD, True))
            else:
                l.addWidget(_lbl(lbl, FONT_SM, True, val or TEXT_PRIMARY))

        l.addWidget(_lbl("Posljednji rad", FONT_XS, False, TEXT_MUTED))
        l.addWidget(_lbl("pi · SESSION-42 · juče 18:20", FONT_SM, True))

        # Gdje je rad stao
        l.addWidget(_sec("Gdje je rad stao"))
        stopped = _lbl("Rad servisnog procesa i dijagnostički endpointi su implementirani. "
                       "Force terminate na Windows-u ostavlja runtime descriptor.", FONT_SM, False, TEXT_SECONDARY)
        stopped.setWordWrap(True); l.addWidget(stopped)

        # Sljedeći korak — vizuelno istaknut
        l.addWidget(_sec("Sljedeći konkretan korak"))
        next_step = _lbl("Implementirati nadzor nad čišćenjem nakon prisilnog prekida.", FONT_SM, True, TEXT_PRIMARY)
        next_step.setWordWrap(True); l.addWidget(next_step)

        # Preuslovi
        l.addWidget(_sec("Prije nastavka provjeriti"))
        prec = _lbl("• trenutni HEAD\n• radno stablo sa neupisanim promjenama\n• neuspješan test životnog ciklusa", FONT_SM, False, TEXT_SECONDARY)
        prec.setWordWrap(True); l.addWidget(prec)

        # Pouzdanost
        cr = QHBoxLayout()
        cr.addWidget(_lbl("Pouzdanost:", FONT_XS, False, TEXT_MUTED))
        cr.addWidget(_lbl("Srednja", FONT_SM, True, YELLOW))
        cr.addWidget(_lbl("· posljednje usklađivanje: prije 2 min", FONT_XS, False, TEXT_MUTED)); cr.addStretch()
        l.addLayout(cr)

        bl = QHBoxLayout()
        for t in ["Nastavi rad", "Otvori izvještaj"]:
            btn = QPushButton(t); btn.setStyleSheet(f"background: {BG_HOVER}; border: 1px solid {BORDER}; border-radius: 4px; color: {TEXT_PRIMARY}; padding: {SPACING_SM}px {SPACING_XL}px;")
            bl.addWidget(btn)
        bl.addStretch(); l.addLayout(bl)


# ═══════════════════════════════════════════════════════════════════
# Desni panel — Detalji stavke plana
# ═══════════════════════════════════════════════════════════════════

class PlanItemDetailsWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;")
        l = QVBoxLayout(self); l.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL); l.setSpacing(SPACING_MD)
        l.addWidget(_lbl("DETALJI STAVKE PLANA", FONT_LG, True))

        for lbl, val in [("FLOW-103", "Rad servisnog procesa"), ("Faza:", "Faza 1"), ("Status:", "Implementirano"), ("Agent:", "pi"), ("Sesija:", "SESSION-42")]:
            r = QHBoxLayout(); r.addWidget(_lbl(lbl, FONT_XS, False, TEXT_MUTED)); r.addWidget(_lbl(val, FONT_SM, True)); r.addStretch(); l.addLayout(r)

        l.addWidget(_sec("Kriterijumi prihvatanja"))
        for c, d, col in [("✓", "FastAPI aplikacija sa životnim ciklusom", GREEN), ("✓", "Single-instance zaključavanje", GREEN),
                           ("✓", "Runtime descriptor", GREEN), ("✓", "/health, /version, /runtime", GREEN),
                           ("◐", "Pristojno gašenje — 1 test ne prolazi", YELLOW), ("○", "Lokalni strukturisani zapisi", GRAY)]:
            rl = QHBoxLayout(); cl = QLabel(c); cl.setFont(QFont("Segoe UI", FONT_SM, QFont.Weight.Bold)); cl.setStyleSheet(f"color: {col}; border: none;"); cl.setFixedWidth(20)
            rl.addWidget(cl); rl.addWidget(_lbl(d, FONT_SM, False, TEXT_SECONDARY)); rl.addStretch(); l.addLayout(rl)

        l.addWidget(_sec("Dokazi"))
        l.addWidget(_lbl("Commit: a8f19d2 · Testovi: 18/19 · Izvještaj: 2026-07-31_FLOW-103.md", FONT_XS, False, TEXT_MUTED))


# ═══════════════════════════════════════════════════════════════════
# Desni panel — Usklađivanje stanja
# ═══════════════════════════════════════════════════════════════════

class ReconciliationWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_CARD}; border: 1px solid {YELLOW}; border-radius: {RADIUS_MD}px; border-left: 4px solid {YELLOW};")
        l = QVBoxLayout(self); l.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL); l.setSpacing(SPACING_SM)
        l.addWidget(_lbl("⚠ PROMJENE VAN FLOWOS-A", FONT_MD, True, YELLOW))
        l.addWidget(_lbl("Projekat je mijenjan van FlowOS-a.", FONT_SM, False, TEXT_SECONDARY))
        l.addWidget(_lbl("3 nova commita · 2 neupisana fajla", FONT_SM, True))
        l.addWidget(_lbl("Grana: main → feature/runtime-fix", FONT_XS, False, TEXT_MUTED))
        l.addWidget(_lbl("Autor nije potvrđen.", FONT_XS, False, RED))


# ═══════════════════════════════════════════════════════════════════
# Footer
# ═══════════════════════════════════════════════════════════════════

class StatusBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(FOOTER_HEIGHT)
        self.setStyleSheet(f"background: {BG_SECONDARY}; border-top: 1px solid {BORDER};")
        l = QHBoxLayout(self); l.setContentsMargins(SPACING_XL, 0, SPACING_XL, 0); l.setSpacing(SPACING_XL)
        for t in ["Servis: aktivan", "API: v1", "Baza: flowos.db · u redu", "Posmatrač: aktivan", "Usklađivanje stanja: prije 2 min"]:
            l.addWidget(_lbl(t, FONT_XS, False, TEXT_MUTED))
        l.addStretch()


# ═══════════════════════════════════════════════════════════════════
# MainWindow
# ═══════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlowOS — Pregled")
        self.resize(1400, 900); self.setMinimumSize(1024, 700)

        c = QWidget(); self.setCentralWidget(c)
        root = QVBoxLayout(c); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        self.topbar = TopBar(); root.addWidget(self.topbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(Sidebar())

        # Centralni — scroll
        cs = QScrollArea(); cs.setWidgetResizable(True); cs.setStyleSheet(f"QScrollArea {{ border: none; background: {BG_PRIMARY}; }}")
        cc = QWidget(); cl = QVBoxLayout(cc); cl.setContentsMargins(SPACING_XXL, SPACING_XL, SPACING_XL, SPACING_XL); cl.setSpacing(SPACING_XL)
        cl.addWidget(PlanProgressWidget()); cl.addWidget(ActiveSessionsWidget()); cl.addWidget(RecentActivityWidget()); cl.addStretch()
        cs.setWidget(cc); splitter.addWidget(cs)

        # Desni — JEDAN QScrollArea sa svim karticama
        rs = QScrollArea(); rs.setWidgetResizable(True); rs.setStyleSheet(f"QScrollArea {{ border: none; background: {BG_PRIMARY}; }}")
        rc = QWidget(); rl = QVBoxLayout(rc); rl.setContentsMargins(0, SPACING_XL, SPACING_XXL, SPACING_XL); rl.setSpacing(SPACING_LG)
        rl.addWidget(ProjectResumeWidget()); rl.addWidget(PlanItemDetailsWidget()); rl.addWidget(ReconciliationWidget()); rl.addStretch()
        rs.setWidget(rc); splitter.addWidget(rs)

        splitter.setSizes([SIDEBAR_DEFAULT, 700, RIGHT_PANEL_DEFAULT])
        splitter.setStretchFactor(0, 0); splitter.setStretchFactor(1, 1); splitter.setStretchFactor(2, 0)
        root.addWidget(splitter)
        root.addWidget(StatusBar())


def main():
    app = QApplication(sys.argv); app.setApplicationName("FlowOS"); apply_dark_theme(app)
    MainWindow().show(); sys.exit(app.exec())


if __name__ == "__main__":
    main()