"""agent_report_source_identity

Revision ID: 4f2c9a7b8d11
Revises: a17e4c8f9b21
Create Date: 2026-08-11 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "4f2c9a7b8d11"
down_revision: str | Sequence[str] | None = "a17e4c8f9b21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Dodaje nullable source identity polja bez legacy backfill-a."""
    op.add_column(
        "agent_reports", sa.Column("source_report_id", sa.String(length=36), nullable=True)
    )
    op.add_column("agent_reports", sa.Column("source_path", sa.String(length=2000), nullable=True))
    op.add_column(
        "agent_reports", sa.Column("source_content_sha256", sa.String(length=64), nullable=True)
    )
    op.create_index(
        "ix_agent_reports_source_report_id",
        "agent_reports",
        ["source_report_id"],
        unique=True,
    )
    op.create_index(
        "ix_agent_reports_source_path",
        "agent_reports",
        ["source_path"],
        unique=True,
    )


def downgrade() -> None:
    """Uklanja samo Phase 2 source identity polja."""
    op.drop_index("ix_agent_reports_source_path", table_name="agent_reports")
    op.drop_index("ix_agent_reports_source_report_id", table_name="agent_reports")
    op.drop_column("agent_reports", "source_content_sha256")
    op.drop_column("agent_reports", "source_path")
    op.drop_column("agent_reports", "source_report_id")
