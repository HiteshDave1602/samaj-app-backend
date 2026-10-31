"""matrimony profile gotra and height (public, shown on cards)

Revision ID: d6a2b8e4f1c9
Revises: a7d3e9f1c2b6
Create Date: 2026-10-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd6a2b8e4f1c9'
down_revision: Union[str, Sequence[str], None] = 'a7d3e9f1c2b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('matrimony_profile', sa.Column('gotra', sa.String(length=60), nullable=True), schema='samaj')
    op.add_column('matrimony_profile', sa.Column('height_cm', sa.SmallInteger(), nullable=True), schema='samaj')
    op.create_check_constraint('ck_matrimony_profile_height', 'matrimony_profile', 'height_cm BETWEEN 100 AND 250',
                               schema='samaj')


def downgrade() -> None:
    op.drop_column('matrimony_profile', 'height_cm', schema='samaj')
    op.drop_column('matrimony_profile', 'gotra', schema='samaj')
