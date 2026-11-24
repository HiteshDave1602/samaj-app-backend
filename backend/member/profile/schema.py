from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, field_validator

from core.validation import Strict, Text
from member.auth.schema import Address, BloodGroup, Dob, Gender, Language, MaritalStatus, Name, NativePlace

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
    city_id: UUID | None  # None: registered for a city not set up yet; city_name is the one they typed
    city_name: str
    city_name_i18n: dict[str, str]
    requested_city: str | None = None
    requested_state: str | None = None
    household_id: UUID | None
    family_name: str | None
    family_name_i18n: dict[str, str]
    native_place: str | None
    native_place_i18n: dict[str, str]
    gotra: str | None = None
    education: str | None = None
    marital_status: str | None = None
    occupation: str | None = None
    hobby: str | None = None
    blood_group: str | None = None
    is_household_head: bool
    status: str  # PENDING: the app shows only Panchang and News (FR-08)
    rejection_reason: str | None
    hide_phone: bool
    hide_address: bool
    notify_news: bool
    language: str
    id_document: IdDocumentOut | None  # the file itself is visible to admins only (FR-10)
    created_at: datetime


class MemberUpdate(Strict):
    """Send only the fields that change. City and mobile number can't be changed here."""
    full_name: Name | None = None
    gender: Gender | None = None
    dob: Dob | None = None
    address: Address | None = None
    family_name: Name | None = None  # household head only
    native_place: NativePlace | None = None  # household head only; null clears it
    # optional details; null clears them
    gotra: Text(120) | None = None
    education: Text(120) | None = None
    marital_status: MaritalStatus | None = None
    occupation: Text(120) | None = None
    hobby: Text(200) | None = None
    blood_group: BloodGroup | None = None
    hide_phone: bool | None = None
    hide_address: bool | None = None
    notify_news: bool | None = None
    language: Language | None = None
    # spelling corrections, merged into the stored ones: {"gu": "દેસાઈ"}
    full_name_i18n: dict[OtherLanguage, Name] | None = None
    family_name_i18n: dict[OtherLanguage, Name] | None = None  # household head only
    native_place_i18n: dict[OtherLanguage, NativePlace] | None = None  # household head only

    @field_validator("full_name", "gender", "dob", "address", "family_name", "hide_phone", "hide_address",
                     "notify_news", "language", "full_name_i18n", "family_name_i18n", "native_place_i18n",
                     mode="before")
    @classmethod
    def not_null(cls, v):
        if v is None:  # only runs for fields actually sent, so "absent" stays allowed
            raise ValueError("This field can't be empty")
        return v
