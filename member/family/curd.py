from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from member.family.schema import FamilyRequestIn
from member.profile.model import FamilyMember, Household, Member


def _household(db: Session, member: Member) -> Household:
    household = db.get(Household, member.household_id) if member.household_id else None
    if household is None:
        raise HTTPException(404, "You are not part of a household yet. Contact your City Admin.")
    return household


def _relative(fm: FamilyMember) -> dict:
    return {c.name: getattr(fm, c.name) for c in FamilyMember.__table__.columns}


def get_household(db: Session, member: Member) -> dict:
    household = _household(db, member)
    members = db.scalars(select(Member).where(Member.household_id == household.household_id,
                                              Member.deleted_at.is_(None))
                         .order_by(Member.is_household_head.desc(), Member.full_name))
    relatives = db.scalars(select(FamilyMember).where(FamilyMember.household_id == household.household_id)
                           .order_by(FamilyMember.created_at))
    return {
        "household_id": household.household_id,
        "family_name": household.family_name,
        "native_place": household.native_place,
        "members": [{"member_id": m.member_id, "full_name": m.full_name, "is_household_head": m.is_household_head}
                    for m in members],
        "relatives": [_relative(fm) for fm in relatives],
    }


def request_addition(db: Session, member: Member, data: FamilyRequestIn) -> dict:
    """FR-17: lands in the City Admin's Family Additions queue as PENDING."""
    household = _household(db, member)
    # ponytail: name + DOB match only; two parallel identical requests can both pass. A rejected one can be resent.
    if db.scalar(select(FamilyMember.family_member_id).where(
            FamilyMember.household_id == household.household_id, FamilyMember.status != "REJECTED",
            func.lower(FamilyMember.full_name) == data.full_name.lower(), FamilyMember.dob == data.dob)):
        raise HTTPException(409, f"{data.full_name} is already added or waiting for approval")
    fm = FamilyMember(household_id=household.household_id, requested_by_member_id=member.member_id,
                      **data.model_dump())
    db.add(fm)
    db.commit()
    return _relative(fm)
