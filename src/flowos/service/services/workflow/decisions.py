"""WorkflowDecisionService — authority cutover za korisničke workflow odluke.

Nakon Phase 3D, WorkflowLedgerEvent(TASK_DECISION) je canonical history
korisničkih odluka. ReportService.set_verdict() delegira authority ovom servisu.
"""

from __future__ import annotations

import json
import logging
import uuid as _uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from flowos.service.services.infrastructure.persistence.models import (
    SessionTaskBinding,
)
from flowos.service.services.infrastructure.persistence.report_models import (
    AgentReport,
    AgentReportBindingLink,
)
from flowos.service.services.infrastructure.persistence.workflow_ledger_models import (
    WorkflowLedgerEvent,
)

logger = logging.getLogger("flowos.decisions")

TASK_DECISION = "TASK_DECISION"
USER_DECISION_SOURCE = "user_decision"


@dataclass(frozen=True)
class _DecisionTarget:
    """Minimalni target group za decision servis (kompatibilan sa ledger._TargetGroup)."""

    target_kind: str
    target_id: str
    task_id: str | None
    plan_item_id: str | None
    binding_link_ids: list[str]
    session_task_binding_ids: list[str]
    resolved_plan_item_ids: list[str]


class WorkflowDecisionService:
    """Authority servis za korisničke workflow odluke o task targetima."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def record_report_decision(
        self,
        report_id: str,
        verdict: str,
        notes: str | None = None,
        decision_id: str | None = None,
    ) -> AgentReport | None:
        """Zapisuje TASK_DECISION za sve dokazive targete reporta.

        Args:
            report_id: ID AgentReport-a.
            verdict: ACCEPTED, NEEDS_WORK, ili REJECTED.
            notes: Opcione napomene.
            decision_id: Opcioni UUID — ako nije dat, generiše se novi.

        Returns:
            Ažurirani AgentReport ili None.
        """
        from flowos.service.services.workflow.ledger import WorkflowLedgerService

        allowed = {"ACCEPTED", "NEEDS_WORK", "REJECTED"}
        if verdict not in allowed:
            raise ValueError(f"Nedozvoljen verdict: {verdict}. Dozvoljeni: {sorted(allowed)}")

        report = self._session.get(AgentReport, report_id)
        if not report:
            return None

        decision_id = decision_id or str(_uuid.uuid4())

        # Detektuj retry/conflict
        existing_events = self._find_existing_decision_events(decision_id)
        if existing_events is not None and len(existing_events) > 0:
            first = existing_events[0]
            payload = json.loads(first.payload_json)
            if (
                payload.get("decision") != verdict
                or payload.get("notes") != notes
                or payload.get("report_id") != report.id
            ):
                raise ValueError(
                    f"decision_id {decision_id} već postoji sa drugačijim "
                    f"verdict/notes — nije dozvoljeno menjati postojeću odluku"
                )
            # Idempotent retry — vrati postojeće stanje bez mutacije
            return report
        # decision_id ne postoji — nastavi

        decision_time = datetime.now(tz=UTC)
        previous_verdict = report.user_verdict

        # Target grouping
        ledger = WorkflowLedgerService(self._session)
        groups: list = list(ledger._build_target_groups(report))
        target_resolution = "binding_links" if groups else None

        if not groups:
            # Legacy fallback: SAMO ako report nema nikakve AgentReportBindingLink
            has_links = (
                self._session.query(AgentReportBindingLink)
                .filter(AgentReportBindingLink.report_id == report.id)
                .count()
            ) > 0
            if has_links:
                # Korumpirani linkovi (cross-session) — ne sme legacy fallback
                groups = []
            else:
                bindings = (
                    self._session.query(SessionTaskBinding)
                    .filter(
                        SessionTaskBinding.session_id == report.session_id,
                        (SessionTaskBinding.task_id.is_not(None))
                        | (SessionTaskBinding.plan_item_id.is_not(None)),
                    )
                    .order_by(
                        SessionTaskBinding.started_at.asc(),
                        SessionTaskBinding.id.asc(),
                    )
                    .all()
                )
                if len(bindings) == 1:
                    b = bindings[0]
                    kind = "task" if b.task_id else "plan_item"
                    tid = b.task_id or b.plan_item_id
                    groups = [
                        _DecisionTarget(
                            target_kind=kind,
                            target_id=tid or "",
                            task_id=b.task_id,
                            plan_item_id=b.plan_item_id,
                            binding_link_ids=[],
                            session_task_binding_ids=[b.id],
                            resolved_plan_item_ids=([b.plan_item_id] if b.plan_item_id else []),
                        )
                    ]
                    target_resolution = "legacy_single_binding"

        # Unassigned: compatibility projection bez TASK_DECISION
        if not groups:
            self._apply_compatibility_projection(
                report, verdict, notes, decision_time, previous_verdict
            )
            return report

        # Za svaki logical target — TASK_DECISION event + consequence
        for group in groups:
            key = self._decision_idempotency_key(decision_id, group.target_kind, group.target_id)
            existing = self._existing_ledger_event(key)
            if existing is not None:
                continue

            decision_payload: dict = {
                "decision_id": decision_id,
                "decision": verdict,
                "previous_decision": previous_verdict,
                "notes": notes,
                "actor_kind": "user",
                "report_id": report.id,
                "target_kind": group.target_kind,
                "target_id": group.target_id,
                "binding_link_ids": group.binding_link_ids,
                "session_task_binding_ids": group.session_task_binding_ids,
                "resolved_plan_item_ids": group.resolved_plan_item_ids,
                "target_resolution": target_resolution,
            }
            if group.task_id is not None:
                decision_payload["task_id"] = group.task_id
            if group.plan_item_id is not None:
                decision_payload["plan_item_id"] = group.plan_item_id

            # Source identity iz reporta
            if report.source_report_id:
                decision_payload["source_report_id"] = report.source_report_id
            if report.source_path:
                decision_payload["source_path"] = report.source_path
            if report.source_content_sha256:
                decision_payload["source_content_sha256"] = report.source_content_sha256

            event = WorkflowLedgerEvent(
                project_id=ledger._project_id_for_report(report),
                event_type=TASK_DECISION,
                session_id=report.session_id,
                task_id=group.task_id,
                plan_item_id=group.plan_item_id,
                source_kind=USER_DECISION_SOURCE,
                source_id=decision_id,
                occurred_at=decision_time,
                recorded_at=datetime.now(tz=UTC),
                idempotency_key=key,
                payload_json=json.dumps(decision_payload, ensure_ascii=False, sort_keys=True),
            )
            self._session.add(event)
            self._session.flush()

        # Compatibility projection
        self._apply_compatibility_projection(
            report, verdict, notes, decision_time, previous_verdict
        )

        # PlanItem consequence za NEEDS_WORK / REJECTED
        if verdict in ("NEEDS_WORK", "REJECTED"):
            self._apply_plan_item_consequences(groups, verdict)

        return report

    # ── Private helpers ───────────────────────────────────────

    def _apply_compatibility_projection(
        self,
        report: AgentReport,
        verdict: str,
        notes: str | None,
        decision_time: datetime,
        previous_verdict: str | None,
    ) -> None:
        """Ažurira AgentReport compatibility polja (ne-Ledger authority)."""
        audit_entry = {
            "timestamp": decision_time.isoformat(),
            "report_id": report.id,
            "previous_verdict": previous_verdict,
            "new_verdict": verdict,
            "previous_status": report.status,
            "new_status": "FINAL",
            "actor": "user",
            "notes": notes,
        }
        try:
            audit_list: list[dict] = json.loads(report.verdict_audit_json or "[]")
        except (json.JSONDecodeError, TypeError):
            audit_list = []
        audit_list.append(audit_entry)
        report.verdict_audit_json = json.dumps(audit_list, ensure_ascii=False)

        report.user_verdict = verdict
        report.user_notes = notes
        report.status = "FINAL"
        report.updated_at = decision_time
        self._session.flush()

    def _apply_plan_item_consequences(self, groups, verdict: str) -> None:
        """Za NEEDS_WORK/REJECTED: IMPLEMENTED/VERIFIED → IN_PROGRESS."""
        from flowos.service.services.infrastructure.persistence.plan_models import (
            PlanItem,
        )
        from flowos.service.services.plan_progress import PlanProgressService

        progress_svc = PlanProgressService(self._session)
        plan_item_ids: set[str] = set()

        for group in groups:
            if group.target_kind == "plan_item":
                plan_item_ids.add(group.target_id)
            for pid in group.resolved_plan_item_ids:
                plan_item_ids.add(pid)

        for pid in sorted(plan_item_ids):
            plan_item = self._session.get(PlanItem, pid)
            if not plan_item or plan_item.status not in ("IMPLEMENTED", "VERIFIED"):
                continue
            progress_svc.validate_transition(
                plan_item,
                "IN_PROGRESS",
                reason=f"Verdict: {verdict}",
                allow_verdict_reopen=True,
            )
            logger.info(
                "DecisionService: plan_item %s → IN_PROGRESS (verdict=%s)",
                plan_item.item_key,
                verdict,
            )

    def _find_existing_decision_events(self, decision_id: str) -> list[WorkflowLedgerEvent] | None:
        """Vraća postojeće TASK_DECISION evente za decision_id ili None."""
        events = (
            self._session.query(WorkflowLedgerEvent)
            .filter(
                WorkflowLedgerEvent.source_kind == USER_DECISION_SOURCE,
                WorkflowLedgerEvent.source_id == decision_id,
            )
            .all()
        )
        return events

    @staticmethod
    def _decision_idempotency_key(decision_id: str, target_kind: str, target_id: str) -> str:
        return (
            f"workflow-ledger:v1:TASK_DECISION:user_decision:"
            f"{decision_id}:{target_kind}:{target_id}"
        )

    def _existing_ledger_event(self, idempotency_key: str) -> WorkflowLedgerEvent | None:
        return (
            self._session.query(WorkflowLedgerEvent)
            .filter(WorkflowLedgerEvent.idempotency_key == idempotency_key)
            .one_or_none()
        )
