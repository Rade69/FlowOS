"""EvidenceBundle — read model koji objedinjuje sve dokaze za plan stavku.

Konsoliduje: session → commits → changed files → verification → report → conflicts
Koristi se za: brzi dokazi panel, nezavisnu provjeru, handoff, audit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session


@dataclass
class EvidenceBundle:
    """Svi dokazi za jednu PlanItem stavku."""

    plan_item_id: str
    plan_item_key: str | None = None
    primary_session_id: str | None = None
    agent_type: str | None = None
    base_commit_sha: str | None = None
    result_commit_sha: str | None = None
    changed_files: list[str] = field(default_factory=list)
    verification_artifact_id: str | None = None
    verification_passed: bool | None = None
    report_id: str | None = None
    report_verdict: str | None = None
    conflict_ids: list[str] = field(default_factory=list)
    open_conflicts: int = 0
    criteria: list[dict] = field(default_factory=list)


class EvidenceService:
    """Gradi EvidenceBundle za plan stavku iz svih trajnih izvora."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def build(self, plan_item_id: str) -> EvidenceBundle | None:
        """Kreira EvidenceBundle za datu plan stavku."""
        from flowos.service.services.infrastructure.persistence.activity_models import FileActivity
        from flowos.service.services.infrastructure.persistence.conflict_models import Conflict
        from flowos.service.services.infrastructure.persistence.models import AgentSession
        from flowos.service.services.infrastructure.persistence.plan_models import (
            PlanItem,
            PlanItemCriterion,
        )
        from flowos.service.services.infrastructure.persistence.report_models import AgentReport

        plan_item = self._db.get(PlanItem, plan_item_id)
        if not plan_item:
            return None

        bundle = EvidenceBundle(
            plan_item_id=plan_item_id,
            plan_item_key=plan_item.item_key if hasattr(plan_item, 'item_key') else None,
        )

        # ID projekta iz plana
        project_id = (
            plan_item.plan.phase.project_id
            if hasattr(plan_item, 'plan') and plan_item.plan and plan_item.plan.phase
            else None
        )

        # Primarna sesija za ovu plan stavku (najnovija)
        session = (
            self._db.query(AgentSession)
            .filter(AgentSession.plan_item_id == plan_item_id)
            .order_by(AgentSession.started_at.desc())
            .first()
        )
        if session:
            bundle.primary_session_id = session.id
            bundle.agent_type = session.agent_type
            bundle.base_commit_sha = session.base_commit_sha
            bundle.result_commit_sha = session.result_commit_sha

            # Izmenjeni fajlovi iz FileActivity
            activities = (
                self._db.query(FileActivity)
                .filter(FileActivity.session_id == session.id)
                .all()
            )
            bundle.changed_files = list({a.file_path for a in activities})

        # Verifikacija — pronađi VERIFY_RESULT event
        if session:
            from flowos.service.services.infrastructure.persistence.models import SessionEvent

            verify_event = (
                self._db.query(SessionEvent)
                .filter(
                    SessionEvent.session_id == session.id,
                    SessionEvent.event_type == "VERIFY_RESULT",
                )
                .order_by(SessionEvent.occurred_at.desc())
                .first()
            )
            if verify_event and verify_event.payload_json:
                import json

                try:
                    payload = json.loads(verify_event.payload_json)
                    bundle.verification_artifact_id = payload.get("artifact_id")
                    bundle.verification_passed = payload.get("success")
                except (json.JSONDecodeError, TypeError):
                    pass

        # Izveštaj
        report = (
            self._db.query(AgentReport)
            .filter(AgentReport.session_id == session.id if session else None)
            .order_by(AgentReport.created_at.desc())
            .first()
        ) if session else None
        if report:
            bundle.report_id = report.id
            bundle.report_verdict = report.user_verdict

        # Konflikti — samo oni vezani za ovaj plan item/sesiju/worktree
        if session:
            changed = set(bundle.changed_files)
            conflicts = (
                self._db.query(Conflict)
                .filter(Conflict.project_id == project_id)
                .all()
            )
            relevant: list[Conflict] = []
            for c in conflicts:
                if c.status != "OPEN":
                    continue
                if c.file_path and c.file_path in changed:
                    relevant.append(c)
            if not relevant:
                relevant = [c for c in conflicts if c.status == "OPEN"][:3]
            bundle.conflict_ids = [c.id for c in relevant]
            bundle.open_conflicts = len(bundle.conflict_ids)

        # Kriterijumi
        criteria = (
            self._db.query(PlanItemCriterion)
            .filter(PlanItemCriterion.plan_item_id == plan_item_id)
            .all()
        )
        for c in criteria:
            bundle.criteria.append({
                "criterion_id": c.id,
                "description": c.description,
                "status": c.status,
                "evidence_artifact_id": c.evidence_artifact_id,
            })

        return bundle
