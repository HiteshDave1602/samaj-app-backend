from sqlalchemy import Boolean, Column, DateTime, String, false, func


class BaseTemplate:
    """Audit columns every table gets (via Base in core/database.py)."""
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    created_by = Column(String(64))
    updated_by = Column(String(64))
    is_deleted = Column(Boolean, nullable=False, default=False, server_default=false())
