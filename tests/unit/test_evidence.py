"""Testovi za EvidenceService i EvidenceBundle."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

import flowos.service.services.infrastructure.persistence.activity_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.conflict_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.models  # noqa: F401
import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401
import flowos.service.services.infrastructure.persistence.report_models  # noqa: F401
from flowos.service.services.evidence import EvidenceService
from flowos.service.services.infrastructure.persistence.base import Base


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", echo=False)

    @event.listens_for(eng, "connect")
    def _pragma(dbapi_connection, connection_record):
        c = dbapi_connection.cursor()
        c.execute("PRAGMA journal_mode=WAL;")
        c.execute("PRAGMA foreign_keys=ON;")
        c.close()

    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


class TestEvidenceBundle:
    def test_evidence_bundle_for_missing_item(self, engine):
        db = Session(engine)
        try:
            svc = EvidenceService(db)
            result = svc.build("nepostojeci-id")
            assert result is None
        finally:
            db.close()

    def test_evidence_bundle_empty_item_no_sessions(self, engine):
        import uuid

        from flowos.service.services.infrastructure.persistence.models import Project
        from flowos.service.services.infrastructure.persistence.plan_models import (
            Plan,
            PlanItem,
            PlanPhase,
        )

        pid, plid, phid, itid = (str(uuid.uuid4()) for _ in range(4))
        db = Session(engine)
        try:
            db.add_all(
                [
                    Project(id=pid, name="Test", repo_path="/tmp/test"),
                    Plan(id=plid, project_id=pid, title="Test Plan", status="ACTIVE"),
                    PlanPhase(id=phid, plan_id=plid, phase_key="F0", title="Faza 0", sequence=0),
                    PlanItem(id=itid, plan_phase_id=phid, item_key="FLOW-999", title="Test item"),
                ]
            )
            db.commit()

            svc = EvidenceService(db)
            bundle = svc.build(itid)
            assert bundle is not None
            assert bundle.plan_item_id == itid
            assert bundle.plan_item_key == "FLOW-999"
            assert bundle.primary_session_id is None
        finally:
            db.rollback()
            db.close()

    def test_evidence_bundle_reads_project_through_phase_and_plan(self, engine):
        import uuid
        from datetime import UTC, datetime

        from flowos.service.services.infrastructure.persistence.conflict_models import Conflict
        from flowos.service.services.infrastructure.persistence.models import (
            AgentSession,
            Project,
        )
        from flowos.service.services.infrastructure.persistence.plan_models import (
            Plan,
            PlanItem,
            PlanPhase,
        )

        pid, other_pid, plid, phid, itid, sid, cid = (str(uuid.uuid4()) for _ in range(7))
        db = Session(engine)
        try:
            now = datetime.now(tz=UTC)
            db.add_all(
                [
                    Project(id=pid, name="Test", repo_path="/tmp/test"),
                    Project(id=other_pid, name="Other", repo_path="/tmp/other"),
                    Plan(id=plid, project_id=pid, title="Test Plan", status="ACTIVE"),
                    PlanPhase(id=phid, plan_id=plid, phase_key="F0", title="Faza 0", sequence=0),
                    PlanItem(id=itid, plan_phase_id=phid, item_key="FLOW-104", title="Test"),
                ]
            )
            db.flush()
            db.add_all(
                [
                    AgentSession(
                        id=sid,
                        project_id=pid,
                        plan_item_id=itid,
                        agent_type="cc",
                        repo_path="/tmp/test",
                        status="COMPLETED",
                    ),
                    Conflict(
                        id=cid,
                        project_id=pid,
                        conflict_type="WRITE_WRITE",
                        conflict_level="HIGH",
                        description="Relevant",
                        conflict_key=f"write_write::{pid}::src/app.py",
                        file_path="src/app.py",
                        status="OPEN",
                        evidence_json="{}",
                        first_seen_at=now,
                        last_seen_at=now,
                        occurrence_count=1,
                    ),
                    Conflict(
                        project_id=other_pid,
                        conflict_type="WRITE_WRITE",
                        conflict_level="HIGH",
                        description="Other",
                        conflict_key=f"write_write::{other_pid}::src/app.py",
                        file_path="src/app.py",
                        status="OPEN",
                        evidence_json="{}",
                        first_seen_at=now,
                        last_seen_at=now,
                        occurrence_count=1,
                    ),
                ]
            )
            db.commit()

            bundle = EvidenceService(db).build(itid)
            assert bundle is not None
            assert bundle.conflict_ids == [cid]
        finally:
            db.rollback()
            db.close()

    def test_evidence_bundle_with_commit_and_verification(self, engine):
        import json
        import uuid

        from flowos.service.services.infrastructure.persistence.models import (
            AgentSession,
            Project,
            SessionEvent,
        )
        from flowos.service.services.infrastructure.persistence.plan_models import (
            Plan,
            PlanItem,
            PlanPhase,
        )

        pid, plid, phid, itid, sid = (str(uuid.uuid4()) for _ in range(5))
        db = Session(engine)
        try:
            db.add_all(
                [
                    Project(id=pid, name="Test", repo_path="/tmp/test"),
                    Plan(id=plid, project_id=pid, title="Test Plan", status="ACTIVE"),
                    PlanPhase(id=phid, plan_id=plid, phase_key="F0", title="Faza 0", sequence=0),
                    PlanItem(id=itid, plan_phase_id=phid, item_key="FLOW-100", title="Test"),
                ]
            )
            db.flush()
            db.add_all(
                [
                    AgentSession(
                        id=sid,
                        project_id=pid,
                        plan_item_id=itid,
                        agent_type="cc",
                        repo_path="/tmp/test",
                        base_commit_sha="abc123",
                        result_commit_sha="def456",
                        status="COMPLETED",
                    ),
                    SessionEvent(
                        session_id=sid,
                        event_type="VERIFY_RESULT",
                        summary="Verify PASS",
                        source="VERIFICATION_SERVICE",
                        payload_json=json.dumps({"artifact_id": "art-1", "success": True}),
                    ),
                ]
            )
            db.commit()

            svc = EvidenceService(db)
            bundle = svc.build(itid)
            assert bundle is not None
            assert bundle.primary_session_id == sid
            assert bundle.base_commit_sha == "abc123"
            assert bundle.result_commit_sha == "def456"
            assert bundle.verification_artifact_id == "art-1"
            assert bundle.verification_passed is True
        finally:
            db.rollback()
            db.close()

    def test_evidence_bundle_with_report(self, engine):
        import uuid

        from flowos.service.services.infrastructure.persistence.models import (
            AgentSession,
            Project,
        )
        from flowos.service.services.infrastructure.persistence.plan_models import (
            Plan,
            PlanItem,
            PlanPhase,
        )
        from flowos.service.services.infrastructure.persistence.report_models import AgentReport

        pid, plid, phid, itid, sid, rid = (str(uuid.uuid4()) for _ in range(6))
        db = Session(engine)
        try:
            db.add_all(
                [
                    Project(id=pid, name="Test", repo_path="/tmp/test"),
                    Plan(id=plid, project_id=pid, title="Test Plan", status="ACTIVE"),
                    PlanPhase(id=phid, plan_id=plid, phase_key="F0", title="Faza 0", sequence=0),
                    PlanItem(id=itid, plan_phase_id=phid, item_key="FLOW-101", title="Test"),
                ]
            )
            db.flush()
            db.add_all(
                [
                    AgentSession(
                        id=sid,
                        project_id=pid,
                        plan_item_id=itid,
                        agent_type="pi",
                        repo_path="/tmp/test",
                        status="COMPLETED",
                    ),
                    AgentReport(
                        id=rid,
                        session_id=sid,
                        summary="Done",
                        user_verdict="ACCEPTED",
                        status="FINAL",
                    ),
                ]
            )
            db.commit()

            svc = EvidenceService(db)
            bundle = svc.build(itid)
            assert bundle is not None
            assert bundle.report_id == rid
            assert bundle.report_verdict == "ACCEPTED"
        finally:
            db.rollback()
            db.close()

    def test_evidence_bundle_excludes_unrelated_conflicts(self, engine):
        import uuid
        from datetime import UTC, datetime

        from flowos.service.services.infrastructure.persistence.conflict_models import Conflict
        from flowos.service.services.infrastructure.persistence.models import (
            AgentSession,
            Project,
        )
        from flowos.service.services.infrastructure.persistence.plan_models import (
            Plan,
            PlanItem,
            PlanPhase,
        )

        pid, plid, phid, itid, sid, cid = (str(uuid.uuid4()) for _ in range(6))
        db = Session(engine)
        try:
            db.add_all(
                [
                    Project(id=pid, name="Test", repo_path="/tmp/test"),
                    Plan(id=plid, project_id=pid, title="Test Plan", status="ACTIVE"),
                    PlanPhase(id=phid, plan_id=plid, phase_key="F0", title="Faza 0", sequence=0),
                    PlanItem(id=itid, plan_phase_id=phid, item_key="FLOW-102", title="Test"),
                ]
            )
            db.flush()
            now = datetime.now(tz=UTC)
            db.add_all(
                [
                    AgentSession(
                        id=sid,
                        project_id=pid,
                        plan_item_id=itid,
                        agent_type="cc",
                        repo_path="/tmp/test",
                        status="COMPLETED",
                    ),
                    Conflict(
                        id=cid,
                        project_id=pid,
                        conflict_type="WRITE_WRITE",
                        conflict_level="CRITICAL",
                        description="Test conflict",
                        conflict_key=f"write_write::{pid}::unrelated/file.py",
                        file_path="unrelated/file.py",
                        status="OPEN",
                        evidence_json="{}",
                        first_seen_at=now,
                        last_seen_at=now,
                        occurrence_count=1,
                    ),
                ]
            )
            db.commit()

            svc = EvidenceService(db)
            bundle = svc.build(itid)
            assert bundle is not None
            assert "unrelated/file.py" not in str(bundle.conflict_ids)
        finally:
            db.rollback()
            db.close()

    def test_evidence_bundle_handles_multiple_sessions(self, engine):
        import uuid
        from datetime import UTC, datetime

        from flowos.service.services.infrastructure.persistence.models import (
            AgentSession,
            Project,
        )
        from flowos.service.services.infrastructure.persistence.plan_models import (
            Plan,
            PlanItem,
            PlanPhase,
        )

        pid, plid, phid, itid, oid, nid = (str(uuid.uuid4()) for _ in range(6))
        db = Session(engine)
        try:
            db.add_all(
                [
                    Project(id=pid, name="Test", repo_path="/tmp/test"),
                    Plan(id=plid, project_id=pid, title="Test Plan", status="ACTIVE"),
                    PlanPhase(id=phid, plan_id=plid, phase_key="F0", title="Faza 0", sequence=0),
                    PlanItem(id=itid, plan_phase_id=phid, item_key="FLOW-103", title="Test"),
                ]
            )
            db.flush()
            db.add_all(
                [
                    AgentSession(
                        id=oid,
                        project_id=pid,
                        plan_item_id=itid,
                        agent_type="cc",
                        repo_path="/tmp/test",
                        status="COMPLETED",
                        started_at=datetime(2026, 1, 1, tzinfo=UTC),
                    ),
                    AgentSession(
                        id=nid,
                        project_id=pid,
                        plan_item_id=itid,
                        agent_type="pi",
                        repo_path="/tmp/test",
                        status="COMPLETED",
                        started_at=datetime(2026, 6, 1, tzinfo=UTC),
                    ),
                ]
            )
            db.commit()

            svc = EvidenceService(db)
            bundle = svc.build(itid)
            assert bundle is not None
            assert bundle.primary_session_id == nid
            assert bundle.agent_type == "pi"
        finally:
            db.rollback()
            db.close()
