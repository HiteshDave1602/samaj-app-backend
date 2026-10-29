"""name translations

Revision ID: c5f9d2a7b3e1
Revises: b4e8c1f6a9d2
Create Date: 2026-10-29 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from core.translit import localized

revision: str = 'c5f9d2a7b3e1'
down_revision: Union[str, Sequence[str], None] = 'b4e8c1f6a9d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# table -> (primary key, [(source column, translation column)])
COLUMNS = {
    'member': ('member_id', [('full_name', 'full_name_i18n')]),
    'family_member': ('family_member_id', [('full_name', 'full_name_i18n')]),
    'household': ('household_id', [('family_name', 'family_name_i18n'), ('native_place', 'native_place_i18n')]),
    'city': ('city_id', [('name', 'name_i18n')]),
}


def upgrade() -> None:
    conn = op.get_bind()
    for table, (pk, cols) in COLUMNS.items():
        for src, dst in cols:
            op.add_column(table, sa.Column(dst, JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
                          schema='samaj')
        # backfill: new writes get these from the before_flush hook in member/profile/model.py
        t = sa.table(table, sa.column(pk), *[sa.column(c) for c, _ in cols], *[sa.column(d, JSONB) for _, d in cols],
                     schema='samaj')
        for row in conn.execute(sa.select(t.c[pk], *[t.c[c] for c, _ in cols])).all():
            conn.execute(t.update().where(t.c[pk] == row[0])
                         .values({d: localized(row[i + 1]) for i, (_, d) in enumerate(cols)}))


def downgrade() -> None:
    for table, (_, cols) in COLUMNS.items():
        for _, dst in cols:
            op.drop_column(table, dst, schema='samaj')
