from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from core.validation import Email, PersonName, Strict

FullName = PersonName


class CityAdminCreate(Strict):
    city_id: UUID
    full_name: FullName
    email: Email
    password: str = Field(min_length=12, max_length=128)


class CityAdminUpdate(Strict):
    full_name: FullName | None = None
    email: Email | None = None
    status: Literal["ACTIVE", "SUSPENDED", "DEACTIVATED"] | None = None


class PasswordReset(Strict):
    new_password: str = Field(min_length=12, max_length=128)


class CityAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    admin_id: UUID
    city_id: UUID
    full_name: str
    email: str
    status: str
    mfa_enrolled_at: datetime | None
    last_login_at: datetime | None
    created_at: datetime
