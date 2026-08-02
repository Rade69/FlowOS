"""ProjectResumeView, PlanItemDetailsView, ReconciliationView (FLOW-105B, 207B)."""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from flowos.gui.theme.labels import status_label
from flowos.gui.views.overview_skeleton import (
    BG_CARD,
    BORDER,
    FONT_LG,
    FONT_MD,
    FONT_SM,
    FONT_XS,
    GREEN,
    PURPLE,
    RADIUS_MD,
    RED,
    SPACING_MD,
    SPACING_SM,
    SPACING_XL,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    YELLOW,
    _lbl,
    _sec,
)


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
        while self._content.count() > 1:
            it = self._content.takeAt(1)
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

    def render(self, data):
        self._clear()
        if not data or data.get("status") == "NO_HISTORY":
            self._content.addWidget(_lbl("Nema prethodne istorije.", FONT_SM, False, TEXT_MUTED))
            self._content.addStretch()
            return
        item_key = data.get("plan_item_key", "")
        item_title = data.get("plan_item_title", "")
        if item_key or item_title:
            self._content.addWidget(
                _lbl(f"{item_key} — {item_title}" if item_key else item_title, FONT_MD, True)
            )
        ist = data.get("plan_item_status", "")
        if ist:
            self._content.addWidget(_lbl(status_label(ist), FONT_SM, True, PURPLE))
        where = data.get("where_stopped", "")
        if where:
            self._content.addWidget(_sec("Gdje je rad stao"))
            w = _lbl(where, FONT_SM, False, TEXT_SECONDARY)
            w.setWordWrap(True)
            self._content.addWidget(w)
        ns_text = data.get("next_step", "")
        if ns_text:
            self._content.addWidget(_sec("Sljedeci konkretan korak"))
            ns = _lbl(ns_text, FONT_SM, True, TEXT_PRIMARY)
            ns.setWordWrap(True)
            self._content.addWidget(ns)
        prec = data.get("preconditions", "")
        if prec:
            self._content.addWidget(_sec("Prije nastavka provjeriti"))
            pc = _lbl(prec, FONT_SM, False, TEXT_SECONDARY)
            pc.setWordWrap(True)
            self._content.addWidget(pc)
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
        self._content.addLayout(cr)
        self._content.addStretch()


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
        while self._content.count() > 1:
            it = self._content.takeAt(1)
            if it.widget():
                it.widget().deleteLater()

    def render(self, data):
        self._clear()
        if not data:
            self._content.addWidget(_lbl("Izaberite stavku plana.", FONT_SM, False, TEXT_MUTED))
            self._content.addStretch()
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
            self._content.addLayout(rl)
        self._content.addStretch()


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
        while self._content.count() > 1:
            it = self._content.takeAt(1)
            if it.widget():
                it.widget().deleteLater()

    def render(self, data):
        self._clear()
        if not data:
            self.hide()
            return
        self.show()
        self._content.addWidget(
            _lbl("Projekat je mijenjan van FlowOS-a.", FONT_SM, False, TEXT_SECONDARY)
        )
        nc = data.get("new_commits", 0)
        df = data.get("dirty_files", 0)
        self._content.addWidget(_lbl(f"{nc} nova commita · {df} neupisana fajla", FONT_SM, True))
        br = data.get("current_branch", "")
        if br:
            self._content.addWidget(_lbl(f"Grana: {br}", FONT_XS, False, TEXT_MUTED))
        self._content.addWidget(_lbl("Autor nije potvrđen.", FONT_XS, False, RED))
