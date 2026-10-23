from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from auth.deps import get_actor, require_city_admin
from cityadmin.matrimony import curd
from cityadmin.matrimony.schema import ProfileOut, ProfilePage
from cityadmin.member_approval.schema import RejectIn
from core.database import get_db
from superadmin.audit_log.curd import Actor
from superadmin.city_admin.model import AdminUser

# Photo moderation (SF-04): a profile stays out of search until approved (FR-22).
# Flow: reject any unsuitable photo with a reason -> approve the profile (approves its remaining photos).
router = APIRouter(prefix="/cityadmin/matrimony", tags=["City Admin: Matrimony Moderation"])


@router.get("/profiles", response_model=ProfilePage)
def list_profiles(
    status: Literal["DRAFT", "PENDING_MODERATION", "APPROVED", "REJECTED", "ARCHIVED"] | None = None,
    pending_photos: bool | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_city_admin),
    db: Session = Depends(get_db),
):
    """Own city's profiles, oldest change first. Queues: status=PENDING_MODERATION (new profiles) and
    pending_photos=true (any profile with photos to review)."""
    return curd.list_profiles(db, admin, limit, offset, status, pending_photos)


@router.get("/profiles/{profile_id}", response_model=ProfileOut)
def get_profile(profile_id: UUID, admin: AdminUser = Depends(require_city_admin), db: Session = Depends(get_db)):
    return curd.get_profile(db, admin, profile_id)


@router.post("/profiles/{profile_id}/approve", response_model=ProfileOut)
def approve_profile(
    profile_id: UUID,
    admin: AdminUser = Depends(require_city_admin),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    return curd.decide_profile(db, admin, actor, profile_id, "APPROVED")


@router.post("/profiles/{profile_id}/reject", response_model=ProfileOut)
def reject_profile(
    profile_id: UUID,
    data: RejectIn,
    admin: AdminUser = Depends(require_city_admin),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    return curd.decide_profile(db, admin, actor, profile_id, "REJECTED", data.reason)


@router.get("/photos/{photo_id}/file", response_class=Response,
            responses={200: {"content": {"image/jpeg": {}, "image/png": {}}}})
def photo_file(photo_id: UUID, admin: AdminUser = Depends(require_city_admin), db: Session = Depends(get_db)):
    data, mime_type = curd.photo_file(db, admin, photo_id)
    return Response(data, media_type=mime_type, headers={"Cache-Control": "no-store"})


@router.post("/photos/{photo_id}/approve", response_model=ProfileOut)
def approve_photo(
    photo_id: UUID,
    admin: AdminUser = Depends(require_city_admin),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    return curd.decide_photo(db, admin, actor, photo_id, "APPROVED")


@router.post("/photos/{photo_id}/reject", response_model=ProfileOut)
def reject_photo(
    photo_id: UUID,
    data: RejectIn,
    admin: AdminUser = Depends(require_city_admin),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    return curd.decide_photo(db, admin, actor, photo_id, "REJECTED", data.reason)
