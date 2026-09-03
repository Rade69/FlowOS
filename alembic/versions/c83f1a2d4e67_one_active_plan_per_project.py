"""Enforce at most one ACTIVE plan per project.

Revision ID: c83f1a2d4e67
Revises: b7c2e1d4a903
Create Date: 2026-09-03 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c83f1a2d4e67"
down_revision: str | Sequence[str] | None = "b7c2e1d4a903"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Dodaje partial UNIQUE index; postojeći duplikati prekidaju migraciju."""
    op.create_index(
        "uq_plans_one_active_per_project",
        "plans",
        ["project_id"],
        unique=True,
        sqlite_where=sa.text("status = 'ACTIVE'"),
    )


def downgrade() -> None:
    """Uklanja samo ACTIVE uniqueness zaštitu."""
    op.drop_index("uq_plans_one_active_per_project", table_name="plans")
