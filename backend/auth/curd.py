import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from uuid import UUID

from cryptography.fernet import InvalidToken
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from auth.model import AuthSession
from core.config import settings
from core.security import fernet as _fernet, hash_password, new_totp_secret, verify_password, verify_totp
from superadmin.audit_log import curd as audit
from superadmin.city_admin.model import AdminUser

IDLE_TIMEOUT = timedelta(days=5)  # FR-73 says 30 min; relaxed on request
SESSION_MAX_AGE = timedelta(days=5)  # must be >= IDLE_TIMEOUT or the idle limit never applies
TICKET_TTL_SECONDS = 300
MAX_FAILURES, FAILURE_WINDOW = 5, 15 * 60

_DUMMY_HASH = hash_password(secrets.token_hex(16))  # keeps unknown-email logins as slow as real ones

# ponytail: in-process failure counter; resets on restart and isn't shared across workers.
# Move to security_event (MFA_FAILED) counts once that table exists.
_failures: dict[str, list[float]] = {}


def _check_not_locked(key: str):
    now = time.time()
    recent = [t for t in _failures.get(key, []) if now - t < FAILURE_WINDOW]
    _failures[key] = recent
    if len(recent) >= MAX_FAILURES:
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.")


def _record_failure(key: str):
    _failures.setdefault(key, []).append(time.time())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def login(db: Session, email: str, password: str) -> dict:
    key = f"pw:{email.lower()}"
    _check_not_locked(key)
    admin = db.scalar(select(AdminUser).where(AdminUser.email == email))
    main_ok = verify_password(password, admin.password_hash if admin else _DUMMY_HASH)
    # Always two checks, so timing doesn't tell whether a Super Admin has a City Admin panel password.
    alt_hash = admin.city_panel_password_hash if admin and admin.role == "SUPER_ADMIN" else None
    city_panel = verify_password(password, alt_hash or _DUMMY_HASH) and alt_hash is not None and not main_ok
    if admin is None or not (main_ok or city_panel):
        _record_failure(key)
        raise HTTPException(401, "Invalid email or password")
    if admin.status != "ACTIVE":
        raise HTTPException(403, "Account is not active")
    _failures.pop(key, None)
    if not settings.admin_mfa:
        return {"mfa_enrolled": admin.mfa_enrolled_at is not None} | _start_session(db, admin, city_panel)
    ticket = _fernet.encrypt(f"{admin.admin_id}:{int(city_panel)}".encode()).decode()
    return {"mfa_ticket": ticket, "mfa_enrolled": admin.mfa_enrolled_at is not None}


def _admin_from_ticket(db: Session, ticket: str) -> tuple[AdminUser, bool]:
    """(admin, city_panel) from a login ticket."""
    try:
        admin_id, _, city_panel = _fernet.decrypt(ticket.encode(), ttl=TICKET_TTL_SECONDS).decode().partition(":")
        admin = db.get(AdminUser, UUID(admin_id))
    except (InvalidToken, ValueError):
        raise HTTPException(401, "MFA ticket is invalid or expired; log in again")
    if not admin or admin.status != "ACTIVE":
        raise HTTPException(401, "MFA ticket is invalid or expired; log in again")
    return admin, city_panel == "1"


def enroll_mfa(db: Session, ticket: str) -> dict:
    admin, _ = _admin_from_ticket(db, ticket)
    if admin.mfa_enrolled_at is not None:
        # Re-enrolment only after a Super Admin MFA reset (FR-74).
        raise HTTPException(409, "MFA is already enrolled")
    if admin.totp_secret_enc is not None:
        # Repeat enroll before first verify returns the same secret, so the app already set up keeps working.
        secret = _fernet.decrypt(admin.totp_secret_enc).decode()
    else:
        secret = new_totp_secret()
        admin.totp_secret_enc = _fernet.encrypt(secret.encode())
        db.commit()
    label = quote(f"Samaj Admin:{admin.email}")
    return {"secret": secret, "otpauth_uri": f"otpauth://totp/{label}?secret={secret}&issuer=Samaj%20Admin"}


def verify_mfa(db: Session, ticket: str, code: str) -> dict:
    admin, city_panel = _admin_from_ticket(db, ticket)
    if admin.totp_secret_enc is None:
        raise HTTPException(400, "MFA is not enrolled; call /mfa/enroll first")
    key = f"mfa:{admin.admin_id}"
    _check_not_locked(key)
    secret = _fernet.decrypt(admin.totp_secret_enc).decode()
    if not verify_totp(secret, code):
        _record_failure(key)
        raise HTTPException(401, "ERR_AUTH_01: MFA verification failed. Check your device clock "
                                 "or ask the Super Admin to reset your MFA.")
    _failures.pop(key, None)
    if admin.mfa_enrolled_at is None:
        admin.mfa_enrolled_at = _now()
    return _start_session(db, admin, city_panel)


def _start_session(db: Session, admin: AdminUser, city_panel: bool = False) -> dict:
    now = _now()
    admin.last_login_at = now
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(
        admin_id=admin.admin_id,
        refresh_token_hash=hash_token(token),
        mfa_verified=True,  # required by ck_auth_session_2; not proof of MFA while settings.admin_mfa is off
        city_panel=city_panel,
        last_activity_at=now,
        expires_at=now + SESSION_MAX_AGE,
    ))
    db.commit()
    return {"access_token": token, "idle_timeout_minutes": int(IDLE_TIMEOUT.total_seconds() // 60)}


def revoke_sessions(db: Session, admin_id: UUID, keep: UUID | None = None):
    """Caller commits. `keep`: a session_id to leave signed in."""
    q = update(AuthSession).where(AuthSession.admin_id == admin_id, AuthSession.revoked_at.is_(None))
    if keep:
        q = q.where(AuthSession.session_id != keep)
    db.execute(q.values(revoked_at=_now()))


def change_password(db: Session, token: str, current_password: str, new_password: str, ip: str | None):
    """Self-service change of the password this session signed in with: the caller's session stays, every other one ends."""
    sess, admin = session_admin(db, token)
    field, other = ("city_panel_password_hash", "password_hash") if sess.city_panel else ("password_hash", "city_panel_password_hash")
    _set_password(db, admin, field, other, current_password, new_password)
    revoke_sessions(db, admin.admin_id, keep=sess.session_id)
    action = "CITY_PANEL_PASSWORD_CHANGE" if sess.city_panel else "ADMIN_PASSWORD_CHANGE"
    audit.log(db, audit.Actor(admin.admin_id, ip), action, "admin_user", admin.admin_id, admin.city_id)
    db.commit()


def set_city_panel_password(db: Session, admin: AdminUser, current_password: str, new_password: str, ip: str | None):
    """Super Admin, from the Super Admin panel: set/replace the password that opens the City Admin panel.
    Checked against the main password; City Admin panel sessions end."""
    _set_password(db, admin, "city_panel_password_hash", "password_hash", current_password, new_password,
                  check_field="password_hash")
    db.execute(update(AuthSession).where(AuthSession.admin_id == admin.admin_id, AuthSession.city_panel,
                                         AuthSession.revoked_at.is_(None)).values(revoked_at=_now()))
    audit.log(db, audit.Actor(admin.admin_id, ip), "CITY_PANEL_PASSWORD_SET", "admin_user", admin.admin_id, None)
    db.commit()


def _set_password(db: Session, admin: AdminUser, field: str, other: str, current_password: str, new_password: str,
                  check_field: str | None = None):
    """Caller commits. `other` is the account's second password: they must differ, or login can't tell the panels apart."""
    key = f"pwchange:{admin.admin_id}"
    _check_not_locked(key)  # a stolen session can't brute-force the password
    if not verify_password(current_password, getattr(admin, check_field or field)):
        _record_failure(key)
        raise HTTPException(400, "Current password is incorrect")  # not 401: the panel reads that as "session expired"
    _failures.pop(key, None)
    if new_password == current_password and not check_field:
        raise HTTPException(400, "New password must be different from the current one")
    if getattr(admin, other) and verify_password(new_password, getattr(admin, other)):
        raise HTTPException(400, "Super Admin panel and City Admin panel passwords must be different")
    setattr(admin, field, hash_password(new_password))


def logout(db: Session, token: str):
    sess, _ = session_admin(db, token)
    sess.revoked_at = _now()
    db.commit()


def session_admin(db: Session, token: str) -> tuple[AuthSession, AdminUser]:
    sess = db.scalar(select(AuthSession).where(
        AuthSession.refresh_token_hash == hash_token(token),
        AuthSession.admin_id.is_not(None),
        AuthSession.revoked_at.is_(None),
    ))
    now = _now()
    if not sess or now >= sess.expires_at:
        raise HTTPException(401, "Session expired; log in again")
    if now - sess.last_activity_at > IDLE_TIMEOUT:
        sess.revoked_at = now
        db.commit()
        raise HTTPException(401, "Session timed out due to inactivity; log in again")
    admin = db.get(AdminUser, sess.admin_id)
    if admin.status != "ACTIVE":
        raise HTTPException(401, "Account is not active")
    sess.last_activity_at = now
    db.commit()
    return sess, admin
