from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
State = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class CityCreate(BaseModel):
    name: Name
    state: State


class CityUpdate(BaseModel):
    name: Name | None = None
    state: State | None = None
    is_active: bool | None = None


class CityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    city_id: UUID
    name: str
    state: str
    is_active: bool
    created_at: datetime
