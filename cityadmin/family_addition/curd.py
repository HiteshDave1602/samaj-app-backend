from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from member.profile.model import FamilyMember, Household, Member
from superadmin.audit_log import curd as audit
from superadmin.city_admin.model import AdminUser


def _query(admin: AdminUser):
    # FR-71: a family member belongs to the city of its household.
    return (
        select(FamilyMember, Household.family_name, Member.full_name)
        .join(Household, Household.household_id == FamilyMember.household_id)
        .join(Member, Member.member_id == FamilyMember.requested_by_member_id)
        .where(Household.city_id == admin.city_id)
    )


def _out(fm: FamilyMember, family_name: str, requested_by_name: str | None) -> dict:
    return {c.name: getattr(fm, c.name) for c in FamilyMember.__table__.columns} | {
        "family_name": family_name, "requested_by_name": requested_by_name,
    }


def list_requests(db: Session, admin: AdminUser, limit: int, offset: int, status: str | None = None) -> dict:
    q = _query(admin)
    if status:
        q = q.where(FamilyMember.status == status)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.execute(q.order_by(FamilyMember.created_at, FamilyMember.family_member_id).limit(limit).offset(offset))
    return {"total": total, "items": [_out(*r) for r in rows]}  # oldest first, like the member queue


def _get_in_city(db: Session, admin: AdminUser, family_member_id: UUID, lock: bool = False) -> FamilyMember:
    fm = db.get(FamilyMember, family_member_id, with_for_update=lock)
    if fm is None:
        raise HTTPException(404, "Family addition request not found")
    if db.scalar(select(Household.city_id).where(Household.household_id == fm.household_id)) != admin.city_id:
        raise audit.Denied("CROSS_CITY_DENIED", "This request belongs to another city", family_member_id)
    return fm


def get(db: Session, admin: AdminUser, family_member_id: UUID) -> dict:
    _get_in_city(db, admin, family_member_id)
    return _out(*db.execute(_query(admin).where(FamilyMember.family_member_id == family_member_id)).one())


def decide(db: Session, admin: AdminUser, actor: audit.Actor, family_member_id: UUID, status: str,
           reason: str | None = None) -> dict:
    """FR-18: APPROVED puts the relative in the directory under the household; REJECTED tells the member why."""
    fm = _get_in_city(db, admin, family_member_id, lock=True)  # lock: a double-click can't decide twice
    if fm.status != "PENDING":
        raise HTTPException(409, f"This request is already {fm.status}")
    fm.status, fm.rejection_reason = status, reason
    fm.reviewed_by_admin_id, fm.reviewed_at = admin.admin_id, datetime.now(timezone.utc)
    after = {"status": status} | ({"rejection_reason": reason} if reason else {})
    audit.log(db, actor, "FAMILY_APPROVE" if status == "APPROVED" else "FAMILY_REJECT", "family_member",
              fm.family_member_id, admin.city_id, {"status": "PENDING"}, after)
    db.commit()
    # ponytail: no FAMILY_DECISION notification to the requester yet; it comes with the notification outbox.
    return get(db, admin, family_member_id)
