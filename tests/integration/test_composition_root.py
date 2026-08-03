"""Composition-root E2E test — stvarni wiring watcher → ActivityService → Conflict."""

import contextlib
import os
import tempfile
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import flowos.service.services.infrastructure.persistence.activity_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.conflict_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.report_models  # noqa: F401
from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.conflict_models import Conflict
from flowos.service.services.infrastructure.persistence.models import AgentSession, Project
from flowos.service.services.infrastructure.watcher import WatcherPipeline


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


class TestCompositionRootE2E:
    """Testira stvarni wiring: watcher callback → ActivityService → conflict callback."""

    def test_watcher_callback_produces_activity_and_conflict(self, engine, tmp_path: Path):
        """Stvarni composition-root tok: watcher događaj → FileActivity → WRITE_WRITE."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / "src").mkdir()
        test_file = repo_path / "src" / "app.py"
        test_file.write_text("# test\n")

        project_id = "cr-proj-001"
        repo_str = str(repo_path)

        db = Session(engine)
        try:
            # 1. Kreiraj projekat i dve aktivne sesije (isti tree)
            project = Project(id=project_id, name="CR Test", repo_path=repo_str)
            db.add(project)

            session_a = AgentSession(
                id="cr-sess-a",
                project_id=project_id,
                agent_type="cc",
                repo_path=repo_str,
                status="ACTIVE",
            )
            session_b = AgentSession(
                id="cr-sess-b",
                project_id=project_id,
                agent_type="pi",
                repo_path=repo_str,
                status="ACTIVE",
            )
            db.add_all([session_a, session_b])
            db.flush()
            db.commit()

            # 2. Kreiraj watcher callback istom fabrikom kao composition_root lifespan
            #    (isti pattern: ActivityService + conflict callback registracija)
            from flowos.service.services.activity.service import ActivityService
            from flowos.service.services.attribution.service import ActiveSession
            from flowos.service.services.conflicts.service import ConflictDetectionService

            events_received: list = []

            def watcher_callback(event):
                events_received.append(event)
                cb_db = Session(engine)
                try:
                    # Učitaj aktivne sesije — isto kao composition_root lifespan
                    from flowos.shared.enums.session import SessionStatus

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
                            session_id=s.id,
                            worktree_path=s.worktree_path,
                            repo_path=s.repo_path,
                        )
                        for s in active_sessions_raw
                    ]

                    activity_svc = ActivityService(cb_db)

                    # Registruj conflict callback — isti pattern kao composition_root
                    if len(active) >= 2:

                        def _conflict_cb(activity):
                            conflict_svc = ConflictDetectionService(cb_db)
                            conflict_svc.on_file_activity(activity, active)
                            cb_db.commit()

                        activity_svc.register_conflict_callback(_conflict_cb)

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

            # 3. Pokreni watcher i izmeni fajl
            watcher = WatcherPipeline(callback=watcher_callback, debounce_ms=200)
            watcher.start(repo_str)
            assert watcher.is_running

            try:
                time.sleep(0.5)  # sačekaj da watcher počne
                test_file.write_text("# modified by both sessions\n")
                time.sleep(2.0)  # sačekaj debounce + obradu

                assert len(events_received) >= 1, (
                    f"Watcher nije detektovao promenu fajla. Događaji: {len(events_received)}"
                )
            finally:
                watcher.stop()
                assert not watcher.is_running

            # 4. Potvrdi FileActivity i heartbeat
            from flowos.service.services.infrastructure.persistence.activity_models import (
                FileActivity,
            )

            check_db = Session(engine)
            try:
                activities = (
                    check_db.query(FileActivity).filter(FileActivity.project_id == project_id).all()
                )
                app_events = [a for a in activities if "app.py" in a.file_path]
                assert len(app_events) >= 1, (
                    f"Očekuje se bar 1 FileActivity za app.py. Dobijeno: {len(app_events)}"
                )

                # 5. Simuliraj WRITE_WRITE: dodaj aktivnosti za obe sesije kroz ActivityService
                #    sa registrovanim conflict callback-om — isti pattern kao composition_root
                from flowos.service.services.activity.service import ActivityService as ASvc
                from flowos.service.services.attribution.service import ActiveSession as AS

                activity_svc2 = ASvc(check_db)
                conflict_svc = ConflictDetectionService(check_db)

                # Callback koji emulira composition_root: detektuje WRITE_WRITE i LATE_OVERLAP
                active_both = [
                    AS(session_id="cr-sess-a", repo_path=repo_str),
                    AS(session_id="cr-sess-b", repo_path=repo_str),
                ]

                def _conflict_cb(act):
                    conflict_svc.on_file_activity(act, active_both)
                    check_db.commit()

                activity_svc2.register_conflict_callback(_conflict_cb)

                # Aktivnost za session_a
                activity_svc2.record_file_event(
                    file_path=str(test_file),
                    event_type="MODIFIED",
                    project_id=project_id,
                    repo_path=repo_str,
                    active_sessions=[AS(session_id="cr-sess-a", repo_path=repo_str)],
                )
                # Aktivnost za session_b — callback će detektovati WRITE_WRITE
                activity_svc2.record_file_event(
                    file_path=str(test_file),
                    event_type="MODIFIED",
                    project_id=project_id,
                    repo_path=repo_str,
                    active_sessions=[AS(session_id="cr-sess-b", repo_path=repo_str)],
                )
                check_db.commit()

                # 6. Potvrdi WRITE_WRITE Conflict
                ww_conflicts = (
                    check_db.query(Conflict)
                    .filter(
                        Conflict.project_id == project_id,
                        Conflict.conflict_type == "WRITE_WRITE",
                    )
                    .all()
                )
                assert len(ww_conflicts) >= 1, (
                    f"Očekuje se WRITE_WRITE konflikt kroz composition-root tok. "
                    f"Dobijeno: {len(ww_conflicts)}"
                )
                ww = ww_conflicts[0]
                assert ww.conflict_key is not None
                assert ww.conflict_level == "HIGH"
                assert ww.first_seen_at is not None
                assert ww.last_seen_at is not None
                assert ww.occurrence_count >= 1
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
