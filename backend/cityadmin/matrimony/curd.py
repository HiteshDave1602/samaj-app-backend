from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import String, cast, exists, func, select, update
from sqlalchemy.orm import Session, aliased

from cityadmin.member_approval.curd import city_filter
from core import private_files
from member.matrimony.model import MatrimonyPhoto, MatrimonyProfile
from member.notification import curd as notification
from member.profile.curd import age
from member.profile.model import Member
from superadmin.audit_log import curd as audit
from superadmin.audit_log.model import AuditLog
from superadmin.city_admin.model import AdminUser

PHOTO_URL = "/{}/matrimony/photos/{}/file"  # the caller's panel: cityadmin | superadmin
_pending = (MatrimonyPhoto.profile_id == MatrimonyProfile.profile_id, MatrimonyPhoto.status == "PENDING")
_pending_count = select(func.count()).where(*_pending).correlate(MatrimonyProfile).scalar_subquery()


def _summary(p: MatrimonyProfile, city_id: UUID, full_name: str | None, gender: str | None, dob: date | None,
             pending: int) -> dict:
    return {c.name: getattr(p, c.name) for c in MatrimonyProfile.__table__.columns} | {
        "city_id": city_id, "full_name": full_name, "gender": gender, "age": age(dob), "pending_photo_count": pending,
    }


# removed profiles, and profiles of deleted members, are gone from every admin list
_live = (MatrimonyProfile.deleted_at.is_(None), Member.deleted_at.is_(None))


def _query(admin: AdminUser, city_id: UUID | None = None):
    # FR-71: a profile belongs to its member's city; that City Admin moderates it. The Super Admin sees every city.
    return (select(MatrimonyProfile, Member.city_id, Member.full_name, Member.gender, Member.dob, _pending_count)
            .join(Member, Member.member_id == MatrimonyProfile.member_id)
            .where(*city_filter(Member.city_id, admin, city_id), *_live))


def counts(db: Session, admin: AdminUser, city_id: UUID | None = None) -> dict:
    """Profiles per status; statuses with none are left out."""
    return dict(db.execute(select(MatrimonyProfile.status, func.count())
                           .join(Member, Member.member_id == MatrimonyProfile.member_id)
                           .where(*city_filter(Member.city_id, admin, city_id), *_live)
                           .group_by(MatrimonyProfile.status)).all())


def list_profiles(db: Session, admin: AdminUser, limit: int, offset: int, status: str | None = None,
                  pending_photos: bool | None = None, city_id: UUID | None = None) -> dict:
    """pending_photos=true is the photo queue: new profiles plus approved ones with newly added photos."""
    q = _query(admin, city_id)
    if status:
        q = q.where(MatrimonyProfile.status == status)
    if pending_photos is not None:
        q = q.where(exists().where(*_pending) if pending_photos else ~exists().where(*_pending))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.execute(q.order_by(MatrimonyProfile.updated_at, MatrimonyProfile.profile_id).limit(limit).offset(offset))
    return {"total": total, "items": [_summary(*r) for r in rows]}  # oldest first


def _get_profile(db: Session, admin: AdminUser, profile_id: UUID, lock: bool = False) -> MatrimonyProfile:
    profile = db.get(MatrimonyProfile, profile_id, with_for_update=lock)
    member = profile and db.get(Member, profile.member_id)
    if profile is None or profile.deleted_at is not None or member.deleted_at is not None:
        raise HTTPException(404, "Matrimony profile not found")
    if admin.role != "SUPER_ADMIN" and member.city_id != admin.city_id:
        raise audit.Denied("CROSS_CITY_DENIED", "This profile belongs to another city", profile_id)
    return profile


def delete_profile(db: Session, admin: AdminUser, actor: audit.Actor, profile_id: UUID):
    """The member's City Admin, or the Super Admin, removes a profile: out of search and every queue at once, and
    the member can no longer open, edit or recreate it. Kept as a row (deleted_at) for the audit trail."""
    profile = _get_profile(db, admin, profile_id, lock=True)
    profile.deleted_at = datetime.now(timezone.utc)  # ORM, not bulk UPDATE: the search outbox must see it
    audit.log(db, actor, "MATRIMONY_DELETE", "matrimony_profile", profile_id,
              db.get(Member, profile.member_id).city_id, {"status": profile.status}, {"deleted": True})
    db.commit()


def _get_photo(db: Session, admin: AdminUser, photo_id: UUID, lock: bool = False) -> MatrimonyPhoto:
    photo = db.get(MatrimonyPhoto, photo_id, with_for_update=lock)
    if photo is None:
        raise HTTPException(404, "Photo not found")
    _get_profile(db, admin, photo.profile_id)
    return photo


def get_profile(db: Session, admin: AdminUser, profile_id: UUID) -> dict:
    _get_profile(db, admin, profile_id)
    row = db.execute(_query(admin).where(MatrimonyProfile.profile_id == profile_id)).one()
    photos = db.scalars(select(MatrimonyPhoto).where(MatrimonyPhoto.profile_id == profile_id)
                        .order_by(MatrimonyPhoto.sort_order))
    panel = "superadmin" if admin.role == "SUPER_ADMIN" else "cityadmin"
    return _summary(*row) | {"photos": [
        {c.name: getattr(ph, c.name) for c in MatrimonyPhoto.__table__.columns} | {
            "file_url": PHOTO_URL.format(panel, ph.photo_id)} for ph in photos]}


def photo_file(db: Session, admin: AdminUser, photo_id: UUID) -> tuple[bytes, str]:
    photo = _get_photo(db, admin, photo_id)
    data = private_files.load(photo.storage_key)
    if data is None:
        raise HTTPException(404, "Photo file not found")
    return data, photo.mime_type


def decide_profile(db: Session, admin: AdminUser, actor: audit.Actor, profile_id: UUID, status: str,
                   reason: str | None = None) -> dict:
    """FR-22: APPROVED makes the profile searchable, and approves the photos still pending on it.
    To turn down single photos, reject them first (FR-23); the rest go through with the profile."""
    profile = _get_profile(db, admin, profile_id, lock=True)
    if profile.status != "PENDING_MODERATION":
        raise HTTPException(409, f"This profile is {profile.status}, not waiting for moderation")
    now = datetime.now(timezone.utc)
    profile.status, profile.moderation_reason = status, reason
    profile.moderated_by_admin_id, profile.moderated_at = admin.admin_id, now
    after = {"status": status} | ({"moderation_reason": reason} if reason else {})
    if status == "APPROVED":
        after["photos_approved"] = db.execute(
            update(MatrimonyPhoto).where(MatrimonyPhoto.profile_id == profile_id, MatrimonyPhoto.status == "PENDING")
            .values(status="APPROVED", moderated_by_admin_id=admin.admin_id, moderated_at=now)).rowcount
    # the member's city, not the admin's: the Super Admin has none, and the city's decision log reads it
    audit.log(db, actor, "MATRIMONY_APPROVE" if status == "APPROVED" else "MATRIMONY_REJECT", "matrimony_profile",
              profile_id, db.get(Member, profile.member_id).city_id, {"status": "PENDING_MODERATION"}, after)
    notification.add(db, profile.member_id, "PROFILE_DECISION", approved=status == "APPROVED", reason=reason)
    db.commit()
    # ponytail: search shows it once matrimony_search_mv exists (member-side matrimony).
    return get_profile(db, admin, profile_id)


def decide_photo(db: Session, admin: AdminUser, actor: audit.Actor, photo_id: UUID, status: str,
                 reason: str | None = None) -> dict:
    """FR-23: a rejected photo is hidden from the profile and the member sees the reason.
    Also how new photos on an already approved profile are reviewed; approved ones stay visible meanwhile."""
    photo = _get_photo(db, admin, photo_id, lock=True)
    if photo.status != "PENDING":
        raise HTTPException(409, f"This photo is already {photo.status}")
    photo.status, photo.rejection_reason = status, reason
    photo.moderated_by_admin_id, photo.moderated_at = admin.admin_id, datetime.now(timezone.utc)
    after = {"status": status} | ({"rejection_reason": reason} if reason else {})
    member = db.get(Member, db.get(MatrimonyProfile, photo.profile_id).member_id)
    audit.log(db, actor, "PHOTO_APPROVE" if status == "APPROVED" else "PHOTO_REJECT", "matrimony_photo",
              photo_id, member.city_id, {"status": "PENDING"}, after)
    notification.add(db, member.member_id, "PHOTO_DECISION", approved=status == "APPROVED", reason=reason)
    db.commit()
    return get_profile(db, admin, photo.profile_id)


DECISIONS = ("MATRIMONY_APPROVE", "MATRIMONY_REJECT", "PHOTO_APPROVE", "PHOTO_REJECT")


def list_decisions(db: Session, admin: AdminUser, limit: int, offset: int, city_id: UUID | None = None) -> dict:
    """Decision history, newest first, read from the audit log: a profile's status moves on after a decision
    (edits, archiving), but its audit entries don't. A photo the member later deleted keeps its entry, but without a name or profile."""
    by_profile, photo_profile = aliased(MatrimonyProfile), aliased(MatrimonyProfile)
    profile_id = func.coalesce(by_profile.profile_id, photo_profile.profile_id)
    q = (select(AuditLog.occurred_at, AuditLog.action, AuditLog.after_state, AdminUser.full_name, profile_id,
                Member.full_name, AuditLog.city_id)
         .outerjoin(AdminUser, AdminUser.admin_id == AuditLog.actor_id)
         .outerjoin(by_profile, (AuditLog.target_table == "matrimony_profile")
                    & (cast(by_profile.profile_id, String) == AuditLog.target_id))
         .outerjoin(MatrimonyPhoto, (AuditLog.target_table == "matrimony_photo")
                    & (cast(MatrimonyPhoto.photo_id, String) == AuditLog.target_id))
         .outerjoin(photo_profile, photo_profile.profile_id == MatrimonyPhoto.profile_id)
         .outerjoin(Member, Member.member_id == func.coalesce(by_profile.member_id, photo_profile.member_id))
         .where(*city_filter(AuditLog.city_id, admin, city_id), AuditLog.action.in_(DECISIONS)))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.execute(q.order_by(AuditLog.occurred_at.desc(), AuditLog.audit_id.desc()).limit(limit).offset(offset))
    return {"total": total, "items": [
        {"occurred_at": at, "action": action, "admin_name": admin_name, "profile_id": pid, "full_name": name,
         "city_id": cid, "reason": (after or {}).get("moderation_reason") or (after or {}).get("rejection_reason")}
        for at, action, after, admin_name, pid, name, cid in rows]}
