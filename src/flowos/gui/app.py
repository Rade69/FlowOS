"""FlowOS GUI — PySide6 aplikacija (FLOW-106, FLOW-105A/B, FLOW-207/B).

Povezuje View → Controller → GUI Services → Backend API.
Automatski pokreće flowos-service.exe ako nije aktivan.
"""

import subprocess
import sys
import time

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
    def __init__(self, use_live: bool = True):
        self._window = MainWindow()
        self._active_project_id: str | None = None
        self._service_process: subprocess.Popen | None = None

        self._plan_view = PlanProgressView()
        self._sessions_view = SessionsView()
        self._activity_view = RecentActivityWidget()
        self._resume_view = ProjectResumeView()
        self._details_view = PlanItemDetailsView()
        self._reconciliation_view = ReconciliationView()
        self._worktrees_view = WorktreesView()

        self._window.set_central_widgets(  # type: ignore[attr-defined]
            [self._plan_view, self._sessions_view, self._activity_view]
        )
        self._window.set_right_widgets(  # type: ignore[attr-defined]
            [self._resume_view, self._details_view, self._reconciliation_view]
        )

        if use_live:
            self._ensure_service_running()
            self._setup_live()

    def show(self):
        self._window.show()

    def _get_service_port(self) -> int:
        """Čita port servisa iz runtime descriptor-a ili koristi default."""
        import json
        import os

        descriptor_path = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
            "FlowOS",
            "runtime",
            "service.json",
        )
        try:
            with open(descriptor_path) as f:
                data = json.load(f)
                port = data.get("port", 9100)
                if isinstance(port, int) and 1024 <= port <= 65535:
                    return port
        except Exception:
            pass
        return 9100

    def _ensure_service_running(self):
        """Proverava da li servis radi; ako ne — pokreće ga."""
        import httpx

        port = self._get_service_port()

        try:
            resp = httpx.get(f"http://127.0.0.1:{port}/health", timeout=2)
            if resp.status_code == 200:
                return  # Servis već radi
        except Exception:
            pass

        # Servis nije dostupan — pokreni ga
        service_exe = "flowos-service.exe"
        try:
            self._service_process = subprocess.Popen(
                [service_exe],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Sačekaj da servis postane dostupan (max 10s)
            for _ in range(20):
                try:
                    resp = httpx.get(f"http://127.0.0.1:{port}/health", timeout=1)
                    if resp.status_code == 200:
                        return
                except Exception:
                    time.sleep(0.5)
        except FileNotFoundError:
            print("flowos-service.exe nije pronađen — pokrenite servis ručno.")
        except Exception:
            pass

    def _setup_live(self):
        port = self._get_service_port()
        api = GuiApiClient(base_url=f"http://127.0.0.1:{port}")
        self._controller = OverviewController(api)

        self._controller.health_updated.connect(self._on_health)
        self._controller.projects_loaded.connect(self._on_projects)
        self._controller.plan_progress_loaded.connect(self._plan_view.render)
        self._controller.resume_loaded.connect(self._on_resume)
        self._controller.sessions_loaded.connect(self._sessions_view.render)
        self._controller.error_occurred.connect(self._on_error)

        # Worktrees: poveži API signale sa View-om
        api.worktrees_received.connect(self._worktrees_view.render)
        self._worktrees_view.refresh_requested.connect(
            lambda: api.fetch_worktrees(self._active_project_id or "")
        )
        self._worktrees_view.integrate_requested.connect(lambda wid: api.prepare_integration(wid))
        self._worktrees_view.cleanup_requested.connect(lambda wid: api.cleanup_worktree(wid))

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
