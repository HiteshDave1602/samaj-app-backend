from calendar import isleap
from datetime import date, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import exists, false, func, literal, null, or_, select, union_all
from sqlalchemy.orm import Session

from core import media
from core.security import fernet
from member.profile.model import FamilyMember, Household, Member
from search import es
from superadmin.city.model import City

_listed = (Member.status == "ACTIVE", Member.deleted_at.is_(None))  # pending, rejected, archived never appear
EXTRA = ("gotra", "education", "marital_status", "occupation", "hobby", "blood_group")  # profile details


def _live(household_id):
    # A household shows only while it has an active member, so an archived family's relatives drop out too.
    # A directory-import household (family_key set) has no app members and always shows.
    return or_(exists().where(Member.household_id == household_id, *_listed), Household.family_key.is_not(None))


def _members(name: str | None, city_id: UUID | None, family_name: str | None):
    # column order must match _relatives: the two are UNIONed
    q = (select(literal("MEMBER").label("kind"), Member.member_id.label("id"), Member.full_name, Member.full_name_i18n,
                Member.gender, null().label("relationship"), Member.is_household_head, Member.household_id,
                Household.family_name, Household.family_name_i18n, Household.native_place, Household.native_place_i18n,
                City.name.label("city_name"), City.name_i18n.label("city_name_i18n"), Member.mobile_enc,
                Member.address_enc,
                Member.hide_phone, Member.hide_address, Member.photo_key, Member.city_id,
                *(getattr(Member, c) for c in EXTRA))
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
                (FamilyMember.relationship == "SELF").label("is_household_head"), Household.household_id,
                Household.family_name, Household.family_name_i18n, Household.native_place, Household.native_place_i18n,
                City.name.label("city_name"), City.name_i18n.label("city_name_i18n"), FamilyMember.mobile_enc,
                FamilyMember.address_enc,
                false().label("hide_phone"), false().label("hide_address"), null().label("photo_key"), Household.city_id,
                *(getattr(FamilyMember, c) for c in EXTRA))
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
        "photo_url": media.url(row.photo_key),
    } | {c: getattr(row, c) for c in EXTRA}


def search(db: Session, viewer: Member, *, name: str | None, city_id: UUID | None, family_name: str | None,
           offset: int, limit: int) -> dict:
    """FR-65: any combination of name, city and family name; members and approved relatives together.
    ponytail: offset paging, fine at 50k members; switch to a (full_name, id) cursor if deep pages get slow."""
    u = union_all(_members(name, city_id, family_name), _relatives(name, city_id, family_name)).subquery()
    rows = db.execute(select(u).order_by(u.c.full_name, u.c.id).offset(offset).limit(limit + 1)).all()
    if not rows and offset == 0 and (name or family_name):
        return _closest(db, viewer, name=name, city_id=city_id, family_name=family_name, limit=limit)
    return {"items": [_entry(r, viewer) for r in rows[:limit]],
            "next_offset": offset + limit if len(rows) > limit else None}


def to_heads(db: Session, viewer: Member, page: dict) -> dict:
    """The directory lists families: whoever matched shows as their household's head, once per family.
    ponytail: deduped per page, so a family can repeat across pages; group in the query if deep paging matters."""
    hids = {i["household_id"] for i in page["items"] if i["household_id"] and not i["is_household_head"]}
    heads = {}
    if hids:
        u = union_all(_members(None, None, None).where(Member.household_id.in_(hids), Member.is_household_head),
                      _relatives(None, None, None).where(FamilyMember.household_id.in_(hids),
                                                         FamilyMember.relationship == "SELF")).subquery()
        for r in db.execute(select(u)):
            heads.setdefault(r.household_id, _entry(r, viewer))
    seen, items = set(), []
    for i in page["items"]:
        i = heads.get(i["household_id"], i)  # no head listed: keep the person who matched
        if (k := i["household_id"] or i["id"]) not in seen:
            seen.add(k)
            items.append(i)
    return page | {"items": items}


def _closest(db: Session, viewer: Member, *, name, city_id, family_name, limit: int) -> dict:
    """Nothing contained the text (a misspelling): the most similar names instead, one page, best first.
    ponytail: scores every listed person in the city; fine as the fallback at 50k, ES answers this normally."""
    u = union_all(_members(None, city_id, None), _relatives(None, city_id, None)).subquery()
    scores = [func.coalesce(func.word_similarity(t, col), 0) for t, col in
              ((name, u.c.full_name), (family_name, u.c.family_name)) if t]
    rows = db.execute(select(u).where(*(s > es.CLOSEST_SIMILARITY for s in scores))  # each term close, like AND
                      .order_by(sum(scores).desc(), u.c.id).limit(limit)).all()
    return {"items": [_entry(r, viewer) for r in rows], "next_offset": None, "suggested": True}


def birthdays(db: Session, viewer: Member, days: int, limit: int, city_id: UUID | None = None) -> list[dict]:
    """Listed people (all cities, or one) whose birthday falls today or in the next `days` days, soonest first.
    Only the upcoming date goes out, never the year of birth (FR-66). A 29 Feb birthday shows on 1 Mar off leap years."""
    today = date.today()
    on = {}  # "MM-DD" -> the upcoming date it falls on
    for i in range(days + 1):
        d = today + timedelta(days=i)
        on[d.strftime("%m-%d")] = d
        if (d.month, d.day) == (3, 1) and not isleap(d.year):
            on["02-29"] = d
    u = union_all(_members(None, city_id, None).add_columns(Member.dob),
                  _relatives(None, city_id, None).add_columns(FamilyMember.dob)).subquery()
    mmdd = func.to_char(u.c.dob, "MM-DD")
    # ponytail: sorts every match in Python (~1k/week at 50k people); order in SQL if the window or data grows
    rows = db.execute(select(u, mmdd.label("mmdd")).where(mmdd.in_(on))).all()
    rows.sort(key=lambda r: (on[r.mmdd], r.full_name or ""))
    return [_entry(r, viewer) | {"birthday": on[r.mmdd], "days_away": (on[r.mmdd] - today).days}
            for r in rows[:limit]]


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
                           .order_by((FamilyMember.relationship == "SELF").desc(), FamilyMember.created_at)).all()
    return {"household_id": h.household_id, "family_name": h.family_name, "family_name_i18n": h.family_name_i18n,
            "native_place": h.native_place, "native_place_i18n": h.native_place_i18n,
            "city_name": city.name, "city_name_i18n": city.name_i18n,
            "people": [_entry(r, viewer) for r in [*members, *relatives]]}
