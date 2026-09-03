"""Integracioni testovi za Workflow Ledger Phase 3D — TASK_DECISION.

Phase 3D uvodi authority cutover: ReportService.set_verdict() delegira
na WorkflowDecisionService, koji kreira TASK_DECISION Ledger evente.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
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
from flowos.service.services.reports.service import ReportService
from flowos.service.services.sessions.bindings import SessionTaskBindingService
from flowos.service.services.sessions.service import SessionService
from flowos.service.services.workflow.decisions import (
    TASK_DECISION,
    USER_DECISION_SOURCE,
    WorkflowDecisionService,
)


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")

    @event.listens_for(eng, "connect")
    def _enable_foreign_keys(dbapi_connection, connection_record):  # noqa: ARG001
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def db_session(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def project(db_session: Session, tmp_path: Path) -> Project:
    repo = tmp_path / "repo"
    repo.mkdir()
    project = Project(id="project-3d", name="Ledger 3D", repo_path=str(repo))
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
        id=f"item-{key}", plan_phase_id=phase.id, item_key=key, title=key, status="IN_PROGRESS"
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
    db: Session, project: Project, *, task_id: str | None = None, plan_item_id: str | None = None
) -> AgentSession:
    return SessionService(db).create_session(
        project_id=project.id,
        agent_type="codex",
        repo_path=project.repo_path,
        task_id=task_id,
        plan_item_id=plan_item_id,
    )


def _make_report(
    db: Session,
    session_id: str,
    report_type: str = "implementation",
    work_status: str = "completed",
) -> AgentReport:
    rid = str(uuid4())
    return ReportService(db).create_draft(
        session_id,
        report_type=report_type,
        work_status=work_status,
        source_report_id=rid,
        source_path=f"/fake/{rid}.md",
        source_content_sha256="a" * 64,
    )


def _ledger_events(
    db: Session, project: Project, event_type: str = TASK_DECISION
) -> list[WorkflowLedgerEvent]:
    return (
        db.query(WorkflowLedgerEvent)
        .filter(
            WorkflowLedgerEvent.project_id == project.id,
            WorkflowLedgerEvent.event_type == event_type,
        )
        .order_by(WorkflowLedgerEvent.recorded_at.asc(), WorkflowLedgerEvent.id.asc())
        .all()
    )


# ═══════════════════════════════════════════════════════════════════
class TestTaskDecisionBasic:
    """Osnovni TASK_DECISION testovi."""

    def test_accepted_creates_task_decision(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "3d-acc")
        task = _task(db_session, project, item, "3d-acc")
        ses = _session(db_session, project, task_id=task.id)
        report = _make_report(db_session, ses.id)
        ReportService(db_session).link_report_to_binding(
            report.id, SessionTaskBindingService(db_session).get_bindings(ses.id)[0].id
        )
        db_session.flush()

        result = ReportService(db_session).set_verdict(report.id, "ACCEPTED")
        assert result is not None
        assert result.user_verdict == "ACCEPTED"
        assert result.status == "FINAL"

        events = _ledger_events(db_session, project)
        assert len(events) == 1
        e = events[0]
        assert e.event_type == TASK_DECISION
        assert e.source_kind == USER_DECISION_SOURCE
        assert e.task_id == task.id
        payload = json.loads(e.payload_json)
        assert payload["decision"] == "ACCEPTED"
        assert payload["previous_decision"] is None

    def test_needs_work_creates_task_decision(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "3d-nw")
        task = _task(db_session, project, item, "3d-nw")
        ses = _session(db_session, project, task_id=task.id)
        report = _make_report(db_session, ses.id)
        ReportService(db_session).link_report_to_binding(
            report.id, SessionTaskBindingService(db_session).get_bindings(ses.id)[0].id
        )
        db_session.flush()

        ReportService(db_session).set_verdict(report.id, "NEEDS_WORK")
        events = _ledger_events(db_session, project)
        assert len(events) == 1
        payload = json.loads(events[0].payload_json)
        assert payload["decision"] == "NEEDS_WORK"

    def test_rejected_creates_task_decision(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "3d-rej")
        task = _task(db_session, project, item, "3d-rej")
        ses = _session(db_session, project, task_id=task.id)
        report = _make_report(db_session, ses.id)
        ReportService(db_session).link_report_to_binding(
            report.id, SessionTaskBindingService(db_session).get_bindings(ses.id)[0].id
        )
        db_session.flush()

        ReportService(db_session).set_verdict(report.id, "REJECTED")
        events = _ledger_events(db_session, project)
        assert len(events) == 1
        payload = json.loads(events[0].payload_json)
        assert payload["decision"] == "REJECTED"

    def test_accepted_does_not_change_plan_item(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "3d-nochange")
        item.status = "IMPLEMENTED"
        task = _task(db_session, project, item, "3d-nochange")
        ses = _session(db_session, project, task_id=task.id)
        report = _make_report(db_session, ses.id)
        ReportService(db_session).link_report_to_binding(
            report.id, SessionTaskBindingService(db_session).get_bindings(ses.id)[0].id
        )
        db_session.flush()

        ReportService(db_session).set_verdict(report.id, "ACCEPTED")
        db_session.refresh(item)
        assert item.status == "IMPLEMENTED"

    def test_needs_work_reopens_implemented(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "3d-impl")
        item.status = "IMPLEMENTED"
        task = _task(db_session, project, item, "3d-impl")
        ses = _session(db_session, project, task_id=task.id)
        report = _make_report(db_session, ses.id)
        ReportService(db_session).link_report_to_binding(
            report.id, SessionTaskBindingService(db_session).get_bindings(ses.id)[0].id
        )
        db_session.flush()

        ReportService(db_session).set_verdict(report.id, "NEEDS_WORK")
        db_session.refresh(item)
        assert item.status == "IN_PROGRESS"

    def test_needs_work_reopens_verified(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "3d-ver")
        item.status = "VERIFIED"
        task = _task(db_session, project, item, "3d-ver")
        ses = _session(db_session, project, task_id=task.id)
        report = _make_report(db_session, ses.id)
        ReportService(db_session).link_report_to_binding(
            report.id, SessionTaskBindingService(db_session).get_bindings(ses.id)[0].id
        )
        db_session.flush()

        ReportService(db_session).set_verdict(report.id, "NEEDS_WORK")
        db_session.refresh(item)
        assert item.status == "IN_PROGRESS"


class TestTaskDecisionMultiTarget:
    """Multi-target i A-B-A testovi."""

    def test_two_targets_produce_two_events(self, db_session: Session, project: Project):
        item_a = _plan_item(db_session, project, "A")
        item_b = _plan_item(db_session, project, "B")
        task_a = _task(db_session, project, item_a, "A")
        task_b = _task(db_session, project, item_b, "B")
        ses = _session(db_session, project, task_id=task_a.id)
        bindings = SessionTaskBindingService(db_session)
        bindings.switch_binding(ses.id, task_id=task_b.id)
        report = _make_report(db_session, ses.id)
        for b in bindings.get_bindings(ses.id):
            ReportService(db_session).link_report_to_binding(report.id, b.id)
        db_session.flush()

        ReportService(db_session).set_verdict(report.id, "ACCEPTED", decision_id=str(uuid4()))
        events = _ledger_events(db_session, project)
        assert len(events) == 2
        task_ids = {e.task_id for e in events}
        assert task_ids == {task_a.id, task_b.id}


class TestTaskDecisionIdempotency:
    """Retry i conflict testovi."""

    def test_same_decision_id_retry_no_duplicate(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "retry")
        task = _task(db_session, project, item, "retry")
        ses = _session(db_session, project, task_id=task.id)
        report = _make_report(db_session, ses.id)
        ReportService(db_session).link_report_to_binding(
            report.id, SessionTaskBindingService(db_session).get_bindings(ses.id)[0].id
        )
        db_session.flush()

        did = str(uuid4())
        r1 = ReportService(db_session).set_verdict(report.id, "ACCEPTED", decision_id=did)
        r2 = ReportService(db_session).set_verdict(report.id, "ACCEPTED", decision_id=did)
        assert r1 is not None
        assert r2 is not None
        events = _ledger_events(db_session, project)
        assert len(events) == 1

    def test_same_decision_id_different_verdict_raises(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "conflict")
        task = _task(db_session, project, item, "conflict")
        ses = _session(db_session, project, task_id=task.id)
        report = _make_report(db_session, ses.id)
        ReportService(db_session).link_report_to_binding(
            report.id, SessionTaskBindingService(db_session).get_bindings(ses.id)[0].id
        )
        db_session.flush()

        did = str(uuid4())
        ReportService(db_session).set_verdict(report.id, "NEEDS_WORK", decision_id=did)
        with pytest.raises(ValueError, match="već postoji"):
            ReportService(db_session).set_verdict(report.id, "ACCEPTED", decision_id=did)

    def test_invalid_verdict_raises(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "inv")
        task = _task(db_session, project, item, "inv")
        ses = _session(db_session, project, task_id=task.id)
        report = _make_report(db_session, ses.id)
        ReportService(db_session).link_report_to_binding(
            report.id, SessionTaskBindingService(db_session).get_bindings(ses.id)[0].id
        )
        db_session.flush()

        with pytest.raises(ValueError, match="Nedozvoljen verdict"):
            ReportService(db_session).set_verdict(report.id, "INVALID")


class TestTaskDecisionUnassigned:
    """Unassigned report — compatibility projection bez TASK_DECISION."""

    def test_unassigned_updates_compatibility_no_ledger_event(
        self, db_session: Session, project: Project
    ):
        ses = _session(db_session, project)
        report = _make_report(db_session, ses.id)
        db_session.flush()

        result = ReportService(db_session).set_verdict(report.id, "ACCEPTED")
        assert result is not None
        assert result.user_verdict == "ACCEPTED"
        assert result.status == "FINAL"
        assert len(_ledger_events(db_session, project)) == 0


class TestTaskDecisionChaining:
    """D1 → D2 chaining."""

    def test_needs_work_then_accepted_keeps_both(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "chain")
        item.status = "IMPLEMENTED"
        task = _task(db_session, project, item, "chain")
        ses = _session(db_session, project, task_id=task.id)
        report = _make_report(db_session, ses.id)
        ReportService(db_session).link_report_to_binding(
            report.id, SessionTaskBindingService(db_session).get_bindings(ses.id)[0].id
        )
        db_session.flush()

        ReportService(db_session).set_verdict(report.id, "NEEDS_WORK")
        ReportService(db_session).set_verdict(report.id, "ACCEPTED")

        events = _ledger_events(db_session, project)
        assert len(events) == 2
        decisions = {json.loads(e.payload_json)["decision"] for e in events}
        assert decisions == {"NEEDS_WORK", "ACCEPTED"}


class TestTaskDecisionNotes:
    """Notes u payload-u."""

    def test_notes_in_payload(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "notes")
        task = _task(db_session, project, item, "notes")
        ses = _session(db_session, project, task_id=task.id)
        report = _make_report(db_session, ses.id)
        ReportService(db_session).link_report_to_binding(
            report.id, SessionTaskBindingService(db_session).get_bindings(ses.id)[0].id
        )
        db_session.flush()

        ReportService(db_session).set_verdict(report.id, "ACCEPTED", notes="Odobreno")
        events = _ledger_events(db_session, project)
        payload = json.loads(events[0].payload_json)
        assert payload["notes"] == "Odobreno"


class TestTaskDecisionPreviousDecision:
    """previous_decision tracking."""

    def test_previous_decision_recorded(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "prev")
        task = _task(db_session, project, item, "prev")
        ses = _session(db_session, project, task_id=task.id)
        report = _make_report(db_session, ses.id)
        ReportService(db_session).link_report_to_binding(
            report.id, SessionTaskBindingService(db_session).get_bindings(ses.id)[0].id
        )
        db_session.flush()

        ReportService(db_session).set_verdict(report.id, "NEEDS_WORK")
        ReportService(db_session).set_verdict(report.id, "ACCEPTED")

        events = _ledger_events(db_session, project)
        payloads = [json.loads(e.payload_json) for e in events]
        prevs = {p.get("previous_decision") for p in payloads}
        assert None in prevs
        assert "NEEDS_WORK" in prevs


# ═══════════════════════════════════════════════════════════════════
# Dodatni testovi (A-O) za potpunu pokrivenost
# ═══════════════════════════════════════════════════════════════════


class TestRejected:
    def test_rejected_reopens_implemented(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "rej-impl")
        item.status = "IMPLEMENTED"
        task = _task(db_session, project, item, "rej-impl")
        ses = _session(db_session, project, task_id=task.id)
        report = _make_report(db_session, ses.id)
        ReportService(db_session).link_report_to_binding(
            report.id, SessionTaskBindingService(db_session).get_bindings(ses.id)[0].id
        )
        db_session.flush()
        ReportService(db_session).set_verdict(report.id, "REJECTED")
        db_session.refresh(item)
        assert item.status == "IN_PROGRESS"

    def test_rejected_reopens_verified(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "rej-ver")
        item.status = "VERIFIED"
        task = _task(db_session, project, item, "rej-ver")
        ses = _session(db_session, project, task_id=task.id)
        report = _make_report(db_session, ses.id)
        ReportService(db_session).link_report_to_binding(
            report.id, SessionTaskBindingService(db_session).get_bindings(ses.id)[0].id
        )
        db_session.flush()
        ReportService(db_session).set_verdict(report.id, "REJECTED")
        db_session.refresh(item)
        assert item.status == "IN_PROGRESS"


class TestABA:
    def test_aba_produces_one_event_per_logical_target(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "aba")
        task_a = _task(db_session, project, item, "A")
        task_b = _task(db_session, project, item, "B")
        ses = _session(db_session, project, task_id=task_a.id)
        bindings = SessionTaskBindingService(db_session)
        bindings.switch_binding(ses.id, task_id=task_b.id)
        bindings.switch_binding(ses.id, task_id=task_a.id)
        report = _make_report(db_session, ses.id)
        for b in bindings.get_bindings(ses.id):
            ReportService(db_session).link_report_to_binding(report.id, b.id)
        db_session.flush()

        ReportService(db_session).set_verdict(report.id, "ACCEPTED")
        events = _ledger_events(db_session, project)
        assert len(events) == 2
        task_ids = {e.task_id for e in events}
        assert task_ids == {task_a.id, task_b.id}


class TestHistoricalDrift:
    def test_historical_plan_item_drift(self, db_session: Session, project: Project):
        item_p1 = _plan_item(db_session, project, "p1")
        item_p2 = _plan_item(db_session, project, "p2")
        # Početno stanje: P1 IMPLEMENTED, P2 ostaje NOT_STARTED/IN_PROGRESS
        item_p1.status = "IMPLEMENTED"
        item_p2.status = "IN_PROGRESS"
        task = _task(db_session, project, item_p1, "drift")
        ses = _session(db_session, project, task_id=task.id)
        # Snapshot se kreira PRE live drift-a
        report = _make_report(db_session, ses.id)
        link = ReportService(db_session).link_report_to_binding(
            report.id, SessionTaskBindingService(db_session).get_bindings(ses.id)[0].id
        )
        db_session.flush()
        # Snapshot mora biti P1
        assert link.resolved_plan_item_id == item_p1.id

        # TEK ONDA live drift
        task.plan_item_id = item_p2.id
        db_session.flush()
        assert task.plan_item_id == item_p2.id

        ReportService(db_session).set_verdict(report.id, "NEEDS_WORK")
        events = _ledger_events(db_session, project)
        assert len(events) == 1
        # TASK_DECISION historical target = P1
        assert events[0].plan_item_id == item_p1.id
        payload = json.loads(events[0].payload_json)
        assert payload["resolved_plan_item_ids"] == [item_p1.id]

        # P1: IMPLEMENTED → IN_PROGRESS
        db_session.refresh(item_p1)
        assert item_p1.status == "IN_PROGRESS"
        # P2 ostaje u prethodnom statusu (IN_PROGRESS), nije dobio consequence
        db_session.refresh(item_p2)
        assert item_p2.status == "IN_PROGRESS"


class TestMultipleSnapshots:
    def test_multiple_snapshots_null_plan_item_id(self, db_session: Session, project: Project):
        item_a = _plan_item(db_session, project, "ms-a")
        item_b = _plan_item(db_session, project, "ms-b")
        item_c = _plan_item(db_session, project, "ms-c")
        task_a = _task(db_session, project, item_a, "ms-a")
        task_b = _task(db_session, project, item_b, "ms-b")
        ses = _session(db_session, project, task_id=task_a.id)
        bindings = SessionTaskBindingService(db_session)
        bindings.switch_binding(ses.id, task_id=task_b.id)
        bindings.switch_binding(ses.id, task_id=task_a.id)
        report = _make_report(db_session, ses.id)
        task_a_bindings = [b for b in bindings.get_bindings(ses.id) if b.task_id == task_a.id]
        assert len(task_a_bindings) == 2
        link1 = ReportService(db_session).link_report_to_binding(report.id, task_a_bindings[0].id)
        link2 = ReportService(db_session).link_report_to_binding(report.id, task_a_bindings[1].id)
        link1.resolved_plan_item_id = item_a.id
        link2.resolved_plan_item_id = item_c.id
        db_session.flush()

        item_a.status = "IMPLEMENTED"
        item_c.status = "VERIFIED"
        db_session.flush()

        ReportService(db_session).set_verdict(report.id, "NEEDS_WORK")
        events = _ledger_events(db_session, project)
        assert len(events) == 1
        assert events[0].plan_item_id is None
        payload = json.loads(events[0].payload_json)
        assert len(payload["resolved_plan_item_ids"]) == 2

        # Oba historical PlanItem-a moraju dobiti consequence
        db_session.refresh(item_a)
        db_session.refresh(item_c)
        assert item_a.status == "IN_PROGRESS"
        assert item_c.status == "IN_PROGRESS"


class TestCrossProjectCorruption:
    def test_cross_project_corruption_zero_events(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "corrupt")
        task = _task(db_session, project, item, "corrupt")
        ses = _session(db_session, project, task_id=task.id)
        report = _make_report(db_session, ses.id)
        db_session.flush()

        # Drugi projekat
        other = Project(id="other-3d", name="Other", repo_path="/tmp/other")
        db_session.add(other)
        db_session.flush()
        other_ses = _session(db_session, other)
        other_bindings = SessionTaskBindingService(db_session).get_bindings(other_ses.id)
        assert len(other_bindings) >= 1

        # Direktno kreiraj korumpirani cross-project link
        corrupt_link = AgentReportBindingLink(
            report_id=report.id, session_task_binding_id=other_bindings[0].id
        )
        db_session.add(corrupt_link)
        db_session.flush()

        # Pozovi decision writer
        result = WorkflowDecisionService(db_session).record_report_decision(
            report.id, "NEEDS_WORK", decision_id=str(uuid4())
        )
        # Compatibility projection i dalje radi (unassigned-like)
        assert result is not None
        # Ali 0 TASK_DECISION
        events = _ledger_events(db_session, project)
        assert len(events) == 0


class TestRollback:
    def test_consequence_failure_rollback(self, db_session: Session, project: Project, monkeypatch):
        item = _plan_item(db_session, project, "rb")
        item.status = "IMPLEMENTED"
        task = _task(db_session, project, item, "rb")
        ses = _session(db_session, project, task_id=task.id)
        report = _make_report(db_session, ses.id)
        ReportService(db_session).link_report_to_binding(
            report.id, SessionTaskBindingService(db_session).get_bindings(ses.id)[0].id
        )
        db_session.flush()
        db_session.commit()  # commit report pre consequence failure-a

        # Snimi prethodno stanje
        prev_verdict = report.user_verdict
        prev_notes = report.user_notes
        prev_status = item.status

        original = WorkflowDecisionService._apply_plan_item_consequences

        def _failing_consequence(self, groups, verdict):
            original(self, groups, verdict)
            raise RuntimeError("forced consequence failure")

        monkeypatch.setattr(
            WorkflowDecisionService, "_apply_plan_item_consequences", _failing_consequence
        )

        with pytest.raises(RuntimeError):
            WorkflowDecisionService(db_session).record_report_decision(
                report.id, "NEEDS_WORK", decision_id=str(uuid4())
            )

        db_session.rollback()
        # Nakon rollback-a, report i item su u originalnom stanju
        refreshed_report = db_session.get(AgentReport, report.id)
        refreshed_item = db_session.get(type(item), item.id)
        assert refreshed_report.user_verdict == prev_verdict
        assert refreshed_report.user_notes == prev_notes
        assert refreshed_item.status == prev_status
        assert len(_ledger_events(db_session, project)) == 0

    def test_multi_target_partial_failure_rollback(
        self, db_session: Session, project: Project, monkeypatch
    ):
        item_a = _plan_item(db_session, project, "mt-a")
        item_b = _plan_item(db_session, project, "mt-b")
        item_a.status = "IMPLEMENTED"
        item_b.status = "IMPLEMENTED"
        task_a = _task(db_session, project, item_a, "mt-a")
        task_b = _task(db_session, project, item_b, "mt-b")
        ses = _session(db_session, project, task_id=task_a.id)
        bindings = SessionTaskBindingService(db_session)
        bindings.switch_binding(ses.id, task_id=task_b.id)
        report = _make_report(db_session, ses.id)
        for b in bindings.get_bindings(ses.id):
            ReportService(db_session).link_report_to_binding(report.id, b.id)
        db_session.flush()
        db_session.commit()

        prev_status_a = item_a.status
        prev_status_b = item_b.status
        prev_verdict = report.user_verdict

        original = WorkflowDecisionService._apply_plan_item_consequences

        def _fail_on_b(self, groups, verdict):
            # Consequence za task A uspe, za task B padne
            for g in groups:
                if g.task_id == task_a.id:
                    original(self, [g], verdict)
            raise RuntimeError("forced multi-target partial failure")

        monkeypatch.setattr(WorkflowDecisionService, "_apply_plan_item_consequences", _fail_on_b)

        with pytest.raises(RuntimeError):
            WorkflowDecisionService(db_session).record_report_decision(
                report.id, "NEEDS_WORK", decision_id=str(uuid4())
            )

        db_session.rollback()
        refreshed_a = db_session.get(type(item_a), item_a.id)
        refreshed_b = db_session.get(type(item_b), item_b.id)
        refreshed_report = db_session.get(AgentReport, report.id)
        assert refreshed_a.status == prev_status_a
        assert refreshed_b.status == prev_status_b
        assert refreshed_report.user_verdict == prev_verdict
        assert len(_ledger_events(db_session, project)) == 0


class TestDecisionIdConflict:
    def test_conflict_notes(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "c-notes")
        task = _task(db_session, project, item, "c-notes")
        ses = _session(db_session, project, task_id=task.id)
        report = _make_report(db_session, ses.id)
        ReportService(db_session).link_report_to_binding(
            report.id, SessionTaskBindingService(db_session).get_bindings(ses.id)[0].id
        )
        db_session.flush()
        did = str(uuid4())
        ReportService(db_session).set_verdict(report.id, "NEEDS_WORK", notes="A", decision_id=did)
        with pytest.raises(ValueError, match="već postoji"):
            ReportService(db_session).set_verdict(
                report.id, "NEEDS_WORK", notes="B", decision_id=did
            )

    def test_conflict_report(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "c-report")
        task = _task(db_session, project, item, "c-report")
        ses = _session(db_session, project, task_id=task.id)
        report1 = _make_report(db_session, ses.id)
        report2 = _make_report(db_session, ses.id)
        for r in [report1, report2]:
            ReportService(db_session).link_report_to_binding(
                r.id, SessionTaskBindingService(db_session).get_bindings(ses.id)[0].id
            )
        db_session.flush()
        did = str(uuid4())
        ReportService(db_session).set_verdict(report1.id, "NEEDS_WORK", decision_id=did)
        with pytest.raises(ValueError, match="već postoji"):
            ReportService(db_session).set_verdict(report2.id, "NEEDS_WORK", decision_id=did)


class TestAcceptedNoAdvance:
    def test_accepted_no_done_no_verified(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "noadv")
        item.status = "IMPLEMENTED"
        task = _task(db_session, project, item, "noadv")
        ses = _session(db_session, project, task_id=task.id)
        report = _make_report(db_session, ses.id)
        ReportService(db_session).link_report_to_binding(
            report.id, SessionTaskBindingService(db_session).get_bindings(ses.id)[0].id
        )
        db_session.flush()
        ReportService(db_session).set_verdict(report.id, "ACCEPTED")
        db_session.refresh(item)
        assert item.status == "IMPLEMENTED"
        assert item.status not in ("DONE", "VERIFIED")


class TestEventBoundary:
    def test_no_finding_decided_no_user_validation(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "boundary")
        task = _task(db_session, project, item, "boundary")
        ses = _session(db_session, project, task_id=task.id)
        report = _make_report(db_session, ses.id)
        ReportService(db_session).link_report_to_binding(
            report.id, SessionTaskBindingService(db_session).get_bindings(ses.id)[0].id
        )
        db_session.flush()
        ReportService(db_session).set_verdict(report.id, "ACCEPTED")

        all_events = db_session.query(WorkflowLedgerEvent).all()
        event_types = {e.event_type for e in all_events}
        assert "FINDING_DECIDED" not in event_types
        assert "USER_VALIDATION" not in event_types
        assert TASK_DECISION in event_types


class TestLegacyFallback:
    def test_single_binding_legacy_creates_task_decision(
        self, db_session: Session, project: Project
    ):
        item = _plan_item(db_session, project, "legacy-1")
        task = _task(db_session, project, item, "legacy-1")
        ses = _session(db_session, project, task_id=task.id)
        # Report BEZ AgentReportBindingLink — samo legacy binding
        report = _make_report(db_session, ses.id)
        db_session.flush()
        # NE dodaj link_report_to_binding — simuliraj legacy

        ReportService(db_session).set_verdict(report.id, "ACCEPTED")
        events = _ledger_events(db_session, project)
        assert len(events) == 1
        payload = json.loads(events[0].payload_json)
        assert payload["target_resolution"] == "legacy_single_binding"

    def test_ambiguous_legacy_zero_events(self, db_session: Session, project: Project):
        item_a = _plan_item(db_session, project, "amb-a")
        item_b = _plan_item(db_session, project, "amb-b")
        task_a = _task(db_session, project, item_a, "amb-a")
        task_b = _task(db_session, project, item_b, "amb-b")
        ses = _session(db_session, project, task_id=task_a.id)
        SessionTaskBindingService(db_session).switch_binding(ses.id, task_id=task_b.id)
        report = _make_report(db_session, ses.id)
        db_session.flush()

        result = ReportService(db_session).set_verdict(report.id, "ACCEPTED")
        assert result is not None
        assert result.user_verdict == "ACCEPTED"
        assert len(_ledger_events(db_session, project)) == 0
