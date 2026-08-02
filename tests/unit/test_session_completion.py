"""Testovi za SessionCompletionService — Korak 7 korektivnog naloga.

Proverava:
- uspješan završetak sa commitom
- uspješan proces bez commita ali sa dirty fajlovima → NO_COMMIT
- neuspješan exit code
- session ne postoji
- status izveden iz exit code-a
"""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.report_models  # noqa: F401
from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.conflict_models import Conflict
from flowos.service.services.infrastructure.persistence.models import AgentSession, Project
from flowos.service.services.infrastructure.persistence.report_models import AgentReport
from flowos.service.services.sessions.completion import SessionCompletionService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def project(db_session: Session) -> Project:
    p = Project(id="proj-comp-001", name="Test", repo_path="C:/test/repo")
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def active_session(db_session: Session, project: Project) -> AgentSession:
    s = AgentSession(
        id="sess-comp-001",
        project_id=project.id,
        agent_type="claude-code",
        repo_path=project.repo_path,
        status="ACTIVE",
        started_at=datetime.now(tz=UTC),
    )
    db_session.add(s)
    db_session.flush()
    db_session.commit()
    return s


def _mock_git_state(changed=None, untracked=None, commit="abc123", branch="main", dirty=True):
    """Fabrika za mock GitState."""
    from flowos.service.services.infrastructure.git_poller import GitState

    return GitState(
        commit_sha=commit,
        branch=branch,
        is_dirty=dirty,
        changed_files=changed or [],
        untracked_files=untracked or [],
        observed_at="2026-08-02T12:00:00Z",
    )


def _mock_verify_result(success=True, exit_code=0):
    """Fabrika za mock VerifyResult."""
    from flowos.service.services.verification.service import VerifyResult

    return VerifyResult(
        success=success,
        exit_code=exit_code,
        stdout="All tests passed.",
        stderr="",
        duration_seconds=1.5,
        command="python scripts/verify.py",
        started_at="2026-08-02T12:00:00Z",
        finished_at="2026-08-02T12:00:02Z",
    )


class TestSessionCompletion:
    """Osnovni testovi završetka sesije."""

    def test_successful_completion_with_commit(
        self, db_session: Session, active_session: AgentSession
    ):
        """Uspješan završetak sa commitom — status COMPLETED."""
        svc = SessionCompletionService(db_session)

        with (
            patch.object(svc, "_derive_status", return_value="COMPLETED"),
            patch("flowos.service.services.sessions.completion.GitStateReader") as mock_reader,
            patch("flowos.service.services.sessions.completion.VerificationService") as mock_verify,
        ):
            mock_reader.return_value._read_state.return_value = _mock_git_state(
                changed=["src/a.py"], dirty=True
            )
            mock_verify.return_value.run_verify.return_value = None  # verify ne postoji

            svc.complete_session(
                session_id=active_session.id,
                repo_path="C:/test/repo",
                exit_code=0,
                result_commit_sha="def456",
            )

        db_session.refresh(active_session)
        assert active_session.status == "COMPLETED"
        assert active_session.exit_code == 0
        assert active_session.result_commit_sha == "def456"

    def test_no_commit_with_dirty_files_detects_no_commit_conflict(
        self, db_session: Session, active_session: AgentSession
    ):
        """Sesija bez commita sa dirty fajlovima → NO_COMMIT konflikt."""
        svc = SessionCompletionService(db_session)

        with (
            patch("flowos.service.services.sessions.completion.GitStateReader") as mock_reader,
            patch("flowos.service.services.sessions.completion.VerificationService") as mock_verify,
        ):
            mock_reader.return_value._read_state.return_value = _mock_git_state(
                changed=["src/a.py", "src/b.py"],
                untracked=["new_file.py"],
                dirty=True,
            )
            mock_verify.return_value.run_verify.return_value = None

            svc.complete_session(
                session_id=active_session.id,
                repo_path="C:/test/repo",
                exit_code=0,
                result_commit_sha=None,  # nema commita!
            )

        # Proveri da je NO_COMMIT konflikt kreiran
        conflicts = (
            db_session.query(Conflict)
            .filter(
                Conflict.project_id == active_session.project_id,
                Conflict.conflict_type == "NO_COMMIT",
            )
            .all()
        )
        assert len(conflicts) == 1
        assert conflicts[0].status == "OPEN"

        # Proveri da je report kreiran
        reports = db_session.query(AgentReport).all()
        assert len(reports) == 1

    def test_failed_exit_code_sets_failed_status(
        self, db_session: Session, active_session: AgentSession
    ):
        """Neuspješan exit code → FAILED status."""
        svc = SessionCompletionService(db_session)

        with (
            patch("flowos.service.services.sessions.completion.GitStateReader") as mock_reader,
            patch("flowos.service.services.sessions.completion.VerificationService") as mock_verify,
        ):
            mock_reader.return_value._read_state.return_value = _mock_git_state(dirty=False)
            mock_verify.return_value.run_verify.return_value = None

            svc.complete_session(
                session_id=active_session.id,
                repo_path="C:/test/repo",
                exit_code=1,
            )

        db_session.refresh(active_session)
        assert active_session.status == "FAILED"
        assert active_session.exit_code == 1

    def test_session_not_found_no_error(self, db_session: Session):
        """Nepostojeća sesija — ne baca izuzetak."""
        svc = SessionCompletionService(db_session)

        # Ne sme da baci izuzetak
        svc.complete_session(
            session_id="nepostojeca-sesija",
            repo_path="C:/test/repo",
            exit_code=0,
        )
        # Samo loguje grešku, ne baca izuzetak

    def test_exit_code_none_defaults_to_completed(
        self, db_session: Session, active_session: AgentSession
    ):
        """Nepoznat exit code → COMPLETED."""
        svc = SessionCompletionService(db_session)

        with (
            patch("flowos.service.services.sessions.completion.GitStateReader") as mock_reader,
            patch("flowos.service.services.sessions.completion.VerificationService") as mock_verify,
        ):
            mock_reader.return_value._read_state.return_value = _mock_git_state(dirty=False)
            mock_verify.return_value.run_verify.return_value = None

            svc.complete_session(
                session_id=active_session.id,
                repo_path="C:/test/repo",
                exit_code=None,
            )

        db_session.refresh(active_session)
        assert active_session.status == "COMPLETED"

    def test_clean_session_no_no_commit_conflict(
        self, db_session: Session, active_session: AgentSession
    ):
        """Čista sesija bez dirty fajlova → nema NO_COMMIT čak i bez commita."""
        svc = SessionCompletionService(db_session)

        with (
            patch("flowos.service.services.sessions.completion.GitStateReader") as mock_reader,
            patch("flowos.service.services.sessions.completion.VerificationService") as mock_verify,
        ):
            mock_reader.return_value._read_state.return_value = _mock_git_state(
                changed=[], untracked=[], dirty=False
            )
            mock_verify.return_value.run_verify.return_value = None

            svc.complete_session(
                session_id=active_session.id,
                repo_path="C:/test/repo",
                exit_code=0,
                result_commit_sha=None,
            )

        conflicts = db_session.query(Conflict).filter(Conflict.conflict_type == "NO_COMMIT").all()
        assert len(conflicts) == 0

    def test_derive_status(self):
        """Testira _derive_status za sve varijante."""
        assert SessionCompletionService._derive_status(0) == "COMPLETED"
        assert SessionCompletionService._derive_status(1) == "FAILED"
        assert SessionCompletionService._derive_status(127) == "FAILED"
        assert SessionCompletionService._derive_status(-1) == "FAILED"
        assert SessionCompletionService._derive_status(None) == "COMPLETED"
