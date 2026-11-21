from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from auth import curd
from auth.deps import _bearer, client_ip, get_current_admin, require_city_panel_super_admin, require_super_admin
from auth.schema import (
    ActingCityIn, AdminMeOut, EnrollOut, LoginIn, LoginOut, PasswordChangeIn, TicketIn, TokenOut, VerifyIn,
)
from core import ratelimit
from core.config import settings
from core.database import get_db
from superadmin.city import curd as city_curd
from superadmin.city.model import City
from superadmin.city.schema import CityOut
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
def me(request: Request, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Who is logged in; the sign-in page opens the panel for `role`, which shows its menu and, for a City Admin, its city."""
    city = db.get(City, admin.city_id) if admin.city_id else None
    account = db.get(AdminUser, admin.admin_id)  # the stored row; `admin` is a copy in the City Admin panel
    return {"admin_id": admin.admin_id, "role": admin.role, "full_name": admin.full_name, "email": admin.email,
            "city_id": admin.city_id, "city_name": city.name if city else None,
            "mfa_enrolled_at": admin.mfa_enrolled_at, "is_super_admin": account.role == "SUPER_ADMIN",
            "has_city_panel_password": account.city_panel_password_hash is not None}


@router.get("/cities", response_model=list[CityOut], dependencies=[Depends(require_city_panel_super_admin)])
def acting_city_choices(db: Session = Depends(get_db)):
    """Super Admin in the City Admin panel: the cities they can act for."""
    return city_curd.list_cities(db, is_active=True)


@router.put("/city", status_code=204, dependencies=[Depends(require_city_panel_super_admin)])
def choose_acting_city(data: ActingCityIn, request: Request, db: Session = Depends(get_db)):
    """Super Admin in the City Admin panel: act as the City Admin of this city (switchable any time; re-read /me)."""
    city = db.get(City, data.city_id)
    if not city or not city.is_active:
        raise HTTPException(404, "City not found")
    request.state.auth_session.acting_city_id = city.city_id
    db.commit()


@router.post("/city-panel-password", status_code=204)
def set_city_panel_password(data: PasswordChangeIn, request: Request,
                            admin: AdminUser = Depends(require_super_admin), db: Session = Depends(get_db)):
    """Super Admin panel only: set the second password that opens the City Admin panel. current_password is the
    Super Admin password; the new one must differ from it."""
    curd.set_city_panel_password(db, admin, data.current_password, data.new_password, client_ip(request))


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
