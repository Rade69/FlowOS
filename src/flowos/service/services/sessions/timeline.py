"""Timeline Service — agregacija i prikaz događaja sesije.

Timeline prikazuje poslovno relevantne događaje po tri nivoa:
1. SUMMARY — samo ključne prekretnice
2. TIMELINE — svi poslovno relevantni događaji
3. TECHNICAL — svi događaji uključujući sirove podatke

Objedinjuje izvore: SessionEvent, FileActivity, Conflict, Verification, AgentReport.
"""

from enum import StrEnum

from sqlalchemy.orm import Session

from flowos.service.services.infrastructure.persistence.activity_models import FileActivity
from flowos.service.services.infrastructure.persistence.conflict_models import Conflict
from flowos.service.services.infrastructure.persistence.models import SessionEvent
from flowos.service.services.infrastructure.persistence.report_models import AgentReport


class TimelineLevel(StrEnum):
    """Validni nivoi detalja za timeline."""

    SUMMARY = "summary"  # samo ključne prekretnice
    TIMELINE = "timeline"  # svi poslovno relevantni događaji
    TECHNICAL = "technical"  # svi događaji + sirovi detalji


class TimelineService:
    """Agregira događaje iz više izvora u strukturirani timeline."""

    SUMMARY_EVENTS = {"STARTED", "COMPLETED", "ABANDONED", "VERIFY_RESULT", "CHECKPOINT"}

    TIMELINE_EVENTS = {
        "STARTED",
        "COMPLETED",
        "ABANDONED",
        "VERIFY_RESULT",
        "CHECKPOINT",
        "COMMIT_OBSERVED",
        "CONFLICT_WARNING",
        "FILE_ACTIVITY",
        "GIT_SNAPSHOT",
        "NOTE",
    }

    MIN_PAGE = 1
    MIN_PAGE_SIZE = 1
    MAX_PAGE_SIZE = 200

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_timeline(
        self,
        session_id: str,
        *,
        level: str = "timeline",
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """Vraća paginirani timeline za sesiju.

        Args:
            session_id: ID sesije.
            level: Nivo detalja — summary, timeline, technical.
            page: Broj stranice (1-indeksirano, >= 1).
            page_size: Broj događaja po stranici (1-200).

        Returns:
            dict sa 'events', 'total', 'page', 'page_size', 'level'.

        Raises:
            ValueError: Ako je level, page ili page_size nevalidan.
        """
        # Validacija level-a
        try:
            timeline_level = TimelineLevel(level)
        except ValueError:
            raise ValueError(
                f"Nevalidan level: '{level}'. Dozvoljeni: {[lev.value for lev in TimelineLevel]}"
            ) from None

        # Validacija paginacije
        if page < self.MIN_PAGE:
            raise ValueError(f"page mora biti >= {self.MIN_PAGE}, dobijeno: {page}")
        if not (self.MIN_PAGE_SIZE <= page_size <= self.MAX_PAGE_SIZE):
            raise ValueError(
                f"page_size mora biti {self.MIN_PAGE_SIZE}-{self.MAX_PAGE_SIZE}, "
                f"dobijeno: {page_size}"
            )

        # Prikupi događaje iz svih izvora
        all_events: list[dict] = []

        # 1. SessionEvent — primarni izvor
        q = (
            self._session.query(SessionEvent)
            .filter(SessionEvent.session_id == session_id)
            .order_by(SessionEvent.occurred_at.asc())
        )
        if timeline_level == TimelineLevel.SUMMARY:
            q = q.filter(SessionEvent.event_type.in_(self.SUMMARY_EVENTS))
        elif timeline_level == TimelineLevel.TIMELINE:
            q = q.filter(SessionEvent.event_type.in_(self.TIMELINE_EVENTS))

        for e in q.all():
            all_events.append(
                {
                    "id": e.id,
                    "event_type": e.event_type,
                    "summary": e.summary,
                    "source": e.source,
                    "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
                    "origin": "SessionEvent",
                }
            )

        # 2. FileActivity — samo za TECHNICAL nivo
        if timeline_level == TimelineLevel.TECHNICAL:
            activities = (
                self._session.query(FileActivity)
                .filter(FileActivity.session_id == session_id)
                .order_by(FileActivity.occurred_at.asc())
                .all()
            )
            for a in activities:
                all_events.append(
                    {
                        "id": a.id,
                        "event_type": f"FILE_{a.event_type}",
                        "summary": f"{a.event_type}: {a.file_path}",
                        "source": a.source,
                        "occurred_at": a.occurred_at.isoformat() if a.occurred_at else None,
                        "origin": "FileActivity",
                        "file_path": a.file_path,
                        "attribution_type": a.attribution_type,
                    }
                )

        # 3. Conflict — za TECHNICAL i TIMELINE nivo
        if timeline_level != TimelineLevel.SUMMARY:
            conflicts = (
                self._session.query(Conflict)
                .filter(Conflict.session_ids_json.contains(session_id))
                .order_by(Conflict.detected_at.asc())
                .all()
            )
            for c in conflicts:
                all_events.append(
                    {
                        "id": c.id,
                        "event_type": f"CONFLICT_{c.conflict_type}",
                        "summary": c.description,
                        "source": "CONFLICT_DETECTOR",
                        "occurred_at": c.detected_at.isoformat() if c.detected_at else None,
                        "origin": "Conflict",
                        "conflict_level": c.conflict_level,
                        "conflict_type": c.conflict_type,
                    }
                )

        # 4. AgentReport — za TECHNICAL i TIMELINE nivo
        if timeline_level != TimelineLevel.SUMMARY:
            reports = (
                self._session.query(AgentReport)
                .filter(AgentReport.session_id == session_id)
                .order_by(AgentReport.created_at.asc())
                .all()
            )
            for r in reports:
                all_events.append(
                    {
                        "id": r.id,
                        "event_type": "REPORT_" + (r.status or "DRAFT"),
                        "summary": f"Report {r.status}: {r.summary or 'Nema.'}"[:200],
                        "source": "REPORT_SERVICE",
                        "occurred_at": r.created_at.isoformat() if r.created_at else None,
                        "origin": "AgentReport",
                        "verdict": r.user_verdict,
                    }
                )

        # Sortiraj sve događaje po vremenu
        all_events.sort(key=lambda e: e["occurred_at"] or "")

        # Paginacija
        total = len(all_events)
        offset = (page - 1) * page_size
        page_events = all_events[offset : offset + page_size]

        return {
            "events": page_events,
            "total": total,
            "page": page,
            "page_size": page_size,
            "level": level,
        }

    def get_summary(self, session_id: str) -> dict:
        """Vraća kratak sažetak sesije — gde je stala, naredni potez."""
        events_q = (
            self._session.query(SessionEvent)
            .filter(
                SessionEvent.session_id == session_id,
                SessionEvent.event_type.in_(self.SUMMARY_EVENTS),
            )
            .order_by(SessionEvent.occurred_at.desc())
            .limit(10)
            .all()
        )

        latest_event = events_q[0] if events_q else None

        return {
            "session_id": session_id,
            "total_events": (
                self._session.query(SessionEvent)
                .filter(SessionEvent.session_id == session_id)
                .count()
            ),
            "latest_event": {
                "event_type": latest_event.event_type,
                "summary": latest_event.summary,
                "occurred_at": latest_event.occurred_at.isoformat()
                if latest_event and latest_event.occurred_at
                else None,
            }
            if latest_event
            else None,
            "key_milestones": [
                {
                    "event_type": e.event_type,
                    "summary": e.summary,
                    "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
                }
                for e in events_q
            ],
        }
