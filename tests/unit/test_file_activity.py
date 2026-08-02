"""Testovi za FileActivity ORM model — Korak 1 korektivnog naloga.

Proverava:
- kreiranje aktivnosti
- dupli idempotency key
- filtriranje po projektu, sesiji, vremenu
- putanja sa razmacima, Windows putanje
- nullable session attribution
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401 — potrebno za FK
from flowos.service.services.infrastructure.persistence.activity_models import FileActivity
from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.models import AgentSession, Project


@pytest.fixture
def db_session():
    """In-memory SQLite baza za testove FileActivity modela."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def project(db_session: Session) -> Project:
    p = Project(
        id="proj-001",
        name="Test Project",
        repo_path="C:\\Users\\test\\repo",
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def session_entity(db_session: Session, project: Project) -> AgentSession:
    s = AgentSession(
        id="sess-001",
        project_id=project.id,
        agent_type="claude-code",
        repo_path=project.repo_path,
        worktree_path="C:\\Users\\test\\wt1",
    )
    db_session.add(s)
    db_session.flush()
    return s


class TestFileActivityCreation:
    """Kreiranje aktivnosti — osnovni slučajevi."""

    def test_create_minimal(self, db_session: Session, project: Project):
        fa = FileActivity(
            event_id="evt-001",
            project_id=project.id,
            event_type="MODIFIED",
            file_path="src/main.py",
            normalized_path="src/main.py",
            tree_identity="C:\\Users\\test\\repo",
            repository_path="C:\\Users\\test\\repo",
            occurred_at=datetime.now(tz=UTC),
        )
        db_session.add(fa)
        db_session.flush()

        assert fa.id is not None
        assert fa.event_id == "evt-001"
        assert fa.attribution_type == "UNATTRIBUTED"

    def test_create_with_session(
        self, db_session: Session, project: Project, session_entity: AgentSession
    ):
        fa = FileActivity(
            event_id="evt-002",
            project_id=project.id,
            session_id=session_entity.id,
            event_type="CREATED",
            file_path="src/new.py",
            normalized_path="src/new.py",
            tree_identity="C:\\Users\\test\\wt1",
            repository_path=project.repo_path,
            worktree_path=session_entity.worktree_path,
            occurred_at=datetime.now(tz=UTC),
            attribution_type="WORKTREE_EXACT",
            attribution_confidence=1.0,
        )
        db_session.add(fa)
        db_session.flush()

        assert fa.session_id == "sess-001"
        assert fa.attribution_type == "WORKTREE_EXACT"
        assert fa.attribution_confidence == 1.0


class TestIdempotency:
    """Kontrola duplih unosa."""

    def test_duplicate_event_id_raises(self, db_session: Session, project: Project):
        fa1 = FileActivity(
            event_id="evt-dup",
            project_id=project.id,
            event_type="MODIFIED",
            file_path="f.py",
            normalized_path="f.py",
            tree_identity="C:\\Users\\test\\repo",
            repository_path="C:\\Users\\test\\repo",
            occurred_at=datetime.now(tz=UTC),
        )
        db_session.add(fa1)
        db_session.flush()

        fa2 = FileActivity(
            event_id="evt-dup",  # isti event_id
            project_id=project.id,
            event_type="MODIFIED",
            file_path="f2.py",
            normalized_path="f2.py",
            tree_identity="C:\\Users\\test\\repo",
            repository_path="C:\\Users\\test\\repo",
            occurred_at=datetime.now(tz=UTC),
        )
        db_session.add(fa2)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_duplicate_idempotency_key_raises(self, db_session: Session, project: Project):
        fa1 = FileActivity(
            event_id="evt-a",
            idempotency_key="key-dup",
            project_id=project.id,
            event_type="MODIFIED",
            file_path="f.py",
            normalized_path="f.py",
            tree_identity="C:\\Users\\test\\repo",
            repository_path="C:\\Users\\test\\repo",
            occurred_at=datetime.now(tz=UTC),
        )
        db_session.add(fa1)
        db_session.flush()

        fa2 = FileActivity(
            event_id="evt-b",
            idempotency_key="key-dup",  # isti idempotency_key
            project_id=project.id,
            event_type="DELETED",
            file_path="g.py",
            normalized_path="g.py",
            tree_identity="C:\\Users\\test\\repo",
            repository_path="C:\\Users\\test\\repo",
            occurred_at=datetime.now(tz=UTC),
        )
        db_session.add(fa2)
        with pytest.raises(IntegrityError):
            db_session.flush()


class TestQueries:
    """Filtriranje i sortiranje."""

    def _make_activity(
        self,
        db_session: Session,
        event_id: str,
        project_id: str,
        session_id: str | None,
        file_path: str,
        occurred_at: datetime,
    ) -> FileActivity:
        fa = FileActivity(
            event_id=event_id,
            project_id=project_id,
            session_id=session_id,
            event_type="MODIFIED",
            file_path=file_path,
            normalized_path=file_path,
            tree_identity="C:\\Users\\test\\repo",
            repository_path="C:\\Users\\test\\repo",
            occurred_at=occurred_at,
        )
        db_session.add(fa)
        return fa

    def test_filter_by_project(self, db_session: Session, project: Project):
        self._make_activity(db_session, "e1", project.id, None, "a.py", datetime.now(tz=UTC))
        self._make_activity(db_session, "e2", project.id, None, "b.py", datetime.now(tz=UTC))
        db_session.flush()

        activities = (
            db_session.query(FileActivity).filter(FileActivity.project_id == project.id).all()
        )
        assert len(activities) == 2

    def test_filter_by_session(
        self, db_session: Session, project: Project, session_entity: AgentSession
    ):
        self._make_activity(
            db_session, "e3", project.id, session_entity.id, "a.py", datetime.now(tz=UTC)
        )
        self._make_activity(db_session, "e4", project.id, None, "b.py", datetime.now(tz=UTC))
        db_session.flush()

        activities = (
            db_session.query(FileActivity)
            .filter(FileActivity.session_id == session_entity.id)
            .all()
        )
        assert len(activities) == 1
        assert activities[0].event_id == "e3"

    def test_sort_by_occurred_at(self, db_session: Session, project: Project):
        t1 = datetime(2026, 8, 1, 10, 0, 0, tzinfo=UTC)
        t2 = datetime(2026, 8, 1, 10, 1, 0, tzinfo=UTC)
        self._make_activity(db_session, "e5", project.id, None, "first.py", t1)
        self._make_activity(db_session, "e6", project.id, None, "second.py", t2)
        db_session.flush()

        activities = db_session.query(FileActivity).order_by(FileActivity.occurred_at).all()
        assert activities[0].event_id == "e5"
        assert activities[1].event_id == "e6"


class TestEdgeCases:
    """Granični slučajevi."""

    def test_path_with_spaces(self, db_session: Session, project: Project):
        fa = FileActivity(
            event_id="evt-space",
            project_id=project.id,
            event_type="MODIFIED",
            file_path="src/my folder/file name.py",
            normalized_path="src/my folder/file name.py",
            tree_identity="C:\\Users\\test\\repo",
            repository_path="C:\\Users\\test\\repo",
            occurred_at=datetime.now(tz=UTC),
        )
        db_session.add(fa)
        db_session.flush()

        found = db_session.get(FileActivity, fa.id)
        assert found is not None
        assert found.file_path == "src/my folder/file name.py"

    def test_windows_path(self, db_session: Session, project: Project):
        fa = FileActivity(
            event_id="evt-win",
            project_id=project.id,
            event_type="CREATED",
            file_path="C:\\Users\\Marija\\Documents\\projekat\\fajl.py",
            normalized_path="c:\\users\\marija\\documents\\projekat\\fajl.py",
            tree_identity="C:\\Users\\test\\repo",
            repository_path="C:\\Users\\test\\repo",
            occurred_at=datetime.now(tz=UTC),
        )
        db_session.add(fa)
        db_session.flush()

        found = db_session.get(FileActivity, fa.id)
        assert found is not None
        assert "Marija" in found.file_path

    def test_nullable_session(self, db_session: Session, project: Project):
        fa = FileActivity(
            event_id="evt-null-sess",
            project_id=project.id,
            session_id=None,
            event_type="MODIFIED",
            file_path="orphan.py",
            normalized_path="orphan.py",
            tree_identity="C:\\Users\\test\\repo",
            repository_path="C:\\Users\\test\\repo",
            occurred_at=datetime.now(tz=UTC),
            attribution_type="UNATTRIBUTED",
            attribution_confidence=0.0,
        )
        db_session.add(fa)
        db_session.flush()

        assert fa.session_id is None
        assert fa.attribution_type == "UNATTRIBUTED"

    def test_all_fields_populated(
        self, db_session: Session, project: Project, session_entity: AgentSession
    ):
        """Testira sva polja sa punim vrednostima."""
        occurred = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
        fa = FileActivity(
            event_id="evt-full",
            idempotency_key="idem-full-001",
            project_id=project.id,
            session_id=session_entity.id,
            plan_item_id="plan-item-1",
            agent_id="claude-code",
            event_type="MODIFIED",
            file_path="C:\\repo\\src\\main.py",
            normalized_path="c:\\repo\\src\\main.py",
            tree_identity="c:\\repo",
            repository_path="C:\\repo",
            worktree_path="C:\\repo\\wt1",
            attribution_type="WORKTREE_EXACT",
            attribution_confidence=0.95,
            occurred_at=occurred,
            source="WATCHER",
            metadata_json='{"size": 1024}',
        )
        db_session.add(fa)
        db_session.flush()

        found = db_session.get(FileActivity, fa.id)
        assert found is not None
        assert found.event_id == "evt-full"
        assert found.idempotency_key == "idem-full-001"
        assert found.project_id == project.id
        assert found.session_id == session_entity.id
        assert found.plan_item_id == "plan-item-1"
        assert found.agent_id == "claude-code"
        assert found.event_type == "MODIFIED"
        assert found.normalized_path == "c:\\repo\\src\\main.py"
        assert found.tree_identity == "c:\\repo"
        assert found.worktree_path == "C:\\repo\\wt1"
        assert found.attribution_type == "WORKTREE_EXACT"
        assert found.attribution_confidence == 0.95
        assert found.occurred_at == occurred
        assert found.source == "WATCHER"
        assert found.metadata_json == '{"size": 1024}'
        assert found.recorded_at is not None
