from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from auth.deps import require_super_admin
from core.database import get_db
from superadmin.audit_log import curd
from superadmin.audit_log.schema import AuditFilter, AuditLogPage, AuditPageQuery

# Read-only: entries are written by the actions themselves (curd.log), never through this API.
router = APIRouter(
    prefix="/superadmin/audit-logs",
    tags=["Super Admin: Audit Log"],
    dependencies=[Depends(require_super_admin)],
)


@router.get("", response_model=AuditLogPage)
def list_audit_logs(q: Annotated[AuditPageQuery, Query()], db: Session = Depends(get_db)):
    return curd.list_audit_logs(db, q, q.limit, q.offset)


@router.get("/export.csv")
def export_audit_logs(filters: Annotated[AuditFilter, Query()], db: Session = Depends(get_db)):
    return Response(
        curd.export_csv(db, filters),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="audit-log.csv"'},
    )
