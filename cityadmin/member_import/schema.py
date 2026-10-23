from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ImportJobOut(BaseModel):
    import_job_id: UUID
    file_format: str  # CSV | XLSX
    template_version: str
    status: str  # DRY_RUN_READY -> COMMITTED
    total_rows: int | None
    new_count: int
    updated_count: int
    conflict_count: int
    error_count: int
    uploaded_by_admin_id: UUID
    committed_at: datetime | None
    created_at: datetime


class ImportJobPage(BaseModel):
    total: int
    items: list[ImportJobOut]


class ImportRowOut(BaseModel):
    row_number: int  # as in the spreadsheet; the header is row 1
    outcome: str  # NEW | UPDATE | CONFLICT | ERROR
    error_message: str | None
    resolution: str | None  # APPLIED | SKIPPED; conflicts stay empty until decided
    matched_member_id: UUID | None
    full_name: str | None
    mobile_last4: str | None


class ImportRowPage(BaseModel):
    total: int
    items: list[ImportRowOut]


class ResolveIn(BaseModel):
    # APPLY: the file is right; overwrite the member's name, DOB and details. SKIP: keep the member as is.
    action: Literal["APPLY", "SKIP"]
