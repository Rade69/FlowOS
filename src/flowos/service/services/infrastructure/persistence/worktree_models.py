"""SQLAlchemy ORM model za Worktree entitet.

Worktree predstavlja Git worktree kreiran za izolaciju agentske sesije.
Svaki worktree ima tačno jednu writer sesiju i prati svoj životni ciklus
od kreiranja do integracije ili cleanup-a.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from flowos.service.services.infrastructure.persistence.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class Worktree(Base):
    """Git worktree za izolovanu agentsku sesiju."""

    __tablename__ = "worktrees"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("agent_sessions.id", ondelete="SET NULL"), nullable=True
    )

    # Git identitet
    worktree_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    branch_name: Mapped[str] = mapped_column(String(500), nullable=False)
    base_branch: Mapped[str | None] = mapped_column(String(500), nullable=True)
    base_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ACTIVE"
    )  # ACTIVE, READY, INTEGRATED, ABANDONED, CLEANED
    is_clean: Mapped[bool] = mapped_column(Boolean, default=True)
    has_conflicts: Mapped[bool] = mapped_column(Boolean, default=False)

    # Vremenske oznake
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=_utcnow
    )
    integrated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cleaned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Retention
    retention_days: Mapped[int] = mapped_column(Integer, default=7)

    # Integracija
    result_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    integration_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Metadata
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_worktrees_project_id", "project_id"),
        Index("ix_worktrees_session_id", "session_id"),
        Index("ix_worktrees_status", "status"),
        Index("ix_worktrees_task_id", "task_id"),
    )
