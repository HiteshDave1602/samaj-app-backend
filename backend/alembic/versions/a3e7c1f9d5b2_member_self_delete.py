"""a deleted account frees its mobile number: unique among live members only

Revision ID: a3e7c1f9d5b2
Revises: f1d4b8a6c3e2
Create Date: 2026-11-24 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a3e7c1f9d5b2'
down_revision: Union[str, Sequence[str], None] = 'f1d4b8a6c3e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The member (or an admin) deletes the account; that person may register again with the same number.
    op.create_index('ux_member_mobile_live', 'member', ['mobile_hash'], unique=True, schema='samaj',
                    postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_constraint('member_mobile_hash_key', 'member', schema='samaj', type_='unique')


def downgrade() -> None:
    # fails if a number was registered again after a delete; those rows must be resolved by hand first
    op.create_unique_constraint('member_mobile_hash_key', 'member', ['mobile_hash'], schema='samaj')
    op.drop_index('ux_member_mobile_live', 'member', schema='samaj')
