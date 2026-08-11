"""agent_report_v2_bindings

Revision ID: a17e4c8f9b21
Revises: 9b2d1f7a4c63
Create Date: 2026-08-11 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a17e4c8f9b21"
down_revision: str | Sequence[str] | None = "9b2d1f7a4c63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Dodaje nullable v2 semantiku i report-binding veze bez backfill-a."""
    op.add_column("agent_reports", sa.Column("report_type", sa.String(length=50), nullable=True))
    op.add_column("agent_reports", sa.Column("work_status", sa.String(length=20), nullable=True))
    with op.batch_alter_table("agent_reports") as batch_op:
        batch_op.create_check_constraint(
            "ck_agent_reports_work_status",
            "work_status IS NULL OR work_status IN ('completed', 'partial', 'blocked')",
        )
    op.create_table(
        "agent_report_binding_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("session_task_binding_id", sa.String(length=36), nullable=False),
        sa.Column("resolved_plan_item_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["agent_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["session_task_binding_id"], ["session_task_bindings.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["resolved_plan_item_id"], ["plan_items.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "report_id",
            "session_task_binding_id",
            name="uq_agent_report_binding_links_report_binding",
        ),
    )
    op.create_index(
        "ix_agent_report_binding_links_report_id",
        "agent_report_binding_links",
        ["report_id"],
        unique=False,
    )
    op.create_index(
        "ix_agent_report_binding_links_binding_id",
        "agent_report_binding_links",
        ["session_task_binding_id"],
        unique=False,
    )


def downgrade() -> None:
    """Uklanja samo v2 strukturu."""
    op.drop_index(
        "ix_agent_report_binding_links_binding_id", table_name="agent_report_binding_links"
    )
    op.drop_index(
        "ix_agent_report_binding_links_report_id", table_name="agent_report_binding_links"
    )
    op.drop_table("agent_report_binding_links")
    with op.batch_alter_table("agent_reports") as batch_op:
        batch_op.drop_constraint("ck_agent_reports_work_status", type_="check")
    op.drop_column("agent_reports", "work_status")
    op.drop_column("agent_reports", "report_type")
