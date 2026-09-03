"""Workflow Ledger service.

Phase 3A appenduje IMPLEMENTATION_COMPLETED događaje iz canonical DB
AgentReport-a. Phase 3B dodaje TEST_RESULT događaje iz VerificationResult-a.
FLOW-1106 dodaje plan-level PLAN_ACTIVATED audit bez agentske atribucije.
Service ne nudi update/delete contract jer je Ledger append-only.
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
from flowos.service.services.verification.service import VerificationResult

IMPLEMENTATION_COMPLETED = "IMPLEMENTATION_COMPLETED"
AGENT_REPORT_SOURCE = "agent_report"

TEST_RESULT = "TEST_RESULT"
VERIFICATION_ARTIFACT_SOURCE = "verification_artifact"

REVIEW_COMPLETED = "REVIEW_COMPLETED"

PLAN_ACTIVATED = "PLAN_ACTIVATED"
PLAN_SOURCE = "plan"


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
            existing = self._existing_event(key)
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

    def append_test_result(
        self,
        *,
        project_id: str,
        session_id: str | None,
        result: VerificationResult,
    ) -> WorkflowLedgerEvent | None:
        """Appenduje TEST_RESULT event za qualifying VerificationResult.

        TEST_RESULT bilježi isključivo da je scripts/verify.py stvarno
        izvršen i proizveo konkretan PASS/FAIL/TIMEOUT ishod. Ne znači da je
        implementacija ispravna, da je review prošao ili da je PlanItem
        VERIFIED — poziv ove metode ne smije nikad mijenjati PlanItem.status.

        Event je uvijek session/project-scoped (task_id i plan_item_id
        ostaju NULL) jer scripts/verify.py nema dokazivu task-level
        atribuciju — ne izmišlja se veza sa aktivnim/istorijskim bindingom.

        Vraća None (bez ikakve mutacije) ako `result.artifact_path` nije
        postavljen — to znači da ne postoji stvarno persistovan verification
        artefakt na koji bi source_id mogao pokazivati (npr. verify.py nije
        pronađen, ili je artifact save pao). Postojeći VERIFY_RESULT
        SessionEvent ostaje jedini zapis za taj slučaj.

        Baca ValueError ako `session_id` ne odgovara postojećoj AgentSession
        koja pripada `project_id` — poziv se ne oslanja samo na parametre bez
        DB provjere.
        """
        session_obj = self._validate_session_for_project(session_id, project_id)

        if result.artifact_path is None:
            return None

        occurred_at = self._parse_verified_at(result.verified_at)
        key = self._test_result_idempotency_key(result.artifact_id)
        existing = self._existing_event(key)
        if existing is not None:
            return existing

        payload = {
            "artifact_id": result.artifact_id,
            "verify_path": result.verify_path,
            "exit_code": result.exit_code,
            "success": result.success,
            "timed_out": result.timed_out,
            "duration_seconds": result.duration_seconds,
            "artifact_path": result.artifact_path,
        }

        event = WorkflowLedgerEvent(
            project_id=project_id,
            event_type=TEST_RESULT,
            session_id=session_obj.id if session_obj else None,
            task_id=None,
            plan_item_id=None,
            source_kind=VERIFICATION_ARTIFACT_SOURCE,
            source_id=result.artifact_id,
            occurred_at=occurred_at,
            recorded_at=datetime.now(tz=UTC),
            idempotency_key=key,
            payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
        )
        self._session.add(event)
        self._session.flush()
        return event

    def list_for_project(self, project_id: str) -> list[WorkflowLedgerEvent]:
        """Vraća Ledger evente za projekat stabilno sortirane za test/read modele."""
        return (
            self._session.query(WorkflowLedgerEvent)
            .filter(WorkflowLedgerEvent.project_id == project_id)
            .order_by(WorkflowLedgerEvent.recorded_at.asc(), WorkflowLedgerEvent.id.asc())
            .all()
        )

    def append_plan_activated(
        self,
        *,
        project_id: str,
        plan_id: str,
        previous_active_plan_ids: list[str],
        occurred_at: datetime,
    ) -> WorkflowLedgerEvent:
        """Appenduje idempotentan plan-level activation audit događaj."""
        key = f"plan-activated:{plan_id}"
        existing = self._existing_event(key)
        if existing is not None:
            return existing

        payload = {
            "plan_id": plan_id,
            "project_id": project_id,
            "previous_active_plan_ids": sorted(previous_active_plan_ids),
        }
        event = WorkflowLedgerEvent(
            project_id=project_id,
            event_type=PLAN_ACTIVATED,
            session_id=None,
            task_id=None,
            plan_item_id=None,
            source_kind=PLAN_SOURCE,
            source_id=plan_id,
            occurred_at=occurred_at,
            recorded_at=datetime.now(tz=UTC),
            idempotency_key=key,
            payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
        )
        self._session.add(event)
        self._session.flush()
        return event

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

    def _existing_event(self, idempotency_key: str) -> WorkflowLedgerEvent | None:
        return (
            self._session.query(WorkflowLedgerEvent)
            .filter(WorkflowLedgerEvent.idempotency_key == idempotency_key)
            .one_or_none()
        )

    def _validate_session_for_project(
        self, session_id: str | None, project_id: str
    ) -> AgentSession | None:
        """Provjerava da session_id, ako je dat, stvarno pripada project_id.

        Ne vjeruje samo parametrima pozivaoca — poziv se odbija sa ValueError
        ako sesija ne postoji ili pripada drugom projektu.
        """
        if session_id is None:
            return None
        session_obj = self._session.get(AgentSession, session_id)
        if session_obj is None:
            raise ValueError(f"Sesija {session_id} ne postoji")
        if session_obj.project_id != project_id:
            raise ValueError(f"Sesija {session_id} ne pripada projektu {project_id}")
        return session_obj

    @staticmethod
    def _parse_verified_at(verified_at: str) -> datetime:
        """Parsira VerificationResult.verified_at u timezone-aware datetime.

        Ne pada tiho nazad na datetime.now() ako timestamp nije validan —
        occurred_at mora biti stvarno izmjereno vrijeme završetka provjere,
        ne trenutak append-a.
        """
        try:
            parsed = datetime.fromisoformat(verified_at)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"VerificationResult.verified_at nije validan ISO-8601 timestamp: {verified_at!r}"
            ) from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError(
                f"VerificationResult.verified_at mora biti timezone-aware: {verified_at!r}"
            )
        return parsed

    def _is_qualifying_review_report(self, report: AgentReport) -> bool:
        """Review report se kvalifikuje ako ima report_type=review i source identity."""
        return (
            report.report_type == "review"
            and report.source_report_id is not None
            and report.source_path is not None
            and report.source_content_sha256 is not None
            and report.session_id is not None
        )

    def append_review_completed_from_report(self, report_id: str) -> list[WorkflowLedgerEvent]:
        """Appenduje REVIEW_COMPLETED evente za qualifying review AgentReport.

        Koristi isti strogi grouping kao Phase 3A — binding.session_id
        mora odgovarati report.session_id (same-session ingestion).

        Non-qualifying reporti su deterministički no-op.
        Review za unassigned → 0 eventa.
        """

        report = self._session.get(AgentReport, report_id)
        if report is None or not self._is_qualifying_review_report(report):
            return []

        groups = self._build_target_groups(report)
        if not groups:
            return []

        reviewer_identity = self._reviewer_identity(report.session_id)

        events: list[WorkflowLedgerEvent] = []
        for group in groups:
            key = self._review_idempotency_key(report.id, group.target_kind, group.target_id)
            existing = self._existing_event(key)
            if existing is not None:
                events.append(existing)
                continue

            payload: dict = {
                "source_report_id": report.source_report_id,
                "source_path": report.source_path,
                "source_content_sha256": report.source_content_sha256,
                "report_type": report.report_type,
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
            if reviewer_identity is not None:
                payload.update(reviewer_identity)

            event = WorkflowLedgerEvent(
                project_id=self._project_id_for_report(report),
                event_type=REVIEW_COMPLETED,
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

    def _reviewer_identity(self, session_id: str) -> dict | None:
        """Snapshootuje reviewer identity iz AgentSession."""
        session_obj = self._session.get(AgentSession, session_id)
        if session_obj is None:
            return None
        identity: dict = {
            "reviewer_session_id": session_obj.id,
            "reviewer_agent_type": session_obj.agent_type,
        }
        if session_obj.model_name:
            identity["reviewer_model_name"] = session_obj.model_name
        return identity

    @staticmethod
    def _review_idempotency_key(report_id: str, target_kind: str, target_id: str) -> str:
        return (
            "workflow-ledger:v1:REVIEW_COMPLETED:"
            f"agent_report:{report_id}:{target_kind}:{target_id}"
        )

    @staticmethod
    def _test_result_idempotency_key(artifact_id: str) -> str:
        return f"workflow-ledger:v1:TEST_RESULT:verification_artifact:{artifact_id}"
