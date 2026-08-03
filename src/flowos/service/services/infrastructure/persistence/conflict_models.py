"""SQLAlchemy ORM model za Conflict entitet.

Konflikti se detektuju od strane ConflictDetectionService-a
na osnovu posmatranih filesystem/Git događaja i aktivnih sesija.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from flowos.service.services.infrastructure.persistence.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class Conflict(Base):
    """Detektovani konflikt između dve ili više sesija.

    Svaki konflikt ima nivo (HIGH/MEDIUM/INFO), opis, listu
    uključenih sesija, fajl/putanju i status (OPEN/ACKNOWLEDGED/RESOLVED).
    """

    __tablename__ = "conflicts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    file_path: Mapped[str] = mapped_column(String(2000), nullable=False)
    conflict_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )  # dedup ključ (SHA-256)
    session_ids_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]"
    )  # JSON lista ID-jeva sesija
    conflict_level: Mapped[str] = mapped_column(String(10), nullable=False)  # HIGH, MEDIUM, INFO
    conflict_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # WRITE_WRITE, BRANCH_CHANGE, NO_COMMIT, STALE_SESSION
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON sa dokazima (vremena, diff-ovi)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="OPEN"
    )  # OPEN, ACKNOWLEDGED, RESOLVED
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    occurrence_count: Mapped[int] = mapped_column(default=1)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        Index("ix_conflicts_project_id", "project_id"),
        Index("ix_conflicts_status", "status"),
        Index("ix_conflicts_level", "conflict_level"),
        Index("ix_conflicts_detected_at", "detected_at"),
        Index("ix_conflicts_conflict_key", "conflict_key", unique=True),
    )
