from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from superadmin.audit_log import curd as audit
from superadmin.city.model import City
from superadmin.city.schema import CityCreate, CityUpdate


def _check_name_free(db: Session, name: str, state: str, exclude_id: UUID | None = None):
    # Case-insensitive so "Pune"/"pune" don't become two cities; the DB constraint is exact-match only.
    q = select(City.city_id).where(func.lower(City.name) == name.lower(), func.lower(City.state) == state.lower())
    if exclude_id:
        q = q.where(City.city_id != exclude_id)
    if db.scalar(q):
        raise HTTPException(409, "A city with this name already exists in this state")


def _commit(db: Session, city: City) -> City:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A city with this name already exists in this state")
    db.refresh(city)
    return city


FIELDS = ["name", "state", "is_active"]


def create_city(db: Session, data: CityCreate, actor: audit.Actor) -> City:
    _check_name_free(db, data.name, data.state)
    city = City(city_id=uuid4(), name=data.name, state=data.state)  # id set here so the audit entry can use it
    db.add(city)
    audit.log(db, actor, "CITY_CREATE", "city", city.city_id, city.city_id,
              after={"name": data.name, "state": data.state})
    return _commit(db, city)


def list_cities(db: Session, is_active: bool | None = None) -> list[City]:
    q = select(City).order_by(City.state, City.name)
    if is_active is not None:
        q = q.where(City.is_active == is_active)
    return list(db.scalars(q))


def get_city(db: Session, city_id: UUID) -> City:
    city = db.get(City, city_id)
    if not city:
        raise HTTPException(404, "City not found")
    return city


def update_city(db: Session, city_id: UUID, data: CityUpdate, actor: audit.Actor) -> City:
    city = get_city(db, city_id)
    before = audit.snapshot(city, FIELDS)
    name = data.name if data.name is not None else city.name
    state = data.state if data.state is not None else city.state
    if (name, state) != (city.name, city.state):
        _check_name_free(db, name, state, exclude_id=city.city_id)
        city.name, city.state = name, state
    if data.is_active is not None:
        # ponytail: deactivating only blocks new City Admins (see city_admin.curd);
        # existing admins/members are untouched until member features define what it should mean.
        city.is_active = data.is_active
    old, new = audit.changes(before, city)
    if new:
        audit.log(db, actor, "CITY_UPDATE", "city", city.city_id, city.city_id, old, new)
    return _commit(db, city)
