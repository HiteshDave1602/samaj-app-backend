import threading
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from cityadmin.content.model import ContentItem, effective_status
from core import media
from core.database import SessionLocal, get_db
from core.translate import translate
from member.auth.deps import get_current_member
from member.profile.model import Member

router = APIRouter(prefix="/member", tags=["Member Feed"])

AD_EVERY = 5  # FR-50: an ad after every 5 news items. ponytail: fixed until Layout Settings (FR-51).
NEWS_LIMIT = 50  # ponytail: newest 50, no paging; add a cursor when feeds get longer.
_translating = threading.Lock()  # ponytail: one run per server process; a shared lock if it runs several workers


class FeedItemOut(BaseModel):
    content_id: UUID
    content_type: str  # NEWS | AD
    title: str
    title_i18n: dict[str, str]
    body: str | None
    body_i18n: dict[str, str]
    media_url: str | None
    creative_format: str | None  # ads: BANNER inline, FULLSCREEN as an interstitial
    media_width: int | None
    media_height: int | None
    extra_media_urls: list[str]  # member news photos
    start_at: datetime


def _translate_new(content_ids: list[UUID]):
    """Runs after the feed response, so a slow or exhausted service never delays readers: they see the original until
    a later load. Only live items get here, so only approved text leaves the server. Old items, edits and earlier
    failures all land here. Each item is saved on its own, so what was done before the allowance ran out is kept."""
    if not _translating.acquire(blocking=False):
        return  # another request is already on it; a second run would spend the daily allowance twice
    try:
        with SessionLocal() as db:
            for content_id in content_ids:
                x = db.get(ContentItem, content_id)
                if x is None or x.title_i18n:
                    continue
                done = translate([x.title, x.body] if x.body else [x.title])
                if not done:
                    return  # down or over the allowance: the next feed load tries again
                # an admin may have edited the text while the service was working: then this translation is stale
                db.execute(update(ContentItem)
                           .where(ContentItem.content_id == content_id, ContentItem.title == x.title,
                                  ContentItem.body.is_not_distinct_from(x.body))
                           .values(title_i18n={lang: texts[0] for lang, texts in done.items()},
                                   body_i18n={lang: texts[1] for lang, texts in done.items()} if x.body else {}))
                db.commit()
    finally:
        _translating.release()


@router.get("/feed", response_model=list[FeedItemOut])
def feed(background: BackgroundTasks, member: Member = Depends(get_current_member), db: Session = Depends(get_db)):
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
    # shortest first: one long post can't use up the day's allowance before the others get their turn
    untranslated = sorted((x for x in [*news, *ads] if not x.title_i18n), key=lambda x: len(x.title) + len(x.body or ""))
    if untranslated:
        background.add_task(_translate_new, [x.content_id for x in untranslated])
    items = []
    for i, item in enumerate(news, 1):
        items.append(item)
        if ads and i % AD_EVERY == 0:
            items.append(ads[(i // AD_EVERY - 1) % len(ads)])  # rotate through live ads
    return [{c.name: getattr(x, c.name) for c in ContentItem.__table__.columns}
            | {"media_url": media.url(x.media_key), "extra_media_urls": [media.url(k) for k in x.extra_media_keys]}
            for x in items]
