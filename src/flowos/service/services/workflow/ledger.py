"""Workflow Ledger service.

Phase 3A appenduje samo IMPLEMENTATION_COMPLETED događaje iz canonical DB
AgentReport-a. Service ne nudi update/delete contract jer je Ledger append-only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from flowos.service.services.infrastructure.persistence.models import (
    AgentSession,
    SessionTaskBinding,
)
from flowos.service.services.infrastructure.persistence.report_models import (
    AgentReport,
    AgentReportBindingLink,
)
from flowos.service.services.infrastructure.persistence.workflow_ledger_models import (
    WorkflowLedgerEvent,
)

IMPLEMENTATION_COMPLETED = "IMPLEMENTATION_COMPLETED"
AGENT_REPORT_SOURCE = "agent_report"


@dataclass(frozen=True)
class _TargetGroup:
    target_kind: str
    target_id: str
    task_id: str | None
    plan_item_id: str | None
    binding_link_ids: list[str]
    session_task_binding_ids: list[str]
    resolved_plan_item_ids: list[str]


@dataclass
class _TargetAccumulator:
    target_kind: str
    target_id: str
    task_id: str | None
    binding_link_ids: set[str]
    session_task_binding_ids: set[str]
    resolved_plan_item_ids: set[str]


class WorkflowLedgerService:
    """Jedini backend writer za Workflow Ledger događaje."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def append_implementation_completed_from_report(
        self, report_id: str
    ) -> list[WorkflowLedgerEvent]:
        """Appenduje IMPLEMENTATION_COMPLETED evente za qualifying AgentReport.

        Vraća postojeće ili novo-kreirane evente. Non-qualifying reporti su
        deterministički no-op i ne koriste heuristike.
        """
        report = self._session.get(AgentReport, report_id)
        if report is None or not self._is_qualifying_report(report):
            return []

        groups = self._build_target_groups(report)
        if not groups:
            return []

        events: list[WorkflowLedgerEvent] = []
        for group in groups:
            key = self._idempotency_key(report.id, group.target_kind, group.target_id)
            existing = (
                self._session.query(WorkflowLedgerEvent)
                .filter(WorkflowLedgerEvent.idempotency_key == key)
                .one_or_none()
            )
            if existing is not None:
                events.append(existing)
                continue

            payload = {
                "source_report_id": report.source_report_id,
                "source_path": report.source_path,
                "source_content_sha256": report.source_content_sha256,
                "report_type": report.report_type,
                "work_status": report.work_status,
                "target_kind": group.target_kind,
                "target_id": group.target_id,
                "binding_link_ids": group.binding_link_ids,
                "session_task_binding_ids": group.session_task_binding_ids,
                "resolved_plan_item_ids": group.resolved_plan_item_ids,
            }
            if group.task_id is not None:
                payload["task_id"] = group.task_id
            if group.plan_item_id is not None:
                payload["plan_item_id"] = group.plan_item_id

            event = WorkflowLedgerEvent(
                project_id=self._project_id_for_report(report),
                event_type=IMPLEMENTATION_COMPLETED,
                session_id=report.session_id,
                task_id=group.task_id,
                plan_item_id=group.plan_item_id,
                source_kind=AGENT_REPORT_SOURCE,
                source_id=report.id,
                occurred_at=report.created_at,
                recorded_at=datetime.now(tz=UTC),
                idempotency_key=key,
                payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            )
            self._session.add(event)
            self._session.flush()
            events.append(event)

        return events

    def list_for_project(self, project_id: str) -> list[WorkflowLedgerEvent]:
        """Vraća Ledger evente za projekat stabilno sortirane za test/read modele."""
        return (
            self._session.query(WorkflowLedgerEvent)
            .filter(WorkflowLedgerEvent.project_id == project_id)
            .order_by(WorkflowLedgerEvent.recorded_at.asc(), WorkflowLedgerEvent.id.asc())
            .all()
        )

    def list_for_task(self, task_id: str) -> list[WorkflowLedgerEvent]:
        """Vraća Ledger evente za task stabilno sortirane za test/read modele."""
        return (
            self._session.query(WorkflowLedgerEvent)
            .filter(WorkflowLedgerEvent.task_id == task_id)
            .order_by(WorkflowLedgerEvent.recorded_at.asc(), WorkflowLedgerEvent.id.asc())
            .all()
        )

    @staticmethod
    def _is_qualifying_report(report: AgentReport) -> bool:
        return (
            report.report_type == "implementation"
            and report.work_status == "completed"
            and report.source_report_id is not None
            and report.source_path is not None
            and report.source_content_sha256 is not None
            and report.session_id is not None
        )

    def _build_target_groups(self, report: AgentReport) -> list[_TargetGroup]:
        links = (
            self._session.query(AgentReportBindingLink)
            .filter(AgentReportBindingLink.report_id == report.id)
            .order_by(
                AgentReportBindingLink.session_task_binding_id.asc(),
                AgentReportBindingLink.id.asc(),
            )
            .all()
        )
        if not links:
            return []

        grouped: dict[tuple[str, str], _TargetAccumulator] = {}
        for link in links:
            binding = self._session.get(SessionTaskBinding, link.session_task_binding_id)
            if binding is None or binding.session_id != report.session_id:
                return []

            target = self._target_for_binding(binding, link)
            if target is None:
                return []
            target_kind, target_id = target
            key = (target_kind, target_id)
            entry = grouped.setdefault(
                key,
                _TargetAccumulator(
                    target_kind=target_kind,
                    target_id=target_id,
                    task_id=target_id if target_kind == "task" else None,
                    binding_link_ids=set(),
                    session_task_binding_ids=set(),
                    resolved_plan_item_ids=set(),
                ),
            )
            entry.binding_link_ids.add(link.id)
            entry.session_task_binding_ids.add(binding.id)
            if link.resolved_plan_item_id is not None:
                entry.resolved_plan_item_ids.add(link.resolved_plan_item_id)

        result: list[_TargetGroup] = []
        for key in sorted(grouped):
            entry = grouped[key]
            snapshots = sorted(entry.resolved_plan_item_ids)
            plan_item_id = None
            if entry.target_kind == "plan_item":
                plan_item_id = entry.target_id
            elif len(snapshots) == 1:
                plan_item_id = snapshots[0]
            result.append(
                _TargetGroup(
                    target_kind=entry.target_kind,
                    target_id=entry.target_id,
                    task_id=entry.task_id,
                    plan_item_id=plan_item_id,
                    binding_link_ids=sorted(entry.binding_link_ids),
                    session_task_binding_ids=sorted(entry.session_task_binding_ids),
                    resolved_plan_item_ids=snapshots,
                )
            )
        return result

    @staticmethod
    def _target_for_binding(
        binding: SessionTaskBinding, link: AgentReportBindingLink
    ) -> tuple[str, str] | None:
        if binding.task_id:
            return ("task", binding.task_id)
        if binding.plan_item_id:
            return ("plan_item", binding.plan_item_id)
        if link.resolved_plan_item_id:
            return ("plan_item", link.resolved_plan_item_id)
        return None

    @staticmethod
    def _idempotency_key(report_id: str, target_kind: str, target_id: str) -> str:
        return (
            "workflow-ledger:v1:IMPLEMENTATION_COMPLETED:"
            f"agent_report:{report_id}:{target_kind}:{target_id}"
        )

    def _project_id_for_report(self, report: AgentReport) -> str:
        session_obj = self._session.get(AgentSession, report.session_id)
        if session_obj is None:
            raise ValueError(f"Report {report.id} nema validnu AgentSession")
        return session_obj.project_id
