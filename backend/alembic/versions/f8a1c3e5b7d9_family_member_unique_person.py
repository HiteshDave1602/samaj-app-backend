"""family_member: one live entry per person (name + date of birth) per household

member/family/curd.request_addition checked for this before inserting, but two identical requests sent at the same
moment both passed the check. The partial unique index makes the database the referee; REJECTED rows don't count,
so a rejected request can still be sent again, and rows without a date of birth (directory imports) are left out.

Existing duplicates are NOT changed: the upgrade stops and lists how to find them, for a person to merge by hand.

Revision ID: f8a1c3e5b7d9
Revises: e3a7c9d1b5f2
Create Date: 2026-11-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f8a1c3e5b7d9'
down_revision: Union[str, Sequence[str], None] = 'e3a7c9d1b5f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LIVE = "status <> 'REJECTED' AND dob IS NOT NULL"
DUPLICATES = (f"SELECT household_id, lower(full_name) AS name, dob, count(*) FROM samaj.family_member WHERE {LIVE} "
              "GROUP BY 1, 2, 3 HAVING count(*) > 1")


def upgrade() -> None:
    found = op.get_bind().execute(sa.text(f"SELECT count(*) FROM ({DUPLICATES}) d")).scalar()
    if found:
        raise RuntimeError(f"{found} households list the same person twice. Merge or reject the extra rows, then "
                           f"run the upgrade again. Find them with:\n{DUPLICATES}")
    op.create_index('ux_family_member_person', 'family_member',
                    ['household_id', sa.literal_column('lower(full_name)'), 'dob'],
                    unique=True, schema='samaj', postgresql_where=sa.text(LIVE))


def downgrade() -> None:
    op.drop_index('ux_family_member_person', table_name='family_member', schema='samaj')
