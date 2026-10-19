from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from member.auth.schema import Dob, Gender, Name

# Relationship to the household head (DDD family_member.relationship).
Relationship = Literal[
    "SPOUSE", "SON", "DAUGHTER", "FATHER", "MOTHER", "BROTHER", "SISTER", "GRANDFATHER", "GRANDMOTHER",
    "GRANDSON", "GRANDDAUGHTER", "SON_IN_LAW", "DAUGHTER_IN_LAW", "OTHER",
]


class FamilyRequestIn(BaseModel):
    # FR-17: name, relationship, gender and date of birth
    full_name: Name
    relationship: Relationship
    gender: Gender
    dob: Dob


class RelativeOut(BaseModel):
    family_member_id: UUID
    full_name: str
    relationship: str
    gender: str | None
    dob: date | None
    status: str  # PENDING | APPROVED | REJECTED
    rejection_reason: str | None
    requested_by_member_id: UUID
    created_at: datetime


class HouseholdMemberOut(BaseModel):
    member_id: UUID
    full_name: str | None
    is_household_head: bool


class HouseholdOut(BaseModel):
    household_id: UUID
    family_name: str
    native_place: str | None
    members: list[HouseholdMemberOut]  # registered app members in the household
    relatives: list[RelativeOut]  # added by request; APPROVED ones form the family tree (FR-18)
