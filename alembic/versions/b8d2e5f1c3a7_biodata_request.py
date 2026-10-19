"""biodata request

Revision ID: b8d2e5f1c3a7
Revises: a1f4c7e2b9d6
Create Date: 2026-10-17 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b8d2e5f1c3a7'
down_revision: Union[str, Sequence[str], None] = 'a1f4c7e2b9d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('biodata_request',
    sa.Column('request_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('requester_profile_id', sa.Uuid(), nullable=False),
    sa.Column('recipient_profile_id', sa.Uuid(), nullable=False),
    sa.Column('pair_low', sa.Uuid(), sa.Computed('LEAST(requester_profile_id, recipient_profile_id)', persisted=True),
              nullable=False),
    sa.Column('pair_high', sa.Uuid(),
              sa.Computed('GREATEST(requester_profile_id, recipient_profile_id)', persisted=True), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='PENDING', nullable=False),
    sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('resend_allowed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('withdrawn_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('withdrawn_by_profile_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('PENDING','ACCEPTED','DECLINED','WITHDRAWN')", name='ck_biodata_request_status'),
    sa.CheckConstraint('requester_profile_id <> recipient_profile_id', name='ck_biodata_request_1'),
    sa.CheckConstraint("status = 'PENDING' OR responded_at IS NOT NULL", name='ck_biodata_request_2'),
    sa.CheckConstraint("status <> 'WITHDRAWN' OR (withdrawn_at IS NOT NULL AND withdrawn_by_profile_id IS NOT NULL)",
                       name='ck_biodata_request_3'),
    sa.ForeignKeyConstraint(['requester_profile_id'], ['samaj.matrimony_profile.profile_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['recipient_profile_id'], ['samaj.matrimony_profile.profile_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['withdrawn_by_profile_id'], ['samaj.matrimony_profile.profile_id'],
                            ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('request_id'),
    schema='samaj'
    )
    op.create_index('ux_biodata_request_open_pair', 'biodata_request', ['pair_low', 'pair_high'], unique=True,
                    schema='samaj', postgresql_where=sa.text("status IN ('PENDING','ACCEPTED')"))
    op.create_index('ix_biodata_request_recipient', 'biodata_request',
                    ['recipient_profile_id', 'status', sa.literal_column('created_at DESC')], schema='samaj')
    op.create_index('ix_biodata_request_requester', 'biodata_request',
                    ['requester_profile_id', sa.literal_column('created_at DESC')], schema='samaj')
    op.create_index('ix_biodata_request_declined_pair', 'biodata_request',
                    ['pair_low', 'pair_high', 'resend_allowed_at'], schema='samaj',
                    postgresql_where=sa.text("status = 'DECLINED'"))
    op.create_index('ix_biodata_request_withdrawn_by', 'biodata_request', ['withdrawn_by_profile_id'],
                    schema='samaj')


def downgrade() -> None:
    op.drop_table('biodata_request', schema='samaj')  # its indexes go with it
