"""Member profile details entered at registration (same set the directory import carries on family_member).

Revision ID: b2d6f8a3c1e7
Revises: a2c6e8f4b1d3
Create Date: 2026-11-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b2d6f8a3c1e7'
down_revision: Union[str, Sequence[str], None] = 'a2c6e8f4b1d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = [('gotra', sa.String(120)), ('education', sa.String(120)), ('marital_status', sa.String(30)),
           ('occupation', sa.String(120)), ('hobby', sa.String(200)), ('blood_group', sa.String(10))]


def upgrade() -> None:
    for name, type_ in COLUMNS:
        op.add_column('member', sa.Column(name, type_), schema='samaj')


def downgrade() -> None:
    for name, _ in COLUMNS:
        op.drop_column('member', name, schema='samaj')
