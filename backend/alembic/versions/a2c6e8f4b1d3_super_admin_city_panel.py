"""Super Admin second password for the City Admin panel; session remembers panel + chosen city

Revision ID: a2c6e8f4b1d3
Revises: f8a1c3e5b7d9
Create Date: 2026-11-21 12:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a2c6e8f4b1d3'
down_revision: Union[str, Sequence[str], None] = 'f8a1c3e5b7d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('admin_user', sa.Column('city_panel_password_hash', sa.String(255)), schema='samaj')
    op.add_column('auth_session', sa.Column('city_panel', sa.Boolean(), nullable=False, server_default=sa.false()),
                  schema='samaj')
    op.add_column('auth_session', sa.Column(
        'acting_city_id', sa.Uuid(), sa.ForeignKey('samaj.city.city_id', ondelete='SET NULL')), schema='samaj')


def downgrade() -> None:
    op.drop_column('auth_session', 'acting_city_id', schema='samaj')
    op.drop_column('auth_session', 'city_panel', schema='samaj')
    op.drop_column('admin_user', 'city_panel_password_hash', schema='samaj')
