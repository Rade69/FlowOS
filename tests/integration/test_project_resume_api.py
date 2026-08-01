"""API testovi za Project Resume endpoint-e."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.models import AgentSession, Project
from flowos.service.services.infrastructure.persistence.plan_models import Plan, PlanItem, PlanPhase
from flowos.service.services.infrastructure.runtime import RuntimeManager


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///file:test_resume_api?mode=memory&cache=shared",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

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
def app(engine):
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from flowos.service.controllers.http.project_resume import router as resume_router
    from flowos.service.controllers.http.projects import router as projects_router
    from flowos.service.controllers.http.tasks import router as tasks_router

    app = FastAPI(title="FlowOS Test", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(projects_router)
    app.include_router(tasks_router)
    app.include_router(resume_router)
    app.state.session_factory = sessionmaker(bind=engine)
    app.state.runtime = RuntimeManager()
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════════


class TestResumeAPI:
    @pytest.fixture
    def project_id(self, client: TestClient):
        r = client.post("/projects", json={"name": "P", "repo_path": "C:/p"})
        return r.json()["id"]

    def test_resume_no_history(self, client: TestClient, project_id: str):
        resp = client.get(f"/projects/{project_id}/resume")
        assert resp.status_code == 200
        data = resp.json()
        assert data["resume_status"] == "NO_HISTORY"
        assert data["confidence"] == "LOW"

    def test_resume_with_plan(self, client: TestClient, project_id: str, engine):
        # Dodaj plan kroz bazu direktno
        factory = sessionmaker(bind=engine)
        with factory() as s:
            p = s.get(Project, project_id)
            plan = Plan(project_id=project_id, title="Plan", status="ACTIVE")
            s.add(plan)
            s.flush()
            phase = PlanPhase(plan_id=plan.id, phase_key="F0", title="F0", sequence=0)
            s.add(phase)
            s.flush()
            item = PlanItem(
                plan_phase_id=phase.id, item_key="FLOW-001", title="Test", status="IN_PROGRESS"
            )
            s.add(item)
            sess = AgentSession(project_id=project_id, agent_type="pi", repo_path="C:/p")
            s.add(sess)
            s.commit()

        client.post(f"/projects/{project_id}/resume/regenerate")
        resp = client.get(f"/projects/{project_id}/resume")
        assert resp.status_code == 200
        data = resp.json()
        assert data["resume_status"] == "READY_TO_CONTINUE"
        assert data["where_stopped"] is not None

    def test_regenerate(self, client: TestClient, project_id: str):
        resp = client.post(f"/projects/{project_id}/resume/regenerate")
        assert resp.status_code == 200
        assert resp.json()["resume_status"] == "NO_HISTORY"

    def test_workspace_state_empty(self, client: TestClient, project_id: str):
        resp = client.get(f"/projects/{project_id}/workspace-state")
        assert resp.status_code == 200
        assert resp.json()["status"] == "NO_HISTORY"

    def test_external_activity_crud(self, client: TestClient, project_id: str):
        # Kreiraj
        resp = client.post(
            f"/projects/{project_id}/external-activity",
            json={"source": "IDE", "summary": "Ručna izmena README.md"},
        )
        assert resp.status_code == 200
        assert resp.json()["source"] == "IDE"

        # Listaj
        resp = client.get(f"/projects/{project_id}/external-activity")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1
