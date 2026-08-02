"""Testovi za ActivityService — Korak 2 korektivnog naloga.

Proverava:
- watcher event postaje ORM zapis
- attribution se upisuje
- više događaja istog fajla
- različite sesije
- događaj bez moguće atribucije
- duplikat se ne upisuje dva puta
- query metode (recent, session, file, project)
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
from flowos.service.services.activity.service import ActivityService
from flowos.service.services.attribution.service import ActiveSession
from flowos.service.services.infrastructure.persistence.activity_models import FileActivity
from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.models import AgentSession, Project


@pytest.fixture
def db_session():
    """In-memory SQLite baza za testove."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def project(db_session: Session) -> Project:
    p = Project(id="proj-act-001", name="Activity Test", repo_path="C:\\Users\\test\\repo")
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def session_a(db_session: Session, project: Project) -> AgentSession:
    s = AgentSession(
        id="sess-act-a",
        project_id=project.id,
        agent_type="claude-code",
        repo_path=project.repo_path,
        worktree_path="C:\\Users\\test\\wt-a",
        status="ACTIVE",
    )
    db_session.add(s)
    db_session.flush()
    return s


@pytest.fixture
def session_b(db_session: Session, project: Project) -> AgentSession:
    s = AgentSession(
        id="sess-act-b",
        project_id=project.id,
        agent_type="pi",
        repo_path=project.repo_path,
        worktree_path="C:\\Users\\test\\wt-b",
        status="ACTIVE",
    )
    db_session.add(s)
    db_session.flush()
    return s


@pytest.fixture
def service(db_session: Session) -> ActivityService:
    return ActivityService(db_session)


def _active(a_session: AgentSession) -> ActiveSession:
    return ActiveSession(
        session_id=a_session.id,
        worktree_path=a_session.worktree_path,
        repo_path=a_session.repo_path,
    )


class TestRecordFileEvent:
    """Osnovno beleženje događaja."""

    def test_watcher_event_becomes_orm_record(
        self, service: ActivityService, project: Project, session_a: AgentSession
    ):
        activity = service.record_file_event(
            file_path="C:\\Users\\test\\wt-a\\src\\main.py",
            event_type="MODIFIED",
            project_id=project.id,
            repo_path=project.repo_path,
            active_sessions=[_active(session_a)],
        )
        assert activity is not None
        assert activity.id is not None
        assert activity.event_type == "MODIFIED"
        assert "main.py" in activity.file_path

    def test_attribution_is_recorded(
        self, service: ActivityService, project: Project, session_a: AgentSession
    ):
        activity = service.record_file_event(
            file_path="C:\\Users\\test\\wt-a\\src\\app.py",
            event_type="CREATED",
            project_id=project.id,
            repo_path=project.repo_path,
            active_sessions=[_active(session_a)],
        )
        # Fajl u worktree-ju → WORKTREE_EXACT atribucija
        assert activity.attribution_type == "WORKTREE_EXACT"
        assert activity.attribution_confidence == 1.0
        assert activity.session_id == session_a.id

    def test_multiple_events_same_file(
        self, service: ActivityService, project: Project, session_a: AgentSession
    ):
        path = "C:\\Users\\test\\wt-a\\src\\shared.py"
        a1 = service.record_file_event(
            file_path=path,
            event_type="MODIFIED",
            project_id=project.id,
            repo_path=project.repo_path,
            active_sessions=[_active(session_a)],
        )
        a2 = service.record_file_event(
            file_path=path,
            event_type="MODIFIED",
            project_id=project.id,
            repo_path=project.repo_path,
            active_sessions=[_active(session_a)],
        )
        assert a1.event_id != a2.event_id
        assert a1.normalized_path == a2.normalized_path

    def test_different_sessions_different_records(
        self,
        service: ActivityService,
        project: Project,
        session_a: AgentSession,
        session_b: AgentSession,
    ):
        a1 = service.record_file_event(
            file_path="C:\\Users\\test\\wt-a\\f.py",
            event_type="MODIFIED",
            project_id=project.id,
            repo_path=project.repo_path,
            active_sessions=[_active(session_a)],
        )
        a2 = service.record_file_event(
            file_path="C:\\Users\\test\\wt-b\\f.py",
            event_type="MODIFIED",
            project_id=project.id,
            repo_path=project.repo_path,
            active_sessions=[_active(session_b)],
        )
        assert a1.session_id == session_a.id
        assert a2.session_id == session_b.id

    def test_unattributed_event(self, service: ActivityService, project: Project):
        activity = service.record_file_event(
            file_path="C:\\tmp\\orphan.py",
            event_type="MODIFIED",
            project_id=project.id,
            repo_path=project.repo_path,
            active_sessions=None,
        )
        assert activity.attribution_type == "UNATTRIBUTED"
        assert activity.session_id is None
        assert activity.attribution_confidence == 0.0

    def test_duplicate_event_id_not_written_twice(
        self, service: ActivityService, project: Project, db_session: Session
    ):
        # Prvi put
        service.record_file_event(
            file_path="C:\\Users\\test\\repo\\unique.py",
            event_type="MODIFIED",
            project_id=project.id,
            repo_path=project.repo_path,
        )
        db_session.flush()

        # Pokušaj duplikata sa istim event_id-jem — treba da pukne na unique constraint
        from sqlalchemy.exc import IntegrityError

        # Ručno kreiramo duplikat da testiramo constraint
        from flowos.service.services.activity.service import _generate_event_id

        now = datetime.now(tz=UTC)
        dup_event_id = _generate_event_id("unique.py", "MODIFIED", now)

        fa = FileActivity(
            event_id=dup_event_id,
            project_id=project.id,
            event_type="MODIFIED",
            file_path="C:\\Users\\test\\repo\\unique2.py",
            normalized_path="c:\\users\\test\\repo\\unique2.py",
            tree_identity="c:\\users\\test\\repo",
            repository_path="C:\\Users\\test\\repo",
            occurred_at=now,
        )
        db_session.add(fa)
        db_session.flush()

        # Drugi sa istim event_id
        fa2 = FileActivity(
            event_id=dup_event_id,
            project_id=project.id,
            event_type="MODIFIED",
            file_path="C:\\Users\\test\\repo\\unique3.py",
            normalized_path="c:\\users\\test\\repo\\unique3.py",
            tree_identity="c:\\users\\test\\repo",
            repository_path="C:\\Users\\test\\repo",
            occurred_at=now,
        )
        db_session.add(fa2)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_conflict_callback_invoked(
        self, service: ActivityService, project: Project, session_a: AgentSession
    ):
        called: list[FileActivity] = []
        service.register_conflict_callback(lambda fa: called.append(fa))

        service.record_file_event(
            file_path="C:\\Users\\test\\wt-a\\callback.py",
            event_type="MODIFIED",
            project_id=project.id,
            repo_path=project.repo_path,
            active_sessions=[_active(session_a)],
        )
        assert len(called) == 1
        assert called[0].event_type == "MODIFIED"


class TestQueryMethods:
    """Query metode ActivityService-a."""

    def _record(
        self,
        service: ActivityService,
        project: Project,
        session: AgentSession | None,
        path: str,
        event_type: str = "MODIFIED",
    ):
        sessions = [_active(session)] if session else None
        return service.record_file_event(
            file_path=path,
            event_type=event_type,
            project_id=project.id,
            repo_path=project.repo_path,
            active_sessions=sessions,
        )

    def test_get_recent_activities(
        self, service: ActivityService, project: Project, session_a: AgentSession
    ):
        self._record(service, project, session_a, "C:\\Users\\test\\wt-a\\r1.py")
        self._record(service, project, session_a, "C:\\Users\\test\\wt-a\\r2.py")

        recent = service.get_recent_activities(project.id, minutes=60)
        assert len(recent) >= 2

    def test_get_session_activities(
        self,
        service: ActivityService,
        project: Project,
        session_a: AgentSession,
        session_b: AgentSession,
    ):
        self._record(service, project, session_a, "C:\\Users\\test\\wt-a\\s1.py")
        self._record(service, project, session_b, "C:\\Users\\test\\wt-b\\s2.py")

        acts_a = service.get_session_activities(session_a.id)
        assert len(acts_a) >= 1
        assert all(a.session_id == session_a.id for a in acts_a)

    def test_get_file_activities(
        self, service: ActivityService, project: Project, session_a: AgentSession
    ):
        path = "C:\\Users\\test\\wt-a\\target.py"
        self._record(service, project, session_a, path)
        self._record(service, project, session_a, path)  # drugi događaj, isti fajl

        activities = service.get_file_activities(path)
        assert len(activities) >= 2
        assert all("target.py" in a.file_path for a in activities)

    def test_get_project_activities(
        self, service: ActivityService, project: Project, session_a: AgentSession
    ):
        for i in range(5):
            self._record(service, project, session_a, f"C:\\Users\\test\\wt-a\\p{i}.py")

        activities = service.get_project_activities(project.id, limit=200)
        assert len(activities) >= 5

    def test_get_project_activities_pagination(
        self, service: ActivityService, project: Project, session_a: AgentSession
    ):
        for i in range(10):
            self._record(service, project, session_a, f"C:\\Users\\test\\wt-a\\pg{i}.py")

        page1 = service.get_project_activities(project.id, limit=3, offset=0)
        page2 = service.get_project_activities(project.id, limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 3
        # Različiti događaji na različitim stranama
        ids_page1 = {a.id for a in page1}
        ids_page2 = {a.id for a in page2}
        assert ids_page1.isdisjoint(ids_page2)
