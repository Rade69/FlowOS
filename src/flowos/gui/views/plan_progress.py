"""PlanProgressView — prikaz napretka po planu (FLOW-105A)."""

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout

from flowos.gui.theme.labels import status_label
from flowos.gui.views.overview_skeleton import (
    BG_CARD,
    BG_HOVER,
    BG_SECONDARY,
    BORDER,
    FONT_LG,
    FONT_MD,
    FONT_SM,
    GRAY,
    GREEN,
    PURPLE,
    RADIUS_MD,
    SPACING_LG,
    SPACING_MD,
    SPACING_SM,
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
    "NOT_STARTED": GRAY,
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
        h = QHBoxLayout()
        lo.addWidget(_lbl("NAPREDAK PO PLANU", FONT_LG, True))
        lo.addLayout(h)
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

    def render(self, data):
        self._plan_label.setText(
            "Nema aktivnog plana" if not data else f"Aktivni plan: {data.get('plan_title', '')}"
        )
        self._clear_status()
        self._tree.clear()
        if not data:
            return
        phases = data.get("phases", [])
        counts = {}
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
                self._status_row.addWidget(lbl)
        self._status_row.addStretch()
        for ph in phases:
            pi = QTreeWidgetItem(
                self._tree, [ph.get("title", ph.get("phase_key", "")), "", "", "", ""]
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
