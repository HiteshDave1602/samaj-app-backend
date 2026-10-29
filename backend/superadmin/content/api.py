from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, UploadFile
from sqlalchemy.orm import Session

from auth.deps import get_actor, require_super_admin
from cityadmin.content import curd
from cityadmin.content.schema import ContentCreate, ContentOut, ContentPage, ContentUpdate, MediaOut
from core import media
from core.database import get_db
from superadmin.audit_log.curd import Actor
from superadmin.city_admin.model import AdminUser

# Same flow and rules as /cityadmin/content (shared curd), but across every city:
# omit city_id on create to publish to all cities (FR-48); any city's item can be edited or cancelled.
router = APIRouter(prefix="/superadmin/content", tags=["Super Admin: News & Ads"])


@router.post("/media", response_model=MediaOut, status_code=201)
def upload_media(file: UploadFile, admin: AdminUser = Depends(require_super_admin)):
    return curd.upload_media(file.file.read(media.MAX_BYTES + 1))


@router.post("", response_model=ContentOut, status_code=201)
def create_content(
    data: ContentCreate,
    admin: AdminUser = Depends(require_super_admin),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    return curd.create(db, admin, actor, data)


@router.get("", response_model=ContentPage)
def list_content(
    content_type: Literal["NEWS", "AD"] | None = None,
    status: Literal["DRAFT", "PENDING", "SCHEDULED", "LIVE", "EXPIRED", "CANCELLED", "REJECTED"] | None = None,
    city_id: UUID | None = None,
    all_cities: bool | None = None,  # true: only all-city items; false: only city items
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Every city's content, newest start first."""
    return curd.list_content(db, admin, limit, offset, content_type, status, city_id, all_cities)


@router.get("/{content_id}", response_model=ContentOut)
def get_content(content_id: UUID, admin: AdminUser = Depends(require_super_admin), db: Session = Depends(get_db)):
    return curd.get(db, admin, content_id)


@router.put("/{content_id}", response_model=ContentOut)
def update_content(
    content_id: UUID,
    data: ContentUpdate,
    admin: AdminUser = Depends(require_super_admin),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    return curd.update(db, admin, actor, content_id, data)
