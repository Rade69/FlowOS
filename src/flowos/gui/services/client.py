"""GUI API klijent — HTTP komunikacija sa FlowOS backendom.

Koristi QNetworkAccessManager za neblokirajuće HTTP pozive.
Vraća rezultate kroz Qt signale (ne callback hell).
"""

import json

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest


class GuiApiClient(QObject):
    """Asinhroni API klijent za FlowOS backend.

    Sve metode su neblokirajuće — rezultat se emituje kroz Signal.
    """

    health_received = Signal(object)
    projects_received = Signal(object)
    project_created = Signal(object)
    project_deleted = Signal(str)
    plan_progress_received = Signal(object)
    resume_received = Signal(object)
    sessions_received = Signal(object)
    worktrees_received = Signal(object)
    integration_prepared = Signal(object)
    worktree_cleaned = Signal(object)
    plan_item_received = Signal(object)
    timeline_received = Signal(object)
    agents_scanned = Signal(object)
    error_occurred = Signal(int, str)

    def __init__(self, base_url: str = "http://127.0.0.1:9100", parent=None):
        super().__init__(parent)
        self._base_url = base_url.rstrip("/")
        self._nam = QNetworkAccessManager(self)

    @property
    def base_url(self) -> str:
        return self._base_url

    # ── System ─────────────────────────────────────────

    def check_health(self):
        self._get("/health", self.health_received)  # type: ignore[arg-type]

    # ── Projects ───────────────────────────────────────

    def get_projects(self):
        self._get("/projects", self.projects_received)  # type: ignore[arg-type]

    def create_project(self, name: str, repo_path: str):
        body = {"name": name, "repo_path": repo_path}
        self._post("/projects", body, self.project_created)  # type: ignore[arg-type]  # PySide6 SignalInstance

    def delete_project(self, project_id: str):
        self._delete(f"/projects/{project_id}", lambda data: self.project_deleted.emit(project_id))

    # ── Plan ───────────────────────────────────────────

    def get_plan_progress(self, project_id: str):
        self._get(f"/projects/{project_id}/plan-progress", self.plan_progress_received)  # type: ignore[arg-type]

    # ── Resume ─────────────────────────────────────────

    def get_resume(self, project_id: str):
        self._get(f"/projects/{project_id}/resume", self.resume_received)  # type: ignore[arg-type]

    def regenerate_resume(self, project_id: str):
        self._post(f"/projects/{project_id}/resume/regenerate", {}, self.resume_received)  # type: ignore[arg-type]

    # ── Sessions ───────────────────────────────────────

    def get_active_sessions(self, project_id: str):
        self._get(f"/sessions/active?project_id={project_id}", self.sessions_received)  # type: ignore[arg-type]

    # ── Plan Items ─────────────────────────────────────

    def get_plan_item(self, item_id: str):
        self._get(f"/plan-items/{item_id}", self.plan_item_received)  # type: ignore[arg-type]

    # ── Timeline ────────────────────────────────────────

    def get_timeline(self, project_id: str, limit: int = 30):
        self._get(f"/projects/{project_id}/timeline?limit={limit}", self.timeline_received)  # type: ignore[arg-type]

    # ── Agents ──────────────────────────────────────────

    def scan_agents(self):
        self._get("/agents/scan", self.agents_scanned)  # type: ignore[arg-type]

    # ── HTTP helpers ───────────────────────────────────

    def _get(self, path: str, signal: Signal):
        url = f"{self._base_url}{path}"
        req = QNetworkRequest()
        req.setUrl(url)
        req.setRawHeader(b"Accept", b"application/json")
        reply = self._nam.get(req)
        reply.finished.connect(lambda r=reply, s=signal: self._handle_response(r, s))

    def _post(self, path: str, body: dict, signal: Signal):
        url = f"{self._base_url}{path}"
        req = QNetworkRequest()
        req.setUrl(url)
        req.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        data = json.dumps(body).encode("utf-8")
        reply = self._nam.post(req, data)
        reply.finished.connect(lambda r=reply, s=signal: self._handle_response(r, s))

    def _delete(self, path: str, callback):
        url = f"{self._base_url}{path}"
        req = QNetworkRequest()
        req.setUrl(url)
        reply = self._nam.deleteResource(req)
        reply.finished.connect(lambda r=reply, cb=callback: self._handle_response(r, None, cb))

    def _handle_response(self, reply: QNetworkReply, signal: Signal | None, callback=None):
        if reply.error() == QNetworkReply.NetworkError.NoError:
            try:
                data = json.loads(reply.readAll().data().decode())  # type: ignore[union-attr]  # PySide6 QByteArray
                if signal:
                    signal.emit(data)  # type: ignore[attr-defined]  # PySide6 Signal
                elif callback:
                    callback(data)
            except json.JSONDecodeError:
                self.error_occurred.emit(-1, "Neispravan JSON odgovor")
        else:
            code = reply.error()
            msg = reply.errorString()
            self.error_occurred.emit(code, msg)
            if signal:
                signal.emit({"error": msg})  # type: ignore[attr-defined]  # PySide6 Signal
        reply.deleteLater()

    # ── Worktrees ───────────────────────────────────────

    def fetch_worktrees(self, project_id: str):
        self._get(f"/worktrees?project_id={project_id}", self.worktrees_received)  # type: ignore[arg-type]

    def prepare_integration(self, worktree_id: str, base_branch: str = "main"):
        self._post(
            f"/worktrees/{worktree_id}/integrate/prepare?base_branch={base_branch}",
            {},
            self.integration_prepared,  # type: ignore[arg-type]
        )

    def cleanup_worktree(self, worktree_id: str, force: bool = False):
        self._post(
            f"/worktrees/{worktree_id}/cleanup",
            {"force": force},
            self.worktree_cleaned,  # type: ignore[arg-type]
        )
