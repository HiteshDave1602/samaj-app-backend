from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth.deps import get_actor, require_super_admin
from cityadmin.family_addition import curd
from cityadmin.family_addition.schema import FamilyAdditionOut, FamilyAdditionPage
from cityadmin.member_approval.schema import RejectIn
from core.database import get_db
from superadmin.audit_log.curd import Actor
from superadmin.city_admin.model import AdminUser

# Every city's family additions (shared curd with /cityadmin/family-additions). The Super Admin decides alongside
# the City Admins; whoever decides first wins (the other gets 409).
router = APIRouter(prefix="/superadmin/family-additions", tags=["Super Admin: Family Additions"])


@router.get("", response_model=FamilyAdditionPage)
def list_requests(
    status: Literal["PENDING", "APPROVED", "REJECTED", "DECIDED"] | None = "PENDING",
    city_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return curd.list_requests(db, admin, limit, offset, status, city_id)


@router.get("/{family_member_id}", response_model=FamilyAdditionOut)
def get_request(family_member_id: UUID, admin: AdminUser = Depends(require_super_admin),
                db: Session = Depends(get_db)):
    return curd.get(db, admin, family_member_id)


@router.post("/{family_member_id}/approve", response_model=FamilyAdditionOut)
def approve(family_member_id: UUID, admin: AdminUser = Depends(require_super_admin),
            actor: Actor = Depends(get_actor), db: Session = Depends(get_db)):
    return curd.decide(db, admin, actor, family_member_id, "APPROVED")


@router.post("/{family_member_id}/reject", response_model=FamilyAdditionOut)
def reject(family_member_id: UUID, data: RejectIn, admin: AdminUser = Depends(require_super_admin),
           actor: Actor = Depends(get_actor), db: Session = Depends(get_db)):
    return curd.decide(db, admin, actor, family_member_id, "REJECTED", data.reason)
