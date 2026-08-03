"""WorktreesView — prikaz Git worktree-ja (FLOW-404).

Prikazuje: putanju, granu, commit, status, sesiju, akcije.
"""

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout

from flowos.gui.views.overview_skeleton import (
    BG_CARD,
    BG_SECONDARY,
    BORDER,
    FONT_LG,
    GREEN,
    RADIUS_MD,
    RED,
    SPACING_SM,
    TEAL,
    TEXT_MUTED,
    TEXT_PRIMARY,
    YELLOW,
    _lbl,
)

STATUS_COLORS = {
    "ACTIVE": GREEN,
    "READY": TEAL,
    "INTEGRATED": TEXT_MUTED,
    "ABANDONED": YELLOW,
    "CLEANED": TEXT_MUTED,
    "CLEAN": GREEN,
    "DIRTY": YELLOW,
    "CONFLICT": RED,
}


class WorktreesView(QFrame):
    """Prikaz worktree-ja sa akcijama."""

    refresh_requested = Signal()
    integrate_requested = Signal(str)
    cleanup_requested = Signal(str)

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

        self._title_label = _lbl("RADNA STABLA (0)", FONT_LG, True)
        lo.addWidget(self._title_label)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(
            [
                "Putanja",
                "Grana",
                "Commit",
                "Status",
                "Sesija",
                "",
            ]
        )
        self._tree.setRootIsDecorated(False)
        self._tree.setStyleSheet(
            f"QTreeWidget {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px; }}"
            f"QTreeWidget::item {{ padding: {SPACING_SM}px; color: {TEXT_PRIMARY}; }}"
            f"QHeaderView::section {{ background: {BG_SECONDARY}; border: none; border-bottom: 1px solid {BORDER}; padding: {SPACING_SM}px; color: {TEXT_MUTED}; font-weight: bold; }}"
        )
        self._tree.setColumnWidth(0, 240)
        self._tree.setColumnWidth(1, 140)
        self._tree.setColumnWidth(2, 80)
        self._tree.setColumnWidth(3, 80)
        self._tree.setColumnWidth(4, 100)
        self._tree.setColumnWidth(5, 160)
        lo.addWidget(self._tree)

    def render(self, worktrees: list):  # type: ignore[override]
        self._tree.clear()  # type: ignore[union-attr]
        count = len(worktrees)
        self._title_label.setText(f"RADNA STABLA ({count})")  # type: ignore[union-attr]

        if not worktrees:
            return

        for wt in worktrees:
            path = wt.get("path", "") or wt.get("worktree_path", "")
            branch = wt.get("branch", "") or wt.get("branch_name", "")
            commit = (wt.get("commit_sha", "") or "")[:8]
            status = wt.get("status", "") or wt.get("db_status", "") or "—"
            session_id = (
                (wt.get("session_id", "") or "")[:8] + "..." if wt.get("session_id") else "—"
            )

            row = QTreeWidgetItem(self._tree, [path, branch, commit, status, session_id, ""])  # type: ignore[arg-type]

            color = STATUS_COLORS.get(status, TEXT_PRIMARY)
            row.setForeground(3, QColor(color))

            # Akcioni dugmići u poslednjoj koloni
            wt_id = wt.get("id", "")
            if wt_id:
                btn_container = QFrame()
                btn_lo = QVBoxLayout(btn_container)
                btn_lo.setContentsMargins(0, 0, 0, 0)
                btn_lo.setSpacing(2)

                if status in ("ACTIVE", "READY"):
                    integrate_btn = QPushButton("Pregledaj izmjene")
                    integrate_btn.setStyleSheet(
                        f"background: {TEAL}; color: #000; border-radius: 3px; padding: 2px 8px; font-size: 10px;"
                    )
                    integrate_btn.clicked.connect(
                        lambda checked=False, wid=wt_id: self.integrate_requested.emit(wid)
                    )
                    btn_lo.addWidget(integrate_btn)

                if status in ("ABANDONED", "INTEGRATED", "READY"):
                    cleanup_btn = QPushButton("Cleanup")
                    cleanup_btn.setStyleSheet(
                        f"background: {RED}; color: #fff; border-radius: 3px; padding: 2px 8px; font-size: 10px;"
                    )
                    cleanup_btn.clicked.connect(
                        lambda checked=False, wid=wt_id: self.cleanup_requested.emit(wid)
                    )
                    btn_lo.addWidget(cleanup_btn)

                self._tree.setItemWidget(row, 5, btn_container)  # type: ignore[union-attr]
