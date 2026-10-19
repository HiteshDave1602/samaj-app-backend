from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, StringConstraints

Value = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


class PanchangIn(BaseModel):
    tithi: Value
    nakshatra: Value
    yoga: Value
    verified_against_calendar: Literal[True]  # FR-63: the form's "checked against the Samaj calendar" box


class PanchangOut(BaseModel):
    panchang_id: UUID
    panchang_date: date
    tithi: str
    nakshatra: str
    yoga: str
    source: str  # API | MANUAL; MANUAL wins over API for the same date (FR-62)
    verified_against_calendar: bool
    edited_by_admin_id: UUID | None
    edited_by_name: str | None
    fetched_at: datetime | None
    published_at: datetime | None
    updated_at: datetime


class RevisionOut(BaseModel):
    revision_id: UUID
    tithi: str
    nakshatra: str
    yoga: str
    source: str
    edited_by_admin_id: UUID | None
    edited_by_name: str | None
    api_status: str | None
    created_at: datetime


class PanchangDetail(PanchangOut):
    revisions: list[RevisionOut]  # edit history, newest first (FR-62)


class PanchangStatus(BaseModel):
    date: date  # today in IST
    available: bool
    source: str | None
    tomorrow_available: bool
    error_code: Literal["ERR_API_PN"] | None  # FR-60: set from 04:00 IST if today is still missing
    message: str | None  # the SOP corrective action (FR-89)
