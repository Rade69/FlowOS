"""Integracioni testovi za Workflow Ledger Phase 3C — REVIEW_COMPLETED.

Phase 3C uvodi REVIEW_COMPLETED evente iz canonical ingested review
AgentReport-a. Ne menja PlanItem status, ne koristi verdict, i ne parsira
Markdown body.
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
from flowos.service.services.infrastructure.persistence.models import (
    AgentSession,
    Project,
    Task,
)
from flowos.service.services.infrastructure.persistence.plan_models import (
    Plan,
    PlanItem,
    PlanPhase,
)
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
    REVIEW_COMPLETED,
    WorkflowLedgerService,
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
    project = Project(id="project-3c", name="Ledger 3C", repo_path=str(repo))
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
    db: Session, project: Project, *, task_id: str | None = None, plan_item_id: str | None = None
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
    report_type: str = "review",
    work_status: str | None = None,
) -> Path:
    report_dir = Path(repo_path) / "agent_reports"
    report_dir.mkdir(exist_ok=True)
    report_id = str(uuid4()).replace("-", "")
    tasks_yaml = "\n".join(f"  - {t}" for t in tasks)
    front_matter = (
        f"---\n"
        f"flowos_report_version: 1\n"
        f"report_id: {report_id}\n"
        f"agent: codex\n"
        f"model: gpt-5\n"
        f"session_id: {session_id}\n"
        f"report_type: {report_type}\n"
    )
    if work_status is not None:
        front_matter += f"work_status: {work_status}\n"
    front_matter += (
        f"tasks:\n"
        f"{tasks_yaml}\n"
        f"commits: []\n"
        f"created_at: 2026-08-12T10:00:00+02:00\n"
        f"---\n"
        f"\n# Review Report\n\nContent here.\n"
    )
    report_path = report_dir / filename
    report_path.write_text(front_matter, encoding="utf-8")
    return report_path


def _ingest(db: Session, project: Project, path: Path) -> AgentReport:
    result = AgentReportIngestionService(db).ingest_file(
        path, project_id=project.id, repo_path=project.repo_path
    )
    assert result.outcome == AgentReportIngestionOutcome.INGESTED, result.message
    report = (
        db.query(AgentReport).filter(AgentReport.source_report_id == result.source_report_id).one()
    )
    return report


def _ledger_events(
    db: Session, project: Project, event_type: str = REVIEW_COMPLETED
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
# Phase 3C core tests
# ═══════════════════════════════════════════════════════════════════


class TestReviewCompletedBasic:
    """Osnovni REVIEW_COMPLETED testovi."""

    def test_canonical_review_with_task_binding_produces_one_event(
        self, db_session: Session, project: Project
    ):
        item = _plan_item(db_session, project, "3c-1")
        task = _task(db_session, project, item, "3c-1")
        reviewer = _session(db_session, project, task_id=task.id)
        report_path = _write_report(
            project.repo_path, session_id=reviewer.id, tasks=[task.id], report_type="review"
        )
        report = _ingest(db_session, project, report_path)

        events = _ledger_events(db_session, project)
        assert len(events) == 1
        e = events[0]
        assert e.event_type == REVIEW_COMPLETED
        assert e.source_id == report.id
        assert e.task_id == task.id
        payload = json.loads(e.payload_json)
        assert payload["target_kind"] == "task"
        assert payload["target_id"] == task.id
        assert payload["reviewer_session_id"] == reviewer.id

    def test_two_task_targets_produce_two_events(self, db_session: Session, project: Project):
        item_a = _plan_item(db_session, project, "A")
        item_b = _plan_item(db_session, project, "B")
        task_a = _task(db_session, project, item_a, "A")
        task_b = _task(db_session, project, item_b, "B")
        reviewer = _session(db_session, project, task_id=task_a.id)

        # Switch na task_b da bi oba taska imala binding istoriju
        svc = SessionTaskBindingService(db_session)
        svc.switch_binding(reviewer.id, task_id=task_b.id)
        db_session.flush()

        report_path = _write_report(
            project.repo_path,
            session_id=reviewer.id,
            tasks=[task_a.id, task_b.id],
            report_type="review",
        )
        _ingest(db_session, project, report_path)

        events = _ledger_events(db_session, project)
        assert len(events) == 2
        task_ids = {e.task_id for e in events}
        assert task_ids == {task_a.id, task_b.id}

    def test_aba_produces_one_event_per_logical_target(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "aba")
        task_a = _task(db_session, project, item, "A")
        task_b = _task(db_session, project, item, "B")
        reviewer = _session(db_session, project, task_id=task_a.id)
        svc = SessionTaskBindingService(db_session)
        svc.switch_binding(reviewer.id, task_id=task_b.id)
        svc.switch_binding(reviewer.id, task_id=task_a.id)
        db_session.flush()

        # A-B-A: task_a se pojavljuje dvaput u binding istoriji
        report_path = _write_report(
            project.repo_path,
            session_id=reviewer.id,
            tasks=[task_a.id, task_b.id, task_a.id],
            report_type="review",
        )
        _ingest(db_session, project, report_path)

        events = _ledger_events(db_session, project)
        assert len(events) == 2
        task_ids = {e.task_id for e in events}
        assert task_ids == {task_a.id, task_b.id}

    def test_direct_plan_item_review_produces_one_event(
        self, db_session: Session, project: Project
    ):
        item = _plan_item(db_session, project, "3c-pi")
        reviewer = _session(db_session, project, plan_item_id=item.id)
        report_path = _write_report(
            project.repo_path, session_id=reviewer.id, tasks=[item.id], report_type="review"
        )
        _ingest(db_session, project, report_path)

        events = _ledger_events(db_session, project)
        assert len(events) == 1
        e = events[0]
        assert e.plan_item_id == item.id
        payload = json.loads(e.payload_json)
        assert payload["target_kind"] == "plan_item"
        assert payload["target_id"] == item.id

    def test_unassigned_review_produces_zero_events(self, db_session: Session, project: Project):
        reviewer = _session(db_session, project)
        report_path = _write_report(
            project.repo_path, session_id=reviewer.id, tasks=["unassigned"], report_type="review"
        )
        _ingest(db_session, project, report_path)

        events = _ledger_events(db_session, project)
        assert len(events) == 0

    def test_analysis_report_produces_zero_review_events(
        self, db_session: Session, project: Project
    ):
        item = _plan_item(db_session, project, "analysis")
        task = _task(db_session, project, item, "analysis")
        reviewer = _session(db_session, project, task_id=task.id)
        report_path = _write_report(
            project.repo_path, session_id=reviewer.id, tasks=[task.id], report_type="analysis"
        )
        _ingest(db_session, project, report_path)

        # Samo ingestion se desio, nema REVIEW_COMPLETED
        events = (
            db_session.query(WorkflowLedgerEvent)
            .filter(
                WorkflowLedgerEvent.project_id == project.id,
                WorkflowLedgerEvent.event_type == REVIEW_COMPLETED,
            )
            .all()
        )
        assert len(events) == 0

    def test_implementation_report_review_writer_gives_zero(
        self, db_session: Session, project: Project
    ):
        item = _plan_item(db_session, project, "impl")
        task = _task(db_session, project, item, "impl")
        ses = _session(db_session, project, task_id=task.id)
        report_path = _write_report(
            project.repo_path,
            session_id=ses.id,
            tasks=[task.id],
            report_type="implementation",
            work_status="completed",
        )
        _ingest(db_session, project, report_path)

        # IMPLEMENTATION_COMPLETED treba da postoji, ali ne i REVIEW_COMPLETED
        impl_events = _ledger_events(db_session, project, "IMPLEMENTATION_COMPLETED")
        assert len(impl_events) >= 1
        review_events = _ledger_events(db_session, project, REVIEW_COMPLETED)
        assert len(review_events) == 0

    def test_fix_report_produces_zero_review_events(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "fix")
        task = _task(db_session, project, item, "fix")
        ses = _session(db_session, project, task_id=task.id)
        report_path = _write_report(
            project.repo_path,
            session_id=ses.id,
            tasks=[task.id],
            report_type="fix",
            work_status="completed",
        )
        _ingest(db_session, project, report_path)

        events = _ledger_events(db_session, project)
        assert len(events) == 0

    def test_review_without_work_status_qualifies(self, db_session: Session, project: Project):
        """Review bez work_status polja se i dalje kvalifikuje."""
        item = _plan_item(db_session, project, "no-ws")
        task = _task(db_session, project, item, "no-ws")
        reviewer = _session(db_session, project, task_id=task.id)
        report_path = _write_report(
            project.repo_path,
            session_id=reviewer.id,
            tasks=[task.id],
            report_type="review",
            work_status=None,
        )
        _ingest(db_session, project, report_path)

        events = _ledger_events(db_session, project)
        assert len(events) == 1

    def test_direct_service_retry_no_duplicates(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "retry")
        task = _task(db_session, project, item, "retry")
        reviewer = _session(db_session, project, task_id=task.id)
        report_path = _write_report(
            project.repo_path, session_id=reviewer.id, tasks=[task.id], report_type="review"
        )
        report = _ingest(db_session, project, report_path)

        # Direktni retry
        events_1 = WorkflowLedgerService(db_session).append_review_completed_from_report(report.id)
        events_2 = WorkflowLedgerService(db_session).append_review_completed_from_report(report.id)

        assert len(events_1) == 1
        assert len(events_2) == 1
        assert events_1[0].id == events_2[0].id  # isti event
        assert len(_ledger_events(db_session, project)) == 1

    def test_db_unique_constraint_prevents_duplicate(self, db_session: Session, project: Project):
        """Stvarni DB UNIQUE constraint test — ručni duplikat se odbija."""
        item = _plan_item(db_session, project, "dedup")
        task = _task(db_session, project, item, "dedup")
        reviewer = _session(db_session, project, task_id=task.id)
        report_path = _write_report(
            project.repo_path, session_id=reviewer.id, tasks=[task.id], report_type="review"
        )
        report = _ingest(db_session, project, report_path)
        db_session.flush()

        events = _ledger_events(db_session, project)
        assert len(events) == 1

        # Pokušaj ručnog INSERT-a sa istim idempotency_key kroz savepoint
        key = WorkflowLedgerService._review_idempotency_key(report.id, "task", task.id)
        dup = WorkflowLedgerEvent(
            project_id=project.id,
            event_type=REVIEW_COMPLETED,
            session_id=reviewer.id,
            task_id=task.id,
            source_kind=AGENT_REPORT_SOURCE,
            source_id=report.id,
            occurred_at=report.created_at,
            idempotency_key=key,
            payload_json="{}",
        )
        try:
            with db_session.begin_nested():
                db_session.add(dup)
                db_session.flush()
            pytest.fail("Trebalo je da baci IntegrityError")
        except IntegrityError:
            pass  # Očekivano — savepoint rollback-ovan, originalni podaci netaknuti

        assert len(_ledger_events(db_session, project)) == 1

    def test_reviewer_identity_from_db_session(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "identity")
        task = _task(db_session, project, item, "identity")
        reviewer = _session(db_session, project, task_id=task.id)
        # Set model name
        reviewer.model_name = "gpt-5-test"
        db_session.flush()

        report_path = _write_report(
            project.repo_path, session_id=reviewer.id, tasks=[task.id], report_type="review"
        )
        _ingest(db_session, project, report_path)

        events = _ledger_events(db_session, project)
        assert len(events) == 1
        payload = json.loads(events[0].payload_json)
        assert payload["reviewer_session_id"] == reviewer.id
        assert payload["reviewer_agent_type"] == "codex"
        assert payload["reviewer_model_name"] == "gpt-5-test"

    def test_source_identity_in_payload(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "source")
        task = _task(db_session, project, item, "source")
        reviewer = _session(db_session, project, task_id=task.id)
        report_path = _write_report(
            project.repo_path, session_id=reviewer.id, tasks=[task.id], report_type="review"
        )
        report = _ingest(db_session, project, report_path)

        events = _ledger_events(db_session, project)
        assert len(events) == 1
        e = events[0]
        payload = json.loads(e.payload_json)
        assert payload["source_report_id"] == report.source_report_id
        assert payload["source_path"] == report.source_path
        assert payload["source_content_sha256"] == report.source_content_sha256
        assert payload["report_type"] == "review"

    def test_occurred_at_equals_report_created_at(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "occurred")
        task = _task(db_session, project, item, "occurred")
        reviewer = _session(db_session, project, task_id=task.id)
        report_path = _write_report(
            project.repo_path, session_id=reviewer.id, tasks=[task.id], report_type="review"
        )
        report = _ingest(db_session, project, report_path)

        events = _ledger_events(db_session, project)
        assert len(events) == 1
        assert events[0].occurred_at == report.created_at


class TestReviewCompletedSnapshot:
    """PlanItem snapshot testovi."""

    def test_task_plan_item_drift_uses_historical_snapshot(
        self, db_session: Session, project: Project
    ):
        """Kada Task.plan_item_id promeni vrednost posle binding-a, REVIEW_COMPLETED koristi historical snapshot."""
        item_old = _plan_item(db_session, project, "old")
        item_new = _plan_item(db_session, project, "new")
        task = _task(db_session, project, item_old, "drift")
        reviewer = _session(db_session, project, task_id=task.id)

        # Promeni Task.plan_item_id POSLE binding-a (simulacija drifta)
        task.plan_item_id = item_new.id
        db_session.flush()

        report_path = _write_report(
            project.repo_path, session_id=reviewer.id, tasks=[task.id], report_type="review"
        )
        _ingest(db_session, project, report_path)

        events = _ledger_events(db_session, project)
        assert len(events) == 1

    def test_multiple_resolved_plan_item_ids(self, db_session: Session, project: Project):
        """Više historical snapshot-ova → event.plan_item_id NULL + svi u payload-u.

        Obrazac preuzet iz Phase 3A: test_task_event_with_multiple_plan_snapshots_keeps_plan_item_null
        """
        from uuid import uuid4

        item_a = _plan_item(db_session, project, "snap-a")
        item_b = _plan_item(db_session, project, "snap-b")
        item_c = _plan_item(db_session, project, "snap-c")
        task_a = _task(db_session, project, item_a, "snap-a")
        task_b = _task(db_session, project, item_b, "snap-b")
        session = _session(db_session, project, task_id=task_a.id)

        # 2 stvarna binding segmenta kroz switch_binding
        bindings_svc = SessionTaskBindingService(db_session)
        bindings_svc.switch_binding(session.id, task_id=task_b.id)
        bindings_svc.switch_binding(session.id, task_id=task_a.id)

        # Ručno kreiraj review report sa linkovima
        report = ReportService(db_session).create_draft(
            session.id,
            report_type="review",
            source_report_id=str(uuid4()),
            source_path=str(Path(project.repo_path) / "agent_reports" / "manual-multi-3c.md"),
            source_content_sha256="c" * 64,
        )
        task_a_bindings = [
            b for b in bindings_svc.get_bindings(session.id) if b.task_id == task_a.id
        ]
        assert len(task_a_bindings) == 2

        reports_svc = ReportService(db_session)
        link_1 = reports_svc.link_report_to_binding(report.id, task_a_bindings[0].id)
        link_2 = reports_svc.link_report_to_binding(report.id, task_a_bindings[1].id)
        link_1.resolved_plan_item_id = item_a.id
        link_2.resolved_plan_item_id = item_c.id
        db_session.flush()

        [event] = WorkflowLedgerService(db_session).append_review_completed_from_report(report.id)

        assert event.task_id == task_a.id
        assert event.plan_item_id is None
        payload = json.loads(event.payload_json)
        assert payload["resolved_plan_item_ids"] == [item_a.id, item_c.id]


class TestCrossProjectProtection:
    """F6: Cross-project/session corruption zaštita."""

    def test_corrupted_cross_project_link_produces_zero_events(
        self, db_session: Session, project: Project
    ):
        """Korumpirani cross-project link → 0 REVIEW_COMPLETED eventa."""
        item = _plan_item(db_session, project, "corrupt")
        task = _task(db_session, project, item, "corrupt")
        reviewer = _session(db_session, project, task_id=task.id)

        # Napravi drugi projekat sa svojom sesijom i bindingom
        other_project = Project(id="other-proj", name="Other", repo_path="/tmp/other")
        db_session.add(other_project)
        db_session.flush()
        other_session = _session(db_session, other_project)
        db_session.flush()

        # Ručno kreiraj review report u prvom projektu
        report_svc = ReportService(db_session)
        report = report_svc.create_draft(
            reviewer.id,
            report_type="review",
            source_report_id="corrupt-test-id",
            source_path="/fake/corrupt.md",
            source_content_sha256="sha256-corrupt",
        )
        db_session.flush()

        # Direktno kreiraj korumpirani cross-session link
        other_bindings = SessionTaskBindingService(db_session).get_bindings(other_session.id)
        assert len(other_bindings) >= 1
        corrupt_link = AgentReportBindingLink(
            report_id=report.id,
            session_task_binding_id=other_bindings[0].id,
        )
        db_session.add(corrupt_link)
        db_session.flush()

        # _build_target_groups će odbaciti jer binding.session_id != report.session_id
        events = WorkflowLedgerService(db_session).append_review_completed_from_report(report.id)
        assert len(events) == 0

    def test_normal_same_session_review_still_works(self, db_session: Session, project: Project):
        """Normalni same-session review i dalje radi nakon F1 popravke."""
        item = _plan_item(db_session, project, "same-ses")
        task = _task(db_session, project, item, "same-ses")
        reviewer = _session(db_session, project, task_id=task.id)
        report_path = _write_report(
            project.repo_path, session_id=reviewer.id, tasks=[task.id], report_type="review"
        )
        _ingest(db_session, project, report_path)

        events = _ledger_events(db_session, project)
        assert len(events) == 1
        assert events[0].task_id == task.id


class TestTransactionRollback:
    """F7: Transaction rollback — AgentReport + links + Ledger event u istoj transakciji."""

    def test_ledger_failure_rolls_back_report_and_links(
        self, db_session: Session, project: Project, monkeypatch
    ):
        """Stvarni Ledger append → forced RuntimeError → rollback → sva 3 artefakta nestaju."""
        item = _plan_item(db_session, project, "rollback")
        task = _task(db_session, project, item, "rollback")
        reviewer = _session(db_session, project, task_id=task.id)

        # Wrapper: prvo pozovi originalni append, PA tek onda baci exception
        original_append = WorkflowLedgerService.append_review_completed_from_report

        def _append_then_fail(self, report_id: str):
            original_append(self, report_id)
            raise RuntimeError("forced failure after ledger append")

        monkeypatch.setattr(
            WorkflowLedgerService, "append_review_completed_from_report", _append_then_fail
        )

        report_path = _write_report(
            project.repo_path, session_id=reviewer.id, tasks=[task.id], report_type="review"
        )

        from flowos.service.services.reports.ingestion import AgentReportIngestionService

        with pytest.raises(RuntimeError, match="forced failure after ledger append"):
            AgentReportIngestionService(db_session).ingest_file(
                report_path, project_id=project.id, repo_path=project.repo_path
            )

        db_session.rollback()

        # Sva tri DB artefakta moraju nestati
        assert db_session.query(AgentReport).count() == 0
        assert db_session.query(AgentReportBindingLink).count() == 0
        assert db_session.query(WorkflowLedgerEvent).count() == 0
        # Markdown source mora ostati na filesystemu
        assert report_path.exists()


class TestReviewCompletedNoSideEffects:
    """REVIEW_COMPLETED ne sme imati sporedne efekte."""

    def test_review_completed_does_not_change_plan_item_status(
        self, db_session: Session, project: Project
    ):
        item = _plan_item(db_session, project, "nostatus")
        assert item.status == "IN_PROGRESS"
        task = _task(db_session, project, item, "nostatus")
        reviewer = _session(db_session, project, task_id=task.id)
        report_path = _write_report(
            project.repo_path, session_id=reviewer.id, tasks=[task.id], report_type="review"
        )
        _ingest(db_session, project, report_path)

        db_session.refresh(item)
        assert item.status == "IN_PROGRESS"

    def test_markdown_accept_does_not_produce_decision(self, db_session: Session, project: Project):
        """Markdown body 'ACCEPT' ne utiče na REVIEW_COMPLETED."""
        item = _plan_item(db_session, project, "accept")
        task = _task(db_session, project, item, "accept")
        reviewer = _session(db_session, project, task_id=task.id)

        report_dir = Path(project.repo_path) / "agent_reports"
        report_dir.mkdir(exist_ok=True)
        report_id = str(uuid4()).replace("-", "")
        content = (
            f"---\n"
            f"flowos_report_version: 1\n"
            f"report_id: {report_id}\n"
            f"agent: codex\n"
            f"model: gpt-5\n"
            f"session_id: {reviewer.id}\n"
            f"report_type: review\n"
            f"tasks:\n"
            f"  - {task.id}\n"
            f"commits: []\n"
            f"created_at: 2026-08-12T10:00:00+02:00\n"
            f"---\n"
            f"\nACCEPT\n\nSve je u redu.\n"
        )
        rp = report_dir / "accept.md"
        rp.write_text(content, encoding="utf-8")
        _ingest(db_session, project, rp)

        events = _ledger_events(db_session, project)
        assert len(events) == 1
        # Proveri da PlanItem nije promenjen (ACCEPT ne znači VERIFIED)
        db_session.refresh(item)
        assert item.status == "IN_PROGRESS"

    def test_markdown_fixes_required_does_not_produce_decision(
        self, db_session: Session, project: Project
    ):
        """Markdown body 'FIXES REQUIRED' ne utiče na REVIEW_COMPLETED."""
        item = _plan_item(db_session, project, "fixes")
        task = _task(db_session, project, item, "fixes")
        reviewer = _session(db_session, project, task_id=task.id)

        report_dir = Path(project.repo_path) / "agent_reports"
        report_dir.mkdir(exist_ok=True)
        report_id = str(uuid4()).replace("-", "")
        content = (
            f"---\nflowos_report_version: 1\nreport_id: {report_id}\nagent: codex\n"
            f"model: gpt-5\nsession_id: {reviewer.id}\nreport_type: review\n"
            f"tasks:\n  - {task.id}\ncommits: []\n"
            f"created_at: 2026-08-12T10:00:00+02:00\n---\n\nFIXES REQUIRED\n\nTreba popraviti.\n"
        )
        rp = report_dir / "fixes.md"
        rp.write_text(content, encoding="utf-8")
        _ingest(db_session, project, rp)

        events = _ledger_events(db_session, project)
        assert len(events) == 1
        db_session.refresh(item)
        assert item.status == "IN_PROGRESS"
