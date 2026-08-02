"""SQLAlchemy ORM model za FileActivity entitet.

FileActivity beleži svaki filesystem događaj koji watcher detektuje.
Slobodni za atribuciju, detekciju konflikata i timeline rekonstrukciju.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from flowos.service.services.infrastructure.persistence.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class FileActivity(Base):
    """Trajni zapis filesystem događaja iz watcher-a.

    Svaki događaj ima jedinstveni event_id za deduplikaciju i
    idempotency_key za kontrolu ponovljenih unosa.
    """

    __tablename__ = "file_activities"

    # ── Identifikatori ──────────────────────────────────────────
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    event_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True, unique=True)

    # ── Veze ka entitetima ──────────────────────────────────────
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("agent_sessions.id", ondelete="SET NULL"), nullable=True
    )
    plan_item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("plan_items.id", ondelete="SET NULL"), nullable=True
    )
    agent_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── Podaci o događaju ───────────────────────────────────────
    event_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # CREATED, MODIFIED, DELETED
    file_path: Mapped[str] = mapped_column(String(2000), nullable=False)
    normalized_path: Mapped[str] = mapped_column(String(2000), nullable=False)
    tree_identity: Mapped[str] = mapped_column(
        String(2000), nullable=False
    )  # normalizovana worktree ili repo putanja
    repository_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    worktree_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # ── Atribucija ──────────────────────────────────────────────
    attribution_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="UNATTRIBUTED"
    )  # WORKTREE_EXACT, REPOSITORY_EXACT, SOLE_ACTIVE_SESSION_WITHIN_REPO, UNATTRIBUTED, USER
    attribution_confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )  # 0.0 – 1.0

    # ── Vremenske oznake ────────────────────────────────────────
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )  # Kada se događaj desio na filesystem-u
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )  # Kada je događaj zabeležen u bazu

    # ── Metapodaci ──────────────────────────────────────────────
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="WATCHER"
    )  # WATCHER, GIT_POLL, MANUAL
    metadata_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON sa dodatnim kontekstom

    # ── Indeksi ─────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_file_activities_project_id", "project_id"),
        Index("ix_file_activities_session_id", "session_id"),
        Index("ix_file_activities_normalized_path", "normalized_path"),
        Index("ix_file_activities_occurred_at", "occurred_at"),
        Index("ix_file_activities_event_type", "event_type"),
        Index("ix_file_activities_attribution_type", "attribution_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<FileActivity {self.event_type} {self.file_path}"
            f" session={self.session_id or 'none'} attr={self.attribution_type}>"
        )
