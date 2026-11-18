"""news and ad translations

Revision ID: f2b7d9c4e1a8
Revises: e8c4b1d7a2f6
Create Date: 2026-11-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = 'f2b7d9c4e1a8'
down_revision: Union[str, Sequence[str], None] = 'e8c4b1d7a2f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # no backfill: the member feed translates live items that have none yet
    for col in ('title_i18n', 'body_i18n'):
        op.add_column('content_item', sa.Column(col, JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
                      schema='samaj')


def downgrade() -> None:
    for col in ('title_i18n', 'body_i18n'):
        op.drop_column('content_item', col, schema='samaj')
