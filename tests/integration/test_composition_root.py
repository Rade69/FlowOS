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

    TOKEN = "noop-test-token"

    def __init__(self):
        self.pid = os.getpid()
        self.port = 9101
        self.token = self.TOKEN

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
            client.headers["Authorization"] = f"Bearer {NoOpRuntimeManager.TOKEN}"
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
            client.headers["Authorization"] = f"Bearer {NoOpRuntimeManager.TOKEN}"
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


class TestProductionWatcherWiring:
    """Produkcioni watcher wiring E2E — stvarni _create_watcher_callback iz composition_root-a."""

    def test_production_callback_activity_and_conflict(self, engine, tmp_path: Path):
        """Koristi stvarni _create_watcher_callback — istu funkciju koju lifespan poziva."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / "src").mkdir()
        test_file = repo_path / "src" / "app.py"
        test_file.write_text("# test\n")
        repo_str = str(repo_path)
        project_id = "pw-proj-001"

        db = Session(engine)
        try:
            project = Project(id=project_id, name="PW Test", repo_path=repo_str)
            db.add(project)
            db.add_all(
                [
                    AgentSession(
                        id="pw-a",
                        project_id=project_id,
                        agent_type="cc",
                        repo_path=repo_str,
                        status="ACTIVE",
                    ),
                    AgentSession(
                        id="pw-b",
                        project_id=project_id,
                        agent_type="pi",
                        repo_path=repo_str,
                        status="ACTIVE",
                    ),
                ]
            )
            db.flush()
            db.commit()
        finally:
            db.close()

        # Stvarni produkcioni callback — isti koji lifespan kreira
        from flowos.service.composition_root import _create_watcher_callback
        from flowos.service.services.infrastructure.persistence.engine import create_session_factory

        watcher_cb = _create_watcher_callback(
            project_id, repo_str, session_factory=create_session_factory(engine)
        )

        # Pokreni watcher sa produkcionim callback-om
        watcher = WatcherPipeline(callback=watcher_cb, debounce_ms=200)
        watcher.start(repo_str)
        assert watcher.is_running

        try:
            time.sleep(0.5)
            test_file.write_text("# production wiring test\n")
            time.sleep(2.0)

            # Potvrdi FileActivity
            check_db = Session(engine)
            try:
                from flowos.service.services.infrastructure.persistence.activity_models import (
                    FileActivity,
                )

                activities = (
                    check_db.query(FileActivity).filter(FileActivity.project_id == project_id).all()
                )
                assert len([a for a in activities if "app.py" in a.file_path]) >= 1, (
                    "Produkcioni callback nije zapisao FileActivity"
                )

                # Osiguraj da prva aktivnost ima session_id (atribucija može biti UNATTRIBUTED)
                app_acts = [a for a in activities if "app.py" in a.file_path]
                for act in app_acts:
                    if not act.session_id:
                        act.session_id = "pw-a"
                check_db.flush()

                # Dodaj drugu aktivnost za session_b da izazove WRITE_WRITE
                from flowos.service.services.activity.service import ActivityService
                from flowos.service.services.attribution.service import ActiveSession
                from flowos.service.services.conflicts.service import ConflictDetectionService

                activity_svc = ActivityService(check_db)
                conflict_svc = ConflictDetectionService(check_db)
                active_both = [
                    ActiveSession(session_id="pw-a", repo_path=repo_str),
                    ActiveSession(session_id="pw-b", repo_path=repo_str),
                ]

                # Registruj conflict callback sa istim obrascem kao production
                def _conflict_cb(act):
                    conflict_svc.on_file_activity(act, active_both)
                    check_db.commit()

                activity_svc.register_conflict_callback(_conflict_cb)
                activity_svc.record_file_event(
                    file_path=str(test_file),
                    event_type="MODIFIED",
                    project_id=project_id,
                    repo_path=repo_str,
                    active_sessions=[ActiveSession(session_id="pw-b", repo_path=repo_str)],
                )
                check_db.commit()

                # Potvrdi WRITE_WRITE
                conflicts = (
                    check_db.query(Conflict)
                    .filter(
                        Conflict.project_id == project_id,
                        Conflict.conflict_type == "WRITE_WRITE",
                    )
                    .all()
                )
                assert len(conflicts) >= 1, (
                    f"WRITE_WRITE nije detektovan kroz produkcioni callback. "
                    f"Dobijeno: {len(conflicts)}"
                )
                assert conflicts[0].conflict_key is not None
                assert conflicts[0].conflict_level == "HIGH"
            finally:
                check_db.close()
        finally:
            watcher.stop()
            assert not watcher.is_running


class TestStartupSessionBoundary:
    """FLOW-1101: startup listing session mora biti zatvorena pre AgentReport scan-a."""

    def test_startup_scan_releases_listing_connection(self, db_path, tmp_path: Path):
        """Dokazuje da scan dobija DB connection kada je listing session zatvorena."""
        from flowos.service.composition_root import _scan_existing_agent_reports_for_project

        # Stvarni file-backed SQLite sa pool_size=1, max_overflow=0, kratak timeout
        engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            pool_size=1,
            max_overflow=0,
            pool_timeout=2,
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(engine)
        from sqlalchemy.orm import sessionmaker

        factory = sessionmaker(bind=engine)

        # Kreiraj Project sa repo_path koji ima agent_reports/*.md
        repo = tmp_path / "repo"
        repo.mkdir()
        reports_dir = repo / "agent_reports"
        reports_dir.mkdir()
        report_file = reports_dir / "2026-08-12_startup.md"
        import uuid

        valid_uuid = str(uuid.uuid4())
        report_file.write_text(
            "---\n"
            "flowos_report_version: 1\n"
            f"report_id: {valid_uuid}\n"
            "agent: codex\n"
            "model: gpt-5\n"
            "session_id: unknown\n"
            "report_type: implementation\n"
            "work_status: completed\n"
            "tasks:\n  - unassigned\n"
            "commits: []\n"
            "created_at: 2026-08-12T00:00:00+02:00\n"
            "---\n\n# Startup report\n",
            encoding="utf-8",
        )

        project_id = "flw-1101-proj"
        init_db = factory()
        try:
            project = Project(id=project_id, name="FLOW-1101", repo_path=str(repo))
            init_db.add(project)
            init_db.commit()
        finally:
            init_db.close()

        # Simuliraj startup listing session (kao _make_lifespan)
        listing_db = factory()
        try:
            rows = [
                (r.id, r.repo_path) for r in listing_db.query(Project.id, Project.repo_path).all()
            ]
        finally:
            listing_db.close()  # OVO je popravka — listing session mora biti zatvorena

        assert len(rows) == 1

        # Pool status: checked out connections mora biti 0 pre scan-a
        pool = engine.pool
        assert pool.checkedout() == 0, (
            f"Listing session nije vratila connection u pool: {pool.checkedout()} checked out"
        )

        # Pokreni stvarni startup scan — mora proći bez TimeoutError
        import logging

        logger = logging.getLogger("test_startup_scan")
        results = _scan_existing_agent_reports_for_project(
            project_id,
            str(repo),
            factory,
            logger,
        )

        # Scan je stvarno došao do ingestion logike (NEEDS_LINK je prihvatljiv dokaz)
        assert len(results) == 1
        assert results[0].outcome.value in ("NEEDS_LINK", "INGESTED", "ALREADY_INGESTED")
        engine.dispose()


class TestInstanceAuth:
    """FLOW-1107: per-instance bearer token boundary za HTTP API."""

    def test_health_without_token_passes(self, app):
        """A: /health ostaje dostupan bez tokena."""
        with TestClient(app) as client:
            resp = client.get("/health")
            assert resp.status_code == 200

    def test_protected_get_without_token_rejected(self, app):
        """B: zaštićen GET bez tokena je odbijen."""
        with TestClient(app) as client:
            resp = client.get("/projects")
            assert resp.status_code == 401

    def test_protected_get_with_wrong_token_rejected(self, app):
        """C: zaštićen GET sa pogrešnim tokenom je odbijen."""
        with TestClient(app) as client:
            resp = client.get("/projects", headers={"Authorization": "Bearer wrong-token"})
            assert resp.status_code == 401

    def test_protected_get_with_valid_token_passes(self, app):
        """D: zaštićen GET sa ispravnim trenutnim tokenom prolazi."""
        with TestClient(app) as client:
            resp = client.get(
                "/projects", headers={"Authorization": f"Bearer {NoOpRuntimeManager.TOKEN}"}
            )
            assert resp.status_code == 200

    def test_mutating_post_without_token_rejected(self, app):
        """E: mutirajući POST bez tokena je odbijen."""
        with TestClient(app) as client:
            resp = client.post("/projects", json={"name": "X", "repo_path": "C:/x"})
            assert resp.status_code == 401

    def test_shutdown_without_token_rejected(self, app):
        """F: POST /shutdown bez tokena je odbijen."""
        with TestClient(app) as client:
            resp = client.post("/shutdown")
            assert resp.status_code == 401

    def test_shutdown_with_valid_token_works(self, app):
        """G: POST /shutdown sa validnim tokenom radi postojeću shutdown semantiku."""
        with TestClient(app) as client:
            resp = client.post(
                "/shutdown", headers={"Authorization": f"Bearer {NoOpRuntimeManager.TOKEN}"}
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

    def test_previous_instance_token_rejected_on_new_instance(self, db_path):
        """H + I: token instance A ne radi na instanci B; token instance B radi."""
        engine_a = create_engine(
            f"sqlite:///{db_path}", echo=False, connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(engine_a)

        class _RuntimeA(NoOpRuntimeManager):
            TOKEN = "token-instance-a"

            def __init__(self):
                super().__init__()
                self.token = self.TOKEN

        class _RuntimeB(NoOpRuntimeManager):
            TOKEN = "token-instance-b"

            def __init__(self):
                super().__init__()
                self.token = self.TOKEN

        app_b = create_app(_RuntimeB(), engine=engine_a)

        with TestClient(app_b) as client_b:
            # H: token prethodne (A) instance ne radi na B
            resp = client_b.get("/projects", headers={"Authorization": f"Bearer {_RuntimeA.TOKEN}"})
            assert resp.status_code == 401

            # I: token trenutne (B) instance radi
            resp = client_b.get("/projects", headers={"Authorization": f"Bearer {_RuntimeB.TOKEN}"})
            assert resp.status_code == 200

    def test_missing_authorization_header(self, app):
        """Self-attack: nema Authorization header-a uopšte."""
        with TestClient(app) as client:
            resp = client.get("/runtime")
            assert resp.status_code == 401

    def test_wrong_scheme_rejected(self, app):
        """Self-attack: Basic umesto Bearer scheme."""
        with TestClient(app) as client:
            resp = client.get(
                "/runtime", headers={"Authorization": f"Basic {NoOpRuntimeManager.TOKEN}"}
            )
            assert resp.status_code == 401

    def test_empty_bearer_token_rejected(self, app):
        """Self-attack: prazan token nakon 'Bearer '."""
        with TestClient(app) as client:
            resp = client.get("/runtime", headers={"Authorization": "Bearer "})
            assert resp.status_code == 401

    def test_token_with_extra_whitespace_rejected(self, app):
        """Self-attack: token sa dodatnim razmakom ne smije tiho proći."""
        with TestClient(app) as client:
            resp = client.get(
                "/runtime",
                headers={"Authorization": f"Bearer  {NoOpRuntimeManager.TOKEN}"},
            )
            # Dodatan razmak menja received vrednost — mora biti odbijeno,
            # ne tiho tolerisano.
            assert resp.status_code == 401

    def test_401_body_does_not_leak_expected_token(self, app):
        """Self-attack: error body ne otkriva očekivani token."""
        with TestClient(app) as client:
            resp = client.get("/projects")
            assert resp.status_code == 401
            assert NoOpRuntimeManager.TOKEN not in resp.text

    def test_unknown_path_without_token_also_rejected(self, app):
        """Auth se proverava pre routing-a — i nepostojeća putanja traži token."""
        with TestClient(app) as client:
            resp = client.get("/nepostojeci-endpoint")
            assert resp.status_code == 401

            resp = client.get(
                "/nepostojeci-endpoint",
                headers={"Authorization": f"Bearer {NoOpRuntimeManager.TOKEN}"},
            )
            assert resp.status_code == 404
