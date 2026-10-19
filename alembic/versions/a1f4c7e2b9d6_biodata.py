"""biodata

Revision ID: a1f4c7e2b9d6
Revises: 040e047bf82f
Create Date: 2026-10-17 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1f4c7e2b9d6'
down_revision: Union[str, Sequence[str], None] = '040e047bf82f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('biodata',
    sa.Column('profile_id', sa.Uuid(), nullable=False),
    sa.Column('payload_enc', sa.LargeBinary(), nullable=False),
    sa.Column('key_id', sa.String(length=64), nullable=False),
    sa.Column('schema_version', sa.SmallInteger(), server_default=sa.text('1'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['profile_id'], ['samaj.matrimony_profile.profile_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('profile_id'),
    schema='samaj'
    )
    op.execute("CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON samaj.biodata "
               "FOR EACH ROW EXECUTE FUNCTION samaj.set_updated_at()")


def downgrade() -> None:
    op.drop_table('biodata', schema='samaj')
