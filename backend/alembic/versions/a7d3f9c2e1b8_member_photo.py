"""member photo

Revision ID: a7d3f9c2e1b8
Revises: c9e4a1d7f2b5
Create Date: 2026-10-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a7d3f9c2e1b8'
down_revision: Union[str, Sequence[str], None] = 'c9e4a1d7f2b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('member', sa.Column('photo_key', sa.String(64)), schema='samaj')


def downgrade() -> None:
    op.drop_column('member', 'photo_key', schema='samaj')
