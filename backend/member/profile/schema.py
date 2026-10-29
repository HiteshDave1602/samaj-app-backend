from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, field_validator

from member.auth.schema import Address, Dob, Gender, Language, Name

OtherLanguage = Literal["gu", "hi"]


class IdDocumentOut(BaseModel):
    mime_type: str
    size_bytes: int
    created_at: datetime


class MemberOut(BaseModel):
    member_id: UUID
    full_name: str | None
    full_name_i18n: dict[str, str]  # {"gu": ..., "hi": ...}: auto-transliterated or the member's correction
    gender: str | None
    dob: date | None
    mobile_last4: str | None
    mobile: str | None  # in full: the member themself and their City Admin
    photo_url: str | None
    address: str | None
    city_id: UUID
    city_name: str
    city_name_i18n: dict[str, str]
    household_id: UUID | None
    family_name: str | None
    family_name_i18n: dict[str, str]
    native_place: str | None
    native_place_i18n: dict[str, str]
    is_household_head: bool
    status: str  # PENDING: the app shows only Panchang and News (FR-08)
    rejection_reason: str | None
    hide_phone: bool
    hide_address: bool
    notify_news: bool
    language: str
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
    language: Language | None = None
    # spelling corrections, merged into the stored ones: {"gu": "દેસાઈ"}
    full_name_i18n: dict[OtherLanguage, Name] | None = None
    family_name_i18n: dict[OtherLanguage, Name] | None = None  # household head only
    native_place_i18n: dict[OtherLanguage, Name] | None = None  # household head only

    @field_validator("full_name", "gender", "dob", "address", "family_name", "hide_phone", "hide_address",
                     "notify_news", "language", "full_name_i18n", "family_name_i18n", "native_place_i18n",
                     mode="before")
    @classmethod
    def not_null(cls, v):
        if v is None:  # only runs for fields actually sent, so "absent" stays allowed
            raise ValueError("This field can't be empty")
        return v
