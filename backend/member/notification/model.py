from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB

from core.database import Base
import member.profile.model  # noqa: F401  registers member for the FK

KINDS = ("ACCOUNT_DECISION", "FAMILY_DECISION", "PROFILE_DECISION", "PHOTO_DECISION", "NEWS_DECISION",
         "BIODATA_REQUEST", "BIODATA_RESPONSE")


class Notification(Base):
    """A member's in-app inbox (the bell). Written in the same transaction as the change it reports; the app
    builds the text from kind + payload, so it follows the member's language. Read state is one time per member
    (member.notifications_seen_at), which also covers the live news the bell lists without rows here.
    ponytail: in-app only. Push (SF-08, notification_outbox + worker) can fan these out when it lands."""
    __tablename__ = "notification"
    __table_args__ = (
        CheckConstraint(f"kind IN ({','.join(repr(k) for k in KINDS)})", name="ck_notification_kind"),
        Index("ix_notification_member", "member_id", text("created_at DESC")),
    )

    notification_id = Column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    member_id = Column(Uuid, ForeignKey("samaj.member.member_id", ondelete="CASCADE"), nullable=False)
    kind = Column(String(30), nullable=False)
    payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
