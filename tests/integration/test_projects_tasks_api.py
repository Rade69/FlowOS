"""API testovi za Projects i Tasks endpoint-e."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.runtime import RuntimeManager


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///file:test_projects?mode=memory&cache=shared",
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

    from flowos.service.controllers.http.projects import router as projects_router
    from flowos.service.controllers.http.system import router as system_router
    from flowos.service.controllers.http.tasks import router as tasks_router

    app = FastAPI(title="FlowOS Test", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(system_router)
    app.include_router(projects_router)
    app.include_router(tasks_router)
    app.state.session_factory = sessionmaker(bind=engine)
    app.state.runtime = RuntimeManager()
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════════
# Projects CRUD
# ═══════════════════════════════════════════════════════════════════


class TestProjectsAPI:
    def test_create(self, client: TestClient):
        resp = client.post("/projects", json={"name": "FlowOS", "repo_path": "C:/test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "FlowOS"
        assert data["status"] == "ACTIVE"

    def test_create_missing_name(self, client: TestClient):
        resp = client.post("/projects", json={"repo_path": "C:/test"})
        assert resp.status_code == 400

    def test_create_invalid_repo_path(self, client: TestClient):
        resp = client.post("/projects", json={"name": "Test", "repo_path": "relative"})
        assert resp.status_code == 400

    def test_list(self, client: TestClient):
        client.post("/projects", json={"name": "A", "repo_path": "C:/a"})
        client.post("/projects", json={"name": "B", "repo_path": "C:/b"})
        resp = client.get("/projects")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get(self, client: TestClient):
        r = client.post("/projects", json={"name": "Test", "repo_path": "C:/test"})
        pid = r.json()["id"]
        resp = client.get(f"/projects/{pid}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test"

    def test_get_404(self, client: TestClient):
        resp = client.get("/projects/nepostojeci")
        assert resp.status_code == 404

    def test_update(self, client: TestClient):
        r = client.post("/projects", json={"name": "Old", "repo_path": "C:/old"})
        pid = r.json()["id"]
        resp = client.patch(f"/projects/{pid}", json={"name": "New"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New"

    def test_delete(self, client: TestClient):
        r = client.post("/projects", json={"name": "Del", "repo_path": "C:/del"})
        pid = r.json()["id"]
        resp = client.delete(f"/projects/{pid}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        # Treba da vrati 404
        resp = client.get(f"/projects/{pid}")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# Tasks CRUD
# ═══════════════════════════════════════════════════════════════════


class TestTasksAPI:
    @pytest.fixture
    def project_id(self, client: TestClient):
        r = client.post("/projects", json={"name": "P", "repo_path": "C:/p"})
        return r.json()["id"]

    def test_create(self, client: TestClient, project_id: str):
        resp = client.post(
            "/tasks", json={"project_id": project_id, "title": "Implementirati login"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Implementirati login"
        assert data["status"] == "OPEN"
        assert data["priority"] == "NORMAL"

    def test_create_missing_project(self, client: TestClient):
        resp = client.post("/tasks", json={"title": "Test"})
        assert resp.status_code == 400

    def test_list(self, client: TestClient, project_id: str):
        client.post("/tasks", json={"project_id": project_id, "title": "A"})
        client.post("/tasks", json={"project_id": project_id, "title": "B"})
        resp = client.get(f"/tasks?project_id={project_id}")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get(self, client: TestClient, project_id: str):
        r = client.post("/tasks", json={"project_id": project_id, "title": "Test"})
        tid = r.json()["id"]
        resp = client.get(f"/tasks/{tid}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Test"

    def test_get_404(self, client: TestClient):
        resp = client.get("/tasks/nepostojeci")
        assert resp.status_code == 404

    def test_update(self, client: TestClient, project_id: str):
        r = client.post("/tasks", json={"project_id": project_id, "title": "Old"})
        tid = r.json()["id"]
        resp = client.patch(f"/tasks/{tid}", json={"title": "New", "status": "IN_PROGRESS"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "New"
        assert resp.json()["status"] == "IN_PROGRESS"

    def test_delete(self, client: TestClient, project_id: str):
        r = client.post("/tasks", json={"project_id": project_id, "title": "Del"})
        tid = r.json()["id"]
        resp = client.delete(f"/tasks/{tid}")
        assert resp.status_code == 200

        resp = client.get(f"/tasks/{tid}")
        assert resp.status_code == 404
