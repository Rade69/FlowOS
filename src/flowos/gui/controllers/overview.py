"""Overview Controller — povezuje Overview View sa GUI Services.

Podržava: projekte, plan progress, resume, sesije, health.
Mapira DTO u ViewState. Ne pristupa bazi/Git-u/subprocessu.
"""

# mypy: disable-error-code="unreachable"

from PySide6.QtCore import QObject, Signal

from flowos.gui.services.client import GuiApiClient
from flowos.gui.theme.labels import status_label


class OverviewController(QObject):
    projects_loaded = Signal(list)
    # FLOW-1201: project-scoped signali nose (project_id, generation, dto) da
    # GUI sloj može odbaciti zakašnjele odgovore (stari generation ili drugi projekat).
    plan_progress_loaded = Signal(object)
    resume_loaded = Signal(object)
    sessions_loaded = Signal(object)
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

    def load_plan_progress(self, pid: str, generation: int = 0):
        self._api.get_plan_progress(pid, generation)

    def load_resume(self, pid: str, generation: int = 0):
        self._api.get_resume(pid, generation)

    def load_sessions(self, pid: str, generation: int = 0):
        self._api.get_active_sessions(pid, generation)

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

    def _on_plan_progress(self, data):
        project_id, generation, payload = data
        if "error" in payload:
            self.error_occurred.emit(payload["error"])
            return
        plan = payload.get("plan")
        self.plan_progress_loaded.emit(
            (
                project_id,
                generation,
                {
                    "plan_title": plan.get("title", "") if plan else "",
                    "plan_status": plan.get("status", "") if plan else "",
                    "phases": payload.get("phases", []),
                    "total": payload.get("total_items", 0),
                    "completed": payload.get("completed_items", 0),
                    "blocked": payload.get("blocked_items", 0),
                },
            )
        )

    def _on_resume(self, data):
        project_id, generation, payload = data
        if "error" in payload:
            self.error_occurred.emit(payload["error"])
            return
        self.resume_loaded.emit(
            (
                project_id,
                generation,
                {
                    "status": payload.get("resume_status", "NO_HISTORY"),
                    "where_stopped": payload.get("where_stopped", ""),
                    "next_step": payload.get("next_concrete_step", ""),
                    "preconditions": payload.get("resume_preconditions", ""),
                    "confidence": payload.get("confidence", "LOW"),
                    "last_activity": payload.get("last_activity_at", ""),
                    "last_commit": payload.get("last_commit_sha", ""),
                },
            )
        )

    def _on_sessions(self, data):
        project_id, generation, payload = data
        if not isinstance(payload, list):
            self.sessions_loaded.emit((project_id, generation, []))
            return
        self.sessions_loaded.emit(
            (
                project_id,
                generation,
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
                    for s in payload
                ],
            )
        )
