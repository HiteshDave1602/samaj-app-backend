from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from core.validation import Search as SearchText, Strict, Text

from member.profile.schema import IdDocumentOut as MemberIdDocumentOut, MemberOut


class PendingMemberOut(BaseModel):
    member_id: UUID
    city_id: UUID | None  # None: waiting for the Super Admin to create requested_city
    requested_city: str | None
    requested_state: str | None
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


Search = SearchText(120)


class IdDocumentOut(MemberIdDocumentOut):
    document_id: UUID  # mime_type: image/jpeg | image/png | application/pdf


class MemberReviewOut(MemberOut):
    mobile: str | None  # full number, so the City Admin can call to verify
    reviewed_by_admin_id: UUID | None
    reviewed_at: datetime | None
    id_document: IdDocumentOut | None = None  # the file itself: GET /cityadmin/members/{id}/id-document


class RejectIn(Strict):
    # FR-13: Reject needs a reason; the member sees it in the app.
    reason: Text(500, multiline=True)


class NewCityApproveIn(Strict):
    # the city the Super Admin created (or picked) for the member's requested_city; omitted for a member with a city
    city_id: UUID | None = None


class BulkApproveIn(Strict):
    member_ids: list[UUID] = Field(min_length=1, max_length=100)
