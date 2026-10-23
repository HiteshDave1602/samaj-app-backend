from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from auth import curd
from auth.deps import _bearer, get_current_admin
from auth.schema import AdminMeOut, EnrollOut, LoginIn, LoginOut, TicketIn, TokenOut, VerifyIn
from core.database import get_db
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser

# Flow: POST /login -> (first time) POST /mfa/enroll -> POST /mfa/verify -> Bearer token.
router = APIRouter(prefix="/admin/auth", tags=["Admin Auth"])


@router.post("/login", response_model=LoginOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    return curd.login(db, data.email, data.password)


@router.post("/mfa/enroll", response_model=EnrollOut)
def enroll_mfa(data: TicketIn, db: Session = Depends(get_db)):
    return curd.enroll_mfa(db, data.mfa_ticket)


@router.post("/mfa/verify", response_model=TokenOut)
def verify_mfa(data: VerifyIn, db: Session = Depends(get_db)):
    return curd.verify_mfa(db, data.mfa_ticket, data.code)


@router.get("/me", response_model=AdminMeOut)
def me(admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Who is logged in; the dashboard shows the menu for `role` and, for a City Admin, its city."""
    city = db.get(City, admin.city_id) if admin.city_id else None
    return {"admin_id": admin.admin_id, "role": admin.role, "full_name": admin.full_name, "email": admin.email,
            "city_id": admin.city_id, "city_name": city.name if city else None}


@router.post("/logout", status_code=204)
def logout(creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)):
    if creds is None:
        raise HTTPException(401, "Not authenticated")
    curd.logout(db, creds.credentials)
