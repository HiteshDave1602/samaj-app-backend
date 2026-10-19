from datetime import datetime
from typing import Any, Literal, get_args
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr, model_validator

from cityadmin.member_approval.schema import Search

# FR-84: the only columns an export can hold. Biodata is not among them and can't be asked for.
Column = Literal["full_name", "gender", "dob", "age", "mobile", "address", "family_name", "native_place", "status",
                 "member_since"]
ALL_COLUMNS: list[str] = list(get_args(Column))


class ExportFilters(BaseModel):
    status: list[Literal["PENDING", "ACTIVE", "REJECTED", "ARCHIVED"]] = Field(default=["ACTIVE"], min_length=1)
    gender: Literal["MALE", "FEMALE", "OTHER"] | None = None
    age_min: int | None = Field(None, ge=0, le=120)
    age_max: int | None = Field(None, ge=0, le=120)
    area: Search | None = None  # matched in the address and native place
    family_name: Search | None = None

    @model_validator(mode="after")
    def check(self):
        if self.age_min is not None and self.age_max is not None and self.age_min > self.age_max:
            raise ValueError("age_min must not be above age_max")
        return self


class ExportIn(BaseModel):
    filters: ExportFilters = ExportFilters()
    columns: list[Column] = Field(default_factory=lambda: list(ALL_COLUMNS), min_length=1)
    # FR-83: opens the file. SecretStr keeps it out of reprs and logs; it is never stored (FR-85).
    password: SecretStr = Field(min_length=8, max_length=128)


class ExportJobOut(BaseModel):
    export_job_id: UUID
    filters: dict[str, Any]
    columns_exported: list[str]
    row_count: int
    file_format: str
    exported_by_admin_id: UUID
    created_at: datetime


class ExportJobPage(BaseModel):
    total: int
    items: list[ExportJobOut]
