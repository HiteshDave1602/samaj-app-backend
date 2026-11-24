from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import String, cast, func, literal, select, true, union_all, update
from sqlalchemy.orm import Session

from auth.deps import get_current_admin
from cityadmin.content.model import ContentItem
from cityadmin.member_approval.curd import city_filter
from core.database import get_db
from member.matrimony.model import MatrimonyPhoto, MatrimonyProfile
from member.profile.model import FamilyMember, Household, Member
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser

# The admin bell: what members are waiting on, newest first, read straight from the pending queues, so an item
# drops out the moment anyone decides it. A City Admin sees their city; the Super Admin every city (FR-71).
# Read state is admin_user.requests_seen_at, so the badge is the same on every device.
# Flow: GET (badge = unread) -> open the screen -> POST /read.
# ponytail: one seen_at per admin, so the Super Admin opening the bell in the City panel also marks other cities'
# older requests read; add a per-scope seen_at if that matters.
router = APIRouter(prefix="/admin/requests", tags=["Admin Requests"])


class RequestOut(BaseModel):
    id: UUID
    kind: str  # REGISTRATION | FAMILY | PROFILE | PHOTOS | NEWS
    member_name: str | None
    detail: str | None  # REGISTRATION: city not set up yet; FAMILY: the relative's name; PHOTOS: how many; NEWS: title
    at: datetime
    city_name: str | None
    unread: bool


class RequestPage(BaseModel):
    total: int
    unread: int
    items: list[RequestOut]


def _seen_at(db: Session, admin: AdminUser):
    # by id: in the City panel the Super Admin is an unsaved copy (auth.deps), the stored row is theirs
    return db.scalar(select(AdminUser.requests_seen_at).where(AdminUser.admin_id == admin.admin_id))


def _queues(admin: AdminUser):
    def row(id_, kind, name, detail, at, city_id):
        return select(id_.label("id"), literal(kind, String).label("kind"), name.label("member_name"),
                      cast(detail, String).label("detail"), at.label("at"), city_id.label("city_id"))

    # detail: the city typed at registration when it isn't set up yet (city_id null: only the Super Admin sees it)
    registrations = (row(Member.member_id, "REGISTRATION", Member.full_name, Member.requested_city, Member.created_at,
                         Member.city_id)
                     .where(Member.status == "PENDING", Member.deleted_at.is_(None), *city_filter(Member.city_id, admin)))
    family = (row(FamilyMember.family_member_id, "FAMILY", Member.full_name, FamilyMember.full_name,
                  FamilyMember.created_at, Household.city_id)
              .join(Household, Household.household_id == FamilyMember.household_id)
              .join(Member, Member.member_id == FamilyMember.requested_by_member_id)
              .where(FamilyMember.status == "PENDING", *city_filter(Household.city_id, admin)))
    profiles = (row(MatrimonyProfile.profile_id, "PROFILE", Member.full_name, None, MatrimonyProfile.updated_at,
                    Member.city_id)
                .join(Member, Member.member_id == MatrimonyProfile.member_id)
                .where(MatrimonyProfile.status == "PENDING_MODERATION", *city_filter(Member.city_id, admin)))
    # New profiles' photos are reviewed with the profile (PROFILE above); this is photos added to a profile later.
    photos = (row(MatrimonyProfile.profile_id, "PHOTOS", Member.full_name, func.count(),
                  func.max(MatrimonyPhoto.created_at), Member.city_id)
              .join(MatrimonyProfile, MatrimonyProfile.profile_id == MatrimonyPhoto.profile_id)
              .join(Member, Member.member_id == MatrimonyProfile.member_id)
              .where(MatrimonyPhoto.status == "PENDING", MatrimonyProfile.status != "PENDING_MODERATION",
                     *city_filter(Member.city_id, admin))
              .group_by(MatrimonyProfile.profile_id, Member.full_name, Member.city_id))
    news = (row(ContentItem.content_id, "NEWS", Member.full_name, ContentItem.title, ContentItem.created_at,
                ContentItem.city_id)
            .join(Member, Member.member_id == ContentItem.created_by_member_id)
            .where(ContentItem.status == "PENDING", *city_filter(ContentItem.city_id, admin)))
    return union_all(registrations, family, profiles, photos, news).subquery()


@router.get("", response_model=RequestPage)
def list_requests(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                  admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    if admin.role != "SUPER_ADMIN" and admin.city_id is None:  # Super Admin in the City panel, no city picked yet
        return {"total": 0, "unread": 0, "items": []}
    u = _queues(admin)
    seen = _seen_at(db, admin)
    is_new = u.c.at > seen if seen else true()
    total, unread = db.execute(select(func.count(), func.count().filter(is_new)).select_from(u)).one()
    rows = db.execute(select(u, City.name.label("city_name"), is_new.label("unread"))
                      .outerjoin(City, City.city_id == u.c.city_id)
                      .order_by(u.c.at.desc(), u.c.id).limit(limit).offset(offset)).mappings()
    return {"total": total, "unread": unread, "items": list(rows)}


@router.post("/read", status_code=204)
def mark_read(admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Marks everything read; the panel calls it when the Notifications page opens."""
    db.execute(update(AdminUser).where(AdminUser.admin_id == admin.admin_id).values(requests_seen_at=func.now()))
    db.commit()
