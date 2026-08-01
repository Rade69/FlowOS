"""Testovi za PlanMarkdownParser i PlanImportService.

Koristi stvarne isečke FlowOS v2 plana za testiranje parsiranja.
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from flowos.service.services.infrastructure.persistence.base import Base
from flowos.service.services.infrastructure.persistence.models import Project
from flowos.service.services.plan_import import (
    ImportResult,
    PlanImportService,
    PlanMarkdownParser,
)

# ═══════════════════════════════════════════════════════════════════
# Test isečci iz stvarnog FlowOS plana
# ═══════════════════════════════════════════════════════════════════

SAMPLE_PLAN = """# FlowOS — test plan

## Faza 0 — Validacija i bootstrap

### Cilj

Potvrditi ključne tehničke nepoznanice.

### Zadaci

#### FLOW-000 — Bootstrap repozitorija

**Rizik:** HIGH, jer postavlja arhitekturu i radna pravila.

Obavezno:

1. `git status --short`;
2. kreirati `project_rooms`;
3. kreirati minimalni `pyproject.toml`;

**Ne raditi:** GUI funkcionalnost, bazu, watcher.

**Dokaz:** čist import skeleton, verify prolazi.

#### FLOW-004 — Dnevnik stvarnih sesija

**Rizik:** LOW

Korisnik i agent evidentiraju najmanje 10 stvarnih sesija.

**Dokaz:** 10 sesija mapirano.

## Faza 1 — Temelj i prvi vertikalni tok

### Cilj

Pokrenuti servis i GUI.

### Zadaci

#### FLOW-101 — Shared contracts i error model

**Rizik:** MEDIUM

DTO za Project, Task, Session.

Završiti FLOW-000 prije FLOW-101.

**Dokaz:** unit testovi validacije prolaze.

#### FLOW-102 — SQLite i migracije

**Rizik:** MEDIUM

SQLAlchemy setup, WAL, FK.

**Dokaz:** temp DB testovi prolaze.
"""


# ═══════════════════════════════════════════════════════════════════
# Parser testovi
# ═══════════════════════════════════════════════════════════════════


class TestPlanMarkdownParser:
    @pytest.fixture
    def parser(self):
        return PlanMarkdownParser()

    @pytest.fixture
    def result(self, parser):
        return parser.parse(SAMPLE_PLAN)

    def test_title_extracted(self, result: ImportResult):
        assert result.title == "FlowOS — test plan"

    def test_two_phases(self, result: ImportResult):
        assert len(result.phases) == 2
        assert result.phases[0].phase_key == "F0"
        assert result.phases[1].phase_key == "F1"

    def test_phase_zero_items(self, result: ImportResult):
        f0 = result.phases[0]
        assert len(f0.items) == 2
        assert f0.items[0].item_key == "FLOW-000"
        assert f0.items[0].title == "Bootstrap repozitorija"
        assert f0.items[1].item_key == "FLOW-004"
        assert f0.items[1].title == "Dnevnik stvarnih sesija"

    def test_phase_one_items(self, result: ImportResult):
        f1 = result.phases[1]
        assert len(f1.items) == 2
        assert f1.items[0].item_key == "FLOW-101"
        assert f1.items[1].item_key == "FLOW-102"

    def test_risk_levels(self, result: ImportResult):
        f0 = result.phases[0]
        assert f0.items[0].risk_level == "HIGH"
        assert f0.items[1].risk_level == "LOW"

        f1 = result.phases[1]
        assert f1.items[0].risk_level == "MEDIUM"
        assert f1.items[1].risk_level == "MEDIUM"

    def test_criteria_extraction(self, result: ImportResult):
        """FLOW-000 treba da ima kriterijume iz Obavezno + Dokaz + Ne raditi."""
        flow_000 = result.phases[0].items[0]
        assert len(flow_000.criteria) >= 2

        # **Dokaz:** → DOKAZ
        dokaz_keys = [c.key for c in flow_000.criteria]
        assert "DOKAZ" in dokaz_keys

        # **Ne raditi:** → OUT_OF_SCOPE
        assert "OUT_OF_SCOPE" in dokaz_keys

    def test_dependency_extraction(self, result: ImportResult):
        """FLOW-101 treba da ima BLOCKS_START zavisnost od FLOW-000."""
        flow_101 = result.phases[1].items[0]
        blocking_deps = [d for d in flow_101.dependencies if d.dependency_type == "BLOCKS_START"]
        assert len(blocking_deps) >= 1
        assert blocking_deps[0].depends_on_key == "FLOW-000"

    def test_description_not_empty(self, result: ImportResult):
        for phase in result.phases:
            for item in phase.items:
                assert item.description, f"{item.item_key} nema opis"

    def test_stats(self, result: ImportResult):
        stats = result.stats
        assert stats["phases"] == 2
        assert stats["items"] == 4
        assert stats["criteria"] > 0


# ═══════════════════════════════════════════════════════════════════
# Edge case testovi
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    @pytest.fixture
    def parser(self):
        return PlanMarkdownParser()

    def test_empty_plan(self, parser):
        result = parser.parse("# Empty Plan\n\nNo content.")
        assert result.title == "Empty Plan"
        assert len(result.phases) == 0

    def test_no_flow_items(self, parser):
        result = parser.parse("## Faza 1 — Test\n\nNema FLOW stavki.")
        assert len(result.phases) == 1
        assert len(result.phases[0].items) == 0

    def test_default_risk_is_medium(self, parser):
        result = parser.parse("## Faza 1 — Test\n\n#### FLOW-001 — Bez rizika\n\nNema **Rizik:**.")
        assert result.phases[0].items[0].risk_level == "MEDIUM"

    def test_ignore_non_phase_headings(self, parser):
        result = parser.parse(
            "## Arhitektura\n\nOvo nije faza.\n\n## Faza 1 — Prava faza\n\n#### FLOW-001 — Test"
        )
        # "Arhitektura" nije faza heading → treba da ode u unclear ili se ignoriše
        phases = list(result.phases)
        assert len(phases) >= 1
        assert phases[-1].phase_key == "F1"

    def test_nested_flow_items(self, parser):
        """FLOW stavke treba da pripadaju fazi u kojoj su definisane."""
        result = parser.parse(
            "## Faza 0 — Validacija\n\n#### FLOW-000 — Bootstrap\n\n"
            "## Faza 1 — Temelj\n\n#### FLOW-101 — Contracts\n\n#### FLOW-102 — SQLite"
        )
        assert len(result.phases) == 2
        assert len(result.phases[0].items) == 1  # FLOW-000
        assert len(result.phases[1].items) == 2  # FLOW-101, FLOW-102

    def test_flow_with_suffix(self, parser):
        """FLOW-103A, FLOW-105A sa slovnim sufiksom."""
        result = parser.parse(
            "## Faza 1 — Test\n\n#### FLOW-103A — Plan model\n\nOpis.\n\n#### FLOW-105A — GUI skeleton"
        )
        assert result.phases[0].items[0].item_key == "FLOW-103A"
        assert result.phases[0].items[1].item_key == "FLOW-105A"


# ═══════════════════════════════════════════════════════════════════
# PlanImportService integracioni test
# ═══════════════════════════════════════════════════════════════════


class TestPlanImportService:
    @pytest.fixture
    def engine(self):
        eng = create_engine("sqlite://", echo=False)

        @event.listens_for(eng, "connect")
        def _pragma(dbapi_connection, connection_record):  # noqa: ARG001
            c = dbapi_connection.cursor()
            c.execute("PRAGMA journal_mode=WAL;")
            c.execute("PRAGMA foreign_keys=ON;")
            c.close()

        import flowos.service.services.infrastructure.persistence.models  # noqa: F401
        import flowos.service.services.infrastructure.persistence.plan_models  # noqa: F401

        Base.metadata.create_all(eng)
        yield eng
        Base.metadata.drop_all(eng)
        eng.dispose()

    @pytest.fixture
    def session(self, engine):
        SessionLocal = sessionmaker(bind=engine)
        with SessionLocal() as s:
            yield s

    def test_import_creates_draft_plan(self, session: Session):
        project = Project(name="Test", repo_path="C:/test")
        session.add(project)
        session.commit()

        svc = PlanImportService(session)
        result = svc.import_plan(project.id, SAMPLE_PLAN)

        # Provera rezultata
        assert result.stats["phases"] == 2
        assert result.stats["items"] == 4

        # Provera da je Plan kreiran u bazi
        from flowos.service.services.infrastructure.persistence.plan_models import (
            Plan,
            PlanItem,
            PlanItemCriterion,
            PlanItemDependency,
            PlanPhase,
        )

        plans = session.query(Plan).filter(Plan.project_id == project.id).all()
        assert len(plans) == 1
        assert plans[0].status == "DRAFT"

        # Faze
        phases = (
            session.query(PlanPhase)
            .filter(PlanPhase.plan_id == plans[0].id)
            .order_by(PlanPhase.sequence)
            .all()
        )
        assert len(phases) == 2
        assert phases[0].phase_key == "F0"
        assert phases[1].phase_key == "F1"

        # Stavke
        items = (
            session.query(PlanItem)
            .filter(PlanItem.plan_phase_id == phases[0].id)
            .order_by(PlanItem.sequence)
            .all()
        )
        assert len(items) == 2
        assert items[0].item_key == "FLOW-000"
        assert items[0].risk_level == "HIGH"

        # Kriterijumi
        criteria = (
            session.query(PlanItemCriterion)
            .filter(PlanItemCriterion.plan_item_id == items[0].id)
            .all()
        )
        assert len(criteria) >= 2

        # Zavisnosti — FLOW-101 zavisi od FLOW-000
        flow_101 = session.query(PlanItem).filter(PlanItem.item_key == "FLOW-101").first()
        deps = (
            session.query(PlanItemDependency)
            .filter(PlanItemDependency.plan_item_id == flow_101.id)
            .all()
        )
        blocking = [d for d in deps if d.dependency_type == "BLOCKS_START"]
        assert len(blocking) >= 1

    def test_import_preserves_original_text(self, session: Session):
        """Opis stavke treba da sadrži originalni Markdown tekst."""
        project = Project(name="Test", repo_path="C:/test")
        session.add(project)
        session.commit()

        svc = PlanImportService(session)
        svc.import_plan(project.id, SAMPLE_PLAN)

        from flowos.service.services.infrastructure.persistence.plan_models import PlanItem

        flow_000 = session.query(PlanItem).filter(PlanItem.item_key == "FLOW-000").first()
        assert flow_000 is not None
        assert "git status --short" in flow_000.description
        assert "GUI funkcionalnost" in flow_000.description
