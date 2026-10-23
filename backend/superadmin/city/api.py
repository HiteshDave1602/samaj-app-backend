from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.deps import get_actor, require_super_admin
from core.database import get_db
from superadmin.audit_log.curd import Actor
from superadmin.city import curd
from superadmin.city.schema import CityCreate, CityOut, CityUpdate

# No DELETE: admins/members reference cities (FK RESTRICT); deactivate with is_active=false instead.
router = APIRouter(
    prefix="/superadmin/cities",
    tags=["Super Admin: Cities"],
    dependencies=[Depends(require_super_admin)],
)


@router.post("", response_model=CityOut, status_code=201)
def create_city(data: CityCreate, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    return curd.create_city(db, data, actor)


@router.get("", response_model=list[CityOut])
def list_cities(is_active: bool | None = None, db: Session = Depends(get_db)):
    return curd.list_cities(db, is_active)


@router.get("/{city_id}", response_model=CityOut)
def get_city(city_id: UUID, db: Session = Depends(get_db)):
    return curd.get_city(db, city_id)


@router.put("/{city_id}", response_model=CityOut)
def update_city(city_id: UUID, data: CityUpdate, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    return curd.update_city(db, city_id, data, actor)
