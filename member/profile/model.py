from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, FetchedValue, ForeignKey, Index, Integer, LargeBinary, String,
    UniqueConstraint, Uuid, text,
)

from core.database import Base
import superadmin.city.model  # noqa: F401  registers city for the FKs
import superadmin.city_admin.model  # noqa: F401  registers admin_user for reviewed_by_admin_id

_uuid = text("gen_random_uuid()")
_now = text("now()")


class Household(Base):
    __tablename__ = "household"
    __table_args__ = (
        Index("ix_household_city", "city_id"),
        Index("ix_household_family_name_trgm", "family_name", postgresql_using="gin",
              postgresql_ops={"family_name": "gin_trgm_ops"}),  # directory family search (FR-65)
    )

    household_id = Column(Uuid, primary_key=True, server_default=_uuid)
    city_id = Column(Uuid, ForeignKey("samaj.city.city_id", ondelete="RESTRICT"), nullable=False)
    family_name = Column(String(120), nullable=False)
    native_place = Column(String(120))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=_now, server_onupdate=FetchedValue())


class Member(Base):
    """Lifecycle: PENDING -> ACTIVE / REJECTED -> ARCHIVED -> purged (anonymised)."""
    __tablename__ = "member"
    __table_args__ = (
        CheckConstraint("gender IN ('MALE','FEMALE','OTHER')", name="ck_member_gender"),
        CheckConstraint("status IN ('PENDING','ACTIVE','REJECTED','ARCHIVED')", name="ck_member_status"),
        CheckConstraint("source IN ('APP','IMPORT')", name="ck_member_source"),
        CheckConstraint("status <> 'REJECTED' OR rejection_reason IS NOT NULL", name="ck_member_1"),
        CheckConstraint("dob <= CURRENT_DATE", name="ck_member_2"),
        Index("ix_member_city_status", "city_id", "status", "created_at"),
        Index("ix_member_household", "household_id"),
        Index("ux_member_one_head", "household_id", unique=True, postgresql_where=text("is_household_head")),
        Index("ix_member_reviewed_by", "reviewed_by_admin_id"),
        Index("ix_member_name_trgm", "full_name", postgresql_using="gin", postgresql_ops={"full_name": "gin_trgm_ops"},
              postgresql_where=text("status = 'ACTIVE' AND deleted_at IS NULL")),  # directory name search (FR-65)
    )

    member_id = Column(Uuid, primary_key=True, server_default=_uuid)
    city_id = Column(Uuid, ForeignKey("samaj.city.city_id", ondelete="RESTRICT"), nullable=False)
    household_id = Column(Uuid, ForeignKey("samaj.household.household_id", ondelete="SET NULL"))
    is_household_head = Column(Boolean, nullable=False, server_default=text("false"))
    # The number is never stored in clear: Fernet-encrypted copy, HMAC for lookups, last 4 for display.
    mobile_enc = Column(LargeBinary)
    mobile_hash = Column(LargeBinary, nullable=False, unique=True)
    mobile_last4 = Column(String(4))
    full_name = Column(String(120))
    gender = Column(String(10))  # MALE | FEMALE | OTHER
    dob = Column(Date)
    address_enc = Column(LargeBinary)
    status = Column(String(20), nullable=False, server_default="PENDING")
    rejection_reason = Column(String(500))
    reviewed_by_admin_id = Column(Uuid, ForeignKey("samaj.admin_user.admin_id", ondelete="SET NULL"))
    reviewed_at = Column(DateTime(timezone=True))
    hide_phone = Column(Boolean, nullable=False, server_default=text("false"))
    hide_address = Column(Boolean, nullable=False, server_default=text("false"))
    notify_news = Column(Boolean, nullable=False, server_default=text("true"))
    source = Column(String(10), nullable=False, server_default="APP")  # APP | IMPORT
    last_login_at = Column(DateTime(timezone=True))
    archive_notice_at = Column(DateTime(timezone=True))
    archived_at = Column(DateTime(timezone=True))
    deleted_at = Column(DateTime(timezone=True))
    erased_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=_now, server_onupdate=FetchedValue())


class Consent(Base):
    """DPDP consent (FR-07). A new notice version adds a row; rows are never overwritten."""
    __tablename__ = "consent"
    __table_args__ = (
        CheckConstraint("purpose IN ('MEMBERSHIP','MATRIMONY','DIRECTORY','NOTIFICATIONS')", name="ck_consent_purpose"),
        CheckConstraint("channel IN ('APP','IMPORT')", name="ck_consent_channel"),
        UniqueConstraint("member_id", "purpose", "notice_version", name="uq_consent_member_id_purpose_notice_version"),
        Index("ix_consent_member", "member_id"),
    )

    consent_id = Column(Uuid, primary_key=True, server_default=_uuid)
    member_id = Column(Uuid, ForeignKey("samaj.member.member_id", ondelete="RESTRICT"), nullable=False)
    purpose = Column(String(30), nullable=False)
    notice_version = Column(String(20), nullable=False)
    granted_at = Column(DateTime(timezone=True), nullable=False, server_default=_now)
    withdrawn_at = Column(DateTime(timezone=True))
    channel = Column(String(10), nullable=False, server_default="APP")


class IdentityDocument(Base):
    """Optional ID uploaded at registration (FR-09). Only the member's City Admin and the Super Admin see it (FR-10)."""
    __tablename__ = "identity_document"
    __table_args__ = (
        CheckConstraint("mime_type IN ('image/jpeg','image/png','application/pdf')",
                        name="ck_identity_document_mime_type"),
        CheckConstraint("size_bytes BETWEEN 1 AND 2097152", name="ck_identity_document_size_bytes"),
        Index("ix_identity_document_member", "member_id"),
        Index("ix_identity_document_reviewed_by", "reviewed_by_admin_id"),
        Index("ix_identity_document_purge", "purge_after", postgresql_where=text("purge_after IS NOT NULL")),
    )

    document_id = Column(Uuid, primary_key=True, server_default=_uuid)
    member_id = Column(Uuid, ForeignKey("samaj.member.member_id", ondelete="CASCADE"), nullable=False)
    storage_key = Column(String(255), nullable=False)  # core.private_files key
    mime_type = Column(String(40), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    reviewed_by_admin_id = Column(Uuid, ForeignKey("samaj.admin_user.admin_id", ondelete="SET NULL"))
    reviewed_at = Column(DateTime(timezone=True))
    purge_after = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_now)


class FamilyMember(Base):
    """A relative added to a household by request (FR-17). In the directory only once APPROVED (FR-18)."""
    __tablename__ = "family_member"
    __table_args__ = (
        CheckConstraint("gender IN ('MALE','FEMALE','OTHER')", name="ck_family_member_gender"),
        CheckConstraint("status IN ('PENDING','APPROVED','REJECTED')", name="ck_family_member_status"),
        CheckConstraint("status <> 'REJECTED' OR rejection_reason IS NOT NULL", name="ck_family_member_1"),
        Index("ix_family_member_household", "household_id", postgresql_where=text("status = 'APPROVED'")),
        Index("ix_family_member_pending", "status", "created_at", postgresql_where=text("status = 'PENDING'")),
        Index("ix_family_member_requested_by", "requested_by_member_id"),
        Index("ix_family_member_linked", "linked_member_id"),
        Index("ix_family_member_reviewed_by", "reviewed_by_admin_id"),
    )

    family_member_id = Column(Uuid, primary_key=True, server_default=_uuid)
    household_id = Column(Uuid, ForeignKey("samaj.household.household_id", ondelete="CASCADE"), nullable=False)
    requested_by_member_id = Column(Uuid, ForeignKey("samaj.member.member_id", ondelete="RESTRICT"), nullable=False)
    linked_member_id = Column(Uuid, ForeignKey("samaj.member.member_id", ondelete="SET NULL"))
    full_name = Column(String(120), nullable=False)
    relationship = Column(String(30), nullable=False)
    gender = Column(String(10))
    dob = Column(Date)
    status = Column(String(20), nullable=False, server_default="PENDING")
    rejection_reason = Column(String(500))
    reviewed_by_admin_id = Column(Uuid, ForeignKey("samaj.admin_user.admin_id", ondelete="SET NULL"))
    reviewed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=_now)
