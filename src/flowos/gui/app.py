"""FlowOS GUI — PySide6 aplikacija (FLOW-106, FLOW-105A/B, FLOW-207/B).

Povezuje View → Controller → GUI Services → Backend API.
"""

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from flowos.gui.controllers.overview import OverviewController
from flowos.gui.services.client import GuiApiClient
from flowos.gui.views.overview_skeleton import MainWindow, RecentActivityWidget, apply_dark_theme
from flowos.gui.views.plan_progress import PlanProgressView
from flowos.gui.views.project_resume import (
    PlanItemDetailsView,
    ProjectResumeView,
    ReconciliationView,
)
from flowos.gui.views.sessions import SessionsView
from flowos.gui.views.worktrees import WorktreesView


class FlowOsGui:
    def __init__(self, use_live: bool = False):
        self._window = MainWindow()
        self._active_project_id: str | None = None

        self._plan_view = PlanProgressView()
        self._sessions_view = SessionsView()
        self._activity_view = RecentActivityWidget()
        self._resume_view = ProjectResumeView()
        self._details_view = PlanItemDetailsView()
        self._reconciliation_view = ReconciliationView()
        self._worktrees_view = WorktreesView()

        self._window.set_central_widgets(  # type: ignore[attr-defined]  # MainWindow mockup
            [self._plan_view, self._sessions_view, self._activity_view]
        )
        self._window.set_right_widgets(  # type: ignore[attr-defined]
            [self._resume_view, self._details_view, self._reconciliation_view]
        )

        if use_live:
            self._setup_live()

    def show(self):
        self._window.show()

    def _setup_live(self):
        api = GuiApiClient(base_url="http://127.0.0.1:9100")
        self._controller = OverviewController(api)

        self._controller.health_updated.connect(self._on_health)
        self._controller.projects_loaded.connect(self._on_projects)
        self._controller.plan_progress_loaded.connect(self._plan_view.render)
        self._controller.resume_loaded.connect(self._on_resume)
        self._controller.sessions_loaded.connect(self._sessions_view.render)
        self._controller.error_occurred.connect(self._on_error)

        self._window.topbar.refresh_requested.connect(lambda: self._controller.check_health())

        QTimer.singleShot(500, self._controller.check_health)
        QTimer.singleShot(800, self._controller.load_projects)

    def _on_health(self, ok: bool, uptime: str):
        pass

    def _on_projects(self, projects: list):
        if projects:
            pid = projects[0].get("id", "")
            if pid:
                self._active_project_id = pid
                self._controller.load_plan_progress(pid)
                self._controller.load_resume(pid)
                self._controller.load_sessions(pid)

    def _on_resume(self, data: dict):
        self._resume_view.render(data)
        # Reconciliation info
        ws_state = data.get("workspace_state", {})
        if ws_state and ws_state.get("reconciliation_status") not in (None, "CURRENT"):
            self._reconciliation_view.render(
                {
                    "new_commits": ws_state.get("external_commits", 0),
                    "dirty_files": ws_state.get("external_dirty", 0),
                    "current_branch": ws_state.get("last_known_branch", ""),
                }
            )
        else:
            self._reconciliation_view.render(None)

    def _on_error(self, msg: str):
        pass


def main():
    live = "--live" in sys.argv
    app = QApplication(sys.argv)
    app.setApplicationName("FlowOS")
    apply_dark_theme(app)

    gui = FlowOsGui(use_live=live)
    gui.show()

    mode = "LIVE (povezan na backend)" if live else "MOCK (bez backend-a)"
    print(f"FlowOS GUI — {mode}")
    if not live:
        print("  Koristi --live za povezivanje sa servisom.")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
