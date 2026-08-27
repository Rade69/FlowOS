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
import flowos.service.services.infrastructure.persistence.workflow_ledger_models  # noqa: F401
from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.conflict_models import Conflict
from flowos.service.services.infrastructure.persistence.models import (
    AgentSession,
    Project,
    SessionEvent,
)
from flowos.service.services.infrastructure.persistence.plan_models import Plan, PlanItem, PlanPhase
from flowos.service.services.infrastructure.persistence.report_models import AgentReport
from flowos.service.services.infrastructure.persistence.workflow_ledger_models import (
    WorkflowLedgerEvent,
)
from flowos.service.services.sessions.completion import SessionCompletionService
from flowos.service.services.verification.service import VerificationResult
from flowos.service.services.workflow.ledger import WorkflowLedgerService


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
    """Fabrika za mock VerificationResult."""
    from flowos.service.services.verification.service import VerificationResult

    return VerificationResult(
        artifact_id="mock-artifact-id",
        verify_path="scripts/verify.py",
        success=success,
        exit_code=exit_code,
        stdout="All tests passed.",
        stderr="",
        duration_seconds=1.5,
        timed_out=False,
        verified_at="2026-08-02T12:00:00Z",
    )


def _mock_verify_result_with_artifact(
    artifact_path: str, *, success=True, exit_code=0, timed_out=False
) -> VerificationResult:
    """Fabrika za realističan VerificationResult sa postavljenim artifact_path."""
    return VerificationResult(
        artifact_id="artifact-with-path",
        verify_path="scripts/verify.py",
        success=success,
        exit_code=exit_code,
        stdout="All tests passed." if success else "FAIL",
        stderr="",
        duration_seconds=1.5,
        timed_out=timed_out,
        verified_at=datetime.now(tz=UTC).isoformat(),
        artifact_path=artifact_path,
    )


def _plan_item(db: Session, project: Project, status: str) -> PlanItem:
    plan = Plan(id=f"plan-{status}", project_id=project.id, title=status, status="ACTIVE")
    phase = PlanPhase(
        id=f"phase-{status}",
        plan_id=plan.id,
        phase_key=status,
        title=status,
        sequence=0,
    )
    item = PlanItem(
        id=f"item-{status}",
        plan_phase_id=phase.id,
        item_key=f"FLOW-{status}",
        title=status,
        status=status,
    )
    db.add_all([plan, phase, item])
    db.flush()
    return item


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
            mock_reader.return_value.read_state.return_value = _mock_git_state(
                changed=["src/a.py"], dirty=True
            )
            mock_verify.return_value.run_verify.return_value = None  # verify ne postoji

            svc.complete_session(
                session_id=active_session.id,
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
            mock_reader.return_value.read_state.return_value = _mock_git_state(
                changed=["src/a.py", "src/b.py"],
                untracked=["new_file.py"],
                dirty=True,
            )
            mock_verify.return_value.run_verify.return_value = None

            svc.complete_session(
                session_id=active_session.id,
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
            mock_reader.return_value.read_state.return_value = _mock_git_state(dirty=False)
            mock_verify.return_value.run_verify.return_value = None

            svc.complete_session(
                session_id=active_session.id,
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
            exit_code=0,
        )
        # Samo loguje grešku, ne baca izuzetak

    def test_exit_code_none_defaults_to_needs_review(
        self, db_session: Session, active_session: AgentSession
    ):
        """Nepoznat exit code → COMPLETED."""
        svc = SessionCompletionService(db_session)

        with (
            patch("flowos.service.services.sessions.completion.GitStateReader") as mock_reader,
            patch("flowos.service.services.sessions.completion.VerificationService") as mock_verify,
        ):
            mock_reader.return_value.read_state.return_value = _mock_git_state(dirty=False)
            mock_verify.return_value.run_verify.return_value = None

            svc.complete_session(
                session_id=active_session.id,
                exit_code=None,
            )

        db_session.refresh(active_session)
        assert active_session.status == "NEEDS_REVIEW"

    def test_clean_session_no_no_commit_conflict(
        self, db_session: Session, active_session: AgentSession
    ):
        """Čista sesija bez dirty fajlova → nema NO_COMMIT čak i bez commita."""
        svc = SessionCompletionService(db_session)

        with (
            patch("flowos.service.services.sessions.completion.GitStateReader") as mock_reader,
            patch("flowos.service.services.sessions.completion.VerificationService") as mock_verify,
        ):
            mock_reader.return_value.read_state.return_value = _mock_git_state(
                changed=[], untracked=[], dirty=False
            )
            mock_verify.return_value.run_verify.return_value = None

            svc.complete_session(
                session_id=active_session.id,
                exit_code=0,
                result_commit_sha=None,
            )

        conflicts = db_session.query(Conflict).filter(Conflict.conflict_type == "NO_COMMIT").all()
        assert len(conflicts) == 0

    def test_result_commit_does_not_mark_plan_item_implemented(
        self, db_session: Session, project: Project, active_session: AgentSession
    ):
        """Commit je Git činjenica, ne workflow authority za IMPLEMENTED."""
        item = _plan_item(db_session, project, "IN_PROGRESS")
        active_session.plan_item_id = item.id
        active_session.base_commit_sha = "abc123"
        db_session.flush()
        svc = SessionCompletionService(db_session)

        with (
            patch("flowos.service.services.sessions.completion.GitStateReader") as mock_reader,
            patch("flowos.service.services.sessions.completion.VerificationService") as mock_verify,
        ):
            mock_reader.return_value.read_state.return_value = _mock_git_state(
                changed=["src/a.py"], commit="def456", dirty=True
            )
            mock_verify.return_value.run_verify.return_value = None

            svc.complete_session(
                session_id=active_session.id,
                exit_code=0,
                result_commit_sha="def456",
            )

        db_session.refresh(item)
        db_session.refresh(active_session)
        assert item.status == "IN_PROGRESS"
        assert active_session.result_commit_sha == "def456"

    def test_dirty_files_do_not_mark_plan_item_implemented(
        self, db_session: Session, project: Project, active_session: AgentSession
    ):
        """Dirty files su filesystem/Git činjenica, ne workflow authority."""
        item = _plan_item(db_session, project, "IN_PROGRESS")
        active_session.plan_item_id = item.id
        db_session.flush()
        svc = SessionCompletionService(db_session)

        with (
            patch("flowos.service.services.sessions.completion.GitStateReader") as mock_reader,
            patch("flowos.service.services.sessions.completion.VerificationService") as mock_verify,
        ):
            mock_reader.return_value.read_state.return_value = _mock_git_state(
                changed=["src/a.py"], untracked=["new.py"], dirty=True
            )
            mock_verify.return_value.run_verify.return_value = None

            svc.complete_session(
                session_id=active_session.id,
                exit_code=0,
                result_commit_sha=None,
            )

        db_session.refresh(item)
        assert item.status == "IN_PROGRESS"
        assert db_session.query(Conflict).filter(Conflict.conflict_type == "NO_COMMIT").count() == 1

    def test_verify_pass_does_not_mark_plan_item_verified_but_keeps_verify_event(
        self,
        db_session: Session,
        project: Project,
        active_session: AgentSession,
        tmp_path,
    ):
        """Verify PASS ostaje verification činjenica, ne PlanItem status authority."""
        repo = tmp_path / "repo"
        scripts = repo / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "verify.py").write_text("print('ok')", encoding="utf-8")
        project.repo_path = str(repo)
        active_session.repo_path = str(repo)
        item = _plan_item(db_session, project, "IMPLEMENTED")
        active_session.plan_item_id = item.id
        db_session.flush()
        svc = SessionCompletionService(db_session)

        with (
            patch("flowos.service.services.sessions.completion.GitStateReader") as mock_reader,
            patch("flowos.service.services.sessions.completion.VerificationService") as mock_verify,
        ):
            mock_reader.return_value.read_state.return_value = _mock_git_state(dirty=False)
            mock_verify.return_value.run_verify.return_value = _mock_verify_result(
                success=True, exit_code=0
            )

            svc.complete_session(session_id=active_session.id, exit_code=0)

        db_session.refresh(item)
        assert item.status == "IMPLEMENTED"
        verify_event = (
            db_session.query(SessionEvent)
            .filter(
                SessionEvent.session_id == active_session.id,
                SessionEvent.event_type == "VERIFY_RESULT",
            )
            .one()
        )
        assert '"success": true' in (verify_event.payload_json or "")

    def test_verify_pass_creates_test_result_ledger_event(
        self,
        db_session: Session,
        project: Project,
        active_session: AgentSession,
        tmp_path,
    ):
        """Verify PASS sa stvarnim artifact_path proizvodi TEST_RESULT event."""
        repo = tmp_path / "repo"
        scripts = repo / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "verify.py").write_text("print('ok')", encoding="utf-8")
        artifact_dir = tmp_path / "artifacts" / "verification" / "artifact-with-path"
        artifact_dir.mkdir(parents=True)
        project.repo_path = str(repo)
        active_session.repo_path = str(repo)
        db_session.flush()
        svc = SessionCompletionService(db_session)

        with (
            patch("flowos.service.services.sessions.completion.GitStateReader") as mock_reader,
            patch("flowos.service.services.sessions.completion.VerificationService") as mock_verify,
        ):
            mock_reader.return_value.read_state.return_value = _mock_git_state(dirty=False)
            mock_verify.return_value.run_verify.return_value = _mock_verify_result_with_artifact(
                str(artifact_dir), success=True
            )

            svc.complete_session(session_id=active_session.id, exit_code=0)

        event = db_session.query(WorkflowLedgerEvent).one()
        assert event.event_type == "TEST_RESULT"
        assert event.session_id == active_session.id
        assert event.project_id == project.id
        assert event.task_id is None
        assert event.plan_item_id is None

    def test_ledger_savepoint_failure_does_not_break_session_completion(
        self,
        db_session: Session,
        project: Project,
        active_session: AgentSession,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """SAVEPOINT izolacija: TEST_RESULT append neuspjeh ne smije oboriti
        ostatak SessionCompletion transakcije niti ostaviti sesiju u failed
        transaction stanju. Koristi stvaran SQLAlchemy/SQLite begin_nested(),
        ne mockuje transakcionu mehaniku — mockuje se samo ishod
        append_test_result()-a."""
        repo = tmp_path / "repo"
        scripts = repo / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "verify.py").write_text("print('ok')", encoding="utf-8")
        artifact_dir = tmp_path / "artifacts" / "verification" / "savepoint-artifact"
        artifact_dir.mkdir(parents=True)
        project.repo_path = str(repo)
        active_session.repo_path = str(repo)
        item = _plan_item(db_session, project, "IMPLEMENTED")
        active_session.plan_item_id = item.id
        db_session.flush()

        def _raise(self, **kwargs):  # noqa: ARG001
            raise RuntimeError("forced ledger failure")

        monkeypatch.setattr(WorkflowLedgerService, "append_test_result", _raise)

        svc = SessionCompletionService(db_session)
        with (
            patch("flowos.service.services.sessions.completion.GitStateReader") as mock_reader,
            patch("flowos.service.services.sessions.completion.VerificationService") as mock_verify,
        ):
            mock_reader.return_value.read_state.return_value = _mock_git_state(dirty=False)
            mock_verify.return_value.run_verify.return_value = _mock_verify_result_with_artifact(
                str(artifact_dir), success=True
            )

            # NE SMIJE baciti izuzetak van complete_session — SAVEPOINT hvata
            # grešku lokalno, complete_session nastavlja i sam commit-uje.
            svc.complete_session(session_id=active_session.id, exit_code=0)

        # 1. TEST_RESULT event ne postoji (append je pukao unutar SAVEPOINT-a).
        assert db_session.query(WorkflowLedgerEvent).count() == 0

        # 2. Outer SessionCompletion se ipak uspješno commitovao (complete_session
        #    interno zove self._db.commit() — da je sesija bila u failed
        #    transaction stanju, taj poziv bi sam pukao unutar complete_session).
        db_session.refresh(active_session)
        assert active_session.status == "COMPLETED"
        assert active_session.ended_at is not None
        assert active_session.exit_code == 0

        # 3. VERIFY_RESULT SessionEvent postoji — nije obrisan SAVEPOINT rollbackom.
        verify_event = (
            db_session.query(SessionEvent)
            .filter(
                SessionEvent.session_id == active_session.id,
                SessionEvent.event_type == "VERIFY_RESULT",
            )
            .one()
        )
        assert '"success": true' in (verify_event.payload_json or "")

        # 4. PlanItem status nije promijenjen.
        db_session.refresh(item)
        assert item.status == "IMPLEMENTED"

        # 5. Sesija nije ostala u SQLAlchemy failed-transaction stanju — može
        #    dalje raditi normalan rad (flush/commit) van complete_session poziva.
        extra = Project(id="after-savepoint-failure-check", name="X", repo_path="C:/x")
        db_session.add(extra)
        db_session.flush()
        db_session.commit()
        assert db_session.get(Project, "after-savepoint-failure-check") is not None

    def test_derive_status(self):
        """Testira _derive_status za sve varijante."""
        assert SessionCompletionService._derive_status(0) == "COMPLETED"
        assert SessionCompletionService._derive_status(1) == "FAILED"
        assert SessionCompletionService._derive_status(127) == "FAILED"
        assert SessionCompletionService._derive_status(-1) == "FAILED"
        assert SessionCompletionService._derive_status(None) == "NEEDS_REVIEW"

    def test_verification_summary_rediguje_secret(
        self, db_session: Session, active_session: AgentSession, tmp_path
    ):
        """FLOW-1109 REV-1109-H1: DB verification_summary je redigovan, raw ostaje."""
        from flowos.service.services.infrastructure.redaction import (
            register_secret,
            reset_redactor,
        )

        # verify.py mora postojati da complete_session uđe u verify granu.
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "verify.py").write_text("# stub", encoding="utf-8")
        active_session.repo_path = str(tmp_path)
        db_session.commit()

        secret = "sk-completion-test-secret-abcdef123456"
        verify_result = VerificationResult(
            artifact_id="art-secret",
            verify_path="scripts/verify.py",
            success=True,
            exit_code=0,
            stdout=f"before {secret} after",
            stderr=f"err {secret}",
            duration_seconds=1.0,
            timed_out=False,
            verified_at="2026-08-19T00:00:00Z",
        )
        register_secret(secret)
        try:
            svc = SessionCompletionService(db_session)
            with (
                patch("flowos.service.services.sessions.completion.GitStateReader") as mock_reader,
                patch(
                    "flowos.service.services.sessions.completion.VerificationService"
                ) as mock_verify,
            ):
                mock_reader.return_value.read_state.return_value = _mock_git_state(dirty=False)
                mock_verify.return_value.run_verify.return_value = verify_result
                svc.complete_session(session_id=active_session.id, exit_code=0)
        finally:
            reset_redactor()

        report = db_session.query(AgentReport).one()
        summary = report.verification_summary or ""
        assert secret not in summary
        assert "[REDACTED]" in summary
        # RAW verification result (in-memory computation data) nije mutiran.
        assert secret in verify_result.stdout
        assert secret in verify_result.stderr
