"""Controller za validaciju i registraciju ručno praćenih agentskih sesija."""

import os

from PySide6.QtCore import QObject, Signal

from flowos.gui.services.client import GuiApiClient


class AgentsController(QObject):
    """Normalizuje View ulaz i delegira kreiranje EXTERNAL_TRACKED sesije."""

    tracking_requested = Signal()
    tracking_failed = Signal(str)

    def __init__(self, api: GuiApiClient, parent=None):
        super().__init__(parent)
        self._api = api

    def track_agent(self, project_id: str, repo_path: str, pid: int, agent_type: str) -> None:
        normalized_repo_path = repo_path.strip()
        if not normalized_repo_path:
            self.tracking_failed.emit("Nije postavljen repo_path za aktivni projekat")
            return
        if not os.path.isabs(normalized_repo_path):
            self.tracking_failed.emit("repo_path aktivnog projekta mora biti apsolutna putanja")
            return

        normalized_agent_type = "_".join(agent_type.strip().lower().split())
        self._api.create_tracked_session(
            project_id,
            normalized_agent_type,
            normalized_repo_path,
            pid,
        )
        self.tracking_requested.emit()
