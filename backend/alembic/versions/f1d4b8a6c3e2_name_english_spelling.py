"""English spelling for names and places typed in Gujarati or Hindi

Revision ID: f1d4b8a6c3e2
Revises: e9a3b7d5c2f1
Create Date: 2026-11-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from core.translit import localized

revision: str = 'f1d4b8a6c3e2'
down_revision: Union[str, Sequence[str], None] = 'e9a3b7d5c2f1'
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
    # Adds only the "en" key; the stored gu/hi (auto or a member's correction) stay as they are.
    conn = op.get_bind()
    for table, (pk, cols) in COLUMNS.items():
        t = sa.table(table, sa.column(pk), *[sa.column(c) for c, _ in cols], *[sa.column(d, JSONB) for _, d in cols],
                     schema='samaj')
        for row in conn.execute(sa.select(t.c[pk], *[t.c[c] for c, _ in cols], *[t.c[d] for _, d in cols])).all():
            values = {}
            for i, (_, dst) in enumerate(cols):
                src, current = row[1 + i], row[1 + len(cols) + i] or {}
                if src and 'en' not in current:
                    values[dst] = {**current, 'en': localized(src)['en']}
            if values:
                conn.execute(t.update().where(t.c[pk] == row[0]).values(values))


def downgrade() -> None:
    pass  # an extra key the old code ignores
