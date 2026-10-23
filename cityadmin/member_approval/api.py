from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from auth.deps import get_actor, require_city_admin
from cityadmin.member_approval import curd
from cityadmin.member_approval.schema import BulkApproveIn, MemberReviewOut, PendingPage, RejectIn, Search
from core.database import get_db
from superadmin.audit_log.curd import Actor
from superadmin.city_admin.model import AdminUser

router = APIRouter(prefix="/cityadmin/members", tags=["City Admin: Member Approval"])


@router.get("", response_model=PendingPage)
def list_members(
    status: Literal["PENDING", "ACTIVE", "REJECTED", "ARCHIVED"] | None = None,
    q: Search | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_city_admin),
    db: Session = Depends(get_db),
):
    """All members of the admin's city, by name; `q` searches name and family name."""
    return curd.list_members(db, admin, limit, offset, status, q)


@router.get("/pending", response_model=PendingPage)
def list_pending(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_city_admin),
    db: Session = Depends(get_db),
):
    return curd.list_pending(db, admin, limit, offset)


@router.post("/bulk-approve")
def bulk_approve(
    data: BulkApproveIn,
    admin: AdminUser = Depends(require_city_admin),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    return curd.bulk_approve(db, admin, actor, data.member_ids)


@router.get("/{member_id}", response_model=MemberReviewOut)
def get_member(member_id: UUID, admin: AdminUser = Depends(require_city_admin), db: Session = Depends(get_db)):
    return curd.get_member(db, admin, member_id)


@router.get("/{member_id}/id-document", response_class=Response,
            responses={200: {"content": {"image/jpeg": {}, "image/png": {}, "application/pdf": {}}}})
def get_id_document(member_id: UUID, admin: AdminUser = Depends(require_city_admin), db: Session = Depends(get_db)):
    data, mime_type = curd.get_id_document(db, admin, member_id)
    # no-store: an ID scan must not linger in the browser cache of a shared computer
    return Response(data, media_type=mime_type, headers={"Cache-Control": "no-store"})


@router.post("/{member_id}/approve", response_model=MemberReviewOut)
def approve(
    member_id: UUID,
    admin: AdminUser = Depends(require_city_admin),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    return curd.approve(db, admin, actor, member_id)


@router.post("/{member_id}/reject", response_model=MemberReviewOut)
def reject(
    member_id: UUID,
    data: RejectIn,
    admin: AdminUser = Depends(require_city_admin),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    return curd.reject(db, admin, actor, member_id, data.reason)
