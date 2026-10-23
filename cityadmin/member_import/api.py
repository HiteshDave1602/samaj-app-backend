from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, UploadFile
from sqlalchemy.orm import Session

from auth.deps import get_actor, require_city_admin
from cityadmin.member_import import curd
from cityadmin.member_import.schema import ImportJobOut, ImportJobPage, ImportRowOut, ImportRowPage, ResolveIn
from core.database import get_db
from superadmin.audit_log.curd import Actor
from superadmin.city_admin.model import AdminUser

# Flow (SF-12): GET /template -> POST "" (file) = dry-run report -> GET /{id}/rows to review
# -> POST /{id}/commit -> POST /{id}/rows/{n}/resolve for each conflict.
router = APIRouter(prefix="/cityadmin/imports", tags=["City Admin: Member Import"])
MIME = {"CSV": "text/csv", "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


@router.get("/template", response_class=Response)
def template(file_format: Literal["CSV", "XLSX"] = "XLSX", admin: AdminUser = Depends(require_city_admin)):
    name = f"samaj-member-import-{curd.TEMPLATE_VERSION}.{file_format.lower()}"
    return Response(curd.template(file_format), media_type=MIME[file_format],
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("", response_model=ImportJobOut, status_code=201)
def upload(file: UploadFile, admin: AdminUser = Depends(require_city_admin), db: Session = Depends(get_db)):
    """Checks the file and returns the dry-run counts. Wrong headers: 400 and nothing is saved."""
    return curd.upload(db, admin, file.filename, file.file.read(curd.MAX_BYTES + 1))


@router.get("", response_model=ImportJobPage)
def list_jobs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_city_admin),
    db: Session = Depends(get_db),
):
    """Own city's imports, newest first."""
    return curd.list_jobs(db, admin, limit, offset)


@router.get("/{import_job_id}", response_model=ImportJobOut)
def get_job(import_job_id: UUID, admin: AdminUser = Depends(require_city_admin), db: Session = Depends(get_db)):
    return curd.get_job(db, admin, import_job_id)


@router.get("/{import_job_id}/rows", response_model=ImportRowPage)
def list_rows(
    import_job_id: UUID,
    outcome: Literal["NEW", "UPDATE", "CONFLICT", "ERROR"] | None = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_city_admin),
    db: Session = Depends(get_db),
):
    return curd.list_rows(db, admin, import_job_id, limit, offset, outcome)


@router.post("/{import_job_id}/commit", response_model=ImportJobOut)
def commit(
    import_job_id: UUID,
    admin: AdminUser = Depends(require_city_admin),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    return curd.commit(db, admin, actor, import_job_id)


@router.post("/{import_job_id}/rows/{row_number}/resolve", response_model=ImportRowOut)
def resolve(
    import_job_id: UUID,
    row_number: int,
    data: ResolveIn,
    admin: AdminUser = Depends(require_city_admin),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    return curd.resolve(db, admin, actor, import_job_id, row_number, data.action)
