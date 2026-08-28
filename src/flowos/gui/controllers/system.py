"""Controller za GUI shutdown koordinaciju i platform-svjesno otvaranje foldera."""

import os
import subprocess
import sys

from PySide6.QtCore import QObject, Signal

from flowos.gui.services.client import GuiApiClient


class SystemController(QObject):
    """Prevodi sistemske API/OS rezultate u signale koje View wiring prikazuje."""

    shutdown_allowed = Signal()
    shutdown_blocked = Signal(int)
    shutdown_failed = Signal()
    reports_folder_open_failed = Signal(str)

    def __init__(self, api: GuiApiClient, parent=None):
        super().__init__(parent)
        self._api = api

    def request_shutdown(self) -> None:
        self._api.prepare_shutdown(self._on_shutdown_prepared)

    def _on_shutdown_prepared(self, data: dict | None) -> None:
        if data is None:
            self.shutdown_failed.emit()
            return

        active_count = data.get("active_sessions", 0)
        if not isinstance(active_count, int) or isinstance(active_count, bool):
            self.shutdown_failed.emit()
        elif active_count == 0:
            self.shutdown_allowed.emit()
        else:
            self.shutdown_blocked.emit(active_count)

    def open_reports_folder(self, path: str) -> None:
        if not os.path.isdir(path):
            self.reports_folder_open_failed.emit(f"Folder ne postoji: {path}")
            return

        command = (
            "explorer"
            if sys.platform == "win32"
            else "open"
            if sys.platform == "darwin"
            else "xdg-open"
        )
        try:
            subprocess.Popen([command, os.path.abspath(path)])
        except OSError as exc:
            self.reports_folder_open_failed.emit(str(exc))
