"""PlanProgressService — centralna validacija statusnih tranzicija plana.

Odgovornosti:
- Validacija dozvoljenih prelaza između statusa
- Zabrana cikličnih zavisnosti
- Audit svake promene statusa (PlanProgressEvent)
- Izvođenje statusa faze iz statusa njenih stavki
"""

from collections import deque
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from flowos.service.services.infrastructure.persistence.plan_models import (
    PlanItem,
    PlanItemDependency,
    PlanProgressEvent,
)

# ═══════════════════════════════════════════════════════════════════
# Matrica dozvoljenih tranzicija
# ═══════════════════════════════════════════════════════════════════

# format: from_status → set(to_status)
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "NOT_STARTED": {"IN_PROGRESS", "BLOCKED"},
    "IN_PROGRESS": {"IMPLEMENTED", "BLOCKED"},
    "IMPLEMENTED": {"VERIFIED", "BLOCKED"},
    "VERIFIED": {"ACCEPTED", "REJECTED", "BLOCKED"},
    "ACCEPTED": set(),  # Krajnji status, ne menja se
    "REJECTED": {"NOT_STARTED", "BLOCKED"},  # Ponovo otvaranje
    "BLOCKED": {"IN_PROGRESS", "NOT_STARTED", "IMPLEMENTED"},  # Deblokada
}

# Koji statusi zahtevaju timestamp ažuriranje
STATUS_TIMESTAMP_FIELDS: dict[str, str] = {
    "IN_PROGRESS": "started_at",
    "IMPLEMENTED": "implemented_at",
    "VERIFIED": "verified_at",
    "ACCEPTED": "accepted_at",
}

ALL_STATUSES = {
    "NOT_STARTED",
    "IN_PROGRESS",
    "BLOCKED",
    "IMPLEMENTED",
    "VERIFIED",
    "ACCEPTED",
    "REJECTED",
}
DEPENDENCY_TYPES = {"BLOCKS_START", "BLOCKS_VERIFICATION", "INFORMATIONAL"}


class PlanProgressError(ValueError):
    """Neispravna statusna tranzicija."""


class CyclicDependencyError(ValueError):
    """Ciklična zavisnost između PlanItem-a."""


class PlanProgressService:
    """Centralna validacija i audit za statusne promene plana."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Validacija tranzicije ────────────────────────────

    @staticmethod
    def is_transition_allowed(from_status: str, to_status: str) -> bool:
        """Proverava da li je tranzicija dozvoljena."""
        if from_status not in ALL_STATUSES or to_status not in ALL_STATUSES:
            return False
        return to_status in ALLOWED_TRANSITIONS.get(from_status, set())

    def validate_transition(
        self, item: PlanItem, to_status: str, *, reason: str | None = None
    ) -> None:
        """Validira i izvršava statusnu tranziciju sa auditom.

        Raises:
            PlanProgressError: ako tranzicija nije dozvoljena.
        """
        from_status = item.status

        if not self.is_transition_allowed(from_status, to_status):
            raise PlanProgressError(
                f"Tranzicija {from_status} → {to_status} nije dozvoljena. "
                f"Dozvoljeni prelazi: {ALLOWED_TRANSITIONS.get(from_status, set())}"
            )

        # Posebna pravila
        if to_status == "IN_PROGRESS" and from_status == "NOT_STARTED":
            self._check_blocking_dependencies(item)

        # Ažuriraj timestamp ako je primenjivo
        timestamp_field = STATUS_TIMESTAMP_FIELDS.get(to_status)
        if timestamp_field:
            setattr(item, timestamp_field, datetime.now(tz=UTC))

        # Ažuriraj status
        old_status = item.status
        item.status = to_status
        item.updated_at = datetime.now(tz=UTC)

        # Audit događaj
        event = PlanProgressEvent(
            plan_item_id=item.id,
            from_status=old_status,
            to_status=to_status,
            reason=reason,
            source="SYSTEM",
        )
        self._session.add(event)

    # ── Blokirajuće zavisnosti ──────────────────────────

    def _check_blocking_dependencies(self, item: PlanItem) -> None:
        """Proverava da li postoje nezavršene BLOCKS_START zavisnosti."""
        deps = (
            self._session.query(PlanItemDependency)
            .filter(
                PlanItemDependency.plan_item_id == item.id,
                PlanItemDependency.dependency_type == "BLOCKS_START",
            )
            .all()
        )

        for dep in deps:
            dep_item = self._session.get(PlanItem, dep.depends_on_plan_item_id)
            if dep_item and dep_item.status not in ("ACCEPTED", "VERIFIED"):
                raise PlanProgressError(
                    f"Stavka '{item.item_key}' ne može početi dok "
                    f"'{dep_item.item_key}' nije završen (status={dep_item.status}). "
                    f"Zavisnost: BLOCKS_START"
                )

    # ── Ciklične zavisnosti ──────────────────────────────

    def check_cycle(self, item_id: str, depends_on_id: str) -> None:
        """Proverava da li dodavanje zavisnosti stvara ciklus.

        Raises:
            CyclicDependencyError: ako bi nastao ciklus.
        """
        if item_id == depends_on_id:
            raise CyclicDependencyError("Stavka ne može zavisiti od same sebe.")

        # BFS od depends_on_id — ako dođemo do item_id, ciklus
        visited: set[str] = set()
        queue: deque[str] = deque([depends_on_id])

        while queue:
            current = queue.popleft()
            if current == item_id:
                raise CyclicDependencyError(
                    f"Dodavanje zavisnosti {item_id} → {depends_on_id} stvara cikličnu zavisnost."
                )
            if current in visited:
                continue
            visited.add(current)

            deps = (
                self._session.query(PlanItemDependency)
                .filter(PlanItemDependency.plan_item_id == current)
                .all()
            )
            for dep in deps:
                if dep.depends_on_plan_item_id not in visited:
                    queue.append(dep.depends_on_plan_item_id)

    # ── Izvođenje statusa faze ───────────────────────────

    @staticmethod
    def derive_phase_status(items: list[PlanItem]) -> str:
        """Izračunava status faze iz statusa njenih stavki.

        Pravila:
        - Ako su sve ACCEPTED → ACCEPTED
        - Ako je bilo koja IN_PROGRESS → IN_PROGRESS
        - Ako su sve NOT_STARTED → NOT_STARTED
        - Ako je bilo koja BLOCKED → BLOCKED
        - Ako su sve IMPLEMENTED ili bolje → IMPLEMENTED
        - Ako su sve VERIFIED ili ACCEPTED → VERIFIED
        - Inače → NOT_STARTED (mešano stanje)
        """
        if not items:
            return "NOT_STARTED"

        statuses = {i.status for i in items}

        if statuses == {"ACCEPTED"}:
            return "ACCEPTED"
        if "IN_PROGRESS" in statuses:
            return "IN_PROGRESS"
        if "BLOCKED" in statuses:
            return "BLOCKED"
        if statuses.issubset({"NOT_STARTED"}):
            return "NOT_STARTED"
        if statuses.issubset({"VERIFIED", "ACCEPTED"}):
            return "VERIFIED"
        if statuses.issubset({"IMPLEMENTED", "VERIFIED", "ACCEPTED"}):
            return "IMPLEMENTED"

        return "NOT_STARTED"

    # ── Validacija dependency_type ───────────────────────

    @staticmethod
    def is_valid_dependency_type(dep_type: str) -> bool:
        return dep_type in DEPENDENCY_TYPES

    @staticmethod
    def is_valid_status(status: str) -> bool:
        return status in ALL_STATUSES

    # ── Query metodi za API kontrolere ─────────────────

    def get_project_plan_progress(self, project_id: str) -> dict:
        """Vraća sažetak napretka za projekat (za API)."""
        from flowos.service.services.infrastructure.persistence.plan_models import (
            Plan,
            PlanItem,
            PlanPhase,
        )

        plan = (
            self._session.query(Plan)
            .filter(Plan.project_id == project_id, Plan.status.in_(("ACTIVE", "DRAFT")))
            .order_by(Plan.created_at.desc())
            .first()
        )

        if not plan:
            return {"plan": None, "phases": [], "total_items": 0, "completed_items": 0, "blocked_items": 0}

        phases = (
            self._session.query(PlanPhase)
            .filter(PlanPhase.plan_id == plan.id)
            .order_by(PlanPhase.sequence)
            .all()
        )

        total = 0
        completed = 0
        blocked = 0
        phase_dicts = []
        for phase in phases:
            items = (
                self._session.query(PlanItem)
                .filter(PlanItem.plan_phase_id == phase.id)
                .order_by(PlanItem.sequence)
                .all()
            )
            total += len(items)
            completed += sum(1 for i in items if i.status == "ACCEPTED")
            blocked += sum(1 for i in items if i.status == "BLOCKED")
            phase.status = self.derive_phase_status(items)
            phase_dicts.append({
                "id": phase.id, "plan_id": phase.plan_id, "phase_key": phase.phase_key,
                "title": phase.title, "sequence": phase.sequence, "status": phase.status,
            })

        return {
            "plan": {
                "id": plan.id, "project_id": plan.project_id, "title": plan.title,
                "status": plan.status,
                "activated_at": plan.activated_at.isoformat() if plan.activated_at else None,
                "created_at": plan.created_at.isoformat() if plan.created_at else None,
            },
            "phases": phase_dicts,
            "total_items": total,
            "completed_items": completed,
            "blocked_items": blocked,
        }

    def list_plan_items_grouped(self, plan_id: str) -> list[dict]:
        from flowos.service.services.infrastructure.persistence.plan_models import (
            Plan,
            PlanItem,
            PlanPhase,
        )

        plan = self._session.get(Plan, plan_id)
        if not plan:
            return []
        phases = (
            self._session.query(PlanPhase)
            .filter(PlanPhase.plan_id == plan_id)
            .order_by(PlanPhase.sequence)
            .all()
        )
        result = []
        for phase in phases:
            items = (
                self._session.query(PlanItem)
                .filter(PlanItem.plan_phase_id == phase.id)
                .order_by(PlanItem.sequence)
                .all()
            )
            result.append({
                "phase": {"id": phase.id, "plan_id": phase.plan_id, "phase_key": phase.phase_key,
                           "title": phase.title, "sequence": phase.sequence, "status": phase.status},
                "items": [_item_to_dict(i) for i in items],
            })
        return result

    def get_plan_item(self, item_id: str):
        from flowos.service.services.infrastructure.persistence.plan_models import PlanItem
        return self._session.get(PlanItem, item_id)

    def update_plan_item(self, item_id: str, data: dict):
        from flowos.service.services.infrastructure.persistence.plan_models import PlanItem
        item = self._session.get(PlanItem, item_id)
        if not item:
            return None
        allowed = {"title", "description", "risk_level"}
        for key, value in data.items():
            if key in allowed and value is not None:
                setattr(item, key, value)
        return item

    def get_item_criteria(self, item_id: str) -> list:
        from flowos.service.services.infrastructure.persistence.plan_models import (
            PlanItemCriterion,
        )
        return (
            self._session.query(PlanItemCriterion)
            .filter(PlanItemCriterion.plan_item_id == item_id)
            .all()
        )

    def update_criterion(self, criterion_id: str, data: dict):
        from flowos.service.services.infrastructure.persistence.plan_models import (
            PlanItemCriterion,
        )
        criterion = self._session.get(PlanItemCriterion, criterion_id)
        if not criterion:
            return None
        allowed = {"status", "evidence_artifact_id", "verification_summary", "verified_by"}
        for key, value in data.items():
            if key in allowed:
                setattr(criterion, key, value)
        return criterion

    def get_progress_events(self, item_id: str, limit: int = 50) -> list:
        from flowos.service.services.infrastructure.persistence.plan_models import (
            PlanProgressEvent,
        )
        return (
            self._session.query(PlanProgressEvent)
            .filter(PlanProgressEvent.plan_item_id == item_id)
            .order_by(PlanProgressEvent.occurred_at.desc())
            .limit(limit)
            .all()
        )

    def import_plan(self, project_id: str, markdown: str, source_artifact_id: str | None = None) -> tuple[dict, str | None]:
        from flowos.service.services.plan_import import PlanImportService
        svc = PlanImportService(self._session)
        result = svc.import_plan(project_id, markdown, source_artifact_id=source_artifact_id)
        from flowos.service.services.infrastructure.persistence.plan_models import Plan
        plan = (
            self._session.query(Plan)
            .filter(Plan.project_id == project_id, Plan.status == "DRAFT")
            .order_by(Plan.created_at.desc())
            .first()
        )
        plan_id = plan.id if plan else None
        return {
            "plan_id": plan_id or "",
            "phases": result.stats["phases"],
            "items": result.stats["items"],
            "criteria": result.stats["criteria"],
            "dependencies": result.stats["dependencies"],
            "unclear_count": result.stats["unclear"],
            "unclear_sections": result.unclear_sections,
        }, plan_id

    def activate_plan(self, plan_id: str) -> dict:
        from flowos.service.services.infrastructure.persistence.plan_models import Plan
        plan = self._session.get(Plan, plan_id)
        if not plan:
            return None
        if plan.status != "DRAFT":
            return {"error": f"Plan nije u DRAFT statusu (trenutno: {plan.status})"}
        from datetime import UTC, datetime
        # Deaktiviraj prethodni aktivni plan
        prev = (
            self._session.query(Plan)
            .filter(Plan.project_id == plan.project_id, Plan.status == "ACTIVE")
            .first()
        )
        if prev:
            prev.status = "SUPERSEDED"
        plan.status = "ACTIVE"
        plan.activated_at = datetime.now(tz=UTC)
        return {"plan_id": plan.id, "status": "ACTIVE", "activated_at": plan.activated_at.isoformat()}

# ═══════════════════════════════════════════════════════════════════
# Helper funkcije za serijalizaciju (koriste ih API kontroleri)
# ═══════════════════════════════════════════════════════════════════

def _item_to_dict(item) -> dict:
    return {
        "id": item.id, "plan_phase_id": item.plan_phase_id,
        "item_key": item.item_key, "title": item.title,
        "description": item.description, "sequence": item.sequence,
        "risk_level": item.risk_level, "status": item.status,
        "progress_source": item.progress_source,
        "started_at": item.started_at.isoformat() if item.started_at else None,
        "implemented_at": item.implemented_at.isoformat() if item.implemented_at else None,
        "verified_at": item.verified_at.isoformat() if item.verified_at else None,
        "accepted_at": item.accepted_at.isoformat() if item.accepted_at else None,
        "blocked_reason": item.blocked_reason,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }

def _criterion_to_dict(c) -> dict:
    return {
        "id": c.id, "plan_item_id": c.plan_item_id,
        "criterion_key": c.criterion_key, "description": c.description,
        "status": c.status, "evidence_artifact_id": c.evidence_artifact_id,
        "verification_summary": c.verification_summary,
        "verified_at": c.verified_at.isoformat() if c.verified_at else None,
        "verified_by": c.verified_by,
    }

def _event_to_dict(e) -> dict:
    return {
        "id": e.id, "plan_item_id": e.plan_item_id,
        "session_id": e.session_id, "agent_report_id": e.agent_report_id,
        "from_status": e.from_status, "to_status": e.to_status,
        "reason": e.reason, "evidence_artifact_ids_json": e.evidence_artifact_ids_json,
        "source": e.source,
        "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
    }
