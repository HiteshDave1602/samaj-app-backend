from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, Field

from core.validation import Strict, clean

# Login looks an account up; it never creates one, so the lenient older format stays (no lock-outs).
LoginEmail = Annotated[str, BeforeValidator(clean), Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]

TotpCode = Annotated[str, Field(pattern=r"^\d{6}$")]


class LoginIn(Strict):
    email: LoginEmail
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


class VerifyIn(Strict):
    mfa_ticket: str = Field(max_length=1000)
    code: TotpCode


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    idle_timeout_minutes: int


class TicketIn(Strict):
    mfa_ticket: str = Field(max_length=1000)


class PasswordChangeIn(Strict):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)  # same rule as a Super Admin reset


class AdminMeOut(BaseModel):
    admin_id: UUID
    role: str  # SUPER_ADMIN | CITY_ADMIN; the panel this session is for
    full_name: str
    email: str
    city_id: UUID | None  # None for the Super Admin, and for the Super Admin in the City Admin panel before picking a city
    city_name: str | None
    mfa_enrolled_at: datetime | None
    is_super_admin: bool  # true in the City Admin panel too, when it is the Super Admin acting as a City Admin
    has_city_panel_password: bool


class ActingCityIn(Strict):
    city_id: UUID
