from datetime import date
from uuid import UUID

from pydantic import BaseModel


class DirectoryEntry(BaseModel):
    """FR-66: directory fields only. No DOB, no biodata, no matrimony data."""
    kind: str  # MEMBER (registered in the app) | RELATIVE (approved family addition or directory import; no app account)
    id: UUID  # member_id or family_member_id
    full_name: str | None
    full_name_i18n: dict[str, str]  # {"gu": ..., "hi": ...}; the app falls back to the English field
    gender: str | None
    relationship: str | None  # RELATIVE: relationship to the household head
    is_household_head: bool
    household_id: UUID | None
    family_name: str | None
    family_name_i18n: dict[str, str]
    native_place: str | None
    native_place_i18n: dict[str, str]
    city_name: str
    city_name_i18n: dict[str, str]
    phone: str | None
    address: str | None
    phone_hidden: bool  # FR-68: the member chose to hide it; the app shows "Hidden"
    address_hidden: bool
    photo_url: str | None  # MEMBER's profile photo; RELATIVE has none
    # Directory-import details (Super Admin import); null for members and app-added relatives
    gotra: str | None = None
    education: str | None = None
    marital_status: str | None = None
    occupation: str | None = None
    hobby: str | None = None
    blood_group: str | None = None


class BirthdayEntry(DirectoryEntry):
    birthday: date  # the upcoming birthday (this year or next), not the date of birth
    days_away: int  # 0 = today


class DirectoryPage(BaseModel):
    items: list[DirectoryEntry]
    next_offset: int | None  # pass as ?offset= for the next page; null on the last page
    suggested: bool = False  # nothing matched the search (a misspelling?): items are the closest names instead


class HouseholdView(BaseModel):
    household_id: UUID
    family_name: str
    family_name_i18n: dict[str, str]
    native_place: str | None
    native_place_i18n: dict[str, str]
    city_name: str
    city_name_i18n: dict[str, str]
    people: list[DirectoryEntry]  # FR-67: active members (head first) then approved relatives
