"""Integracioni testovi za Workflow Ledger Phase 3A.

Phase 3A uvodi samo IMPLEMENTATION_COMPLETED evente iz canonical ingested
AgentReport-a i ne mijenja PlanItem status.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import flowos.service.services.infrastructure.persistence.activity_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.report_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.workflow_ledger_models  # noqa: F401
from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.models import AgentSession, Project, Task
from flowos.service.services.infrastructure.persistence.plan_models import Plan, PlanItem, PlanPhase
from flowos.service.services.infrastructure.persistence.report_models import (
    AgentReport,
    AgentReportBindingLink,
)
from flowos.service.services.infrastructure.persistence.workflow_ledger_models import (
    WorkflowLedgerEvent,
)
from flowos.service.services.reports.ingestion import (
    AgentReportIngestionOutcome,
    AgentReportIngestionService,
)
from flowos.service.services.reports.service import ReportService
from flowos.service.services.sessions.bindings import SessionTaskBindingService
from flowos.service.services.sessions.service import SessionService
from flowos.service.services.workflow.ledger import (
    AGENT_REPORT_SOURCE,
    IMPLEMENTATION_COMPLETED,
    WorkflowLedgerService,
)


@pytest.fixture
def engine():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, connection_record):  # noqa: ARG001
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def project(db_session: Session, tmp_path: Path) -> Project:
    repo = tmp_path / "repo"
    repo.mkdir()
    project = Project(id="project-ledger", name="Ledger", repo_path=str(repo))
    db_session.add(project)
    db_session.flush()
    return project


def _plan_item(db: Session, project: Project, key: str) -> PlanItem:
    plan = (
        db.query(Plan).filter(Plan.project_id == project.id, Plan.status == "ACTIVE").one_or_none()
    )
    if plan is None:
        plan = Plan(id=f"plan-{key}", project_id=project.id, title=key, status="ACTIVE")
    phase = PlanPhase(id=f"phase-{key}", plan_id=plan.id, phase_key=key, title=key, sequence=0)
    item = PlanItem(
        id=f"item-{key}",
        plan_phase_id=phase.id,
        item_key=key,
        title=key,
        status="IN_PROGRESS",
    )
    db.add_all([plan, phase, item])
    db.flush()
    return item


def _task(db: Session, project: Project, item: PlanItem, key: str) -> Task:
    task = Task(id=f"task-{key}", project_id=project.id, title=key, plan_item_id=item.id)
    db.add(task)
    db.flush()
    return task


def _session(
    db: Session,
    project: Project,
    *,
    task_id: str | None = None,
    plan_item_id: str | None = None,
) -> AgentSession:
    return SessionService(db).create_session(
        project_id=project.id,
        agent_type="codex",
        repo_path=project.repo_path,
        task_id=task_id,
        plan_item_id=plan_item_id,
    )


def _write_report(
    repo_path: str,
    *,
    filename: str = "report.md",
    session_id: str,
    tasks: list[str],
    report_type: str = "implementation",
    work_status: str | None = "completed",
) -> Path:
    reports_dir = Path(repo_path) / "agent_reports"
    reports_dir.mkdir(exist_ok=True)
    lines = [
        "---",
        "flowos_report_version: 1",
        f"report_id: {uuid4()}",
        f"session_id: {session_id}",
        f"report_type: {report_type}",
    ]
    if work_status is not None:
        lines.append(f"work_status: {work_status}")
    lines.extend(["tasks:", *[f"  - {task}" for task in tasks]])
    lines.extend(["created_at: 2026-08-11T15:30:00+02:00", "---", "", "# Body"])
    path = reports_dir / filename
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _ingest(db: Session, project: Project, path: Path) -> AgentReportIngestionOutcome:
    return (
        AgentReportIngestionService(db)
        .ingest_file(
            path,
            project_id=project.id,
            repo_path=project.repo_path,
        )
        .outcome
    )


def _ledger_events(db: Session) -> list[WorkflowLedgerEvent]:
    return db.query(WorkflowLedgerEvent).order_by(WorkflowLedgerEvent.id.asc()).all()


def _payload(event: WorkflowLedgerEvent) -> dict:
    payload = json.loads(event.payload_json)
    assert isinstance(payload, dict)
    return payload


def test_implementation_completed_one_task_binding_creates_one_event(
    db_session: Session, project: Project
):
    item = _plan_item(db_session, project, "FLOW-017")
    task = _task(db_session, project, item, "FLOW-017")
    session = _session(db_session, project, task_id=task.id)
    path = _write_report(project.repo_path, session_id=session.id, tasks=[task.id])

    assert _ingest(db_session, project, path) == AgentReportIngestionOutcome.INGESTED

    event = db_session.query(WorkflowLedgerEvent).one()
    report = db_session.query(AgentReport).one()
    link = db_session.query(AgentReportBindingLink).one()
    assert event.event_type == IMPLEMENTATION_COMPLETED
    assert event.source_kind == AGENT_REPORT_SOURCE
    assert event.source_id == report.id
    assert event.project_id == project.id
    assert event.session_id == session.id
    assert event.task_id == task.id
    assert event.plan_item_id == item.id
    assert event.occurred_at == report.created_at
    payload = _payload(event)
    assert payload["source_report_id"] == report.source_report_id
    assert payload["source_path"] == report.source_path
    assert payload["source_content_sha256"] == report.source_content_sha256
    assert payload["report_type"] == "implementation"
    assert payload["work_status"] == "completed"
    assert payload["target_kind"] == "task"
    assert payload["target_id"] == task.id
    assert payload["binding_link_ids"] == [link.id]
    assert payload["session_task_binding_ids"] == [link.session_task_binding_id]
    assert payload["resolved_plan_item_ids"] == [item.id]


def test_same_report_retry_does_not_duplicate_event(db_session: Session, project: Project):
    item = _plan_item(db_session, project, "FLOW-017")
    task = _task(db_session, project, item, "FLOW-017")
    session = _session(db_session, project, task_id=task.id)
    path = _write_report(project.repo_path, session_id=session.id, tasks=[task.id])
    assert _ingest(db_session, project, path) == AgentReportIngestionOutcome.INGESTED

    assert _ingest(db_session, project, path) == AgentReportIngestionOutcome.ALREADY_INGESTED

    assert db_session.query(WorkflowLedgerEvent).count() == 1


def test_idempotency_key_has_db_unique_constraint(db_session: Session, project: Project):
    item = _plan_item(db_session, project, "FLOW-017")
    task = _task(db_session, project, item, "FLOW-017")
    session = _session(db_session, project, task_id=task.id)
    path = _write_report(project.repo_path, session_id=session.id, tasks=[task.id])
    assert _ingest(db_session, project, path) == AgentReportIngestionOutcome.INGESTED
    existing = db_session.query(WorkflowLedgerEvent).one()

    duplicate = WorkflowLedgerEvent(
        project_id=existing.project_id,
        event_type=existing.event_type,
        session_id=existing.session_id,
        task_id=existing.task_id,
        plan_item_id=existing.plan_item_id,
        source_kind=existing.source_kind,
        source_id=existing.source_id,
        occurred_at=existing.occurred_at,
        recorded_at=existing.recorded_at,
        idempotency_key=existing.idempotency_key,
        payload_json="{}",
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_a_b_a_same_task_creates_one_event_with_all_binding_links(
    db_session: Session, project: Project
):
    item_a = _plan_item(db_session, project, "FLOW-017")
    item_b = _plan_item(db_session, project, "FLOW-018")
    task_a = _task(db_session, project, item_a, "FLOW-017")
    task_b = _task(db_session, project, item_b, "FLOW-018")
    session = _session(db_session, project, task_id=task_a.id)
    bindings = SessionTaskBindingService(db_session)
    bindings.switch_binding(session.id, task_id=task_b.id)
    bindings.switch_binding(session.id, task_id=task_a.id)
    path = _write_report(project.repo_path, session_id=session.id, tasks=[task_a.id])

    assert _ingest(db_session, project, path) == AgentReportIngestionOutcome.INGESTED

    event = db_session.query(WorkflowLedgerEvent).one()
    payload = _payload(event)
    assert event.task_id == task_a.id
    assert len(payload["binding_link_ids"]) == 2
    assert len(payload["session_task_binding_ids"]) == 2
    assert payload["binding_link_ids"] == sorted(payload["binding_link_ids"])
    assert payload["session_task_binding_ids"] == sorted(payload["session_task_binding_ids"])


def test_two_task_targets_create_two_events(db_session: Session, project: Project):
    item_a = _plan_item(db_session, project, "FLOW-017")
    item_b = _plan_item(db_session, project, "FLOW-018")
    task_a = _task(db_session, project, item_a, "FLOW-017")
    task_b = _task(db_session, project, item_b, "FLOW-018")
    session = _session(db_session, project, task_id=task_a.id)
    SessionTaskBindingService(db_session).switch_binding(session.id, task_id=task_b.id)
    path = _write_report(project.repo_path, session_id=session.id, tasks=[task_a.id, task_b.id])

    assert _ingest(db_session, project, path) == AgentReportIngestionOutcome.INGESTED

    events = _ledger_events(db_session)
    assert len(events) == 2
    assert {event.task_id for event in events} == {task_a.id, task_b.id}
    assert {event.plan_item_id for event in events} == {item_a.id, item_b.id}


def test_direct_plan_item_target_creates_event_without_task_id(
    db_session: Session, project: Project
):
    item = _plan_item(db_session, project, "FLOW-017")
    session = _session(db_session, project)
    SessionTaskBindingService(db_session).switch_binding(session.id, plan_item_id=item.id)
    path = _write_report(project.repo_path, session_id=session.id, tasks=[item.id])

    assert _ingest(db_session, project, path) == AgentReportIngestionOutcome.INGESTED

    event = db_session.query(WorkflowLedgerEvent).one()
    payload = _payload(event)
    assert event.task_id is None
    assert event.plan_item_id == item.id
    assert payload["target_kind"] == "plan_item"
    assert payload["target_id"] == item.id


@pytest.mark.parametrize(
    ("report_type", "work_status"),
    [
        ("analysis", None),
        ("review", None),
        ("fix", "completed"),
        ("implementation", "partial"),
        ("implementation", "blocked"),
    ],
)
def test_non_qualifying_report_types_and_statuses_create_no_event(
    db_session: Session, project: Project, report_type: str, work_status: str | None
):
    item = _plan_item(db_session, project, "FLOW-017")
    task = _task(db_session, project, item, "FLOW-017")
    session = _session(db_session, project, task_id=task.id)
    path = _write_report(
        project.repo_path,
        session_id=session.id,
        tasks=[task.id],
        report_type=report_type,
        work_status=work_status,
    )

    assert _ingest(db_session, project, path) == AgentReportIngestionOutcome.INGESTED
    assert (
        db_session.query(WorkflowLedgerEvent)
        .filter(WorkflowLedgerEvent.event_type == IMPLEMENTATION_COMPLETED)
        .count()
        == 0
    )


def test_unassigned_creates_no_event(db_session: Session, project: Project):
    session = _session(db_session, project)
    path = _write_report(project.repo_path, session_id=session.id, tasks=["unassigned"])

    assert _ingest(db_session, project, path) == AgentReportIngestionOutcome.INGESTED

    assert db_session.query(WorkflowLedgerEvent).count() == 0


def test_needs_link_creates_no_report_or_event(db_session: Session, project: Project):
    session = _session(db_session, project)
    path = _write_report(project.repo_path, session_id=session.id, tasks=["FLOW-999"])

    assert _ingest(db_session, project, path) == AgentReportIngestionOutcome.NEEDS_LINK

    assert db_session.query(AgentReport).count() == 0
    assert db_session.query(WorkflowLedgerEvent).count() == 0


def test_legacy_report_never_creates_event(db_session: Session, project: Project):
    item = _plan_item(db_session, project, "FLOW-017")
    task = _task(db_session, project, item, "FLOW-017")
    session = _session(db_session, project, task_id=task.id)
    report = ReportService(db_session).create_draft(session.id)

    assert (
        WorkflowLedgerService(db_session).append_implementation_completed_from_report(report.id)
        == []
    )
    assert db_session.query(WorkflowLedgerEvent).count() == 0


def test_task_event_uses_binding_link_snapshot_not_live_task_plan_item(
    db_session: Session, project: Project
):
    item_a = _plan_item(db_session, project, "FLOW-017")
    item_b = _plan_item(db_session, project, "FLOW-018")
    task = _task(db_session, project, item_a, "FLOW-017")
    session = _session(db_session, project, task_id=task.id)
    binding = SessionTaskBindingService(db_session).get_active_binding(session.id)
    assert binding is not None
    report = ReportService(db_session).create_draft(
        session.id,
        report_type="implementation",
        work_status="completed",
        source_report_id=str(uuid4()),
        source_path=str(Path(project.repo_path) / "agent_reports" / "manual.md"),
        source_content_sha256="a" * 64,
    )
    ReportService(db_session).link_report_to_binding(report.id, binding.id)
    task.plan_item_id = item_b.id
    db_session.flush()

    [event] = WorkflowLedgerService(db_session).append_implementation_completed_from_report(
        report.id
    )

    assert event.task_id == task.id
    assert event.plan_item_id == item_a.id
    assert _payload(event)["resolved_plan_item_ids"] == [item_a.id]


def test_task_event_with_multiple_plan_snapshots_keeps_plan_item_null(
    db_session: Session, project: Project
):
    item_a = _plan_item(db_session, project, "FLOW-017")
    item_b = _plan_item(db_session, project, "FLOW-018")
    item_c = _plan_item(db_session, project, "FLOW-019")
    task_a = _task(db_session, project, item_a, "FLOW-017")
    task_b = _task(db_session, project, item_b, "FLOW-018")
    session = _session(db_session, project, task_id=task_a.id)
    bindings = SessionTaskBindingService(db_session)
    bindings.switch_binding(session.id, task_id=task_b.id)
    bindings.switch_binding(session.id, task_id=task_a.id)
    report = ReportService(db_session).create_draft(
        session.id,
        report_type="implementation",
        work_status="completed",
        source_report_id=str(uuid4()),
        source_path=str(Path(project.repo_path) / "agent_reports" / "manual-multi.md"),
        source_content_sha256="b" * 64,
    )
    task_a_bindings = [
        binding for binding in bindings.get_bindings(session.id) if binding.task_id == task_a.id
    ]
    assert len(task_a_bindings) == 2
    reports = ReportService(db_session)
    link_a = reports.link_report_to_binding(report.id, task_a_bindings[0].id)
    link_c = reports.link_report_to_binding(report.id, task_a_bindings[1].id)
    link_a.resolved_plan_item_id = item_a.id
    link_c.resolved_plan_item_id = item_c.id
    db_session.flush()

    [event] = WorkflowLedgerService(db_session).append_implementation_completed_from_report(
        report.id
    )

    assert event.task_id == task_a.id
    assert event.plan_item_id is None
    assert _payload(event)["resolved_plan_item_ids"] == [item_a.id, item_c.id]


def test_ledger_failure_rolls_back_report_links_and_events(
    db_session: Session, project: Project, monkeypatch: pytest.MonkeyPatch
):
    item = _plan_item(db_session, project, "FLOW-017")
    task = _task(db_session, project, item, "FLOW-017")
    session = _session(db_session, project, task_id=task.id)
    path = _write_report(project.repo_path, session_id=session.id, tasks=[task.id])

    def _raise(self, report_id: str):  # noqa: ARG001
        raise RuntimeError("forced ledger failure")

    monkeypatch.setattr(
        WorkflowLedgerService, "append_implementation_completed_from_report", _raise
    )

    with pytest.raises(RuntimeError, match="forced ledger failure"):
        AgentReportIngestionService(db_session).ingest_file(
            path,
            project_id=project.id,
            repo_path=project.repo_path,
        )
    db_session.rollback()

    assert db_session.query(AgentReport).count() == 0
    assert db_session.query(AgentReportBindingLink).count() == 0
    assert db_session.query(WorkflowLedgerEvent).count() == 0
