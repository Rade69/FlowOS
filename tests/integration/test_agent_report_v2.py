"""Regresioni testovi za AgentReport v2 vezu sa SessionTaskBinding istorijom."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.models import AgentSession, Project, Task
from flowos.service.services.infrastructure.persistence.plan_models import Plan, PlanItem, PlanPhase
from flowos.service.services.infrastructure.persistence.report_models import (
    AgentReport,
    AgentReportBindingLink,
)
from flowos.service.services.reports.service import ReportService
from flowos.service.services.sessions.bindings import SessionTaskBindingService
from flowos.service.services.sessions.service import SessionService
from flowos.service.services.tasks.service import TaskService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, connection_record):  # noqa: ARG001
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _project(db: Session) -> Project:
    project = Project(id="project-report-v2", name="Report v2", repo_path="C:/report-v2")
    db.add(project)
    db.flush()
    return project


def _plan_item(db: Session, project: Project, key: str) -> PlanItem:
    plan = (
        db.query(Plan).filter(Plan.project_id == project.id, Plan.status == "ACTIVE").one_or_none()
    )
    if plan is None:
        plan = Plan(id=f"plan-{key}", project_id=project.id, title=key, status="ACTIVE")
    phase = PlanPhase(id=f"phase-{key}", plan_id=plan.id, phase_key=key, title=key, sequence=0)
    item = PlanItem(
        id=f"item-{key}", plan_phase_id=phase.id, item_key=key, title=key, status="IMPLEMENTED"
    )
    db.add_all([plan, phase, item])
    db.flush()
    return item


def _task(db: Session, project: Project, item: PlanItem, key: str) -> Task:
    task = Task(id=f"task-{key}", project_id=project.id, title=key, plan_item_id=item.id)
    db.add(task)
    db.flush()
    return task


def _session(db: Session, project: Project, task_id: str | None = None) -> AgentSession:
    return SessionService(db).create_session(
        project_id=project.id,
        agent_type="codex",
        repo_path=project.repo_path,
        task_id=task_id,
    )


def test_legacy_report_and_implementation_semantics_remain_supported(
    db_session: Session,
):
    project = _project(db_session)
    session = _session(db_session, project)
    service = ReportService(db_session)

    legacy = service.create_draft(session.id)
    implementation = service.create_draft(
        session.id, report_type="implementation", work_status="completed"
    )

    assert legacy.report_type is None
    assert legacy.work_status is None
    assert implementation.report_type == "implementation"
    assert implementation.work_status == "completed"
    with pytest.raises(ValueError, match="Nedozvoljen work_status"):
        service.create_draft(session.id, work_status="verified")

    db_session.add(AgentReport(session_id=session.id, work_status="invalid"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_report_links_one_and_multiple_bindings_and_rejects_duplicates(db_session: Session):
    project = _project(db_session)
    item_a = _plan_item(db_session, project, "A")
    item_b = _plan_item(db_session, project, "B")
    task_a = _task(db_session, project, item_a, "A")
    task_b = _task(db_session, project, item_b, "B")
    session = _session(db_session, project, task_a.id)
    bindings = SessionTaskBindingService(db_session)
    binding_a = bindings.get_active_binding(session.id)
    assert binding_a is not None
    binding_b = bindings.switch_binding(session.id, task_id=task_b.id)
    report_service = ReportService(db_session)
    report = report_service.create_draft(session.id)

    report_service.link_report_to_binding(report.id, binding_a.id)
    report_service.link_report_to_binding(report.id, binding_b.id)

    assert len(report.binding_links) == 2
    assert {link.resolved_plan_item_id for link in report.binding_links} == {item_a.id, item_b.id}
    with pytest.raises(ValueError, match="već povezan"):
        report_service.link_report_to_binding(report.id, binding_a.id)


def test_report_rejects_binding_from_another_session(db_session: Session):
    project = _project(db_session)
    first = _session(db_session, project)
    second = _session(db_session, project)
    binding = SessionTaskBindingService(db_session).get_active_binding(second.id)
    assert binding is not None
    report = ReportService(db_session).create_draft(first.id)

    with pytest.raises(ValueError, match="istoj sesiji"):
        ReportService(db_session).link_report_to_binding(report.id, binding.id)


def test_deleting_report_cascades_links_but_linked_binding_is_restricted(db_session: Session):
    project = _project(db_session)
    session = _session(db_session, project)
    binding = SessionTaskBindingService(db_session).get_active_binding(session.id)
    assert binding is not None
    report = ReportService(db_session).create_draft(session.id)
    ReportService(db_session).link_report_to_binding(report.id, binding.id)
    report_id = report.id
    db_session.commit()

    db_session.delete(binding)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()

    report = db_session.get(AgentReport, report_id)
    assert report is not None
    db_session.delete(report)
    db_session.flush()
    assert db_session.query(AgentReportBindingLink).count() == 0


def test_linked_report_reopens_original_plan_item_not_current_session_pointer(db_session: Session):
    project = _project(db_session)
    item_a = _plan_item(db_session, project, "A")
    item_b = _plan_item(db_session, project, "B")
    task_a = _task(db_session, project, item_a, "A")
    task_b = _task(db_session, project, item_b, "B")
    session = _session(db_session, project, task_a.id)
    bindings = SessionTaskBindingService(db_session)
    binding_a = bindings.get_active_binding(session.id)
    assert binding_a is not None
    bindings.switch_binding(session.id, task_id=task_b.id)
    assert session.plan_item_id == item_b.id

    reports = ReportService(db_session)
    report = reports.create_draft(session.id)
    reports.link_report_to_binding(report.id, binding_a.id)
    reports.set_verdict(report.id, "NEEDS_WORK")

    assert item_a.status == "IN_PROGRESS"
    assert item_b.status == "IMPLEMENTED"


def test_multi_binding_report_reopens_each_unique_plan_item(db_session: Session):
    project = _project(db_session)
    item_a = _plan_item(db_session, project, "A")
    item_b = _plan_item(db_session, project, "B")
    task_a = _task(db_session, project, item_a, "A")
    task_b = _task(db_session, project, item_b, "B")
    session = _session(db_session, project, task_a.id)
    bindings = SessionTaskBindingService(db_session)
    binding_a = bindings.get_active_binding(session.id)
    assert binding_a is not None
    binding_b = bindings.switch_binding(session.id, task_id=task_b.id)
    reports = ReportService(db_session)
    report = reports.create_draft(session.id)
    reports.link_report_to_binding(report.id, binding_a.id)
    reports.link_report_to_binding(report.id, binding_b.id)

    reports.set_verdict(report.id, "REJECTED")

    assert item_a.status == "IN_PROGRESS"
    assert item_b.status == "IN_PROGRESS"


def test_link_snapshots_task_plan_item_before_task_drift(db_session: Session):
    project = _project(db_session)
    item_a = _plan_item(db_session, project, "A")
    item_b = _plan_item(db_session, project, "B")
    task = _task(db_session, project, item_a, "T")
    session = _session(db_session, project, task.id)
    binding = SessionTaskBindingService(db_session).get_active_binding(session.id)
    assert binding is not None
    reports = ReportService(db_session)
    report = reports.create_draft(session.id)
    link = reports.link_report_to_binding(report.id, binding.id)

    assert link.resolved_plan_item_id == item_a.id
    updated = TaskService(db_session).update_task(task.id, plan_item_id=item_b.id)
    assert updated is not None
    reports.set_verdict(report.id, "NEEDS_WORK")

    assert item_a.status == "IN_PROGRESS"
    assert item_b.status == "IMPLEMENTED"


@pytest.mark.parametrize("initial_status", ["IMPLEMENTED", "VERIFIED"])
def test_linked_report_can_governed_reopen_supported_terminal_states(
    db_session: Session, initial_status: str
):
    project = _project(db_session)
    item = _plan_item(db_session, project, "A")
    item.status = initial_status
    session = _session(db_session, project)
    binding = SessionTaskBindingService(db_session).switch_binding(session.id, plan_item_id=item.id)
    reports = ReportService(db_session)
    report = reports.create_draft(session.id)
    reports.link_report_to_binding(report.id, binding.id)

    reports.set_verdict(report.id, "NEEDS_WORK")

    assert item.status == "IN_PROGRESS"


def test_unassigned_link_does_not_reopen_plan_item(db_session: Session):
    project = _project(db_session)
    item = _plan_item(db_session, project, "A")
    session = _session(db_session, project)
    binding = SessionTaskBindingService(db_session).get_active_binding(session.id)
    assert binding is not None
    report_service = ReportService(db_session)
    report = report_service.create_draft(session.id)
    report_service.link_report_to_binding(report.id, binding.id)

    report_service.set_verdict(report.id, "NEEDS_WORK")

    assert item.status == "IMPLEMENTED"


def test_legacy_report_uses_only_one_historical_binding_as_safe_fallback(db_session: Session):
    project = _project(db_session)
    item = _plan_item(db_session, project, "A")
    session = _session(db_session, project)
    SessionTaskBindingService(db_session).switch_binding(session.id, plan_item_id=item.id)
    report = ReportService(db_session).create_draft(session.id)

    ReportService(db_session).set_verdict(report.id, "NEEDS_WORK")

    assert item.status == "IN_PROGRESS"


def test_legacy_report_with_multiple_bindings_does_not_use_current_pointer(db_session: Session):
    project = _project(db_session)
    item_a = _plan_item(db_session, project, "A")
    item_b = _plan_item(db_session, project, "B")
    task_a = _task(db_session, project, item_a, "A")
    task_b = _task(db_session, project, item_b, "B")
    session = _session(db_session, project, task_a.id)
    SessionTaskBindingService(db_session).switch_binding(session.id, task_id=task_b.id)
    assert session.plan_item_id == item_b.id
    report = ReportService(db_session).create_draft(session.id)

    ReportService(db_session).set_verdict(report.id, "NEEDS_WORK")

    assert item_a.status == "IMPLEMENTED"
    assert item_b.status == "IMPLEMENTED"
