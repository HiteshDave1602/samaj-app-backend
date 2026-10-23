from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from auth.deps import get_actor, require_city_admin
from cityadmin.member_export import curd
from cityadmin.member_export.schema import ExportIn, ExportJobPage
from core.database import get_db
from superadmin.audit_log.curd import Actor
from superadmin.city_admin.model import AdminUser

# 'Export Filtered' (SF-13): own city's members only (FR-71), never biodata (FR-84).
router = APIRouter(prefix="/cityadmin/exports", tags=["City Admin: Member Export"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post("", response_class=Response, responses={200: {"content": {XLSX: {}}}})
def export(
    data: ExportIn,
    admin: AdminUser = Depends(require_city_admin),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    """Returns the password-protected .xlsx; X-Row-Count says how many members it holds."""
    file, row_count = curd.export(db, admin, actor, data)
    return Response(file, media_type=XLSX, headers={
        "Content-Disposition": f'attachment; filename="{curd.filename()}"',
        "X-Row-Count": str(row_count),
        "Cache-Control": "no-store",
    })


@router.get("", response_model=ExportJobPage)
def list_jobs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_city_admin),
    db: Session = Depends(get_db),
):
    """Own city's export history, newest first: who exported, which filters and columns, how many rows."""
    return curd.list_jobs(db, admin, limit, offset)
