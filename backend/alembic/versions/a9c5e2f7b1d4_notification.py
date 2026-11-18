"""notification

Revision ID: a9c5e2f7b1d4
Revises: f2b7d9c4e1a8
Create Date: 2026-11-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a9c5e2f7b1d4'
down_revision: Union[str, Sequence[str], None] = 'f2b7d9c4e1a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('notification',
    sa.Column('notification_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('member_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"),
              nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("kind IN ('ACCOUNT_DECISION','FAMILY_DECISION','PROFILE_DECISION','PHOTO_DECISION',"
                       "'NEWS_DECISION','BIODATA_REQUEST','BIODATA_RESPONSE')", name='ck_notification_kind'),
    sa.ForeignKeyConstraint(['member_id'], ['samaj.member.member_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('notification_id'),
    schema='samaj'
    )
    op.create_index('ix_notification_member', 'notification', ['member_id', sa.literal_column('created_at DESC')],
                    schema='samaj')
    op.add_column('member', sa.Column('notifications_seen_at', sa.DateTime(timezone=True), nullable=True),
                  schema='samaj')


def downgrade() -> None:
    op.drop_column('member', 'notifications_seen_at', schema='samaj')
    op.drop_table('notification', schema='samaj')  # its index goes with it
