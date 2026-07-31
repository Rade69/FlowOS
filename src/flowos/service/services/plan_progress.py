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
        if statuses.issubset({"IMPLEMENTED", "VERIFIED", "ACCEPTED"}):
            return "IMPLEMENTED"
        if statuses.issubset({"VERIFIED", "ACCEPTED"}):
            return "VERIFIED"

        return "NOT_STARTED"

    # ── Validacija dependency_type ───────────────────────

    @staticmethod
    def is_valid_dependency_type(dep_type: str) -> bool:
        return dep_type in DEPENDENCY_TYPES

    @staticmethod
    def is_valid_status(status: str) -> bool:
        return status in ALL_STATUSES
