from uuid import UUID

from pydantic import BaseModel


class DirectoryEntry(BaseModel):
    """FR-66: directory fields only. No DOB, no biodata, no matrimony data."""
    kind: str  # MEMBER (registered in the app) | RELATIVE (approved family addition, no contact details)
    id: UUID  # member_id or family_member_id
    full_name: str | None
    gender: str | None
    relationship: str | None  # RELATIVE: relationship to the household head
    is_household_head: bool
    household_id: UUID | None
    family_name: str | None
    native_place: str | None
    city_name: str
    phone: str | None
    address: str | None
    phone_hidden: bool  # FR-68: the member chose to hide it; the app shows "Hidden"
    address_hidden: bool


class DirectoryPage(BaseModel):
    items: list[DirectoryEntry]
    next_offset: int | None  # pass as ?offset= for the next page; null on the last page


class HouseholdView(BaseModel):
    household_id: UUID
    family_name: str
    native_place: str | None
    city_name: str
    people: list[DirectoryEntry]  # FR-67: active members (head first) then approved relatives
