"""Jedinični testovi za ConflictDetectionService.

Koristi FileActivity i ActiveSession objekte, ne dict-ove.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import flowos.service.services.infrastructure.persistence.models  # noqa: F401
import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
from flowos.service.services.attribution.service import ActiveSession
from flowos.service.services.conflicts.service import ConflictDetectionService
from flowos.service.services.infrastructure.persistence.activity_models import FileActivity
from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.models import AgentSession


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def service(db_session):
    return ConflictDetectionService(db_session)


def _now_ago(minutes: int) -> datetime:
    return datetime.now(tz=UTC) - timedelta(minutes=minutes)


def _activity(
    file_path: str,
    session_id: str,
    occurred_at: datetime | None = None,
    tree_identity: str | None = None,
    event_id: str | None = None,
    normalized_path: str | None = None,
) -> FileActivity:
    """Kreira FileActivity za testiranje."""
    a = FileActivity(
        event_id=event_id or f"evt-{file_path}-{session_id}",
        project_id="p1",
        session_id=session_id,
        event_type="MODIFIED",
        file_path=file_path,
        normalized_path=normalized_path or file_path,
        tree_identity=tree_identity or "",
        repository_path="C:/repo",
        occurred_at=occurred_at or _now_ago(5),
        source="WATCHER",
    )
    return a


def _session(sid: str, worktree_path: str | None = None) -> dict[str, Any]:
    """Kreira podatke sesije kao dict (za ActiveSession)."""
    return {"id": sid, "worktree_path": worktree_path, "repo_path": "C:/repo"}


def _active(sid: str, worktree_path: str | None = None) -> ActiveSession:
    return ActiveSession(session_id=sid, worktree_path=worktree_path, repo_path="C:/repo")


def _agent_session(
    sid: str,
    status: str = "ACTIVE",
    last_activity_at: datetime | None = None,
    pid: int | None = None,
) -> AgentSession:
    s = AgentSession(
        id=sid,
        project_id="p1",
        agent_type="test",
        repo_path="C:/repo",
        status=status,
        pid=pid,
    )
    if last_activity_at:
        s.last_activity_at = last_activity_at
    return s


# ═══════════════════════════════════════════════════════════════
# Pravilo 1: WRITE_WRITE
# ═══════════════════════════════════════════════════════════════


class TestWriteWrite:
    def test_two_sessions_same_file_detected(self, service, db_session):
        activities = [
            _activity("src/app.py", "s1", _now_ago(2)),
            _activity("src/app.py", "s2", _now_ago(3)),
        ]
        sessions = [_active("s1"), _active("s2")]
        conflicts = service.detect_write_write("p1", activities, sessions)
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "WRITE_WRITE"

    def test_one_session_no_conflict(self, service, db_session):
        activities = [_activity("src/app.py", "s1", _now_ago(2))]
        sessions = [_active("s1")]
        conflicts = service.detect_write_write("p1", activities, sessions)
        assert len(conflicts) == 0

    def test_outside_window_ignored(self, service, db_session):
        activities = [
            _activity("src/app.py", "s1", _now_ago(15)),
            _activity("src/app.py", "s2", _now_ago(14)),
        ]
        sessions = [_active("s1"), _active("s2")]
        conflicts = service.detect_write_write("p1", activities, sessions)
        assert len(conflicts) == 0

    def test_different_files_no_conflict(self, service, db_session):
        activities = [
            _activity("src/a.py", "s1", _now_ago(2)),
            _activity("src/b.py", "s2", _now_ago(3)),
        ]
        sessions = [_active("s1"), _active("s2")]
        conflicts = service.detect_write_write("p1", activities, sessions)
        assert len(conflicts) == 0

    def test_duplicate_not_created(self, service, db_session):
        activities = [
            _activity("src/app.py", "s1", _now_ago(2)),
            _activity("src/app.py", "s2", _now_ago(3)),
        ]
        sessions = [_active("s1"), _active("s2")]
        c1 = service.detect_write_write("p1", activities, sessions)
        assert len(c1) == 1
        c2 = service.detect_write_write("p1", activities, sessions)
        assert len(c2) == 0

    def test_same_worktree_detected(self, service, db_session):
        activities = [
            _activity("src/app.py", "s1", _now_ago(2)),
            _activity("src/app.py", "s2", _now_ago(3)),
        ]
        sessions = [_active("s1", "C:/worktrees/w1"), _active("s2", "C:/worktrees/w1")]
        conflicts = service.detect_write_write("p1", activities, sessions)
        assert len(conflicts) == 1

    def test_different_worktree_no_conflict(self, service, db_session):
        activities = [
            _activity("src/app.py", "s1", _now_ago(2)),
            _activity("src/app.py", "s2", _now_ago(3)),
        ]
        sessions = [_active("s1", "C:/worktrees/w1"), _active("s2", "C:/worktrees/w2")]
        conflicts = service.detect_write_write("p1", activities, sessions)
        assert len(conflicts) == 0

    def test_same_session_same_file_no_conflict(self, service, db_session):
        activities = [
            _activity("src/app.py", "s1", _now_ago(2)),
            _activity("src/app.py", "s1", _now_ago(1)),
        ]
        sessions = [_active("s1")]
        conflicts = service.detect_write_write("p1", activities, sessions)
        assert len(conflicts) == 0


# ═══════════════════════════════════════════════════════════════
# Pravilo 2: BRANCH_CHANGE
# ═══════════════════════════════════════════════════════════════


class TestBranchChange:
    def test_branch_change_detected(self, service, db_session):
        session = _agent_session("s1")
        db_session.add(session)
        db_session.flush()
        c = service.detect_branch_change("p1", session, "main", "feature/x")
        assert c is not None
        assert c.conflict_type == "BRANCH_CHANGE"

    def test_branch_change_no_duplicate(self, service, db_session):
        session = _agent_session("s1")
        db_session.add(session)
        db_session.flush()
        c1 = service.detect_branch_change("p1", session, "main", "feature/x")
        assert c1 is not None
        c2 = service.detect_branch_change("p1", session, "main", "feature/x")
        assert c2 is None


# ═══════════════════════════════════════════════════════════════
# Pravilo 3: STALE_SESSION
# ═══════════════════════════════════════════════════════════════


class TestStaleSession:
    def test_stale_session_detected(self, service, db_session):
        session = _agent_session("s1", last_activity_at=_now_ago(60))
        db_session.add(session)
        db_session.flush()
        c = service.detect_stale_session("p1", session)
        assert c is not None
        assert c.conflict_type == "STALE_SESSION"

    def test_active_session_no_conflict(self, service, db_session):
        session = _agent_session("s1", last_activity_at=_now_ago(5))
        db_session.add(session)
        db_session.flush()
        c = service.detect_stale_session("p1", session)
        assert c is None

    def test_no_last_activity_ignored(self, service, db_session):
        session = _agent_session("s1", last_activity_at=None)
        db_session.add(session)
        db_session.flush()
        c = service.detect_stale_session("p1", session)
        assert c is None


# ═══════════════════════════════════════════════════════════════
# Pravilo 4: NO_COMMIT
# ═══════════════════════════════════════════════════════════════


class TestNoCommit:
    def test_no_commit_detected(self, service, db_session):
        session = _agent_session("s1")
        db_session.add(session)
        db_session.flush()
        c = service.detect_no_commit("p1", session, ["src/a.py", "src/b.py"])
        assert c is not None
        assert c.conflict_type == "NO_COMMIT"

    def test_clean_session_no_conflict(self, service, db_session):
        session = _agent_session("s1")
        db_session.add(session)
        db_session.flush()
        c = service.detect_no_commit("p1", session, [])
        assert c is None

    def test_no_duplicate(self, service, db_session):
        session = _agent_session("s1")
        db_session.add(session)
        db_session.flush()
        c1 = service.detect_no_commit("p1", session, ["src/a.py"])
        assert c1 is not None
        c2 = service.detect_no_commit("p1", session, ["src/a.py"])
        assert c2 is None


# ═══════════════════════════════════════════════════════════════
# Acknowledge / Resolve / Open
# ═══════════════════════════════════════════════════════════════


class TestAcknowledgeResolve:
    def test_acknowledge_open_conflict(self, service, db_session):
        session = _agent_session("s1")
        db_session.add(session)
        db_session.flush()
        c = service.detect_no_commit("p1", session, ["f.py"])
        assert c is not None
        ack = service.acknowledge(c.id)
        assert ack is not None
        assert ack.status == "ACKNOWLEDGED"

    def test_acknowledge_non_open_returns_none(self, service, db_session):
        assert service.acknowledge("nonexistent") is None

    def test_resolve_conflict(self, service, db_session):
        session = _agent_session("s1")
        db_session.add(session)
        db_session.flush()
        c = service.detect_no_commit("p1", session, ["f.py"])
        res = service.resolve(c.id)
        assert res is not None
        assert res.status == "RESOLVED"

    def test_list_open(self, service, db_session):
        session = _agent_session("s1")
        db_session.add(session)
        db_session.flush()
        service.detect_no_commit("p1", session, ["f.py"])
        open_list = service.list_open("p1")
        assert len(open_list) == 1


# ═══════════════════════════════════════════════════════════════
# Konfigurabilni pragovi
# ═══════════════════════════════════════════════════════════════


class TestConfigurableThresholds:
    def test_custom_write_window(self, db_session):
        svc = ConflictDetectionService(db_session, write_window_minutes=5)
        activities = [
            _activity("src/app.py", "s1", _now_ago(7)),
            _activity("src/app.py", "s2", _now_ago(6)),
        ]
        sessions = [_active("s1"), _active("s2")]
        conflicts = svc.detect_write_write("p1", activities, sessions)
        assert len(conflicts) == 0

    def test_custom_stale_window(self, db_session):
        svc = ConflictDetectionService(db_session, stale_minutes=15)
        session = _agent_session("s1", last_activity_at=_now_ago(20))
        db_session.add(session)
        db_session.flush()
        c = svc.detect_stale_session("p1", session)
        assert c is not None
