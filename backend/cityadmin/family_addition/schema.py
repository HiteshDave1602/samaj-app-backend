from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class FamilyAdditionOut(BaseModel):
    family_member_id: UUID
    full_name: str
    relationship: str
    gender: str | None
    dob: date | None
    status: str  # PENDING | APPROVED | REJECTED
    rejection_reason: str | None
    household_id: UUID
    family_name: str
    requested_by_member_id: UUID
    requested_by_name: str | None
    reviewed_by_admin_id: UUID | None
    reviewed_by_name: str | None
    reviewed_at: datetime | None
    created_at: datetime


class FamilyAdditionPage(BaseModel):
    total: int
    items: list[FamilyAdditionOut]
