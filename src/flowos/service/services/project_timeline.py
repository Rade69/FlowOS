"""ProjectTimelineService — objedinjeni timeline projekta iz trajnih izvora.

Controller drži tanku HTTP granicu, a ovaj servis spaja FileActivity i
SessionEvent preko stvarnog AgentSession.project_id odnosa.
"""

from sqlalchemy.orm import Session


class ProjectTimelineService:
    """Gradi timeline projekta bez fiktivnih SessionEvent.project_id polja."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_timeline(self, project_id: str, limit: int = 30) -> list[dict]:
        from flowos.service.services.activity.service import ActivityService
        from flowos.service.services.infrastructure.persistence.models import (
            AgentSession,
            SessionEvent,
        )

        items: list[dict] = []

        activity_svc = ActivityService(self._db)
        activities = activity_svc.get_project_activities(project_id, limit=limit)
        for activity in activities:
            items.append(
                {
                    "id": activity.event_id,
                    "type": "FILE",
                    "event": activity.event_type,
                    "file": activity.file_path or "",
                    "session_id": activity.session_id or "",
                    "attribution": activity.attribution_type,
                    "occurred_at": activity.occurred_at.isoformat() if activity.occurred_at else "",
                }
            )

        events = (
            self._db.query(SessionEvent)
            .join(AgentSession, AgentSession.id == SessionEvent.session_id)
            .filter(AgentSession.project_id == project_id)
            .order_by(SessionEvent.occurred_at.desc())
            .limit(limit)
            .all()
        )
        for event in events:
            items.append(
                {
                    "id": event.id,
                    "type": "SESSION",
                    "event": event.event_type,
                    "session_id": event.session_id or "",
                    "occurred_at": event.occurred_at.isoformat() if event.occurred_at else "",
                }
            )

        items.sort(key=lambda item: item.get("occurred_at", ""), reverse=True)
        return items[:limit]
