"""auth_session

Revision ID: b7e1c2a9d4f0
Revises: 6010086077cb
Create Date: 2026-10-14 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b7e1c2a9d4f0'
down_revision: Union[str, Sequence[str], None] = '6010086077cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('auth_session',
    sa.Column('session_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('member_id', sa.Uuid(), nullable=True),
    sa.Column('admin_id', sa.Uuid(), nullable=True),
    sa.Column('refresh_token_hash', sa.LargeBinary(), nullable=False),
    sa.Column('mfa_verified', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('device_label', sa.String(length=80), nullable=True),
    sa.Column('last_activity_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['admin_id'], ['samaj.admin_user.admin_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('session_id'),
    sa.UniqueConstraint('refresh_token_hash'),
    sa.CheckConstraint('(member_id IS NULL) <> (admin_id IS NULL)', name='ck_auth_session_1'),
    sa.CheckConstraint('admin_id IS NULL OR mfa_verified', name='ck_auth_session_2'),
    schema='samaj'
    )
    op.execute("CREATE INDEX ix_auth_session_member ON samaj.auth_session (member_id) WHERE revoked_at IS NULL")
    op.execute("CREATE INDEX ix_auth_session_admin ON samaj.auth_session (admin_id) WHERE revoked_at IS NULL")
    op.create_index('ix_auth_session_expires', 'auth_session', ['expires_at'], schema='samaj')


def downgrade() -> None:
    op.drop_table('auth_session', schema='samaj')
