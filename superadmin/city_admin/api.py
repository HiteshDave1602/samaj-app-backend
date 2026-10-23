from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.deps import get_actor, require_super_admin
from core.database import get_db
from superadmin.audit_log.curd import Actor
from superadmin.city_admin import curd
from superadmin.city_admin.schema import CityAdminCreate, CityAdminOut, CityAdminUpdate, PasswordReset

router = APIRouter(
    prefix="/superadmin/city-admins",
    tags=["Super Admin: City Admins"],
    dependencies=[Depends(require_super_admin)],
)


@router.post("", response_model=CityAdminOut, status_code=201)
def create_city_admin(data: CityAdminCreate, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    return curd.create_city_admin(db, data, actor)


@router.get("", response_model=list[CityAdminOut])
def list_city_admins(
    city_id: UUID | None = None,
    status: Literal["ACTIVE", "SUSPENDED", "DEACTIVATED"] | None = None,
    db: Session = Depends(get_db),
):
    return curd.list_city_admins(db, city_id, status)


@router.get("/{admin_id}", response_model=CityAdminOut)
def get_city_admin(admin_id: UUID, db: Session = Depends(get_db)):
    return curd.get_city_admin(db, admin_id)


@router.put("/{admin_id}", response_model=CityAdminOut)
def update_city_admin(
    admin_id: UUID, data: CityAdminUpdate, db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
):
    return curd.update_city_admin(db, admin_id, data, actor)


@router.post("/{admin_id}/reset-mfa", response_model=CityAdminOut)
def reset_mfa(admin_id: UUID, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    return curd.reset_mfa(db, admin_id, actor)


@router.post("/{admin_id}/reset-password", response_model=CityAdminOut)
def reset_password(
    admin_id: UUID, data: PasswordReset, db: Session = Depends(get_db), actor: Actor = Depends(get_actor),
):
    return curd.reset_password(db, admin_id, data.new_password, actor)
