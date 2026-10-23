import re
from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, Field, StringConstraints


def to_e164(value: str) -> str:
    """'98765 43210', '+91-9876543210' -> '+919876543210'. 10 digits get +91 (the default country)."""
    digits = re.sub(r"[\s\-()]", "", value)
    if re.fullmatch(r"[6-9]\d{9}", digits):
        digits = "+91" + digits
    if not re.fullmatch(r"\+91[6-9]\d{9}|\+(?!91)[1-9]\d{7,14}", digits):
        raise ValueError("Enter a valid mobile number")
    return digits


def dob_in_past(v: date) -> date:
    if not date(1900, 1, 1) <= v <= date.today():
        raise ValueError("Enter a valid date of birth")
    return v


Mobile = Annotated[str, AfterValidator(to_e164)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Address = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Dob = Annotated[date, AfterValidator(dob_in_past)]
Gender = Literal["MALE", "FEMALE", "OTHER"]


class OtpSendIn(BaseModel):
    mobile: Mobile


class OtpSendOut(BaseModel):
    registered: bool  # true: the app shows login; false: it continues to the profile form after the OTP
    expires_in_seconds: int


class OtpVerifyIn(BaseModel):
    mobile: Mobile
    code: str = Field(pattern=r"^\d{6}$")


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    access_expires_in_seconds: int
    member_status: str


class OtpVerifyOut(BaseModel):
    registered: bool
    session: TokenOut | None = None  # registered number: logged in
    registration_ticket: str | None = None  # new number: pass to /register within 15 minutes


class RegisterIn(BaseModel):
    registration_ticket: str
    full_name: Name
    gender: Gender
    dob: Dob
    city_id: UUID
    address: Address
    family_name: Name
    native_place: Name | None = None
    consent: Literal[True]  # FR-07: the app enables Submit only once the box is ticked
    notice_version: str = Field(max_length=20)  # the consent notice the member was shown


class RefreshIn(BaseModel):
    refresh_token: str
