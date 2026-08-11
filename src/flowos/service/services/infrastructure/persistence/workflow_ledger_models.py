"""Workflow Ledger ORM model.

Ledger čuva append-only workflow događaje izvedene iz autoritativnih backend
izvora. Phase 3A piše samo IMPLEMENTATION_COMPLETED iz ingested AgentReport-a.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from flowos.service.services.infrastructure.persistence.base import Base


def _new_uuid() -> str:
    """Generiše novi UUID string za primarni ključ."""
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    """Vraća trenutno vreme u UTC, timezone-aware."""
    return datetime.now(tz=UTC)


class WorkflowLedgerEvent(Base):
    """Append-only workflow event zapis.

    Service sloj je jedini writer. Model je namjerno generičan da kasniji
    TEST_RESULT/review/user-decision događaji ne traže novu baznu strukturu.
    """

    __tablename__ = "workflow_ledger_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("agent_sessions.id", ondelete="SET NULL"), nullable=True
    )
    task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    plan_item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("plan_items.id", ondelete="SET NULL"), nullable=True
    )
    source_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    source_id: Mapped[str] = mapped_column(String(120), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    idempotency_key: Mapped[str] = mapped_column(String(300), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_workflow_ledger_events_idempotency_key"),
        Index("ix_workflow_ledger_project_recorded", "project_id", "recorded_at"),
        Index(
            "ix_workflow_ledger_project_event_recorded",
            "project_id",
            "event_type",
            "recorded_at",
        ),
        Index("ix_workflow_ledger_session_recorded", "session_id", "recorded_at"),
        Index("ix_workflow_ledger_task_recorded", "task_id", "recorded_at"),
        Index("ix_workflow_ledger_plan_item_recorded", "plan_item_id", "recorded_at"),
        Index("ix_workflow_ledger_source", "source_kind", "source_id"),
    )
