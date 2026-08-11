"""SQLAlchemy ORM modeli za FlowOS Core entitete.

Modeli predstavljaju tabele u SQLite bazi. Svi identifikatori
su UUID stringovi (generisani u aplikativnom sloju).
Vremenski podaci se čuvaju u UTC.

Ovi modeli su privatni za persistence sloj. Services sloj
ih koristi interno, a API Controlleri dobijaju samo DTO objekte.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flowos.service.services.infrastructure.persistence.base import Base


def _new_uuid() -> str:
    """Generiše novi UUID string za primarni ključ."""
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    """Vraća trenutno vreme u UTC, timezone-aware."""
    return datetime.now(tz=UTC)


# ═══════════════════════════════════════════════════════════════════
# Project
# ═══════════════════════════════════════════════════════════════════


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    repo_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=_utcnow
    )

    # Veze
    tasks: Mapped[list["Task"]] = relationship(
        "Task", back_populates="project", passive_deletes=True
    )

    __table_args__ = (Index("ix_projects_status", "status"),)


# ═══════════════════════════════════════════════════════════════════
# Task
# ═══════════════════════════════════════════════════════════════════


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="NORMAL")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=_utcnow
    )
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    plan_item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("plan_items.id", ondelete="SET NULL"), nullable=True
    )

    # Veze
    project: Mapped["Project"] = relationship("Project", back_populates="tasks")
    sessions: Mapped[list["AgentSession"]] = relationship("AgentSession", back_populates="task")

    __table_args__ = (
        Index("ix_tasks_project_id", "project_id"),
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_priority", "priority"),
    )


# ═══════════════════════════════════════════════════════════════════
# AgentSession
# ═══════════════════════════════════════════════════════════════════


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    execution_mode: Mapped[str] = mapped_column(
        String(30), nullable=False, default="WRAPPED_TERMINAL"
    )
    terminal_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    working_directory: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    repo_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    branch_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    worktree_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    base_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=_utcnow
    )
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    plan_item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("plan_items.id", ondelete="SET NULL"), nullable=True
    )

    # Veze
    task: Mapped["Task | None"] = relationship("Task", back_populates="sessions")
    task_bindings: Mapped[list["SessionTaskBinding"]] = relationship(
        "SessionTaskBinding",
        back_populates="session",
        order_by="SessionTaskBinding.started_at",
        passive_deletes=True,
    )
    events: Mapped[list["SessionEvent"]] = relationship(
        "SessionEvent",
        back_populates="session",
        order_by="SessionEvent.occurred_at",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_agent_sessions_project_id", "project_id"),
        Index("ix_agent_sessions_task_id", "task_id"),
        Index("ix_agent_sessions_status", "status"),
        Index("ix_agent_sessions_execution_mode", "execution_mode"),
    )


# ═══════════════════════════════════════════════════════════════════
# SessionTaskBinding
# ═══════════════════════════════════════════════════════════════════


class SessionTaskBinding(Base):
    """Istorijski segment veze sesije sa Task, PlanItem ili UNASSIGNED stanjem."""

    __tablename__ = "session_task_bindings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=True
    )
    plan_item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("plan_items.id", ondelete="RESTRICT"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    binding_source: Mapped[str] = mapped_column(String(30), nullable=False)

    session: Mapped["AgentSession"] = relationship("AgentSession", back_populates="task_bindings")

    __table_args__ = (
        CheckConstraint(
            "NOT (task_id IS NOT NULL AND plan_item_id IS NOT NULL)",
            name="ck_session_task_bindings_single_target",
        ),
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ck_session_task_bindings_time_order",
        ),
        CheckConstraint(
            "binding_source IN ('USER', 'LEGACY_DIRECT_FK')",
            name="ck_session_task_bindings_source",
        ),
        Index("ix_session_task_bindings_session_id", "session_id"),
        Index("ix_session_task_bindings_task_id", "task_id"),
        Index("ix_session_task_bindings_plan_item_id", "plan_item_id"),
        Index("ix_session_task_bindings_started_at", "started_at"),
        Index(
            "uq_session_task_bindings_active",
            "session_id",
            unique=True,
            sqlite_where=text("ended_at IS NULL"),
        ),
    )


# ═══════════════════════════════════════════════════════════════════
# SessionEvent (append-only)
# ═══════════════════════════════════════════════════════════════════


class SessionEvent(Base):
    __tablename__ = "session_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="WRAPPER")
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # Veze
    session: Mapped["AgentSession"] = relationship("AgentSession", back_populates="events")

    __table_args__ = (
        Index("ix_session_events_session_id", "session_id"),
        Index("ix_session_events_event_type", "event_type"),
        Index("ix_session_events_occurred_at", "occurred_at"),
    )
