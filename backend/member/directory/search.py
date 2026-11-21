"""Directory search on Elasticsearch (SF-10, FR-65). Same request and response as the Postgres search in curd.py,
which stays as the fallback and as the one definition of who is listed: documents are built from its queries, and
every page is read back through them, so a member archived a second ago never shows.
Matching adds what ILIKE can't: typo tolerance and names typed in Gujarati or Hindi script."""
from collections import defaultdict
from uuid import UUID

from sqlalchemy import literal, select, tuple_, union_all
from sqlalchemy.orm import Session

from member.directory import curd
from member.profile.model import FamilyMember, Member
from search import es

NAME, VERSION = "directory", 1  # bump VERSION with any mapping change, then python -m search.reindex --rebuild
PROPERTIES = {
    "kind": es.KEYWORD, "id": es.KEYWORD, "city_id": es.KEYWORD, "household_id": es.KEYWORD, "gender": es.KEYWORD,
    "full_name": es.name_field(sort=True), "full_name_i18n": es.I18N,
    "family_name": es.name_field(), "family_name_i18n": es.I18N,
}  # no phone, address, photo or DOB: read from Postgres per page


def search(db: Session, viewer: Member, *, name: str | None, city_id: UUID | None, family_name: str | None,
           offset: int, limit: int) -> dict:
    def pg():
        return curd.search(db, viewer, name=name, city_id=city_id, family_name=family_name, offset=offset, limit=limit)

    if offset + limit + 1 > es.MAX_WINDOW:  # deep page: past ES's window, Postgres pages any offset
        return pg()

    def from_es():
        must = [es.name_query(name, "full_name")] if name else []
        if family_name:
            must.append(es.name_query(family_name, "family_name"))
        city = [{"term": {"city_id": str(city_id)}}] if city_id else []
        db.close()  # hand the pooled connection back while ES works; the hydration below takes one again
        hits = es.search(
            NAME, query={"bool": {"filter": city, "must": must}},
            sort=[{"full_name.sort": {"order": "asc", "missing": "_last"}}, {"id": "asc"}],
            from_=offset, size=limit + 1)
        suggested = not hits and offset == 0 and bool(must)
        if suggested:  # misspelt: show the closest names instead of nothing, one page, best first
            close = [es.closest_query(t, [f, f"{f}_i18n.gu", f"{f}_i18n.hi"])
                     for t, f in ((name, "full_name"), (family_name, "family_name")) if t]
            hits = es.search(NAME, query={"bool": {"filter": city, "must": close}}, size=limit)
        page = [h["_id"] for h in hits]
        rows = {key(r): r for r in _rows(db, page[:limit])}
        return {"items": [curd._entry(rows[k], viewer) for k in page[:limit] if k in rows],
                "next_offset": offset + limit if len(page) > limit and not suggested else None,
                "suggested": suggested}

    return es.answer(from_es, pg)


def key(row) -> str:
    return f"{row.kind}:{row.id}"


def _rows(db: Session, keys: list[str]):
    """Listed rows for these document ids (MEMBER:<id> / RELATIVE:<id>); unlisted ones are simply absent."""
    ids = defaultdict(list)
    for k in keys:
        kind, _, i = k.partition(":")
        ids[kind].append(UUID(i))
    return db.execute(union_all(curd._members(None, None, None).where(Member.member_id.in_(ids["MEMBER"])),
                                curd._relatives(None, None, None)
                                .where(FamilyMember.family_member_id.in_(ids["RELATIVE"])))).all()


def _doc(row) -> dict:
    return {"kind": row.kind, "id": str(row.id), "city_id": str(row.city_id),
            "household_id": row.household_id and str(row.household_id), "gender": row.gender,
            "full_name": row.full_name, "full_name_i18n": es.i18n(row.full_name_i18n),
            "family_name": row.family_name, "family_name_i18n": es.i18n(row.family_name_i18n)}


# ---- indexing (search/sync.py) -------------------------------------------------------------------------------------

def targets(db: Session, events) -> dict[str, set[int]]:
    """Document ids the events touch -> the event ids touching them. A household event covers everyone in it."""
    out, households = defaultdict(set), defaultdict(set)
    for eid, entity, xid in events:
        if entity == "member":
            out[f"MEMBER:{xid}"].add(eid)
        elif entity == "relative":
            out[f"RELATIVE:{xid}"].add(eid)
        elif entity == "household":
            households[xid].add(eid)
    if households:
        for kind, pk, model in (("MEMBER", Member.member_id, Member),
                                ("RELATIVE", FamilyMember.family_member_id, FamilyMember)):
            for i, h in db.execute(select(pk, model.household_id).where(model.household_id.in_(households))):
                out[f"{kind}:{i}"] |= households[h]
    return out


def docs(db: Session, keys: list[str]) -> dict[str, dict]:
    """Current documents for the listed ones among keys; the others are to be deleted."""
    return {key(r): _doc(r) for r in _rows(db, keys)}


def batch(db: Session, after: str | None, size: int) -> list[tuple[str, dict]]:
    """The next `size` listed people after document id `after`, in id order (keyset: resumable, no OFFSET)."""
    u = union_all(curd._members(None, None, None), curd._relatives(None, None, None)).subquery()
    q = select(u).order_by(u.c.kind, u.c.id).limit(size)
    if after:
        kind, _, i = after.partition(":")
        q = q.where(tuple_(u.c.kind, u.c.id) > tuple_(literal(kind), literal(UUID(i))))
    return [(key(r), _doc(r)) for r in db.execute(q)]
