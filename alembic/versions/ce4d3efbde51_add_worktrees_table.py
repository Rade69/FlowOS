"""add_worktrees_table

Revision ID: ce4d3efbde51
Revises: 96aa6257d45c
Create Date: 2026-08-03 12:12:02.286946

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ce4d3efbde51'
down_revision: Union[str, Sequence[str], None] = '96aa6257d45c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('worktrees',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('project_id', sa.String(length=36), nullable=False),
    sa.Column('task_id', sa.String(length=36), nullable=True),
    sa.Column('session_id', sa.String(length=36), nullable=True),
    sa.Column('worktree_path', sa.String(length=1000), nullable=False),
    sa.Column('branch_name', sa.String(length=500), nullable=False),
    sa.Column('base_branch', sa.String(length=500), nullable=True),
    sa.Column('base_commit_sha', sa.String(length=40), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('is_clean', sa.Boolean(), nullable=False),
    sa.Column('has_conflicts', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('integrated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cleaned_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('retention_days', sa.Integer(), nullable=False),
    sa.Column('result_commit_sha', sa.String(length=40), nullable=True),
    sa.Column('integration_verified', sa.Boolean(), nullable=False),
    sa.Column('metadata_json', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['session_id'], ['agent_sessions.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_worktrees_project_id', 'worktrees', ['project_id'], unique=False)
    op.create_index('ix_worktrees_session_id', 'worktrees', ['session_id'], unique=False)
    op.create_index('ix_worktrees_status', 'worktrees', ['status'], unique=False)
    op.create_index('ix_worktrees_task_id', 'worktrees', ['task_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_worktrees_task_id', table_name='worktrees')
    op.drop_index('ix_worktrees_status', table_name='worktrees')
    op.drop_index('ix_worktrees_session_id', table_name='worktrees')
    op.drop_index('ix_worktrees_project_id', table_name='worktrees')
    op.drop_table('worktrees')
