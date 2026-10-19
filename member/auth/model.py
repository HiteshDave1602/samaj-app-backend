from sqlalchemy import CheckConstraint, Column, DateTime, Index, LargeBinary, SmallInteger, String, Uuid, text
from sqlalchemy.dialects.postgresql import INET

from core.database import Base


class OtpChallenge(Base):
    """One SMS code. 5-minute expiry, 3 attempts (FR-03); rows per number per hour drive the send limit (FR-04)."""
    __tablename__ = "otp_challenge"
    __table_args__ = (
        CheckConstraint("purpose IN ('LOGIN','REGISTER','ERASURE')", name="ck_otp_challenge_purpose"),
        CheckConstraint("attempts BETWEEN 0 AND 3", name="ck_otp_challenge_attempts"),
        CheckConstraint("expires_at > created_at", name="ck_otp_challenge_1"),
        Index("ix_otp_challenge_mobile_time", "mobile_hash", text("created_at DESC")),
        Index("ix_otp_challenge_created", "created_at", postgresql_using="brin"),
    )

    otp_id = Column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    mobile_hash = Column(LargeBinary, nullable=False)
    purpose = Column(String(12), nullable=False)  # LOGIN | REGISTER | ERASURE
    code_hash = Column(String(255), nullable=False)
    attempts = Column(SmallInteger, nullable=False, server_default=text("0"))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True))
    request_ip = Column(INET)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
