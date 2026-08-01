"""Unit testovi za API contracts — validacija i serijalizacija."""

import pytest
from pydantic import ValidationError

from flowos.shared.contracts.conflicts import ConflictResponse
from flowos.shared.contracts.events import SessionEventCreate
from flowos.shared.contracts.projects import ProjectCreate, ProjectUpdate
from flowos.shared.contracts.reports import ReportUpdate
from flowos.shared.contracts.sessions import SessionCreate, SessionUpdate
from flowos.shared.contracts.system import HealthResponse, VersionResponse
from flowos.shared.contracts.tasks import TaskCreate, TaskUpdate

# ═══════════════════════════════════════════════════════════════════
# System
# ═══════════════════════════════════════════════════════════════════


class TestSystemContracts:
    def test_health_response(self):
        r = HealthResponse()
        assert r.status == "ok"

    def test_version_response(self):
        r = VersionResponse(version="1.0.0", api_version=2)
        assert r.version == "1.0.0"
        assert r.api_version == 2


# ═══════════════════════════════════════════════════════════════════
# Projects
# ═══════════════════════════════════════════════════════════════════


class TestProjectCreate:
    def test_valid(self):
        p = ProjectCreate(name="FlowOS", repo_path="C:/Users/test/repo")
        assert p.name == "FlowOS"
        assert p.repo_path == "C:\\Users\\test\\repo"

    def test_name_empty_raises(self):
        with pytest.raises(ValidationError, match="Ime projekta ne sme biti prazno"):
            ProjectCreate(name="   ", repo_path="C:/repo")

    def test_name_too_long_raises(self):
        with pytest.raises(ValidationError, match="najviše 200"):
            ProjectCreate(name="x" * 201, repo_path="C:/repo")

    def test_repo_path_relative_raises(self):
        with pytest.raises(ValidationError, match="apsolutna putanja"):
            ProjectCreate(name="FlowOS", repo_path="relative/path")


class TestProjectUpdate:
    def test_empty_update_allowed(self):
        p = ProjectUpdate()
        assert p.name is None

    def test_name_validation_on_update(self):
        with pytest.raises(ValidationError, match="Ime projekta ne sme biti prazno"):
            ProjectUpdate(name="   ")

    def test_repo_path_validation_on_update(self):
        with pytest.raises(ValidationError, match="apsolutna putanja"):
            ProjectUpdate(repo_path="relative")


# ═══════════════════════════════════════════════════════════════════
# Tasks
# ═══════════════════════════════════════════════════════════════════


class TestTaskCreate:
    def test_valid(self):
        t = TaskCreate(project_id="uuid-1", title="Implementirati login")
        assert t.title == "Implementirati login"
        assert t.priority == "NORMAL"

    def test_title_empty_raises(self):
        with pytest.raises(ValidationError, match="Naslov zadatka ne sme biti prazan"):
            TaskCreate(project_id="uuid-1", title="   ")

    def test_title_too_long_raises(self):
        with pytest.raises(ValidationError, match="najviše 500"):
            TaskCreate(project_id="uuid-1", title="x" * 501)

    def test_priority_invalid_raises(self):
        with pytest.raises(ValidationError, match="Neispravan prioritet"):
            TaskCreate(project_id="uuid-1", title="Test", priority="NEPOSTOJECI")

    def test_priority_valid_values(self):
        for p in ["LOW", "NORMAL", "HIGH", "URGENT"]:
            t = TaskCreate(project_id="uuid-1", title="Test", priority=p)
            assert t.priority == p

    def test_project_id_empty_raises(self):
        with pytest.raises(ValidationError, match="project_id ne sme biti prazan"):
            TaskCreate(project_id="   ", title="Test")


class TestTaskUpdate:
    def test_empty_update_allowed(self):
        t = TaskUpdate()
        assert t.title is None

    def test_status_invalid_raises(self):
        with pytest.raises(ValidationError, match="Neispravan status"):
            TaskUpdate(status="NEPOSTOJECI")

    def test_status_valid_values(self):
        for s in ["OPEN", "IN_PROGRESS", "BLOCKED", "DONE"]:
            TaskUpdate(status=s)


# ═══════════════════════════════════════════════════════════════════
# Sessions
# ═══════════════════════════════════════════════════════════════════


class TestSessionCreate:
    def test_valid_minimal(self):
        s = SessionCreate(
            project_id="uuid-1",
            agent_type="claude-code",
            repo_path="C:/repo",
            idempotency_key="550e8400-e29b-41d4-a716-446655440000",
        )
        assert s.agent_type == "claude-code"
        assert s.execution_mode == "WRAPPED_TERMINAL"

    def test_execution_mode_invalid_raises(self):
        with pytest.raises(ValidationError, match="Neispravan execution_mode"):
            SessionCreate(
                project_id="uuid-1",
                agent_type="claude-code",
                repo_path="C:/repo",
                idempotency_key="key-1",
                execution_mode="NEPOSTOJECI",
            )

    def test_execution_mode_valid_values(self):
        for mode in ["WRAPPED_TERMINAL", "EXTERNAL_TRACKED", "MANAGED", "DURABLE"]:
            s = SessionCreate(
                project_id="uuid-1",
                agent_type="pi",
                repo_path="C:/repo",
                idempotency_key="key-1",
                execution_mode=mode,
            )
            assert s.execution_mode == mode

    def test_agent_type_empty_raises(self):
        with pytest.raises(ValidationError, match="agent_type ne sme biti prazan"):
            SessionCreate(
                project_id="uuid-1",
                agent_type="   ",
                repo_path="C:/repo",
                idempotency_key="key-1",
            )

    def test_repo_path_relative_raises(self):
        with pytest.raises(ValidationError, match="apsolutna putanja"):
            SessionCreate(
                project_id="uuid-1",
                agent_type="pi",
                repo_path="relative/path",
                idempotency_key="key-1",
            )

    def test_idempotency_key_empty_raises(self):
        with pytest.raises(ValidationError, match="idempotency_key ne sme biti prazan"):
            SessionCreate(
                project_id="uuid-1",
                agent_type="pi",
                repo_path="C:/repo",
                idempotency_key="   ",
            )


class TestSessionUpdate:
    def test_status_invalid_raises(self):
        with pytest.raises(ValidationError, match="Neispravan status"):
            SessionUpdate(status="NEPOSTOJECI")

    def test_status_valid_values(self):
        for s in ["ACTIVE", "IDLE", "COMPLETED", "ABANDONED", "NEEDS_REVIEW"]:
            SessionUpdate(status=s)


# ═══════════════════════════════════════════════════════════════════
# Events
# ═══════════════════════════════════════════════════════════════════


class TestSessionEventCreate:
    def test_valid(self):
        e = SessionEventCreate(
            event_type="STARTED",
            summary="Sesija pokrenuta",
            idempotency_key="key-1",
        )
        assert e.event_type == "STARTED"

    def test_event_type_invalid_raises(self):
        with pytest.raises(ValidationError, match="Neispravan event_type"):
            SessionEventCreate(
                event_type="NEPOSTOJECI",
                summary="Test",
                idempotency_key="key-1",
            )

    def test_summary_empty_raises(self):
        with pytest.raises(ValidationError, match="summary ne sme biti prazan"):
            SessionEventCreate(
                event_type="STARTED",
                summary="   ",
                idempotency_key="key-1",
            )


# ═══════════════════════════════════════════════════════════════════
# Conflicts
# ═══════════════════════════════════════════════════════════════════


class TestConflictResponse:
    def test_conflict_level_invalid_raises(self):
        with pytest.raises(ValidationError, match="Neispravan conflict_level"):
            ConflictResponse(
                id="c-1",
                project_id="p-1",
                file_path="test.py",
                session_ids=["s-1"],
                conflict_level="LOW",  # Nije u {HIGH, MEDIUM, INFO}
                description="Test",
                detected_at="2026-07-31T12:00:00Z",
            )

    def test_conflict_level_valid_values(self):
        for level in ["HIGH", "MEDIUM", "INFO"]:
            c = ConflictResponse(
                id="c-1",
                project_id="p-1",
                file_path="test.py",
                session_ids=["s-1"],
                conflict_level=level,
                description="Test",
                detected_at="2026-07-31T12:00:00Z",
            )
            assert c.conflict_level == level


# ═══════════════════════════════════════════════════════════════════
# Reports
# ═══════════════════════════════════════════════════════════════════


class TestReportUpdate:
    def test_user_verdict_invalid_raises(self):
        with pytest.raises(ValidationError, match="Neispravan user_verdict"):
            ReportUpdate(user_verdict="MAYBE")

    def test_user_verdict_valid_values(self):
        for v in ["ACCEPTED", "NEEDS_WORK", "REJECTED"]:
            r = ReportUpdate(user_verdict=v)
            assert r.user_verdict == v

    def test_empty_update_allowed(self):
        r = ReportUpdate()
        assert r.user_verdict is None
