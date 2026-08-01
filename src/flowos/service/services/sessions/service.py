"""Session Service — registracija i životni ciklus sesije."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from flowos.service.services.infrastructure.persistence.models import AgentSession
from flowos.shared.enums.session import SessionStatus


class SessionService:
    """Upravljanje životnim ciklusom agentske sesije."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_session(
        self,
        project_id: str,
        agent_type: str,
        repo_path: str,
        *,
        task_id: str | None = None,
        model_name: str | None = None,
        execution_mode: str = "WRAPPED_TERMINAL",
        branch_name: str | None = None,
        worktree_path: str | None = None,
        plan_item_id: str | None = None,
        base_commit_sha: str | None = None,
        pid: int | None = None,
    ) -> AgentSession:
        """Registruje novu sesiju."""
        session_obj = AgentSession(
            project_id=project_id,
            task_id=task_id,
            agent_type=agent_type,
            model_name=model_name,
            execution_mode=execution_mode,
            repo_path=repo_path,
            branch_name=branch_name,
            worktree_path=worktree_path,
            plan_item_id=plan_item_id,
            base_commit_sha=base_commit_sha,
            pid=pid,
            status=SessionStatus.ACTIVE.value,
            started_at=datetime.now(tz=UTC),
            last_activity_at=datetime.now(tz=UTC),
        )
        self._session.add(session_obj)
        self._session.flush()
        return session_obj

    def end_session(
        self,
        session_id: str,
        *,
        exit_code: int | None = None,
        result_commit_sha: str | None = None,
        status: str = "COMPLETED",
    ) -> AgentSession | None:
        """Završava sesiju. Ne prepisuje base_commit_sha."""
        allowed = {"COMPLETED", "FAILED", "INTERRUPTED", "TIMED_OUT"}
        if status not in allowed:
            raise ValueError(f"Nedozvoljen status sesije: {status}. Dozvoljeni: {sorted(allowed)}")
        session_obj = self._session.get(AgentSession, session_id)
        if not session_obj:
            return None
        session_obj.status = status
        session_obj.ended_at = datetime.now(tz=UTC)
        session_obj.exit_code = exit_code
        if result_commit_sha:
            session_obj.result_commit_sha = result_commit_sha
        self._session.flush()
        return session_obj

    def get_session(self, session_id: str) -> AgentSession | None:
        return self._session.get(AgentSession, session_id)

    def list_active_sessions(self, project_id: str) -> list[AgentSession]:
        return (
            self._session.query(AgentSession)
            .filter(
                AgentSession.project_id == project_id,
                AgentSession.status.in_(("ACTIVE", "IDLE")),
            )
            .order_by(AgentSession.started_at.desc())
            .all()
        )

    def list_sessions(self, project_id: str, limit: int = 50) -> list[AgentSession]:
        return (
            self._session.query(AgentSession)
            .filter(AgentSession.project_id == project_id)
            .order_by(AgentSession.started_at.desc())
            .limit(limit)
            .all()
        )