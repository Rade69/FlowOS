"""Integracioni testovi za Workflow Ledger Phase 3B — TEST_RESULT.

Phase 3B dodaje TEST_RESULT evente iz VerificationResult-a. Event bilježi
isključivo da je scripts/verify.py stvarno izvršen i proizveo konkretan
PASS/FAIL/TIMEOUT ishod — nikad ne mijenja PlanItem.status, nikad ne
pretpostavlja task/plan_item atribuciju.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import flowos.service.services.infrastructure.persistence.activity_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.report_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.workflow_ledger_models  # noqa: F401
from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.models import AgentSession, Project, Task
from flowos.service.services.infrastructure.persistence.plan_models import Plan, PlanItem, PlanPhase
from flowos.service.services.infrastructure.persistence.workflow_ledger_models import (
    WorkflowLedgerEvent,
)
from flowos.service.services.sessions.bindings import SessionTaskBindingService
from flowos.service.services.sessions.service import SessionService
from flowos.service.services.verification.service import ArtifactStore, VerificationService
from flowos.service.services.workflow.ledger import (
    TEST_RESULT,
    VERIFICATION_ARTIFACT_SOURCE,
    WorkflowLedgerService,
)


@pytest.fixture
def engine():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, connection_record):  # noqa: ARG001
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def project(db_session: Session, tmp_path: Path) -> Project:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    project = Project(id="project-testresult", name="TestResult", repo_path=str(repo))
    db_session.add(project)
    db_session.flush()
    return project


def _session(db: Session, project: Project) -> AgentSession:
    return SessionService(db).create_session(
        project_id=project.id, agent_type="codex", repo_path=project.repo_path
    )


def _write_verify_script(repo_path: str, body: str) -> None:
    script = Path(repo_path) / "scripts" / "verify.py"
    script.write_text(textwrap.dedent(body), encoding="utf-8")


def _payload(event: WorkflowLedgerEvent) -> dict:
    payload = json.loads(event.payload_json)
    assert isinstance(payload, dict)
    return payload


def _plan_item(db: Session, project: Project, key: str, status: str = "IN_PROGRESS") -> PlanItem:
    plan = (
        db.query(Plan).filter(Plan.project_id == project.id, Plan.status == "ACTIVE").one_or_none()
    )
    if plan is None:
        plan = Plan(id=f"plan-{key}", project_id=project.id, title=key, status="ACTIVE")
    phase = PlanPhase(id=f"phase-{key}", plan_id=plan.id, phase_key=key, title=key, sequence=0)
    item = PlanItem(
        id=f"item-{key}", plan_phase_id=phase.id, item_key=key, title=key, status=status
    )
    db.add_all([plan, phase, item])
    db.flush()
    return item


def _task(db: Session, project: Project, item: PlanItem, key: str) -> Task:
    task = Task(id=f"task-{key}", project_id=project.id, title=key, plan_item_id=item.id)
    db.add(task)
    db.flush()
    return task


class TestPassFailTimeout:
    """1-3: PASS/FAIL/TIMEOUT sa stvarnim artefaktom kreiraju TEST_RESULT."""

    def test_pass_creates_test_result_event(self, db_session: Session, project: Project):
        _write_verify_script(project.repo_path, "print('ok')\nimport sys; sys.exit(0)\n")
        session = _session(db_session, project)
        db_session.commit()

        result = VerificationService().run_verify(
            project.repo_path, session_id=session.id, project_id=project.id
        )
        assert result.artifact_path is not None
        assert result.success is True

        event = WorkflowLedgerService(db_session).append_test_result(
            project_id=project.id, session_id=session.id, result=result
        )

        assert event is not None
        assert event.event_type == TEST_RESULT
        stored = db_session.query(WorkflowLedgerEvent).one()
        assert stored.id == event.id
        assert _payload(event)["success"] is True

    def test_fail_creates_test_result_event(self, db_session: Session, project: Project):
        _write_verify_script(project.repo_path, "import sys; sys.exit(1)\n")
        session = _session(db_session, project)
        db_session.commit()

        result = VerificationService().run_verify(
            project.repo_path, session_id=session.id, project_id=project.id
        )
        assert result.artifact_path is not None
        assert result.success is False
        assert result.timed_out is False

        event = WorkflowLedgerService(db_session).append_test_result(
            project_id=project.id, session_id=session.id, result=result
        )

        assert event is not None
        payload = _payload(event)
        assert payload["success"] is False
        assert payload["timed_out"] is False
        assert payload["exit_code"] == 1

    def test_timeout_creates_test_result_event(self, db_session: Session, project: Project):
        _write_verify_script(project.repo_path, "import time; time.sleep(5)\n")
        session = _session(db_session, project)
        db_session.commit()

        result = VerificationService(timeout_seconds=1).run_verify(
            project.repo_path, session_id=session.id, project_id=project.id
        )
        assert result.artifact_path is not None
        assert result.timed_out is True
        assert result.success is False

        event = WorkflowLedgerService(db_session).append_test_result(
            project_id=project.id, session_id=session.id, result=result
        )

        assert event is not None
        payload = _payload(event)
        assert payload["success"] is False
        assert payload["timed_out"] is True


class TestArtifactQualification:
    """4-5: bez perzistovanog artefakta, nema TEST_RESULT eventa."""

    def test_verify_not_found_creates_no_event(self, db_session: Session, project: Project):
        # Namjerno NE pišemo scripts/verify.py.
        session = _session(db_session, project)
        db_session.commit()

        result = VerificationService().run_verify(
            project.repo_path, session_id=session.id, project_id=project.id
        )
        assert result.artifact_path is None

        event = WorkflowLedgerService(db_session).append_test_result(
            project_id=project.id, session_id=session.id, result=result
        )

        assert event is None
        assert db_session.query(WorkflowLedgerEvent).count() == 0

    def test_artifact_save_failure_creates_no_event(
        self, db_session: Session, project: Project, monkeypatch: pytest.MonkeyPatch
    ):
        _write_verify_script(project.repo_path, "import sys; sys.exit(0)\n")
        session = _session(db_session, project)
        db_session.commit()

        def _raise(self, *args, **kwargs):  # noqa: ARG001
            raise OSError("disk pun")

        monkeypatch.setattr(ArtifactStore, "save", _raise)

        result = VerificationService().run_verify(
            project.repo_path, session_id=session.id, project_id=project.id
        )
        # Komanda JE izvršena (exit_code je stvaran), ali artefakt nije sačuvan.
        assert result.exit_code == 0
        assert result.artifact_path is None

        event = WorkflowLedgerService(db_session).append_test_result(
            project_id=project.id, session_id=session.id, result=result
        )

        assert event is None
        assert db_session.query(WorkflowLedgerEvent).count() == 0


class TestEventShape:
    """6-15: source identity, scope, occurred_at, payload sadržaj."""

    def _pass_result(self, db_session: Session, project: Project, session: AgentSession):
        _write_verify_script(project.repo_path, "import sys; sys.exit(0)\n")
        return VerificationService().run_verify(
            project.repo_path, session_id=session.id, project_id=project.id
        )

    def test_source_kind_and_id(self, db_session: Session, project: Project):
        session = _session(db_session, project)
        db_session.commit()
        result = self._pass_result(db_session, project, session)

        event = WorkflowLedgerService(db_session).append_test_result(
            project_id=project.id, session_id=session.id, result=result
        )

        assert event.source_kind == VERIFICATION_ARTIFACT_SOURCE
        assert event.source_id == result.artifact_id

    def test_event_project_and_session_correct(self, db_session: Session, project: Project):
        session = _session(db_session, project)
        db_session.commit()
        result = self._pass_result(db_session, project, session)

        event = WorkflowLedgerService(db_session).append_test_result(
            project_id=project.id, session_id=session.id, result=result
        )

        assert event.project_id == project.id
        assert event.session_id == session.id

    def test_task_and_plan_item_are_null(self, db_session: Session, project: Project):
        item = _plan_item(db_session, project, "FLOW-1")
        task = _task(db_session, project, item, "FLOW-1")
        session = _session(db_session, project)
        SessionTaskBindingService(db_session).switch_binding(session.id, task_id=task.id)
        db_session.commit()
        result = self._pass_result(db_session, project, session)

        event = WorkflowLedgerService(db_session).append_test_result(
            project_id=project.id, session_id=session.id, result=result
        )

        assert event.task_id is None
        assert event.plan_item_id is None

    def test_task_plan_item_null_even_with_aba_binding_history(
        self, db_session: Session, project: Project
    ):
        item_a = _plan_item(db_session, project, "FLOW-A")
        item_b = _plan_item(db_session, project, "FLOW-B")
        task_a = _task(db_session, project, item_a, "FLOW-A")
        task_b = _task(db_session, project, item_b, "FLOW-B")
        session = _session(db_session, project)
        bindings = SessionTaskBindingService(db_session)
        bindings.switch_binding(session.id, task_id=task_a.id)
        bindings.switch_binding(session.id, task_id=task_b.id)
        bindings.switch_binding(session.id, task_id=task_a.id)
        db_session.commit()
        result = self._pass_result(db_session, project, session)

        event = WorkflowLedgerService(db_session).append_test_result(
            project_id=project.id, session_id=session.id, result=result
        )

        assert event.task_id is None
        assert event.plan_item_id is None
        assert "task_id" not in _payload(event)
        assert "plan_item_id" not in _payload(event)

    def test_occurred_at_matches_parsed_verified_at(self, db_session: Session, project: Project):
        from datetime import datetime

        session = _session(db_session, project)
        db_session.commit()
        result = self._pass_result(db_session, project, session)

        event = WorkflowLedgerService(db_session).append_test_result(
            project_id=project.id, session_id=session.id, result=result
        )

        assert event.occurred_at == datetime.fromisoformat(result.verified_at)
        assert event.occurred_at.tzinfo is not None

    def test_payload_has_only_expected_evidence_fields(self, db_session: Session, project: Project):
        session = _session(db_session, project)
        db_session.commit()
        result = self._pass_result(db_session, project, session)

        event = WorkflowLedgerService(db_session).append_test_result(
            project_id=project.id, session_id=session.id, result=result
        )
        payload = _payload(event)

        assert set(payload) == {
            "artifact_id",
            "verify_path",
            "exit_code",
            "success",
            "timed_out",
            "duration_seconds",
            "artifact_path",
        }
        assert payload["artifact_id"] == result.artifact_id
        assert payload["artifact_path"] == result.artifact_path

    def test_payload_does_not_contain_raw_stdout_or_stderr(
        self, db_session: Session, project: Project
    ):
        session = _session(db_session, project)
        db_session.commit()
        result = self._pass_result(db_session, project, session)

        event = WorkflowLedgerService(db_session).append_test_result(
            project_id=project.id, session_id=session.id, result=result
        )

        assert "stdout" not in event.payload_json
        assert "stderr" not in event.payload_json


class TestIdempotency:
    """16-18: direktan retry, DB unique, session/project mismatch."""

    def test_direct_retry_returns_same_event_no_duplicate(
        self, db_session: Session, project: Project
    ):
        _write_verify_script(project.repo_path, "import sys; sys.exit(0)\n")
        session = _session(db_session, project)
        db_session.commit()
        result = VerificationService().run_verify(
            project.repo_path, session_id=session.id, project_id=project.id
        )
        svc = WorkflowLedgerService(db_session)

        first = svc.append_test_result(project_id=project.id, session_id=session.id, result=result)
        second = svc.append_test_result(project_id=project.id, session_id=session.id, result=result)

        assert first is not None
        assert second is not None
        assert first.id == second.id
        assert db_session.query(WorkflowLedgerEvent).count() == 1

    def test_db_unique_constraint_still_prevents_duplicate(
        self, db_session: Session, project: Project
    ):
        _write_verify_script(project.repo_path, "import sys; sys.exit(0)\n")
        session = _session(db_session, project)
        db_session.commit()
        result = VerificationService().run_verify(
            project.repo_path, session_id=session.id, project_id=project.id
        )
        existing = WorkflowLedgerService(db_session).append_test_result(
            project_id=project.id, session_id=session.id, result=result
        )
        db_session.commit()

        duplicate = WorkflowLedgerEvent(
            project_id=existing.project_id,
            event_type=existing.event_type,
            session_id=existing.session_id,
            task_id=None,
            plan_item_id=None,
            source_kind=existing.source_kind,
            source_id=existing.source_id,
            occurred_at=existing.occurred_at,
            recorded_at=existing.recorded_at,
            idempotency_key=existing.idempotency_key,
            payload_json="{}",
        )
        db_session.add(duplicate)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_session_project_mismatch_is_rejected(
        self, db_session: Session, project: Project, tmp_path: Path
    ):
        other_repo = tmp_path / "other"
        other_repo.mkdir()
        other_project = Project(id="other-project", name="Other", repo_path=str(other_repo))
        db_session.add(other_project)
        db_session.flush()
        session_in_other = _session(db_session, other_project)
        db_session.commit()

        _write_verify_script(project.repo_path, "import sys; sys.exit(0)\n")
        result = VerificationService().run_verify(
            project.repo_path, session_id=session_in_other.id, project_id=project.id
        )

        with pytest.raises(ValueError, match="ne pripada projektu"):
            WorkflowLedgerService(db_session).append_test_result(
                project_id=project.id, session_id=session_in_other.id, result=result
            )
        assert db_session.query(WorkflowLedgerEvent).count() == 0

    def test_nonexistent_session_is_rejected(self, db_session: Session, project: Project):
        _write_verify_script(project.repo_path, "import sys; sys.exit(0)\n")
        result = VerificationService().run_verify(
            project.repo_path, session_id=str(uuid4()), project_id=project.id
        )

        with pytest.raises(ValueError, match="ne postoji"):
            WorkflowLedgerService(db_session).append_test_result(
                project_id=project.id, session_id=str(uuid4()), result=result
            )


class TestNoPlanItemStatusChange:
    """20-22: PASS/FAIL/TIMEOUT nikad ne mijenjaju PlanItem.status."""

    @pytest.mark.parametrize(
        ("script_body", "expect_success", "expect_timed_out"),
        [
            ("import sys; sys.exit(0)\n", True, False),
            ("import sys; sys.exit(1)\n", False, False),
            ("import time; time.sleep(5)\n", False, True),
        ],
        ids=["pass", "fail", "timeout"],
    )
    def test_result_never_changes_plan_item_status(
        self,
        db_session: Session,
        project: Project,
        script_body: str,
        expect_success: bool,
        expect_timed_out: bool,
    ):
        item = _plan_item(db_session, project, "FLOW-STATUS", status="IMPLEMENTED")
        task = _task(db_session, project, item, "FLOW-STATUS")
        session = _session(db_session, project)
        SessionTaskBindingService(db_session).switch_binding(session.id, task_id=task.id)
        db_session.commit()
        _write_verify_script(project.repo_path, script_body)

        timeout = 1 if expect_timed_out else VerificationService.DEFAULT_TIMEOUT
        result = VerificationService(timeout_seconds=timeout).run_verify(
            project.repo_path, session_id=session.id, project_id=project.id
        )
        assert result.success is expect_success
        assert result.timed_out is expect_timed_out

        WorkflowLedgerService(db_session).append_test_result(
            project_id=project.id, session_id=session.id, result=result
        )

        db_session.refresh(item)
        assert item.status == "IMPLEMENTED"
