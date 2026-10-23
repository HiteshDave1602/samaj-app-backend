from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from member.auth.deps import get_active_member, get_current_member
from member.family import curd
from member.family.schema import FamilyRequestIn, HouseholdOut, RelativeOut
from member.profile.model import Member

# Flow (SF-03): POST /member/family -> City Admin approves in /cityadmin/family-additions -> APPROVED in GET.
router = APIRouter(prefix="/member/family", tags=["Member Family"])


@router.get("", response_model=HouseholdOut)
def get_household(member: Member = Depends(get_current_member), db: Session = Depends(get_db)):
    """The member's household: registered members plus relatives with their request status."""
    return curd.get_household(db, member)


@router.post("", response_model=RelativeOut, status_code=201)
def request_addition(data: FamilyRequestIn, member: Member = Depends(get_active_member),
                     db: Session = Depends(get_db)):
    """Active members only (FR-17). Relationship is to the household head."""
    return curd.request_addition(db, member, data)
