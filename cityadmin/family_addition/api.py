from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth.deps import get_actor, require_city_admin
from cityadmin.family_addition import curd
from cityadmin.family_addition.schema import FamilyAdditionOut, FamilyAdditionPage
from cityadmin.member_approval.schema import RejectIn
from core.database import get_db
from superadmin.audit_log.curd import Actor
from superadmin.city_admin.model import AdminUser

# Members ask for relatives to be added to their household (FR-17); they reach the directory only once approved.
router = APIRouter(prefix="/cityadmin/family-additions", tags=["City Admin: Family Additions"])


@router.get("", response_model=FamilyAdditionPage)
def list_requests(
    status: Literal["PENDING", "APPROVED", "REJECTED"] | None = "PENDING",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_city_admin),
    db: Session = Depends(get_db),
):
    """Own city's requests, oldest first. Defaults to the PENDING queue; pass status= for others."""
    return curd.list_requests(db, admin, limit, offset, status)


@router.get("/{family_member_id}", response_model=FamilyAdditionOut)
def get_request(family_member_id: UUID, admin: AdminUser = Depends(require_city_admin),
                db: Session = Depends(get_db)):
    return curd.get(db, admin, family_member_id)


@router.post("/{family_member_id}/approve", response_model=FamilyAdditionOut)
def approve(
    family_member_id: UUID,
    admin: AdminUser = Depends(require_city_admin),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    return curd.decide(db, admin, actor, family_member_id, "APPROVED")


@router.post("/{family_member_id}/reject", response_model=FamilyAdditionOut)
def reject(
    family_member_id: UUID,
    data: RejectIn,
    admin: AdminUser = Depends(require_city_admin),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    return curd.decide(db, admin, actor, family_member_id, "REJECTED", data.reason)
