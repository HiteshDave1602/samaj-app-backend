from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from core.validation import Strict, Text
from member.auth.schema import Address, BloodGroup, Dob, Gender, MaritalStatus, Mobile, Name

# Relationship to the household head (DDD family_member.relationship).
Relationship = Literal[
    "SPOUSE", "SON", "DAUGHTER", "FATHER", "MOTHER", "BROTHER", "SISTER", "GRANDFATHER", "GRANDMOTHER",
    "GRANDSON", "GRANDDAUGHTER", "SON_IN_LAW", "DAUGHTER_IN_LAW", "OTHER",
]


class FamilyRequestIn(Strict):
    # FR-17: name, relationship, gender and date of birth
    full_name: Name
    relationship: Relationship
    gender: Gender
    dob: Dob
    # optional, same as registration; shown in the directory once approved
    mobile: Mobile | None = None
    address: Address | None = None
    gotra: Text(120) | None = None
    education: Text(120) | None = None
    marital_status: MaritalStatus | None = None
    occupation: Text(120) | None = None
    hobby: Text(200) | None = None
    blood_group: BloodGroup | None = None


class RelativeOut(BaseModel):
    family_member_id: UUID
    full_name: str
    full_name_i18n: dict[str, str]  # {"gu": ..., "hi": ...}
    relationship: str
    gender: str | None
    dob: date | None
    status: str  # PENDING | APPROVED | REJECTED
    rejection_reason: str | None
    requested_by_member_id: UUID | None  # None: added by a directory import
    created_at: datetime


class HouseholdMemberOut(BaseModel):
    member_id: UUID
    full_name: str | None
    full_name_i18n: dict[str, str]
    is_household_head: bool


class HouseholdOut(BaseModel):
    household_id: UUID
    family_name: str
    family_name_i18n: dict[str, str]
    native_place: str | None
    native_place_i18n: dict[str, str]
    members: list[HouseholdMemberOut]  # registered app members in the household
    relatives: list[RelativeOut]  # added by request; APPROVED ones form the family tree (FR-18)
