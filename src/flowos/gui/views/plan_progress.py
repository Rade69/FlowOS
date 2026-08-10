"""PlanProgressView — prikaz napretka po planu (FLOW-105A)."""

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from flowos.gui.theme.labels import status_label
from flowos.gui.views.overview_skeleton import (
    BG_CARD,
    BG_HOVER,
    BG_SECONDARY,
    BLUE,
    BORDER,
    FONT_LG,
    FONT_MD,
    FONT_SM,
    FONT_XS,
    GRAY,
    GREEN,
    PURPLE,
    RADIUS_MD,
    RED,
    SPACING_LG,
    SPACING_MD,
    SPACING_SM,
    SPACING_XL,
    TEAL,
    TEXT_MUTED,
    TEXT_PRIMARY,
    YELLOW,
    _lbl,
    _status_color,
)

STATUS_COUNT_COLORS = {
    "ACCEPTED": GREEN,
    "VERIFIED": TEAL,
    "IMPLEMENTED": PURPLE,
    "IN_PROGRESS": YELLOW,
    "BLOCKED": "#F38BA8",
    "NOT_STARTED": "#A6ADC8",  # TEXT_SECONDARY — svetlija siva
}
STATUS_COUNT_LABELS = {
    "ACCEPTED": "prihvaceno",
    "VERIFIED": "provjereno",
    "IMPLEMENTED": "implementirano",
    "IN_PROGRESS": "u toku",
    "BLOCKED": "blokirano",
    "NOT_STARTED": "nije zapoceto",
}


class PlanProgressView(QFrame):
    import_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tree = None
        self._status_row = None
        self._plan_label = None
        self._setup_ui()
        self.render(None)

    def _setup_ui(self):
        self.setStyleSheet("background: transparent; border: none;")
        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(SPACING_MD)

        # Header row: naslov + dugme za uvoz
        hh = QHBoxLayout()
        hh.addWidget(_lbl("NAPREDAK PO PLANU", FONT_LG, True))
        hh.addStretch()
        import_btn = QPushButton("Uvezi plan")
        import_btn.setStyleSheet(
            f"QPushButton {{ background: {BLUE}; color: #000; border: none; border-radius: {RADIUS_MD}px; "
            f"padding: {SPACING_SM}px {SPACING_LG}px; font-size: {FONT_SM}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: #7AA2F7; }}"
        )
        import_btn.clicked.connect(self.import_requested.emit)
        hh.addWidget(import_btn)
        lo.addLayout(hh)
        self._plan_label = _lbl("", FONT_SM, False, TEXT_MUTED)
        lo.addWidget(self._plan_label)
        self._status_row = QHBoxLayout()
        self._status_row.setSpacing(SPACING_LG)
        lo.addLayout(self._status_row)
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(
            ["Faza / Stavka", "Status", "Agent/Sesija", "Kriterijumi", "Stanje"]
        )
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setIndentation(20)
        self._tree.setStyleSheet(
            f"QTreeWidget{{background:{BG_CARD};border:1px solid {BORDER};border-radius:{RADIUS_MD}px;}}"
            f"QTreeWidget::item{{padding:{SPACING_SM}px;color:{TEXT_PRIMARY};}}"
            f"QTreeWidget::item:selected{{background:{BG_HOVER};}}"
            f"QHeaderView::section{{background:{BG_SECONDARY};border:none;border-bottom:1px solid {BORDER};padding:{SPACING_SM}px;color:{TEXT_MUTED};font-weight:bold;}}"
        )
        self._tree.setColumnWidth(0, 340)
        self._tree.setColumnWidth(1, 100)
        self._tree.setColumnWidth(2, 110)
        self._tree.setColumnWidth(3, 80)
        self._tree.setColumnWidth(4, 110)
        lo.addWidget(self._tree)

    def render(self, data):  # type: ignore[override]
        self._plan_label.setText(  # type: ignore[union-attr]
            "Nema aktivnog plana" if not data else f"Aktivni plan: {data.get('plan_title', '')}"
        )
        self._clear_status()
        self._tree.clear()  # type: ignore[union-attr]
        if not data:
            return
        phases = data.get("phases", [])
        counts = {}  # type: ignore[var-annotated]
        for ph in phases:
            for it in ph.get("items", []):
                counts[it.get("status", "NOT_STARTED")] = (
                    counts.get(it.get("status", "NOT_STARTED"), 0) + 1
                )
        for sk in ["ACCEPTED", "VERIFIED", "IMPLEMENTED", "IN_PROGRESS", "BLOCKED", "NOT_STARTED"]:
            c = counts.get(sk, 0)
            if c > 0 or sk == "NOT_STARTED":
                lbl = QLabel(f"{c} {STATUS_COUNT_LABELS.get(sk, sk)}")
                lbl.setFont(QFont("Segoe UI", FONT_SM, QFont.Weight.Bold))
                lbl.setStyleSheet(f"color:{STATUS_COUNT_COLORS.get(sk, GRAY)};border:none;")
                self._status_row.addWidget(lbl)  # type: ignore[union-attr]
        self._status_row.addStretch()  # type: ignore[union-attr]
        for ph in phases:
            pi = QTreeWidgetItem(
                self._tree,  # type: ignore[arg-type]
                [ph.get("title", ph.get("phase_key", "")), "", "", "", ""],
            )
            pi.setExpanded(True)
            pi.setFont(0, QFont("Segoe UI", FONT_MD, QFont.Weight.Bold))
            for it in ph.get("items", []):
                ik = it.get("item_key", "")
                it_title = it.get("title", "")
                ist = it.get("status", "NOT_STARTED")
                agent = it.get("owner_session_id", "—") or "—"
                cd = it.get("completed_criteria", 0)
                ct = it.get("total_criteria", 0)
                crit = f"{cd}/{ct}" if ct > 0 else "—"
                state = it.get("state_summary", "") or "—"
                label = f"{ik}  {it_title}" if ik else it_title
                row = QTreeWidgetItem(pi, [label, status_label(ist), agent, crit, state])
                row.setForeground(1, QColor(_status_color(ist)))

    def _clear_status(self):
        if not self._status_row:
            return
        while self._status_row.count():
            it = self._status_row.takeAt(0)
            if it.widget():
                it.widget().deleteLater()


# ═══════════════════════════════════════════════════════════════════
# CurrentPhaseView — prikaz samo aktivne faze na Pregledu
# ═══════════════════════════════════════════════════════════════════


class CurrentPhaseView(QFrame):
    """Prikazuje samo relevantne stavke aktivne faze — ne ceo plan."""

    item_selected = Signal(str)
    open_full_plan_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;")
        self._content = QVBoxLayout(self)
        self._content.setContentsMargins(SPACING_XL, SPACING_LG, SPACING_XL, SPACING_LG)
        self._content.setSpacing(SPACING_SM)
        self.render([])

    def render(self, phases: list):  # type: ignore[override]
        self._clear()
        if not phases:
            self._content.addWidget(_lbl("Nema podataka o planu.", FONT_SM, False, TEXT_MUTED))
            self._content.addStretch()
            return

        # Pronađi aktivnu fazu (prvu sa stavkama koje nisu sve NOT_STARTED)
        active_phase = None
        for ph in phases:
            items = ph.get("items", [])
            statuses = {it.get("status", "NOT_STARTED") for it in items}
            if statuses != {"NOT_STARTED"}:
                active_phase = ph
                break
        if not active_phase:
            active_phase = phases[0] if phases else None
        if not active_phase:
            return

        items = active_phase.get("items", [])

        self._content.addWidget(
            _lbl(f"{active_phase.get('phase_key', '')} — {active_phase.get('title', '')}", FONT_MD, True)
        )
        self._content.addSpacing(SPACING_SM)

        # IN_PROGRESS
        in_progress = [it for it in items if it.get("status") == "IN_PROGRESS"]
        if in_progress:
            self._content.addWidget(_lbl("U TOKU", FONT_XS, True, YELLOW))
            for it in in_progress:
                self._add_item_row(it, YELLOW)

        # BLOCKED
        blocked = [it for it in items if it.get("status") == "BLOCKED"]
        if blocked:
            self._content.addWidget(_lbl("BLOKIRANO", FONT_XS, True, RED))
            for it in blocked:
                self._add_item_row(it, RED)

        # IMPLEMENTED — poslednja
        implemented = [it for it in items if it.get("status") in ("IMPLEMENTED", "VERIFIED")]
        if implemented:
            last = implemented[-1]
            self._content.addWidget(_lbl("POSLJEDNJA ZAVRŠENA", FONT_XS, True, PURPLE))
            self._add_item_row(last, PURPLE)

        # SLEDEĆE — najviše 2
        next_items = [it for it in items if it.get("status") == "NOT_STARTED"][:2]
        if next_items:
            self._content.addWidget(_lbl("SLJEDEĆE", FONT_XS, True, TEXT_MUTED))
            for it in next_items:
                self._add_item_row(it, TEXT_MUTED)

        self._content.addSpacing(SPACING_SM)
        btn = QPushButton("Otvori cijeli plan →")
        btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {BORDER}; color: {BLUE}; "
            f"border-radius: {RADIUS_MD}px; padding: {SPACING_SM}px; font-size: {FONT_SM}px; }}"
            f"QPushButton:hover {{ background: {BG_HOVER}; }}"
        )
        btn.clicked.connect(self.open_full_plan_requested.emit)
        self._content.addWidget(btn)
        self._content.addStretch()

    def _add_item_row(self, it: dict, color: str) -> None:
        key = it.get("item_key", "")
        title = it.get("title", "")
        label = f"{key}  {title}" if key else title
        row = _lbl(label, FONT_SM, False, TEXT_PRIMARY)
        self._content.addWidget(row)

    def _clear(self) -> None:
        while self._content.count():
            w = self._content.takeAt(0)
            if w.widget():
                w.widget().deleteLater()
            elif w.layout():
                self._clear_layout(w.layout())

    def _clear_layout(self, lo) -> None:
        while lo.count():
            w = lo.takeAt(0)
            if w.widget():
                w.widget().deleteLater()
            elif w.layout():
                self._clear_layout(w.layout())


# ═══════════════════════════════════════════════════════════════════
# StatusSummaryBar — klikabilni statusni badge elementi
# ═══════════════════════════════════════════════════════════════════


class StatusSummaryBar(QFrame):
    """Horizontalni bar sa statusnim badge-vima."""

    status_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent; border: none;")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(SPACING_SM)
        self._layout.addStretch()
        self.render({})

    def render(self, counts: dict[str, int]) -> None:  # type: ignore[override]
        self._clear_badges()
        order = ["ACCEPTED", "VERIFIED", "IMPLEMENTED", "IN_PROGRESS", "BLOCKED", "NOT_STARTED"]
        labels = {
            "ACCEPTED": "Prihvaćeno", "VERIFIED": "Provjereno",
            "IMPLEMENTED": "Implementirano", "IN_PROGRESS": "U toku",
            "BLOCKED": "Blokirano", "NOT_STARTED": "Nije započeto",
        }
        for status in order:
            c = counts.get(status, 0)
            if c == 0 and status != "NOT_STARTED":
                continue
            color = STATUS_COUNT_COLORS.get(status, GRAY)
            badge = QPushButton(f"{c} {labels.get(status, status)}")
            badge.setStyleSheet(
                f"QPushButton {{ background: transparent; border: 1px solid {color}; "
                f"color: {color}; border-radius: {RADIUS_MD}px; padding: 2px {SPACING_SM}px; "
                f"font-size: {FONT_XS}px; }}"
                f"QPushButton:hover {{ background: {BG_HOVER}; }}"
            )
            badge.clicked.connect(lambda checked, s=status: self.status_selected.emit(s))
            self._layout.insertWidget(self._layout.count() - 1, badge)

    def _clear_badges(self) -> None:
        while self._layout.count() > 1:  # ostavi stretch
            w = self._layout.takeAt(0)
            if w.widget():
                w.widget().deleteLater()
