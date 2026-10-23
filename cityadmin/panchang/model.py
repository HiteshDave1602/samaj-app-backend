from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, FetchedValue, ForeignKey, Index, String, UniqueConstraint,
    Uuid, text,
)

from core.database import Base
import superadmin.city_admin.model  # noqa: F401  registers admin_user for the FKs

_uuid = text("gen_random_uuid()")
_now = text("now()")


class PanchangDay(Base):
    """The effective Tithi, Nakshatra and Yoga for a date (SOP §6.4). A manual entry overrides API values (FR-62).
    One reference location per deployment (ASM-05), so location_code is always DEFAULT for now."""
    __tablename__ = "panchang_day"
    __table_args__ = (
        CheckConstraint("source IN ('API','MANUAL')", name="ck_panchang_day_source"),
        CheckConstraint("source = 'API' OR (edited_by_admin_id IS NOT NULL AND verified_against_calendar)",
                        name="ck_panchang_day_1"),
        UniqueConstraint("location_code", "panchang_date", name="uq_panchang_day_location_code_panchang_date"),
        Index("ix_panchang_day_edited_by", "edited_by_admin_id"),
    )

    panchang_id = Column(Uuid, primary_key=True, server_default=_uuid)
    panchang_date = Column(Date, nullable=False)
    location_code = Column(String(20), nullable=False, server_default="DEFAULT")
    tithi = Column(String(40), nullable=False)
    nakshatra = Column(String(40), nullable=False)
    yoga = Column(String(40), nullable=False)
    source = Column(String(6), nullable=False)  # API | MANUAL
    verified_against_calendar = Column(Boolean, nullable=False, server_default=text("false"))
    edited_by_admin_id = Column(Uuid, ForeignKey("samaj.admin_user.admin_id", ondelete="SET NULL"))
    fetched_at = Column(DateTime(timezone=True))
    published_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=_now, server_onupdate=FetchedValue())


class PanchangRevision(Base):
    """Append-only history of every fetch and manual edit: the edit history in the dashboard (FR-62)."""
    __tablename__ = "panchang_revision"
    __table_args__ = (
        CheckConstraint("source IN ('API','MANUAL')", name="ck_panchang_revision_source"),
        Index("ix_panchang_revision_day", "panchang_id", text("created_at DESC")),
        Index("ix_panchang_revision_edited_by", "edited_by_admin_id"),
    )

    revision_id = Column(Uuid, primary_key=True, server_default=_uuid)
    panchang_id = Column(Uuid, ForeignKey("samaj.panchang_day.panchang_id", ondelete="RESTRICT"), nullable=False)
    tithi = Column(String(40), nullable=False)
    nakshatra = Column(String(40), nullable=False)
    yoga = Column(String(40), nullable=False)
    source = Column(String(6), nullable=False)
    edited_by_admin_id = Column(Uuid, ForeignKey("samaj.admin_user.admin_id", ondelete="SET NULL"))
    api_status = Column(String(20))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_now)
