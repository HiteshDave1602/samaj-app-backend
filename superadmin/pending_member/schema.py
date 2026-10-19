from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class OverdueMemberOut(BaseModel):
    member_id: UUID
    full_name: str | None
    created_at: datetime
    city_id: UUID
    city_name: str
    city_admin_id: UUID | None  # None: the city has no active City Admin, so nobody can approve
    city_admin_name: str | None
