from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import exists, false, literal, null, select, union_all
from sqlalchemy.orm import Session

from core.security import fernet
from member.profile.model import FamilyMember, Household, Member
from superadmin.city.model import City

_listed = (Member.status == "ACTIVE", Member.deleted_at.is_(None))  # pending, rejected, archived never appear


def _live(household_id) -> exists:
    # A household shows only while it has an active member, so an archived family's relatives drop out too.
    return exists().where(Member.household_id == household_id, *_listed)


def _members(name: str | None, city_id: UUID | None, family_name: str | None):
    # column order must match _relatives: the two are UNIONed
    q = (select(literal("MEMBER").label("kind"), Member.member_id.label("id"), Member.full_name, Member.full_name_i18n,
                Member.gender, null().label("relationship"), Member.is_household_head, Member.household_id,
                Household.family_name, Household.family_name_i18n, Household.native_place, Household.native_place_i18n,
                City.name.label("city_name"), City.name_i18n.label("city_name_i18n"), Member.mobile_enc,
                Member.address_enc,
                Member.hide_phone, Member.hide_address)
         .join(City, City.city_id == Member.city_id)
         .outerjoin(Household, Household.household_id == Member.household_id)
         .where(*_listed))
    if name:
        q = q.where(Member.full_name.icontains(name, autoescape=True))
    if city_id:
        q = q.where(Member.city_id == city_id)
    if family_name:
        q = q.where(Household.family_name.icontains(family_name, autoescape=True))
    return q


def _relatives(name: str | None, city_id: UUID | None, family_name: str | None):
    # FR-18: approved only. A relative linked to a registered member is listed as that member instead.
    q = (select(literal("RELATIVE").label("kind"), FamilyMember.family_member_id.label("id"), FamilyMember.full_name,
                FamilyMember.full_name_i18n, FamilyMember.gender, FamilyMember.relationship,
                false().label("is_household_head"), Household.household_id,
                Household.family_name, Household.family_name_i18n, Household.native_place, Household.native_place_i18n,
                City.name.label("city_name"), City.name_i18n.label("city_name_i18n"), null().label("mobile_enc"),
                null().label("address_enc"),
                false().label("hide_phone"), false().label("hide_address"))
         .join(Household, Household.household_id == FamilyMember.household_id)
         .join(City, City.city_id == Household.city_id)
         .where(FamilyMember.status == "APPROVED", FamilyMember.linked_member_id.is_(None),
                _live(Household.household_id)))
    if name:
        q = q.where(FamilyMember.full_name.icontains(name, autoescape=True))
    if city_id:
        q = q.where(Household.city_id == city_id)
    if family_name:
        q = q.where(Household.family_name.icontains(family_name, autoescape=True))
    return q


def _entry(row, viewer: Member) -> dict:
    own = row.id == viewer.member_id  # your own hidden fields still show to you
    show_phone = row.mobile_enc is not None and (own or not row.hide_phone)
    show_address = row.address_enc is not None and (own or not row.hide_address)
    return {
        "kind": row.kind, "id": row.id, "full_name": row.full_name, "full_name_i18n": row.full_name_i18n,
        "gender": row.gender, "relationship": row.relationship, "is_household_head": row.is_household_head,
        # no household (outer join): the *_i18n come back NULL
        "household_id": row.household_id, "family_name": row.family_name, "family_name_i18n": row.family_name_i18n or {},
        "native_place": row.native_place, "native_place_i18n": row.native_place_i18n or {},
        "city_name": row.city_name, "city_name_i18n": row.city_name_i18n,
        "phone": fernet.decrypt(row.mobile_enc).decode() if show_phone else None,
        "address": fernet.decrypt(row.address_enc).decode() if show_address else None,
        "phone_hidden": row.hide_phone and not own, "address_hidden": row.hide_address and not own,
    }


def search(db: Session, viewer: Member, *, name: str | None, city_id: UUID | None, family_name: str | None,
           offset: int, limit: int) -> dict:
    """FR-65: any combination of name, city and family name; members and approved relatives together.
    ponytail: offset paging, fine at 50k members; switch to a (full_name, id) cursor if deep pages get slow."""
    u = union_all(_members(name, city_id, family_name), _relatives(name, city_id, family_name)).subquery()
    rows = db.execute(select(u).order_by(u.c.full_name, u.c.id).offset(offset).limit(limit + 1)).all()
    return {"items": [_entry(r, viewer) for r in rows[:limit]],
            "next_offset": offset + limit if len(rows) > limit else None}


def household(db: Session, viewer: Member, household_id: UUID) -> dict:
    """FR-67: the household with its active members and approved relatives."""
    row = db.execute(select(Household, City).join(City, City.city_id == Household.city_id)
                     .where(Household.household_id == household_id, _live(Household.household_id))).one_or_none()
    if row is None:
        raise HTTPException(404, "Household not found")
    h, city = row
    members = db.execute(_members(None, None, None).where(Member.household_id == household_id)
                         .order_by(Member.is_household_head.desc(), Member.full_name)).all()
    relatives = db.execute(_relatives(None, None, None).where(FamilyMember.household_id == household_id)
                           .order_by(FamilyMember.created_at)).all()
    return {"household_id": h.household_id, "family_name": h.family_name, "family_name_i18n": h.family_name_i18n,
            "native_place": h.native_place, "native_place_i18n": h.native_place_i18n,
            "city_name": city.name, "city_name_i18n": city.name_i18n,
            "people": [_entry(r, viewer) for r in [*members, *relatives]]}
