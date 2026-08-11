"""SQLAlchemy ORM model za AgentReport.

AgentReport predstavlja strukturisani izveštaj o agentskoj sesiji.
Markdown verzija se čuva kao artefakt, a strukturisani podaci u bazi.
"""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flowos.service.services.infrastructure.persistence.base import Base

if TYPE_CHECKING:
    from flowos.service.services.infrastructure.persistence.models import SessionTaskBinding


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class AgentReport(Base):
    """Strukturisani izveštaj o agentskoj sesiji ili jobu.

    Polja prate agent_report_template.md iz agent metode:
    svaka sekcija bez sadržaja ostaje sa vrednošću 'Nema.'
    """

    __tablename__ = "agent_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False
    )
    agent_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Deterministička implementer semantika; legacy reporti ostaju NULL.
    report_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    work_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Status izveštaja
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")  # DRAFT, FINAL

    # Sadržaj izveštaja (po agent_report_template.md)
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    reproduction_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    implementation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    untouched_scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    independent_review_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    found_issues: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejected_options: Mapped[str | None] = mapped_column(Text, nullable=True)
    conflicting_sources: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Commit i artefakt reference
    commit_shas_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON lista
    changed_files_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON lista

    # Rizici i follow-up
    open_risks: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Korisnička potvrda
    user_confirmation_required: Mapped[bool] = mapped_column(default=False)
    user_verdict: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # ACCEPTED, NEEDS_WORK, REJECTED
    user_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    verdict_audit_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON lista audit zapisa: [{timestamp, verdict, previous_verdict, notes}]

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=_utcnow
    )

    binding_links: Mapped[list["AgentReportBindingLink"]] = relationship(
        "AgentReportBindingLink",
        back_populates="report",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint(
            "work_status IS NULL OR work_status IN ('completed', 'partial', 'blocked')",
            name="ck_agent_reports_work_status",
        ),
        Index("ix_agent_reports_session_id", "session_id"),
        Index("ix_agent_reports_status", "status"),
    )


class AgentReportBindingLink(Base):
    """Veza reporta sa autoritativnim istorijskim binding segmentom."""

    __tablename__ = "agent_report_binding_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_reports.id", ondelete="CASCADE"), nullable=False
    )
    session_task_binding_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("session_task_bindings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    resolved_plan_item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("plan_items.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    report: Mapped["AgentReport"] = relationship("AgentReport", back_populates="binding_links")
    session_task_binding: Mapped["SessionTaskBinding"] = relationship(
        "SessionTaskBinding", back_populates="report_links"
    )

    __table_args__ = (
        UniqueConstraint(
            "report_id",
            "session_task_binding_id",
            name="uq_agent_report_binding_links_report_binding",
        ),
        Index("ix_agent_report_binding_links_report_id", "report_id"),
        Index("ix_agent_report_binding_links_binding_id", "session_task_binding_id"),
    )
