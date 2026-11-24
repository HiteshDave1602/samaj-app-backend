"""admin requests seen

Revision ID: c4e8a1f6d2b9
Revises: b2d6f8a3c1e7
Create Date: 2026-11-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c4e8a1f6d2b9'
down_revision: Union[str, Sequence[str], None] = 'b2d6f8a3c1e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('admin_user', sa.Column('requests_seen_at', sa.DateTime(timezone=True), nullable=True),
                  schema='samaj')


def downgrade() -> None:
    op.drop_column('admin_user', 'requests_seen_at', schema='samaj')
