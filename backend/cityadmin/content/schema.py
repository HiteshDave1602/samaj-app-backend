from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field, StringConstraints, model_validator

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000)]


class ContentCreate(BaseModel):
    content_type: Literal["NEWS", "AD"]
    # FR-48. City Admin: optional, must be their own city. Super Admin: a city, or omitted for every city.
    city_id: UUID | None = None
    title: Title
    body: Body | None = None  # required for NEWS
    media_key: str | None = None  # from POST /cityadmin/content/media; required for AD
    creative_format: Literal["BANNER", "FULLSCREEN"] | None = None  # required for AD
    start_at: AwareDatetime
    end_at: AwareDatetime
    status: Literal["DRAFT", "SCHEDULED"] = "SCHEDULED"

    @model_validator(mode="after")
    def check(self):
        if self.end_at <= self.start_at:  # FR-46
            raise ValueError("End date-time must be after the start date-time")
        if self.content_type == "NEWS" and not self.body:
            raise ValueError("News needs a body")
        if self.content_type == "NEWS" and self.creative_format:
            raise ValueError("creative_format is for ads only")
        if self.content_type == "AD" and not (self.media_key and self.creative_format):
            raise ValueError("An ad needs media_key and creative_format")
        return self


class ContentUpdate(BaseModel):
    title: Title | None = None
    body: Body | None = None
    media_key: str | None = None
    creative_format: Literal["BANNER", "FULLSCREEN"] | None = None
    start_at: AwareDatetime | None = None
    end_at: AwareDatetime | None = None
    status: Literal["DRAFT", "SCHEDULED", "CANCELLED"] | None = None  # CANCELLED is final


class NewsSubmit(BaseModel):
    """Member news (POST /member/news); images from POST /member/news/media."""
    title: Title
    body: Body
    media_key: str  # banner
    extra_media_keys: list[str] = Field([], max_length=5)


class NewsSubmitted(BaseModel):
    content_id: UUID
    status: str  # PENDING


class ContentOut(BaseModel):
    content_id: UUID
    content_type: str
    city_id: UUID | None
    title: str
    body: str | None
    media_key: str | None
    media_url: str | None
    creative_format: str | None
    media_width: int | None
    media_height: int | None
    start_at: datetime
    end_at: datetime
    extra_media_urls: list[str]
    status: str  # DRAFT | PENDING | SCHEDULED | LIVE | EXPIRED | CANCELLED | REJECTED
    created_by_admin_id: UUID | None
    created_by_member_id: UUID | None  # set on member-submitted news
    created_at: datetime


class ContentPage(BaseModel):
    total: int
    items: list[ContentOut]


class MediaOut(BaseModel):
    media_key: str
    media_url: str
    width: int
    height: int
