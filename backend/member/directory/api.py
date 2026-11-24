from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.validation import Search
from member.auth.deps import get_active_member, get_searching_member
from member.directory import curd, search as es_search
from member.directory.schema import BirthdayEntry, DirectoryPage, HouseholdView
from member.profile.model import Member

# SF-10. Active members only (FR-08). Hide your phone/address with PUT /member/me (FR-68).
router = APIRouter(prefix="/member/directory", tags=["Member Directory"])


@router.get("", response_model=DirectoryPage)
def search(
    name: Search(120, 2) | None = None,
    city_id: UUID | None = None,
    family_name: Search(120, 2) | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    member: Member = Depends(get_searching_member),
    db: Session = Depends(get_db),
):
    """FR-65: filters combine; name and family name match anywhere, case-insensitive. Sorted by name.
    With the search engine on, they also match small typos and Gujarati/Hindi spellings. 429 past the search rate."""
    return curd.to_heads(db, member, es_search.search(db, member, name=name, city_id=city_id,
                                                      family_name=family_name, offset=offset, limit=limit))


@router.get("/birthdays", response_model=list[BirthdayEntry])
def birthdays(days: int = Query(7, ge=0, le=31), limit: int = Query(30, ge=1, le=200), city_id: UUID | None = None,
              member: Member = Depends(get_active_member), db: Session = Depends(get_db)):
    """Home screen reminders: birthdays across all cities (or `city_id`) from today through the next `days` days,
    soonest first."""
    return curd.birthdays(db, member, days, limit, city_id)


@router.get("/households/{household_id}", response_model=HouseholdView)
def household(household_id: UUID, member: Member = Depends(get_active_member), db: Session = Depends(get_db)):
    return curd.household(db, member, household_id)
