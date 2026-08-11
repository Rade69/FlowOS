"""session_task_bindings

Revision ID: 9b2d1f7a4c63
Revises: ce4d3efbde51
Create Date: 2026-08-10 18:35:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9b2d1f7a4c63"
down_revision: Union[str, Sequence[str], None] = "ce4d3efbde51"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "session_task_bindings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("plan_item_id", sa.String(length=36), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("binding_source", sa.String(length=30), nullable=False),
        sa.CheckConstraint(
            "NOT (task_id IS NOT NULL AND plan_item_id IS NOT NULL)",
            name="ck_session_task_bindings_single_target",
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ck_session_task_bindings_time_order",
        ),
        sa.CheckConstraint(
            "binding_source IN ('USER', 'LEGACY_DIRECT_FK')",
            name="ck_session_task_bindings_source",
        ),
        sa.ForeignKeyConstraint(["plan_item_id"], ["plan_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_session_task_bindings_plan_item_id",
        "session_task_bindings",
        ["plan_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_session_task_bindings_session_id",
        "session_task_bindings",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_session_task_bindings_started_at",
        "session_task_bindings",
        ["started_at"],
        unique=False,
    )
    op.create_index(
        "ix_session_task_bindings_task_id",
        "session_task_bindings",
        ["task_id"],
        unique=False,
    )
    op.create_index(
        "uq_session_task_bindings_active",
        "session_task_bindings",
        ["session_id"],
        unique=True,
        sqlite_where=sa.text("ended_at IS NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_session_task_bindings_active", table_name="session_task_bindings")
    op.drop_index("ix_session_task_bindings_task_id", table_name="session_task_bindings")
    op.drop_index("ix_session_task_bindings_started_at", table_name="session_task_bindings")
    op.drop_index("ix_session_task_bindings_session_id", table_name="session_task_bindings")
    op.drop_index("ix_session_task_bindings_plan_item_id", table_name="session_task_bindings")
    op.drop_table("session_task_bindings")
