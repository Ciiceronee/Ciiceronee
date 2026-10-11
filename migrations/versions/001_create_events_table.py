"""Create events table for event sourcing

Revision ID: 001_create_events_table
Revises: None
Create Date: 2026-01-23

Issue: #119 - Event Sourcing Phase 2
Author: Omolara Oladipupo (@laradipupo)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_create_events_table'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the events table and indexes for event sourcing."""
    
    # Create audit schema if not exists
    op.execute("CREATE SCHEMA IF NOT EXISTS audit")
    
    # Create events table
    op.create_table(
        'events',
        sa.Column('event_id', postgresql.UUID(as_uuid=True), primary_key=True),
        # Postgres only auto-increments PRIMARY KEY columns; a plain non-PK
        # BIGINT gets no default. Global ordering is backed by an explicit
        # sequence (created below in upgrade()).
        sa.Column('sequence_number', sa.BigInteger(), unique=True, nullable=False),
        sa.Column('aggregate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('aggregate_type', sa.String(50), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('event_data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint('aggregate_id', 'version', name='unique_aggregate_version'),
        schema='audit'
    )
    
    # Create indexes for common query patterns
    op.create_index(
        'idx_events_aggregate_id',
        'events',
        ['aggregate_id'],
        schema='audit'
    )
    op.create_index(
        'idx_events_aggregate_type',
        'events',
        ['aggregate_type'],
        schema='audit'
    )
    op.create_index(
        'idx_events_event_type',
        'events',
        ['event_type'],
        schema='audit'
    )
    op.create_index(
        'idx_events_timestamp',
        'events',
        [sa.text('timestamp DESC')],
        schema='audit'
    )
    op.create_index(
        'idx_events_aggregate_version',
        'events',
        ['aggregate_id', 'version'],
        schema='audit'
    )
    
    # Create GIN indexes for JSONB queries
    op.execute(
        "CREATE INDEX idx_events_event_data ON audit.events USING GIN (event_data)"
    )
    op.execute(
        "CREATE INDEX idx_events_metadata ON audit.events USING GIN (metadata)"
    )

    # Explicit sequence: Postgres does not auto-increment non-PK columns.
    op.execute("CREATE SEQUENCE IF NOT EXISTS audit.events_sequence_number_seq")
    op.execute(
        "ALTER TABLE audit.events "
        "ALTER COLUMN sequence_number "
        "SET DEFAULT nextval('audit.events_sequence_number_seq')"
    )


def downgrade() -> None:
    """Drop the events table."""
    op.execute("ALTER TABLE audit.events ALTER COLUMN sequence_number DROP DEFAULT")
    op.execute("DROP SEQUENCE IF EXISTS audit.events_sequence_number_seq")
    op.drop_table('events', schema='audit')
