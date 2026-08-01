"""Overview Controller — povezuje Overview View sa GUI Services.

FLOW-106: Prvi vertikalni tok GUI → API → Backend → SQLite → DTO → ViewState.
"""

from PySide6.QtCore import QObject, Signal

from flowos.gui.services.client import GuiApiClient


class OverviewController(QObject):
    """Koordinator za Overview ekran.

    Povezuje View signale sa API pozivima, mapira DTO u ViewState.
    Ne pristupa bazi, Git-u, filesystemu ni subprocessu.
    """

    # Signali ka View-u
    projects_loaded = Signal(list)
    plan_progress_loaded = Signal(dict)
    resume_loaded = Signal(dict)
    health_updated = Signal(bool, str)
    error_occurred = Signal(str)

    def __init__(self, api: GuiApiClient, parent=None):
        super().__init__(parent)
        self._api = api

        # Poveži API signale
        api.health_received.connect(self._on_health)
        api.projects_received.connect(self._on_projects)
        api.project_created.connect(lambda d: self.load_projects())
        api.plan_progress_received.connect(self._on_plan_progress)
        api.resume_received.connect(self._on_resume)
        api.error_occurred.connect(self._on_error)

    # ── Akcije ─────────────────────────────────────────

    def load_projects(self):
        self._api.get_projects()

    def load_plan_progress(self, project_id: str):
        self._api.get_plan_progress(project_id)

    def load_resume(self, project_id: str):
        self._api.get_resume(project_id)

    def check_health(self):
        self._api.check_health()

    def create_project(self, name: str, repo_path: str):
        self._api.create_project(name, repo_path)

    # ── Mapiranje DTO → ViewState ──────────────────────

    @staticmethod
    def _project_to_viewstate(p: dict) -> dict:
        return {
            "id": p.get("id", ""),
            "name": p.get("name", ""),
            "repo_path": p.get("repo_path", ""),
            "status": p.get("status", "ACTIVE"),
            "created_at": p.get("created_at", ""),
        }

    @staticmethod
    def _plan_to_viewstate(data: dict) -> dict:
        plan = data.get("plan")
        if not plan:
            return {"phases": [], "total": 0, "completed": 0, "blocked": 0}
        return {
            "plan_title": plan.get("title", ""),
            "plan_status": plan.get("status", ""),
            "phases": data.get("phases", []),
            "total": data.get("total_items", 0),
            "completed": data.get("completed_items", 0),
            "blocked": data.get("blocked_items", 0),
        }

    @staticmethod
    def _resume_to_viewstate(data: dict) -> dict:
        return {
            "status": data.get("resume_status", "NO_HISTORY"),
            "where_stopped": data.get("where_stopped", ""),
            "next_step": data.get("next_concrete_step", ""),
            "preconditions": data.get("resume_preconditions", ""),
            "confidence": data.get("confidence", "LOW"),
            "last_activity": data.get("last_activity_at", ""),
            "last_commit": data.get("last_commit_sha", ""),
        }

    # ── Interne obrade ─────────────────────────────────

    def _on_health(self, data: dict):
        ok = data.get("status") == "ok"
        uptime = data.get("uptime", 0)
        self.health_updated.emit(ok, f"{uptime:.0f}s")

    def _on_projects(self, data: list):
        viewstate = [self._project_to_viewstate(p) for p in data]
        self.projects_loaded.emit(viewstate)

    def _on_plan_progress(self, data: dict):
        if "error" in data:
            self.error_occurred.emit(data["error"])
            return
        self.plan_progress_loaded.emit(self._plan_to_viewstate(data))

    def _on_resume(self, data: dict):
        if "error" in data:
            self.error_occurred.emit(data["error"])
            return
        self.resume_loaded.emit(self._resume_to_viewstate(data))

    def _on_error(self, code: int, msg: str):
        self.error_occurred.emit(f"[{code}] {msg}")