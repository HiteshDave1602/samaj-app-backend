"""member news submissions

Revision ID: a7d3e9f1c2b6
Revises: c5f9d2a7b3e1
Create Date: 2026-10-29 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a7d3e9f1c2b6'
down_revision: Union[str, Sequence[str], None] = 'c5f9d2a7b3e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('content_item', sa.Column('extra_media_keys', sa.ARRAY(sa.String(length=255)),
                                            server_default='{}', nullable=False), schema='samaj')
    op.add_column('content_item', sa.Column('created_by_member_id', sa.Uuid(), nullable=True), schema='samaj')
    op.create_foreign_key('content_item_created_by_member_id_fkey', 'content_item', 'member',
                          ['created_by_member_id'], ['member_id'], source_schema='samaj', referent_schema='samaj',
                          ondelete='RESTRICT')
    op.alter_column('content_item', 'created_by_admin_id', nullable=True, schema='samaj')
    op.create_check_constraint('ck_content_item_5', 'content_item',
                               'num_nonnulls(created_by_admin_id, created_by_member_id) = 1', schema='samaj')
    op.drop_constraint('ck_content_item_status', 'content_item', schema='samaj')
    op.create_check_constraint(
        'ck_content_item_status', 'content_item',
        "status IN ('DRAFT','PENDING','SCHEDULED','LIVE','EXPIRED','CANCELLED','REJECTED')", schema='samaj')


def downgrade() -> None:
    op.execute("DELETE FROM samaj.content_item WHERE created_by_member_id IS NOT NULL")
    op.drop_constraint('ck_content_item_status', 'content_item', schema='samaj')
    op.create_check_constraint('ck_content_item_status', 'content_item',
                               "status IN ('DRAFT','SCHEDULED','LIVE','EXPIRED','CANCELLED')", schema='samaj')
    op.drop_constraint('ck_content_item_5', 'content_item', schema='samaj')
    op.alter_column('content_item', 'created_by_admin_id', nullable=False, schema='samaj')
    op.drop_constraint('content_item_created_by_member_id_fkey', 'content_item', schema='samaj')
    op.drop_column('content_item', 'created_by_member_id', schema='samaj')
    op.drop_column('content_item', 'extra_media_keys', schema='samaj')
