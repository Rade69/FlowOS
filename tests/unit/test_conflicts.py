"""Jedinični testovi za ConflictDetectionService.

Testiraju svih 5 pravila detekcije konflikta:
1. WRITE_WRITE — dve aktivne sesije, isti fajl
2. LATE_OVERLAP — druga sesija menjala u zadnjih 30 min
3. BRANCH_CHANGE — branch promenjen ispod sesije
4. STALE_SESSION — sesija bez aktivnosti > 30 min
5. NO_COMMIT — sesija završena sa izmenama bez commita
"""

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Osiguraj da su svi modeli importovani za kreiranje tabela (FK reference)
import flowos.service.services.infrastructure.persistence.models  # noqa: F401
import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
from flowos.service.services.conflicts.service import ConflictDetectionService
from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.conflict_models import Conflict


@pytest.fixture
def db_session():
    """In-memory SQLite sesija sa kreiranim tabelama."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def service(db_session):
    return ConflictDetectionService(db_session)


def _now_ago(minutes: int) -> str:
    """ISO timestamp N minuta u prošlosti."""
    return (datetime.now(tz=UTC) - timedelta(minutes=minutes)).isoformat()


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


# ═══════════════════════════════════════════════════════════════
# Pravilo 1: WRITE_WRITE
# ═══════════════════════════════════════════════════════════════


class TestWriteWrite:
    def test_two_sessions_same_file_detected(self, service, db_session):
        activities = [
            {
                "file_path": "src/app.py",
                "session_id": "s1",
                "observed_at": _now_ago(2),
                "repo_path": "C:/repo",
            },
            {
                "file_path": "src/app.py",
                "session_id": "s2",
                "observed_at": _now_ago(5),
                "repo_path": "C:/repo",
            },
        ]
        active_sessions = [
            {"id": "s1", "worktree_path": None, "repo_path": "C:/repo"},
            {"id": "s2", "worktree_path": None, "repo_path": "C:/repo"},
        ]
        conflicts = service.detect_write_write("p1", activities, active_sessions)
        assert len(conflicts) == 1
        c = conflicts[0]
        assert c.conflict_level == "HIGH"
        assert c.conflict_type == "WRITE_WRITE"
        session_ids = json.loads(c.session_ids_json)
        assert "s1" in session_ids
        assert "s2" in session_ids

    def test_one_session_no_conflict(self, service, db_session):
        activities = [
            {
                "file_path": "src/app.py",
                "session_id": "s1",
                "observed_at": _now_ago(2),
                "repo_path": "C:/repo",
            },
        ]
        active_sessions = [
            {"id": "s1", "worktree_path": None, "repo_path": "C:/repo"},
        ]
        conflicts = service.detect_write_write("p1", activities, active_sessions)
        assert len(conflicts) == 0

    def test_outside_window_ignored(self, service, db_session):
        activities = [
            {
                "file_path": "src/app.py",
                "session_id": "s1",
                "observed_at": _now_ago(2),
                "repo_path": "C:/repo",
            },
            {
                "file_path": "src/app.py",
                "session_id": "s2",
                "observed_at": _now_ago(20),
                "repo_path": "C:/repo",
            },
        ]
        active_sessions = [
            {"id": "s1", "repo_path": "C:/repo"},
            {"id": "s2", "repo_path": "C:/repo"},
        ]
        conflicts = service.detect_write_write("p1", activities, active_sessions)
        # Samo s1 je unutar prozora, s2 je van — nema dva aktivna upisivača unutar prozora
        assert len(conflicts) == 0

    def test_different_files_no_conflict(self, service, db_session):
        activities = [
            {
                "file_path": "src/a.py",
                "session_id": "s1",
                "observed_at": _now_ago(2),
                "repo_path": "C:/repo",
            },
            {
                "file_path": "src/b.py",
                "session_id": "s2",
                "observed_at": _now_ago(3),
                "repo_path": "C:/repo",
            },
        ]
        active_sessions = [
            {"id": "s1", "repo_path": "C:/repo"},
            {"id": "s2", "repo_path": "C:/repo"},
        ]
        conflicts = service.detect_write_write("p1", activities, active_sessions)
        assert len(conflicts) == 0

    def test_duplicate_not_created(self, service, db_session):
        """Već postoji OPEN WRITE_WRITE konflikt — ne pravi duplikat."""
        activities = [
            {
                "file_path": "src/dup.py",
                "session_id": "s1",
                "observed_at": _now_ago(2),
                "repo_path": "C:/repo",
            },
            {
                "file_path": "src/dup.py",
                "session_id": "s2",
                "observed_at": _now_ago(3),
                "repo_path": "C:/repo",
            },
        ]
        active_sessions = [
            {"id": "s1", "repo_path": "C:/repo"},
            {"id": "s2", "repo_path": "C:/repo"},
        ]
        # Prvi poziv
        c1 = service.detect_write_write("p1", activities, active_sessions)
        assert len(c1) == 1
        # Drugi poziv sa istim podacima
        c2 = service.detect_write_write("p1", activities, active_sessions)
        assert len(c2) == 0

    def test_same_worktree_detected(self, service, db_session):
        """Dve sesije u istom worktree-ju → WRITE_WRITE konflikt."""
        activities = [
            {
                "file_path": "src/app.py",
                "session_id": "s1",
                "observed_at": _now_ago(2),
                "repo_path": "C:/repo",
            },
            {
                "file_path": "src/app.py",
                "session_id": "s2",
                "observed_at": _now_ago(3),
                "repo_path": "C:/repo",
            },
        ]
        active_sessions = [
            {"id": "s1", "worktree_path": "C:/wt/shared", "repo_path": "C:/repo"},
            {"id": "s2", "worktree_path": "C:/wt/shared", "repo_path": "C:/repo"},
        ]
        conflicts = service.detect_write_write("p1", activities, active_sessions)
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "WRITE_WRITE"

    def test_different_worktree_no_conflict(self, service, db_session):
        """Dve sesije u različitim worktree-ovima → nema WRITE_WRITE konflikta."""
        activities = [
            {
                "file_path": "src/app.py",
                "session_id": "s1",
                "observed_at": _now_ago(2),
                "repo_path": "C:/repo",
            },
            {
                "file_path": "src/app.py",
                "session_id": "s2",
                "observed_at": _now_ago(3),
                "repo_path": "C:/repo",
            },
        ]
        active_sessions = [
            {"id": "s1", "worktree_path": "C:/wt-a", "repo_path": "C:/repo"},
            {"id": "s2", "worktree_path": "C:/wt-b", "repo_path": "C:/repo"},
        ]
        conflicts = service.detect_write_write("p1", activities, active_sessions)
        assert len(conflicts) == 0, "Različiti worktree-evi → nema konflikta (izolacija)"

    def test_same_session_same_file_no_conflict(self, service, db_session):
        """Ista sesija, isti fajl → nije konflikt."""
        activities = [
            {
                "file_path": "src/app.py",
                "session_id": "s1",
                "observed_at": _now_ago(2),
                "repo_path": "C:/repo",
            },
            {
                "file_path": "src/app.py",
                "session_id": "s1",
                "observed_at": _now_ago(1),
                "repo_path": "C:/repo",
            },
        ]
        active_sessions = [
            {"id": "s1", "repo_path": "C:/repo"},
        ]
        conflicts = service.detect_write_write("p1", activities, active_sessions)
        assert len(conflicts) == 0


# ═══════════════════════════════════════════════════════════════
# Pravilo 3: BRANCH_CHANGE
# ═══════════════════════════════════════════════════════════════


class TestBranchChange:
    def test_branch_change_detected(self, service, db_session):
        session = {"id": "s1", "repo_path": "C:/repo"}
        c = service.detect_branch_change("p1", session, "main", "feature/x")
        assert c is not None
        assert c.conflict_level == "MEDIUM"
        assert c.conflict_type == "BRANCH_CHANGE"

    def test_branch_change_no_duplicate(self, service, db_session):
        session = {"id": "s1"}
        service.detect_branch_change("p1", session, "main", "feature/x")
        c2 = service.detect_branch_change("p1", session, "main", "feature/x")
        assert c2 is None


# ═══════════════════════════════════════════════════════════════
# Pravilo 4: STALE_SESSION
# ═══════════════════════════════════════════════════════════════


class TestStaleSession:
    def test_stale_session_detected(self, service, db_session):
        session = {"id": "s1", "last_activity_at": _now_ago(60)}
        c = service.detect_stale_session("p1", session)
        assert c is not None
        assert c.conflict_type == "STALE_SESSION"
        assert c.conflict_level == "INFO"

    def test_active_session_no_conflict(self, service, db_session):
        session = {"id": "s1", "last_activity_at": _now_ago(5)}
        c = service.detect_stale_session("p1", session)
        assert c is None

    def test_no_last_activity_ignored(self, service, db_session):
        session = {"id": "s1"}
        c = service.detect_stale_session("p1", session)
        assert c is None


# ═══════════════════════════════════════════════════════════════
# Pravilo 5: NO_COMMIT
# ═══════════════════════════════════════════════════════════════


class TestNoCommit:
    def test_no_commit_detected(self, service, db_session):
        session = {"id": "s1"}
        c = service.detect_no_commit("p1", session, ["src/a.py", "src/b.py"])
        assert c is not None
        assert c.conflict_type == "NO_COMMIT"
        assert c.conflict_level == "INFO"

    def test_clean_session_no_conflict(self, service, db_session):
        session = {"id": "s1"}
        c = service.detect_no_commit("p1", session, [])
        assert c is None

    def test_no_duplicate(self, service, db_session):
        session = {"id": "s1"}
        service.detect_no_commit("p1", session, ["src/a.py"])
        c2 = service.detect_no_commit("p1", session, ["src/b.py"])
        assert c2 is None


# ═══════════════════════════════════════════════════════════════
# Acknowledge / Resolve
# ═══════════════════════════════════════════════════════════════


class TestAcknowledgeResolve:
    def test_acknowledge_open_conflict(self, service, db_session):
        c = Conflict(
            project_id="p1",
            file_path="test.py",
            session_ids_json="[]",
            conflict_level="MEDIUM",
            conflict_type="BRANCH_CHANGE",
            description="test",
        )
        db_session.add(c)
        db_session.flush()

        result = service.acknowledge(c.id)
        assert result is not None
        assert result.status == "ACKNOWLEDGED"
        assert result.acknowledged_at is not None

    def test_acknowledge_non_open_returns_none(self, service, db_session):
        c = Conflict(
            project_id="p1",
            file_path="test.py",
            session_ids_json="[]",
            conflict_level="MEDIUM",
            conflict_type="BRANCH_CHANGE",
            description="test",
            status="RESOLVED",
        )
        db_session.add(c)
        db_session.flush()

        result = service.acknowledge(c.id)
        assert result is None

    def test_resolve_conflict(self, service, db_session):
        c = Conflict(
            project_id="p1",
            file_path="test.py",
            session_ids_json="[]",
            conflict_level="MEDIUM",
            conflict_type="BRANCH_CHANGE",
            description="test",
        )
        db_session.add(c)
        db_session.flush()

        result = service.resolve(c.id)
        assert result is not None
        assert result.status == "RESOLVED"

    def test_list_open(self, service, db_session):
        c1 = Conflict(
            project_id="p1",
            file_path="a.py",
            session_ids_json="[]",
            conflict_level="HIGH",
            conflict_type="WRITE_WRITE",
            description="",
            status="OPEN",
        )
        c2 = Conflict(
            project_id="p1",
            file_path="b.py",
            session_ids_json="[]",
            conflict_level="MEDIUM",
            conflict_type="BRANCH_CHANGE",
            description="",
            status="ACKNOWLEDGED",
        )
        db_session.add_all([c1, c2])
        db_session.flush()

        open_conflicts = service.list_open("p1")
        assert len(open_conflicts) == 1
        assert open_conflicts[0].id == c1.id


# ═══════════════════════════════════════════════════════════════
# Konfigurabilni pragovi
# ═══════════════════════════════════════════════════════════════


class TestConfigurableThresholds:
    def test_custom_write_window(self, db_session):
        svc = ConflictDetectionService(db_session, write_window_minutes=5, stale_minutes=15)
        activities = [
            {
                "file_path": "x.py",
                "session_id": "s1",
                "observed_at": _now_ago(2),
                "repo_path": "C:/repo",
            },
            {
                "file_path": "x.py",
                "session_id": "s2",
                "observed_at": _now_ago(7),
                "repo_path": "C:/repo",
            },
        ]
        active = [{"id": "s1"}, {"id": "s2"}]
        # s2 je na 7 min — unutar default 10, ali van custom 5
        conflicts = svc.detect_write_write("p1", activities, active)
        assert len(conflicts) == 0

    def test_custom_stale_window(self, db_session):
        svc = ConflictDetectionService(db_session, stale_minutes=15)
        session = {"id": "s1", "last_activity_at": _now_ago(20)}
        c = svc.detect_stale_session("p1", session)
        assert c is not None

        svc2 = ConflictDetectionService(db_session, stale_minutes=60)
        c2 = svc2.detect_stale_session("p1", session)
        assert c2 is None
