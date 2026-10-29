from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from cityadmin.content.model import ContentItem, effective_status
from core import media
from core.database import get_db
from member.auth.deps import get_current_member
from member.profile.model import Member

router = APIRouter(prefix="/member", tags=["Member Feed"])

AD_EVERY = 5  # FR-50: an ad after every 5 news items. ponytail: fixed until Layout Settings (FR-51).
NEWS_LIMIT = 50  # ponytail: newest 50, no paging; add a cursor when feeds get longer.


class FeedItemOut(BaseModel):
    content_id: UUID
    content_type: str  # NEWS | AD
    title: str
    body: str | None
    media_url: str | None
    creative_format: str | None  # ads: BANNER inline, FULLSCREEN as an interstitial
    media_width: int | None
    media_height: int | None
    extra_media_urls: list[str]  # member news photos
    start_at: datetime


@router.get("/feed", response_model=list[FeedItemOut])
def feed(member: Member = Depends(get_current_member), db: Session = Depends(get_db)):
    """FR-49: live news for the member's city plus all-city items, newest first, ads mixed in.
    PENDING members see it too (FR-08)."""
    q = (
        select(ContentItem)
        .where(effective_status == "LIVE",
               or_(ContentItem.city_id == member.city_id, ContentItem.city_id.is_(None)))
        .order_by(ContentItem.start_at.desc(), ContentItem.content_id)
    )
    news = db.scalars(q.where(ContentItem.content_type == "NEWS").limit(NEWS_LIMIT)).all()
    ads = db.scalars(q.where(ContentItem.content_type == "AD")).all()
    items = []
    for i, item in enumerate(news, 1):
        items.append(item)
        if ads and i % AD_EVERY == 0:
            items.append(ads[(i // AD_EVERY - 1) % len(ads)])  # rotate through live ads
    return [{c.name: getattr(x, c.name) for c in ContentItem.__table__.columns}
            | {"media_url": media.url(x.media_key), "extra_media_urls": [media.url(k) for k in x.extra_media_keys]}
            for x in items]
