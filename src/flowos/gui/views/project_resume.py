"""ProjectResumeView, PlanItemDetailsView, ReconciliationView, ResumeHeroView (FLOW-105B, 207B)."""

# mypy: disable-error-code="union-attr,unused-ignore"

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from flowos.gui.theme.labels import status_label
from flowos.gui.views.overview_skeleton import (
    BG_CARD,
    BLUE,
    BORDER,
    FONT_LG,
    FONT_MD,
    FONT_SM,
    FONT_XL,
    FONT_XS,
    GREEN,
    PURPLE,
    RADIUS_MD,
    RED,
    SPACING_LG,
    SPACING_MD,
    SPACING_SM,
    SPACING_XL,
    SPACING_XS,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    YELLOW,
    _lbl,
    _sec,
)

# ═══════════════════════════════════════════════════════════════════
# ResumeHeroView — "Gdje si stao" hero komponenta
# ═══════════════════════════════════════════════════════════════════


class ResumeHeroView(QFrame):
    """Hero komponenta na vrhu Pregleda — odgovara na 3 pitanja:
    Šta trenutno radi? Gdje je stao? Šta je sljedeći korak?"""

    continue_requested = Signal()
    report_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;"
        )
        self._content = QVBoxLayout(self)
        self._content.setContentsMargins(SPACING_XL, SPACING_LG, SPACING_XL, SPACING_LG)
        self._content.setSpacing(SPACING_SM)
        self.render(None)

    def _clear(self) -> None:
        while self._content.count():
            it = self._content.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
            elif it.layout():
                self._clear_layout(it.layout())

    def _clear_layout(self, lo) -> None:
        while lo.count():
            it = lo.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
            elif it.layout():
                self._clear_layout(it.layout())

    def render(self, data: dict | None) -> None:  # type: ignore[override]
        self._clear()
        if not data or data.get("status") == "NO_HISTORY":
            self._render_empty(data)
            return

        header = QHBoxLayout()
        header.addWidget(_lbl("GDJE SI STAO", FONT_LG, True))
        header.addStretch()
        self._content.addLayout(header)

        # Aktivna stavka
        item_key = data.get("plan_item_key", "")
        item_title = data.get("plan_item_title", "")
        if item_key or item_title:
            line = f"{item_key} — {item_title}" if item_key else item_title
            self._content.addWidget(_lbl(line, FONT_XL, True, TEXT_PRIMARY))

        # Meta linija: agent · sesija · posljednja aktivnost
        meta_parts = []
        agent = data.get("agent_type", "") or data.get("owner_session_id", "")
        if agent:
            meta_parts.append(agent)
        last = data.get("last_activity", "") or data.get("last_activity_at", "")
        if last:
            meta_parts.append(last)
        if meta_parts:
            self._content.addWidget(_lbl(" · ".join(meta_parts), FONT_SM, False, TEXT_SECONDARY))

        # Status
        ist = data.get("plan_item_status", "")
        if ist:
            self._content.addWidget(_lbl(status_label(ist), FONT_SM, True, PURPLE))

        self._content.addSpacing(SPACING_MD)

        # Gdje je stao
        where = data.get("where_stopped", "")
        if where:
            self._content.addWidget(_sec("Gdje je rad stao"))
            w = _lbl(where, FONT_SM, False, TEXT_SECONDARY)
            w.setWordWrap(True)
            self._content.addWidget(w)

        # Sljedeći korak
        ns_text = data.get("next_step", "") or data.get("next_concrete_step", "")
        if ns_text:
            self._content.addWidget(_sec("Sljedeći konkretan korak"))
            ns = _lbl(ns_text, FONT_MD, True, TEXT_PRIMARY)
            ns.setWordWrap(True)
            self._content.addWidget(ns)

        # Preconditions
        prec = data.get("preconditions", "") or data.get("resume_preconditions", "")
        if prec:
            self._content.addWidget(_sec("Prije nastavka provjeriti"))
            pc = _lbl(prec, FONT_SM, False, TEXT_SECONDARY)
            pc.setWordWrap(True)
            self._content.addWidget(pc)

        # Confidence + dugme
        footer = QHBoxLayout()
        confidence = data.get("confidence", "LOW")
        conf_colors = {"HIGH": GREEN, "MEDIUM": YELLOW, "LOW": RED}
        conf_labels = {"HIGH": "Visoka", "MEDIUM": "Srednja", "LOW": "Niska"}
        footer.addWidget(_lbl("Pouzdanost:", FONT_XS, False, TEXT_MUTED))
        footer.addWidget(
            _lbl(
                conf_labels.get(confidence, confidence),
                FONT_SM,
                True,
                conf_colors.get(confidence, YELLOW),
            )
        )
        footer.addStretch()
        continue_btn = QPushButton("Nastavi rad →")
        continue_btn.setStyleSheet(
            f"QPushButton {{ background: {BLUE}; color: #000; border: none; border-radius: {RADIUS_MD}px; "
            f"padding: {SPACING_SM}px {SPACING_LG}px; font-size: {FONT_SM}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: #7AA2F7; }}"
        )
        continue_btn.clicked.connect(self.continue_requested.emit)
        footer.addWidget(continue_btn)
        self._content.addLayout(footer)

    def _render_empty(self, data: dict | None) -> None:
        header = QHBoxLayout()
        header.addWidget(_lbl("GDJE SI STAO", FONT_LG, True))
        header.addStretch()
        self._content.addLayout(header)

        sessions_count = (data or {}).get("active_sessions", 0)
        last_activity = (data or {}).get("last_activity_at", "")

        self._content.addWidget(
            _lbl("Još nema završene sesije za ovaj projekat.", FONT_MD, False, TEXT_SECONDARY)
        )

        if sessions_count > 0:
            self._content.addWidget(
                _lbl(f"Aktivne sesije: {sessions_count}", FONT_SM, False, GREEN)
            )
        if last_activity:
            self._content.addWidget(
                _lbl(f"Posljednja aktivnost: {last_activity}", FONT_XS, False, TEXT_MUTED)
            )
        self._content.addWidget(
            _lbl("Sažetak će biti kreiran nakon završetka sesije.", FONT_XS, False, TEXT_MUTED)
        )


# ═══════════════════════════════════════════════════════════════════
# ProjectResumeView
# ═══════════════════════════════════════════════════════════════════


class ProjectResumeView(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._content = None
        self._setup_ui()
        self.render(None)

    def _setup_ui(self):
        self.setStyleSheet(
            f"background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;"
        )
        self._content = QVBoxLayout(self)
        self._content.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL)
        self._content.setSpacing(SPACING_MD)
        self._content.addWidget(_lbl("GDJE SI STAO", FONT_LG, True))

    def _clear(self):
        while self._content.count() > 1:  # type: ignore[union-attr]
            it = self._content.takeAt(1)  # type: ignore[union-attr]
            if it.widget():
                it.widget().deleteLater()
            elif it.layout():
                self._clear_layout(it.layout())

    def _clear_layout(self, lo):
        while lo.count():
            it = lo.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
            elif it.layout():
                self._clear_layout(it.layout())

    def render(self, data):  # type: ignore[override]
        self._clear()
        if not data or data.get("status") == "NO_HISTORY":
            self._content.addWidget(_lbl("Nema prethodne istorije.", FONT_SM, False, TEXT_MUTED))  # type: ignore[union-attr]
            self._content.addStretch()  # type: ignore[union-attr]
            return
        item_key = data.get("plan_item_key", "")
        item_title = data.get("plan_item_title", "")
        if item_key or item_title:
            self._content.addWidget(  # type: ignore[union-attr]
                _lbl(f"{item_key} — {item_title}" if item_key else item_title, FONT_MD, True)
            )
        ist = data.get("plan_item_status", "")
        if ist:
            self._content.addWidget(_lbl(status_label(ist), FONT_SM, True, PURPLE))  # type: ignore[union-attr]
        where = data.get("where_stopped", "")
        if where:
            self._content.addWidget(_sec("Gdje je rad stao"))  # type: ignore[union-attr]
            w = _lbl(where, FONT_SM, False, TEXT_SECONDARY)
            w.setWordWrap(True)
            self._content.addWidget(w)  # type: ignore[union-attr]
        ns_text = data.get("next_step", "")
        if ns_text:
            self._content.addWidget(_sec("Sljedeci konkretan korak"))  # type: ignore[union-attr]
            ns = _lbl(ns_text, FONT_SM, True, TEXT_PRIMARY)
            ns.setWordWrap(True)
            self._content.addWidget(ns)  # type: ignore[union-attr]
        prec = data.get("preconditions", "")
        if prec:
            self._content.addWidget(_sec("Prije nastavka provjeriti"))  # type: ignore[union-attr]
            pc = _lbl(prec, FONT_SM, False, TEXT_SECONDARY)
            pc.setWordWrap(True)
            self._content.addWidget(pc)  # type: ignore[union-attr]
        confidence = data.get("confidence", "LOW")
        conf_colors = {"HIGH": GREEN, "MEDIUM": YELLOW, "LOW": RED}
        conf_labels = {"HIGH": "Visoka", "MEDIUM": "Srednja", "LOW": "Niska"}
        cr = QHBoxLayout()
        cr.addWidget(_lbl("Pouzdanost:", FONT_XS, False, TEXT_MUTED))
        cr.addWidget(
            _lbl(
                conf_labels.get(confidence, confidence),
                FONT_SM,
                True,
                conf_colors.get(confidence, YELLOW),
            )
        )
        cr.addStretch()
        self._content.addLayout(cr)  # type: ignore[union-attr]
        self._content.addStretch()  # type: ignore[union-attr]


class PlanItemDetailsView(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._content = None
        self._setup_ui()
        self.render(None)

    def _setup_ui(self):
        self.setStyleSheet(
            f"background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;"
        )
        self._content = QVBoxLayout(self)
        self._content.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL)
        self._content.setSpacing(SPACING_MD)
        self._content.addWidget(_lbl("DETALJI STAVKE PLANA", FONT_LG, True))

    def _clear(self):
        while self._content.count() > 1:  # type: ignore[union-attr]
            it = self._content.takeAt(1)  # type: ignore[union-attr]
            if it.widget():
                it.widget().deleteLater()

    def render(self, data):  # type: ignore[override]
        self._clear()
        if not data:
            self._content.addWidget(_lbl("Izaberite stavku plana.", FONT_SM, False, TEXT_MUTED))  # type: ignore[union-attr]
            self._content.addStretch()  # type: ignore[union-attr]
            return
        criteria = data.get("criteria", [])
        for c in criteria:
            st = c.get("status", "PENDING")
            symbols = {"PASSED": "✓", "FAILED": "✗", "IN_PROGRESS": "◐", "PENDING": "○"}
            colors = {"PASSED": GREEN, "FAILED": RED, "IN_PROGRESS": YELLOW, "PENDING": TEXT_MUTED}
            rl = QHBoxLayout()
            cl = QLabel(symbols.get(st, "○"))
            cl.setFont(QFont("Segoe UI", FONT_SM, QFont.Weight.Bold))
            cl.setStyleSheet(f"color:{colors.get(st, TEXT_MUTED)};border:none;")
            cl.setFixedWidth(20)
            rl.addWidget(cl)
            rl.addWidget(_lbl(c.get("description", ""), FONT_SM, False, TEXT_SECONDARY))
            rl.addStretch()
            self._content.addLayout(rl)  # type: ignore[union-attr]
        self._content.addStretch()  # type: ignore[union-attr]


class ReconciliationView(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._content = None
        self._setup_ui()
        self.hide()

    def _setup_ui(self):
        self.setStyleSheet(
            f"background: {BG_CARD}; border: 1px solid {YELLOW}; border-radius: {RADIUS_MD}px; border-left: 4px solid {YELLOW};"
        )
        self._content = QVBoxLayout(self)
        self._content.setContentsMargins(SPACING_XL, SPACING_XL, SPACING_XL, SPACING_XL)
        self._content.setSpacing(SPACING_SM)
        self._content.addWidget(_lbl("⚠ PROMJENE VAN FLOWOS-A", FONT_MD, True, YELLOW))

    def _clear(self):
        while self._content.count() > 1:  # type: ignore[union-attr]
            it = self._content.takeAt(1)  # type: ignore[union-attr]
            if it.widget():
                it.widget().deleteLater()

    def render(self, data):  # type: ignore[override]
        self._clear()
        if not data:
            self.hide()
            return
        self.show()
        self._content.addWidget(  # type: ignore[union-attr]
            _lbl("Projekat je mijenjan van FlowOS-a.", FONT_SM, False, TEXT_SECONDARY)
        )
        nc = data.get("new_commits", 0)
        df = data.get("dirty_files", 0)
        self._content.addWidget(_lbl(f"{nc} nova commita · {df} neupisana fajla", FONT_SM, True))  # type: ignore[union-attr]
        br = data.get("current_branch", "")
        if br:
            self._content.addWidget(_lbl(f"Grana: {br}", FONT_XS, False, TEXT_MUTED))  # type: ignore[union-attr]
        self._content.addWidget(_lbl("Autor nije potvrđen.", FONT_XS, False, RED))  # type: ignore[union-attr]


# ═══════════════════════════════════════════════════════════════════
# AttentionPanel — blokatori i upozorenja
# ═══════════════════════════════════════════════════════════════════


class AttentionPanel(QFrame):
    """Prikazuje stavke koje zahtevaju pažnju: blokirani plan, konflikti, offline."""

    item_activated = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_MD}px;"
        )
        self._content = QVBoxLayout(self)
        self._content.setContentsMargins(SPACING_XL, SPACING_LG, SPACING_XL, SPACING_LG)
        self._content.setSpacing(SPACING_SM)
        self._content.addWidget(_lbl("PAŽNJA", FONT_LG, True))
        self._items = QVBoxLayout()
        self._items.setSpacing(SPACING_XS)
        self._content.addLayout(self._items)
        self._content.addStretch()
        self.render({})

    def render(self, data: dict) -> None:  # type: ignore[override]
        self._clear()
        items = []
        blocked = data.get("blocked_items", 0)
        if blocked > 0:
            items.append((f"{blocked} blokiranih stavki plana", "Plan"))

        offline = data.get("service_offline", False)
        if offline:
            items.append(("Servis nije dostupan", ""))

        conflicts = data.get("conflicts", 0)
        if conflicts > 0:
            items.append((f"{conflicts} otvorenih konflikata", "Konflikti"))

        ext = data.get("external_changes", False)
        if ext:
            items.append(("Vanjske Git promjene", "Konflikti"))

        if not items:
            self._items.addWidget(_lbl("Nema otvorenih blokatora.", FONT_XS, False, GREEN))
            return

        for text, nav_target in items:
            lbl = _lbl(f"• {text}", FONT_SM, False, YELLOW)
            if nav_target:
                lbl.setStyleSheet(
                    f"color: {YELLOW}; border: none; background: transparent; text-decoration: underline;"
                )
                lbl.setCursor(Qt.CursorShape.PointingHandCursor)  # type: ignore[attr-defined]
                lbl.mousePressEvent = (  # type: ignore[assignment]
                    lambda e, t=nav_target, label=text: self.item_activated.emit(t, label)
                )
            self._items.addWidget(lbl)

    def _clear(self) -> None:
        while self._items.count():
            w = self._items.takeAt(0)
            if w.widget():
                w.widget().deleteLater()
