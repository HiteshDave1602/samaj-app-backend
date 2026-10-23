"""admin_user role/city check + one active City Admin per city (FR-70)

Revision ID: c3d8f5e1a2b6
Revises: b7e1c2a9d4f0
Create Date: 2026-10-14 12:30:00

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'c3d8f5e1a2b6'
down_revision: Union[str, Sequence[str], None] = 'b7e1c2a9d4f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        'ck_admin_user_role', 'admin_user', "role IN ('SUPER_ADMIN','CITY_ADMIN')", schema='samaj')
    op.create_check_constraint(
        'ck_admin_user_status', 'admin_user', "status IN ('ACTIVE','SUSPENDED','DEACTIVATED')", schema='samaj')
    op.create_check_constraint(
        'ck_admin_user_1', 'admin_user',
        "(role = 'SUPER_ADMIN' AND city_id IS NULL) OR (role = 'CITY_ADMIN' AND city_id IS NOT NULL)",
        schema='samaj')
    op.execute(
        "CREATE UNIQUE INDEX ux_admin_user_one_city_admin ON samaj.admin_user (city_id) "
        "WHERE role = 'CITY_ADMIN' AND status = 'ACTIVE'")


def downgrade() -> None:
    op.execute("DROP INDEX samaj.ux_admin_user_one_city_admin")
    op.drop_constraint('ck_admin_user_1', 'admin_user', schema='samaj')
    op.drop_constraint('ck_admin_user_status', 'admin_user', schema='samaj')
    op.drop_constraint('ck_admin_user_role', 'admin_user', schema='samaj')
