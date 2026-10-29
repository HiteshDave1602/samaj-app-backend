from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# Public summary only. Biodata is never part of any admin response (FR-36), so it has no field here.
class ProfileListItem(BaseModel):
    profile_id: UUID
    member_id: UUID
    full_name: str | None
    gender: str | None
    age: int | None
    education_level: str
    occupation: str | None
    family_background: str
    managed_by: str  # SELF | PARENT | SIBLING | RELATIVE (FR-21)
    status: str  # DRAFT | PENDING_MODERATION | APPROVED | REJECTED | ARCHIVED
    pending_photo_count: int
    created_at: datetime
    updated_at: datetime


class ProfilePage(BaseModel):
    total: int
    items: list[ProfileListItem]


class PhotoOut(BaseModel):
    photo_id: UUID
    sort_order: int
    status: str  # PENDING | APPROVED | REJECTED
    rejection_reason: str | None
    mime_type: str
    size_bytes: int
    file_url: str  # admin-only; needs the same Bearer token
    moderated_by_admin_id: UUID | None
    moderated_at: datetime | None
    created_at: datetime


class ProfileOut(ProfileListItem):
    location_city_id: UUID
    education_detail: str | None
    about: str | None
    moderation_reason: str | None
    moderated_by_admin_id: UUID | None
    moderated_at: datetime | None
    photos: list[PhotoOut]


class Decision(BaseModel):
    occurred_at: datetime
    action: str  # MATRIMONY_APPROVE | MATRIMONY_REJECT | PHOTO_APPROVE | PHOTO_REJECT
    admin_name: str | None
    profile_id: UUID | None  # None once the profile is gone
    full_name: str | None
    reason: str | None  # rejections only


class DecisionPage(BaseModel):
    total: int
    items: list[Decision]
