"""Funkcionalne stranične View komponente za sidebar navigaciju.

Svaka stranica prima podatke iz API-ja kroz render() metod.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from flowos.gui.views.overview_skeleton import (
    BG_CARD,
    BG_PRIMARY,
    BG_SECONDARY,
    BLUE,
    BORDER,
    FONT_MD,
    FONT_SM,
    FONT_XL,
    FONT_XS,
    GREEN,
    RADIUS_MD,
    RED,
    SPACING_LG,
    SPACING_MD,
    SPACING_SM,
    SPACING_XXL,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    YELLOW,
    _lbl,
)


class ProjectsPage(QFrame):
    project_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_PRIMARY};")
        lo = QVBoxLayout(self)
        lo.setContentsMargins(SPACING_XXL, SPACING_XXL, SPACING_XXL, SPACING_XXL)
        lo.setSpacing(SPACING_MD)

        lo.addWidget(_lbl("PROJEKTI", FONT_XL, True))
        self._list = QVBoxLayout()
        self._list.setSpacing(SPACING_SM)
        lo.addLayout(self._list)
        lo.addStretch()
        self.render([])

    def render(self, projects: list) -> None:  # type: ignore[override]
        self._clear()
        if not projects:
            self._list.addWidget(_lbl("Nema projekata.", FONT_MD, False, TEXT_MUTED))
            return
        for p in projects:
            card = QFrame()
            card.setStyleSheet(
                f"background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px; padding: {SPACING_MD}px;"
            )
            cl = QVBoxLayout(card)
            cl.addWidget(_lbl(p.get("name", ""), FONT_MD, True))
            cl.addWidget(_lbl(p.get("repo_path", ""), FONT_XS, False, TEXT_MUTED))
            self._list.addWidget(card)

    def _clear(self) -> None:
        while self._list.count():
            w = self._list.takeAt(0)
            if w.widget():
                w.widget().deleteLater()


class TasksPage(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_PRIMARY};")
        lo = QVBoxLayout(self)
        lo.setContentsMargins(SPACING_XXL, SPACING_XXL, SPACING_XXL, SPACING_XXL)
        lo.setSpacing(SPACING_MD)

        lo.addWidget(_lbl("ZADACI", FONT_XL, True))
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Naziv", "Status", "Prioritet", "Plan stavka"])
        self._tree.setStyleSheet(
            f"QTreeWidget {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px; }}"
            f"QTreeWidget::item {{ padding: {SPACING_SM}px; color: {TEXT_PRIMARY}; }}"
            f"QHeaderView::section {{ background: {BG_SECONDARY}; border: none; border-bottom: 1px solid {BORDER}; padding: {SPACING_SM}px; color: {TEXT_MUTED}; font-weight: bold; }}"
        )
        lo.addWidget(self._tree)
        self.render([])

    def render(self, tasks: list) -> None:  # type: ignore[override]
        self._tree.clear()
        if not tasks:
            return
        for t in tasks:
            QTreeWidgetItem(self._tree, [
                t.get("title", ""), t.get("status", "—"),
                t.get("priority", "—"), t.get("plan_item_id", "—") or "—",
            ])


class AgentsPage(QFrame):
    scan_requested = Signal()
    track_requested = Signal(int, str)  # pid, agent_type

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_PRIMARY};")
        lo = QVBoxLayout(self)
        lo.setContentsMargins(SPACING_XXL, SPACING_XXL, SPACING_XXL, SPACING_XXL)
        lo.setSpacing(SPACING_MD)

        header = QHBoxLayout()
        header.addWidget(_lbl("AGENTI", FONT_XL, True))
        header.addStretch()
        scan_btn = QPushButton("Skeniraj procese")
        scan_btn.setStyleSheet(
            f"QPushButton {{ background: {BLUE}; color: #000; border: none; border-radius: {RADIUS_MD}px; padding: {SPACING_SM}px {SPACING_LG}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: #7AA2F7; }}"
        )
        scan_btn.clicked.connect(self.scan_requested.emit)
        header.addWidget(scan_btn)
        lo.addLayout(header)

        self._list = QVBoxLayout()
        self._list.setSpacing(SPACING_SM)
        lo.addLayout(self._list)
        lo.addStretch()
        self.render({"agents": []})

    def render(self, data: dict) -> None:  # type: ignore[override]
        self._clear()
        agents = data.get("agents", []) if isinstance(data, dict) else []
        total = data.get("total", len(agents)) if isinstance(data, dict) else len(agents)

        if not agents:
            self._list.addWidget(_lbl(
                "Nema pronađenih agenata. Klikni 'Skeniraj procese'.",
                FONT_MD, False, TEXT_MUTED
            ))
            return

        self._list.addWidget(_lbl(f"Pronađeno {total} agentskih procesa:", FONT_SM, False, GREEN))

        for a in agents:
            card = QFrame()
            card.setStyleSheet(
                f"background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px; padding: {SPACING_MD}px;"
            )
            cl = QHBoxLayout(card)
            info = QVBoxLayout()
            info.addWidget(_lbl(a.get("agent_type", "Nepoznat"), FONT_MD, True))
            info.addWidget(_lbl(
                f"PID: {a.get('pid', '')}  |  {a.get('image', '')}",
                FONT_XS, False, TEXT_MUTED
            ))
            title = a.get("title", "")
            if title:
                info.addWidget(_lbl(title, FONT_XS, False, TEXT_SECONDARY))
            cl.addLayout(info)
            cl.addStretch()
            track_btn = QPushButton("Prati")
            track_btn.setStyleSheet(
                f"QPushButton {{ background: {GREEN}; color: #000; border: none; border-radius: {RADIUS_MD}px; "
                f"padding: {SPACING_SM}px {SPACING_LG}px; font-weight: bold; }}"
                f"QPushButton:hover {{ background: #8BD5A1; }}"
            )
            pid = a.get("pid", 0)
            agent_type = a.get("agent_type", "")
            track_btn.clicked.connect(lambda checked, p=pid, t=agent_type: self.track_requested.emit(p, t))
            cl.addWidget(track_btn)
            self._list.addWidget(card)

    def _clear(self) -> None:
        while self._list.count():
            w = self._list.takeAt(0)
            if w.widget():
                w.widget().deleteLater()


class ConflictsPage(QFrame):
    conflict_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_PRIMARY};")
        lo = QVBoxLayout(self)
        lo.setContentsMargins(SPACING_XXL, SPACING_XXL, SPACING_XXL, SPACING_XXL)
        lo.setSpacing(SPACING_MD)

        lo.addWidget(_lbl("KONFLIKTI", FONT_XL, True))
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Tip", "Nivo", "Fajl", "Status", "Detektovan"])
        self._tree.setStyleSheet(
            f"QTreeWidget {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px; }}"
            f"QTreeWidget::item {{ padding: {SPACING_SM}px; color: {TEXT_PRIMARY}; }}"
            f"QHeaderView::section {{ background: {BG_SECONDARY}; border: none; border-bottom: 1px solid {BORDER}; padding: {SPACING_SM}px; color: {TEXT_MUTED}; font-weight: bold; }}"
        )
        self._tree.setColumnWidth(0, 140)
        self._tree.setColumnWidth(1, 80)
        self._tree.setColumnWidth(2, 200)
        self._tree.setColumnWidth(3, 100)
        self._tree.setColumnWidth(4, 160)
        lo.addWidget(self._tree)
        self.render([])

    def render(self, conflicts: list) -> None:  # type: ignore[override]
        self._tree.clear()
        if not conflicts:
            return
        for c in conflicts:
            level = c.get("conflict_level", "")
            color = RED if level == "HIGH" else YELLOW if level == "MEDIUM" else TEXT_MUTED
            row = QTreeWidgetItem(self._tree, [
                c.get("conflict_type", ""), level,
                c.get("file_path", "") or c.get("description", "")[:60],
                c.get("status", ""),
                c.get("detected_at", "")[:19] if c.get("detected_at") else "",
            ])
            row.setForeground(1, color)


class ReportsPage(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_PRIMARY};")
        lo = QVBoxLayout(self)
        lo.setContentsMargins(SPACING_XXL, SPACING_XXL, SPACING_XXL, SPACING_XXL)
        lo.setSpacing(SPACING_MD)

        lo.addWidget(_lbl("IZVJEŠTAJI", FONT_XL, True))
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Sesija", "Sažetak", "Status", "Vrijeme"])
        self._tree.setStyleSheet(
            f"QTreeWidget {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px; }}"
            f"QTreeWidget::item {{ padding: {SPACING_SM}px; color: {TEXT_PRIMARY}; }}"
            f"QHeaderView::section {{ background: {BG_SECONDARY}; border: none; border-bottom: 1px solid {BORDER}; padding: {SPACING_SM}px; color: {TEXT_MUTED}; font-weight: bold; }}"
        )
        self._tree.setColumnWidth(0, 100)
        self._tree.setColumnWidth(1, 300)
        self._tree.setColumnWidth(2, 100)
        self._tree.setColumnWidth(3, 160)
        lo.addWidget(self._tree)
        self.render([])

    def render(self, reports: list) -> None:  # type: ignore[override]
        self._tree.clear()
        if not reports:
            return
        for r in reports:
            QTreeWidgetItem(self._tree, [
                (r.get("session_id", "") or "")[:8] + "...",
                (r.get("summary", "") or "")[:60],
                r.get("verdict", "DRAFT") or "DRAFT",
                r.get("created_at", "")[:19] if r.get("created_at") else "",
            ])


class SettingsPage(QFrame):
    settings_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_PRIMARY};")
        lo = QVBoxLayout(self)
        lo.setContentsMargins(SPACING_XXL, SPACING_XXL, SPACING_XXL, SPACING_XXL)
        lo.setSpacing(SPACING_MD)

        lo.addWidget(_lbl("POSTAVKE", FONT_XL, True))
        lo.addWidget(_lbl("FlowOS v0.1.0", FONT_MD, True))
        lo.addWidget(_lbl("Lokalni lični operativni sistem za agentske sesije.", FONT_SM, False, TEXT_SECONDARY))
        lo.addSpacing(SPACING_LG)
        lo.addWidget(_lbl("Backend: http://127.0.0.1:9100", FONT_SM, False, TEXT_MUTED))
        lo.addWidget(_lbl("Baza: %LOCALAPPDATA%/FlowOS/data/flowos.db", FONT_XS, False, TEXT_MUTED))
        lo.addStretch()
        self.render({})

    def render(self, data: dict) -> None:  # type: ignore[override]
        pass
