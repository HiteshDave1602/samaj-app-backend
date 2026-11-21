from ipaddress import ip_address

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from auth import curd
from core import ratelimit
from core.config import settings
from core.guard import envelope
from core.database import SessionLocal, get_db
from superadmin.audit_log.curd import Actor, Denied
from superadmin.audit_log.model import SecurityEvent
from superadmin.city_admin.model import AdminUser

_bearer = HTTPBearer(auto_error=False)


def get_current_admin(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> AdminUser:
    if creds is None:
        raise HTTPException(401, "Not authenticated")
    sess, admin = curd.session_admin(db, creds.credentials)
    request.state.admin_id = admin.admin_id  # for log_denied
    request.state.auth_session = sess
    ratelimit.check("admin", admin.admin_id, settings.admin_rate_per_minute)  # every admin route comes through here
    if sess.city_panel:
        # Super Admin in the City Admin panel: a never-saved City Admin copy scoped to the chosen city, so every
        # City Admin route and city filter applies unchanged, and every Super Admin route refuses it.
        admin = AdminUser(admin_id=admin.admin_id, role="CITY_ADMIN", city_id=sess.acting_city_id, status=admin.status,
                          full_name=admin.full_name, email=admin.email, mfa_enrolled_at=admin.mfa_enrolled_at)
    return admin


def require_super_admin(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
    if admin.role != "SUPER_ADMIN":
        raise HTTPException(403, "Super Admin only")
    return admin


def require_city_admin(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
    """City scope (FR-71) is then enforced per query with admin.city_id."""
    if admin.role != "CITY_ADMIN":
        raise HTTPException(403, "City Admin only")
    if admin.city_id is None:
        raise HTTPException(409, "Choose a city first")  # Super Admin in the City Admin panel, no city picked yet
    return admin


def require_city_panel_super_admin(request: Request, admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
    if not request.state.auth_session.city_panel:
        raise HTTPException(403, "Only for the Super Admin in the City Admin panel")
    return admin


def get_actor(request: Request, admin: AdminUser = Depends(get_current_admin)) -> Actor:
    """Who is acting, for audit entries. Role checks stay on the router; this only identifies the caller.
    Behind a proxy, run uvicorn with --proxy-headers so request.client is the real client IP."""
    return Actor(admin_id=admin.admin_id, ip=client_ip(request))


def client_ip(request: Request) -> str | None:
    host = request.client.host if request.client else None
    try:
        return str(ip_address(host)) if host else None
    except ValueError:  # e.g. "testclient"; a non-IP must not fail a write to an INET column
        return None


def log_denied(request: Request, exc: Denied) -> JSONResponse:
    """Exception handler: records the denial, then answers 403 as usual."""
    admin_id = getattr(request.state, "admin_id", None)
    member_id = getattr(request.state, "member_id", None)
    actor_type = "ADMIN" if admin_id else "MEMBER" if member_id else "ANONYMOUS"
    with SessionLocal() as db:  # own transaction: the request's is abandoned with the error
        db.add(SecurityEvent(
            event_type=exc.event_type, actor_type=actor_type, actor_id=admin_id or member_id,
            endpoint=f"{request.method} {request.url.path}"[:120],
            target_id=str(exc.target_id) if exc.target_id else None, reason=exc.detail[:200],
            source_ip=client_ip(request),
        ))
        db.commit()
    return envelope(403, exc.detail)
