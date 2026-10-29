"""member language

Revision ID: b4e8c1f6a9d2
Revises: a7d3f9c2e1b8
Create Date: 2026-10-29 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b4e8c1f6a9d2'
down_revision: Union[str, Sequence[str], None] = 'a7d3f9c2e1b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('member', sa.Column('language', sa.String(2), nullable=False, server_default='en'), schema='samaj')
    op.create_check_constraint('ck_member_language', 'member', "language IN ('en','gu','hi')", schema='samaj')


def downgrade() -> None:
    op.drop_constraint('ck_member_language', 'member', schema='samaj')
    op.drop_column('member', 'language', schema='samaj')
