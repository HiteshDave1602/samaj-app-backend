from logging.config import fileConfig

from alembic import context

from core.config import settings
from core.database import Base, engine
import superadmin.city.model  # noqa: F401  registers tables on Base.metadata
import superadmin.city_admin.model  # noqa: F401
import auth.model  # noqa: F401
import superadmin.audit_log.model  # noqa: F401
import member.profile.model  # noqa: F401
import member.auth.model  # noqa: F401
import cityadmin.content.model  # noqa: F401
import member.matrimony.model  # noqa: F401
import cityadmin.panchang.model  # noqa: F401
import cityadmin.member_import.model  # noqa: F401
import cityadmin.member_export.model  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_name(name, type_, parent_names):
    # only diff our schema; ignore public and anything else in the DB
    if type_ == "schema":
        return name == "samaj"
    # partitions (audit_log_default, security_event_default, later monthly ones) are not models
    return not (type_ == "table" and name.startswith(("audit_log_", "security_event_")))


opts = dict(target_metadata=target_metadata, include_schemas=True, include_name=include_name, compare_server_default=True)


if context.is_offline_mode():
    context.configure(url=settings.database_url, literal_binds=True, dialect_opts={"paramstyle": "named"}, **opts)
    with context.begin_transaction():
        context.run_migrations()
else:
    with engine.connect() as connection:
        context.configure(connection=connection, **opts)
        with context.begin_transaction():
            context.run_migrations()
