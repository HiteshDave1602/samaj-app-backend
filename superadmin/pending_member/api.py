from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.deps import require_super_admin
from core.database import get_db
from superadmin.pending_member import curd
from superadmin.pending_member.schema import OverdueMemberOut

router = APIRouter(
    prefix="/superadmin/pending-members",
    tags=["Super Admin: Pending Members"],
    dependencies=[Depends(require_super_admin)],
)


@router.get("/overdue", response_model=list[OverdueMemberOut])
def list_overdue(db: Session = Depends(get_db)):
    return curd.list_overdue(db)
