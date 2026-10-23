from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cityadmin.content.model import ContentItem, effective_status
from cityadmin.content.schema import ContentCreate, ContentUpdate
from core import media
from superadmin.audit_log import curd as audit
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser

FIELDS = ["title", "body", "media_key", "creative_format", "start_at", "end_at", "status"]
FULLSCREEN = (1080, 1920)  # FR-45. ponytail: fixed; Layout Settings (FR-51) makes it editable.


def to_out(item: ContentItem, status: str) -> dict:
    return {c.name: getattr(item, c.name) for c in ContentItem.__table__.columns} | {
        "status": status, "media_url": media.url(item.media_key),
    }


# Shared by /cityadmin/content and /superadmin/content. A City Admin reaches only their city's items;
# the Super Admin reaches every item, including all-city ones (city_id NULL) (FR-48).
def _get_own(db: Session, admin: AdminUser, content_id: UUID, lock: bool = False) -> tuple[ContentItem, str]:
    q = select(ContentItem, effective_status).where(ContentItem.content_id == content_id)
    row = db.execute(q.with_for_update(of=ContentItem) if lock else q).one_or_none()
    if row is None:
        raise HTTPException(404, "Content not found")
    if admin.role != "SUPER_ADMIN" and row[0].city_id != admin.city_id:
        raise audit.Denied("CROSS_CITY_DENIED", "This content belongs to another city", content_id)
    return row[0], row[1]


def get(db: Session, admin: AdminUser, content_id: UUID) -> dict:
    return to_out(*_get_own(db, admin, content_id))


def list_content(db: Session, admin: AdminUser, limit: int, offset: int,
                 content_type: str | None = None, status: str | None = None,
                 city_id: UUID | None = None, all_cities: bool | None = None) -> dict:
    """city_id / all_cities filter the Super Admin's view; a City Admin always gets their own city."""
    q = select(ContentItem, effective_status)
    if admin.role != "SUPER_ADMIN":
        q = q.where(ContentItem.city_id == admin.city_id)
    elif city_id:
        q = q.where(ContentItem.city_id == city_id)
    elif all_cities is not None:
        q = q.where(ContentItem.city_id.is_(None) if all_cities else ContentItem.city_id.is_not(None))
    if content_type:
        q = q.where(ContentItem.content_type == content_type)
    if status:
        q = q.where(effective_status == status)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.execute(q.order_by(ContentItem.start_at.desc(), ContentItem.content_id).limit(limit).offset(offset))
    return {"total": total, "items": [to_out(*r) for r in rows]}


def _set_media(item: ContentItem, key: str):
    dims = media.dimensions(key)
    if dims is None:
        raise HTTPException(400, "Unknown media_key; upload the image first")
    item.media_key, (item.media_width, item.media_height) = key, dims


def _check(item: ContentItem):
    """Rules on the merged item, so create and update can't drift apart."""
    if item.end_at <= item.start_at:  # FR-46
        raise HTTPException(400, "End date-time must be after the start date-time")
    if item.content_type == "NEWS" and item.creative_format:
        raise HTTPException(400, "creative_format is for ads only")
    if item.creative_format == "FULLSCREEN" and (item.media_width, item.media_height) != FULLSCREEN:
        raise HTTPException(400, f"ERR_IMG_UL: A full-screen ad must be 1080x1920 pixels; this image is "
                                 f"{item.media_width}x{item.media_height}")
    if item.status == "SCHEDULED" and item.end_at <= datetime.now(timezone.utc):
        raise HTTPException(400, "End date-time is in the past")


def _target_city(db: Session, admin: AdminUser, city_id: UUID | None) -> UUID | None:
    if admin.role != "SUPER_ADMIN":
        if city_id and city_id != admin.city_id:  # FR-48 acceptance: other city ids are 403
            raise audit.Denied("CROSS_CITY_DENIED", "City Admins can publish only to their own city", city_id)
        return admin.city_id
    if city_id is None:
        return None  # every city
    city = db.get(City, city_id)
    if city is None:
        raise HTTPException(404, "City not found")
    if not city.is_active:
        raise HTTPException(400, "City is not active")
    return city_id


def upload_media(data: bytes) -> dict:
    # FR-89: image failures carry the SOP code ERR_IMG_UL and the corrective action.
    if len(data) > media.MAX_BYTES:
        raise HTTPException(413, "ERR_IMG_UL: Image is larger than 5 MB. Compress it and upload again.")
    try:
        key, width, height = media.save(data)
    except ValueError as exc:
        raise HTTPException(400, f"ERR_IMG_UL: {exc}")
    return {"media_key": key, "media_url": media.url(key), "width": width, "height": height}


def create(db: Session, admin: AdminUser, actor: audit.Actor, data: ContentCreate) -> dict:
    item = ContentItem(
        content_id=uuid4(),  # set here so the audit entry can use it
        content_type=data.content_type,
        city_id=_target_city(db, admin, data.city_id),
        title=data.title,
        body=data.body,
        creative_format=data.creative_format,
        start_at=data.start_at,
        end_at=data.end_at,
        status=data.status,
        created_by_admin_id=admin.admin_id,
    )
    if data.media_key:
        _set_media(item, data.media_key)
    _check(item)
    db.add(item)
    audit.log(db, actor, "CONTENT_CREATE", "content_item", item.content_id, item.city_id,
              after={"content_type": item.content_type} | audit.snapshot(item, FIELDS))
    db.commit()
    return get(db, admin, item.content_id)


def update(db: Session, admin: AdminUser, actor: audit.Actor, content_id: UUID, data: ContentUpdate) -> dict:
    item, status = _get_own(db, admin, content_id, lock=True)
    if status in ("EXPIRED", "CANCELLED"):
        raise HTTPException(409, f"{status.capitalize()} content can't be changed")
    before = audit.snapshot(item, FIELDS)
    for f in ("title", "body", "creative_format", "start_at", "end_at", "status"):
        if (value := getattr(data, f)) is not None:
            setattr(item, f, value)
    if data.media_key is not None:
        _set_media(item, data.media_key)
    _check(item)
    old, new = audit.changes(before, item)
    if new:
        action = "CONTENT_CANCEL" if new.get("status") == "CANCELLED" else "CONTENT_UPDATE"
        audit.log(db, actor, action, "content_item", item.content_id, item.city_id, old, new)
    db.commit()
    return get(db, admin, content_id)
