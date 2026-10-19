"""directory search

Revision ID: c9e4a1d7f2b5
Revises: b8d2e5f1c3a7
Create Date: 2026-10-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c9e4a1d7f2b5'
down_revision: Union[str, Sequence[str], None] = 'b8d2e5f1c3a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Trigram indexes from the schema file: ILIKE '%term%' on names (FR-65).
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index('ix_member_name_trgm', 'member', ['full_name'], unique=False, schema='samaj',
                    postgresql_using='gin', postgresql_ops={'full_name': 'gin_trgm_ops'},
                    postgresql_where=sa.text("status = 'ACTIVE' AND deleted_at IS NULL"))
    op.create_index('ix_household_family_name_trgm', 'household', ['family_name'], unique=False, schema='samaj',
                    postgresql_using='gin', postgresql_ops={'family_name': 'gin_trgm_ops'})


def downgrade() -> None:
    op.drop_index('ix_household_family_name_trgm', table_name='household', schema='samaj')
    op.drop_index('ix_member_name_trgm', table_name='member', schema='samaj')
