from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from auth.deps import require_super_admin
from cityadmin.member_approval import curd
from cityadmin.member_approval.schema import MemberReviewOut, PendingPage, Search
from core.database import get_db
from superadmin.city_admin.model import AdminUser

# Read-only view of every city's members (shared curd with /cityadmin/members).
# Approving and rejecting stay with each city's City Admin (FR-71).
router = APIRouter(prefix="/superadmin/members", tags=["Super Admin: Members"])


@router.get("/counts", response_model=dict[str, int])
def counts(city_id: UUID | None = None, admin: AdminUser = Depends(require_super_admin), db: Session = Depends(get_db)):
    """Members per status, e.g. {"PENDING": 4, "ACTIVE": 120, "REJECTED": 3}."""
    return curd.counts(db, admin, city_id)


@router.get("", response_model=PendingPage)
def list_members(
    status: Literal["PENDING", "ACTIVE", "REJECTED", "ARCHIVED"] | None = None,
    q: Search | None = None,
    city_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Every city's members by name (or one city's); `q` searches name and family name."""
    return curd.list_members(db, admin, limit, offset, status, q, city_id)


@router.get("/pending", response_model=PendingPage)
def list_pending(
    city_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return curd.list_pending(db, admin, limit, offset, city_id)


@router.get("/{member_id}", response_model=MemberReviewOut)
def get_member(member_id: UUID, admin: AdminUser = Depends(require_super_admin), db: Session = Depends(get_db)):
    return curd.get_member(db, admin, member_id)


@router.get("/{member_id}/id-document", response_class=Response,
            responses={200: {"content": {"image/jpeg": {}, "image/png": {}, "application/pdf": {}}}})
def get_id_document(member_id: UUID, admin: AdminUser = Depends(require_super_admin), db: Session = Depends(get_db)):
    data, mime_type = curd.get_id_document(db, admin, member_id)  # FR-10: the Super Admin may open it
    return Response(data, media_type=mime_type, headers={"Cache-Control": "no-store"})
