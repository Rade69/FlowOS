"""Regresioni testovi za SessionService plan_item validaciju."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.runtime import RuntimeManager


def test_create_session_accepts_valid_plan_item_id():
    engine = create_engine(
        "sqlite:///file:test_sessions_plan_item?mode=memory&cache=shared",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_connection, connection_record):  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    import flowos.service.services.infrastructure.persistence.models  # noqa: F401
    import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401

    Base.metadata.create_all(engine)
    try:
        from flowos.service.controllers.http.projects import router as projects_router
        from flowos.service.controllers.http.sessions import router as sessions_router
        from flowos.service.services.infrastructure.persistence.plan_models import (
            Plan,
            PlanItem,
            PlanPhase,
        )

        app = FastAPI(title="FlowOS Test", version="0.1.0")
        app.include_router(projects_router)
        app.include_router(sessions_router)
        app.state.session_factory = sessionmaker(bind=engine)
        app.state.runtime = RuntimeManager()

        with TestClient(app) as client:
            project = client.post(
                "/projects", json={"name": "Plan Session", "repo_path": "C:/plan-session"}
            ).json()
            factory = sessionmaker(bind=engine)
            with factory() as db:
                plan = Plan(project_id=project["id"], title="Plan", status="ACTIVE")
                db.add(plan)
                db.flush()
                phase = PlanPhase(plan_id=plan.id, phase_key="F0", title="Faza 0", sequence=0)
                db.add(phase)
                db.flush()
                item = PlanItem(plan_phase_id=phase.id, item_key="FLOW-1", title="Item")
                db.add(item)
                db.commit()
                item_id = item.id

            resp = client.post(
                "/sessions",
                json={
                    "project_id": project["id"],
                    "agent_type": "codex",
                    "repo_path": "C:/plan-session",
                    "plan_item_id": item_id,
                },
            )
            assert resp.status_code == 200
            assert resp.json()["plan_item_id"] == item_id
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
