"""Testovi za ProjectResumeService — regeneracija "Gde si stao" sažetka."""

import json

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.models import AgentSession, Project
from flowos.service.services.infrastructure.persistence.plan_models import Plan, PlanItem, PlanPhase
from flowos.service.services.infrastructure.persistence.resume_models import (
    ProjectResumeState,
    ProjectWorkspaceState,
)
from flowos.service.services.project_resume import ProjectResumeService


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", echo=False)

    @event.listens_for(eng, "connect")
    def _pragma(dbapi_connection, connection_record):  # noqa: ARG001
        c = dbapi_connection.cursor()
        c.execute("PRAGMA journal_mode=WAL;")
        c.execute("PRAGMA foreign_keys=ON;")
        c.close()

    import flowos.service.services.infrastructure.persistence.models  # noqa: F401
    import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
    import flowos.service.services.infrastructure.persistence.resume_models  # noqa: F401

    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def session(engine):
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as s:
        yield s


@pytest.fixture
def project(session: Session):
    p = Project(name="Test", repo_path="C:/test")
    session.add(p)
    session.commit()
    return p


def _make_plan(session: Session, project_id: str) -> Plan:
    plan = Plan(project_id=project_id, title="Plan", status="ACTIVE")
    session.add(plan)
    session.flush()
    return plan


def _make_phase(session: Session, plan_id: str) -> PlanPhase:
    phase = PlanPhase(plan_id=plan_id, phase_key="F0", title="F0", sequence=0)
    session.add(phase)
    session.flush()
    return phase


def _make_item(session: Session, phase_id: str, key: str, title: str, status: str = "NOT_STARTED", **kw):
    item = PlanItem(plan_phase_id=phase_id, item_key=key, title=title, status=status, **kw)
    session.add(item)
    session.flush()
    return item


# ═══════════════════════════════════════════════════════════════════


class TestResumeRegeneration:
    def test_no_history(self, session: Session, project: Project):
        svc = ProjectResumeService(session)
        resume = svc.regenerate(project.id)
        assert resume.resume_status == "NO_HISTORY"
        assert resume.confidence == "LOW"
        assert "nema aktivni plan" in resume.where_stopped

    def test_with_active_plan(self, session: Session, project: Project):
        plan = _make_plan(session, project.id)
        phase = _make_phase(session, plan.id)
        _make_item(session, phase.id, "FLOW-001", "Test Item", status="IN_PROGRESS")
        sess = AgentSession(project_id=project.id, agent_type="pi", repo_path="C:/test")
        session.add(sess)
        session.commit()

        svc = ProjectResumeService(session)
        resume = svc.regenerate(project.id)
        assert resume.resume_status == "READY_TO_CONTINUE"
        assert "FLOW-001" in resume.where_stopped

    def test_with_session_and_plan(self, session: Session, project: Project):
        plan = _make_plan(session, project.id)
        phase = _make_phase(session, plan.id)
        _make_item(session, phase.id, "FLOW-042", "Feature", status="IMPLEMENTED")
        sess = AgentSession(project_id=project.id, agent_type="pi", repo_path="C:/test")
        session.add(sess)
        session.flush()

        svc = ProjectResumeService(session)
        resume = svc.regenerate(project.id)
        assert resume.last_session_id == sess.id
        assert "IMPLEMENTED" in resume.where_stopped or "implementirana" in resume.where_stopped
        assert resume.next_concrete_step is not None
        assert "verifikaciju" in resume.next_concrete_step.lower()

    def test_blocked_item(self, session: Session, project: Project):
        plan = _make_plan(session, project.id)
        phase = _make_phase(session, plan.id)
        _make_item(session, phase.id, "FLOW-BLK", "Blocked", status="BLOCKED", blocked_reason="Čeka se zavisnost")
        session.commit()

        svc = ProjectResumeService(session)
        resume = svc.regenerate(project.id)
        assert resume.resume_status == "BLOCKED"
        assert resume.open_blockers_json is not None
        blockers = json.loads(resume.open_blockers_json)
        assert len(blockers) == 1
        assert blockers[0]["item_key"] == "FLOW-BLK"

    def test_with_workspace_state_current(self, session: Session, project: Project):
        plan = _make_plan(session, project.id)
        phase = _make_phase(session, plan.id)
        _make_item(session, phase.id, "FLOW-001", "T", status="VERIFIED")
        ws = ProjectWorkspaceState(project_id=project.id, last_known_commit_sha="abc123", reconciliation_status="CURRENT")
        sess = AgentSession(project_id=project.id, agent_type="pi", repo_path="C:/test")
        session.add_all([ws, sess])
        session.commit()

        svc = ProjectResumeService(session)
        resume = svc.regenerate(project.id)
        assert resume.last_commit_sha == "abc123"
        assert resume.confidence in ("HIGH", "MEDIUM")

    def test_external_changes_reduce_confidence(self, session: Session, project: Project):
        plan = _make_plan(session, project.id)
        phase = _make_phase(session, plan.id)
        _make_item(session, phase.id, "FLOW-001", "T", status="IN_PROGRESS")
        ws = ProjectWorkspaceState(project_id=project.id, reconciliation_status="EXTERNAL_DIRTY_CHANGES")
        sess = AgentSession(project_id=project.id, agent_type="pi", repo_path="C:/test")
        session.add_all([ws, sess])
        session.commit()

        svc = ProjectResumeService(session)
        resume = svc.regenerate(project.id)
        assert resume.resume_status == "EXTERNAL_CHANGES"
        assert resume.confidence == "MEDIUM"

    def test_regenerate_updates_existing(self, session: Session, project: Project):
        svc = ProjectResumeService(session)
        r1 = svc.regenerate(project.id)
        assert r1.resume_status == "NO_HISTORY"

        plan = _make_plan(session, project.id)
        phase = _make_phase(session, plan.id)
        _make_item(session, phase.id, "FLOW-001", "T", status="IN_PROGRESS")
        sess = AgentSession(project_id=project.id, agent_type="pi", repo_path="C:/test")
        session.add(sess)
        session.commit()

        r2 = svc.regenerate(project.id)
        assert r2.id == r1.id
        assert r2.resume_status == "READY_TO_CONTINUE"

        count = session.query(ProjectResumeState).filter(ProjectResumeState.project_id == project.id).count()
        assert count == 1

    def test_preconditions(self, session: Session, project: Project):
        svc = ProjectResumeService(session)
        resume = svc.regenerate(project.id)
        assert "Aktivirati plan" in resume.resume_preconditions