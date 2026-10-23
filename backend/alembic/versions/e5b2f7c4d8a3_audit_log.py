"""audit_log, append-only (FR-86, FR-87)

Revision ID: e5b2f7c4d8a3
Revises: d4a9e6b3c7f1
Create Date: 2026-10-15 12:00:00

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'e5b2f7c4d8a3'
down_revision: Union[str, Sequence[str], None] = 'd4a9e6b3c7f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS samaj.audit_log_audit_id_seq AS BIGINT")
    op.execute("""
        CREATE TABLE samaj.audit_log (
            audit_id      BIGINT NOT NULL DEFAULT nextval('samaj.audit_log_audit_id_seq'),
            occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            actor_type    VARCHAR(8) NOT NULL,
            actor_id      UUID,
            action        VARCHAR(40) NOT NULL,
            target_table  VARCHAR(40),
            target_id     VARCHAR(64),
            city_id       UUID,
            before_state  JSONB,
            after_state   JSONB,
            source_ip     INET,
            request_id    UUID,
            CONSTRAINT pk_audit_log PRIMARY KEY (audit_id, occurred_at),
            CONSTRAINT ck_audit_log_actor_type CHECK (actor_type IN ('ADMIN','MEMBER','SYSTEM'))
        ) PARTITION BY RANGE (occurred_at)
    """)
    # ponytail: one DEFAULT partition holds every row for now. When retention (24 months) matters,
    # add monthly partitions with pg_partman as in the DDD; it moves rows out of the default partition.
    op.execute("CREATE TABLE samaj.audit_log_default PARTITION OF samaj.audit_log DEFAULT")
    op.execute("CREATE INDEX ix_audit_log_occurred ON samaj.audit_log USING brin (occurred_at)")
    op.execute("CREATE INDEX ix_audit_log_actor ON samaj.audit_log (actor_id, occurred_at DESC)")
    op.execute("CREATE INDEX ix_audit_log_city_action ON samaj.audit_log (city_id, action, occurred_at DESC)")
    op.execute("CREATE INDEX ix_audit_log_target ON samaj.audit_log (target_table, target_id)")

    # FR-87: nobody, including the Super Admin or a role granted UPDATE by mistake, can change entries.
    op.execute("""
        CREATE FUNCTION samaj.block_log_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION '% is append-only', TG_TABLE_NAME USING ERRCODE = '42501'; END $$
    """)
    op.execute("""
        CREATE TRIGGER trg_audit_append_only BEFORE UPDATE OR DELETE ON samaj.audit_log
            FOR EACH ROW EXECUTE FUNCTION samaj.block_log_change()
    """)
    # ponytail: TRUNCATE isn't caught by the row trigger. The DDD revokes it from the app roles
    # (samaj_app etc.); do that when those roles are created.


def downgrade() -> None:
    op.execute("DROP TABLE samaj.audit_log")  # drops its partitions and trigger too
    op.execute("DROP FUNCTION samaj.block_log_change()")
    op.execute("DROP SEQUENCE samaj.audit_log_audit_id_seq")
