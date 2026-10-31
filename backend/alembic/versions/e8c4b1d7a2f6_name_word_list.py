"""name spellings from the word list

Revision ID: e8c4b1d7a2f6
Revises: d6a2b8e4f1c9
Create Date: 2026-10-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from core.translit import localized

revision: str = 'e8c4b1d7a2f6'
down_revision: Union[str, Sequence[str], None] = 'd6a2b8e4f1c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# same columns as c5f9d2a7b3e1_name_translations
COLUMNS = {
    'member': ('member_id', [('full_name', 'full_name_i18n')]),
    'family_member': ('family_member_id', [('full_name', 'full_name_i18n')]),
    'household': ('household_id', [('family_name', 'family_name_i18n'), ('native_place', 'native_place_i18n')]),
    'city': ('city_id', [('name', 'name_i18n')]),
}


def upgrade() -> None:
    # Re-spell only values the letter rules made; anything else is a member's correction and stays.
    conn = op.get_bind()
    for table, (pk, cols) in COLUMNS.items():
        t = sa.table(table, sa.column(pk), *[sa.column(c) for c, _ in cols], *[sa.column(d, JSONB) for _, d in cols],
                     schema='samaj')
        for row in conn.execute(sa.select(t.c[pk], *[t.c[c] for c, _ in cols], *[t.c[d] for _, d in cols])).all():
            values = {}
            for i, (_, dst) in enumerate(cols):
                src, current = row[1 + i], row[1 + len(cols) + i]
                if (current or {}) == localized(src, words=False):
                    values[dst] = localized(src)
            if values:
                conn.execute(t.update().where(t.c[pk] == row[0]).values(values))


def downgrade() -> None:
    pass  # spellings only; the old ones are not worth restoring
