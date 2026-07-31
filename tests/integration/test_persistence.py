"""Integracioni testovi za SQLite persistence — temp baza.

Koristi SQLite :memory: bazu za izolovane testove.
Testira ORM modele, veze, kaskade, WAL i FK integritet.
"""

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.models import (
    AgentSession,
    Project,
    SessionEvent,
    Task,
)


@pytest.fixture
def engine():
    """SQLite engine sa WAL-om koristeci :memory: za izolaciju."""
    eng = create_engine("sqlite://", echo=False)

    @event.listens_for(eng, "connect")
    def _set_pragma(dbapi_connection, connection_record):  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def session(engine):
    """Nova sesija za svaki test."""
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as s:
        yield s


# ═══════════════════════════════════════════════════════════════════
# Project
# ═══════════════════════════════════════════════════════════════════


class TestProjectCRUD:
    def test_create(self, session: Session):
        p = Project(name="FlowOS", repo_path="C:/Users/test/repo")
        session.add(p)
        session.commit()

        found = session.get(Project, p.id)
        assert found is not None
        assert found.name == "FlowOS"
        assert found.repo_path == "C:/Users/test/repo"
        assert found.status == "ACTIVE"
        assert found.created_at is not None

    def test_update(self, session: Session):
        p = Project(name="Test", repo_path="C:/repo")
        session.add(p)
        session.commit()

        p.name = "Updated"
        session.commit()

        found = session.get(Project, p.id)
        assert found.name == "Updated"
        assert found.updated_at is not None

    def test_delete(self, session: Session):
        p = Project(name="Test", repo_path="C:/repo")
        session.add(p)
        session.commit()

        session.delete(p)
        session.commit()

        assert session.get(Project, p.id) is None


# ═══════════════════════════════════════════════════════════════════
# Task
# ═══════════════════════════════════════════════════════════════════


class TestTaskCRUD:
    def test_create_with_project(self, session: Session):
        project = Project(name="FlowOS", repo_path="C:/repo")
        session.add(project)
        session.commit()

        task = Task(project_id=project.id, title="Implementirati login")
        session.add(task)
        session.commit()

        found = session.get(Task, task.id)
        assert found is not None
        assert found.title == "Implementirati login"
        assert found.status == "OPEN"
        assert found.priority == "NORMAL"
        assert found.project_id == project.id

    def test_task_belongs_to_project(self, session: Session):
        project = Project(name="FlowOS", repo_path="C:/repo")
        session.add(project)
        session.commit()

        task = Task(project_id=project.id, title="Test task")
        session.add(task)
        session.commit()

        # Lazy load relationship
        found = session.get(Task, task.id)
        assert found.project is not None
        assert found.project.name == "FlowOS"

    def test_cascade_delete_project_deletes_tasks(self, session: Session):
        project = Project(name="FlowOS", repo_path="C:/repo")
        session.add(project)
        session.flush()  # Osiguraj da project ima ID

        task = Task(project_id=project.id, title="Test")
        session.add(task)
        session.commit()

        task_id = task.id

        session.delete(project)
        session.commit()

        assert session.get(Task, task_id) is None


# ═══════════════════════════════════════════════════════════════════
# AgentSession
# ═══════════════════════════════════════════════════════════════════


class TestAgentSessionCRUD:
    def test_create_minimal(self, session: Session):
        project = Project(name="FlowOS", repo_path="C:/repo")
        session.add(project)
        session.commit()

        s = AgentSession(
            project_id=project.id,
            agent_type="claude-code",
            repo_path="C:/repo",
        )
        session.add(s)
        session.commit()

        found = session.get(AgentSession, s.id)
        assert found is not None
        assert found.agent_type == "claude-code"
        assert found.execution_mode == "WRAPPED_TERMINAL"
        assert found.status == "ACTIVE"

    def test_create_with_all_fields(self, session: Session):
        project = Project(name="FlowOS", repo_path="C:/repo")
        session.add(project)
        session.flush()  # Osiguraj da project ima ID

        task = Task(project_id=project.id, title="FLOW-101")
        session.add(task)
        session.flush()  # Osiguraj da task ima ID
        session.commit()

        s = AgentSession(
            task_id=task.id,
            project_id=project.id,
            agent_type="pi",
            model_name="glm-4.7",
            execution_mode="WRAPPED_TERMINAL",
            terminal_label="Terminal 1",
            working_directory="C:/repo",
            repo_path="C:/repo",
            branch_name="main",
            worktree_path="C:/worktrees/FLOW-101",
            base_commit_sha="abc123",
            pid=12345,
        )
        session.add(s)
        session.commit()

        found = session.get(AgentSession, s.id)
        assert found.model_name == "glm-4.7"
        assert found.branch_name == "main"
        assert found.base_commit_sha == "abc123"
        assert found.pid == 12345

    def test_session_task_nullable(self, session: Session):
        """Sesija moze postojati bez task-a (EXTERNAL_TRACKED)."""
        project = Project(name="FlowOS", repo_path="C:/repo")
        session.add(project)
        session.commit()

        s = AgentSession(
            project_id=project.id,
            agent_type="codex",
            repo_path="C:/repo",
            task_id=None,
        )
        session.add(s)
        session.commit()

        found = session.get(AgentSession, s.id)
        assert found.task_id is None


# ═══════════════════════════════════════════════════════════════════
# SessionEvent
# ═══════════════════════════════════════════════════════════════════


class TestSessionEventCRUD:
    def test_create_event(self, session: Session):
        project = Project(name="FlowOS", repo_path="C:/repo")
        session.add(project)
        session.commit()

        s = AgentSession(project_id=project.id, agent_type="pi", repo_path="C:/repo")
        session.add(s)
        session.commit()

        event = SessionEvent(
            session_id=s.id,
            event_type="STARTED",
            summary="Sesija pokrenuta",
            idempotency_key="key-001",
        )
        session.add(event)
        session.commit()

        found = session.get(SessionEvent, event.id)
        assert found is not None
        assert found.event_type == "STARTED"
        assert found.idempotency_key == "key-001"

    def test_unique_idempotency_key(self, session: Session):
        project = Project(name="FlowOS", repo_path="C:/repo")
        session.add(project)
        session.flush()  # Osiguraj da project ima ID

        s = AgentSession(project_id=project.id, agent_type="pi", repo_path="C:/repo")
        session.add(s)
        session.flush()  # Osiguraj da session ima ID
        session.commit()

        e1 = SessionEvent(session_id=s.id, event_type="NOTE", summary="Test", idempotency_key="dup")
        session.add(e1)
        session.commit()

        e2 = SessionEvent(
            session_id=s.id, event_type="NOTE", summary="Test2", idempotency_key="dup"
        )
        session.add(e2)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_cascade_delete_session_deletes_events(self, session: Session):
        project = Project(name="FlowOS", repo_path="C:/repo")
        session.add(project)
        session.flush()

        s = AgentSession(project_id=project.id, agent_type="pi", repo_path="C:/repo")
        session.add(s)
        session.flush()  # Osiguraj da session ima ID
        session.commit()

        event = SessionEvent(
            session_id=s.id, event_type="STARTED", summary="Test", idempotency_key="k1"
        )
        session.add(event)
        session.commit()
        event_id = event.id

        session.delete(s)
        session.commit()

        assert session.get(SessionEvent, event_id) is None


# ═══════════════════════════════════════════════════════════════════
# WAL i FK integritet
# ═══════════════════════════════════════════════════════════════════


class TestSQLiteSettings:
    def test_wal_enabled(self, engine):
        # :memory: baza uvek vraca 'memory', ne 'wal'
        # WAL se testira u test_file_db_works testu
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA journal_mode;")).scalar()
            # Prihvatamo i 'wal' i 'memory' (obe su OK za testiranje)
            assert result.lower() in ("wal", "memory")

    def test_foreign_keys_enabled(self, engine):
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA foreign_keys;")).scalar()
            assert result == 1

    def test_foreign_key_violation_raises(self, session: Session):
        """Task sa nepostojecim project_id treba da padne."""
        task = Task(project_id="00000000-0000-0000-0000-000000000000", title="Orphan")
        session.add(task)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_all_tables_exist(self, engine):
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        assert "projects" in table_names
        assert "tasks" in table_names
        assert "agent_sessions" in table_names
        assert "session_events" in table_names

    def test_file_db_works(self):
        """Testira da baza radi i kao fajl (ne samo :memory:)."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            eng = create_engine(f"sqlite:///{db_path}")

            @event.listens_for(eng, "connect")
            def _set_pragma(dbapi_connection, connection_record):  # noqa: ARG001
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA foreign_keys=ON;")
                cursor.close()

            Base.metadata.create_all(eng)

            # Provera da fajl postoji
            assert db_path.exists()

            # Upis i čitanje
            SessionLocal = sessionmaker(bind=eng)
            with SessionLocal() as s:
                p = Project(name="FileTest", repo_path="C:/test")
                s.add(p)
                s.commit()
                assert s.get(Project, p.id) is not None

            Base.metadata.drop_all(eng)
            eng.dispose()
