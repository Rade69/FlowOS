"""Integracioni testovi za AgentReport v2 Phase 2 Markdown ingestion."""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

import flowos.service.services.infrastructure.persistence.activity_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.report_models  # noqa: F401
from flowos.service.composition_root import (
    _create_watcher_callback,
    _scan_existing_agent_reports_for_project,
)
from flowos.service.services.infrastructure.persistence.activity_models import FileActivity
from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.models import AgentSession, Project, Task
from flowos.service.services.infrastructure.persistence.plan_models import Plan, PlanItem, PlanPhase
from flowos.service.services.infrastructure.persistence.report_models import (
    AgentReport,
    AgentReportBindingLink,
)
from flowos.service.services.reports.front_matter import AgentReportFrontMatterParser
from flowos.service.services.reports.ingestion import (
    AgentReportIngestionOutcome,
    AgentReportIngestionService,
    normalize_source_path,
)
from flowos.service.services.reports.service import ReportService
from flowos.service.services.sessions.bindings import SessionTaskBindingService
from flowos.service.services.sessions.service import SessionService


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
    project = Project(id="project-ingestion", name="Ingestion", repo_path=str(repo))
    db_session.add(project)
    db_session.flush()
    return project


def _factory(engine):
    return sessionmaker(bind=engine, autoflush=True, expire_on_commit=False)


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
    report_id: str | None = None,
    session_id: str,
    tasks: list[str],
    report_type: str = "implementation",
    work_status: str | None = "completed",
    body: str = "# Body",
) -> Path:
    reports_dir = Path(repo_path) / "agent_reports"
    reports_dir.mkdir(exist_ok=True)
    report_id = report_id or str(uuid4())
    lines = [
        "---",
        "flowos_report_version: 1",
        f"report_id: {report_id}",
        f"session_id: {session_id}",
        f"report_type: {report_type}",
    ]
    if work_status is not None:
        lines.append(f"work_status: {work_status}")
    lines.extend(["tasks:", *[f"  - {task}" for task in tasks]])
    lines.extend(["created_at: 2026-08-11T15:30:00+02:00", "---", "", body])
    path = reports_dir / filename
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _ingest(db: Session, project: Project, path: Path):
    return AgentReportIngestionService(db).ingest_file(
        path,
        project_id=project.id,
        repo_path=project.repo_path,
    )


def test_first_ingest_creates_one_agent_report(db_session: Session, project: Project):
    item = _plan_item(db_session, project, "FLOW-017")
    task = _task(db_session, project, item, "FLOW-017")
    session = _session(db_session, project, task_id=task.id)
    path = _write_report(project.repo_path, session_id=session.id, tasks=[task.id])

    result = _ingest(db_session, project, path)

    assert result.outcome == AgentReportIngestionOutcome.INGESTED
    assert db_session.query(AgentReport).count() == 1
    assert db_session.query(AgentReportBindingLink).count() == 1


def test_same_id_path_hash_is_idempotent_noop(db_session: Session, project: Project):
    session = _session(db_session, project)
    report_id = str(uuid4())
    path = _write_report(
        project.repo_path, report_id=report_id, session_id=session.id, tasks=["unassigned"]
    )
    assert _ingest(db_session, project, path).outcome == AgentReportIngestionOutcome.INGESTED

    result = _ingest(db_session, project, path)

    assert result.outcome == AgentReportIngestionOutcome.ALREADY_INGESTED
    assert db_session.query(AgentReport).count() == 1


def test_same_id_path_different_hash_is_immutable_conflict(db_session: Session, project: Project):
    session = _session(db_session, project)
    report_id = str(uuid4())
    path = _write_report(
        project.repo_path, report_id=report_id, session_id=session.id, tasks=["unassigned"]
    )
    assert _ingest(db_session, project, path).outcome == AgentReportIngestionOutcome.INGESTED
    _write_report(
        project.repo_path,
        report_id=report_id,
        session_id=session.id,
        tasks=["unassigned"],
        body="# Changed",
    )

    result = _ingest(db_session, project, path)

    assert result.outcome == AgentReportIngestionOutcome.IMMUTABLE_CONFLICT
    assert db_session.query(AgentReport).count() == 1


def test_same_id_different_path_is_immutable_conflict(db_session: Session, project: Project):
    session = _session(db_session, project)
    report_id = str(uuid4())
    first = _write_report(
        project.repo_path,
        filename="first.md",
        report_id=report_id,
        session_id=session.id,
        tasks=["unassigned"],
    )
    second = _write_report(
        project.repo_path,
        filename="second.md",
        report_id=report_id,
        session_id=session.id,
        tasks=["unassigned"],
    )
    assert _ingest(db_session, project, first).outcome == AgentReportIngestionOutcome.INGESTED

    result = _ingest(db_session, project, second)

    assert result.outcome == AgentReportIngestionOutcome.IMMUTABLE_CONFLICT


def test_different_id_same_path_after_success_is_immutable_conflict(
    db_session: Session, project: Project
):
    session = _session(db_session, project)
    path = _write_report(project.repo_path, session_id=session.id, tasks=["unassigned"])
    assert _ingest(db_session, project, path).outcome == AgentReportIngestionOutcome.INGESTED
    _write_report(project.repo_path, session_id=session.id, tasks=["unassigned"])

    result = _ingest(db_session, project, path)

    assert result.outcome == AgentReportIngestionOutcome.IMMUTABLE_CONFLICT


def test_source_path_unique_constraint_closes_two_transaction_precheck_race(tmp_path: Path):
    db_path = tmp_path / "race.db"
    engine = create_engine(f"sqlite:///{db_path}")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, connection_record):  # noqa: ARG001
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    repo = tmp_path / "repo"
    (repo / "agent_reports").mkdir(parents=True)
    source_path = normalize_source_path(repo / "agent_reports" / "race.md")

    with Session(engine) as setup:
        project = Project(id="project-race", name="Race", repo_path=str(repo))
        setup.add(project)
        setup.flush()
        session = SessionService(setup).create_session(
            project_id=project.id,
            agent_type="codex",
            repo_path=project.repo_path,
        )
        session_id = session.id
        setup.commit()

    report_id_a = str(uuid4())
    report_id_b = str(uuid4())
    markdown_a = "\n".join(
        [
            "---",
            "flowos_report_version: 1",
            f"report_id: {report_id_a}",
            f"session_id: {session_id}",
            "report_type: implementation",
            "work_status: completed",
            "tasks:",
            "  - unassigned",
            "created_at: 2026-08-11T15:30:00+02:00",
            "---",
            "",
            "# A",
        ]
    )
    markdown_b = markdown_a.replace(report_id_a, report_id_b).replace("# A", "# B")
    parser = AgentReportFrontMatterParser()
    front_matter_a = parser.parse_text(markdown_a)
    front_matter_b = parser.parse_text(markdown_b)
    hash_a = __import__("hashlib").sha256(markdown_a.encode("utf-8")).hexdigest()
    hash_b = __import__("hashlib").sha256(markdown_b.encode("utf-8")).hexdigest()

    t1 = Session(engine)
    t2 = Session(engine)
    try:
        assert (
            AgentReportIngestionService(t1)._check_identity(front_matter_a, source_path, hash_a)
            is None
        )
        assert (
            AgentReportIngestionService(t2)._check_identity(front_matter_b, source_path, hash_b)
            is None
        )

        t1.add(
            AgentReport(
                session_id=session_id,
                report_type=front_matter_a.report_type,
                work_status=front_matter_a.work_status,
                source_report_id=front_matter_a.report_id,
                source_path=source_path,
                source_content_sha256=hash_a,
            )
        )
        t1.commit()

        t2.add(
            AgentReport(
                session_id=session_id,
                report_type=front_matter_b.report_type,
                work_status=front_matter_b.work_status,
                source_report_id=front_matter_b.report_id,
                source_path=source_path,
                source_content_sha256=hash_b,
            )
        )
        with pytest.raises(IntegrityError):
            t2.commit()
        t2.rollback()
    finally:
        t1.close()
        t2.close()

    with Session(engine) as check:
        assert check.query(AgentReport).filter(AgentReport.source_path == source_path).count() == 1


def test_multiple_legacy_reports_with_null_source_path_remain_allowed(
    db_session: Session, project: Project
):
    session = _session(db_session, project)

    ReportService(db_session).create_draft(session.id)
    ReportService(db_session).create_draft(session.id)
    db_session.flush()

    assert db_session.query(AgentReport).filter(AgentReport.source_path.is_(None)).count() == 2


def test_source_path_unique_violation_becomes_immutable_conflict(
    db_session: Session, project: Project, monkeypatch: pytest.MonkeyPatch
):
    session = _session(db_session, project)
    path = _write_report(project.repo_path, session_id=session.id, tasks=["unassigned"])
    assert _ingest(db_session, project, path).outcome == AgentReportIngestionOutcome.INGESTED
    db_session.commit()
    _write_report(project.repo_path, session_id=session.id, tasks=["unassigned"], body="# B")

    monkeypatch.setattr(AgentReportIngestionService, "_check_identity", lambda *args: None)
    result = _ingest(db_session, project, path)

    assert result.outcome == AgentReportIngestionOutcome.IMMUTABLE_CONFLICT
    assert db_session.query(AgentReport).count() == 1


def test_watcher_duplicate_created_modified_does_not_duplicate_agent_report(
    engine, db_session: Session, project: Project
):
    session = _session(db_session, project)
    path = _write_report(project.repo_path, session_id=session.id, tasks=["unassigned"])
    db_session.commit()

    callback = _create_watcher_callback(
        project.id, project.repo_path, session_factory=_factory(engine)
    )
    callback(type("Event", (), {"path": str(path), "event_type": "CREATED"})())
    callback(type("Event", (), {"path": str(path), "event_type": "MODIFIED"})())

    with Session(engine) as check:
        assert check.query(AgentReport).count() == 1
        assert check.query(FileActivity).count() == 2


def test_unknown_session_needs_link_without_db_report(db_session: Session, project: Project):
    path = _write_report(project.repo_path, session_id="unknown", tasks=["unassigned"])

    result = _ingest(db_session, project, path)

    assert result.outcome == AgentReportIngestionOutcome.NEEDS_LINK
    assert db_session.query(AgentReport).count() == 0


def test_yaml_unsafe_tag_is_invalid_without_db_mutation(
    db_session: Session, project: Project, monkeypatch: pytest.MonkeyPatch
):
    session = _session(db_session, project)
    calls: list[str] = []
    monkeypatch.setattr(os, "system", lambda cmd: calls.append(cmd) or 0)
    reports_dir = Path(project.repo_path) / "agent_reports"
    reports_dir.mkdir()
    path = reports_dir / "unsafe.md"
    path.write_text(
        "\n".join(
            [
                "---",
                "flowos_report_version: 1",
                f"report_id: {uuid4()}",
                f"session_id: {session.id}",
                "report_type: implementation",
                "work_status: completed",
                "tasks:",
                "  - unassigned",
                "created_at: 2026-08-11T15:30:00+02:00",
                'agent: !!python/object/apply:os.system ["echo SHOULD_NOT_RUN"]',
                "---",
                "",
                "# Unsafe",
            ]
        ),
        encoding="utf-8",
    )

    result = _ingest(db_session, project, path)

    assert result.outcome == AgentReportIngestionOutcome.INVALID
    assert calls == []
    assert db_session.query(AgentReport).count() == 0


def test_nonexistent_session_needs_link(db_session: Session, project: Project):
    path = _write_report(project.repo_path, session_id=str(uuid4()), tasks=["unassigned"])

    result = _ingest(db_session, project, path)

    assert result.outcome == AgentReportIngestionOutcome.NEEDS_LINK


def test_cross_project_session_needs_link(db_session: Session, project: Project, tmp_path: Path):
    other_repo = tmp_path / "other"
    other_repo.mkdir()
    other_project = Project(id="other-project", name="Other", repo_path=str(other_repo))
    db_session.add(other_project)
    db_session.flush()
    other_session = _session(db_session, other_project)
    path = _write_report(project.repo_path, session_id=other_session.id, tasks=["unassigned"])

    result = _ingest(db_session, project, path)

    assert result.outcome == AgentReportIngestionOutcome.NEEDS_LINK
    assert db_session.query(AgentReport).count() == 0


def test_known_session_unassigned_creates_report_without_links(
    db_session: Session, project: Project
):
    session = _session(db_session, project)
    path = _write_report(project.repo_path, session_id=session.id, tasks=["unassigned"])

    result = _ingest(db_session, project, path)

    assert result.outcome == AgentReportIngestionOutcome.INGESTED
    assert db_session.query(AgentReport).count() == 1
    assert db_session.query(AgentReportBindingLink).count() == 0


def test_exact_task_binding(db_session: Session, project: Project):
    item = _plan_item(db_session, project, "FLOW-017")
    task = _task(db_session, project, item, "FLOW-017")
    session = _session(db_session, project, task_id=task.id)
    path = _write_report(project.repo_path, session_id=session.id, tasks=[task.id])

    assert _ingest(db_session, project, path).outcome == AgentReportIngestionOutcome.INGESTED
    link = db_session.query(AgentReportBindingLink).one()
    assert link.resolved_plan_item_id == item.id


def test_exact_plan_item_binding(db_session: Session, project: Project):
    item = _plan_item(db_session, project, "FLOW-017")
    session = _session(db_session, project)
    SessionTaskBindingService(db_session).switch_binding(session.id, plan_item_id=item.id)
    path = _write_report(project.repo_path, session_id=session.id, tasks=[item.id])

    assert _ingest(db_session, project, path).outcome == AgentReportIngestionOutcome.INGESTED
    assert db_session.query(AgentReportBindingLink).count() == 1


def test_exact_plan_item_key_binding(db_session: Session, project: Project):
    item = _plan_item(db_session, project, "FLOW-017")
    session = _session(db_session, project)
    SessionTaskBindingService(db_session).switch_binding(session.id, plan_item_id=item.id)
    path = _write_report(project.repo_path, session_id=session.id, tasks=["FLOW-017"])

    assert _ingest(db_session, project, path).outcome == AgentReportIngestionOutcome.INGESTED
    assert db_session.query(AgentReportBindingLink).count() == 1


def test_multi_task_report_links_all_resolved_bindings(db_session: Session, project: Project):
    item_a = _plan_item(db_session, project, "FLOW-017")
    item_b = _plan_item(db_session, project, "FLOW-018")
    task_a = _task(db_session, project, item_a, "FLOW-017")
    task_b = _task(db_session, project, item_b, "FLOW-018")
    session = _session(db_session, project, task_id=task_a.id)
    SessionTaskBindingService(db_session).switch_binding(session.id, task_id=task_b.id)
    path = _write_report(project.repo_path, session_id=session.id, tasks=[task_a.id, task_b.id])

    assert _ingest(db_session, project, path).outcome == AgentReportIngestionOutcome.INGESTED
    assert db_session.query(AgentReportBindingLink).count() == 2


def test_a_b_a_history_links_all_relevant_exact_target_segments(
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

    assert _ingest(db_session, project, path).outcome == AgentReportIngestionOutcome.INGESTED
    assert db_session.query(AgentReportBindingLink).count() == 2


def test_nonexistent_token_has_no_partial_mutation(db_session: Session, project: Project):
    item = _plan_item(db_session, project, "FLOW-017")
    task = _task(db_session, project, item, "FLOW-017")
    session = _session(db_session, project, task_id=task.id)
    path = _write_report(project.repo_path, session_id=session.id, tasks=[task.id, "FLOW-999"])

    result = _ingest(db_session, project, path)

    assert result.outcome == AgentReportIngestionOutcome.NEEDS_LINK
    assert db_session.query(AgentReport).count() == 0
    assert db_session.query(AgentReportBindingLink).count() == 0


def test_current_session_pointer_is_not_binding_fallback(db_session: Session, project: Project):
    item = _plan_item(db_session, project, "FLOW-017")
    task = _task(db_session, project, item, "FLOW-017")
    session = _session(db_session, project)
    session.task_id = task.id
    session.plan_item_id = item.id
    path = _write_report(project.repo_path, session_id=session.id, tasks=[task.id])

    result = _ingest(db_session, project, path)

    assert result.outcome == AgentReportIngestionOutcome.NEEDS_LINK
    assert db_session.query(AgentReport).count() == 0


def test_startup_scan_ingests_existing_report_then_watcher_noops(
    engine, db_session: Session, project: Project
):
    session = _session(db_session, project)
    path = _write_report(project.repo_path, session_id=session.id, tasks=["unassigned"])
    db_session.commit()

    results = _scan_existing_agent_reports_for_project(
        project.id,
        project.repo_path,
        _factory(engine),
        type("Logger", (), {"info": lambda *args: None, "exception": lambda *args: None})(),
    )
    callback = _create_watcher_callback(
        project.id, project.repo_path, session_factory=_factory(engine)
    )
    callback(type("Event", (), {"path": str(path), "event_type": "CREATED"})())

    with Session(engine) as check:
        assert [result.outcome for result in results] == [AgentReportIngestionOutcome.INGESTED]
        assert check.query(AgentReport).count() == 1


def test_startup_scan_missing_agent_reports_folder_is_ok(
    engine, db_session: Session, project: Project
):
    db_session.commit()

    results = _scan_existing_agent_reports_for_project(
        project.id,
        project.repo_path,
        _factory(engine),
        type("Logger", (), {"info": lambda *args: None, "exception": lambda *args: None})(),
    )

    assert results == []


def test_startup_scan_legacy_file_does_not_crash(engine, db_session: Session, project: Project):
    reports_dir = Path(project.repo_path) / "agent_reports"
    reports_dir.mkdir()
    (reports_dir / "legacy.md").write_text("# Legacy", encoding="utf-8")
    db_session.commit()

    results = _scan_existing_agent_reports_for_project(
        project.id,
        project.repo_path,
        _factory(engine),
        type("Logger", (), {"info": lambda *args: None, "exception": lambda *args: None})(),
    )

    assert [result.outcome for result in results] == [
        AgentReportIngestionOutcome.LEGACY_NO_FRONT_MATTER
    ]


def test_watcher_keeps_file_activity_when_ingestion_returns_invalid(
    engine, db_session: Session, project: Project
):
    reports_dir = Path(project.repo_path) / "agent_reports"
    reports_dir.mkdir()
    path = reports_dir / "invalid.md"
    path.write_text("---\nflowos_report_version: [\n---", encoding="utf-8")
    db_session.commit()

    callback = _create_watcher_callback(
        project.id, project.repo_path, session_factory=_factory(engine)
    )
    callback(type("Event", (), {"path": str(path), "event_type": "CREATED"})())

    with Session(engine) as check:
        activity = check.query(FileActivity).one()
        metadata = json.loads(activity.metadata_json or "{}")
        assert metadata["agent_report_ingestion"]["outcome"] == "INVALID"
        assert check.query(AgentReport).count() == 0


def test_unexpected_ingestion_exception_does_not_break_watcher_activity(
    engine, db_session: Session, project: Project, monkeypatch: pytest.MonkeyPatch
):
    session = _session(db_session, project)
    path = _write_report(project.repo_path, session_id=session.id, tasks=["unassigned"])
    db_session.commit()

    def _raise(*args, **kwargs):  # noqa: ARG001
        raise RuntimeError("boom")

    monkeypatch.setattr(AgentReportIngestionService, "ingest_file", _raise)
    callback = _create_watcher_callback(
        project.id, project.repo_path, session_factory=_factory(engine)
    )
    callback(type("Event", (), {"path": str(path), "event_type": "CREATED"})())

    with Session(engine) as check:
        assert check.query(FileActivity).count() == 1
        assert check.query(AgentReport).count() == 0
