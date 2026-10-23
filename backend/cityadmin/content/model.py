from sqlalchemy import (
    CheckConstraint, Column, DateTime, FetchedValue, ForeignKey, Index, SmallInteger, String, Text, Uuid, case,
    func, text,
)

from core.database import Base
import superadmin.city.model  # noqa: F401  registers city and admin_user for the FKs
import superadmin.city_admin.model  # noqa: F401

_now = text("now()")


class ContentItem(Base):
    """News item or ad campaign (SF-07). city_id NULL = every city (Super Admin only)."""
    __tablename__ = "content_item"
    __table_args__ = (
        CheckConstraint("content_type IN ('NEWS','AD')", name="ck_content_item_content_type"),
        CheckConstraint("creative_format IN ('BANNER','FULLSCREEN')", name="ck_content_item_creative_format"),
        CheckConstraint("status IN ('DRAFT','SCHEDULED','LIVE','EXPIRED','CANCELLED')", name="ck_content_item_status"),
        CheckConstraint("end_at > start_at", name="ck_content_item_1"),
        CheckConstraint("content_type = 'NEWS' OR (creative_format IS NOT NULL AND media_key IS NOT NULL)",
                        name="ck_content_item_2"),
        CheckConstraint("creative_format IS DISTINCT FROM 'FULLSCREEN' OR (media_width = 1080 AND media_height = 1920)",
                        name="ck_content_item_3"),
        CheckConstraint("content_type = 'AD' OR body IS NOT NULL", name="ck_content_item_4"),
        Index("ix_content_item_feed", "status", "city_id", text("start_at DESC"),
              postgresql_where=text("status = 'LIVE'")),
        Index("ix_content_item_due", "start_at", postgresql_where=text("status = 'SCHEDULED'")),
        Index("ix_content_item_expiring", "end_at", postgresql_where=text("status = 'LIVE'")),
        Index("ix_content_item_city", "city_id"),
        Index("ix_content_item_created_by", "created_by_admin_id"),
    )

    content_id = Column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    content_type = Column(String(4), nullable=False)  # NEWS | AD
    city_id = Column(Uuid, ForeignKey("samaj.city.city_id", ondelete="RESTRICT"))
    title = Column(String(200), nullable=False)
    body = Column(Text)
    media_key = Column(String(255))
    creative_format = Column(String(10))  # BANNER | FULLSCREEN, ads only
    media_width = Column(SmallInteger)
    media_height = Column(SmallInteger)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(20), nullable=False, server_default="DRAFT")
    created_by_admin_id = Column(Uuid, ForeignKey("samaj.admin_user.admin_id", ondelete="RESTRICT"), nullable=False)
    published_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=_now, server_onupdate=FetchedValue())


# FR-47: a SCHEDULED item is LIVE between start_at and end_at and EXPIRED after, worked out at read time.
# ponytail: stored status never becomes LIVE/EXPIRED and published_at stays NULL; a job that flips them
# (using ix_content_item_due/_expiring) comes with the NEWS_LIVE push (SF-08).
effective_status = case(
    (ContentItem.status != "SCHEDULED", ContentItem.status),
    (ContentItem.end_at <= func.now(), "EXPIRED"),
    (ContentItem.start_at <= func.now(), "LIVE"),
    else_="SCHEDULED",
).label("effective_status")
