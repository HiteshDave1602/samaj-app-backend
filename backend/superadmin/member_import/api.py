from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, UploadFile
from sqlalchemy.orm import Session

from auth.deps import get_actor, require_super_admin
from cityadmin.member_import.api import MIME
from cityadmin.member_import.schema import ImportJobOut, ImportJobPage, ImportRowPage
from core.database import get_db
from superadmin.audit_log.curd import Actor
from superadmin.city_admin.model import AdminUser
from superadmin.member_import import curd

# Directory import: GET /template -> POST "" (file) = dry-run report -> GET /{id}/rows -> POST /{id}/commit.
# Each row names its own city (Section (City)); a Self row and the rows below it form one household.
router = APIRouter(prefix="/superadmin/imports", tags=["Super Admin: Directory Import"])


@router.get("/template", response_class=Response)
def template(file_format: Literal["CSV", "XLSX"] = "XLSX", admin: AdminUser = Depends(require_super_admin)):
    name = f"samaj-directory-import-{curd.TEMPLATE_VERSION}.{file_format.lower()}"
    return Response(curd.template(file_format), media_type=MIME[file_format],
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("", response_model=ImportJobOut, status_code=201)
def upload(file: UploadFile, admin: AdminUser = Depends(require_super_admin), db: Session = Depends(get_db)):
    """Checks the file and returns the dry-run counts. Wrong headers: 400 and nothing is saved."""
    return curd.upload(db, admin, file.filename, file.file.read(curd.MAX_BYTES + 1))


@router.get("", response_model=ImportJobPage)
def list_jobs(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
              admin: AdminUser = Depends(require_super_admin), db: Session = Depends(get_db)):
    """Directory imports, newest first."""
    return curd.list_jobs(db, limit, offset)


@router.get("/{import_job_id}", response_model=ImportJobOut)
def get_job(import_job_id: UUID, admin: AdminUser = Depends(require_super_admin), db: Session = Depends(get_db)):
    return curd.get_job(db, import_job_id)


@router.get("/{import_job_id}/rows", response_model=ImportRowPage)
def list_rows(
    import_job_id: UUID,
    outcome: Literal["NEW", "UPDATE", "ERROR"] | None = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return curd.list_rows(db, import_job_id, limit, offset, outcome)


@router.post("/{import_job_id}/commit", response_model=ImportJobOut)
def commit(import_job_id: UUID, admin: AdminUser = Depends(require_super_admin),
           actor: Actor = Depends(get_actor), db: Session = Depends(get_db)):
    return curd.commit(db, admin, actor, import_job_id)
