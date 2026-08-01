"""Testovi za PlanProgressService — statusne tranzicije, zavisnosti, ciklusi."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.plan_models import (
    Plan,
    PlanItem,
    PlanItemDependency,
    PlanPhase,
    PlanProgressEvent,
)
from flowos.service.services.plan_progress import (
    CyclicDependencyError,
    PlanProgressError,
    PlanProgressService,
)


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", echo=False)

    @event.listens_for(eng, "connect")
    def _pragma(dbapi_connection, connection_record):  # noqa: ARG001
        c = dbapi_connection.cursor()
        c.execute("PRAGMA journal_mode=WAL;")
        c.execute("PRAGMA foreign_keys=ON;")
        c.close()

    # Uvezi sve modele pre create_all
    import flowos.service.services.infrastructure.persistence.models  # noqa: F401
    import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401

    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def session(engine):
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as s:
        yield s


@pytest.fixture
def plan_and_phase(session: Session):
    """Kreira Plan i PlanPhase za testove."""
    from flowos.service.services.infrastructure.persistence.models import Project

    project = Project(name="Test", repo_path="C:/test")
    session.add(project)
    session.flush()

    plan = Plan(project_id=project.id, title="Test Plan", status="ACTIVE")
    session.add(plan)
    session.flush()

    phase = PlanPhase(plan_id=plan.id, phase_key="F0", title="Faza 0", sequence=0)
    session.add(phase)
    session.flush()

    session.commit()
    return plan, phase


@pytest.fixture
def svc(session: Session):
    return PlanProgressService(session)


# ═══════════════════════════════════════════════════════════════════
# Matrica tranzicija
# ═══════════════════════════════════════════════════════════════════


class TestTransitionMatrix:
    def test_allowed_not_started_to_in_progress(self):
        assert PlanProgressService.is_transition_allowed("NOT_STARTED", "IN_PROGRESS")

    def test_allowed_not_started_to_blocked(self):
        assert PlanProgressService.is_transition_allowed("NOT_STARTED", "BLOCKED")

    def test_allowed_in_progress_to_implemented(self):
        assert PlanProgressService.is_transition_allowed("IN_PROGRESS", "IMPLEMENTED")

    def test_allowed_implemented_to_verified(self):
        assert PlanProgressService.is_transition_allowed("IMPLEMENTED", "VERIFIED")

    def test_allowed_verified_to_accepted(self):
        assert PlanProgressService.is_transition_allowed("VERIFIED", "ACCEPTED")

    def test_allowed_verified_to_rejected(self):
        assert PlanProgressService.is_transition_allowed("VERIFIED", "REJECTED")

    def test_allowed_blocked_to_in_progress(self):
        assert PlanProgressService.is_transition_allowed("BLOCKED", "IN_PROGRESS")

    def test_allowed_rejected_to_not_started(self):
        assert PlanProgressService.is_transition_allowed("REJECTED", "NOT_STARTED")

    def test_forbidden_accepted_to_anything(self):
        assert not PlanProgressService.is_transition_allowed("ACCEPTED", "IN_PROGRESS")
        assert not PlanProgressService.is_transition_allowed("ACCEPTED", "BLOCKED")

    def test_forbidden_not_started_to_accepted(self):
        assert not PlanProgressService.is_transition_allowed("NOT_STARTED", "ACCEPTED")

    def test_forbidden_in_progress_to_accepted(self):
        assert not PlanProgressService.is_transition_allowed("IN_PROGRESS", "ACCEPTED")

    def test_invalid_statuses(self):
        assert not PlanProgressService.is_transition_allowed("NEPOSTOJECI", "IN_PROGRESS")
        assert not PlanProgressService.is_transition_allowed("IN_PROGRESS", "NEPOSTOJECI")


# ═══════════════════════════════════════════════════════════════════
# Tranzicije sa auditom
# ═══════════════════════════════════════════════════════════════════


class TestTransitionWithAudit:
    def test_simple_transition(self, plan_and_phase, svc: PlanProgressService, session: Session):
        _, phase = plan_and_phase
        item = PlanItem(
            plan_phase_id=phase.id, item_key="FLOW-001", title="Test", status="NOT_STARTED"
        )
        session.add(item)
        session.commit()

        svc.validate_transition(item, "IN_PROGRESS", reason="Počinje sesija")
        session.commit()

        assert item.status == "IN_PROGRESS"
        assert item.started_at is not None

        # Audit događaj
        events = (
            session.query(PlanProgressEvent).filter(PlanProgressEvent.plan_item_id == item.id).all()
        )
        assert len(events) == 1
        assert events[0].from_status == "NOT_STARTED"
        assert events[0].to_status == "IN_PROGRESS"
        assert events[0].reason == "Počinje sesija"

    def test_invalid_transition_raises(
        self, plan_and_phase, svc: PlanProgressService, session: Session
    ):
        _, phase = plan_and_phase
        item = PlanItem(
            plan_phase_id=phase.id, item_key="FLOW-001", title="Test", status="NOT_STARTED"
        )
        session.add(item)
        session.commit()

        with pytest.raises(PlanProgressError, match="nije dozvoljena"):
            svc.validate_transition(item, "ACCEPTED")

        # Status NIJE promenjen
        session.refresh(item)
        assert item.status == "NOT_STARTED"

    def test_full_happy_path(self, plan_and_phase, svc: PlanProgressService, session: Session):
        """NOT_STARTED → IN_PROGRESS → IMPLEMENTED → VERIFIED → ACCEPTED."""
        _, phase = plan_and_phase
        item = PlanItem(plan_phase_id=phase.id, item_key="FLOW-042", title="Full test")
        session.add(item)
        session.commit()

        path = [
            ("IN_PROGRESS", "Sesija FLOW-042"),
            ("IMPLEMENTED", "Agent završio"),
            ("VERIFIED", "Testovi prolaze"),
            ("ACCEPTED", "Korisnik potvrdio"),
        ]

        for to_status, reason in path:
            svc.validate_transition(item, to_status, reason=reason)
            session.commit()

        assert item.status == "ACCEPTED"
        assert item.accepted_at is not None

        events = (
            session.query(PlanProgressEvent).filter(PlanProgressEvent.plan_item_id == item.id).all()
        )
        assert len(events) == 4

    def test_block_unblock(self, plan_and_phase, svc: PlanProgressService, session: Session):
        _, phase = plan_and_phase
        item = PlanItem(plan_phase_id=phase.id, item_key="FLOW-BLK", title="Test")
        session.add(item)
        session.commit()

        svc.validate_transition(item, "IN_PROGRESS", reason="Start")
        session.commit()

        svc.validate_transition(item, "BLOCKED", reason="Problem sa zavisnošću")
        session.commit()
        assert item.status == "BLOCKED"
        assert item.blocked_reason is None  # reason je u eventu, ne na item-u

        svc.validate_transition(item, "IN_PROGRESS", reason="Deblokirano")
        session.commit()
        assert item.status == "IN_PROGRESS"


# ═══════════════════════════════════════════════════════════════════
# Zavisnosti
# ═══════════════════════════════════════════════════════════════════


class TestDependencies:
    def test_blocking_dependency_prevents_start(
        self, plan_and_phase, svc: PlanProgressService, session: Session
    ):
        _, phase = plan_and_phase
        dep = PlanItem(
            plan_phase_id=phase.id, item_key="FLOW-DEP", title="Dependency", status="NOT_STARTED"
        )
        item = PlanItem(plan_phase_id=phase.id, item_key="FLOW-MAIN", title="Main")
        session.add_all([dep, item])
        session.flush()

        # MAIN zavisi od DEP sa BLOCKS_START
        d = PlanItemDependency(
            plan_item_id=item.id,
            depends_on_plan_item_id=dep.id,
            dependency_type="BLOCKS_START",
        )
        session.add(d)
        session.commit()

        # Treba da padne — DEP nije završen
        with pytest.raises(PlanProgressError, match="ne može početi dok"):
            svc.validate_transition(item, "IN_PROGRESS")

    def test_blocking_dependency_allows_when_done(
        self, plan_and_phase, svc: PlanProgressService, session: Session
    ):
        _, phase = plan_and_phase
        dep = PlanItem(
            plan_phase_id=phase.id, item_key="FLOW-DEP", title="Dependency", status="ACCEPTED"
        )
        item = PlanItem(plan_phase_id=phase.id, item_key="FLOW-MAIN", title="Main")
        session.add_all([dep, item])
        session.flush()

        d = PlanItemDependency(
            plan_item_id=item.id,
            depends_on_plan_item_id=dep.id,
            dependency_type="BLOCKS_START",
        )
        session.add(d)
        session.commit()

        # Treba da prođe — DEP je ACCEPTED
        svc.validate_transition(item, "IN_PROGRESS")
        session.commit()
        assert item.status == "IN_PROGRESS"

    def test_self_dependency_forbidden(self, plan_and_phase, svc: PlanProgressService):
        _, phase = plan_and_phase
        with pytest.raises(CyclicDependencyError, match="same sebe"):
            svc.check_cycle("id-1", "id-1")

    def test_cycle_detection_simple(
        self, plan_and_phase, svc: PlanProgressService, session: Session
    ):
        _, phase = plan_and_phase
        a = PlanItem(plan_phase_id=phase.id, item_key="FLOW-A", title="A")
        b = PlanItem(plan_phase_id=phase.id, item_key="FLOW-B", title="B")
        session.add_all([a, b])
        session.flush()

        # A → B
        session.add(PlanItemDependency(plan_item_id=a.id, depends_on_plan_item_id=b.id))
        session.commit()

        # Dodavanje B → A stvara ciklus
        with pytest.raises(CyclicDependencyError, match="cikličnu"):
            svc.check_cycle(b.id, a.id)

    def test_informational_dependency_does_not_block(
        self, plan_and_phase, svc: PlanProgressService, session: Session
    ):
        _, phase = plan_and_phase
        dep = PlanItem(
            plan_phase_id=phase.id, item_key="FLOW-INFO", title="Info Dep", status="NOT_STARTED"
        )
        item = PlanItem(plan_phase_id=phase.id, item_key="FLOW-MAIN", title="Main")
        session.add_all([dep, item])
        session.flush()

        d = PlanItemDependency(
            plan_item_id=item.id,
            depends_on_plan_item_id=dep.id,
            dependency_type="INFORMATIONAL",
        )
        session.add(d)
        session.commit()

        # Ne blokira — INFORMATIONAL
        svc.validate_transition(item, "IN_PROGRESS")
        session.commit()
        assert item.status == "IN_PROGRESS"


# ═══════════════════════════════════════════════════════════════════
# Izvođenje statusa faze
# ═══════════════════════════════════════════════════════════════════


class TestPhaseStatusDerivation:
    def test_all_not_started(self):
        items = [
            PlanItem(id="1", plan_phase_id="p", item_key="A", title="A", status="NOT_STARTED"),  # type: ignore[call-arg]
            PlanItem(id="2", plan_phase_id="p", item_key="B", title="B", status="NOT_STARTED"),  # type: ignore[call-arg]
        ]
        assert PlanProgressService.derive_phase_status(items) == "NOT_STARTED"

    def test_one_in_progress(self):
        items = [
            PlanItem(id="1", plan_phase_id="p", item_key="A", title="A", status="NOT_STARTED"),  # type: ignore[call-arg]
            PlanItem(id="2", plan_phase_id="p", item_key="B", title="B", status="IN_PROGRESS"),  # type: ignore[call-arg]
        ]
        assert PlanProgressService.derive_phase_status(items) == "IN_PROGRESS"

    def test_all_accepted(self):
        items = [
            PlanItem(id="1", plan_phase_id="p", item_key="A", title="A", status="ACCEPTED"),  # type: ignore[call-arg]
            PlanItem(id="2", plan_phase_id="p", item_key="B", title="B", status="ACCEPTED"),  # type: ignore[call-arg]
        ]
        assert PlanProgressService.derive_phase_status(items) == "ACCEPTED"

    def test_blocked_dominates(self):
        items = [
            PlanItem(id="1", plan_phase_id="p", item_key="A", title="A", status="VERIFIED"),  # type: ignore[call-arg]
            PlanItem(id="2", plan_phase_id="p", item_key="B", title="B", status="BLOCKED"),  # type: ignore[call-arg]
        ]
        assert PlanProgressService.derive_phase_status(items) == "BLOCKED"

    def test_empty_list(self):
        assert PlanProgressService.derive_phase_status([]) == "NOT_STARTED"

    def test_all_implemented_or_better(self):
        items = [
            PlanItem(id="1", plan_phase_id="p", item_key="A", title="A", status="IMPLEMENTED"),  # type: ignore[call-arg]
            PlanItem(id="2", plan_phase_id="p", item_key="B", title="B", status="VERIFIED"),  # type: ignore[call-arg]
        ]
        assert PlanProgressService.derive_phase_status(items) == "IMPLEMENTED"

    def test_mixed_verified_accepted(self):
        items = [
            PlanItem(id="1", plan_phase_id="p", item_key="A", title="A", status="VERIFIED"),  # type: ignore[call-arg]
            PlanItem(id="2", plan_phase_id="p", item_key="B", title="B", status="ACCEPTED"),  # type: ignore[call-arg]
        ]
        assert PlanProgressService.derive_phase_status(items) == "VERIFIED"


# ═══════════════════════════════════════════════════════════════════
# Validacije
# ═══════════════════════════════════════════════════════════════════


class TestValidations:
    def test_valid_dependency_types(self):
        assert PlanProgressService.is_valid_dependency_type("BLOCKS_START")
        assert PlanProgressService.is_valid_dependency_type("BLOCKS_VERIFICATION")
        assert PlanProgressService.is_valid_dependency_type("INFORMATIONAL")
        assert not PlanProgressService.is_valid_dependency_type("NEPOSTOJECI")

    def test_valid_statuses(self):
        for s in [
            "NOT_STARTED",
            "IN_PROGRESS",
            "BLOCKED",
            "IMPLEMENTED",
            "VERIFIED",
            "ACCEPTED",
            "REJECTED",
        ]:
            assert PlanProgressService.is_valid_status(s)
        assert not PlanProgressService.is_valid_status("DONE")
        assert not PlanProgressService.is_valid_status("NEPOSTOJECI")
