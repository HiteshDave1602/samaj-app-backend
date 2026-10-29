from sqlalchemy import Boolean, Column, DateTime, String, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB

from core.database import Base


class City(Base):
    __tablename__ = "city"
    __table_args__ = (UniqueConstraint("name", "state", name="uq_city_name_state"),)

    city_id = Column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    name = Column(String(80), nullable=False)
    name_i18n = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # {"gu": ..., "hi": ...}
    state = Column(String(60), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
