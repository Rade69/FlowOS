"""FLOW-1106 activation contract: uniqueness, resume, audit and rollback."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import flowos.service.services.infrastructure.persistence.models  # noqa: F401
import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.report_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.resume_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.workflow_ledger_models  # noqa: F401
from flowos.service.controllers.http.plan_progress import router
from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.models import (
    AgentSession,
    Project,
    SessionTaskBinding,
    Task,
)
from flowos.service.services.infrastructure.persistence.plan_models import Plan
from flowos.service.services.infrastructure.persistence.report_models import AgentReport
from flowos.service.services.infrastructure.persistence.resume_models import ProjectResumeState
from flowos.service.services.infrastructure.persistence.workflow_ledger_models import (
    WorkflowLedgerEvent,
)
from flowos.service.services.project_resume import ProjectResumeService
from flowos.service.services.workflow.ledger import PLAN_ACTIVATED, WorkflowLedgerService


@pytest.fixture
def engine():
    """Izolovan SQLite engine sa istim FK ponašanjem kao servis."""
    value = create_engine(
        "sqlite:///file:test_plan_activation?mode=memory&cache=shared",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(value, "connect")
    def _pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(value)
    yield value
    Base.metadata.drop_all(value)
    value.dispose()


@pytest.fixture
def app(engine):
    value = FastAPI()
    value.include_router(router)
    value.state.session_factory = sessionmaker(bind=engine)
    return value


@pytest.fixture
def client(app):
    return TestClient(app)


def _project(session: Session, name: str = "Project") -> Project:
    project = Project(name=name, repo_path=f"C:/{name}")
    session.add(project)
    session.flush()
    return project


def _plan(session: Session, project_id: str, status: str, title: str) -> Plan:
    plan = Plan(project_id=project_id, status=status, title=title)
    session.add(plan)
    session.flush()
    return plan


def _seed(app, *, old_active_count: int = 0):
    with app.state.session_factory() as session:
        project = _project(session)
        old_plans = [
            _plan(session, project.id, "ACTIVE", f"Old {index}")
            for index in range(old_active_count)
        ]
        target = _plan(session, project.id, "DRAFT", "Target")
        resume = ProjectResumeState(
            project_id=project.id,
            active_plan_id=old_plans[0].id if old_plans else None,
        )
        session.add(resume)
        session.commit()
        return project.id, target.id, [plan.id for plan in old_plans]


def _activation_state(app, project_id: str, target_id: str):
    with app.state.session_factory() as session:
        plans = session.query(Plan).filter(Plan.project_id == project_id).all()
        resume = (
            session.query(ProjectResumeState)
            .filter(ProjectResumeState.project_id == project_id)
            .one()
        )
        events = (
            session.query(WorkflowLedgerEvent)
            .filter(
                WorkflowLedgerEvent.project_id == project_id,
                WorkflowLedgerEvent.event_type == PLAN_ACTIVATED,
            )
            .all()
        )
        return {
            "target_status": next(plan.status for plan in plans if plan.id == target_id),
            "active_ids": sorted(plan.id for plan in plans if plan.status == "ACTIVE"),
            "superseded_ids": sorted(plan.id for plan in plans if plan.status == "SUPERSEDED"),
            "resume_plan_id": resume.active_plan_id,
            "events": events,
        }


def test_t1_t3_t4_t5_activate_without_previous_active(app, client):
    project_id, target_id, _ = _seed(app)

    response = client.post(f"/plans/{target_id}/activate")

    assert response.status_code == 200
    state = _activation_state(app, project_id, target_id)
    assert state["target_status"] == "ACTIVE"
    assert state["active_ids"] == [target_id]
    assert state["resume_plan_id"] == target_id
    assert len(state["events"]) == 1
    event_record = state["events"][0]
    assert event_record.source_kind == "plan"
    assert event_record.source_id == target_id
    assert event_record.session_id is None
    assert event_record.task_id is None
    assert event_record.plan_item_id is None
    assert json.loads(event_record.payload_json) == {
        "plan_id": target_id,
        "previous_active_plan_ids": [],
        "project_id": project_id,
    }


def test_t2_t3_activate_supersedes_previous_active(app, client):
    project_id, target_id, old_ids = _seed(app, old_active_count=1)

    response = client.post(f"/plans/{target_id}/activate")

    assert response.status_code == 200
    state = _activation_state(app, project_id, target_id)
    assert state["active_ids"] == [target_id]
    assert state["superseded_ids"] == old_ids
    assert json.loads(state["events"][0].payload_json)["previous_active_plan_ids"] == old_ids


def test_t3_database_rejects_second_active_plan(app):
    with app.state.session_factory() as session:
        project = _project(session)
        _plan(session, project.id, "ACTIVE", "First")
        session.commit()
        session.add(Plan(project_id=project.id, status="ACTIVE", title="Second"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_t6_repeat_activation_is_409_and_does_not_duplicate_audit(app, client):
    project_id, target_id, _ = _seed(app)
    assert client.post(f"/plans/{target_id}/activate").status_code == 200

    response = client.post(f"/plans/{target_id}/activate")

    assert response.status_code == 409
    state = _activation_state(app, project_id, target_id)
    assert state["active_ids"] == [target_id]
    assert len(state["events"]) == 1


def test_activation_does_not_fabricate_execution_history(app, client):
    _project_id, target_id, _ = _seed(app)

    assert client.post(f"/plans/{target_id}/activate").status_code == 200

    with app.state.session_factory() as session:
        assert session.query(AgentSession).count() == 0
        assert session.query(Task).count() == 0
        assert session.query(AgentReport).count() == 0
        assert session.query(SessionTaskBinding).count() == 0


def test_t7_missing_target_has_no_partial_changes(app, client):
    project_id, _target_id, old_ids = _seed(app, old_active_count=1)

    response = client.post("/plans/missing/activate")

    assert response.status_code == 404
    state = _activation_state(app, project_id, _target_id)
    assert state["active_ids"] == old_ids
    assert state["events"] == []


def test_t8_activation_does_not_touch_other_project(app, client):
    project_id, target_id, _ = _seed(app, old_active_count=1)
    with app.state.session_factory() as session:
        other = _project(session, "Other")
        other_active = _plan(session, other.id, "ACTIVE", "Other active")
        session.commit()
        other_id = other.id
        other_active_id = other_active.id

    assert client.post(f"/plans/{target_id}/activate").status_code == 200

    with app.state.session_factory() as session:
        assert session.get(Plan, other_active_id).status == "ACTIVE"
        assert (
            session.query(Plan).filter(Plan.project_id == other_id, Plan.status == "ACTIVE").count()
            == 1
        )
        assert (
            session.query(Plan)
            .filter(Plan.project_id == project_id, Plan.status == "ACTIVE")
            .one()
            .id
            == target_id
        )


def test_t9_legacy_multiple_active_plans_are_all_superseded(app, client, engine):
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP INDEX uq_plans_one_active_per_project")
    project_id, target_id, old_ids = _seed(app, old_active_count=2)

    response = client.post(f"/plans/{target_id}/activate")

    assert response.status_code == 200
    state = _activation_state(app, project_id, target_id)
    assert state["active_ids"] == [target_id]
    assert state["superseded_ids"] == sorted(old_ids)


def test_t10_status_flush_failure_rolls_back_everything(app, monkeypatch):
    project_id, target_id, old_ids = _seed(app, old_active_count=1)
    original_flush = Session.flush
    calls = 0

    def fail_second_flush(session, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated status flush failure")
        return original_flush(session, *args, **kwargs)

    monkeypatch.setattr(Session, "flush", fail_second_flush)
    response = TestClient(app, raise_server_exceptions=False).post(f"/plans/{target_id}/activate")

    assert response.status_code == 500
    state = _activation_state(app, project_id, target_id)
    assert state["target_status"] == "DRAFT"
    assert state["active_ids"] == old_ids
    assert state["events"] == []


def test_t11_audit_failure_rolls_back_status_and_resume(app, monkeypatch):
    project_id, target_id, old_ids = _seed(app, old_active_count=1)

    def fail_audit(*_args, **_kwargs):
        raise RuntimeError("simulated audit failure")

    monkeypatch.setattr(WorkflowLedgerService, "append_plan_activated", fail_audit)
    response = TestClient(app, raise_server_exceptions=False).post(f"/plans/{target_id}/activate")

    assert response.status_code == 500
    state = _activation_state(app, project_id, target_id)
    assert state["target_status"] == "DRAFT"
    assert state["active_ids"] == old_ids
    assert state["resume_plan_id"] == old_ids[0]
    assert state["events"] == []


def test_t12_resume_failure_rolls_back_status_and_skips_audit(app, monkeypatch):
    project_id, target_id, old_ids = _seed(app, old_active_count=1)

    def fail_resume(*_args, **_kwargs):
        raise RuntimeError("simulated resume failure")

    monkeypatch.setattr(ProjectResumeService, "regenerate", fail_resume)
    response = TestClient(app, raise_server_exceptions=False).post(f"/plans/{target_id}/activate")

    assert response.status_code == 500
    state = _activation_state(app, project_id, target_id)
    assert state["target_status"] == "DRAFT"
    assert state["active_ids"] == old_ids
    assert state["resume_plan_id"] == old_ids[0]
    assert state["events"] == []
