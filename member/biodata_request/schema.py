from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from member.matrimony.schema import ProfileCard, RequestState


class BiodataRequestOut(RequestState):
    counterpart_profile_id: UUID
    counterpart: ProfileCard | None  # null once that profile is no longer listed
    created_at: datetime
    responded_at: datetime | None
    withdrawn_at: datetime | None


class BiodataRequestPage(BaseModel):
    total: int
    items: list[BiodataRequestOut]
