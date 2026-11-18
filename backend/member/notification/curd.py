from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy import String, func, literal, or_, select, true, union_all
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from cityadmin.content.model import ContentItem, effective_status
from member.notification.model import Notification
from member.profile.model import Member


def add(db: Session, member_id: UUID, kind: str, **payload):
    """Joins the caller's transaction: it commits, or rolls back, with the change it reports."""
    db.add(Notification(member_id=member_id, kind=kind, payload=jsonable_encoder(payload)))


def _news(member: Member):
    """NEWS_LIVE: the news the feed shows right now, as of when it went live. Worked out at read time, so scheduled
    news appears when it starts, a cancelled one drops out, and an all-city post writes no row per member.
    The member's own posts are left out: NEWS_DECISION already told them."""
    return (select(ContentItem.content_id, literal("NEWS_LIVE", String),
                   func.jsonb_build_object("content_id", ContentItem.content_id, "title", ContentItem.title,
                                           "title_i18n", ContentItem.title_i18n, type_=JSONB),
                   ContentItem.start_at)
            .where(ContentItem.content_type == "NEWS", effective_status == "LIVE",
                   or_(ContentItem.city_id == member.city_id, ContentItem.city_id.is_(None)),
                   ContentItem.created_by_member_id.is_distinct_from(member.member_id)))


def list_for(db: Session, member: Member, limit: int, offset: int) -> dict:
    """Newest first. Biodata kinds carry the other member's profile_id; its public card is attached at read time,
    so a name hidden or a profile unlisted since isn't shown."""
    from member.biodata_request.curd import _cards  # here: biodata_request imports this module

    q = select(Notification.notification_id.label("id"), Notification.kind, Notification.payload,
               Notification.created_at).where(Notification.member_id == member.member_id)
    u = (union_all(q, _news(member)) if member.notify_news else q).subquery()  # "Notify me about news" in the profile
    seen = member.notifications_seen_at
    total = db.scalar(select(func.count()).select_from(u))
    unread = db.scalar(select(func.count()).select_from(u).where(u.c.created_at > seen if seen else true()))
    rows = db.execute(select(u).order_by(u.c.created_at.desc(), u.c.id).limit(limit).offset(offset)).all()
    cards = _cards(db, {UUID(r.payload["profile_id"]) for r in rows if "profile_id" in r.payload})
    return {"total": total, "unread": unread, "items": [{
        "notification_id": r.id, "kind": r.kind, "payload": r.payload, "created_at": r.created_at,
        "unread": seen is None or r.created_at > seen,
        "counterpart": cards.get(UUID(r.payload["profile_id"])) if "profile_id" in r.payload else None,
    } for r in rows]}


def mark_read(db: Session, member: Member):
    member.notifications_seen_at = func.now()
    db.commit()
