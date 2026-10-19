import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from superadmin.audit_log.model import AuditLog
from superadmin.audit_log.schema import AuditFilter
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser

# Date filters are calendar days in India (no DST, so a fixed offset is exact).
IST = timezone(timedelta(hours=5, minutes=30))


@dataclass(frozen=True)
class Actor:
    admin_id: UUID
    ip: str | None


class Denied(HTTPException):
    """A 403 that is also written to security_event (FR-10, FR-71) by the handler in main.py."""

    def __init__(self, event_type: str, detail: str, target_id: UUID | None = None):
        super().__init__(403, detail)
        self.event_type, self.target_id = event_type, target_id


def snapshot(obj, fields: list[str]) -> dict[str, Any]:
    return {f: getattr(obj, f) for f in fields}


def changes(before: dict[str, Any], obj) -> tuple[dict, dict]:
    """(before, after) limited to the fields of `before` that changed on obj."""
    changed = [f for f, v in before.items() if getattr(obj, f) != v]
    return {f: before[f] for f in changed}, {f: getattr(obj, f) for f in changed}


def log(db: Session, actor: Actor, action: str, target_table: str, target_id: UUID, city_id: UUID | None,
        before: dict | None = None, after: dict | None = None):
    """Caller commits, so the entry is saved together with the change it describes (or not at all).
    Never pass passwords, secrets or biodata in before/after."""
    db.add(AuditLog(
        actor_type="ADMIN",
        actor_id=actor.admin_id,
        action=action,
        target_table=target_table,
        target_id=str(target_id),
        city_id=city_id,
        before_state=jsonable_encoder(before) if before else None,
        after_state=jsonable_encoder(after) if after else None,
        source_ip=actor.ip,
    ))


def _query(f: AuditFilter):
    q = (
        select(AuditLog, AdminUser.full_name, City.name)
        .outerjoin(AdminUser, AdminUser.admin_id == AuditLog.actor_id)
        .outerjoin(City, City.city_id == AuditLog.city_id)
    )
    if f.date_from:
        q = q.where(AuditLog.occurred_at >= datetime.combine(f.date_from, time(), IST))
    if f.date_to:  # inclusive: the whole of date_to
        q = q.where(AuditLog.occurred_at < datetime.combine(f.date_to + timedelta(days=1), time(), IST))
    if f.actor_id:
        q = q.where(AuditLog.actor_id == f.actor_id)
    if f.action:
        q = q.where(AuditLog.action == f.action)
    if f.city_id:
        q = q.where(AuditLog.city_id == f.city_id)
    return q.order_by(AuditLog.occurred_at.desc(), AuditLog.audit_id.desc())


def _row(entry: AuditLog, actor_name: str | None, city_name: str | None) -> dict:
    return {c.name: getattr(entry, c.name) for c in AuditLog.__table__.columns} | {
        "actor_name": actor_name, "city_name": city_name,
    }


def list_audit_logs(db: Session, f: AuditFilter, limit: int, offset: int) -> dict:
    q = _query(f)
    total = db.scalar(select(func.count()).select_from(q.order_by(None).subquery()))
    rows = db.execute(q.limit(limit).offset(offset))
    return {"total": total, "items": [_row(*r) for r in rows]}


CSV_COLUMNS = ["occurred_at", "actor_type", "actor_name", "actor_id", "action", "target_table", "target_id",
               "city_name", "city_id", "before_state", "after_state", "source_ip"]


def _cell(value) -> str:
    if value is None:
        return ""
    s = json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else str(value)
    # Stops Excel from running a name like "=HYPERLINK(...)" as a formula (CSV injection).
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def export_csv(db: Session, f: AuditFilter) -> bytes:
    # ponytail: built in memory; fine for the monthly review (~50k rows). Stream it if multi-year exports appear.
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_COLUMNS)
    for r in db.execute(_query(f)):
        row = _row(*r)
        w.writerow([_cell(row[c]) for c in CSV_COLUMNS])
    return buf.getvalue().encode("utf-8-sig")  # BOM so Excel shows Hindi/Gujarati names correctly
