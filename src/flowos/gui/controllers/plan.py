"""Controller za korisnički izabran Markdown plan i osvježavanje plan prikaza."""

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from flowos.gui.services.client import GuiApiClient


class PlanController(QObject):
    """Čita izabrani plan i delegira HTTP operaciju javnom API klijentu."""

    import_succeeded = Signal(object)
    import_failed = Signal(str)

    def __init__(self, api: GuiApiClient, parent=None):
        super().__init__(parent)
        self._api = api

    def import_plan(self, project_id: str, file_path: str, generation: int = 0) -> None:
        try:
            markdown_text = Path(file_path).read_text(encoding="utf-8")
        except OSError as exc:
            self.import_failed.emit(str(exc))
            return

        def _on_success(data: dict) -> None:
            if "error" in data:
                self.import_failed.emit(str(data["error"]))
                return
            self._api.get_plan_progress(project_id, generation)
            self.import_succeeded.emit(data)

        self._api.import_plan(project_id, markdown_text, _on_success)
