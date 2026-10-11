"""Create scenarios and simulations tables for API persistence

Revision ID: 003_scenarios_and_simulations
Revises: 002_create_snapshots_table
Create Date: 2026-09-14

Issue: Phase 0 item 4 - API persistence for scenarios and simulations
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
# Keep this under 32 characters: alembic_version.version_num is VARCHAR(32).
revision: str = '003_scenarios_and_simulations'
down_revision: Union[str, None] = '002_create_snapshots_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create scenarios and simulations tables for API persistence."""

    op.create_table(
        'scenarios',
        sa.Column('scenario_id', sa.Uuid(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('spec', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        schema='public',
    )

    op.create_table(
        'simulations',
        sa.Column('simulation_id', sa.Uuid(), primary_key=True),
        sa.Column('scenario_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('finished_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('result', postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['scenario_id'], ['public.scenarios.scenario_id'], name='fk_simulations_scenario_id'),
        schema='public',
    )

    # Indexes for common query patterns
    op.create_index(
        'idx_simulations_scenario_id',
        'simulations',
        ['scenario_id'],
        schema='public',
    )
    op.create_index(
        'idx_simulations_status',
        'simulations',
        ['status'],
        schema='public',
    )


def downgrade() -> None:
    """Drop the scenarios and simulations tables."""
    op.drop_index('idx_simulations_status', table_name='simulations', schema='public')
    op.drop_index('idx_simulations_scenario_id', table_name='simulations', schema='public')
    op.drop_table('simulations', schema='public')
    op.drop_table('scenarios', schema='public')
