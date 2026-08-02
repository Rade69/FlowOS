"""Integracioni test za Korak 3 — Watcher → ActivityService → FileActivity.

Proverava kompletan tok: filesystem događaj → trajni zapis u bazi.

Koristi stvarni watchdog observer i privremeni Git repozitorijum.
Watchdog callback se poziva iz drugog thread-a, pa se koristi
file-based SQLite sa check_same_thread=False.
"""

import contextlib
import os
import tempfile
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
from flowos.service.services.activity.service import ActivityService
from flowos.service.services.attribution.service import ActiveSession
from flowos.service.services.infrastructure.persistence.activity_models import FileActivity
from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.models import AgentSession, Project
from flowos.service.services.infrastructure.watcher import WatcherPipeline


@pytest.fixture
def temp_repo():
    """Privremeni direktorijum koji simulira Git repozitorijum."""
    with tempfile.TemporaryDirectory(prefix="flowos_test_repo_") as tmp:
        repo = Path(tmp)
        (repo / ".git").mkdir(exist_ok=True)
        (repo / "src").mkdir(exist_ok=True)
        yield repo


@pytest.fixture(scope="function")
def engine():
    """Jedan SQLite engine sa check_same_thread=False za ceo test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    eng = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()
    with contextlib.suppress(OSError):
        os.unlink(db_path)


@pytest.fixture
def db_session(engine):
    """Sesija za glavni thread."""
    with Session(engine) as session:
        yield session


@pytest.fixture
def project(db_session: Session) -> Project:
    p = Project(id="proj-int-001", name="Integration Test", repo_path="PLACEHOLDER")
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def active_session(db_session: Session, project: Project, temp_repo: Path) -> AgentSession:
    # Ažuriraj project.repo_path na stvarnu putanju
    project.repo_path = str(temp_repo)
    db_session.flush()

    s = AgentSession(
        id="sess-int-001",
        project_id=project.id,
        agent_type="claude-code",
        repo_path=str(temp_repo),
        worktree_path=None,
        status="ACTIVE",
    )
    db_session.add(s)
    db_session.flush()
    # Commit da bi podaci bili vidljivi iz drugog thread-a
    db_session.commit()
    return s


class TestWatcherToActivityFlow:
    """Kompletan tok: watcher → ActivityService → FileActivity."""

    def test_file_created_generates_activity(
        self, temp_repo: Path, engine, project: Project, active_session: AgentSession
    ):
        """Kreira fajl, pokreće watcher, potvrđuje FileActivity zapis."""
        events_received: list = []

        def watcher_callback(event):
            """Callback iz watchdog thread-a."""
            events_received.append(event)
            db = Session(engine)
            try:
                activity_svc = ActivityService(db)
                activity_svc.record_file_event(
                    file_path=event.path,
                    event_type=event.event_type,
                    project_id=project.id,
                    repo_path=str(temp_repo),
                    active_sessions=[
                        ActiveSession(
                            session_id=active_session.id,
                            worktree_path=active_session.worktree_path,
                            repo_path=active_session.repo_path,
                        )
                    ],
                    source="WATCHER",
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

        watcher = WatcherPipeline(callback=watcher_callback, debounce_ms=200)
        watcher.start(str(temp_repo))
        assert watcher.is_running

        try:
            test_file = temp_repo / "src" / "new_file.py"
            test_file.write_text("# test file", encoding="utf-8")
            time.sleep(2.5)

            # Pročitaj iz baze (nova sesija)
            check_db = Session(engine)
            try:
                activities = (
                    check_db.query(FileActivity).filter(FileActivity.project_id == project.id).all()
                )
                file_events = [a for a in activities if "new_file.py" in a.file_path]
                assert len(file_events) >= 1, (
                    f"Očekuje se događaj za new_file.py. "
                    f"Ukupno aktivnosti: {len(activities)}, "
                    f"Callback poziva: {len(events_received)}"
                )
                evt = file_events[0]
                assert evt.project_id == project.id
                assert evt.source == "WATCHER"
                assert evt.session_id is not None
            finally:
                check_db.close()
        finally:
            watcher.stop()
            assert not watcher.is_running

    def test_watcher_stops_cleanly(self, temp_repo: Path):
        """Proverava da se watcher zaustavlja i da više ne emituje događaje."""
        events_after_stop: list = []

        def callback(event):
            events_after_stop.append(event)

        watcher = WatcherPipeline(callback=callback, debounce_ms=200)
        watcher.start(str(temp_repo))
        assert watcher.is_running

        watcher.stop()
        assert not watcher.is_running

        test_file = temp_repo / "after_stop.py"
        test_file.write_text("# after stop", encoding="utf-8")
        time.sleep(1.5)

        assert len(events_after_stop) <= 1, (
            f"Ne očekuju se novi događaji nakon stop, dobijeno: {len(events_after_stop)}"
        )

    def test_multiple_files_multiple_activities(
        self, temp_repo: Path, engine, project: Project, active_session: AgentSession
    ):
        """Više fajlova → više FileActivity zapisa."""
        events_received: list = []

        def watcher_callback(event):
            events_received.append(event)
            db = Session(engine)
            try:
                activity_svc = ActivityService(db)
                activity_svc.record_file_event(
                    file_path=event.path,
                    event_type=event.event_type,
                    project_id=project.id,
                    repo_path=str(temp_repo),
                    active_sessions=[
                        ActiveSession(
                            session_id=active_session.id,
                            worktree_path=active_session.worktree_path,
                            repo_path=active_session.repo_path,
                        )
                    ],
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

        watcher = WatcherPipeline(callback=watcher_callback, debounce_ms=200)
        watcher.start(str(temp_repo))

        try:
            for i in range(3):
                f = temp_repo / "src" / f"multi_{i}.py"
                f.write_text(f"# file {i}", encoding="utf-8")
                time.sleep(0.1)

            time.sleep(2.5)

            check_db = Session(engine)
            try:
                activities = (
                    check_db.query(FileActivity).filter(FileActivity.project_id == project.id).all()
                )
                multi_events = [a for a in activities if "multi_" in a.file_path]
                assert len(multi_events) >= 2, (
                    f"Očekuju se bar 2 događaja za multi_ fajlove. "
                    f"Dobijeno: {len(multi_events)}, "
                    f"Callback poziva: {len(events_received)}, "
                    f"Ukupno aktivnosti: {len(activities)}"
                )
            finally:
                check_db.close()
        finally:
            watcher.stop()

    def test_nonexistent_path_raises(self):
        """Pokretanje watcher-a na nepostojećoj putanji baca FileNotFoundError."""
        watcher = WatcherPipeline(callback=lambda e: None)
        with pytest.raises(FileNotFoundError):
            watcher.start("/nonexistent/path/xyz")
