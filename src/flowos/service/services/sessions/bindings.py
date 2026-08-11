"""Service sloj za istorijske SessionTaskBinding segmente.

Ovaj modul uvodi autoritativnu istoriju promjena task konteksta sesije,
dok AgentSession.task_id/plan_item_id ostaju legacy compatibility pointeri.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from flowos.service.services.infrastructure.persistence.models import (
    AgentSession,
    SessionTaskBinding,
    Task,
)
from flowos.service.services.infrastructure.persistence.plan_models import Plan, PlanItem, PlanPhase
from flowos.shared.enums.session import SessionTaskBindingSource


class SessionTaskBindingService:
    """Upravlja vremenskim binding segmentima jedne agentske sesije."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_bindings(self, session_id: str) -> list[SessionTaskBinding]:
        return (
            self._session.query(SessionTaskBinding)
            .filter(SessionTaskBinding.session_id == session_id)
            .order_by(SessionTaskBinding.started_at.asc(), SessionTaskBinding.id.asc())
            .all()
        )

    def get_active_binding(self, session_id: str) -> SessionTaskBinding | None:
        active = (
            self._session.query(SessionTaskBinding)
            .filter(
                SessionTaskBinding.session_id == session_id,
                SessionTaskBinding.ended_at.is_(None),
            )
            .all()
        )
        if len(active) > 1:
            raise ValueError(f"Sesija {session_id} ima više od jednog aktivnog bindinga")
        return active[0] if active else None

    def switch_binding(
        self,
        session_id: str,
        *,
        task_id: str | None = None,
        plan_item_id: str | None = None,
        binding_source: SessionTaskBindingSource = SessionTaskBindingSource.USER,
        switched_at: datetime | None = None,
    ) -> SessionTaskBinding:
        """Zatvara aktivni binding i kreira novi aktivni segment."""
        if task_id and plan_item_id:
            raise ValueError("Binding može imati task_id ili plan_item_id, ne oba")

        session_obj = self._session.get(AgentSession, session_id)
        if not session_obj:
            raise ValueError(f"Sesija {session_id} ne postoji")

        now = switched_at or datetime.now(tz=UTC)

        # 1. Validiraj novi target PRE zatvaranja postojećeg bindinga
        self._validate_target_project(session_obj, task_id=task_id, plan_item_id=plan_item_id)

        # 2. Zatvori aktivni binding (tek nakon što je novi target validan)
        active = self.get_active_binding(session_id)
        if active:
            self._close_binding(active, now)

        binding = SessionTaskBinding(
            session_id=session_id,
            task_id=task_id,
            plan_item_id=plan_item_id,
            started_at=now,
            binding_source=binding_source.value,
        )
        self._session.add(binding)
        self._sync_legacy_pointer(session_obj, task_id=task_id, plan_item_id=plan_item_id)
        self._session.flush()
        return binding

    def close_active_binding(
        self, session_id: str, *, ended_at: datetime | None = None
    ) -> SessionTaskBinding | None:
        """Zatvara aktivni binding bez falsifikovanja istorije ili backfill-a."""
        active = self.get_active_binding(session_id)
        if not active:
            return None
        self._close_binding(active, ended_at or datetime.now(tz=UTC))
        self._session.flush()
        return active

    def _close_binding(self, binding: SessionTaskBinding, ended_at: datetime) -> None:
        if self._as_utc(ended_at) < self._as_utc(binding.started_at):
            raise ValueError("Binding se ne može završiti prije početka")
        binding.ended_at = ended_at

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _validate_target_project(
        self,
        session_obj: AgentSession,
        *,
        task_id: str | None,
        plan_item_id: str | None,
    ) -> None:
        if task_id:
            task = self._session.get(Task, task_id)
            if not task:
                raise ValueError(f"Task {task_id} ne postoji")
            if task.project_id != session_obj.project_id:
                raise ValueError(
                    f"Task {task_id} ne pripada projektu sesije {session_obj.project_id}"
                )

        if plan_item_id:
            plan_item = self._session.get(PlanItem, plan_item_id)
            if not plan_item:
                raise ValueError(f"PlanItem {plan_item_id} ne postoji")
            phase = self._session.get(PlanPhase, plan_item.plan_phase_id)
            plan = self._session.get(Plan, phase.plan_id) if phase else None
            if not plan or plan.project_id != session_obj.project_id:
                raise ValueError(
                    f"PlanItem {plan_item_id} ne pripada projektu sesije {session_obj.project_id}"
                )

    def _sync_legacy_pointer(
        self,
        session_obj: AgentSession,
        *,
        task_id: str | None,
        plan_item_id: str | None,
    ) -> None:
        if task_id:
            task = self._session.get(Task, task_id)
            session_obj.task_id = task_id
            session_obj.plan_item_id = task.plan_item_id if task else None
            return

        session_obj.task_id = None
        session_obj.plan_item_id = plan_item_id
