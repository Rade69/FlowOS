"""Composition-root testovi — od servisnog wiring-a do create_app() lifespan-a."""

import contextlib
import os
import tempfile
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import flowos.service.services.infrastructure.persistence.activity_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.conflict_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.report_models  # noqa: F401
from flowos.service.composition_root import create_app
from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.conflict_models import Conflict
from flowos.service.services.infrastructure.persistence.models import AgentSession, Project
from flowos.service.services.infrastructure.watcher import WatcherPipeline


class NoOpRuntimeManager:
    """RuntimeManager bez mutex-a — za testiranje."""

    def __init__(self):
        self.pid = os.getpid()
        self.port = 9101

    def acquire_lock(self) -> None:
        pass

    def release_lock(self) -> None:
        pass

    def delete_descriptor(self) -> None:
        pass


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    with contextlib.suppress(OSError):
        os.unlink(path)


@pytest.fixture
def engine(db_path):
    eng = create_engine(
        f"sqlite:///{db_path}", echo=False, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def app(db_path):
    engine = create_engine(
        f"sqlite:///{db_path}", echo=False, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    runtime = NoOpRuntimeManager()
    return create_app(runtime, engine=engine)


class TestCreateAppLifespan:
    """Pravi create_app() testovi sa lifespan-om."""

    def test_health_endpoint(self, app):
        """create_app() proizvodi funkcionalnu aplikaciju."""
        with TestClient(app) as client:
            resp = client.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

    def test_app_state_initialized_by_lifespan(self, app):
        """Lifespan startup inicijalizuje app.state."""
        with TestClient(app) as client:
            st = client.app.state
            assert hasattr(st, "runtime")
            assert hasattr(st, "session_factory")
            assert hasattr(st, "complete_session")
            assert hasattr(st, "watchers")
            assert isinstance(st.watchers, dict)

    def test_project_and_session_crud(self, app):
        """API rute za projekte i sesije rade kroz stvarni create_app."""
        with TestClient(app) as client:
            resp = client.post("/projects", json={"name": "CRT", "repo_path": "C:/t"})
            assert resp.status_code == 200
            pid = resp.json()["id"]

            resp = client.post(
                "/sessions",
                json={"project_id": pid, "agent_type": "cc", "repo_path": "C:/t"},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "ACTIVE"

    def test_watcher_activity_conflict_service_wiring(self, app, tmp_path: Path):
        """Servisni integracioni test: watcher → ActivityService → conflict callback → WRITE_WRITE.

        Koristi isti wiring pattern kao composition_root lifespan, ali kroz direktne
        servisne pozive jer lifespan ne pokreće watcher za dinamički dodate projekte.
        """
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / "src").mkdir()
        test_file = repo_path / "src" / "app.py"
        test_file.write_text("# test\n")
        repo_str = str(repo_path)

        with TestClient(app) as client:
            resp = client.post("/projects", json={"name": "WR", "repo_path": repo_str})
            assert resp.status_code == 200
            project_id = resp.json()["id"]

            resp_a = client.post(
                "/sessions",
                json={"project_id": project_id, "agent_type": "cc", "repo_path": repo_str},
            )
            resp_b = client.post(
                "/sessions",
                json={"project_id": project_id, "agent_type": "pi", "repo_path": repo_str},
            )
            assert resp_a.status_code == 200
            assert resp_b.status_code == 200
            session_a_id = resp_a.json()["id"]
            session_b_id = resp_b.json()["id"]

            # Direktan pristup bazi — koristimo app.state.session_factory
            db = client.app.state.session_factory()
            try:
                from flowos.service.services.activity.service import ActivityService
                from flowos.service.services.attribution.service import ActiveSession
                from flowos.service.services.conflicts.service import ConflictDetectionService

                activity_svc = ActivityService(db)
                conflict_svc = ConflictDetectionService(db)
                active_both = [
                    ActiveSession(session_id=session_a_id, repo_path=repo_str),
                    ActiveSession(session_id=session_b_id, repo_path=repo_str),
                ]

                def conflict_cb(act):
                    conflict_svc.on_file_activity(act, active_both)
                    db.commit()

                activity_svc.register_conflict_callback(conflict_cb)
                activity_svc.record_file_event(
                    file_path=str(test_file),
                    event_type="MODIFIED",
                    project_id=project_id,
                    repo_path=repo_str,
                    active_sessions=[ActiveSession(session_id=session_a_id, repo_path=repo_str)],
                )
                activity_svc.record_file_event(
                    file_path=str(test_file),
                    event_type="MODIFIED",
                    project_id=project_id,
                    repo_path=repo_str,
                    active_sessions=[ActiveSession(session_id=session_b_id, repo_path=repo_str)],
                )
                db.commit()

                conflicts = (
                    db.query(Conflict)
                    .filter(
                        Conflict.project_id == project_id, Conflict.conflict_type == "WRITE_WRITE"
                    )
                    .all()
                )
                assert len(conflicts) >= 1, (
                    f"WRITE_WRITE nije detektovan. Dobijeno: {len(conflicts)}"
                )
                assert conflicts[0].conflict_key is not None
                assert conflicts[0].conflict_level == "HIGH"
            finally:
                db.close()

    def test_lifespan_cleanup_no_exceptions(self, app):
        """Lifespan shutdown ne baca izuzetke."""
        with TestClient(app):
            pass
        # Ako je došlo do ovde bez exception-a, cleanup je prošao


class TestServiceWiringIntegration:
    """Servisni integracioni testovi — watcher callback pattern."""

    def test_watcher_callback_produces_activity(self, engine, tmp_path: Path):
        """Watcher callback proizvodi FileActivity kroz isti pattern kao composition_root."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / "src").mkdir()
        test_file = repo_path / "src" / "app.py"
        test_file.write_text("# test\n")
        repo_str = str(repo_path)
        project_id = "sw-proj-001"

        db = Session(engine)
        try:
            project = Project(id=project_id, name="SW Test", repo_path=repo_str)
            db.add(project)
            db.add_all(
                [
                    AgentSession(
                        id="sw-a",
                        project_id=project_id,
                        agent_type="cc",
                        repo_path=repo_str,
                        status="ACTIVE",
                    ),
                    AgentSession(
                        id="sw-b",
                        project_id=project_id,
                        agent_type="pi",
                        repo_path=repo_str,
                        status="ACTIVE",
                    ),
                ]
            )
            db.flush()
            db.commit()

            from flowos.service.services.activity.service import ActivityService
            from flowos.service.services.attribution.service import ActiveSession
            from flowos.service.services.conflicts.service import ConflictDetectionService
            from flowos.shared.enums.session import SessionStatus

            events_received: list = []

            def watcher_callback(event):
                events_received.append(event)
                cb_db = Session(engine)
                try:
                    active_sessions_raw = (
                        cb_db.query(AgentSession)
                        .filter(
                            AgentSession.project_id == project_id,
                            AgentSession.status.in_(
                                (SessionStatus.ACTIVE.value, SessionStatus.IDLE.value)
                            ),
                        )
                        .all()
                    )
                    active = [
                        ActiveSession(
                            session_id=s.id, worktree_path=s.worktree_path, repo_path=s.repo_path
                        )
                        for s in active_sessions_raw
                    ]
                    activity_svc = ActivityService(cb_db)
                    if len(active) >= 2:

                        def _cb(act):
                            cs = ConflictDetectionService(cb_db)
                            cs.on_file_activity(act, active)
                            cb_db.commit()

                        activity_svc.register_conflict_callback(_cb)
                    activity_svc.record_file_event(
                        file_path=event.path,
                        event_type=event.event_type,
                        project_id=project_id,
                        repo_path=repo_str,
                        active_sessions=active,
                        source="WATCHER",
                    )
                    cb_db.commit()
                except Exception:
                    cb_db.rollback()
                    raise
                finally:
                    cb_db.close()

            watcher = WatcherPipeline(callback=watcher_callback, debounce_ms=200)
            watcher.start(repo_str)
            assert watcher.is_running
            try:
                time.sleep(0.5)
                test_file.write_text("# modified\n")
                time.sleep(2.0)
                assert len(events_received) >= 1
            finally:
                watcher.stop()
                assert not watcher.is_running

            from flowos.service.services.infrastructure.persistence.activity_models import (
                FileActivity,
            )

            check_db = Session(engine)
            try:
                activities = (
                    check_db.query(FileActivity).filter(FileActivity.project_id == project_id).all()
                )
                assert len([a for a in activities if "app.py" in a.file_path]) >= 1
            finally:
                check_db.close()
        finally:
            db.close()

    def test_no_watcher_leftovers_after_shutdown(self, tmp_path: Path):
        """Potvrđuje da nema aktivnih watcher threadova posle stop()."""
        repo_path = tmp_path / "repo2"
        repo_path.mkdir()
        watcher = WatcherPipeline(callback=lambda e: None, debounce_ms=100)
        watcher.start(str(repo_path))
        assert watcher.is_running
        watcher.stop()
        assert not watcher.is_running
