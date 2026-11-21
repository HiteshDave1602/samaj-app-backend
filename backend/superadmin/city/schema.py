from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from core.validation import Place, Strict

Name = Place(80)
State = Place(60)


class CityCreate(Strict):
    name: Name
    state: State


class CityUpdate(Strict):
    name: Name | None = None
    state: State | None = None
    is_active: bool | None = None


class CityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    city_id: UUID
    name: str
    name_i18n: dict[str, str]  # {"gu": ..., "hi": ...}, auto-transliterated
    state: str
    is_active: bool
    created_at: datetime
