from sqlalchemy import ARRAY, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB

from core.database import Base
import superadmin.city.model  # noqa: F401  registers city and admin_user for the FKs
import superadmin.city_admin.model  # noqa: F401


class ExportJob(Base):
    """Record of an 'Export Filtered' (FR-82). The password and the file are never stored (FR-85)."""
    __tablename__ = "export_job"
    __table_args__ = (
        CheckConstraint("row_count >= 0", name="ck_export_job_row_count"),
        CheckConstraint("file_format IN ('CSV','XLSX')", name="ck_export_job_file_format"),
        Index("ix_export_job_admin_time", "exported_by_admin_id", text("created_at DESC")),
        Index("ix_export_job_city", "city_id"),
    )

    export_job_id = Column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    city_id = Column(Uuid, ForeignKey("samaj.city.city_id", ondelete="RESTRICT"))
    exported_by_admin_id = Column(Uuid, ForeignKey("samaj.admin_user.admin_id", ondelete="RESTRICT"), nullable=False)
    filters = Column(JSONB, nullable=False)
    columns_exported = Column(ARRAY(Text), nullable=False)
    row_count = Column(Integer, nullable=False)
    file_format = Column(String(4), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
