from sqlalchemy import (
    CheckConstraint, Column, Computed, DateTime, FetchedValue, ForeignKey, Index, Integer, LargeBinary, SmallInteger,
    String, UniqueConstraint, Uuid, text,
)

from core.database import Base
import member.profile.model  # noqa: F401  registers member, city and admin_user for the FKs

_uuid = text("gen_random_uuid()")
_now = text("now()")


class MatrimonyProfile(Base):
    """Public summary of a matrimony listing (FR-08, FR-20). Holds no biodata: that lives in its own table,
    which no admin endpoint reads (FR-36)."""
    __tablename__ = "matrimony_profile"
    __table_args__ = (
        CheckConstraint("managed_by IN ('SELF','PARENT','SIBLING','RELATIVE')", name="ck_matrimony_profile_managed_by"),
        CheckConstraint("education_level IN ('SCHOOL','DIPLOMA','GRADUATE','POSTGRADUATE','DOCTORATE','OTHER')",
                        name="ck_matrimony_profile_education_level"),
        CheckConstraint("status IN ('DRAFT','PENDING_MODERATION','APPROVED','REJECTED','ARCHIVED')",
                        name="ck_matrimony_profile_status"),
        CheckConstraint("status <> 'REJECTED' OR moderation_reason IS NOT NULL", name="ck_matrimony_profile_1"),
        Index("ix_matrimony_profile_moderation", "status", "created_at",
              postgresql_where=text("status = 'PENDING_MODERATION'")),
        Index("ix_matrimony_profile_location", "location_city_id"),
        Index("ix_matrimony_profile_moderated_by", "moderated_by_admin_id"),
    )

    profile_id = Column(Uuid, primary_key=True, server_default=_uuid)
    member_id = Column(Uuid, ForeignKey("samaj.member.member_id", ondelete="RESTRICT"), nullable=False, unique=True)
    location_city_id = Column(Uuid, ForeignKey("samaj.city.city_id", ondelete="RESTRICT"), nullable=False)
    managed_by = Column(String(10), nullable=False, server_default="SELF")
    education_level = Column(String(20), nullable=False)
    education_detail = Column(String(120))
    occupation = Column(String(80))
    gotra = Column(String(60))  # gotra and height are public, unlike the biodata's copies
    height_cm = Column(SmallInteger, CheckConstraint("height_cm BETWEEN 100 AND 250", name="ck_matrimony_profile_height"))
    family_background = Column(String(20), nullable=False)
    about = Column(String(500))
    status = Column(String(20), nullable=False, server_default="DRAFT")
    moderation_reason = Column(String(500))
    moderated_by_admin_id = Column(Uuid, ForeignKey("samaj.admin_user.admin_id", ondelete="SET NULL"))
    moderated_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=_now, server_onupdate=FetchedValue())


class Biodata(Base):
    """Private biodata (FR-20): one encrypted JSON document per profile. Readable by its owner, and by the other
    side of an ACCEPTED biodata request (SF-06). Never by admins (FR-36).
    ponytail: Fernet in the app, not the DDD's KMS key + SECURITY DEFINER get_biodata(); key_id marks which."""
    __tablename__ = "biodata"

    profile_id = Column(Uuid, ForeignKey("samaj.matrimony_profile.profile_id", ondelete="CASCADE"), primary_key=True)
    payload_enc = Column(LargeBinary, nullable=False)
    key_id = Column(String(64), nullable=False)
    schema_version = Column(SmallInteger, nullable=False, server_default=text("1"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=_now, server_onupdate=FetchedValue())


class BiodataRequest(Base):
    """User A asks User B to exchange biodata (SF-06). Only ACCEPTED grants access, to that pair only (FR-33).
    pair_low/pair_high make the pair direction-independent: one open request per pair either way (FR-30)."""
    __tablename__ = "biodata_request"
    __table_args__ = (
        CheckConstraint("status IN ('PENDING','ACCEPTED','DECLINED','WITHDRAWN')", name="ck_biodata_request_status"),
        CheckConstraint("requester_profile_id <> recipient_profile_id", name="ck_biodata_request_1"),
        CheckConstraint("status = 'PENDING' OR responded_at IS NOT NULL", name="ck_biodata_request_2"),
        CheckConstraint("status <> 'WITHDRAWN' OR (withdrawn_at IS NOT NULL AND withdrawn_by_profile_id IS NOT NULL)",
                        name="ck_biodata_request_3"),
        Index("ux_biodata_request_open_pair", "pair_low", "pair_high", unique=True,
              postgresql_where=text("status IN ('PENDING','ACCEPTED')")),
        Index("ix_biodata_request_recipient", "recipient_profile_id", "status", text("created_at DESC")),
        Index("ix_biodata_request_requester", "requester_profile_id", text("created_at DESC")),
        Index("ix_biodata_request_declined_pair", "pair_low", "pair_high", "resend_allowed_at",
              postgresql_where=text("status = 'DECLINED'")),
        Index("ix_biodata_request_withdrawn_by", "withdrawn_by_profile_id"),
    )

    request_id = Column(Uuid, primary_key=True, server_default=_uuid)
    requester_profile_id = Column(Uuid, ForeignKey("samaj.matrimony_profile.profile_id", ondelete="CASCADE"),
                                  nullable=False)
    recipient_profile_id = Column(Uuid, ForeignKey("samaj.matrimony_profile.profile_id", ondelete="CASCADE"),
                                  nullable=False)
    pair_low = Column(Uuid, Computed("LEAST(requester_profile_id, recipient_profile_id)", persisted=True),
                      nullable=False)
    pair_high = Column(Uuid, Computed("GREATEST(requester_profile_id, recipient_profile_id)", persisted=True),
                       nullable=False)
    status = Column(String(20), nullable=False, server_default="PENDING")
    responded_at = Column(DateTime(timezone=True))
    resend_allowed_at = Column(DateTime(timezone=True))  # responded_at + 30 days when DECLINED (FR-39)
    withdrawn_at = Column(DateTime(timezone=True))
    withdrawn_by_profile_id = Column(Uuid, ForeignKey("samaj.matrimony_profile.profile_id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_now)


class MatrimonyPhoto(Base):
    """Moderated before it is shown (FR-23). At most 5 per profile."""
    __tablename__ = "matrimony_photo"
    __table_args__ = (
        CheckConstraint("mime_type IN ('image/jpeg','image/png')", name="ck_matrimony_photo_mime_type"),
        CheckConstraint("size_bytes BETWEEN 1 AND 2097152", name="ck_matrimony_photo_size_bytes"),
        CheckConstraint("sort_order BETWEEN 1 AND 5", name="ck_matrimony_photo_sort_order"),
        CheckConstraint("status IN ('PENDING','APPROVED','REJECTED')", name="ck_matrimony_photo_status"),
        CheckConstraint("status <> 'REJECTED' OR rejection_reason IS NOT NULL", name="ck_matrimony_photo_1"),
        UniqueConstraint("profile_id", "sort_order", name="uq_matrimony_photo_profile_id_sort_order"),
        Index("ix_matrimony_photo_pending", "created_at", postgresql_where=text("status = 'PENDING'")),
        Index("ix_matrimony_photo_moderated_by", "moderated_by_admin_id"),
    )

    photo_id = Column(Uuid, primary_key=True, server_default=_uuid)
    profile_id = Column(Uuid, ForeignKey("samaj.matrimony_profile.profile_id", ondelete="CASCADE"), nullable=False)
    storage_key = Column(String(255), nullable=False)  # core.private_files key
    mime_type = Column(String(20), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sort_order = Column(SmallInteger, nullable=False)
    status = Column(String(20), nullable=False, server_default="PENDING")
    rejection_reason = Column(String(500))
    moderated_by_admin_id = Column(Uuid, ForeignKey("samaj.admin_user.admin_id", ondelete="SET NULL"))
    moderated_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_now)
