from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.database import get_db
from member.auth.deps import get_active_member
from member.directory import curd
from member.directory.schema import DirectoryPage, HouseholdView
from member.profile.model import Member

# SF-10. Active members only (FR-08). Hide your phone/address with PUT /member/me (FR-68).
router = APIRouter(prefix="/member/directory", tags=["Member Directory"])


@router.get("", response_model=DirectoryPage)
def search(
    name: str | None = Query(None, min_length=2, max_length=120),
    city_id: UUID | None = None,
    family_name: str | None = Query(None, min_length=2, max_length=120),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    member: Member = Depends(get_active_member),
    db: Session = Depends(get_db),
):
    """FR-65: filters combine; name and family name match anywhere, case-insensitive. Sorted by name."""
    return curd.search(db, member, name=name, city_id=city_id, family_name=family_name, offset=offset, limit=limit)


@router.get("/households/{household_id}", response_model=HouseholdView)
def household(household_id: UUID, member: Member = Depends(get_active_member), db: Session = Depends(get_db)):
    return curd.household(db, member, household_id)
