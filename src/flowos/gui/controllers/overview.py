"""Overview Controller — povezuje Overview View sa GUI Services.

Podržava: projekte, plan progress, resume, sesije, health.
Mapira DTO u ViewState. Ne pristupa bazi/Git-u/subprocessu.
"""

from PySide6.QtCore import QObject, Signal

from flowos.gui.services.client import GuiApiClient
from flowos.gui.theme.labels import status_label


class OverviewController(QObject):
    projects_loaded = Signal(list)
    plan_progress_loaded = Signal(dict)
    resume_loaded = Signal(dict)
    sessions_loaded = Signal(list)
    health_updated = Signal(bool, str)
    error_occurred = Signal(str)

    def __init__(self, api: GuiApiClient, parent=None):
        super().__init__(parent)
        self._api = api

        api.health_received.connect(self._on_health)
        api.projects_received.connect(self._on_projects)
        api.plan_progress_received.connect(self._on_plan_progress)
        api.resume_received.connect(self._on_resume)
        api.sessions_received.connect(self._on_sessions)
        api.error_occurred.connect(lambda c, m: self.error_occurred.emit(f"[{c}] {m}"))

    def load_projects(self):
        self._api.get_projects()

    def load_plan_progress(self, pid: str):
        self._api.get_plan_progress(pid)

    def load_resume(self, pid: str):
        self._api.get_resume(pid)

    def load_sessions(self, pid: str):
        self._api.get_active_sessions(pid)

    def check_health(self):
        self._api.check_health()

    def _on_health(self, d: dict):
        ok = d.get("status") == "ok"
        self.health_updated.emit(ok, f"{d.get('uptime', 0):.0f}s")

    def _on_projects(self, data: list):
        self.projects_loaded.emit(
            [
                {
                    "id": p.get("id", ""),
                    "name": p.get("name", ""),
                    "repo_path": p.get("repo_path", ""),
                    "status": p.get("status", "ACTIVE"),
                }
                for p in data
            ]
        )

    def _on_plan_progress(self, data: dict):
        if "error" in data:
            self.error_occurred.emit(data["error"])
            return
        plan = data.get("plan")
        self.plan_progress_loaded.emit(
            {
                "plan_title": plan.get("title", "") if plan else "",
                "plan_status": plan.get("status", "") if plan else "",
                "phases": data.get("phases", []),
                "total": data.get("total_items", 0),
                "completed": data.get("completed_items", 0),
                "blocked": data.get("blocked_items", 0),
            }
        )

    def _on_resume(self, data: dict):
        if "error" in data:
            self.error_occurred.emit(data["error"])
            return
        self.resume_loaded.emit(
            {
                "status": data.get("resume_status", "NO_HISTORY"),
                "where_stopped": data.get("where_stopped", ""),
                "next_step": data.get("next_concrete_step", ""),
                "preconditions": data.get("resume_preconditions", ""),
                "confidence": data.get("confidence", "LOW"),
                "last_activity": data.get("last_activity_at", ""),
                "last_commit": data.get("last_commit_sha", ""),
            }
        )

    def _on_sessions(self, data: list):
        if not isinstance(data, list):
            self.sessions_loaded.emit([])
            return
        self.sessions_loaded.emit(
            [
                {
                    "id": s.get("id", ""),
                    "agent_type": s.get("agent_type", ""),
                    "plan_item_id": s.get("plan_item_id"),
                    "status": status_label(s.get("status", "")),
                    "started_at": s.get("started_at", ""),
                    "last_activity_at": s.get("last_activity_at", ""),
                    "worktree_path": s.get("worktree_path"),
                    "branch_name": s.get("branch_name", ""),
                }
                for s in data
            ]
        )
