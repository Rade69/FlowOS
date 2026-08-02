"""Testovi za centralne mape prevoda."""

from flowos.gui.theme.labels import (
    OTHER_LABELS,
    status_label,
    ui_label,
)


class TestTranslations:
    def test_implemented_is_translated(self):
        assert status_label("IMPLEMENTED") == "Implementirano"

    def test_verified_is_translated(self):
        assert status_label("VERIFIED") == "Provjereno"

    def test_accepted_is_translated(self):
        assert status_label("ACCEPTED") == "Prihvaćeno"

    def test_needs_review_is_translated(self):
        assert status_label("NEEDS_REVIEW") == "Potreban pregled"

    def test_active_is_translated(self):
        assert status_label("ACTIVE") == "Aktivna"

    def test_not_started_is_translated(self):
        assert status_label("NOT_STARTED") == "Nije započeto"

    def test_in_progress_is_translated(self):
        assert status_label("IN_PROGRESS") == "U toku"

    def test_blocked_is_translated(self):
        assert status_label("BLOCKED") == "Blokirano"

    def test_rejected_is_translated(self):
        assert status_label("REJECTED") == "Odbijeno"

    def test_completed_is_translated(self):
        assert status_label("COMPLETED") == "Završena"

    def test_unknown_status_returns_original(self):
        assert status_label("NEPOZNATO") == "NEPOZNATO"

    def test_ui_labels_contain_key_terms(self):
        assert ui_label("overview") == "Pregled"
        assert ui_label("worktrees") == "Radna stabla"
        assert ui_label("reconciliation") == "Usklađivanje stanja"

    def test_other_labels(self):
        assert OTHER_LABELS["watcher"] == "Posmatrač"
        assert OTHER_LABELS["where_stopped"] == "Gdje si stao"
        assert OTHER_LABELS["confidence"] == "Pouzdanost"
