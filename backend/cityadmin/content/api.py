from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, UploadFile
from sqlalchemy.orm import Session

from auth.deps import get_actor, require_city_admin
from cityadmin.content import curd
from cityadmin.content.schema import ContentCreate, ContentOut, ContentPage, ContentUpdate, MediaOut
from cityadmin.member_approval.schema import RejectIn
from core import media
from core.database import get_db
from superadmin.audit_log.curd import Actor
from superadmin.city_admin.model import AdminUser

# Flow: POST /media (image) -> POST "" with its media_key -> live between start_at and end_at.
# No DELETE: set status CANCELLED, which keeps the audit trail readable.
# Member news arrives PENDING (list ?status=PENDING): approve makes it live now, reject keeps it out.
router = APIRouter(prefix="/cityadmin/content", tags=["City Admin: News & Ads"])


@router.post("/media", response_model=MediaOut, status_code=201)
def upload_media(file: UploadFile, admin: AdminUser = Depends(require_city_admin)):
    return curd.upload_media(file.file.read(media.MAX_BYTES + 1))


@router.post("", response_model=ContentOut, status_code=201)
def create_content(
    data: ContentCreate,
    admin: AdminUser = Depends(require_city_admin),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    return curd.create(db, admin, actor, data)


@router.get("", response_model=ContentPage)
def list_content(
    content_type: Literal["NEWS", "AD"] | None = None,
    status: Literal["DRAFT", "PENDING", "SCHEDULED", "LIVE", "EXPIRED", "CANCELLED", "REJECTED"] | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_city_admin),
    db: Session = Depends(get_db),
):
    """Own city's content, newest start first."""
    return curd.list_content(db, admin, limit, offset, content_type, status)


@router.get("/{content_id}", response_model=ContentOut)
def get_content(content_id: UUID, admin: AdminUser = Depends(require_city_admin), db: Session = Depends(get_db)):
    return curd.get(db, admin, content_id)


@router.put("/{content_id}", response_model=ContentOut)
def update_content(
    content_id: UUID,
    data: ContentUpdate,
    admin: AdminUser = Depends(require_city_admin),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    return curd.update(db, admin, actor, content_id, data)


@router.post("/{content_id}/approve", response_model=ContentOut)
def approve(
    content_id: UUID,
    admin: AdminUser = Depends(require_city_admin),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    return curd.decide(db, admin, actor, content_id, "SCHEDULED")


@router.post("/{content_id}/reject", response_model=ContentOut)
def reject(
    content_id: UUID,
    data: RejectIn,
    admin: AdminUser = Depends(require_city_admin),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    return curd.decide(db, admin, actor, content_id, "REJECTED", data.reason)
