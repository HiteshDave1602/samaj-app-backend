from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from auth.deps import require_super_admin
from cityadmin.matrimony import curd
from cityadmin.matrimony.schema import DecisionPage, ProfileOut, ProfilePage
from core.database import get_db
from superadmin.city_admin.model import AdminUser

# Read-only view of every city's matrimony moderation (shared curd with /cityadmin/matrimony).
# Approving and rejecting stay with each city's City Admin (FR-71). Biodata is never shown (FR-36).
router = APIRouter(prefix="/superadmin/matrimony", tags=["Super Admin: Matrimony"])


@router.get("/counts", response_model=dict[str, int])
def counts(city_id: UUID | None = None, admin: AdminUser = Depends(require_super_admin), db: Session = Depends(get_db)):
    """Profiles per status, e.g. {"PENDING_MODERATION": 4, "APPROVED": 12, "REJECTED": 3}."""
    return curd.counts(db, admin, city_id)


@router.get("/profiles", response_model=ProfilePage)
def list_profiles(
    status: Literal["DRAFT", "PENDING_MODERATION", "APPROVED", "REJECTED", "ARCHIVED"] | None = None,
    pending_photos: bool | None = None,
    city_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return curd.list_profiles(db, admin, limit, offset, status, pending_photos, city_id)


@router.get("/decisions", response_model=DecisionPage)
def list_decisions(
    city_id: UUID | None = None,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return curd.list_decisions(db, admin, limit, offset, city_id)


@router.get("/profiles/{profile_id}", response_model=ProfileOut)
def get_profile(profile_id: UUID, admin: AdminUser = Depends(require_super_admin), db: Session = Depends(get_db)):
    return curd.get_profile(db, admin, profile_id)


@router.get("/photos/{photo_id}/file", response_class=Response,
            responses={200: {"content": {"image/jpeg": {}, "image/png": {}}}})
def photo_file(photo_id: UUID, admin: AdminUser = Depends(require_super_admin), db: Session = Depends(get_db)):
    data, mime_type = curd.photo_file(db, admin, photo_id)
    return Response(data, media_type=mime_type, headers={"Cache-Control": "no-store"})
