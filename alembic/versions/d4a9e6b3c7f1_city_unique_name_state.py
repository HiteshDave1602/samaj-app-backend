"""city unique (name, state)

Revision ID: d4a9e6b3c7f1
Revises: c3d8f5e1a2b6
Create Date: 2026-10-14 13:00:00

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'd4a9e6b3c7f1'
down_revision: Union[str, Sequence[str], None] = 'c3d8f5e1a2b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint('uq_city_name_state', 'city', ['name', 'state'], schema='samaj')


def downgrade() -> None:
    op.drop_constraint('uq_city_name_state', 'city', schema='samaj')
