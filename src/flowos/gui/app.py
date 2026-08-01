"""FlowOS GUI — PySide6 aplikacija (FLOW-106).

Pokreće MainWindow, povezuje View → Controller → GUI Services → Backend API.
Prvi vertikalni tok: GUI ↔ FastAPI ↔ SQLite.

Pokreni: python -m flowos.gui.app [--live]
"""

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from flowos.gui.controllers.overview import OverviewController
from flowos.gui.services.client import GuiApiClient
from flowos.gui.views.overview_skeleton import MainWindow, apply_dark_theme


class FlowOsGui:
    """Kompozicioni koren GUI-ja — povezuje sve slojeve."""

    def __init__(self, use_live: bool = False):
        self._window = MainWindow()
        self._use_live = use_live

        if use_live:
            self._setup_live()

    def show(self):
        self._window.show()

    def _setup_live(self):
        """Povezuje Controller sa API-jem i View-om."""
        api = GuiApiClient(base_url="http://127.0.0.1:9100")
        self._controller = OverviewController(api)

        self._controller.health_updated.connect(self._on_health)
        self._controller.projects_loaded.connect(self._on_projects)
        self._controller.plan_progress_loaded.connect(self._on_plan)
        self._controller.resume_loaded.connect(self._on_resume)
        self._controller.error_occurred.connect(self._on_error)

        self._window.topbar.refresh_requested.connect(lambda: self._controller.check_health())

        QTimer.singleShot(500, self._controller.check_health)
        QTimer.singleShot(800, self._controller.load_projects)

    def _on_health(self, ok: bool, uptime: str):
        print(f"GUI: Health {'OK' if ok else 'FAIL'} ({uptime})")

    def _on_projects(self, projects: list):
        print(f"GUI: {len(projects)} projekata učitano")

    def _on_plan(self, data: dict):
        print(f"GUI: Plan — {data.get('total', 0)} stavki")

    def _on_resume(self, data: dict):
        print(f"GUI: Resume — {data.get('status', '?')}: {data.get('where_stopped', '')[:60]}")

    def _on_error(self, msg: str):
        print(f"GUI: Greška — {msg}")


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
