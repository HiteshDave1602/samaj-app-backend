from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cityadmin.panchang.model import PanchangDay, PanchangRevision
from cityadmin.panchang.schema import PanchangIn
from superadmin.audit_log import curd as audit
from superadmin.audit_log.curd import IST
from superadmin.city_admin.model import AdminUser

LOCATION = "DEFAULT"  # ASM-05: one Panchang per deployment
ALERT_AT = time(4, 0)  # FR-60: ERR_API_PN from 04:00 IST, leaving an hour to publish by 05:00
FIELDS = ["tithi", "nakshatra", "yoga", "source"]
ERR_API_PN = ("No Panchang for today yet. Enter Tithi, Nakshatra and Yoga manually, checked against the "
              "Samaj Panchang calendar, before 05:00 AM.")


def _day(db: Session, d: date, lock: bool = False) -> PanchangDay | None:
    q = select(PanchangDay).where(PanchangDay.location_code == LOCATION, PanchangDay.panchang_date == d)
    return db.scalar(q.with_for_update() if lock else q)


def _out(row, editor_name: str | None) -> dict:
    return {c.name: getattr(row, c.name) for c in row.__table__.columns} | {"edited_by_name": editor_name}


def list_days(db: Session, date_from: date, date_to: date) -> list[dict]:
    rows = db.execute(
        select(PanchangDay, AdminUser.full_name)
        .outerjoin(AdminUser, AdminUser.admin_id == PanchangDay.edited_by_admin_id)
        .where(PanchangDay.location_code == LOCATION, PanchangDay.panchang_date.between(date_from, date_to))
        .order_by(PanchangDay.panchang_date))
    return [_out(*r) for r in rows]


def get_day(db: Session, d: date) -> dict:
    day = _day(db, d)
    if day is None:
        raise HTTPException(404, f"No Panchang for {d} yet")
    editor = db.get(AdminUser, day.edited_by_admin_id) if day.edited_by_admin_id else None
    revisions = db.execute(
        select(PanchangRevision, AdminUser.full_name)
        .outerjoin(AdminUser, AdminUser.admin_id == PanchangRevision.edited_by_admin_id)
        .where(PanchangRevision.panchang_id == day.panchang_id)
        .order_by(PanchangRevision.created_at.desc()))
    return _out(day, editor.full_name if editor else None) | {"revisions": [_out(*r) for r in revisions]}


def set_manual(db: Session, admin: AdminUser, actor: audit.Actor, d: date, data: PanchangIn) -> dict:
    """FR-61/62: enter or correct a day. Manual values replace API values and are published at once."""
    day = _day(db, d, lock=True)
    before = audit.snapshot(day, FIELDS) if day else None
    if day is None:
        day = PanchangDay(panchang_id=uuid4(), panchang_date=d, location_code=LOCATION)
        db.add(day)
    day.tithi, day.nakshatra, day.yoga = data.tithi, data.nakshatra, data.yoga
    day.source, day.verified_against_calendar, day.edited_by_admin_id = "MANUAL", True, admin.admin_id
    day.published_at = day.published_at or datetime.now(timezone.utc)
    try:
        db.flush()  # the day row first: the revision's FK points at it
        db.add(PanchangRevision(panchang_id=day.panchang_id, tithi=day.tithi, nakshatra=day.nakshatra, yoga=day.yoga,
                                source="MANUAL", edited_by_admin_id=admin.admin_id))
        audit.log(db, actor, "PANCHANG_OVERRIDE", "panchang_day", day.panchang_id, admin.city_id,
                  before, audit.snapshot(day, FIELDS) | {"panchang_date": d})
        db.commit()
    except IntegrityError:  # another admin created the same date at the same moment
        db.rollback()
        raise HTTPException(409, "This date was just saved by someone else. Reload and check it.")
    return get_day(db, d)


def status(db: Session, now: datetime) -> dict:
    """FR-60 as the dashboard sees it. ponytail: no push/email alert yet (notification outbox), and no
    astrology API fetch yet (provider not chosen, DEP-01), so until then every day needs manual entry."""
    now_ist = now.astimezone(IST)
    today = _day(db, now_ist.date())
    alert = today is None and now_ist.time() >= ALERT_AT
    return {
        "date": now_ist.date(),
        "available": today is not None,
        "source": today.source if today else None,
        "tomorrow_available": _day(db, now_ist.date() + timedelta(days=1)) is not None,
        "error_code": "ERR_API_PN" if alert else None,
        "message": ERR_API_PN if alert else None,
    }
