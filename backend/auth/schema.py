from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from superadmin.city_admin.schema import Email

TotpCode = Annotated[str, Field(pattern=r"^\d{6}$")]


class LoginIn(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=128)


class LoginOut(BaseModel):
    mfa_ticket: str | None = None  # valid 5 min; pass to /mfa/enroll or /mfa/verify
    mfa_enrolled: bool
    # Set instead of mfa_ticket when MFA is switched off (settings.admin_mfa)
    access_token: str | None = None
    idle_timeout_minutes: int | None = None


class EnrollOut(BaseModel):
    secret: str
    otpauth_uri: str  # render as a QR code for the authenticator app


class VerifyIn(BaseModel):
    mfa_ticket: str
    code: TotpCode


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    idle_timeout_minutes: int


class TicketIn(BaseModel):
    mfa_ticket: str


class AdminMeOut(BaseModel):
    admin_id: UUID
    role: str  # SUPER_ADMIN | CITY_ADMIN
    full_name: str
    email: str
    city_id: UUID | None  # None for the Super Admin
    city_name: str | None
