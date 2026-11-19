from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from auth import curd
from auth.deps import _bearer, client_ip, get_current_admin
from auth.schema import AdminMeOut, EnrollOut, LoginIn, LoginOut, PasswordChangeIn, TicketIn, TokenOut, VerifyIn
from core import ratelimit
from core.config import settings
from core.database import get_db
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser

# Flow: POST /login -> (first time) POST /mfa/enroll -> POST /mfa/verify -> Bearer token.
router = APIRouter(prefix="/admin/auth", tags=["Admin Auth"])


def _per_ip(request: Request):
    """Login / MFA calls per client IP; the per-email failure lock (curd) can't see guesses spread over emails."""
    ratelimit.check("admin_auth", client_ip(request), settings.auth_ip_rate_per_minute)


@router.post("/login", response_model=LoginOut, dependencies=[Depends(_per_ip)])
def login(data: LoginIn, db: Session = Depends(get_db)):
    return curd.login(db, data.email, data.password)


@router.post("/mfa/enroll", response_model=EnrollOut, dependencies=[Depends(_per_ip)])
def enroll_mfa(data: TicketIn, db: Session = Depends(get_db)):
    return curd.enroll_mfa(db, data.mfa_ticket)


@router.post("/mfa/verify", response_model=TokenOut, dependencies=[Depends(_per_ip)])
def verify_mfa(data: VerifyIn, db: Session = Depends(get_db)):
    return curd.verify_mfa(db, data.mfa_ticket, data.code)


@router.get("/me", response_model=AdminMeOut)
def me(admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Who is logged in; the dashboard shows the menu for `role` and, for a City Admin, its city."""
    city = db.get(City, admin.city_id) if admin.city_id else None
    return {"admin_id": admin.admin_id, "role": admin.role, "full_name": admin.full_name, "email": admin.email,
            "city_id": admin.city_id, "city_name": city.name if city else None,
            "mfa_enrolled_at": admin.mfa_enrolled_at}


@router.post("/logout", status_code=204)
def logout(creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)):
    if creds is None:
        raise HTTPException(401, "Not authenticated")
    curd.logout(db, creds.credentials)


@router.post("/change-password", status_code=204)
def change_password(data: PasswordChangeIn, request: Request,
                    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)):
    """The signed-in admin changes their own password; other devices are signed out."""
    if creds is None:
        raise HTTPException(401, "Not authenticated")
    curd.change_password(db, creds.credentials, data.current_password, data.new_password, client_ip(request))
