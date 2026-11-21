"""Super Admin directory import: imported people are family_member rows (no app account) in households keyed by
the family head's name and mobile; they carry phone, address and profile details shown in the directory.

Revision ID: e3a7c9d1b5f2
Revises: b4e8c2f6a1d9
Create Date: 2026-11-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e3a7c9d1b5f2'
down_revision: Union[str, Sequence[str], None] = 'b4e8c2f6a1d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = [('mobile_enc', sa.LargeBinary()), ('address_enc', sa.LargeBinary()), ('gotra', sa.String(120)),
           ('education', sa.String(120)), ('marital_status', sa.String(30)), ('occupation', sa.String(120)),
           ('hobby', sa.String(200)), ('blood_group', sa.String(10))]


def upgrade() -> None:
    op.add_column('household', sa.Column('family_key', sa.String(200)), schema='samaj')
    op.create_index('ux_household_city_family_key', 'household', ['city_id', 'family_key'], unique=True,
                    schema='samaj', postgresql_where=sa.text('family_key IS NOT NULL'))
    op.alter_column('family_member', 'requested_by_member_id', nullable=True, schema='samaj')
    for name, type_ in COLUMNS:
        op.add_column('family_member', sa.Column(name, type_), schema='samaj')
    op.alter_column('import_job', 'city_id', nullable=True, schema='samaj')


def downgrade() -> None:
    op.execute("DELETE FROM samaj.import_job WHERE city_id IS NULL")
    op.alter_column('import_job', 'city_id', nullable=False, schema='samaj')
    for name, _ in COLUMNS:
        op.drop_column('family_member', name, schema='samaj')
    op.execute("DELETE FROM samaj.family_member WHERE requested_by_member_id IS NULL")
    op.alter_column('family_member', 'requested_by_member_id', nullable=False, schema='samaj')
    op.drop_index('ux_household_city_family_key', table_name='household', schema='samaj')
    op.drop_column('household', 'family_key', schema='samaj')
