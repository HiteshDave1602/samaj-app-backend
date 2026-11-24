import re
from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, Field, model_validator

from core.validation import PersonName, Place, Strict, Text


def to_e164(value: str) -> str:
    """'98765 43210', '+91-9876543210' -> '+919876543210'. 10 digits get +91 (the default country)."""
    digits = re.sub(r"[\s\-()]", "", value.strip()[:40])  # cap first: nobody's number is longer
    if re.fullmatch(r"[6-9]\d{9}", digits):
        digits = "+91" + digits
    if not re.fullmatch(r"\+91[6-9]\d{9}|\+(?!91)[1-9]\d{7,14}", digits):
        raise ValueError("Enter a valid mobile number")
    if len(set(digits[-10:])) == 1:  # 9999999999: never issued, always a placeholder
        raise ValueError("Enter your real mobile number")
    return digits


def dob_in_past(v: date) -> date:
    if not date(1900, 1, 1) <= v <= date.today():
        raise ValueError("Enter a valid date of birth")
    return v


Mobile = Annotated[str, AfterValidator(to_e164)]
Name = PersonName  # people and family names (core/validation.py)
NativePlace = Place(120)
Address = Text(500, multiline=True)  # free form: house numbers, "/", "#", commas all belong in addresses
Dob = Annotated[date, AfterValidator(dob_in_past)]
Gender = Literal["MALE", "FEMALE", "OTHER"]
Language = Literal["en", "gu", "hi"]  # the app's UI languages
MaritalStatus = Literal["Single", "Married", "Widowed", "Divorced"]
BloodGroup = Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
DETAILS = ("gotra", "education", "marital_status", "occupation", "hobby", "blood_group")  # optional profile details


class OtpSendIn(Strict):
    mobile: Mobile
    # login: 404 for an unknown number, without sending a code; register: 409 for a known one. None: either.
    intent: Literal["login", "register"] | None = None


class OtpSendOut(BaseModel):
    registered: bool  # true: the app shows login; false: it continues to the profile form after the OTP
    expires_in_seconds: int
    code: str | None = None  # only with settings.otp_show_code (demo, no SMS gateway yet)


class OtpVerifyIn(Strict):
    mobile: Mobile
    code: str = Field(pattern=r"^\d{6}$")


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    access_expires_in_seconds: int
    member_status: str


class OtpVerifyOut(BaseModel):
    registered: bool  # false: no account for this number; the app offers to register
    session: TokenOut | None = None  # approved member: logged in
    # registered but not approved yet (PENDING) or REJECTED: no session; the app shows the waiting screen
    member_status: str | None = None
    rejection_reason: str | None = None


class RegisterOut(BaseModel):
    member_status: str  # PENDING: no session; the member logs in with an OTP once an admin approves


class RegisterIn(Strict):
    # Not OTP-verified: the number is proven at the first login, and the admin calls it to verify before approving.
    mobile: Mobile
    full_name: Name
    gender: Gender
    dob: Dob
    # A listed city, or the name and state of one not set up yet: the Super Admin then creates it and decides.
    city_id: UUID | None = None
    requested_city: Place(80) | None = None
    requested_state: Place(60) | None = None
    address: Address
    family_name: Name
    native_place: NativePlace | None = None
    gotra: Text(120) | None = None
    education: Text(120) | None = None
    marital_status: MaritalStatus | None = None
    occupation: Text(120) | None = None
    hobby: Text(200) | None = None
    blood_group: BloodGroup | None = None
    language: Language = "en"
    consent: Literal[True]  # FR-07: the app enables Submit only once the box is ticked
    notice_version: str = Field(max_length=20)  # the consent notice the member was shown

    @model_validator(mode="after")
    def one_city(self):
        typed = (self.requested_city is not None, self.requested_state is not None)
        if typed != ((False, False) if self.city_id else (True, True)):
            raise ValueError("Select a city, or enter your city and state")
        return self


class RefreshIn(Strict):
    refresh_token: str = Field(max_length=200)
