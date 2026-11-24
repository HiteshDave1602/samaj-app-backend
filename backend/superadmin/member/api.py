from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from auth.deps import get_actor, require_super_admin
from cityadmin.member_approval import curd
from cityadmin.member_approval.schema import MemberReviewOut, NewCityApproveIn, PendingPage, RejectIn, Search
from core.database import get_db
from superadmin.audit_log.curd import Actor
from superadmin.city_admin.model import AdminUser

# Read-only view of every city's members (shared curd with /cityadmin/members).
# Approving and rejecting stay with each city's City Admin (FR-71), except registrations for a city not set up yet
# (city_id null, `no_city=true`): those have no City Admin, so the Super Admin creates the city, then decides here.
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
    no_city: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Every city's members by name (or one city's); `q` searches name and family name."""
    return curd.list_members(db, admin, limit, offset, status, q, city_id, no_city)


@router.get("/pending", response_model=PendingPage)
def list_pending(
    city_id: UUID | None = None,
    no_city: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return curd.list_pending(db, admin, limit, offset, city_id, no_city)


@router.get("/{member_id}", response_model=MemberReviewOut)
def get_member(member_id: UUID, admin: AdminUser = Depends(require_super_admin), db: Session = Depends(get_db)):
    return curd.get_member(db, admin, member_id)


@router.get("/{member_id}/id-document", response_class=Response,
            responses={200: {"content": {"image/jpeg": {}, "image/png": {}, "application/pdf": {}}}})
def get_id_document(member_id: UUID, admin: AdminUser = Depends(require_super_admin), db: Session = Depends(get_db)):
    data, mime_type = curd.get_id_document(db, admin, member_id)  # FR-10: the Super Admin may open it
    return Response(data, media_type=mime_type, headers={"Cache-Control": "no-store"})


@router.delete("/{member_id}", status_code=204)
def delete_member(
    member_id: UUID,
    admin: AdminUser = Depends(require_super_admin),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    """Any city's member (or one waiting for a new city); they can't log in afterwards."""
    curd.delete_member(db, admin, actor, member_id)


@router.post("/{member_id}/approve", response_model=MemberReviewOut)
def approve_new_city(
    member_id: UUID,
    data: NewCityApproveIn,
    admin: AdminUser = Depends(require_super_admin),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    """Cityless registrations only (409 otherwise): moves the member into `city_id`, then approves."""
    return curd.approve_new_city(db, admin, actor, member_id, data.city_id)


@router.post("/{member_id}/reject", response_model=MemberReviewOut)
def reject_new_city(
    member_id: UUID,
    data: RejectIn,
    admin: AdminUser = Depends(require_super_admin),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    return curd.reject_new_city(db, admin, actor, member_id, data.reason)
