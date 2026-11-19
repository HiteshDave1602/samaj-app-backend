"""otp_challenge per-IP index: the per-IP OTP send limit counts rows by request_ip

Revision ID: b4e8c2f6a1d9
Revises: d3b7f1a9c5e2
Create Date: 2026-11-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b4e8c2f6a1d9'
down_revision: Union[str, Sequence[str], None] = 'd3b7f1a9c5e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_otp_challenge_ip_time', 'otp_challenge', ['request_ip', sa.literal_column('created_at DESC')],
                    unique=False, schema='samaj')


def downgrade() -> None:
    op.drop_index('ix_otp_challenge_ip_time', table_name='otp_challenge', schema='samaj')
