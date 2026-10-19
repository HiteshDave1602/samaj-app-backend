from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    metadata = MetaData(schema="samaj")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
