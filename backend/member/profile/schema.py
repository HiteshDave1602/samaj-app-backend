from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

from member.auth.schema import Address, Dob, Gender, Name


class IdDocumentOut(BaseModel):
    mime_type: str
    size_bytes: int
    created_at: datetime


class MemberOut(BaseModel):
    member_id: UUID
    full_name: str | None
    gender: str | None
    dob: date | None
    mobile_last4: str | None
    address: str | None
    city_id: UUID
    city_name: str
    household_id: UUID | None
    family_name: str | None
    native_place: str | None
    is_household_head: bool
    status: str  # PENDING: the app shows only Panchang and News (FR-08)
    rejection_reason: str | None
    hide_phone: bool
    hide_address: bool
    notify_news: bool
    id_document: IdDocumentOut | None  # the file itself is visible to admins only (FR-10)
    created_at: datetime


class MemberUpdate(BaseModel):
    """Send only the fields that change. City and mobile number can't be changed here."""
    full_name: Name | None = None
    gender: Gender | None = None
    dob: Dob | None = None
    address: Address | None = None
    family_name: Name | None = None  # household head only
    native_place: Name | None = None  # household head only; null clears it
    hide_phone: bool | None = None
    hide_address: bool | None = None
    notify_news: bool | None = None

    @field_validator("full_name", "gender", "dob", "address", "family_name", "hide_phone", "hide_address",
                     "notify_news", mode="before")
    @classmethod
    def not_null(cls, v):
        if v is None:  # only runs for fields actually sent, so "absent" stays allowed
            raise ValueError("This field can't be empty")
        return v
