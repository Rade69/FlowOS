"""FLOW-1201 — testovi za izbor projekta, propagaciju contexta i stale-data zaštitu.

Testovi koriste pravi MainWindow/TopBar (qtbot) i spy controller/api/view da
dokažu tok bez realnog backend servisa i bez hardcoded-only asertacija.
"""

import pytest
from PySide6.QtWidgets import QFileDialog, QInputDialog

from flowos.gui.composition_root import FlowOsGui
from flowos.gui.views.overview_skeleton import MainWindow

PROJECT_A = {"id": "a", "name": "Project A", "repo_path": "C:/a", "updated_at": ""}
PROJECT_B = {"id": "b", "name": "Project B", "repo_path": "C:/b", "updated_at": ""}


class SpyView:
    """Minimalan view koji beleži render pozive (i project context za Tasks)."""

    def __init__(self):
        self.renders = []

    def render(self, data):
        self.renders.append(data)

    def set_project_id(self, project_id):
        self.renders.append(("project_id", project_id))


class SpyController:
    def __init__(self):
        self.plan_calls = []
        self.resume_calls = []
        self.sessions_calls = []
        self.projects_calls = 0

    def load_plan_progress(self, pid):
        self.plan_calls.append(pid)

    def load_resume(self, pid):
        self.resume_calls.append(pid)

    def load_sessions(self, pid):
        self.sessions_calls.append(pid)

    def load_projects(self):
        self.projects_calls += 1

    def check_health(self):
        pass


class SpyApi:
    base_url = "http://127.0.0.1:9100"
    token = None

    def __init__(self):
        self.timeline_calls = []
        self.worktrees_calls = []
        self.created = []

    def get_timeline(self, pid):
        self.timeline_calls.append(pid)

    def fetch_worktrees(self, pid):
        self.worktrees_calls.append(pid)

    def create_project(self, name, repo_path):
        self.created.append((name, repo_path))


_VIEW_NAMES = [
    "resume_hero",
    "status_bar",
    "current_phase",
    "sessions_overview",
    "plan_page",
    "reconciliation",
    "sessions_page",
    "worktrees_page",
    "activity",
    "attention",
    "agents_page",
    "conflicts_page",
    "projects_page",
    "tasks_page",
    "details",
]


@pytest.fixture
def gui_env(qtbot, monkeypatch):
    # FLOW-1201 F2: production closeEvent otvara modalni QMessageBox koji bi
    # blokirao pytest-qt teardown (widget.close()). U testu se close
    # confirmation neutrališe — production closeEvent se ne mijenja.
    monkeypatch.setattr(MainWindow, "closeEvent", lambda self, event: event.accept())
    window = MainWindow()
    qtbot.addWidget(window)
    controller = SpyController()
    api = SpyApi()
    views = {name: SpyView() for name in _VIEW_NAMES}
    gui = FlowOsGui(window=window, controller=None, api=None, views=views)
    gui._controller = controller
    gui._api = api
    # Uspostavi stvaran TopBar signal path (isti kod koji _wire_controller poziva u live modu).
    gui._wire_topbar()
    return gui, controller, api, views, window


def test_t1_topbar_shows_active_project(gui_env):
    gui, _controller, _api, _views, window = gui_env
    gui._on_projects([PROJECT_A])
    assert gui._active_project_id == "a"
    assert window.topbar._proj_label.text() == "Project A"
    assert window.topbar._project_combo.currentText() == "Project A"


def test_t2_switch_updates_active_project_id(gui_env):
    gui, _controller, _api, _views, _window = gui_env
    gui._on_projects([PROJECT_A, PROJECT_B])
    assert gui._active_project_id == "a"
    gui._on_project_selected("b")
    assert gui._active_project_id == "b"


def test_t3_switch_propagates_context(gui_env):
    gui, controller, api, views, _window = gui_env
    gui._on_projects([PROJECT_A, PROJECT_B])
    gui._on_project_selected("b")
    assert controller.plan_calls[-1] == "b"
    assert controller.resume_calls[-1] == "b"
    assert controller.sessions_calls[-1] == "b"
    assert api.timeline_calls[-1] == "b"
    assert api.worktrees_calls[-1] == "b"
    assert views["tasks_page"].renders[-1] == ("project_id", "b")


def test_t4_no_stale_data_after_switch(gui_env):
    gui, _controller, _api, views, _window = gui_env
    gui._on_projects([PROJECT_A, PROJECT_B])
    # Simuliraj prethodno prikazane A podatke na Plan ekranu.
    views["plan_page"].render({"plan_title": "A plan"})
    gui._on_project_selected("b")
    # Switch je očistio ekran pre učitavanja B — poslednji render nije A podatak.
    assert views["plan_page"].renders[-1] is None


def test_t5_add_project_uses_backend_contract(gui_env, monkeypatch):
    gui, _controller, api, _views, _window = gui_env
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("Novi", True)))
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "C:/novi")
    )
    gui._on_add_project()
    assert api.created == [("Novi", "C:/novi")]


def test_t6_create_error_does_not_refresh_as_success(gui_env):
    gui, controller, _api, _views, _window = gui_env
    gui._on_project_created({"error": "repo_path mora biti apsolutna putanja"})
    assert controller.projects_calls == 0


def test_t7_create_project_does_not_git_init(tmp_path):
    """Backend create_project ne sme kreirati .git niti pozivati git init."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import flowos.service.services.infrastructure.persistence.models  # noqa: F401
    import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
    import flowos.service.services.infrastructure.persistence.report_models  # noqa: F401
    from flowos.service.services.infrastructure.persistence.base import Base
    from flowos.service.services.projects.service import ProjectService

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    repo = tmp_path / "repo"
    repo.mkdir()
    ProjectService(session).create_project("X", str(repo))
    session.commit()
    assert not (repo / ".git").exists()


def test_t8_no_projects_neutral_state(gui_env):
    gui, _controller, _api, _views, window = gui_env
    gui._on_projects([])
    assert gui._active_project_id is None
    assert window.topbar._proj_label.text() == "Nema izabranog projekta"
    assert window.topbar._project_combo.count() == 0


def test_t9_two_projects_switch_returns_context(gui_env):
    gui, controller, _api, _views, window = gui_env
    gui._on_projects([PROJECT_A, PROJECT_B])
    gui._on_project_selected("b")
    gui._on_project_selected("a")
    assert gui._active_project_id == "a"
    assert controller.plan_calls == ["a", "b", "a"]
    assert window.topbar._proj_label.text() == "Project A"


def test_t10_failure_during_switch_leaves_no_false_consistency(gui_env):
    gui, _controller, _api, views, window = gui_env
    gui._on_projects([PROJECT_A, PROJECT_B])
    views["plan_page"].render({"plan_title": "A plan"})
    gui._on_project_selected("b")
    # TopBar je već na B, ali Plan ekran je očišćen (ne prikazuje A podatke kao B).
    assert window.topbar._proj_label.text() == "Project B"
    assert views["plan_page"].renders[-1] is None


def test_t11_late_response_after_switch_is_ignored(gui_env):
    """FLOW-1201 F1: zakašnjeli A odgovor posle switch-a na B mora biti odbačen.

    Test pada ako se stale-response guard ukloni — tada bi se A podaci
    renderovali na ekranima koji su već prebačeni na B (ili očišćeni).
    """
    gui, _controller, _api, views, _window = gui_env
    gui._on_projects([PROJECT_A, PROJECT_B])
    # Prethodno prikazani A podaci (aktivno stanje A pre switch-a).
    views["plan_page"].render({"plan_title": "A plan"})
    views["sessions_page"].render([{"id": "sA"}])
    views["resume_hero"].render({"status": "A"})
    views["activity"].render([{"id": "actA"}])
    views["worktrees_page"].render([{"id": "wtA"}])
    gui._on_project_selected("b")

    # Zakašnjeli A odgovori stižu tek sada, kad je aktivan B.
    gui._on_plan_progress(("a", {"phases": [], "plan_title": "A plan", "blocked": 0}))
    gui._on_sessions(("a", [{"id": "sA"}]))
    gui._on_resume(("a", {"status": "A", "workspace_state": {}}))
    gui._on_timeline(("a", [{"id": "actA"}]))
    gui._on_worktrees(("a", [{"id": "wtA"}]))

    # Svi ekrani ostaju u očišćenom stanju — A se ne renderuje pod B.
    assert views["plan_page"].renders[-1] is None
    assert views["sessions_page"].renders[-1] == []
    assert views["resume_hero"].renders[-1] is None
    assert views["activity"].renders[-1] == []
    assert views["worktrees_page"].renders[-1] == []


def test_t12_combo_signal_wiring_changes_active_project(gui_env):
    """FLOW-1201 F3: stvaran Qt signal path (QComboBox) menja aktivan projekat.

    Test pada ako se ukloni `topbar.project_selected.connect(self._on_project_selected)`.
    """
    gui, controller, _api, _views, window = gui_env
    gui._on_projects([PROJECT_A, PROJECT_B])
    assert gui._active_project_id == "a"

    # Stvarni Qt tok: currentIndexChanged → _on_combo_changed → project_selected.emit.
    window.topbar._project_combo.setCurrentIndex(1)  # Project B

    assert gui._active_project_id == "b"
    assert window.topbar._proj_label.text() == "Project B"
    assert controller.plan_calls[-1] == "b"
