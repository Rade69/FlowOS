"""Session Service — registracija i životni ciklus sesije."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from flowos.service.services.infrastructure.persistence.models import AgentSession
from flowos.service.services.sessions.bindings import SessionTaskBindingService
from flowos.shared.enums.session import SessionStatus, SessionTaskBindingSource


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
        """Registruje novu sesiju.

        Validacija se izvršava pre flush-a:
        - Projekat mora postojati
        - Task mora pripadati projektu
        - Plan item mora pripadati aktivnom planu projekta
        - Worktree ne sme biti zauzet drugom aktivnom sesijom
        """
        from flowos.service.services.infrastructure.persistence.models import Project, Task
        from flowos.service.services.infrastructure.persistence.plan_models import (
            Plan,
            PlanItem,
            PlanPhase,
        )

        # Validacija: projekat postoji
        project = self._session.get(Project, project_id)
        if not project:
            raise ValueError(f"Projekat {project_id} ne postoji")

        task = None
        plan_item = None

        # Validacija: task pripada projektu
        if task_id:
            task = self._session.get(Task, task_id)
            if not task:
                raise ValueError(f"Task {task_id} ne postoji")
            if task.project_id != project_id:
                raise ValueError(f"Task {task_id} ne pripada projektu {project_id}")

        # Validacija: plan item pripada aktivnom planu projekta
        if plan_item_id:
            plan_item = self._session.get(PlanItem, plan_item_id)
            if not plan_item:
                raise ValueError(f"PlanItem {plan_item_id} ne postoji")
            phase = self._session.get(PlanPhase, plan_item.plan_phase_id)
            plan = self._session.get(Plan, phase.plan_id) if phase else None
            if not plan or plan.project_id != project_id:
                raise ValueError(f"PlanItem {plan_item_id} ne pripada projektu {project_id}")

        if task_id and plan_item_id and task and task.plan_item_id != plan_item_id:
            raise ValueError(
                f"Task {task_id} nije povezan sa proslijeđenim PlanItem {plan_item_id}"
            )

        # Validacija: worktree nije zauzet drugom aktivnom sesijom
        if worktree_path:
            from flowos.service.services.infrastructure.persistence.worktree_models import Worktree

            wt = (
                self._session.query(Worktree)
                .filter(Worktree.worktree_path == worktree_path)
                .first()
            )
            if wt and wt.project_id != project_id:
                raise ValueError(f"Worktree {worktree_path} ne pripada projektu {project_id}")
            if wt and wt.session_id:
                existing = self._session.get(AgentSession, wt.session_id)
                if existing and existing.status in ("ACTIVE", "IDLE"):
                    raise ValueError(
                        f"Worktree je već zauzet sesijom {wt.session_id}. "
                        f"Jedan worktree = najviše jedna writer sesija."
                    )

        legacy_plan_item_id = task.plan_item_id if task else plan_item_id

        session_obj = AgentSession(
            project_id=project_id,
            task_id=task_id,
            agent_type=agent_type,
            model_name=model_name,
            execution_mode=execution_mode,
            repo_path=repo_path,
            branch_name=branch_name,
            worktree_path=worktree_path,
            plan_item_id=legacy_plan_item_id,
            base_commit_sha=base_commit_sha,
            pid=pid,
            status=SessionStatus.ACTIVE.value,
            started_at=datetime.now(tz=UTC),
            last_activity_at=datetime.now(tz=UTC),
        )
        self._session.add(session_obj)
        self._session.flush()

        binding_task_id = task_id
        binding_plan_item_id = None if task_id else plan_item_id
        SessionTaskBindingService(self._session).switch_binding(
            session_obj.id,
            task_id=binding_task_id,
            plan_item_id=binding_plan_item_id,
            binding_source=SessionTaskBindingSource.LEGACY_DIRECT_FK,
            switched_at=session_obj.started_at,
        )

        # Ako je sesija povezana sa worktree-jem, ažuriraj Worktree model
        if worktree_path:
            wt = (
                self._session.query(Worktree)
                .filter(Worktree.worktree_path == worktree_path)
                .first()
            )
            if wt:
                wt.session_id = session_obj.id
                wt.last_activity_at = datetime.now(tz=UTC)
                self._session.flush()

        # Emituj WebSocket događaj
        from flowos.service.controllers.websocket.events import event_bus

        event_bus.emit_sync(
            "session.created",
            {
                "session_id": session_obj.id,
                "project_id": project_id,
                "agent_type": agent_type,
                "execution_mode": execution_mode,
                "worktree_path": worktree_path,
            },
        )

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
        SessionTaskBindingService(self._session).close_active_binding(
            session_id, ended_at=session_obj.ended_at
        )
        self._session.flush()
        return session_obj

    def record_heartbeat(self, session_id: str) -> AgentSession | None:
        """Beleži procesni heartbeat za sesiju.

        Nezavisno od filesystem aktivnosti. Poziva se periodično
        iz adaptera, wrapper-a ili process monitora.

        Heartbeat se prihvata samo za ne-terminalna stanja
        (ACTIVE, IDLE). Za terminalna stanja (COMPLETED, ABANDONED,
        NEEDS_REVIEW i sve završne statuse) baca ValueError.
        """
        session_obj = self._session.get(AgentSession, session_id)
        if not session_obj:
            return None

        if session_obj.status not in ("ACTIVE", "IDLE"):
            raise ValueError(f"Sesija je u terminalnom stanju {session_obj.status}")

        session_obj.last_heartbeat_at = datetime.now(tz=UTC)
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
