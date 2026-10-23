from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from cityadmin.panchang.curd import LOCATION
from cityadmin.panchang.model import PanchangDay
from core.database import get_db
from member.auth.deps import get_current_member
from member.profile.model import Member
from superadmin.audit_log.curd import IST

router = APIRouter(prefix="/member", tags=["Member Panchang"])


class PanchangOut(BaseModel):
    panchang_date: date
    tithi: str
    nakshatra: str
    yoga: str


@router.get("/panchang", response_model=PanchangOut)
def panchang(date: date | None = None, member: Member = Depends(get_current_member), db: Session = Depends(get_db)):
    """FR-59: today's Tithi, Nakshatra and Yoga (IST); ?date= for another day (FR-64).
    PENDING members see it too (FR-08). 404 until the day is published."""
    d = date or datetime.now(IST).date()
    day = db.scalar(select(PanchangDay).where(PanchangDay.location_code == LOCATION, PanchangDay.panchang_date == d,
                                              PanchangDay.published_at.is_not(None)))
    if day is None:
        raise HTTPException(404, f"Panchang for {d} is not available yet")
    return day
