"""Regresioni testovi za SessionTaskBinding phase 1 migraciju."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from flowos.service.controllers.http.sessions import router as sessions_router
from flowos.service.controllers.http.tasks import router as tasks_router
from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.models import (
    AgentSession,
    Project,
    SessionTaskBinding,
    Task,
)
from flowos.service.services.infrastructure.persistence.plan_models import Plan, PlanItem, PlanPhase
from flowos.service.services.sessions.bindings import SessionTaskBindingService
from flowos.service.services.sessions.service import SessionService
from flowos.shared.enums.session import SessionTaskBindingSource


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///file:test_session_task_bindings?mode=memory&cache=shared",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_connection, connection_record):  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def _project(db: Session, name: str = "P") -> Project:
    project = Project(name=name, repo_path=f"C:/{name}")
    db.add(project)
    db.flush()
    return project


def _task(db: Session, project: Project, title: str = "Task", plan_item_id: str | None = None):
    task = Task(project_id=project.id, title=title, plan_item_id=plan_item_id)
    db.add(task)
    db.flush()
    return task


def _plan_item(db: Session, project: Project, key: str = "FLOW-1") -> PlanItem:
    plan = (
        db.query(Plan).filter(Plan.project_id == project.id, Plan.status == "ACTIVE").one_or_none()
    )
    if plan is None:
        plan = Plan(project_id=project.id, title=f"Plan {key}", status="ACTIVE")
    db.add(plan)
    db.flush()
    phase = PlanPhase(plan_id=plan.id, phase_key=f"F-{key}", title="Faza", sequence=0)
    db.add(phase)
    db.flush()
    item = PlanItem(plan_phase_id=phase.id, item_key=key, title=f"Item {key}")
    db.add(item)
    db.flush()
    return item


def _session_service(db: Session, project: Project, **kwargs) -> AgentSession:
    return SessionService(db).create_session(
        project_id=project.id,
        agent_type="codex",
        repo_path=project.repo_path,
        **kwargs,
    )


def test_new_session_with_task_gets_initial_binding(db_session: Session):
    project = _project(db_session)
    task = _task(db_session, project)

    session = _session_service(db_session, project, task_id=task.id)
    binding = SessionTaskBindingService(db_session).get_active_binding(session.id)

    assert binding is not None
    assert binding.task_id == task.id
    assert binding.plan_item_id is None
    assert binding.binding_source == SessionTaskBindingSource.LEGACY_DIRECT_FK.value
    assert session.task_id == task.id


def test_new_session_with_plan_item_gets_initial_binding(db_session: Session):
    project = _project(db_session)
    item = _plan_item(db_session, project)

    session = _session_service(db_session, project, plan_item_id=item.id)
    binding = SessionTaskBindingService(db_session).get_active_binding(session.id)

    assert binding is not None
    assert binding.task_id is None
    assert binding.plan_item_id == item.id
    assert session.task_id is None
    assert session.plan_item_id == item.id


def test_new_session_without_task_gets_unassigned_binding(db_session: Session):
    project = _project(db_session)

    session = _session_service(db_session, project)
    binding = SessionTaskBindingService(db_session).get_active_binding(session.id)

    assert binding is not None
    assert binding.task_id is None
    assert binding.plan_item_id is None
    assert session.task_id is None
    assert session.plan_item_id is None


def test_switch_task_a_to_task_b_closes_previous_binding(db_session: Session):
    project = _project(db_session)
    task_a = _task(db_session, project, "A")
    task_b = _task(db_session, project, "B")
    session = _session_service(db_session, project, task_id=task_a.id)

    new_binding = SessionTaskBindingService(db_session).switch_binding(
        session.id, task_id=task_b.id
    )
    bindings = SessionTaskBindingService(db_session).get_bindings(session.id)

    assert len(bindings) == 2
    assert bindings[0].task_id == task_a.id
    assert bindings[0].ended_at is not None
    assert new_binding.task_id == task_b.id
    assert new_binding.ended_at is None


def test_task_to_unassigned_and_unassigned_to_task_work(db_session: Session):
    project = _project(db_session)
    task = _task(db_session, project)
    session = _session_service(db_session, project, task_id=task.id)
    service = SessionTaskBindingService(db_session)

    unassigned = service.switch_binding(session.id)
    assert unassigned.task_id is None
    assert unassigned.plan_item_id is None
    assert session.task_id is None
    assert session.plan_item_id is None

    rebound = service.switch_binding(session.id, task_id=task.id)
    assert rebound.task_id == task.id
    assert rebound.ended_at is None
    assert session.task_id == task.id


def test_cross_project_task_is_rejected(db_session: Session):
    project_a = _project(db_session, "A")
    project_b = _project(db_session, "B")
    task_b = _task(db_session, project_b)
    session = _session_service(db_session, project_a)

    with pytest.raises(ValueError, match="ne pripada projektu sesije"):
        SessionTaskBindingService(db_session).switch_binding(session.id, task_id=task_b.id)


def test_cross_project_plan_item_is_rejected(db_session: Session):
    project_a = _project(db_session, "A")
    project_b = _project(db_session, "B")
    item_b = _plan_item(db_session, project_b)
    session = _session_service(db_session, project_a)

    with pytest.raises(ValueError, match="ne pripada projektu sesije"):
        SessionTaskBindingService(db_session).switch_binding(session.id, plan_item_id=item_b.id)


def test_database_rejects_two_active_bindings_for_one_session(db_session: Session):
    project = _project(db_session)
    session = _session_service(db_session, project)

    db_session.add(
        SessionTaskBinding(
            session_id=session.id,
            started_at=datetime.now(tz=UTC),
            binding_source=SessionTaskBindingSource.USER.value,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_session_end_closes_active_binding(db_session: Session):
    project = _project(db_session)
    session = _session_service(db_session, project)

    ended = SessionService(db_session).end_session(session.id, status="COMPLETED")
    binding = SessionTaskBindingService(db_session).get_bindings(session.id)[0]

    assert ended is not None
    assert binding.ended_at is not None
    assert ended.ended_at is not None
    assert binding.ended_at.replace(tzinfo=UTC) == ended.ended_at


def test_switch_refreshes_legacy_agent_session_fields(db_session: Session):
    project = _project(db_session)
    item = _plan_item(db_session, project)
    task = _task(db_session, project, plan_item_id=item.id)
    session = _session_service(db_session, project)

    SessionTaskBindingService(db_session).switch_binding(session.id, task_id=task.id)
    assert session.task_id == task.id
    assert session.plan_item_id == item.id

    SessionTaskBindingService(db_session).switch_binding(session.id, plan_item_id=item.id)
    assert session.task_id is None
    assert session.plan_item_id == item.id


def test_inconsistent_legacy_task_and_plan_item_are_rejected(db_session: Session):
    project = _project(db_session)
    item_a = _plan_item(db_session, project, "FLOW-A")
    item_b = _plan_item(db_session, project, "FLOW-B")
    task = _task(db_session, project, plan_item_id=item_a.id)

    with pytest.raises(ValueError, match="nije povezan"):
        _session_service(db_session, project, task_id=task.id, plan_item_id=item_b.id)


def test_get_bindings_returns_chronological_history(db_session: Session):
    project = _project(db_session)
    task_a = _task(db_session, project, "A")
    task_b = _task(db_session, project, "B")
    session = _session_service(db_session, project, task_id=task_a.id)
    service = SessionTaskBindingService(db_session)
    assert session.started_at is not None
    start = session.started_at
    service.close_active_binding(session.id, ended_at=start + timedelta(seconds=1))
    service.switch_binding(session.id, task_id=task_a.id, switched_at=start + timedelta(minutes=1))
    service.switch_binding(session.id, task_id=task_b.id, switched_at=start + timedelta(minutes=2))

    bindings = service.get_bindings(session.id)

    assert [binding.task_id for binding in bindings] == [task_a.id, task_a.id, task_b.id]
    assert bindings == sorted(bindings, key=lambda binding: binding.started_at)


def test_http_get_bindings_returns_history(db_session: Session):
    project = _project(db_session)
    task = _task(db_session, project)
    session = _session_service(db_session, project, task_id=task.id)
    task_id = task.id
    session_id = session.id
    db_session.commit()
    client = _client_for(db_session)

    resp = client.get(f"/sessions/{session_id}/bindings")

    assert resp.status_code == 200
    assert resp.json()[0]["task_id"] == task_id
    assert resp.json()[0]["binding_kind"] == "TASK"


def test_http_switch_does_not_allow_client_to_forge_binding_source(db_session: Session):
    project = _project(db_session)
    session = _session_service(db_session, project)
    session_id = session.id
    db_session.commit()
    client = _client_for(db_session)

    forged = client.post(
        f"/sessions/{session_id}/bindings/switch",
        json={"task_id": None, "plan_item_id": None, "binding_source": "LEGACY_DIRECT_FK"},
    )
    assert forged.status_code == 422

    valid = client.post(
        f"/sessions/{session_id}/bindings/switch",
        json={"task_id": None, "plan_item_id": None},
    )
    assert valid.status_code == 200
    assert valid.json()["binding_source"] == SessionTaskBindingSource.USER.value


def _client_for(db: Session) -> TestClient:
    app = FastAPI(title="FlowOS Binding Test")
    app.include_router(sessions_router)
    factory = sessionmaker(bind=db.get_bind())
    app.state.session_factory = factory
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════════
# Regresioni testovi — F1, F2, F3 review fixes
# ═══════════════════════════════════════════════════════════════════


class TestF1SwitchOrder:
    """F1: switch prvo validira, pa zatvara — neuspeli switch ne sme zatvoriti postojeći binding."""

    def test_invalid_target_does_not_close_existing_binding(self, db_session: Session):
        project = _project(db_session)
        task_a = _task(db_session, project, "A")
        session = _session_service(db_session, project, task_id=task_a.id)
        session_id = session.id
        svc = SessionTaskBindingService(db_session)

        # Provera: task_a je aktivan binding
        active = svc.get_active_binding(session_id)
        assert active is not None
        assert active.task_id == task_a.id

        # Pokušaj switch na NEPOSTOJEĆI task_id
        with pytest.raises(ValueError, match="ne postoji"):
            svc.switch_binding(session_id, task_id="nepostojeci-id")

        # FLUSH bez rollback-a — binding MORA ostati netaknut
        db_session.flush()

        active_after = svc.get_active_binding(session_id)
        assert active_after is not None, "Aktivni binding ne sme nestati nakon neuspelog switch-a"
        assert active_after.task_id == task_a.id, "task_id mora ostati TASK A"
        assert active_after.ended_at is None, "Binding ne sme biti zatvoren"

        # Legacy pointer takođe netaknut
        db_session.refresh(session)
        assert session.task_id == task_a.id

    def test_cross_project_switch_does_not_close_existing_binding(self, db_session: Session):
        """F1: switch na task iz drugog projekta ne zatvara postojeći binding."""
        project_a = _project(db_session, "A")
        project_b = _project(db_session, "B")
        task_a = _task(db_session, project_a, "A")
        task_b = _task(db_session, project_b, "B")
        session = _session_service(db_session, project_a, task_id=task_a.id)
        svc = SessionTaskBindingService(db_session)

        active = svc.get_active_binding(session.id)
        assert active.task_id == task_a.id

        with pytest.raises(ValueError, match="ne pripada projektu"):
            svc.switch_binding(session.id, task_id=task_b.id)

        db_session.flush()
        active_after = svc.get_active_binding(session.id)
        assert active_after is not None
        assert active_after.task_id == task_a.id


class TestF2RestrictFK:
    """F2: RESTRICT FK — istorijski binding ne sme izgubiti target pri hard-delete-u."""

    def test_delete_task_with_binding_is_rejected(self, db_session: Session):
        project = _project(db_session)
        task = _task(db_session, project, "R1")
        ses = _session_service(db_session, project, task_id=task.id)
        task_id = task.id
        session_id = ses.id
        db_session.commit()

        # Zatvori sesiju (binding postaje istorijski)
        svc = SessionTaskBindingService(db_session)
        svc.close_active_binding(session_id)
        db_session.commit()

        # Pokušaj brisanja Task-a direktno na DB nivou — RESTRICT odbija
        from sqlalchemy.exc import IntegrityError

        db_session.delete(task)
        with pytest.raises(IntegrityError):
            db_session.flush()

        db_session.rollback()

        # Binding MORA ostati TASK, ne UNASSIGNED
        bindings = svc.get_bindings(session_id)
        assert len(bindings) >= 1
        found = [b for b in bindings if b.task_id == task_id]
        assert len(found) == 1, "Istorijski binding mora zadržati task_id"

    def test_delete_task_with_binding_http_returns_409(self, db_session: Session):
        project = _project(db_session)
        task = _task(db_session, project, "R2")
        ses = _session_service(db_session, project, task_id=task.id)
        task_id = task.id
        session_id = ses.id
        svc = SessionTaskBindingService(db_session)
        svc.close_active_binding(session_id)
        db_session.commit()

        app = FastAPI()
        app.include_router(tasks_router)
        factory = sessionmaker(bind=db_session.get_bind())
        app.state.session_factory = factory

        client = TestClient(app)
        resp = client.delete(f"/tasks/{task_id}")
        assert resp.status_code == 409, f"Očekivan 409, dobijen {resp.status_code}: {resp.text}"

    def test_plan_item_fk_is_also_restricted(self, db_session: Session):
        """F2: PlanItem FK takođe RESTRICT — istorijski binding ne sme izgubiti target."""
        project = _project(db_session)
        plan = Plan(id="plan-f2", project_id=project.id, title="TP", status="ACTIVE")
        phase = PlanPhase(id="phase-f2", plan_id="plan-f2", phase_key="F0", title="F0", sequence=0)
        item = PlanItem(id="item-f2", plan_phase_id="phase-f2", item_key="F2-TEST", title="F2 item")
        db_session.add_all([plan, phase, item])
        db_session.commit()

        ses = _session_service(db_session, project, plan_item_id=item.id)
        session_id = ses.id
        svc = SessionTaskBindingService(db_session)
        svc.close_active_binding(session_id)
        db_session.commit()

        # Pokušaj brisanja PlanItem-a
        db_session.delete(item)
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

        # Binding mora ostati PLAN_ITEM
        bindings = svc.get_bindings(session_id)
        assert len(bindings) >= 1
        assert any(b.plan_item_id == item.id for b in bindings), "PlanItem FK RESTRICT"


class TestF3Concurrency:
    """F3: konkurentni switch — IntegrityError → 409."""

    def test_concurrent_switch_returns_409(self, db_session: Session, monkeypatch):
        project = _project(db_session)
        task_a = _task(db_session, project, "A")
        ses = _session_service(db_session, project, task_id=task_a.id)
        session_id = ses.id
        db_session.commit()

        def _raise_integrity_error(*args, **kwargs):  # noqa: ARG001
            raise IntegrityError("concurrent active binding", {}, Exception("unique"))

        monkeypatch.setattr(SessionTaskBindingService, "switch_binding", _raise_integrity_error)
        client = _client_for(db_session)
        resp = client.post(
            f"/sessions/{session_id}/bindings/switch",
            json={"task_id": None, "plan_item_id": None},
        )
        assert resp.status_code == 409
        assert "Osvježi stanje" in resp.json()["detail"]


class TestLegacySession:
    """Regresioni test za legacy sesiju bez bindinga."""

    def test_close_active_binding_on_legacy_session_is_safe(self, db_session: Session):
        """Zatvaranje bindinga na istorijskoj sesiji bez binding zapisa ne baca grešku."""
        project = _project(db_session)
        ses = AgentSession(
            project_id=project.id,
            agent_type="codex",
            repo_path=project.repo_path,
            status="ACTIVE",
            started_at=datetime.now(tz=UTC),
        )
        db_session.add(ses)
        db_session.flush()
        db_session.commit()

        svc = SessionTaskBindingService(db_session)
        result = svc.close_active_binding(ses.id)
        assert result is None


class TestTimestampValidation:
    """Timestamp validacija: switch sa starijim vremenom se odbija."""

    def test_switch_with_older_timestamp_is_rejected(self, db_session: Session):
        project = _project(db_session)
        task_a = _task(db_session, project, "A")
        task_b = _task(db_session, project, "B")
        ses = _session_service(db_session, project, task_id=task_a.id)
        session_id = ses.id
        db_session.commit()

        svc = SessionTaskBindingService(db_session)
        active = svc.get_active_binding(session_id)
        assert active is not None

        # switched_at pre started_at aktivnog bindinga
        old_time = active.started_at - timedelta(hours=1)

        with pytest.raises(ValueError, match="ne može završiti prije početka"):
            svc.switch_binding(session_id, task_id=task_b.id, switched_at=old_time)

        # Aktivni binding mora ostati netaknut
        active_after = svc.get_active_binding(session_id)
        assert active_after is not None
        assert active_after.task_id == task_a.id
