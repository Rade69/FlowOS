"""Testovi za ReportService — verdict audit i append-only ponašanje."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.workflow_ledger_models  # noqa: F401
from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.models import AgentSession, Project
from flowos.service.services.reports.service import ReportService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def project(db_session: Session) -> Project:
    p = Project(id="proj-rpt-001", name="Report Test", repo_path="C:/test/repo")
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def session(db_session: Session, project: Project) -> AgentSession:
    s = AgentSession(
        id="sess-rpt-001",
        project_id=project.id,
        agent_type="test",
        repo_path=project.repo_path,
        status="ACTIVE",
        started_at=datetime.now(tz=UTC),
    )
    db_session.add(s)
    db_session.flush()
    return s


class TestReportService:
    def test_create_draft(self, db_session: Session, session: AgentSession):
        svc = ReportService(db_session)
        report = svc.create_draft(
            session_id=session.id,
            summary="Test summary",
            scope="Test scope",
        )
        assert report.id is not None
        assert report.status == "DRAFT"
        assert report.summary == "Test summary"

    def test_set_verdict_with_audit(self, db_session: Session, session: AgentSession):
        svc = ReportService(db_session)
        report = svc.create_draft(session_id=session.id, summary="Test")
        updated = svc.set_verdict(report.id, "ACCEPTED", notes="Looks good")

        assert updated is not None
        assert updated.user_verdict == "ACCEPTED"
        assert updated.status == "FINAL"
        assert updated.verdict_audit_json is not None

        import json

        audit = json.loads(updated.verdict_audit_json)
        assert len(audit) == 1
        entry = audit[0]
        assert entry["new_verdict"] == "ACCEPTED"
        assert entry["previous_verdict"] is None
        assert entry["new_status"] == "FINAL"
        assert entry["actor"] == "user"
        assert entry["notes"] == "Looks good"

    def test_set_verdict_chaining(self, db_session: Session, session: AgentSession):
        svc = ReportService(db_session)
        report = svc.create_draft(session_id=session.id, summary="Test")

        svc.set_verdict(report.id, "NEEDS_WORK", notes="Fix bugs")
        svc.set_verdict(report.id, "ACCEPTED", notes="Fixed")

        db_session.refresh(report)
        import json

        audit = json.loads(report.verdict_audit_json or "[]")
        assert len(audit) == 2
        assert audit[0]["new_verdict"] == "NEEDS_WORK"
        assert audit[1]["new_verdict"] == "ACCEPTED"
        assert audit[1]["previous_verdict"] == "NEEDS_WORK"

    def test_update_report_cannot_change_verdict(self, db_session: Session, session: AgentSession):
        svc = ReportService(db_session)
        report = svc.create_draft(session_id=session.id, summary="Test")
        svc.set_verdict(report.id, "ACCEPTED", notes="OK")

        with pytest.raises(ValueError, match="ne može da se menja"):
            svc.update_report(report.id, user_verdict="NEEDS_WORK")

    def test_update_report_cannot_change_verdict_audit_json(
        self, db_session: Session, session: AgentSession
    ):
        svc = ReportService(db_session)
        report = svc.create_draft(session_id=session.id, summary="Test")
        svc.set_verdict(report.id, "ACCEPTED", notes="OK")

        original_audit = report.verdict_audit_json

        with pytest.raises(ValueError, match="ne može da se menja"):
            svc.update_report(report.id, verdict_audit_json="[]")

        db_session.refresh(report)
        assert report.verdict_audit_json == original_audit

    def test_invalid_verdict_raises(self, db_session: Session, session: AgentSession):
        svc = ReportService(db_session)
        report = svc.create_draft(session_id=session.id, summary="Test")

        with pytest.raises(ValueError, match="Nedozvoljen verdict"):
            svc.set_verdict(report.id, "INVALID")
