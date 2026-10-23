from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, LargeBinary, String, Uuid, text

from core.database import Base
import member.profile.model  # noqa: F401  registers member for the member_id FK


class AuthSession(Base):
    __tablename__ = "auth_session"
    __table_args__ = (
        Index("ix_auth_session_member", "member_id", postgresql_where=text("revoked_at IS NULL")),
        Index("ix_auth_session_admin", "admin_id", postgresql_where=text("revoked_at IS NULL")),
        Index("ix_auth_session_expires", "expires_at"),
    )

    session_id = Column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    member_id = Column(Uuid, ForeignKey("samaj.member.member_id", ondelete="CASCADE"))
    admin_id = Column(Uuid, ForeignKey("samaj.admin_user.admin_id", ondelete="CASCADE"))
    refresh_token_hash = Column(LargeBinary, nullable=False, unique=True)  # sha256 of the bearer token
    mfa_verified = Column(Boolean, nullable=False, server_default=text("false"))
    device_label = Column(String(80))
    last_activity_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
