from sqlalchemy import (
    CheckConstraint, Column, DateTime, FetchedValue, ForeignKey, Index, LargeBinary, String, Uuid, text,
)
from sqlalchemy.dialects.postgresql import CITEXT

from core.database import Base
import superadmin.city.model  # noqa: F401  registers the city table for the city_id FK

_uuid = text("gen_random_uuid()")
_now = text("now()")


class AdminUser(Base):
    __tablename__ = "admin_user"
    __table_args__ = (
        CheckConstraint("role IN ('SUPER_ADMIN','CITY_ADMIN')", name="ck_admin_user_role"),
        CheckConstraint("status IN ('ACTIVE','SUSPENDED','DEACTIVATED')", name="ck_admin_user_status"),
        CheckConstraint(
            "(role = 'SUPER_ADMIN' AND city_id IS NULL) OR (role = 'CITY_ADMIN' AND city_id IS NOT NULL)",
            name="ck_admin_user_1",
        ),
        # FR-70: at most one ACTIVE City Admin per city.
        Index(
            "ux_admin_user_one_city_admin", "city_id", unique=True,
            postgresql_where=text("role = 'CITY_ADMIN' AND status = 'ACTIVE'"),
        ),
    )

    admin_id = Column(Uuid, primary_key=True, server_default=_uuid)
    role = Column(String(12), nullable=False)  # SUPER_ADMIN | CITY_ADMIN
    city_id = Column(Uuid, ForeignKey("samaj.city.city_id"))
    full_name = Column(String(120), nullable=False)
    email = Column(CITEXT, nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    totp_secret_enc = Column(LargeBinary)
    mfa_enrolled_at = Column(DateTime(timezone=True))
    status = Column(String(20), nullable=False, server_default="ACTIVE")  # ACTIVE | SUSPENDED | DEACTIVATED
    last_login_at = Column(DateTime(timezone=True))
    deactivated_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_now)
    # set by the trg_set_updated_at trigger in the DB
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=_now, server_onupdate=FetchedValue())
