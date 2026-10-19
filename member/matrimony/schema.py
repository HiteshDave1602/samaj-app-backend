from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from member.auth.schema import Mobile
from superadmin.city_admin.schema import Email

ManagedBy = Literal["SELF", "PARENT", "SIBLING", "RELATIVE"]  # FR-21
EducationLevel = Literal["SCHOOL", "DIPLOMA", "GRADUATE", "POSTGRADUATE", "DOCTORATE", "OTHER"]
# ponytail: placeholder bands; the DDD leaves family_background values to the Samaj bylaws (OQ-12).
FamilyBackground = Literal["JOINT", "NUCLEAR", "OTHER"]


def _text(n: int):
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=n)]


class ProfileCreate(BaseModel):
    location_city_id: UUID | None = None  # defaults to the member's city
    managed_by: ManagedBy = "SELF"
    education_level: EducationLevel
    education_detail: _text(120) | None = None
    occupation: _text(80) | None = None
    family_background: FamilyBackground
    about: _text(500) | None = None  # public, so the City Admin reviews it with the photos


class ProfileUpdate(BaseModel):
    """Send only the fields that change; null clears an optional one."""
    location_city_id: UUID | None = None
    managed_by: ManagedBy | None = None
    education_level: EducationLevel | None = None
    education_detail: _text(120) | None = None
    occupation: _text(80) | None = None
    family_background: FamilyBackground | None = None
    about: _text(500) | None = None

    @field_validator("location_city_id", "managed_by", "education_level", "family_background", mode="before")
    @classmethod
    def not_null(cls, v):
        if v is None:
            raise ValueError("This field can't be empty")
        return v


class MyPhotoOut(BaseModel):
    photo_id: UUID
    sort_order: int
    status: str  # PENDING | APPROVED | REJECTED; only APPROVED is shown to others
    rejection_reason: str | None  # FR-23: shown to the member
    file_url: str  # needs the member's Bearer token
    created_at: datetime


class MyProfileOut(BaseModel):
    profile_id: UUID
    full_name: str | None  # name, gender and age come from the member record
    gender: str | None
    age: int | None
    location_city_id: UUID
    managed_by: str
    education_level: str
    education_detail: str | None
    occupation: str | None
    family_background: str
    about: str | None
    status: str  # DRAFT | PENDING_MODERATION | APPROVED | REJECTED | ARCHIVED
    moderation_reason: str | None
    photos: list[MyPhotoOut]
    has_biodata: bool
    created_at: datetime
    updated_at: datetime


# Search results (FR-26): public summary only. No name, biodata or contact fields -- by contract, nothing
# beyond what the DDD's matrimony_search_mv carries.
class ProfileCard(BaseModel):
    profile_id: UUID
    gender: str | None
    age: int | None
    education_level: str
    education_detail: str | None
    occupation: str | None
    family_background: str
    location_city_id: UUID
    location_city_name: str
    managed_by: str
    cover_photo_url: str | None  # first approved photo


class SearchPage(BaseModel):
    items: list[ProfileCard]
    next_after: UUID | None  # pass as ?after= for the next page; null on the last page


class PublicPhotoOut(BaseModel):
    photo_id: UUID
    sort_order: int
    file_url: str


class RequestState(BaseModel):
    """The latest biodata request between you and a profile; drives the Request / Pending / View Biodata button."""
    request_id: UUID
    status: str  # PENDING | ACCEPTED | DECLINED | WITHDRAWN
    sent_by_me: bool
    resend_allowed_at: datetime | None  # after a decline: when you may ask again (FR-39)


class PublicProfileOut(ProfileCard):
    about: str | None
    photos: list[PublicPhotoOut]  # approved only
    biodata_request: RequestState | None  # null: never asked; ACCEPTED: GET /profiles/{id}/biodata works


# ponytail: field set v1 is a guess at a typical Samaj biodata; the DDD leaves it open (OQ-12).
# Bump BIODATA_SCHEMA_VERSION when it changes.
class BiodataIn(BaseModel):
    """PUT replaces the whole biodata; omitted fields are cleared."""
    model_config = ConfigDict(extra="forbid")

    height_cm: int | None = Field(None, ge=100, le=250)
    diet: Literal["VEG", "NON_VEG", "EGGETARIAN", "JAIN", "VEGAN"] | None = None
    birth_time: Annotated[str, StringConstraints(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")] | None = None  # HH:MM
    birth_place: _text(120) | None = None
    rashi: _text(40) | None = None
    nakshatra: _text(40) | None = None
    gotra: _text(60) | None = None
    manglik: Literal["YES", "NO", "ANSHIK", "DONT_KNOW"] | None = None
    father_name: _text(120) | None = None
    father_occupation: _text(120) | None = None
    mother_name: _text(120) | None = None
    mother_occupation: _text(120) | None = None
    siblings: _text(300) | None = None
    annual_income: _text(60) | None = None
    residence_address: _text(500) | None = None
    contact_phone: Mobile | None = None
    contact_email: Email | None = None
    expectations: _text(1000) | None = None


class BiodataOut(BiodataIn):
    model_config = ConfigDict(extra="ignore")
    updated_at: datetime
