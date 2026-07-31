"""SQLAlchemy ORM modeli za strukturisano praćenje plana projekta.

Plan, PlanPhase, PlanItem, PlanItemCriterion, PlanItemDependency,
PlanProgressEvent — omogućavaju FlowOS-u da prati šta je planirano,
koji su kriterijumi, koje su zavisnosti i kako se menja status.

Ovi modeli su privatni za persistence sloj.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flowos.service.services.infrastructure.persistence.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


# ═══════════════════════════════════════════════════════════════════
# Plan
# ═══════════════════════════════════════════════════════════════════


class Plan(Base):
    """Aktivirani plan projekta (jedan po projektu)."""

    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    source_artifact_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=_utcnow
    )

    phases: Mapped[list["PlanPhase"]] = relationship(
        "PlanPhase", back_populates="plan", order_by="PlanPhase.sequence"
    )

    __table_args__ = (Index("ix_plans_project_id", "project_id"),)


# ═══════════════════════════════════════════════════════════════════
# PlanPhase
# ═══════════════════════════════════════════════════════════════════


class PlanPhase(Base):
    """Faza u planu (npr. 'Faza 0 — Validacija')."""

    __tablename__ = "plan_phases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False
    )
    phase_key: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="NOT_STARTED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    plan: Mapped["Plan"] = relationship("Plan", back_populates="phases")
    items: Mapped[list["PlanItem"]] = relationship(
        "PlanItem", back_populates="phase", order_by="PlanItem.sequence"
    )

    __table_args__ = (
        Index("ix_plan_phases_plan_id", "plan_id"),
        UniqueConstraint("plan_id", "phase_key", name="uq_plan_phases_key"),
    )


# ═══════════════════════════════════════════════════════════════════
# PlanItem
# ═══════════════════════════════════════════════════════════════════


class PlanItem(Base):
    """Pojedinačna planirana stavka (npr. FLOW-103A)."""

    __tablename__ = "plan_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    plan_phase_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plan_phases.id", ondelete="CASCADE"), nullable=False
    )
    item_key: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False, default="MEDIUM")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="NOT_STARTED")
    progress_source: Mapped[str] = mapped_column(String(20), nullable=False, default="MANUAL")
    owner_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    implemented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=_utcnow
    )

    phase: Mapped["PlanPhase"] = relationship("PlanPhase", back_populates="items")
    criteria: Mapped[list["PlanItemCriterion"]] = relationship(
        "PlanItemCriterion", back_populates="plan_item", passive_deletes=True
    )
    progress_events: Mapped[list["PlanProgressEvent"]] = relationship(
        "PlanProgressEvent",
        back_populates="plan_item",
        order_by="PlanProgressEvent.occurred_at",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_plan_items_phase_id", "plan_phase_id"),
        Index("ix_plan_items_status", "status"),
        Index("ix_plan_items_item_key", "item_key"),
    )


# ═══════════════════════════════════════════════════════════════════
# PlanItemCriterion
# ═══════════════════════════════════════════════════════════════════


class PlanItemCriterion(Base):
    """Acceptance kriterijum za planiranu stavku."""

    __tablename__ = "plan_item_criteria"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    plan_item_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("plan_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    criterion_key: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    evidence_artifact_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    verification_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=_utcnow
    )

    plan_item: Mapped["PlanItem"] = relationship("PlanItem", back_populates="criteria")

    __table_args__ = (
        Index("ix_plan_item_criteria_item_id", "plan_item_id"),
        Index("ix_plan_item_criteria_status", "status"),
    )


# ═══════════════════════════════════════════════════════════════════
# PlanItemDependency
# ═══════════════════════════════════════════════════════════════════


class PlanItemDependency(Base):
    """Zavisnost između dve planirane stavke."""

    __tablename__ = "plan_item_dependencies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    plan_item_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("plan_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    depends_on_plan_item_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("plan_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    dependency_type: Mapped[str] = mapped_column(String(30), nullable=False, default="BLOCKS_START")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        Index("ix_deps_plan_item_id", "plan_item_id"),
        Index("ix_deps_depends_on", "depends_on_plan_item_id"),
        UniqueConstraint("plan_item_id", "depends_on_plan_item_id", name="uq_dependency_pair"),
    )


# ═══════════════════════════════════════════════════════════════════
# PlanProgressEvent (append-only audit)
# ═══════════════════════════════════════════════════════════════════


class PlanProgressEvent(Base):
    """Append-only audit svake promene statusa planirane stavke."""

    __tablename__ = "plan_progress_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    plan_item_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("plan_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    agent_report_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    from_status: Mapped[str] = mapped_column(String(20), nullable=False)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_artifact_ids_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="SYSTEM")
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    plan_item: Mapped["PlanItem"] = relationship("PlanItem", back_populates="progress_events")

    __table_args__ = (
        Index("ix_progress_events_item_id", "plan_item_id"),
        Index("ix_progress_events_occurred_at", "occurred_at"),
    )
