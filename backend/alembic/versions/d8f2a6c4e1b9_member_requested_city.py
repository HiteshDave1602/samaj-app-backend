"""member requested city: register for a city the Super Admin hasn't created yet

Revision ID: d8f2a6c4e1b9
Revises: c4e8a1f6d2b9
Create Date: 2026-11-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd8f2a6c4e1b9'
down_revision: Union[str, Sequence[str], None] = 'c4e8a1f6d2b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('member', sa.Column('requested_city', sa.String(80), nullable=True), schema='samaj')
    op.add_column('member', sa.Column('requested_state', sa.String(60), nullable=True), schema='samaj')
    op.alter_column('member', 'city_id', nullable=True, schema='samaj')
    op.alter_column('household', 'city_id', nullable=True, schema='samaj')
    op.create_check_constraint(
        'ck_member_3', 'member',
        "city_id IS NOT NULL OR (status IN ('PENDING','REJECTED') AND requested_city IS NOT NULL)", schema='samaj')


def downgrade() -> None:
    # fails while cityless registrations exist: approve or delete them first
    op.drop_constraint('ck_member_3', 'member', schema='samaj')
    op.alter_column('household', 'city_id', nullable=False, schema='samaj')
    op.alter_column('member', 'city_id', nullable=False, schema='samaj')
    op.drop_column('member', 'requested_state', schema='samaj')
    op.drop_column('member', 'requested_city', schema='samaj')
