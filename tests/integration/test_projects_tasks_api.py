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

    import flowos.service.services.infrastructure.persistence.conflict_models  # noqa: F401
    import flowos.service.services.infrastructure.persistence.models  # noqa: F401
    import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
    import flowos.service.services.infrastructure.persistence.resume_models  # noqa: F401
    import flowos.service.services.infrastructure.persistence.worktree_models  # noqa: F401

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
        assert resp.status_code == 422

    def test_create_invalid_repo_path(self, client: TestClient):
        resp = client.post("/projects", json={"name": "Test", "repo_path": "relative"})
        assert resp.status_code == 422

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

    def test_timeline_filters_session_events_by_session_project(self, client: TestClient, engine):
        from flowos.service.services.infrastructure.persistence.models import (
            AgentSession,
            SessionEvent,
        )

        project_a = client.post("/projects", json={"name": "A", "repo_path": "C:/a"}).json()
        project_b = client.post("/projects", json={"name": "B", "repo_path": "C:/b"}).json()
        factory = sessionmaker(bind=engine)
        with factory() as db:
            session_a = AgentSession(
                project_id=project_a["id"],
                agent_type="codex",
                repo_path="C:/a",
            )
            session_b = AgentSession(
                project_id=project_b["id"],
                agent_type="crush",
                repo_path="C:/b",
            )
            db.add_all([session_a, session_b])
            db.flush()
            db.add_all(
                [
                    SessionEvent(
                        session_id=session_a.id,
                        event_type="A_EVENT",
                        summary="Event za projekat A",
                    ),
                    SessionEvent(
                        session_id=session_b.id,
                        event_type="B_EVENT",
                        summary="Event za projekat B",
                    ),
                ]
            )
            db.commit()

        resp = client.get(f"/projects/{project_a['id']}/timeline")
        assert resp.status_code == 200
        session_events = [item for item in resp.json() if item["type"] == "SESSION"]
        assert [item["event"] for item in session_events] == ["A_EVENT"]

    def test_project_state_uses_existing_workspace_and_worktree_fields(
        self, client: TestClient, engine
    ):
        from flowos.service.services.infrastructure.persistence.resume_models import (
            ProjectWorkspaceState,
        )
        from flowos.service.services.infrastructure.persistence.worktree_models import Worktree

        project = client.post("/projects", json={"name": "State", "repo_path": "C:/state"}).json()
        factory = sessionmaker(bind=engine)
        with factory() as db:
            db.add(
                ProjectWorkspaceState(
                    project_id=project["id"],
                    last_known_status_porcelain=" M src/app.py",
                    reconciliation_status="CURRENT",
                )
            )
            db.add(
                Worktree(
                    project_id=project["id"],
                    worktree_path="C:/state-wt",
                    branch_name="flowos/test",
                    is_clean=False,
                )
            )
            db.commit()

        resp = client.get(f"/projects/{project['id']}/state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["git_dirty"] is True
        assert data["dirty_worktrees"] == 1


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
        assert resp.status_code == 422

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

    def test_t1_unassigned_task_returns_plan_item_id_null(
        self, client: TestClient, project_id: str
    ):
        """FLOW-1202A T1: Task bez PlanItem veze mora eksplicitno vratiti null."""
        client.post("/tasks", json={"project_id": project_id, "title": "Unassigned"})
        resp = client.get(f"/tasks?project_id={project_id}")
        assert resp.status_code == 200
        tasks = resp.json()
        assert len(tasks) == 1
        assert "plan_item_id" in tasks[0]
        assert tasks[0]["plan_item_id"] is None

    def test_t2_linked_task_returns_plan_item_id(self, client: TestClient, project_id: str, engine):
        """FLOW-1202A T2: Task vezan za PlanItem vraća tačan plan_item_id kroz HTTP."""
        from flowos.service.services.infrastructure.persistence.models import Task
        from flowos.service.services.infrastructure.persistence.plan_models import (
            Plan,
            PlanItem,
            PlanPhase,
        )

        factory = sessionmaker(bind=engine)
        with factory() as db:
            plan = Plan(project_id=project_id, title="Plan", status="DRAFT")
            db.add(plan)
            db.flush()
            phase = PlanPhase(plan_id=plan.id, phase_key="F1", title="Faza 1", sequence=1)
            db.add(phase)
            db.flush()
            item = PlanItem(
                plan_phase_id=phase.id,
                item_key="FLOW-001",
                title="Item",
                sequence=0,
                risk_level="MEDIUM",
                status="NOT_STARTED",
            )
            db.add(item)
            db.flush()
            task = Task(project_id=project_id, title="Linked", plan_item_id=item.id)
            db.add(task)
            db.commit()
            item_id = item.id

        resp = client.get(f"/tasks?project_id={project_id}")
        assert resp.status_code == 200
        tasks = resp.json()
        assert len(tasks) == 1
        assert tasks[0]["plan_item_id"] == item_id

    def test_t3_project_scoping(self, client: TestClient):
        """FLOW-1202A T3: GET /tasks?project_id=A vraća samo Task A."""
        a = client.post("/projects", json={"name": "A", "repo_path": "C:/a"}).json()
        b = client.post("/projects", json={"name": "B", "repo_path": "C:/b"}).json()
        client.post("/tasks", json={"project_id": a["id"], "title": "Task A"})
        client.post("/tasks", json={"project_id": b["id"], "title": "Task B"})

        resp = client.get(f"/tasks?project_id={a['id']}")
        assert resp.status_code == 200
        tasks = resp.json()
        assert [t["title"] for t in tasks] == ["Task A"]
