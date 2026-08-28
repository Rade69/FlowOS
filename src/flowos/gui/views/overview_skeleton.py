"""FlowOS GUI — Overview ekran (preveden, popravljen desni panel).

Tamna tema, QSplitter + layouti, svi pojmovi na srpskom.
View → Controller → Services arhitektura.

Pokreni: python src/flowos/gui/views/overview_skeleton.py
"""

# mypy: disable-error-code="union-attr,return-value"

import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QSystemTrayIcon,
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
    "NOT_STARTED": GRAY,
    "IN_PROGRESS": YELLOW,
    "BLOCKED": RED,
    "IMPLEMENTED": PURPLE,
    "VERIFIED": TEAL,
    "ACCEPTED": GREEN,
    "REJECTED": "#EBA0AC",
    "NEEDS_REVIEW": YELLOW,
    "ACTIVE": GREEN,
    "COMPLETED": GRAY,
    "NO_HISTORY": GRAY,
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
    if bold:
        f.setBold(True)
    lbl.setFont(f)
    lbl.setStyleSheet(f"color: {color}; border: none; background: transparent;")
    return lbl


def _sec(text=""):
    return _lbl(text.upper(), FONT_XS, True, TEXT_MUTED)


def _card(parent=None):
    f = QFrame(parent)
    f.setStyleSheet(
        f"background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;"
    )
    return f


def _status_color(status: str) -> str:
    return STATUS_COLORS.get(status, GRAY)


# ═══════════════════════════════════════════════════════════════════
# TopBar
# ═══════════════════════════════════════════════════════════════════


class TopBar(QFrame):
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(TOPBAR_HEIGHT)
        self.setStyleSheet(f"background: {BG_SECONDARY}; border-bottom: 1px solid {BORDER};")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING_XL, 0, SPACING_XL, 0)
        layout.setSpacing(SPACING_MD)

        self._proj_label = _lbl("FlowOS", FONT_LG, True, BLUE)
        layout.addWidget(self._proj_label)

        sep = QLabel("·")
        sep.setStyleSheet(f"color: {BORDER}; border: none; font-size: {FONT_LG}px;")
        layout.addWidget(sep)

        self._phase_label = _lbl("", FONT_SM, False, TEXT_SECONDARY)
        layout.addWidget(self._phase_label)

        self._stats_label = _lbl("", FONT_SM, False, TEXT_MUTED)
        layout.addWidget(self._stats_label)

        layout.addStretch()

        self._git_label = _lbl("", FONT_SM, False, TEXT_MUTED)
        layout.addWidget(self._git_label)

        btn = QPushButton("↻")
        btn.setFixedSize(32, 32)
        btn.setToolTip("Osveži podatke")
        btn.setStyleSheet(
            f"QPushButton {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 4px; color: {TEXT_PRIMARY}; }}"
            f"QPushButton:hover {{ background: {BG_HOVER}; }}"
        )
        btn.clicked.connect(self.refresh_requested.emit)
        layout.addWidget(btn)

    def set_info(
        self, project: str = "", phase: str = "", sessions: int = -1, git_status: str = ""
    ) -> None:
        if project:
            self._proj_label.setText(project)
        if phase:
            self._phase_label.setText(phase)
        parts = []
        if sessions >= 0:
            parts.append(
                f"{sessions} aktivna sesija"
                if sessions == 1
                else f"{sessions} aktivne sesije"
                if sessions > 0
                else ""
            )
        self._stats_label.setText(" · ".join(p for p in parts if p))
        if git_status:
            self._git_label.setText(git_status)


# ═══════════════════════════════════════════════════════════════════
# Sidebar
# ═══════════════════════════════════════════════════════════════════


class Sidebar(QFrame):
    navigation_requested = Signal(str)
    action_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(SIDEBAR_MIN)
        self.setMaximumWidth(300)
        self.setStyleSheet(f"background: {BG_SECONDARY}; border-right: 1px solid {BORDER};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, SPACING_MD, 0, SPACING_MD)
        layout.setSpacing(0)

        nav_label = _sec("Navigacija")
        nav_label.setContentsMargins(SPACING_XL, SPACING_SM, 0, SPACING_SM)
        layout.addWidget(nav_label)

        self._nav_buttons: dict[str, QPushButton] = {}
        nav_groups = [
            ("RAD", ["Pregled", "Plan", "Zadaci", "Sesije"]),
            ("NADZOR", ["Agenti", "Radna stabla", "Konflikti", "Izvještaji"]),
            ("SISTEM", ["Projekti", "Postavke"]),
        ]
        for group_label, nav_keys in nav_groups:
            if group_label:
                sep = _sec(group_label)
                sep.setContentsMargins(SPACING_XL, SPACING_SM, 0, SPACING_XS)
                layout.addWidget(sep)
            for item in nav_keys:
                btn = QPushButton(f"  {item}")
                btn.setFixedHeight(36)
                btn.setStyleSheet(
                    f"QPushButton {{ background: transparent; border-left: 3px solid transparent; border-top:none; border-right:none; border-bottom:none; color: {TEXT_SECONDARY}; text-align:left; padding-left:{SPACING_XL}px; font-size:{FONT_SM}px; }} QPushButton:hover {{ background: {BG_HOVER}; color: {TEXT_PRIMARY}; }}"
                )
                btn.clicked.connect(lambda checked, key=item: self._on_nav(key))
                self._nav_buttons[item] = btn
                layout.addWidget(btn)

        self._set_active("Pregled")

        layout.addSpacing(SPACING_XL)

        # Aktivni projekat — popunjena kartica
        proj_title = _sec("AKTIVNI PROJEKAT")
        proj_title.setContentsMargins(SPACING_XL, SPACING_SM, 0, SPACING_SM)
        layout.addWidget(proj_title)
        card = _card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        cl.setSpacing(SPACING_SM)
        self._proj_name = _lbl("Nema projekta", FONT_MD, True)
        cl.addWidget(self._proj_name)
        self._proj_plan = _lbl("", FONT_XS, False, GREEN)
        cl.addWidget(self._proj_plan)
        self._proj_task = _lbl("", FONT_SM, True)
        cl.addWidget(self._proj_task)
        self._proj_status = _lbl("", FONT_XS, False, PURPLE)
        cl.addWidget(self._proj_status)
        self._proj_last = _lbl("", FONT_XS, False, TEXT_MUTED)
        cl.addWidget(self._proj_last)
        layout.addWidget(card)

        layout.addSpacing(SPACING_MD)

        actions_title = _sec("Brze akcije")
        actions_title.setContentsMargins(SPACING_XL, SPACING_SM, 0, SPACING_SM)
        layout.addWidget(actions_title)
        for a in [
            "Nova sesija",
            "Dodaj zadatak",
            "Uvezi plan",
            "Pregledaj vanjske promjene",
            "Otvori dnevnik",
        ]:
            btn = QPushButton(f"  {a}")
            btn.setFixedHeight(32)
            btn.setStyleSheet(
                f"QPushButton {{ background:transparent; border:none; color:{TEXT_SECONDARY}; text-align:left; padding-left:{SPACING_XL}px; font-size:{FONT_SM}px; }} QPushButton:hover {{ color:{TEXT_PRIMARY}; }}"
            )
            btn.clicked.connect(lambda checked, key=a: self.action_requested.emit(key))
            layout.addWidget(btn)

        layout.addStretch()

    def _on_nav(self, key: str) -> None:
        self._set_active(key)
        self.navigation_requested.emit(key)

    def _set_active(self, active_key: str) -> None:
        for key, btn in self._nav_buttons.items():
            active = key == active_key
            bg = BG_HOVER if active else "transparent"
            bl = (
                f"border-left: 3px solid {BLUE};"
                if active
                else "border-left: 3px solid transparent;"
            )
            color = TEXT_PRIMARY if active else TEXT_SECONDARY
            btn.setStyleSheet(
                f"QPushButton {{ background: {bg}; {bl} border-top:none; border-right:none; border-bottom:none; color: {color}; text-align:left; padding-left:{SPACING_XL}px; font-size:{FONT_SM}px; }} QPushButton:hover {{ background: {BG_HOVER}; color: {TEXT_PRIMARY}; }}"
            )

    def set_project_info(self, data: dict | None) -> None:
        if not data:
            self._proj_name.setText("Nema projekta")
            self._proj_plan.setText("")
            self._proj_task.setText("")
            self._proj_status.setText("")
            self._proj_last.setText("")
            return
        self._proj_name.setText(data.get("name", ""))
        plan_title = data.get("plan_title", "")
        self._proj_plan.setText(f"Plan: {plan_title}" if plan_title else "")
        task = data.get("active_plan_item", "")
        self._proj_task.setText(task if task else "")
        status = data.get("active_plan_status", "")
        self._proj_status.setText(status if status else "")
        last = data.get("last_activity", "")
        self._proj_last.setText(f"Posljednji rad: {last}" if last else "")


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

        header = QHBoxLayout()
        header.addWidget(_lbl("NAPREDAK PO PLANU", FONT_LG, True))
        header.addStretch()
        header.addWidget(_lbl("Aktivni plan: FlowOS v3", FONT_SM, False, TEXT_MUTED))
        layout.addLayout(header)

        # Statusni sažetak na srpskom
        sr = QHBoxLayout()
        sr.setSpacing(SPACING_LG)
        for n, s, c in [
            (3, "prihvaćene", GREEN),
            (1, "provjerena", TEAL),
            (1, "implementirana", PURPLE),
            (1, "u toku", YELLOW),
            (3, "nisu započete", GRAY),
        ]:
            it = QLabel(f"{n} {s}")
            it.setFont(QFont("Segoe UI", FONT_SM, QFont.Weight.Bold))
            it.setStyleSheet(f"color: {c}; border: none;")
            sr.addWidget(it)
        sr.addStretch()
        layout.addLayout(sr)

        tree = QTreeWidget()
        tree.setHeaderLabels(["Faza / Stavka", "Status", "Agent/Sesija", "Kriterijumi", "Stanje"])
        tree.setAlternatingRowColors(True)
        tree.setRootIsDecorated(True)
        tree.setIndentation(20)
        tree.setStyleSheet(f"""QTreeWidget {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px; }}
            QTreeWidget::item {{ padding: {SPACING_SM}px; color: {TEXT_PRIMARY}; }}
            QTreeWidget::item:selected {{ background: {BG_HOVER}; }}
            QHeaderView::section {{ background: {BG_SECONDARY}; border: none; border-bottom: 1px solid {BORDER}; padding: {SPACING_SM}px; color: {TEXT_MUTED}; font-weight: bold; }}""")
        tree.setColumnWidth(0, 340)
        tree.setColumnWidth(1, 100)
        tree.setColumnWidth(2, 110)
        tree.setColumnWidth(3, 80)
        tree.setColumnWidth(4, 110)

        f1 = QTreeWidgetItem(tree, ["Faza 1 — Temelj i prvi vertikalni tok", "", "", "", ""])
        f1.setExpanded(True)
        f1.setFont(0, QFont("Segoe UI", FONT_MD, QFont.Weight.Bold))
        for key, status, agent, crit, ns in [
            ("FLOW-101  Zajednički ugovori", "VERIFIED", "—", "6/6", "Spremno"),
            ("FLOW-102  SQLite i migracije", "ACCEPTED", "—", "8/8", "Završeno"),
            (
                "FLOW-103  Rad servisnog procesa",
                "IMPLEMENTED",
                "pi / SESSION-42",
                "5/7",
                "Potreban pregled",
            ),
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
        l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(SPACING_SM)
        l.addWidget(_lbl("AKTIVNE SESIJE (1)", FONT_LG, True))

        tree = QTreeWidget()
        tree.setHeaderLabels(["Sesija", "Agent", "Plan stavka", "Grana", "Status"])
        tree.setRootIsDecorated(False)
        tree.setMaximumHeight(90)
        tree.setStyleSheet(f"""QTreeWidget {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px; }}
            QTreeWidget::item {{ padding: {SPACING_SM}px; color: {TEXT_PRIMARY}; }}
            QHeaderView::section {{ background: {BG_SECONDARY}; border: none; border-bottom: 1px solid {BORDER}; padding: {SPACING_SM}px; color: {TEXT_MUTED}; font-weight: bold; }}""")
        row = QTreeWidgetItem(
            tree, ["SESSION-42", "pi", "FLOW-103", "flow/FLOW-103", status_label("ACTIVE")]
        )
        row.setForeground(4, QColor(GREEN))
        l.addWidget(tree)


# ═══════════════════════════════════════════════════════════════════
# Centralni — Nedavna aktivnost
# ═══════════════════════════════════════════════════════════════════


class RecentActivityWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._content = QVBoxLayout(self)
        self._content.setContentsMargins(0, 0, 0, 0)
        self._content.setSpacing(SPACING_SM)
        self._content.addWidget(_lbl("NEDAVNA AKTIVNOST", FONT_LG, True))
        self._items_layout = QVBoxLayout()
        self._items_layout.setSpacing(SPACING_XS)
        self._content.addLayout(self._items_layout)
        self._content.addStretch()
        self.render([])

    def render(self, items: list) -> None:  # type: ignore[override]
        self._clear_items()
        if not items or not isinstance(items, list):
            self._items_layout.addWidget(
                _lbl("Nema nedavne aktivnosti.", FONT_XS, False, TEXT_MUTED)
            )
            return
        for item in items[:20]:
            event_type = item.get("type", "")
            label_map = {
                "FILE": "FAJL",
                "SESSION": "SESIJA",
                "GIT": "GIT",
                "TEST": "TEST",
                "PLAN": "PLAN",
                "KONFLIKT": "KONFLIKT",
            }
            label = label_map.get(event_type, event_type)
            summary = item.get("event", "") or item.get("file", "")
            ts = item.get("occurred_at", "")
            relative = ""
            if ts:
                try:
                    from datetime import UTC, datetime

                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    delta = datetime.now(tz=UTC) - dt
                    s = int(delta.total_seconds())
                    if s < 60:
                        relative = "upravo"
                    elif s < 3600:
                        relative = f"prije {s // 60}m"
                    elif s < 86400:
                        relative = f"prije {s // 3600}h"
                    else:
                        relative = f"prije {s // 86400}d"
                except Exception:
                    pass

            row = QHBoxLayout()
            row.addWidget(_lbl(label, FONT_XS, True, BLUE))
            row.addWidget(_lbl(summary[:60], FONT_XS, False, TEXT_SECONDARY))
            row.addWidget(_lbl(relative, FONT_XS, False, TEXT_MUTED))
            row.addStretch()
            self._items_layout.addLayout(row)

    def _clear_items(self) -> None:
        while self._items_layout.count():
            w = self._items_layout.takeAt(0)
            if w.widget():
                w.widget().deleteLater()
            elif w.layout():
                self._clear_recursive(w.layout())

    def _clear_recursive(self, lo) -> None:
        while lo.count():
            w = lo.takeAt(0)
            if w.widget():
                w.widget().deleteLater()
            elif w.layout():
                self._clear_recursive(w.layout())


# ═══════════════════════════════════════════════════════════════════
# Desni panel — Gdje si stao (čitljiv, word wrap)
# ═══════════════════════════════════════════════════════════════════


class ProjectResumeWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;"
        )
        l = QVBoxLayout(self)
        l.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL)
        l.setSpacing(SPACING_MD)
        l.addWidget(_lbl("GDJE SI STAO", FONT_LG, True))

        # Glavne info
        for lbl, val in [
            ("FLOW-103 — Rad servisnog procesa", ""),
            ("Implementirano", PURPLE),
            ("Nije provjereno", YELLOW),
        ]:
            if lbl.startswith("FLOW"):
                l.addWidget(_lbl(lbl, FONT_MD, True))
            else:
                l.addWidget(_lbl(lbl, FONT_SM, True, val or TEXT_PRIMARY))

        l.addWidget(_lbl("Posljednji rad", FONT_XS, False, TEXT_MUTED))
        l.addWidget(_lbl("pi · SESSION-42 · juče 18:20", FONT_SM, True))

        # Gdje je rad stao
        l.addWidget(_sec("Gdje je rad stao"))
        stopped = _lbl(
            "Rad servisnog procesa i dijagnostički endpointi su implementirani. "
            "Force terminate na Windows-u ostavlja runtime descriptor.",
            FONT_SM,
            False,
            TEXT_SECONDARY,
        )
        stopped.setWordWrap(True)
        l.addWidget(stopped)

        # Sljedeći korak — vizuelno istaknut
        l.addWidget(_sec("Sljedeći konkretan korak"))
        next_step = _lbl(
            "Implementirati nadzor nad čišćenjem nakon prisilnog prekida.",
            FONT_SM,
            True,
            TEXT_PRIMARY,
        )
        next_step.setWordWrap(True)
        l.addWidget(next_step)

        # Preuslovi
        l.addWidget(_sec("Prije nastavka provjeriti"))
        prec = _lbl(
            "• trenutni HEAD\n• radno stablo sa neupisanim promjenama\n• neuspješan test životnog ciklusa",
            FONT_SM,
            False,
            TEXT_SECONDARY,
        )
        prec.setWordWrap(True)
        l.addWidget(prec)

        # Pouzdanost
        cr = QHBoxLayout()
        cr.addWidget(_lbl("Pouzdanost:", FONT_XS, False, TEXT_MUTED))
        cr.addWidget(_lbl("Srednja", FONT_SM, True, YELLOW))
        cr.addWidget(_lbl("· posljednje usklađivanje: prije 2 min", FONT_XS, False, TEXT_MUTED))
        cr.addStretch()
        l.addLayout(cr)

        bl = QHBoxLayout()
        for t in ["Nastavi rad", "Otvori izvještaj"]:
            btn = QPushButton(t)
            btn.setStyleSheet(
                f"background: {BG_HOVER}; border: 1px solid {BORDER}; border-radius: 4px; color: {TEXT_PRIMARY}; padding: {SPACING_SM}px {SPACING_XL}px;"
            )
            bl.addWidget(btn)
        bl.addStretch()
        l.addLayout(bl)


# ═══════════════════════════════════════════════════════════════════
# Desni panel — Detalji stavke plana
# ═══════════════════════════════════════════════════════════════════


class PlanItemDetailsWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;"
        )
        l = QVBoxLayout(self)
        l.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL)
        l.setSpacing(SPACING_MD)
        l.addWidget(_lbl("DETALJI STAVKE PLANA", FONT_LG, True))

        for lbl, val in [
            ("FLOW-103", "Rad servisnog procesa"),
            ("Faza:", "Faza 1"),
            ("Status:", "Implementirano"),
            ("Agent:", "pi"),
            ("Sesija:", "SESSION-42"),
        ]:
            r = QHBoxLayout()
            r.addWidget(_lbl(lbl, FONT_XS, False, TEXT_MUTED))
            r.addWidget(_lbl(val, FONT_SM, True))
            r.addStretch()
            l.addLayout(r)

        l.addWidget(_sec("Kriterijumi prihvatanja"))
        for c, d, col in [
            ("✓", "FastAPI aplikacija sa životnim ciklusom", GREEN),
            ("✓", "Single-instance zaključavanje", GREEN),
            ("✓", "Runtime descriptor", GREEN),
            ("✓", "/health, /version, /runtime", GREEN),
            ("◐", "Pristojno gašenje — 1 test ne prolazi", YELLOW),
            ("○", "Lokalni strukturisani zapisi", GRAY),
        ]:
            rl = QHBoxLayout()
            cl = QLabel(c)
            cl.setFont(QFont("Segoe UI", FONT_SM, QFont.Weight.Bold))
            cl.setStyleSheet(f"color: {col}; border: none;")
            cl.setFixedWidth(20)
            rl.addWidget(cl)
            rl.addWidget(_lbl(d, FONT_SM, False, TEXT_SECONDARY))
            rl.addStretch()
            l.addLayout(rl)

        l.addWidget(_sec("Dokazi"))
        l.addWidget(
            _lbl(
                "Commit: a8f19d2 · Testovi: 18/19 · Izvještaj: 2026-07-31_FLOW-103.md",
                FONT_XS,
                False,
                TEXT_MUTED,
            )
        )


# ═══════════════════════════════════════════════════════════════════
# Desni panel — Usklađivanje stanja
# ═══════════════════════════════════════════════════════════════════


class ReconciliationWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"background: {BG_CARD}; border: 1px solid {YELLOW}; border-radius: {RADIUS_MD}px; border-left: 4px solid {YELLOW};"
        )
        l = QVBoxLayout(self)
        l.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL)
        l.setSpacing(SPACING_SM)
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
        l = QHBoxLayout(self)
        l.setContentsMargins(SPACING_XL, 0, SPACING_XL, 0)
        l.setSpacing(SPACING_XL)

        self._health = _lbl("● Servis: povezuje se…", FONT_XS, False, YELLOW)
        l.addWidget(self._health)
        self._sessions = _lbl("Sesije: —", FONT_XS, False, TEXT_MUTED)
        l.addWidget(self._sessions)
        self._watcher = _lbl("Posmatrač: —", FONT_XS, False, TEXT_MUTED)
        l.addWidget(self._watcher)
        self._git = _lbl("Git: —", FONT_XS, False, TEXT_MUTED)
        l.addWidget(self._git)
        l.addStretch()

    def set_connected(self, ok: bool) -> None:
        if ok:
            self._health.setText("● Servis: aktivan")
            self._health.setStyleSheet(f"color: {GREEN}; border: none; background: transparent;")
        else:
            self._health.setText("● Servis: nedostupan")
            self._health.setStyleSheet(f"color: {RED}; border: none; background: transparent;")

    def set_stats(self, sessions: int, projects: int, watcher_active: bool) -> None:
        self._sessions.setText(f"Sesije: {sessions}" if sessions >= 0 else "Sesije: —")
        self._watcher.setText("● Posmatrač: aktivan" if watcher_active else "Posmatrač: —")
        if watcher_active:
            self._watcher.setStyleSheet(f"color: {GREEN}; border: none; background: transparent;")


# ═══════════════════════════════════════════════════════════════════
# MainWindow
# ═══════════════════════════════════════════════════════════════════


class MainWindow(QMainWindow):
    """Glavni prozor sa sidebar navigacijom i QStackedWidget-om."""

    page_changed = Signal(str)
    reports_folder_requested = Signal()

    PAGE_NAMES = [
        "Pregled",
        "Projekti",
        "Plan",
        "Sesije",
        "Zadaci",
        "Agenti",
        "Radna stabla",
        "Konflikti",
        "Izvještaji",
        "Postavke",
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlowOS — Pregled")
        self.resize(1400, 900)
        self.setMinimumSize(1024, 700)

        c = QWidget()
        self.setCentralWidget(c)
        root = QVBoxLayout(c)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.topbar = TopBar()
        root.addWidget(self.topbar)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        self._sidebar = Sidebar()
        self._sidebar.navigation_requested.connect(self._on_navigate)
        self._sidebar.action_requested.connect(self._on_action)
        self._splitter.addWidget(self._sidebar)

        self._stack = QStackedWidget()
        self._pages: dict[str, QWidget] = {}

        self._build_overview_page()
        self._build_placeholder_pages()
        self._splitter.addWidget(self._stack)

        self._splitter.setSizes([SIDEBAR_DEFAULT, 900])
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        root.addWidget(self._splitter)
        self._statusbar = StatusBar()
        root.addWidget(self._statusbar)

        # System tray
        self._setup_tray()

    def _setup_tray(self) -> None:
        # System tray — za sada onemogućen (treba ikona)
        return

    # ── Overview (Pregled) stranica ─────────────────────

    def _build_overview_page(self):
        page = QWidget()
        page.setStyleSheet(f"background: {BG_PRIMARY};")
        hsplit = QSplitter(Qt.Orientation.Horizontal)

        # Centralni deo — vertikalni layout sa ResumeHero na vrhu
        cs = QScrollArea()
        cs.setWidgetResizable(True)
        cs.setStyleSheet(f"QScrollArea {{ border: none; background: {BG_PRIMARY}; }}")
        self._central_widget = QWidget()
        self._central_layout = QVBoxLayout(self._central_widget)
        self._central_layout.setContentsMargins(SPACING_XL, SPACING_MD, SPACING_MD, SPACING_XL)
        self._central_layout.setSpacing(SPACING_MD)
        # Placeholderi — zamenjuju se kroz set_central_widgets
        self._central_layout.addWidget(PlanProgressWidget())
        self._central_layout.addWidget(ActiveSessionsWidget())
        self._central_layout.addWidget(RecentActivityWidget())
        self._central_layout.addStretch()
        cs.setWidget(self._central_widget)
        hsplit.addWidget(cs)

        # Desni deo
        rs = QScrollArea()
        rs.setWidgetResizable(True)
        rs.setStyleSheet(f"QScrollArea {{ border: none; background: {BG_PRIMARY}; }}")
        self._right_widget = QWidget()
        self._right_layout = QVBoxLayout(self._right_widget)
        self._right_layout.setContentsMargins(0, SPACING_MD, SPACING_XL, SPACING_XL)
        self._right_layout.setSpacing(SPACING_MD)
        self._right_layout.addWidget(ProjectResumeWidget())
        self._right_layout.addWidget(PlanItemDetailsWidget())
        self._right_layout.addWidget(ReconciliationWidget())
        self._right_layout.addStretch()
        rs.setWidget(self._right_widget)
        hsplit.addWidget(rs)

        hsplit.setSizes([700, RIGHT_PANEL_DEFAULT])
        hsplit.setStretchFactor(0, 1)
        hsplit.setStretchFactor(1, 0)

        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(hsplit)

        self._add_page("Pregled", page)

    # ── Placeholder stranice ────────────────────────────

    def _build_placeholder_pages(self):
        for name in self.PAGE_NAMES:
            if name == "Pregled":
                continue
            page = self._make_placeholder(name)
            self._add_page(name, page)

    def _make_placeholder(self, title: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {BG_PRIMARY};")
        lo = QVBoxLayout(w)
        lo.setContentsMargins(SPACING_XXL, SPACING_XXL, SPACING_XXL, SPACING_XXL)
        lo.addStretch()
        lbl = _lbl(title.upper(), FONT_XXL, True, TEXT_MUTED)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lo.addWidget(lbl)
        hint = _lbl("U izradi…", FONT_MD, False, TEXT_MUTED)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lo.addWidget(hint)
        lo.addStretch()
        return w

    def _add_page(self, name: str, widget: QWidget) -> None:
        self._pages[name] = widget
        self._stack.addWidget(widget)

    # ── Navigacija ──────────────────────────────────────

    def _on_navigate(self, page_name: str) -> None:
        if page_name in self._pages:
            self._stack.setCurrentWidget(self._pages[page_name])
            self.setWindowTitle(f"FlowOS — {page_name}")
            self.page_changed.emit(page_name)

    def _on_action(self, action: str) -> None:
        mapping = {
            "Nova sesija": "Sesije",
            "Dodaj zadatak": "Zadaci",
            "Pregledaj vanjske promjene": "Konflikti",
        }
        if action in mapping:
            self._on_navigate(mapping[action])
        elif action == "Uvezi plan":
            self._on_navigate("Plan")
        elif action == "Otvori dnevnik":
            self.reports_folder_requested.emit()

    @property
    def overview_page(self) -> QWidget:
        return self._pages.get("Pregled", self._stack.widget(0))

    def set_project_info(self, data: dict | None) -> None:
        self._sidebar.set_project_info(data)

    def set_status(self, connected: bool, sessions: int = -1, watcher_active: bool = False) -> None:
        self._statusbar.set_connected(connected)
        self._statusbar.set_stats(sessions, 0, watcher_active)

    def set_topbar_info(
        self, project: str = "", phase: str = "", sessions: int = -1, git_status: str = ""
    ) -> None:
        self.topbar.set_info(project, phase, sessions, git_status)

    def set_page_widget(self, name: str, widget: QWidget) -> None:
        """Zamenjuje placeholder stranicu pravim View-om."""
        if name in self._pages:
            old = self._pages[name]
            idx = self._stack.indexOf(old)
            self._stack.removeWidget(old)
            old.deleteLater()
            self._pages[name] = widget
            if idx >= 0:
                self._stack.insertWidget(idx, widget)
            else:
                self._stack.addWidget(widget)

    # ── Live data injection (za Pregled stranicu) ──────

    def set_central_widgets(self, widgets: list[QWidget]) -> None:
        for i in reversed(range(self._central_layout.count())):
            w = self._central_layout.itemAt(i).widget()
            if w is not None:
                w.setParent(None)
        for w in widgets:
            self._central_layout.addWidget(w)
        self._central_layout.addStretch()

    def set_right_widgets(self, widgets: list[QWidget]) -> None:
        for i in reversed(range(self._right_layout.count())):
            w = self._right_layout.itemAt(i).widget()
            if w is not None:
                w.setParent(None)
        for w in widgets:
            self._right_layout.addWidget(w)
        self._right_layout.addStretch()

    # ── Zatvaranje ───────────────────────────────────────

    shutdown_requested = Signal()

    def closeEvent(self, event) -> None:
        from PySide6.QtWidgets import QMessageBox

        msg = QMessageBox(self)
        msg.setWindowTitle("FlowOS")
        msg.setText("Šta želite da uradite?")
        msg.setInformativeText(
            "Zatvaranje prozora ne zaustavlja pozadinski servis i agentske sesije."
        )
        btn_close = msg.addButton("Zatvori samo prozor", QMessageBox.ButtonRole.AcceptRole)
        btn_shutdown = msg.addButton(
            "Zaustavi sve i ugasi FlowOS", QMessageBox.ButtonRole.DestructiveRole
        )
        btn_cancel = msg.addButton("Odustani", QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(btn_cancel)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked is btn_close:
            event.accept()
        elif clicked is btn_shutdown:
            self.shutdown_requested.emit()
            event.accept()
        else:
            event.ignore()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("FlowOS")
    apply_dark_theme(app)
    MainWindow().show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
