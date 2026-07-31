"""FlowOS vremenski utility.

Svi vremenski podaci čuvaju se u UTC, GUI prikazuje u lokalnom vremenu.
"""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Vraća trenutno vreme u UTC, timezone-aware."""
    return datetime.now(tz=UTC)
