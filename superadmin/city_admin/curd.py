from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.curd import revoke_sessions
from core.security import hash_password
from superadmin.audit_log import curd as audit
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser
from superadmin.city_admin.schema import CityAdminCreate, CityAdminUpdate

ROLE = "CITY_ADMIN"
FIELDS = ["full_name", "email", "status"]
STATUS_ACTIONS = {"ACTIVE": "CITY_ADMIN_ACTIVATE", "SUSPENDED": "CITY_ADMIN_SUSPEND", "DEACTIVATED": "CITY_ADMIN_DEACTIVATE"}


def _check_email_free(db: Session, email: str, exclude_id: UUID | None = None):
    q = select(AdminUser.admin_id).where(AdminUser.email == email)
    if exclude_id:
        q = q.where(AdminUser.admin_id != exclude_id)
    if db.scalar(q):
        raise HTTPException(409, "Email is already in use")


def _check_city_has_no_active_admin(db: Session, city_id: UUID, exclude_id: UUID | None = None):
    q = select(AdminUser.admin_id).where(
        AdminUser.city_id == city_id, AdminUser.role == ROLE, AdminUser.status == "ACTIVE"
    )
    if exclude_id:
        q = q.where(AdminUser.admin_id != exclude_id)
    if db.scalar(q):
        raise HTTPException(409, "This city already has an active City Admin")


def _commit(db: Session, admin: AdminUser) -> AdminUser:
    # The pre-checks give clear messages; the DB constraints catch races between them.
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email is already in use or the city already has an active City Admin")
    db.refresh(admin)
    return admin


def _log(db: Session, actor: audit.Actor, action: str, admin: AdminUser, before=None, after=None):
    audit.log(db, actor, action, "admin_user", admin.admin_id, admin.city_id, before, after)


def create_city_admin(db: Session, data: CityAdminCreate, actor: audit.Actor) -> AdminUser:
    city = db.get(City, data.city_id)
    if not city:
        raise HTTPException(404, "City not found")
    if not city.is_active:
        raise HTTPException(400, "City is not active")
    _check_email_free(db, data.email)
    _check_city_has_no_active_admin(db, data.city_id)

    admin = AdminUser(
        admin_id=uuid4(),  # set here so the audit entry can use it
        role=ROLE,
        city_id=data.city_id,
        full_name=data.full_name,
        email=data.email,
        password_hash=hash_password(data.password),
    )
    db.add(admin)
    _log(db, actor, "ROLE_ASSIGN", admin, after={"role": ROLE, "full_name": data.full_name, "email": data.email})
    return _commit(db, admin)


def list_city_admins(db: Session, city_id: UUID | None = None, status: str | None = None) -> list[AdminUser]:
    q = select(AdminUser).where(AdminUser.role == ROLE).order_by(AdminUser.created_at.desc())
    if city_id:
        q = q.where(AdminUser.city_id == city_id)
    if status:
        q = q.where(AdminUser.status == status)
    return list(db.scalars(q))


def get_city_admin(db: Session, admin_id: UUID) -> AdminUser:
    admin = db.get(AdminUser, admin_id)
    if not admin or admin.role != ROLE:
        raise HTTPException(404, "City Admin not found")
    return admin


def _get_changeable(db: Session, admin_id: UUID) -> AdminUser:
    admin = get_city_admin(db, admin_id)
    if admin.status == "DEACTIVATED":
        # ponytail: deactivation is final; create a new City Admin instead of reviving one.
        raise HTTPException(400, "Deactivated City Admins cannot be changed")
    return admin


def reset_mfa(db: Session, admin_id: UUID, actor: audit.Actor) -> AdminUser:
    # FR-74: the admin re-enrols on their next login.
    admin = _get_changeable(db, admin_id)
    admin.totp_secret_enc = None
    admin.mfa_enrolled_at = None
    revoke_sessions(db, admin.admin_id)
    _log(db, actor, "ADMIN_MFA_RESET", admin)
    return _commit(db, admin)


def reset_password(db: Session, admin_id: UUID, new_password: str, actor: audit.Actor) -> AdminUser:
    admin = _get_changeable(db, admin_id)
    admin.password_hash = hash_password(new_password)
    revoke_sessions(db, admin.admin_id)
    _log(db, actor, "ADMIN_PASSWORD_RESET", admin)  # never the password itself
    return _commit(db, admin)


def update_city_admin(db: Session, admin_id: UUID, data: CityAdminUpdate, actor: audit.Actor) -> AdminUser:
    admin = _get_changeable(db, admin_id)
    before = audit.snapshot(admin, FIELDS)

    if data.email is not None and data.email != admin.email:
        _check_email_free(db, data.email, exclude_id=admin.admin_id)
        admin.email = data.email
    if data.full_name is not None:
        admin.full_name = data.full_name
    if data.status is not None and data.status != admin.status:
        if data.status == "ACTIVE":
            _check_city_has_no_active_admin(db, admin.city_id, exclude_id=admin.admin_id)
        if data.status == "DEACTIVATED":
            admin.deactivated_at = datetime.now(timezone.utc)
        admin.status = data.status
        if data.status != "ACTIVE":
            revoke_sessions(db, admin.admin_id)
    old, new = audit.changes(before, admin)
    if new:
        # A status change names the action so the audit view can filter on it; other edits are CITY_ADMIN_UPDATE.
        _log(db, actor, STATUS_ACTIONS.get(new.get("status"), "CITY_ADMIN_UPDATE"), admin, old, new)
    return _commit(db, admin)
