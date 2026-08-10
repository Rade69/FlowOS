"""SessionsView — prikaz aktivnih sesija (FLOW-207).

Zamenjuje placeholder ActiveSessionsWidget. Prima DTO podatke kroz render().
Prikazuje: sesija ID, agent tip, plan stavku, granu/worktree, status.
"""

from PySide6.QtCore import Signal
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
    YELLOW,
    _lbl,
)


class SessionsView(QFrame):
    """Prikaz aktivnih sesija sa podacima iz API-ja."""

    session_selected = Signal(str)

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
        self._tree.setHeaderLabels(["Agent", "Plan stavka", "Radno stablo", "Trajanje", "Posljednja aktivnost", "Status"])
        self._tree.setRootIsDecorated(False)
        self._tree.setStyleSheet(
            f"QTreeWidget {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px; }}"
            f"QTreeWidget::item {{ padding: {SPACING_SM}px; color: {TEXT_PRIMARY}; }}"
            f"QHeaderView::section {{ background: {BG_SECONDARY}; border: none; border-bottom: 1px solid {BORDER}; padding: {SPACING_SM}px; color: {TEXT_MUTED}; font-weight: bold; }}"
        )
        self._tree.setColumnWidth(0, 100)
        self._tree.setColumnWidth(1, 140)
        self._tree.setColumnWidth(2, 180)
        self._tree.setColumnWidth(3, 80)
        self._tree.setColumnWidth(4, 120)
        self._tree.setColumnWidth(5, 80)
        lo.addWidget(self._tree)

    def render(self, sessions: list):  # type: ignore[override]
        self._tree.clear()  # type: ignore[union-attr]
        count = len(sessions)
        self._title_label.setText(f"AKTIVNE SESIJE ({count})")  # type: ignore[union-attr]

        if not sessions:
            from flowos.gui.views.overview_skeleton import TEXT_MUTED
            self._tree.setHeaderLabels(["Nema aktivnih sesija"])
            empty = QTreeWidgetItem(["— agenti koji trenutno rade će se pojaviti ovdje —"])
            empty.setForeground(0, QColor(TEXT_MUTED))
            self._tree.addTopLevelItem(empty)
            self._tree.setMaximumHeight(60)
            return

        self._tree.setMaximumHeight(min(30 + count * 36, 200))  # type: ignore[union-attr]
        for s in sessions:
            agent = s.get("agent_type", "")
            plan = s.get("plan_item_id") or "—"
            worktree = s.get("worktree_path") or s.get("branch_name") or "—"
            if len(worktree) > 40:
                worktree = "..." + worktree[-37:]

            # Trajanje
            started = s.get("started_at", "")
            duration = ""
            if started:
                try:
                    from datetime import UTC, datetime
                    dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                    delta = datetime.now(tz=UTC) - dt
                    mins = int(delta.total_seconds() / 60)
                    if mins < 60:
                        duration = f"{mins}m"
                    elif mins < 1440:
                        duration = f"{mins // 60}h {mins % 60}m"
                    else:
                        duration = f"{mins // 1440}d"
                except Exception:
                    pass

            last_activity = s.get("last_activity_at", "")
            if last_activity:
                try:
                    from datetime import UTC, datetime
                    dt = datetime.fromisoformat(str(last_activity).replace("Z", "+00:00"))
                    delta = datetime.now(tz=UTC) - dt
                    mins = int(delta.total_seconds() / 60)
                    if mins < 1:
                        last_activity = "upravo"
                    elif mins < 60:
                        last_activity = f"prije {mins}m"
                    elif mins < 1440:
                        last_activity = f"prije {mins // 60}h"
                    else:
                        last_activity = f"prije {mins // 1440}d"
                except Exception:
                    pass

            status = s.get("status", "")
            status_color = GREEN if status == "ACTIVE" else YELLOW

            row = QTreeWidgetItem(
                self._tree,  # type: ignore[arg-type]
                [agent, plan, worktree, duration, last_activity, status],
            )
            row.setForeground(5, QColor(status_color))
            row.setToolTip(0, f"ID: {s.get('id', '')}")
            row.setData(0, 32, s.get("id", ""))
