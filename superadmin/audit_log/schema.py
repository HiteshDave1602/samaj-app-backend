from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AuditFilter(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    actor_id: UUID | None = None
    action: str | None = Field(None, max_length=40)
    city_id: UUID | None = None


class AuditPageQuery(AuditFilter):
    # FastAPI only unpacks a query model when it's the route's sole query parameter, so paging lives here.
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)


class AuditLogOut(BaseModel):
    audit_id: int
    occurred_at: datetime
    actor_type: str
    actor_id: UUID | None
    actor_name: str | None
    action: str
    target_table: str | None
    target_id: str | None
    city_id: UUID | None
    city_name: str | None
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    source_ip: str | None


class AuditLogPage(BaseModel):
    total: int
    items: list[AuditLogOut]
