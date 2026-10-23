from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from member.profile.schema import IdDocumentOut as MemberIdDocumentOut, MemberOut


class PendingMemberOut(BaseModel):
    member_id: UUID
    full_name: str | None
    gender: str | None
    dob: date | None
    family_name: str | None
    native_place: str | None
    mobile_last4: str | None
    status: str
    created_at: datetime  # the app shows how long it has waited; 72 h escalates to the Super Admin


class PendingPage(BaseModel):
    total: int
    items: list[PendingMemberOut]


Search = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class IdDocumentOut(MemberIdDocumentOut):
    document_id: UUID  # mime_type: image/jpeg | image/png | application/pdf


class MemberReviewOut(MemberOut):
    mobile: str | None  # full number, so the City Admin can call to verify
    reviewed_by_admin_id: UUID | None
    reviewed_at: datetime | None
    id_document: IdDocumentOut | None = None  # the file itself: GET /cityadmin/members/{id}/id-document


class RejectIn(BaseModel):
    # FR-13: Reject needs a reason; the member sees it in the app.
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class BulkApproveIn(BaseModel):
    member_ids: list[UUID] = Field(min_length=1, max_length=100)
