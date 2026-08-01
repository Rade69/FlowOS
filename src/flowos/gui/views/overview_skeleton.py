"""FlowOS GUI — Overview ekran skeleton (FLOW-105).

Kompletan statički skeleton prema GUI specifikaciji v3.
Tamna tema, QSplitter + layouti, lažni ViewState podaci.
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

# ═══════════════════════════════════════════════════════════════════
# Tamna tema — Design tokeni
# ═══════════════════════════════════════════════════════════════════

# Osnovne boje
BG_PRIMARY = "#1E1E2E"
BG_SECONDARY = "#181825"
BG_TERTIARY = "#11111B"
BG_CARD = "#252536"
BG_HOVER = "#313244"

TEXT_PRIMARY = "#CDD6F4"
TEXT_SECONDARY = "#A6ADC8"
TEXT_MUTED = "#6C7086"

BORDER = "#45475A"
BORDER_ACTIVE = "#89B4FA"

# Semantičke boje (Catppuccin Mocha)
BLUE = "#89B4FA"
GREEN = "#A6E3A1"
YELLOW = "#F9E2AF"
RED = "#F38BA8"
PURPLE = "#CBA6F7"
TEAL = "#94E2D5"
GRAY = "#585B70"

# Statusne boje
STATUS_NOT_STARTED = GRAY
STATUS_IN_PROGRESS = YELLOW
STATUS_BLOCKED = RED
STATUS_IMPLEMENTED = PURPLE
STATUS_VERIFIED = TEAL
STATUS_ACCEPTED = GREEN
STATUS_REJECTED = "#EBA0AC"

# Dimenzije
SIDEBAR_MIN = 220
SIDEBAR_DEFAULT = 240
RIGHT_PANEL_MIN = 340
RIGHT_PANEL_DEFAULT = 380
TOPBAR_HEIGHT = 52
FOOTER_HEIGHT = 28

FONT_XS = 10
FONT_SM = 11
FONT_MD = 12
FONT_LG = 14
FONT_XL = 16
FONT_XXL = 20

RADIUS_SM = 4
RADIUS_MD = 6
RADIUS_LG = 8
SPACING_XS = 2
SPACING_SM = 4
SPACING_MD = 8
SPACING_LG = 12
SPACING_XL = 16
SPACING_XXL = 24


# ═══════════════════════════════════════════════════════════════════
# Tamni QPalette
# ═══════════════════════════════════════════════════════════════════

def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG_PRIMARY))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(BG_SECONDARY))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(BG_CARD))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(BG_CARD))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button, QColor(BG_CARD))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(RED))
    palette.setColor(QPalette.ColorRole.Link, QColor(BLUE))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(BLUE))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(BG_PRIMARY))
    app.setPalette(palette)


# ═══════════════════════════════════════════════════════════════════
# Helper funkcije
# ═══════════════════════════════════════════════════════════════════

def _label(text: str, font_size: int = FONT_MD, bold: bool = False, color: str = TEXT_PRIMARY) -> QLabel:
    lbl = QLabel(text)
    font = QFont("Segoe UI", font_size)
    if bold:
        font.setBold(True)
    lbl.setFont(font)
    lbl.setStyleSheet(f"color: {color}; border: none; background: transparent;")
    return lbl


def _card(parent=None) -> QFrame:
    f = QFrame(parent)
    f.setStyleSheet(f"background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;")
    return f


def _section_title(text: str) -> QLabel:
    return _label(text.upper(), FONT_XS, True, TEXT_MUTED)


def _status_badge(status: str) -> str:
    colors = {
        "NOT_STARTED": STATUS_NOT_STARTED, "IN_PROGRESS": STATUS_IN_PROGRESS,
        "BLOCKED": STATUS_BLOCKED, "IMPLEMENTED": STATUS_IMPLEMENTED,
        "VERIFIED": STATUS_VERIFIED, "ACCEPTED": STATUS_ACCEPTED,
        "REJECTED": STATUS_REJECTED,
        "ACTIVE": GREEN, "READY_TO_CONTINUE": GREEN, "NEEDS_REVIEW": YELLOW,
        "HIGH": GREEN, "MEDIUM": YELLOW, "LOW": RED,
        "PASSED": GREEN, "PENDING": GRAY, "FAILED": RED, "IN_PROGRESS_CRITERION": YELLOW,
    }
    return colors.get(status, GRAY)


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

        # Logo
        logo = _label("◆ FlowOS", FONT_LG, True, BLUE)
        layout.addWidget(logo)

        # Separator
        sep = QLabel("|")
        sep.setStyleSheet(f"color: {BORDER}; border: none;")
        layout.addWidget(sep)

        # Projekat
        proj_label = _label("Projekat:", FONT_SM, False, TEXT_MUTED)
        proj_name = _label("FlowOS Core ▼", FONT_MD, True, TEXT_PRIMARY)
        layout.addWidget(proj_label)
        layout.addWidget(proj_name)

        layout.addSpacing(SPACING_XL)

        # Status projekta
        status_indicator = QLabel("●")
        status_indicator.setStyleSheet(f"color: {GREEN}; border: none; font-size: 14px;")
        status_text = _label("Ažurno", FONT_SM, False, GREEN)
        layout.addWidget(status_indicator)
        layout.addWidget(status_text)

        layout.addStretch()

        # Status servisa
        svc_label = _label("● Servis aktivan", FONT_SM, False, GREEN)
        layout.addWidget(svc_label)

        # Osvježi
        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(32, 32)
        refresh_btn.setStyleSheet(f"background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_SM}px; color: {TEXT_PRIMARY};")
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        layout.addWidget(refresh_btn)


# ═══════════════════════════════════════════════════════════════════
# Sidebar
# ═══════════════════════════════════════════════════════════════════

class Sidebar(QFrame):
    navigation_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(SIDEBAR_MIN)
        self.setMaximumWidth(300)
        self.setStyleSheet(f"background: {BG_SECONDARY}; border-right: 1px solid {BORDER};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, SPACING_MD, 0, SPACING_MD)
        layout.setSpacing(0)

        # ── Navigacija ──
        nav_label = _section_title("Navigacija")
        nav_label.setContentsMargins(SPACING_XL, SPACING_SM, 0, SPACING_SM)
        layout.addWidget(nav_label)

        nav_items = ["Pregled", "Projekti", "Plan", "Sesije", "Zadaci", "Agenti", "Worktrees", "Konflikti", "Izvještaji", "Postavke"]
        for item in nav_items:
            is_active = item == "Pregled"
            bg = BG_HOVER if is_active else "transparent"
            border_left = f"border-left: 3px solid {BLUE};" if is_active else "border-left: 3px solid transparent;"
            nav_btn = QPushButton(f"  {item}")
            nav_btn.setFixedHeight(36)
            nav_btn.setStyleSheet(
                f"QPushButton {{ background: {bg}; {border_left} border-top: none; border-right: none; border-bottom: none;"
                f"color: {TEXT_PRIMARY if is_active else TEXT_SECONDARY}; text-align: left; padding-left: {SPACING_XL}px; font-size: {FONT_SM}px; }}"
                f"QPushButton:hover {{ background: {BG_HOVER}; color: {TEXT_PRIMARY}; }}"
            )
            layout.addWidget(nav_btn)

        layout.addSpacing(SPACING_XL)

        # ── Sažetak aktivnog projekta ──
        summary_title = _section_title("Aktivni projekat")
        summary_title.setContentsMargins(SPACING_XL, SPACING_SM, 0, SPACING_SM)
        layout.addWidget(summary_title)

        summary_card = _card()
        summary_card.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        sl = QVBoxLayout(summary_card)
        sl.setSpacing(SPACING_SM)
        sl.addWidget(_label("FlowOS Core", FONT_MD, True))
        sl.addWidget(_label("Plan v3 · ACTIVE", FONT_XS, False, GREEN))
        sl.addWidget(_label("FLOW-103 Service runtime", FONT_SM, True))
        sl.addWidget(_label("IMPLEMENTED · nije VERIFIED", FONT_XS, False, PURPLE))
        sl.addWidget(_label("Posljednji rad: juče 18:20", FONT_XS, False, TEXT_MUTED))
        layout.addWidget(summary_card)

        layout.addSpacing(SPACING_MD)

        # ── Brze akcije ──
        actions_title = _section_title("Brze akcije")
        actions_title.setContentsMargins(SPACING_XL, SPACING_SM, 0, SPACING_SM)
        layout.addWidget(actions_title)

        for action in ["Nova sesija", "Dodaj zadatk", "Uvezi plan", "Pregledaj vanjske promjene", "Otvori dnevnik"]:
            btn = QPushButton(f"  {action}")
            btn.setFixedHeight(32)
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; border: none; color: {TEXT_SECONDARY}; text-align: left; padding-left: {SPACING_XL}px; font-size: {FONT_SM}px; }}"
                f"QPushButton:hover {{ color: {TEXT_PRIMARY}; }}"
            )
            layout.addWidget(btn)

        layout.addStretch()

        # ── Status veze ──
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(SPACING_XL, 0, SPACING_MD, 0)
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {GREEN}; border: none;")
        conn_label = _label("Povezano sa servisom", FONT_XS, False, GREEN)
        status_layout.addWidget(dot)
        status_layout.addWidget(conn_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)


# ═══════════════════════════════════════════════════════════════════
# Centralni — Plan Progress
# ═══════════════════════════════════════════════════════════════════

class PlanProgressWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent; border: none;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING_MD)

        # Naslov
        header = QHBoxLayout()
        header.addWidget(_label("NAPREDAK PO PLANU", FONT_LG, True))
        header.addStretch()
        header.addWidget(_label("Aktivni plan: FlowOS v3", FONT_SM, False, TEXT_MUTED))
        layout.addLayout(header)

        # Statusni sažetak
        status_row = QHBoxLayout()
        status_row.setSpacing(SPACING_LG)
        for count, label, color in [(3, "ACCEPTED", GREEN), (1, "VERIFIED", TEAL), (1, "IMPLEMENTED", PURPLE), (1, "IN PROGRESS", YELLOW), (3, "NOT STARTED", GRAY)]:
            item = QLabel(f"{count} {label}")
            item.setFont(QFont("Segoe UI", FONT_SM, QFont.Weight.Bold))
            item.setStyleSheet(f"color: {color}; border: none;")
            status_row.addWidget(item)
        status_row.addStretch()
        layout.addLayout(status_row)

        # Tabela (QTreeWidget)
        tree = QTreeWidget()
        tree.setHeaderLabels(["Faza / Stavka", "Status", "Agent/Sesija", "Kriterijumi", "Stanje nastavka"])
        tree.setAlternatingRowColors(True)
        tree.setRootIsDecorated(True)
        tree.setIndentation(20)
        tree.setStyleSheet(f"""
            QTreeWidget {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px; }}
            QTreeWidget::item {{ padding: {SPACING_SM}px; color: {TEXT_PRIMARY}; }}
            QTreeWidget::item:selected {{ background: {BG_HOVER}; }}
            QHeaderView::section {{ background: {BG_SECONDARY}; border: none; border-bottom: 1px solid {BORDER}; padding: {SPACING_SM}px; color: {TEXT_MUTED}; font-weight: bold; }}
        """)
        tree.setColumnWidth(0, 300)
        tree.setColumnWidth(1, 100)
        tree.setColumnWidth(2, 120)
        tree.setColumnWidth(3, 100)
        tree.setColumnWidth(4, 140)

        # Faza 1
        f1 = QTreeWidgetItem(tree, ["Faza 1 — Temelj i prvi vertikalni tok", "", "", "", ""])
        f1.setExpanded(True)
        f1.setFont(0, QFont("Segoe UI", FONT_MD, QFont.Weight.Bold))

        items = [
            ("FLOW-101  Shared contracts", "VERIFIED", "—", "6/6", "Spremno"),
            ("FLOW-102  SQLite i migracije", "ACCEPTED", "—", "8/8", "Završeno"),
            ("FLOW-103  Service runtime", "IMPLEMENTED", "pi / SESSION-42", "5/7", "NEEDS_REVIEW"),
            ("FLOW-104  Projects/Tasks API", "NOT_STARTED", "—", "0/6", "BLOCKED"),
        ]
        for key, status, agent, crit, next_step in items:
            row = QTreeWidgetItem(f1, [key, status, agent, crit, next_step])
            row.setForeground(1, QColor(_status_badge(status)))

        # Faza 2
        f2 = QTreeWidgetItem(tree, ["Faza 2 — Wrapper, watcher i Aktivne sesije", "", "", "", ""])
        f2.setFont(0, QFont("Segoe UI", FONT_MD, QFont.Weight.Bold))
        QTreeWidgetItem(f2, ["FLOW-201  CLI skeleton", "NOT_STARTED", "—", "0/4", "—"])

        layout.addWidget(tree)


# ═══════════════════════════════════════════════════════════════════
# Centralni — Aktivne sesije
# ═══════════════════════════════════════════════════════════════════

class ActiveSessionsWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING_SM)

        layout.addWidget(_label("AKTIVNE SESIJE (2)", FONT_LG, True))

        tree = QTreeWidget()
        tree.setHeaderLabels(["Sesija", "Agent", "Plan stavka", "Worktree/Branch", "Status"])
        tree.setRootIsDecorated(False)
        tree.setMaximumHeight(120)
        tree.setStyleSheet(f"""
            QTreeWidget {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px; }}
            QTreeWidget::item {{ padding: {SPACING_SM}px; color: {TEXT_PRIMARY}; }}
            QHeaderView::section {{ background: {BG_SECONDARY}; border: none; border-bottom: 1px solid {BORDER}; padding: {SPACING_SM}px; color: {TEXT_MUTED}; font-weight: bold; }}
        """)

        sessions = [
            ("SESSION-42", "pi", "FLOW-103 Service runtime", "flow/FLOW-103", "ACTIVE"),
            ("SESSION-41", "Claude Code", "FLOW-104 Projects/Tasks", "main", "ACTIVE"),
        ]
        for sid, agent, plan, wb, status in sessions:
            row = QTreeWidgetItem(tree, [sid, agent, plan, wb, status])
            row.setForeground(4, QColor(_status_badge(status)))

        layout.addWidget(tree)


# ═══════════════════════════════════════════════════════════════════
# Centralni — Nedavna aktivnost
# ═══════════════════════════════════════════════════════════════════

class RecentActivityWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING_SM)

        header = QHBoxLayout()
        header.addWidget(_label("NEDAVNA AKTIVNOST", FONT_LG, True))
        header.addStretch()
        header.addWidget(QPushButton("Otvori timeline →"))
        layout.addLayout(header)

        events = [
            ("17:22", "pi / SESSION-42", "Commit a8f19d2"),
            ("17:10", "pi / SESSION-42", "Testovi: 18/19 prolazi"),
            ("16:40", "Sesija pokrenuta", "FLOW-103"),
            ("15:55", "FLOW-102", "Prešao u VERIFIED"),
        ]

        for time, source, detail in events:
            row_layout = QHBoxLayout()
            t = _label(time, FONT_XS, False, TEXT_MUTED)
            t.setFixedWidth(50)
            row_layout.addWidget(t)
            row_layout.addWidget(_label(source, FONT_SM, True))
            row_layout.addWidget(_label(detail, FONT_SM, False, TEXT_SECONDARY))
            row_layout.addStretch()
            layout.addLayout(row_layout)


# ═══════════════════════════════════════════════════════════════════
# Desni panel — Gdje si stao
# ═══════════════════════════════════════════════════════════════════

class ProjectResumeWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL)
        layout.setSpacing(SPACING_MD)

        layout.addWidget(_label("GDJE SI STAO", FONT_LG, True))

        # Informacije
        rows = [
            ("Plan:", "FlowOS v3"),
            ("Posljednja stavka:", "FLOW-103 — Service runtime"),
            ("Stanje:", "IMPLEMENTED · nije VERIFIED"),
            ("Posljednja sesija:", "pi · SESSION-42 · juče 18:20"),
            ("Posljednji dokaz:", "commit a8f19d2 · 18/19 testova"),
        ]
        for label, value in rows:
            row = QHBoxLayout()
            row.addWidget(_label(label, FONT_XS, False, TEXT_MUTED))
            row.addWidget(_label(value, FONT_SM, True))
            row.addStretch()
            layout.addLayout(row)

        layout.addSpacing(SPACING_SM)

        # Gdje je rad stao
        layout.addWidget(_section_title("Gdje je rad stao"))
        layout.addWidget(_label("Runtime servis i endpointi implementirani. Force terminate ostavlja descriptor.", FONT_SM, False, TEXT_SECONDARY))

        # Sljedeći korak
        layout.addWidget(_section_title("Sljedeći konkretan korak"))
        layout.addWidget(_label("Implementirati supervisor cleanup nakon hard terminate-a.", FONT_SM, True, TEXT_PRIMARY))

        # Preuslovi
        layout.addWidget(_section_title("Prije nastavka provjeriti"))
        layout.addWidget(_label("• trenutni HEAD\n• dirty tree\n• failing Windows lifecycle test", FONT_SM, False, TEXT_SECONDARY))

        # Confidence
        conf_layout = QHBoxLayout()
        conf_layout.addWidget(_label("Pouzdanost:", FONT_XS, False, TEXT_MUTED))
        conf_layout.addWidget(_label("SREDNJA", FONT_SM, True, YELLOW))
        conf_layout.addWidget(_label("· posljednji reconciliation: prije 2 min", FONT_XS, False, TEXT_MUTED))
        conf_layout.addStretch()
        layout.addLayout(conf_layout)

        # Dugmad
        btn_layout = QHBoxLayout()
        for text in ["Nastavi rad", "Otvori report"]:
            btn = QPushButton(text)
            btn.setStyleSheet(f"background: {BG_HOVER}; border: 1px solid {BORDER}; border-radius: {RADIUS_SM}px; color: {TEXT_PRIMARY}; padding: {SPACING_SM}px {SPACING_XL}px;")
            btn_layout.addWidget(btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)


# ═══════════════════════════════════════════════════════════════════
# Desni panel — Detalji stavke plana
# ═══════════════════════════════════════════════════════════════════

class PlanItemDetailsWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL)
        layout.setSpacing(SPACING_MD)

        layout.addWidget(_label("DETALJI STAVKE PLANA", FONT_LG, True))

        # Info
        for label, value in [("FLOW-103", "Service runtime"), ("Faza:", "Faza 1"), ("Status:", "IMPLEMENTED"), ("Agent:", "pi"), ("Sesija:", "SESSION-42")]:
            row = QHBoxLayout()
            row.addWidget(_label(label, FONT_XS, False, TEXT_MUTED))
            row.addWidget(_label(value, FONT_SM, True))
            row.addStretch()
            layout.addLayout(row)

        # Acceptance kriterijumi
        layout.addWidget(_section_title("Acceptance kriterijumi"))
        criteria = [
            ("✓", "FastAPI app sa lifespan-om", GREEN),
            ("✓", "Single-instance lock", GREEN),
            ("✓", "Runtime descriptor", GREEN),
            ("✓", "/health, /version, /runtime", GREEN),
            ("◐", "Graceful shutdown — 1 test pada", YELLOW),
            ("○", "Lokalni strukturisani logovi", GRAY),
        ]
        for check, desc, color in criteria:
            row = QHBoxLayout()
            c = _label(check, FONT_SM, True, color)
            c.setFixedWidth(20)
            row.addWidget(c)
            row.addWidget(_label(desc, FONT_SM, False, TEXT_SECONDARY))
            row.addStretch()
            layout.addLayout(row)

        # Dokazi
        layout.addWidget(_section_title("Dokazi"))
        layout.addWidget(_label("Commit: a8f19d2 · Testovi: 18/19 · Report: 2026-07-31_FLOW-103.md", FONT_XS, False, TEXT_MUTED))


# ═══════════════════════════════════════════════════════════════════
# Desni panel — Reconciliation
# ═══════════════════════════════════════════════════════════════════

class ReconciliationWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_CARD}; border: 1px solid {YELLOW}; border-radius: {RADIUS_MD}px; border-left: 4px solid {YELLOW};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL)
        layout.setSpacing(SPACING_SM)

        layout.addWidget(_label("⚠ PROMJENE VAN FLOWOS-A", FONT_MD, True, YELLOW))
        layout.addWidget(_label("Projekat je mijenjan van FlowOS-a.", FONT_SM, False, TEXT_SECONDARY))
        layout.addWidget(_label("3 nova commita · 2 nekomitovana fajla", FONT_SM, True))
        layout.addWidget(_label("Branch: main → feature/runtime-fix", FONT_XS, False, TEXT_MUTED))
        layout.addWidget(_label("Autor nije potvrđen.", FONT_XS, False, RED))


# ═══════════════════════════════════════════════════════════════════
# Footer
# ═══════════════════════════════════════════════════════════════════

class StatusBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(FOOTER_HEIGHT)
        self.setStyleSheet(f"background: {BG_SECONDARY}; border-top: 1px solid {BORDER};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING_XL, 0, SPACING_XL, 0)
        layout.setSpacing(SPACING_XL)

        for text in ["Servis: aktivan", "API: v1", "Baza: flowos.db · OK", "Watcher: aktivan", "Reconciliation: prije 2 min"]:
            layout.addWidget(_label(text, FONT_XS, False, TEXT_MUTED))
        layout.addStretch()


# ═══════════════════════════════════════════════════════════════════
# MainWindow
# ═══════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlowOS — Pregled")
        self.resize(1400, 900)
        self.setMinimumSize(1024, 700)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Topbar
        self.topbar = TopBar()
        root.addWidget(self.topbar)

        # Glavni sadržaj: Sidebar + Centralni + Desni
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.sidebar = Sidebar()
        splitter.addWidget(self.sidebar)

        # Centralni — scrollabilan
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {BG_PRIMARY}; }}")

        central_content = QWidget()
        central_layout = QVBoxLayout(central_content)
        central_layout.setContentsMargins(SPACING_XXL, SPACING_XL, SPACING_XL, SPACING_XL)
        central_layout.setSpacing(SPACING_XL)

        central_layout.addWidget(PlanProgressWidget())
        central_layout.addWidget(ActiveSessionsWidget())
        central_layout.addWidget(RecentActivityWidget())
        central_layout.addStretch()

        scroll.setWidget(central_content)
        splitter.addWidget(scroll)

        # Desni panel — scrollabilan
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {BG_PRIMARY}; }}")

        right_content = QWidget()
        right_layout = QVBoxLayout(right_content)
        right_layout.setContentsMargins(0, SPACING_XL, SPACING_XXL, SPACING_XL)
        right_layout.setSpacing(SPACING_LG)

        right_layout.addWidget(ProjectResumeWidget())
        right_layout.addWidget(PlanItemDetailsWidget())
        right_layout.addWidget(ReconciliationWidget())
        right_layout.addStretch()

        right_scroll.setWidget(right_content)
        splitter.addWidget(right_scroll)

        # Proporcije
        splitter.setSizes([SIDEBAR_DEFAULT, 700, RIGHT_PANEL_DEFAULT])
        splitter.setStretchFactor(0, 0)  # Sidebar — fixed
        splitter.setStretchFactor(1, 1)  # Centralni — rasteže se
        splitter.setStretchFactor(2, 0)  # Desni — fixed

        root.addWidget(splitter)

        # Footer
        root.addWidget(StatusBar())


# ═══════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("FlowOS")
    apply_dark_theme(app)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
