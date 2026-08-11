"""workflow_ledger_events

Revision ID: b7c2e1d4a903
Revises: 4f2c9a7b8d11
Create Date: 2026-08-11 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7c2e1d4a903"
down_revision: str | Sequence[str] | None = "4f2c9a7b8d11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Kreira append-only Workflow Ledger tabelu bez backfill-a."""
    op.create_table(
        "workflow_ledger_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("plan_item_id", sa.String(length=36), nullable=True),
        sa.Column("source_kind", sa.String(length=80), nullable=False),
        sa.Column("source_id", sa.String(length=120), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=300), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["plan_item_id"], ["plan_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_workflow_ledger_events_idempotency_key"
        ),
    )
    op.create_index(
        "ix_workflow_ledger_project_recorded",
        "workflow_ledger_events",
        ["project_id", "recorded_at"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_ledger_project_event_recorded",
        "workflow_ledger_events",
        ["project_id", "event_type", "recorded_at"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_ledger_session_recorded",
        "workflow_ledger_events",
        ["session_id", "recorded_at"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_ledger_task_recorded",
        "workflow_ledger_events",
        ["task_id", "recorded_at"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_ledger_plan_item_recorded",
        "workflow_ledger_events",
        ["plan_item_id", "recorded_at"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_ledger_source",
        "workflow_ledger_events",
        ["source_kind", "source_id"],
        unique=False,
    )


def downgrade() -> None:
    """Uklanja samo Workflow Ledger Phase 3A tabelu."""
    op.drop_index("ix_workflow_ledger_source", table_name="workflow_ledger_events")
    op.drop_index("ix_workflow_ledger_plan_item_recorded", table_name="workflow_ledger_events")
    op.drop_index("ix_workflow_ledger_task_recorded", table_name="workflow_ledger_events")
    op.drop_index("ix_workflow_ledger_session_recorded", table_name="workflow_ledger_events")
    op.drop_index(
        "ix_workflow_ledger_project_event_recorded", table_name="workflow_ledger_events"
    )
    op.drop_index("ix_workflow_ledger_project_recorded", table_name="workflow_ledger_events")
    op.drop_table("workflow_ledger_events")
