from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from member.auth.deps import get_current_member
from member.matrimony.schema import ProfileCard
from member.notification import curd
from member.profile.model import Member

# The bell: admin decisions on the member's requests, biodata requests / answers, and live news.
# Flow: GET (badge = unread) -> open the screen -> POST /read.
router = APIRouter(prefix="/member/notifications", tags=["Member Notifications"])


class NotificationOut(BaseModel):
    notification_id: UUID
    kind: str  # notification.model KINDS, plus NEWS_LIVE (live news, not stored: see curd._news)
    payload: dict  # approved/accepted, reason, name/title, profile_id/content_id: see the curd calls per kind
    created_at: datetime
    unread: bool
    counterpart: ProfileCard | None  # biodata kinds: the other member, while listed


class NotificationPage(BaseModel):
    total: int
    unread: int
    items: list[NotificationOut]


@router.get("", response_model=NotificationPage)
def list_notifications(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                       member: Member = Depends(get_current_member), db: Session = Depends(get_db)):
    return curd.list_for(db, member, limit, offset)


@router.post("/read", status_code=204)
def mark_read(member: Member = Depends(get_current_member), db: Session = Depends(get_db)):
    """Marks everything read; the app calls it when the screen opens."""
    curd.mark_read(db, member)
