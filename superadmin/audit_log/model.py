from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, Index, String, Uuid, text
from sqlalchemy.dialects.postgresql import INET, JSONB

from core.database import Base


class AuditLog(Base):
    """Append-only (FR-87): a DB trigger rejects UPDATE/DELETE. No FKs, so rows outlive what they describe."""
    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint("actor_type IN ('ADMIN','MEMBER','SYSTEM')", name="ck_audit_log_actor_type"),
        Index("ix_audit_log_occurred", "occurred_at", postgresql_using="brin"),
        Index("ix_audit_log_actor", "actor_id", text("occurred_at DESC")),
        Index("ix_audit_log_city_action", "city_id", "action", text("occurred_at DESC")),
        Index("ix_audit_log_target", "target_table", "target_id"),
        {"postgresql_partition_by": "RANGE (occurred_at)"},
    )

    audit_id = Column(BigInteger, primary_key=True, server_default=text("nextval('samaj.audit_log_audit_id_seq')"))
    occurred_at = Column(DateTime(timezone=True), primary_key=True, server_default=text("now()"))
    actor_type = Column(String(8), nullable=False)  # ADMIN | MEMBER | SYSTEM
    actor_id = Column(Uuid)
    action = Column(String(40), nullable=False)
    target_table = Column(String(40))
    target_id = Column(String(64))
    city_id = Column(Uuid)
    before_state = Column(JSONB)  # changed fields only; never passwords, secrets or biodata
    after_state = Column(JSONB)
    source_ip = Column(INET)
    request_id = Column(Uuid)


class SecurityEvent(Base):
    """Denied access (cross-city 403s, ID documents, biodata). Append-only, like audit_log."""
    __tablename__ = "security_event"
    __table_args__ = (
        CheckConstraint("event_type IN ('BIODATA_DENIED','CROSS_CITY_DENIED','ID_DOC_DENIED','OTP_LOCKED',"
                        "'OTP_RATE_LIMIT','MFA_FAILED','TOKEN_REUSE')", name="ck_security_event_event_type"),
        CheckConstraint("actor_type IN ('ADMIN','MEMBER','ANONYMOUS')", name="ck_security_event_actor_type"),
        Index("ix_security_event_occurred", "occurred_at", postgresql_using="brin"),
        Index("ix_security_event_type", "event_type", text("occurred_at DESC")),
        Index("ix_security_event_actor", "actor_id", text("occurred_at DESC")),
        {"postgresql_partition_by": "RANGE (occurred_at)"},
    )

    event_id = Column(BigInteger, primary_key=True,
                      server_default=text("nextval('samaj.security_event_event_id_seq')"))
    occurred_at = Column(DateTime(timezone=True), primary_key=True, server_default=text("now()"))
    event_type = Column(String(30), nullable=False)
    actor_type = Column(String(8), nullable=False)  # ADMIN | MEMBER | ANONYMOUS
    actor_id = Column(Uuid)
    endpoint = Column(String(120), nullable=False)
    target_id = Column(String(64))
    reason = Column(String(200))
    source_ip = Column(INET)
