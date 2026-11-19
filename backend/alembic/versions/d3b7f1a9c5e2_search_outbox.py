"""search outbox

Revision ID: d3b7f1a9c5e2
Revises: a9c5e2f7b1d4
Create Date: 2026-11-18 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd3b7f1a9c5e2'
down_revision: Union[str, Sequence[str], None] = 'a9c5e2f7b1d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Transactional outbox for the Elasticsearch directory/matrimony index (search/outbox.py)
    op.create_table('search_outbox',
    sa.Column('id', sa.BigInteger(), sa.Identity(), nullable=False),
    sa.Column('entity', sa.String(length=12), nullable=False),
    sa.Column('entity_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('attempts', sa.SmallInteger(), server_default=sa.text('0'), nullable=False),
    sa.Column('next_attempt_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_error', sa.String(length=500), nullable=True),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('dead_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("entity IN ('member','relative','household','matrimony')", name='ck_search_outbox_entity'),
    sa.PrimaryKeyConstraint('id'),
    schema='samaj'
    )
    op.create_index('ix_search_outbox_due', 'search_outbox', ['next_attempt_at'], schema='samaj',
                    postgresql_where=sa.text('processed_at IS NULL AND dead_at IS NULL'))
    op.create_index('ix_search_outbox_processed', 'search_outbox', ['processed_at'], schema='samaj',
                    postgresql_where=sa.text('processed_at IS NOT NULL'))


def downgrade() -> None:
    op.drop_table('search_outbox', schema='samaj')  # its indexes go with it
