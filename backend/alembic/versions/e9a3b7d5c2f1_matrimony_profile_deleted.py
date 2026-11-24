"""matrimony profile deleted_at: removed by a City Admin or the Super Admin

Revision ID: e9a3b7d5c2f1
Revises: d8f2a6c4e1b9
Create Date: 2026-11-24 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e9a3b7d5c2f1'
down_revision: Union[str, Sequence[str], None] = 'd8f2a6c4e1b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('matrimony_profile', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
                  schema='samaj')


def downgrade() -> None:
    op.drop_column('matrimony_profile', 'deleted_at', schema='samaj')
