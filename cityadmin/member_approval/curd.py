from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from core import private_files, sms
from core.security import fernet
from member.profile.curd import latest_document, to_profile
from member.profile.model import Household, IdentityDocument, Member
from superadmin.audit_log import curd as audit
from superadmin.city_admin.model import AdminUser


def _page(db: Session, admin: AdminUser, limit: int, offset: int, filters: list, order_by: list) -> dict:
    # FR-71: every list is limited to the admin's own city.
    q = (
        select(Member, Household.family_name, Household.native_place)
        .outerjoin(Household, Household.household_id == Member.household_id)
        .where(Member.city_id == admin.city_id, Member.deleted_at.is_(None), *filters)
    )
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.execute(q.order_by(*order_by).limit(limit).offset(offset))
    return {"total": total, "items": [{
        "member_id": m.member_id, "full_name": m.full_name, "gender": m.gender, "dob": m.dob,
        "family_name": family_name, "native_place": native_place, "mobile_last4": m.mobile_last4,
        "status": m.status, "created_at": m.created_at,
    } for m, family_name, native_place in rows]}


def list_pending(db: Session, admin: AdminUser, limit: int, offset: int) -> dict:
    # FR-12: oldest first.
    return _page(db, admin, limit, offset, [Member.status == "PENDING"], [Member.created_at])


def list_members(db: Session, admin: AdminUser, limit: int, offset: int,
                 status: str | None = None, search: str | None = None) -> dict:
    filters = []
    if status:
        filters.append(Member.status == status)
    if search:  # name or family name, case-insensitive; autoescape keeps % and _ literal
        filters.append(or_(Member.full_name.icontains(search, autoescape=True),
                           Household.family_name.icontains(search, autoescape=True)))
    return _page(db, admin, limit, offset, filters, [Member.full_name, Member.member_id])


def _get_in_city(db: Session, admin: AdminUser, member_id: UUID, lock: bool = False,
                 event: str = "CROSS_CITY_DENIED") -> Member:
    member = db.get(Member, member_id, with_for_update=lock)
    if member is None or member.deleted_at is not None:
        raise HTTPException(404, "Member not found")
    if member.city_id != admin.city_id:  # FR-11: 403, and logged as a security event
        raise audit.Denied(event, "This member belongs to another city", member_id)
    return member


def get_member(db: Session, admin: AdminUser, member_id: UUID) -> dict:
    member = _get_in_city(db, admin, member_id)
    return to_profile(db, member) | {
        "mobile": _mobile(member),
        "reviewed_by_admin_id": member.reviewed_by_admin_id,
        "reviewed_at": member.reviewed_at,
    }


def get_id_document(db: Session, admin: AdminUser, member_id: UUID) -> tuple[bytes, str]:
    """FR-10: only the member's City Admin (and the Super Admin) may open it; anyone else is 403 + logged."""
    _get_in_city(db, admin, member_id, event="ID_DOC_DENIED")
    doc = latest_document(db, member_id)
    data = doc and private_files.load(doc.storage_key)
    if data is None:
        raise HTTPException(404, "This member has not uploaded an ID document")
    return data, doc.mime_type


def _decide(db: Session, admin: AdminUser, actor: audit.Actor, member: Member, status: str, reason: str | None = None):
    if member.status != "PENDING":
        raise HTTPException(409, f"{member.full_name} is already {member.status}")
    member.status = status
    member.rejection_reason = reason
    member.reviewed_by_admin_id = admin.admin_id
    member.reviewed_at = datetime.now(timezone.utc)
    db.execute(update(IdentityDocument)  # the ID was checked as part of this decision
               .where(IdentityDocument.member_id == member.member_id, IdentityDocument.reviewed_at.is_(None))
               .values(reviewed_by_admin_id=admin.admin_id, reviewed_at=member.reviewed_at))
    after = {"status": status} | ({"rejection_reason": reason} if reason else {})
    audit.log(db, actor, "MEMBER_APPROVE" if status == "ACTIVE" else "MEMBER_REJECT", "member",
              member.member_id, member.city_id, {"status": "PENDING"}, after)


def _mobile(member: Member) -> str | None:
    return fernet.decrypt(member.mobile_enc).decode() if member.mobile_enc else None


def _notify(member: Member):
    # FR-14 asks for push, falling back to SMS without a push token. No push yet (SF-08), so always SMS.
    # ponytail: sent inline after commit; moves to notification_outbox + worker with push.
    text = ("Your Samaj membership is approved. Open the app to see the directory and matrimony."
            if member.status == "ACTIVE" else
            "Your Samaj registration was not approved. Open the app to see the reason.")
    if mobile := _mobile(member):
        sms.send_sms(mobile, text)


def approve(db: Session, admin: AdminUser, actor: audit.Actor, member_id: UUID) -> dict:
    member = _get_in_city(db, admin, member_id, lock=True)  # lock: a double-click can't approve twice
    _decide(db, admin, actor, member, "ACTIVE")
    db.commit()
    _notify(member)
    return get_member(db, admin, member_id)


def reject(db: Session, admin: AdminUser, actor: audit.Actor, member_id: UUID, reason: str) -> dict:
    member = _get_in_city(db, admin, member_id, lock=True)
    _decide(db, admin, actor, member, "REJECTED", reason)
    db.commit()
    _notify(member)
    return get_member(db, admin, member_id)


def bulk_approve(db: Session, admin: AdminUser, actor: audit.Actor, member_ids: list[UUID]) -> dict:
    # FR-16: all or nothing; one audit entry per member. Any 403/404/409 rolls the whole batch back.
    members = [_get_in_city(db, admin, mid, lock=True) for mid in dict.fromkeys(member_ids)]
    for member in members:
        _decide(db, admin, actor, member, "ACTIVE")
    db.commit()
    for member in members:
        _notify(member)
    return {"approved": len(members)}
