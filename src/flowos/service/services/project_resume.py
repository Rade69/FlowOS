"""ProjectResumeService — regeneracija "Gde si stao" sažetka iz trajnih izvora.

Koristi Plan, Session, Report, WorkspaceState za izgradnju
ProjectResumeState. Ne radi Git reconciliation (to je za FLOW-104/202).
"""

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from flowos.service.services.infrastructure.persistence.models import AgentSession
from flowos.service.services.infrastructure.persistence.plan_models import (
    Plan,
    PlanItem,
)
from flowos.service.services.infrastructure.persistence.resume_models import (
    ExternalActivity,
    ProjectResumeState,
    ProjectWorkspaceState,
)

# ═══════════════════════════════════════════════════════════════════
# Confidence pravila
# ═══════════════════════════════════════════════════════════════════

# Kada je resume HIGH confidence:
# - postoji aktivan plan sa stavkom
# - poslednja sesija ima report
# - workspace state je CURRENT
# - nema otvorenih blokada

# MEDIUM:
# - postoji plan ali bez reporta
# - ili workspace state nije CURRENT

# LOW:
# - nema plana
# - ili NO_HISTORY


class ProjectResumeService:
    """Regeneriše ProjectResumeState iz trajnih izvora."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def regenerate(self, project_id: str) -> ProjectResumeState:
        """Regeneriše "Gde si stao" sažetak za projekat.

        Args:
            project_id: ID projekta.

        Returns:
            ProjectResumeState sa ažuriranim sažetkom.
        """
        # Nađi ili kreiraj resume state
        resume = (
            self._session.query(ProjectResumeState)
            .filter(ProjectResumeState.project_id == project_id)
            .first()
        )
        if not resume:
            resume = ProjectResumeState(project_id=project_id)
            self._session.add(resume)

        # 1. Aktivan plan
        plan = (
            self._session.query(Plan)
            .filter(Plan.project_id == project_id, Plan.status == "ACTIVE")
            .order_by(Plan.activated_at.desc())
            .first()
        )
        resume.active_plan_id = plan.id if plan else None

        # 2. Poslednja aktivna/završena plan stavka
        last_item = None
        if plan:
            from flowos.service.services.infrastructure.persistence.plan_models import PlanPhase

            phases = (
                self._session.query(PlanPhase)
                .filter(PlanPhase.plan_id == plan.id)
                .order_by(PlanPhase.sequence)
                .all()
            )
            for phase in phases:
                items = (
                    self._session.query(PlanItem)
                    .filter(PlanItem.plan_phase_id == phase.id)
                    .order_by(PlanItem.sequence.desc())
                    .all()
                )
                for item in items:
                    if item.status in ("IN_PROGRESS", "IMPLEMENTED", "VERIFIED"):
                        last_item = item
                        break
                if last_item:
                    break
            # Ako nema aktivnih, uzmi poslednju IMPLEMENTED/VERIFIED/ACCEPTED
            if not last_item and phases:
                items = (
                    self._session.query(PlanItem)
                    .filter(PlanItem.plan_phase_id == phases[-1].id)
                    .order_by(PlanItem.sequence.desc())
                    .all()
                )
                for item in items:
                    if item.status != "NOT_STARTED":
                        last_item = item
                        break

        resume.last_plan_item_id = last_item.id if last_item else None

        # 3. Poslednja sesija
        last_session = (
            self._session.query(AgentSession)
            .filter(AgentSession.project_id == project_id)
            .order_by(AgentSession.started_at.desc())
            .first()
        )
        resume.last_session_id = last_session.id if last_session else None
        resume.last_task_id = last_session.task_id if last_session else None

        # 4. Workspace state
        ws = (
            self._session.query(ProjectWorkspaceState)
            .filter(ProjectWorkspaceState.project_id == project_id)
            .first()
        )
        if ws:
            resume.last_commit_sha = ws.last_known_commit_sha
            resume.last_activity_at = ws.last_observed_at

        # 5. Otvorene blokade (PlanItem sa statusom BLOCKED)
        blocked_items: list[dict] = []
        if plan:
            all_blocked = self._session.query(PlanItem).filter(PlanItem.status == "BLOCKED").all()
            # Filtriraj samo one u ovom planu
            for bi in all_blocked:
                phase = bi.phase if hasattr(bi, "phase") else None
                if phase and phase.plan_id == plan.id:
                    blocked_items.append(
                        {
                            "item_key": bi.item_key,
                            "title": bi.title,
                            "reason": bi.blocked_reason,
                        }
                    )

        resume.open_blockers_json = json.dumps(blocked_items) if blocked_items else None

        # 6. Izgradi where_stopped i next_concrete_step
        if last_item:
            status_labels = {
                "NOT_STARTED": "nije početa",
                "IN_PROGRESS": "u toku",
                "BLOCKED": "blokirana",
                "IMPLEMENTED": "implementirana (čeka verifikaciju)",
                "VERIFIED": "verifikovana (čeka potvrdu)",
                "ACCEPTED": "prihvaćena",
            }
            resume.where_stopped = (
                f"Poslednja aktivna stavka: {last_item.item_key} — {last_item.title} "
                f"(status: {status_labels.get(last_item.status, last_item.status)})"
            )

            if last_item.status == "IN_PROGRESS":
                resume.next_concrete_step = (
                    f"Završiti {last_item.item_key} i označiti kao IMPLEMENTED"
                )
            elif last_item.status == "IMPLEMENTED":
                resume.next_concrete_step = f"Pokrenuti verifikaciju za {last_item.item_key}"
            elif last_item.status == "VERIFIED":
                resume.next_concrete_step = f"Korisnik da prihvati ili odbije {last_item.item_key}"
            elif last_item.status == "BLOCKED":
                resume.next_concrete_step = (
                    f"Razrešiti blokadu: {last_item.blocked_reason or 'nepoznat razlog'}"
                )
            else:
                resume.next_concrete_step = f"Označiti {last_item.item_key} kao IN_PROGRESS"
        elif plan:
            resume.where_stopped = f"Aktivni plan: {plan.title}. Nema započetih stavki."
            resume.next_concrete_step = "Početi prvu stavku u planu."
        else:
            resume.where_stopped = "Projekat nema aktivni plan."
            resume.next_concrete_step = "Importovati i aktivirati plan."

        # 7. Preuslovi za nastavak
        preconditions: list[str] = []
        if blocked_items:
            preconditions.append(f"Razrešiti {len(blocked_items)} blokiranih stavki")
        if ws and ws.reconciliation_status != "CURRENT":
            preconditions.append("Rešiti reconciliation pre nastavka")
        if not plan:
            preconditions.append("Aktivirati plan")

        resume.resume_preconditions = (
            "\n".join(preconditions) if preconditions else "Nema preuslova."
        )

        # 8. Confidence
        resume.confidence = self._compute_confidence(resume, ws, plan, last_session)

        # 9. Status
        if not plan:
            resume.resume_status = "NO_HISTORY"
        elif blocked_items:
            resume.resume_status = "BLOCKED"
        elif ws and ws.reconciliation_status != "CURRENT":
            resume.resume_status = "EXTERNAL_CHANGES"
        elif not last_session:
            resume.resume_status = "NEEDS_REVIEW"
        else:
            resume.resume_status = "READY_TO_CONTINUE"

        resume.generated_at = datetime.now(tz=UTC)
        self._session.flush()
        return resume

    def get_current_resume(self, project_id: str):
        """Vraća postojeći resume state bez regeneracije (read-only)."""
        return (
            self._session.query(ProjectResumeState)
            .filter(ProjectResumeState.project_id == project_id)
            .first()
        )

    def get_workspace_state(self, project_id: str) -> dict | None:
        ws = (
            self._session.query(ProjectWorkspaceState)
            .filter(ProjectWorkspaceState.project_id == project_id)
            .first()
        )
        if not ws:
            return None
        return {
            "id": ws.id, "project_id": ws.project_id,
            "last_known_commit_sha": ws.last_known_commit_sha,
            "last_known_branch": ws.last_known_branch,
            "reconciliation_status": ws.reconciliation_status,
            "external_change_summary": ws.external_change_summary,
            "last_observed_at": ws.last_observed_at.isoformat() if ws.last_observed_at else None,
            "last_reconciled_at": ws.last_reconciled_at.isoformat() if ws.last_reconciled_at else None,
        }

    def create_external_activity(self, project_id: str, data: dict) -> dict:
        activity = ExternalActivity(
            project_id=project_id,
            plan_item_id=data.get("plan_item_id"),
            task_id=data.get("task_id"),
            source=data.get("source", "UNKNOWN"),
            summary=data.get("summary", "Nepoznata eksterna izmena"),
            commit_shas_json=data.get("commit_shas_json"),
            changed_files_json=data.get("changed_files_json"),
            user_note=data.get("user_note"),
        )
        self._session.add(activity)
        self._session.flush()
        return {
            "id": activity.id, "project_id": activity.project_id,
            "source": activity.source, "summary": activity.summary,
            "attribution": activity.attribution,
            "created_at": activity.created_at.isoformat() if activity.created_at else None,
        }

    def list_external_activities(self, project_id: str, limit: int = 50) -> list[dict]:
        activities = (
            self._session.query(ExternalActivity)
            .filter(ExternalActivity.project_id == project_id)
            .order_by(ExternalActivity.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": a.id, "source": a.source, "summary": a.summary,
                "attribution": a.attribution, "user_note": a.user_note,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in activities
        ]

    @staticmethod
    def _compute_confidence(
        resume: ProjectResumeState,
        ws: ProjectWorkspaceState | None,
        plan: Plan | None,
        last_session: AgentSession | None,
    ) -> str:
        """Računa confidence nivo za resume sažetak."""
        if not plan:
            return "LOW"
        if not last_session:
            return "LOW"
        if ws and ws.reconciliation_status != "CURRENT":
            return "MEDIUM"
        if resume.open_blockers_json:
            return "MEDIUM"
        return "HIGH"
