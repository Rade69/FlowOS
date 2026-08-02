"""SessionsView — prikaz aktivnih sesija (FLOW-207).

Zamenjuje placeholder ActiveSessionsWidget. Prima DTO podatke kroz render().
Prikazuje: sesija ID, agent tip, plan stavku, granu/worktree, status.
"""

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QTreeWidget, QTreeWidgetItem, QVBoxLayout

from flowos.gui.views.overview_skeleton import (
    BG_CARD,
    BG_SECONDARY,
    BORDER,
    FONT_LG,
    GREEN,
    RADIUS_MD,
    SPACING_SM,
    TEXT_MUTED,
    TEXT_PRIMARY,
    _lbl,
)


class SessionsView(QFrame):
    """Prikaz aktivnih sesija sa podacima iz API-ja."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tree: QTreeWidget | None = None
        self._title_label: QTreeWidget | None = None
        self._setup_ui()
        self.render([])

    def _setup_ui(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(SPACING_SM)

        count = 0
        self._title_label = _lbl(f"AKTIVNE SESIJE ({count})", FONT_LG, True)
        lo.addWidget(self._title_label)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Sesija", "Agent", "Plan stavka", "Grana/Worktree", "Status"])
        self._tree.setRootIsDecorated(False)
        self._tree.setStyleSheet(
            f"QTreeWidget {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px; }}"
            f"QTreeWidget::item {{ padding: {SPACING_SM}px; color: {TEXT_PRIMARY}; }}"
            f"QHeaderView::section {{ background: {BG_SECONDARY}; border: none; border-bottom: 1px solid {BORDER}; padding: {SPACING_SM}px; color: {TEXT_MUTED}; font-weight: bold; }}"
        )
        self._tree.setColumnWidth(0, 100)
        self._tree.setColumnWidth(1, 80)
        self._tree.setColumnWidth(2, 100)
        self._tree.setColumnWidth(3, 160)
        self._tree.setColumnWidth(4, 80)
        lo.addWidget(self._tree)

    def render(self, sessions: list):  # type: ignore[override]  # QWidget.render overload
        """Prima listu sesija iz API-ja i prikazuje ih."""
        self._tree.clear()  # type: ignore[union-attr]
        count = len(sessions)
        self._title_label.setText(f"AKTIVNE SESIJE ({count})")  # type: ignore[union-attr]

        if not sessions:
            return

        self._tree.setMaximumHeight(min(30 + count * 36, 200))  # type: ignore[union-attr]
        for s in sessions:
            sid = s.get("id", "")[:8] + "..."
            agent = s.get("agent_type", "")
            plan = s.get("plan_item_id", "—") or "—"
            if plan != "—" and len(plan) > 8:
                plan = plan[:8] + "..."
            branch = s.get("branch_name", "") or s.get("worktree_path", "") or "—"
            status = s.get("status", "")

            row = QTreeWidgetItem(self._tree, [sid, agent, plan, branch, status])  # type: ignore[arg-type]
            if status == "ACTIVE":
                row.setForeground(4, QColor(GREEN))
