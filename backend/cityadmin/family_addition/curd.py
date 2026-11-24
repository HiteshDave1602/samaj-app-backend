from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from cityadmin.member_approval.curd import city_filter
from core.security import fernet
from member.notification import curd as notification
from member.profile.model import FamilyMember, Household, Member
from superadmin.audit_log import curd as audit
from superadmin.city_admin.model import AdminUser

Reviewer = aliased(AdminUser)


def _query(admin: AdminUser, city_id: UUID | None = None):
    # FR-71: a family member belongs to the city of its household; the Super Admin sees every city (or city_id's).
    return (
        select(FamilyMember, Household.family_name, Household.city_id, Member.full_name, Reviewer.full_name)
        .join(Household, Household.household_id == FamilyMember.household_id)
        .join(Member, Member.member_id == FamilyMember.requested_by_member_id)
        .outerjoin(Reviewer, Reviewer.admin_id == FamilyMember.reviewed_by_admin_id)
        .where(*city_filter(Household.city_id, admin, city_id))
    )


def _out(fm: FamilyMember, family_name: str, city_id: UUID | None, requested_by_name: str | None,
         reviewed_by_name: str | None) -> dict:
    return {c.name: getattr(fm, c.name) for c in FamilyMember.__table__.columns} | {
        "family_name": family_name, "city_id": city_id,
        "requested_by_name": requested_by_name, "reviewed_by_name": reviewed_by_name,
        "mobile": fernet.decrypt(fm.mobile_enc).decode() if fm.mobile_enc else None,
        "address": fernet.decrypt(fm.address_enc).decode() if fm.address_enc else None,
    }


def list_requests(db: Session, admin: AdminUser, limit: int, offset: int, status: str | None = None,
                  city_id: UUID | None = None) -> dict:
    """DECIDED = the decision log: APPROVED + REJECTED, newest decision first. Other statuses: oldest request first."""
    q = _query(admin, city_id)
    if status == "DECIDED":
        q = q.where(FamilyMember.status != "PENDING")
        order = (FamilyMember.reviewed_at.desc(), FamilyMember.family_member_id)
    else:
        if status:
            q = q.where(FamilyMember.status == status)
        order = (FamilyMember.created_at, FamilyMember.family_member_id)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.execute(q.order_by(*order).limit(limit).offset(offset))
    return {"total": total, "items": [_out(*r) for r in rows]}


def _get_in_city(db: Session, admin: AdminUser, family_member_id: UUID, lock: bool = False) -> FamilyMember:
    fm = db.get(FamilyMember, family_member_id, with_for_update=lock)
    if fm is None:
        raise HTTPException(404, "Family addition request not found")
    if admin.role != "SUPER_ADMIN" and _city(db, fm) != admin.city_id:
        raise audit.Denied("CROSS_CITY_DENIED", "This request belongs to another city", family_member_id)
    return fm


def _city(db: Session, fm: FamilyMember) -> UUID | None:
    return db.scalar(select(Household.city_id).where(Household.household_id == fm.household_id))


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
              fm.family_member_id, _city(db, fm), {"status": "PENDING"}, after)  # the household's: Super Admin has none
    notification.add(db, fm.requested_by_member_id, "FAMILY_DECISION", approved=status == "APPROVED",
                     reason=reason, name=fm.full_name)
    db.commit()
    return get(db, admin, family_member_id)
