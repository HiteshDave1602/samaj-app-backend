from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.deps import get_actor, require_city_admin
from cityadmin.panchang import curd
from cityadmin.panchang.schema import PanchangDetail, PanchangIn, PanchangOut, PanchangStatus
from core.database import get_db
from superadmin.audit_log.curd import IST, Actor
from superadmin.city_admin.model import AdminUser

# One Panchang for the whole deployment (ASM-05); any City Admin can enter or correct a day (SF-09).
router = APIRouter(prefix="/cityadmin/panchang", tags=["City Admin: Panchang"])


@router.get("/status", response_model=PanchangStatus)
def status(admin: AdminUser = Depends(require_city_admin), db: Session = Depends(get_db)):
    """Poll from the dashboard: error_code ERR_API_PN means today's Panchang must be entered by hand now."""
    return curd.status(db, datetime.now(timezone.utc))


@router.get("", response_model=list[PanchangOut])
def list_days(
    date_from: date | None = None,
    date_to: date | None = None,
    admin: AdminUser = Depends(require_city_admin),
    db: Session = Depends(get_db),
):
    """Days that have values, by date. Defaults to today and the next 6 days (IST); at most 92 days."""
    date_from = date_from or datetime.now(IST).date()
    date_to = date_to or date_from + timedelta(days=6)
    if not timedelta(0) <= date_to - date_from <= timedelta(days=92):
        raise HTTPException(400, "date_to must be on or after date_from, and at most 92 days later")
    return curd.list_days(db, date_from, date_to)


@router.get("/{panchang_date}", response_model=PanchangDetail)
def get_day(panchang_date: date, admin: AdminUser = Depends(require_city_admin), db: Session = Depends(get_db)):
    return curd.get_day(db, panchang_date)


@router.put("/{panchang_date}", response_model=PanchangDetail)
def set_manual(
    panchang_date: date,
    data: PanchangIn,
    admin: AdminUser = Depends(require_city_admin),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    return curd.set_manual(db, admin, actor, panchang_date, data)
