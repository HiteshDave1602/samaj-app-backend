"""Matrimony search on Elasticsearch (SF-05, FR-25). Same filters, order and keyset cursor as curd.search, which stays
as the Postgres fallback and as the one definition of what is searchable (curd.public_query): documents are built from
it and each page is read back through it. Adds an optional free-text `q` over name, occupation, gotra, education and
native place. Profile ids sort the same as text and as uuid, so a cursor works on either backend."""
from collections import defaultdict
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from member.matrimony import curd
from member.matrimony.model import MatrimonyProfile
from member.profile.model import Member
from search import es

NAME, VERSION = "matrimony", 1  # bump VERSION with any mapping change, then python -m search.reindex --rebuild
TEXT_FIELDS = ["full_name", "full_name_i18n.gu", "full_name_i18n.hi", "occupation", "gotra", "education_detail",
               "native_place", "native_place_i18n.gu", "native_place_i18n.hi"]
PROPERTIES = {
    "profile_id": es.KEYWORD, "member_id": es.KEYWORD, "gender": es.KEYWORD, "dob": {"type": "date"},
    "education_level": es.KEYWORD, "family_background": es.KEYWORD, "location_city_id": es.KEYWORD,
    "full_name": es.TEXT, "full_name_i18n": es.I18N, "occupation": es.TEXT, "gotra": es.TEXT,
    "education_detail": es.TEXT, "native_place": es.TEXT, "native_place_i18n": es.I18N,
}  # no biodata, contact or photo fields


def search(db: Session, member: Member, *, q: str | None, age_min: int | None, age_max: int | None,
           gender: str | None, education_level: list[str], city_id: list[UUID], family_background: list[str],
           after: UUID | None, limit: int) -> dict:
    def pg():
        return curd.search(db, member, text=q, age_min=age_min, age_max=age_max, gender=gender,
                           education_level=education_level, city_id=city_id, family_background=family_background,
                           after=after, limit=limit)

    def from_es():
        f = []
        if age_min is not None:
            f.append({"range": {"dob": {"lte": curd._years_ago(age_min).isoformat()}}})
        if age_max is not None:
            f.append({"range": {"dob": {"gt": curd._years_ago(age_max + 1).isoformat()}}})
        for field, value in (("gender", gender), ("education_level", education_level),
                             ("location_city_id", [str(c) for c in city_id]), ("family_background", family_background)):
            if value:
                f.append({"terms": {field: value if isinstance(value, list) else [value]}})
        must = [{"bool": {"minimum_should_match": 1, "should": [  # whole words within typo distance, or word prefixes
            {"multi_match": {"query": q, "fields": TEXT_FIELDS, "operator": "and", "fuzziness": es.FUZZY,
                             "prefix_length": 1}},
            {"multi_match": {"query": q, "fields": TEXT_FIELDS, "operator": "and", "type": "bool_prefix"}}]}}] if q else []
        not_mine = [{"term": {"member_id": str(member.member_id)}}]  # FR-27: never your own
        db.close()  # hand the pooled connection back while ES works; the hydration below takes one again
        hits = es.search(NAME, query={"bool": {"filter": f, "must": must, "must_not": not_mine}},
                         sort=[{"profile_id": "asc"}], size=limit + 1, **({"search_after": [str(after)]} if after else {}))
        suggested = not hits and after is None and bool(q)
        if suggested:  # misspelt: show the closest profiles instead of nothing, one page, best first
            hits = es.search(NAME, query={"bool": {"filter": f, "must": [es.closest_query(q, TEXT_FIELDS)],
                                                   "must_not": not_mine}}, size=limit)
        page = [h["_id"] for h in hits]
        rows = {str(r[0].profile_id): r for r in db.execute(
            curd.public_query().where(MatrimonyProfile.profile_id.in_([UUID(i) for i in page[:limit]]),
                                      MatrimonyProfile.member_id != member.member_id))}
        return {"items": [curd.card(*rows[i]) for i in page[:limit] if i in rows],
                "next_after": page[limit - 1] if len(page) > limit and not suggested else None,
                "suggested": suggested}

    return es.answer(from_es, pg)


def _doc(p: MatrimonyProfile, name: str | None, name_i18n: dict, gender: str | None, dob: date | None,
         native: str | None, native_i18n: dict | None, *_) -> dict:
    return {"profile_id": str(p.profile_id), "member_id": str(p.member_id), "gender": gender,
            "dob": dob and dob.isoformat(), "education_level": p.education_level,
            "family_background": p.family_background, "location_city_id": str(p.location_city_id),
            "full_name": name, "full_name_i18n": es.i18n(name_i18n), "occupation": p.occupation, "gotra": p.gotra,
            "education_detail": p.education_detail, "native_place": native, "native_place_i18n": es.i18n(native_i18n)}


# ---- indexing (search/sync.py) -------------------------------------------------------------------------------------

def targets(db: Session, events) -> dict[str, set[int]]:
    """Profile ids the events touch -> the event ids touching them. Member and household events reach the profiles
    of those members: status, gender, DOB, name and native place all feed search."""
    out, members, households = defaultdict(set), defaultdict(set), defaultdict(set)
    for eid, entity, xid in events:
        if entity == "matrimony":
            out[str(xid)].add(eid)
        elif entity == "member":
            members[xid].add(eid)
        elif entity == "household":
            households[xid].add(eid)
    if members:
        for pid, m in db.execute(select(MatrimonyProfile.profile_id, MatrimonyProfile.member_id)
                                 .where(MatrimonyProfile.member_id.in_(members))):
            out[str(pid)] |= members[m]
    if households:
        for pid, h in db.execute(select(MatrimonyProfile.profile_id, Member.household_id)
                                 .join(Member, Member.member_id == MatrimonyProfile.member_id)
                                 .where(Member.household_id.in_(households))):
            out[str(pid)] |= households[h]
    return out


def docs(db: Session, keys: list[str]) -> dict[str, dict]:
    rows = db.execute(curd.public_query().where(MatrimonyProfile.profile_id.in_([UUID(k) for k in keys])))
    return {str(r[0].profile_id): _doc(*r) for r in rows}


def batch(db: Session, after: str | None, size: int) -> list[tuple[str, dict]]:
    q = curd.public_query().order_by(MatrimonyProfile.profile_id).limit(size)
    if after:
        q = q.where(MatrimonyProfile.profile_id > UUID(after))
    return [(str(r[0].profile_id), _doc(*r)) for r in db.execute(q)]
