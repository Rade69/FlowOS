"""SQLAlchemy ORM modeli za trajno stanje projekta i povratak.

ProjectWorkspaceState — poslednje poznato Git stanje
ProjectResumeState  — materijalizovani sažetak "Gde si stao"
ProjectReconciliationEvent — append-only audit Git promena van FlowOS-a
ExternalActivity — trag za promene van FlowOS-a bez lažne atribucije
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


# ═══════════════════════════════════════════════════════════════════
# ProjectWorkspaceState
# ═══════════════════════════════════════════════════════════════════


class ProjectWorkspaceState(Base):
    """Poslednje poznato Git stanje projekta — koristi se za reconciliation."""

    __tablename__ = "project_workspace_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    last_known_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_known_branch: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_known_status_porcelain: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_known_dirty_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_reconciled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reconciliation_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="CURRENT"
    )
    external_change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=_utcnow)

    __table_args__ = (Index("ix_ws_project_id", "project_id"),)


# ═══════════════════════════════════════════════════════════════════
# ProjectResumeState
# ═══════════════════════════════════════════════════════════════════


class ProjectResumeState(Base):
    """Materijalizovani sažetak "Gde si stao" — regeneriše se iz izvora."""

    __tablename__ = "project_resume_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    active_plan_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_plan_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_report_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resume_status: Mapped[str] = mapped_column(String(30), nullable=False, default="NO_HISTORY")
    where_stopped: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_concrete_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_preconditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    open_blockers_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    open_decisions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(String(10), nullable=False, default="LOW")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (Index("ix_rs_project_id", "project_id"),)


# ═══════════════════════════════════════════════════════════════════
# ProjectReconciliationEvent (append-only)
# ═══════════════════════════════════════════════════════════════════


class ProjectReconciliationEvent(Base):
    """Append-only zapis poređenja poslednjeg poznatog i trenutnog Git stanja."""

    __tablename__ = "project_reconciliation_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    previous_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    current_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    previous_branch: Mapped[str | None] = mapped_column(String(500), nullable=True)
    current_branch: Mapped[str | None] = mapped_column(String(500), nullable=True)
    previous_dirty_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_dirty_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result: Mapped[str] = mapped_column(String(30), nullable=False)
    new_commit_shas_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_files_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_resolution: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_rec_events_project_id", "project_id"),
        Index("ix_rec_events_occurred_at", "occurred_at"),
    )


# ═══════════════════════════════════════════════════════════════════
# ExternalActivity
# ═══════════════════════════════════════════════════════════════════


class ExternalActivity(Base):
    """Trag za promene van FlowOS-a — bez lažne atribucije."""

    __tablename__ = "external_activities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    plan_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="UNKNOWN")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    commit_shas_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_files_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    attribution: Mapped[str] = mapped_column(String(30), nullable=False, default="UNATTRIBUTED")
    user_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (Index("ix_ext_activity_project_id", "project_id"),)
