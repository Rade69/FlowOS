"""ProjectStateService — jedinstveno stanje projekta iz svih izvora.

Konsoliduje: PlanItem statuse, Session statuse, Conflict statuse,
WorkspaceState, Worktree statuse, Verification rezultate u jedan odgovor.

Koristi se za: početni ekran, Gdje si stao, topbar badge, CLI status.
"""

from sqlalchemy.orm import Session

from flowos.service.services.infrastructure.persistence.conflict_models import Conflict
from flowos.service.services.infrastructure.persistence.models import AgentSession
from flowos.service.services.infrastructure.persistence.plan_models import (
    Plan,
    PlanItem,
    PlanPhase,
)
from flowos.service.services.infrastructure.persistence.resume_models import (
    ProjectResumeState,
    ProjectWorkspaceState,
)
from flowos.service.services.infrastructure.persistence.worktree_models import Worktree
from flowos.shared.enums.session import SessionStatus

OPERATIONAL_STATES = [
    "READY",
    "WORK_IN_PROGRESS",
    "NEEDS_ATTENTION",
    "BLOCKED",
    "NEEDS_REVIEW",
    "READY_TO_ACCEPT",
    "SAFE_TO_CONTINUE",
    "EXTERNAL_CHANGES",
    "NO_ACTIVE_PLAN",
]


class ProjectStateService:
    """Konsoliduje stanje projekta iz svih trajnih izvora."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_state(self, project_id: str) -> dict:
        active_plan = (
            self._db.query(Plan)
            .filter(Plan.project_id == project_id, Plan.status == "ACTIVE")
            .first()
        )

        # Aktivne sesije
        active_sessions = (
            self._db.query(AgentSession)
            .filter(
                AgentSession.project_id == project_id,
                AgentSession.status.in_(
                    (SessionStatus.ACTIVE.value, SessionStatus.IDLE.value)
                ),
            )
            .all()
        )

        # Plan itemi
        plan_items: list[PlanItem] = []
        if active_plan:
            phase_ids = [p.id for p in self._db.query(PlanPhase).filter(PlanPhase.plan_id == active_plan.id).all()]
            if phase_ids:
                plan_items = (
                    self._db.query(PlanItem)
                    .filter(PlanItem.plan_phase_id.in_(phase_ids))
                    .all()
                )

        # Konflikti
        open_conflicts = (
            self._db.query(Conflict)
            .filter(Conflict.project_id == project_id, Conflict.status == "OPEN")
            .count()
        )

        # Workspace state
        ws_state = (
            self._db.query(ProjectWorkspaceState)
            .filter(ProjectWorkspaceState.project_id == project_id)
            .first()
        )

        # Resume
        resume = (
            self._db.query(ProjectResumeState)
            .filter(ProjectResumeState.project_id == project_id)
            .first()
        )

        # Worktrees
        worktrees = (
            self._db.query(Worktree)
            .filter(Worktree.project_id == project_id)
            .all()
        )
        dirty_worktrees = sum(1 for w in worktrees if w.git_status == "DIRTY")

        # Izvedeno stanje
        operational_state = self._derive_state(
            active_plan, plan_items, active_sessions, open_conflicts, ws_state
        )

        # Aktivna plan stavka
        active_item = None
        for it in plan_items:
            if it.status == "IN_PROGRESS":
                active_item = it
                break
        if not active_item:
            for it in plan_items:
                if it.status == "BLOCKED":
                    active_item = it
                    break

        # Next action
        next_action = self._derive_next_action(
            active_item, active_sessions, open_conflicts, ws_state
        )

        return {
            "project_id": project_id,
            "operational_state": operational_state,
            "active_plan_id": active_plan.id if active_plan else None,
            "active_plan_title": active_plan.title if active_plan else None,
            "active_plan_item": {
                "id": active_item.id,
                "item_key": active_item.item_key,
                "title": active_item.title,
                "status": active_item.status,
            } if active_item else None,
            "active_sessions": len(active_sessions),
            "open_conflicts": open_conflicts,
            "git_dirty": ws_state.is_dirty if ws_state else False,
            "external_changes": ws_state.reconciliation_status != "CURRENT" if ws_state else False,
            "dirty_worktrees": dirty_worktrees,
            "resume_confidence": resume.confidence if resume else "LOW",
            "next_action": next_action,
        }

    def _derive_state(
        self,
        plan,
        plan_items: list,
        sessions: list,
        conflicts: int,
        ws_state,
    ) -> str:
        if not plan:
            return "NO_ACTIVE_PLAN"
        if conflicts > 0:
            return "NEEDS_ATTENTION"
        if any(it.status == "BLOCKED" for it in plan_items):
            return "BLOCKED"
        if any(it.status == "IN_PROGRESS" for it in plan_items):
            return "WORK_IN_PROGRESS"
        if any(it.status in ("VERIFIED", "IMPLEMENTED") for it in plan_items):
            return "NEEDS_REVIEW"
        if sessions:
            return "WORK_IN_PROGRESS"
        if ws_state and ws_state.reconciliation_status != "CURRENT":
            return "EXTERNAL_CHANGES"
        if all(it.status == "NOT_STARTED" for it in plan_items):
            return "READY"
        return "READY"

    def _derive_next_action(self, active_item, sessions, conflicts, ws_state) -> dict | None:
        if conflicts > 0:
            return {
                "action_type": "RESOLVE_CONFLICT",
                "label": f"Riješiti {conflicts} otvorenih konflikata",
                "target_type": "PROJECT",
                "priority": "HIGH",
            }
        if ws_state and ws_state.reconciliation_status not in ("CURRENT", None):
            return {
                "action_type": "RECONCILE_EXTERNAL_CHANGES",
                "label": "Uskladiti vanjske Git promjene",
                "target_type": "PROJECT",
                "priority": "HIGH",
            }
        if active_item:
            if active_item.status == "IN_PROGRESS":
                return {
                    "action_type": "CONTINUE_ACTIVE_SESSION",
                    "label": f"Nastaviti rad na {active_item.item_key}",
                    "target_type": "PLAN_ITEM",
                    "target_id": active_item.id,
                    "priority": "MEDIUM",
                }
            if active_item.status == "IMPLEMENTED":
                return {
                    "action_type": "RUN_VERIFICATION",
                    "label": f"Pokrenuti verifikaciju za {active_item.item_key}",
                    "target_type": "PLAN_ITEM",
                    "target_id": active_item.id,
                    "priority": "HIGH",
                }
            if active_item.status == "VERIFIED":
                return {
                    "action_type": "ACCEPT_VERIFIED_ITEM",
                    "label": f"Prihvatiti {active_item.item_key}",
                    "target_type": "PLAN_ITEM",
                    "target_id": active_item.id,
                    "priority": "MEDIUM",
                }
        if not sessions:
            return {
                "action_type": "START_FIRST_PLAN_ITEM",
                "label": "Započeti prvu planiranu stavku",
                "target_type": "PLAN",
                "priority": "LOW",
            }
        return None
