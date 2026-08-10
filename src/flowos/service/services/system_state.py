"""SystemStateService — read-only sistemski upiti za HTTP system rute."""

from sqlalchemy.orm import Session

from flowos.service.services.infrastructure.persistence.models import AgentSession
from flowos.shared.enums.session import SessionStatus


class SystemStateService:
    """Čuva persistence detalje izvan system controllera."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def count_active_sessions(self) -> int:
        return (
            self._db.query(AgentSession)
            .filter(AgentSession.status.in_((SessionStatus.ACTIVE.value, SessionStatus.IDLE.value)))
            .count()
        )
