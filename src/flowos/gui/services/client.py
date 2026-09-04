"""GUI API klijent — HTTP komunikacija sa FlowOS backendom.

Koristi QNetworkAccessManager za neblokirajuće HTTP pozive.
Vraća rezultate kroz Qt signale (ne callback hell).
"""

import json
from typing import Any

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

    def __init__(
        self, base_url: str = "http://127.0.0.1:9100", token: str | None = None, parent=None
    ):
        super().__init__(parent)
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._nam = QNetworkAccessManager(self)

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def token(self) -> str | None:
        """Auth token trenutne service instance (FLOW-1107), ili None u MOCK modu."""
        return self._token

    def _apply_auth_header(self, req: QNetworkRequest) -> None:
        """Dodaje Authorization: Bearer <token> ako je token poznat.

        /health backend prihvata i bez tokena, ali slanje ne šteti — nema
        potrebe za posebnim izuzetkom po ruti na klijentu.
        """
        if self._token:
            req.setRawHeader(b"Authorization", f"Bearer {self._token}".encode())

    # ── System ─────────────────────────────────────────

    def check_health(self):
        self._get("/health", self.health_received)

    def prepare_shutdown(self, on_ready) -> None:
        """Provjerava smije li se servis ugasiti i vraća dict ili None."""
        req = QNetworkRequest()
        req.setUrl(f"{self._base_url}/system/shutdown/prepare")
        req.setRawHeader(b"Accept", b"application/json")
        self._apply_auth_header(req)
        reply = self._nam.get(req)

        def _handle_prepare_response() -> None:
            data = None
            if reply.error() == QNetworkReply.NetworkError.NoError:
                try:
                    payload = json.loads(bytes(reply.readAll().data()).decode())
                    if isinstance(payload, dict):
                        data = payload
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
            on_ready(data)
            reply.deleteLater()

        reply.finished.connect(_handle_prepare_response)

    def confirm_shutdown(self, on_success) -> None:
        """Potvrđuje gašenje servisa kroz javni GUI API ugovor."""
        self._post("/system/shutdown/confirm", {}, on_success)

    # ── Projects ───────────────────────────────────────

    def get_projects(self):
        self._get("/projects", self.projects_received)

    def create_project(self, name: str, repo_path: str):
        body = {"name": name, "repo_path": repo_path}
        self._post("/projects", body, self.project_created)

    def delete_project(self, project_id: str):
        self._delete(f"/projects/{project_id}", lambda data: self.project_deleted.emit(project_id))

    # ── Plan ───────────────────────────────────────────

    def get_plan_progress(self, project_id: str, generation: int = 0):
        # FLOW-1201: emituje (project_id, generation, payload) da potrošač može
        # odbaciti zakašnjeli odgovor (stari generation ili drugi projekat).
        self._get(
            f"/projects/{project_id}/plan-progress",
            lambda data, pid=project_id, gen=generation: self.plan_progress_received.emit(
                (pid, gen, data)
            ),
        )

    def import_plan(self, project_id: str, markdown_text: str, on_success) -> None:
        """Uvozi plan koristeći canonical PlanImportRequest polje."""
        self._post(
            f"/projects/{project_id}/import-plan",
            {"markdown_text": markdown_text},
            on_success,
        )

    # ── Resume ─────────────────────────────────────────

    def get_resume(self, project_id: str, generation: int = 0):
        self._get(
            f"/projects/{project_id}/resume",
            lambda data, pid=project_id, gen=generation: self.resume_received.emit(
                (pid, gen, data)
            ),
        )

    def regenerate_resume(self, project_id: str, generation: int = 0):
        self._post(
            f"/projects/{project_id}/resume/regenerate",
            {},
            lambda data, pid=project_id, gen=generation: self.resume_received.emit(
                (pid, gen, data)
            ),
        )

    # ── Sessions ───────────────────────────────────────

    def get_active_sessions(self, project_id: str, generation: int = 0):
        self._get(
            f"/sessions/active?project_id={project_id}",
            lambda data, pid=project_id, gen=generation: self.sessions_received.emit(
                (pid, gen, data)
            ),
        )

    def create_tracked_session(
        self,
        project_id: str,
        agent_type: str,
        repo_path: str,
        pid: int,
        generation: int = 0,
    ) -> None:
        """Kreira EXTERNAL_TRACKED sesiju za već pokrenut agentski proces."""
        self._post(
            "/sessions",
            {
                "project_id": project_id,
                "agent_type": agent_type,
                "repo_path": repo_path,
                "execution_mode": "EXTERNAL_TRACKED",
                "pid": pid,
            },
            lambda data, pid=project_id, gen=generation: self.sessions_received.emit(
                (pid, gen, data)
            ),
        )

    # ── Plan Items ─────────────────────────────────────

    def get_plan_item(self, item_id: str):
        self._get(f"/plan-items/{item_id}", self.plan_item_received)

    # ── Timeline ────────────────────────────────────────

    def get_timeline(self, project_id: str, limit: int = 30, generation: int = 0):
        self._get(
            f"/projects/{project_id}/timeline?limit={limit}",
            lambda data, pid=project_id, gen=generation: self.timeline_received.emit(
                (pid, gen, data)
            ),
        )

    # ── Agents ──────────────────────────────────────────

    def scan_agents(self):
        self._get("/agents/scan", self.agents_scanned)

    # ── HTTP helpers ───────────────────────────────────

    def _get(self, path: str, signal: Any):
        url = f"{self._base_url}{path}"
        req = QNetworkRequest()
        req.setUrl(url)
        req.setRawHeader(b"Accept", b"application/json")
        self._apply_auth_header(req)
        reply = self._nam.get(req)
        reply.finished.connect(lambda r=reply, s=signal: self._handle_response(r, s))

    def _post(self, path: str, body: dict, signal: Any):
        url = f"{self._base_url}{path}"
        req = QNetworkRequest()
        req.setUrl(url)
        req.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        self._apply_auth_header(req)
        data = json.dumps(body).encode("utf-8")
        reply = self._nam.post(req, data)
        reply.finished.connect(lambda r=reply, s=signal: self._handle_response(r, s))

    def _delete(self, path: str, callback):
        url = f"{self._base_url}{path}"
        req = QNetworkRequest()
        req.setUrl(url)
        self._apply_auth_header(req)
        reply = self._nam.deleteResource(req)
        reply.finished.connect(lambda r=reply, cb=callback: self._handle_response(r, None, cb))

    def _handle_response(
        self,
        reply: QNetworkReply,
        signal: Any,
        callback=None,
    ):
        if reply.error() == QNetworkReply.NetworkError.NoError:
            try:
                data = json.loads(reply.readAll().data().decode())  # type: ignore[union-attr]  # PySide6 QByteArray
                self._dispatch(signal, callback, data)
            except json.JSONDecodeError:
                self.error_occurred.emit(-1, "Neispravan JSON odgovor")
        else:
            code = reply.error().value if reply.error() is not None else -1
            msg = reply.errorString()
            self.error_occurred.emit(code, msg)
            self._dispatch(signal, callback, {"error": msg})
        reply.deleteLater()

    @staticmethod
    def _dispatch(signal: Any, callback, payload: Any) -> None:
        """Emitovanje payload-a: Qt signal pre plain Python callable-a.

        Bound Qt SignalInstance je callable == True, ali direktan poziv
        `signal(...)` baca TypeError. Zato se Qt signali prepoznaju i
        emituju kroz `.emit()`, a tek obične Python callable funkcije se
        pozivaju direktno.
        """
        if signal is not None and hasattr(signal, "emit"):
            signal.emit(payload)
        elif callable(signal):
            signal(payload)
        elif callback is not None:
            callback(payload)

    # ── Worktrees ───────────────────────────────────────

    def fetch_worktrees(self, project_id: str, generation: int = 0):
        self._get(
            f"/worktrees?project_id={project_id}",
            lambda data, pid=project_id, gen=generation: self.worktrees_received.emit(
                (pid, gen, data)
            ),
        )

    def prepare_integration(self, worktree_id: str, base_branch: str = "main"):
        self._post(
            f"/worktrees/{worktree_id}/integrate/prepare?base_branch={base_branch}",
            {},
            self.integration_prepared,
        )

    def cleanup_worktree(self, worktree_id: str, force: bool = False):
        self._post(
            f"/worktrees/{worktree_id}/cleanup",
            {"force": force},
            self.worktree_cleaned,
        )
