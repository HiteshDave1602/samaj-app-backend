from sqlalchemy import (
    CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Uuid, text,
)

from core.database import Base
import member.profile.model  # noqa: F401  registers member, city and admin_user for the FKs


class ImportJob(Base):
    """A CSV/XLSX member-list upload (SOP §6.5): validated -> dry-run report -> committed.
    A header mismatch rejects the file before anything is written (FR-76), so no job exists for it."""
    __tablename__ = "import_job"
    __table_args__ = (
        CheckConstraint("file_format IN ('CSV','XLSX')", name="ck_import_job_file_format"),
        CheckConstraint("status IN ('VALIDATING','REJECTED','DRY_RUN_READY','COMMITTING','COMMITTED','FAILED')",
                        name="ck_import_job_status"),
        CheckConstraint("total_rows <= 50000", name="ck_import_job_total_rows"),
        Index("ix_import_job_city_time", "city_id", text("created_at DESC")),
        Index("ix_import_job_uploaded_by", "uploaded_by_admin_id"),
    )

    import_job_id = Column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    city_id = Column(Uuid, ForeignKey("samaj.city.city_id", ondelete="RESTRICT"), nullable=False)
    uploaded_by_admin_id = Column(Uuid, ForeignKey("samaj.admin_user.admin_id", ondelete="RESTRICT"), nullable=False)
    file_key = Column(String(255), nullable=False)  # core.private_files key of the uploaded file
    file_format = Column(String(4), nullable=False)
    template_version = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, server_default="VALIDATING")
    total_rows = Column(Integer)
    new_count = Column(Integer, nullable=False, server_default=text("0"))
    updated_count = Column(Integer, nullable=False, server_default=text("0"))
    conflict_count = Column(Integer, nullable=False, server_default=text("0"))
    error_count = Column(Integer, nullable=False, server_default=text("0"))
    report_key = Column(String(255))
    committed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class ImportRow(Base):
    """One row of an import with its dedup outcome. payload_enc is the Fernet-encrypted cleaned row."""
    __tablename__ = "import_row"
    __table_args__ = (
        CheckConstraint("outcome IN ('NEW','UPDATE','CONFLICT','ERROR')", name="ck_import_row_outcome"),
        CheckConstraint("resolution IN ('APPLIED','SKIPPED')", name="ck_import_row_resolution"),
        Index("ix_import_row_conflicts", "import_job_id",
              postgresql_where=text("outcome = 'CONFLICT' AND resolution IS NULL")),
        Index("ix_import_row_member", "matched_member_id"),
    )

    import_job_id = Column(Uuid, ForeignKey("samaj.import_job.import_job_id", ondelete="CASCADE"), primary_key=True)
    row_number = Column(Integer, primary_key=True)  # spreadsheet row; the header is row 1
    outcome = Column(String(8), nullable=False)
    mobile_hash = Column(LargeBinary)
    matched_member_id = Column(Uuid, ForeignKey("samaj.member.member_id", ondelete="SET NULL"))
    payload_enc = Column(LargeBinary)
    error_message = Column(String(500))
    resolution = Column(String(10))  # APPLIED | SKIPPED
