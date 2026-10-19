from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from member.profile.model import Member
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser

ESCALATE_AFTER = timedelta(hours=72)  # FR-16


def list_overdue(db: Session) -> list[dict]:
    """Registrations pending > 72 h in any city, oldest first, with the city's active admin (None: city has none).
    ponytail: a list only; the email in FR-16 comes with an email sender."""
    rows = db.execute(
        select(Member, City.name, AdminUser.admin_id, AdminUser.full_name)
        .join(City, City.city_id == Member.city_id)
        .outerjoin(AdminUser, and_(AdminUser.city_id == Member.city_id, AdminUser.role == "CITY_ADMIN",
                                   AdminUser.status == "ACTIVE"))
        .where(Member.status == "PENDING", Member.deleted_at.is_(None),
               # ponytail: first-time registrations only. Profiles back in review after an edit (ASM-10)
               # have no "resubmitted at" time; add member.submitted_at if those should escalate too.
               Member.reviewed_at.is_(None),
               Member.created_at < datetime.now(timezone.utc) - ESCALATE_AFTER)
        .order_by(Member.created_at)
    )
    return [{
        "member_id": m.member_id, "full_name": m.full_name, "created_at": m.created_at,
        "city_id": m.city_id, "city_name": city_name,
        "city_admin_id": admin_id, "city_admin_name": admin_name,
    } for m, city_name, admin_id, admin_name in rows]
