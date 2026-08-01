"""API testovi za Plan Progress endpoint-e."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.models import Project
from flowos.service.services.infrastructure.persistence.plan_models import (
    Plan,
    PlanItem,
    PlanItemCriterion,
    PlanPhase,
)
from flowos.service.services.infrastructure.runtime import RuntimeManager


@pytest.fixture
def engine():
    """SQLite engine sa deljenom :memory: bazom (StaticPool)."""
    eng = create_engine(
        "sqlite:///file:test_plan_api?mode=memory&cache=shared",
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

    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def runtime():
    mgr = RuntimeManager()
    return mgr


@pytest.fixture
def app(runtime, engine):
    """FastAPI app sa testnim engine-om, bez lifespan-a."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(title="FlowOS Test", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    from flowos.service.controllers.http.plan_progress import router as plan_progress_router
    from flowos.service.controllers.http.system import router as system_router

    app.include_router(system_router, tags=["System"])
    app.include_router(plan_progress_router, tags=["Plan Progress"])
    app.state.session_factory = sessionmaker(bind=engine)
    app.state.runtime = runtime
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def project_id(app):
    """Kreira projekat i vraća ID."""
    factory = app.state.session_factory
    with factory() as s:
        p = Project(name="Test", repo_path="C:/test")
        s.add(p)
        s.commit()
        return p.id


@pytest.fixture
def plan_data(app, project_id):
    """Kreira Plan + PlanPhase + 2 PlanItem-a sa kriterijumima. Vraća dict ID-jeva."""
    factory = app.state.session_factory
    with factory() as s:
        plan = Plan(project_id=project_id, title="Test Plan", status="DRAFT")
        s.add(plan)
        s.flush()

        phase = PlanPhase(plan_id=plan.id, phase_key="F0", title="Faza 0", sequence=0)
        s.add(phase)
        s.flush()

        item_ids = []
        for i, (key, title) in enumerate([("FLOW-001", "First"), ("FLOW-002", "Second")]):
            item = PlanItem(
                plan_phase_id=phase.id,
                item_key=key,
                title=title,
                sequence=i,
                risk_level="MEDIUM",
                status="NOT_STARTED",
            )
            s.add(item)
            s.flush()
            item_ids.append(item.id)

            crit = PlanItemCriterion(
                plan_item_id=item.id,
                criterion_key="TEST",
                description="Must pass tests",
                status="PENDING",
            )
            s.add(crit)

        s.commit()
        return {
            "plan_id": plan.id,
            "phase_id": phase.id,
            "item_ids": item_ids,
            "project_id": project_id,
        }


# ═══════════════════════════════════════════════════════════════════
# Plan progres
# ═══════════════════════════════════════════════════════════════════


class TestPlanProgress:
    def test_get_project_progress_empty(self, client: TestClient, project_id: str):
        resp = client.get(f"/projects/{project_id}/plan-progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_items"] == 0

    def test_get_project_progress_with_plan(self, client: TestClient, plan_data: dict):
        pid = plan_data["project_id"]
        resp = client.get(f"/projects/{pid}/plan-progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] is not None
        assert data["plan"]["status"] == "DRAFT"
        assert data["total_items"] == 2

    def test_list_plan_items(self, client: TestClient, plan_data: dict):
        plan_id = plan_data["plan_id"]
        resp = client.get(f"/plans/{plan_id}/items")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert len(data[0]["items"]) == 2

    def test_get_plan_item(self, client: TestClient, plan_data: dict):
        item_id = plan_data["item_ids"][0]
        resp = client.get(f"/plan-items/{item_id}")
        assert resp.status_code == 200
        assert resp.json()["item_key"] == "FLOW-001"

    def test_get_plan_item_404(self, client: TestClient):
        resp = client.get("/plan-items/nepostojeci")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# Statusne akcije
# ═══════════════════════════════════════════════════════════════════


class TestStatusActions:
    def test_start_item(self, client: TestClient, plan_data: dict):
        item_id = plan_data["item_ids"][0]
        resp = client.post(f"/plan-items/{item_id}/start", json={"reason": "Pocinje sesija"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "IN_PROGRESS"

    def test_mark_implemented(self, client: TestClient, plan_data: dict):
        item_id = plan_data["item_ids"][0]
        client.post(f"/plan-items/{item_id}/start")
        resp = client.post(
            f"/plan-items/{item_id}/mark-implemented", json={"reason": "Agent zavrsio"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "IMPLEMENTED"

    def test_verify(self, client: TestClient, plan_data: dict):
        item_id = plan_data["item_ids"][0]
        client.post(f"/plan-items/{item_id}/start")
        client.post(f"/plan-items/{item_id}/mark-implemented")
        resp = client.post(f"/plan-items/{item_id}/verify", json={"reason": "Testovi prolaze"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "VERIFIED"

    def test_accept(self, client: TestClient, plan_data: dict):
        item_id = plan_data["item_ids"][0]
        client.post(f"/plan-items/{item_id}/start")
        client.post(f"/plan-items/{item_id}/mark-implemented")
        client.post(f"/plan-items/{item_id}/verify")
        resp = client.post(f"/plan-items/{item_id}/accept", json={"reason": "Korisnik potvrdio"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ACCEPTED"

    def test_block_and_unblock(self, client: TestClient, plan_data: dict):
        item_id = plan_data["item_ids"][0]
        client.post(f"/plan-items/{item_id}/start")
        resp = client.post(f"/plan-items/{item_id}/block", json={"reason": "Blokirano"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "BLOCKED"

        resp = client.post(f"/plan-items/{item_id}/unblock")
        assert resp.status_code == 200
        assert resp.json()["status"] == "IN_PROGRESS"

    def test_invalid_transition_returns_409(self, client: TestClient, plan_data: dict):
        item_id = plan_data["item_ids"][0]
        resp = client.post(f"/plan-items/{item_id}/accept", json={"reason": "Skoci"})
        assert resp.status_code == 409


# ═══════════════════════════════════════════════════════════════════
# Kriterijumi i progres
# ═══════════════════════════════════════════════════════════════════


class TestCriteriaAndEvents:
    def test_list_criteria(self, client: TestClient, plan_data: dict):
        item_id = plan_data["item_ids"][0]
        resp = client.get(f"/plan-items/{item_id}/criteria")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_update_criterion(self, client: TestClient, plan_data: dict):
        item_id = plan_data["item_ids"][0]
        resp = client.get(f"/plan-items/{item_id}/criteria")
        crit_id = resp.json()[0]["id"]

        resp = client.patch(
            f"/plan-item-criteria/{crit_id}",
            json={"status": "PASSED", "verification_summary": "Sve OK"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "PASSED"

    def test_progress_events(self, client: TestClient, plan_data: dict):
        item_id = plan_data["item_ids"][0]
        client.post(f"/plan-items/{item_id}/start")
        client.post(f"/plan-items/{item_id}/mark-implemented")

        resp = client.get(f"/plan-items/{item_id}/progress-events")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2


# ═══════════════════════════════════════════════════════════════════
# Import
# ═══════════════════════════════════════════════════════════════════


class TestPlanImportApi:
    SAMPLE_MD = """# Test Plan
## Faza 0 — Test
#### FLOW-001 — Test item
**Rizik:** LOW
Opis stavke.
**Dokaz:** test prolazi.
"""

    def test_import_plan(self, client: TestClient, project_id: str):
        resp = client.post(
            f"/projects/{project_id}/import-plan",
            json={"markdown_text": self.SAMPLE_MD},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == 1
        assert data["phases"] == 1

    def test_import_empty_returns_400(self, client: TestClient, project_id: str):
        resp = client.post(
            f"/projects/{project_id}/import-plan",
            json={"markdown_text": ""},
        )
        assert resp.status_code == 400

    def test_activate_plan(self, client: TestClient, project_id: str):
        resp = client.post(
            f"/projects/{project_id}/import-plan",
            json={"markdown_text": self.SAMPLE_MD},
        )
        plan_id = resp.json()["plan_id"]

        resp = client.post(f"/plans/{plan_id}/activate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ACTIVE"

        # Drugi put — 409 jer je već ACTIVE
        resp = client.post(f"/plans/{plan_id}/activate")
        assert resp.status_code == 409
