"""End-to-end member directory (SF-10) against the dev DB: python test_directory.py
Search by name / city / family, household view, hide phone/address. Cleans up after itself."""
import secrets
from datetime import date, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from core.security import fernet
from main import app
from core.database import SessionLocal
from member.auth.curd import _start_session, mobile_hash
from member.profile.model import FamilyMember, Household, Member
from search.sync import drain
from superadmin.city.model import City

c = TestClient(app)
tag = secrets.token_hex(4)


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def new_member(db, city: City, household: Household, name: str, status: str, head=False, **kw) -> tuple[Member, dict]:
    mobile = f"+919{secrets.randbelow(10**9):09d}"
    m = Member(member_id=uuid4(), city_id=city.city_id, household_id=household.household_id, is_household_head=head,
               mobile_hash=mobile_hash(mobile), mobile_enc=fernet.encrypt(mobile.encode()), mobile_last4=mobile[-4:],
               full_name=name, gender="MALE", dob=date(1980, 5, 1), status=status,
               address_enc=fernet.encrypt(f"{name} street".encode()), **kw)
    db.add(m)
    db.flush()
    return m, bearer(_start_session(db, m)["access_token"])


def born(days_away: int) -> date:  # a 2000 date of birth whose birthday is days_away from today
    d = date.today() + timedelta(days=days_away)
    return date(2000, d.month, d.day)


with SessionLocal() as db:
    x, y = City(name=f"DirX-{tag}", state="T"), City(name=f"DirY-{tag}", state="T")
    db.add_all([x, y])
    db.flush()
    fam = f"Zq{tag}"  # unique family name so other test data never matches
    hx = Household(household_id=uuid4(), city_id=x.city_id, family_name=f"{fam} Patel")
    hy = Household(household_id=uuid4(), city_id=y.city_id, family_name=f"{fam} Shah")
    gone = Household(household_id=uuid4(), city_id=x.city_id, family_name=f"{fam} Archived")
    hb = Household(household_id=uuid4(), city_id=x.city_id, family_name=f"Bd{tag}", family_key=f"bd{tag}")  # import
    db.add_all([hx, hy, gone, hb])
    db.flush()
    raj, raj_h = new_member(db, x, hx, f"{fam} Raj", "ACTIVE", head=True, hide_phone=True)
    new_member(db, x, hx, f"{fam} Pending", "PENDING")
    amit, _ = new_member(db, y, hy, f"{fam} Amit", "ACTIVE", head=True)
    _, pend_h = new_member(db, y, hy, f"{fam} Neel", "PENDING")
    new_member(db, x, gone, f"{fam} Old", "ARCHIVED", head=True)
    db.add_all([
        FamilyMember(household_id=hx.household_id, requested_by_member_id=raj.member_id, full_name=f"{fam} Son",
                     relationship="SON", gender="MALE", status="APPROVED"),
        FamilyMember(household_id=hx.household_id, requested_by_member_id=raj.member_id, full_name=f"{fam} Wait",
                     relationship="DAUGHTER", gender="FEMALE", status="PENDING"),
        FamilyMember(household_id=hx.household_id, requested_by_member_id=raj.member_id, full_name=f"{fam} Linked",
                     relationship="BROTHER", status="APPROVED", linked_member_id=amit.member_id),
        FamilyMember(household_id=gone.household_id, requested_by_member_id=raj.member_id, full_name=f"{fam} Ghost",
                     relationship="SON", status="APPROVED", dob=born(0)),
        # birthdays: today, in 3 days, in 20 days (outside the default week)
        *(FamilyMember(household_id=hb.household_id, requested_by_member_id=raj.member_id, full_name=f"B{n}",
                       relationship="SON", status="APPROVED", dob=born(n)) for n in (3, 0, 20)),
    ])
    db.commit()
    city_ids = [x.city_id, y.city_id]
    amit_h = bearer(_start_session(db, amit)["access_token"])
    db.commit()
    ids = {"raj": str(raj.member_id), "amit": str(amit.member_id), "hx": str(hx.household_id),
           "gone": str(gone.household_id)}
drain()  # search engine on: index the rows above now rather than on the worker's next pass

try:
    get = lambda h=amit_h, **p: c.get("/member/directory", headers=h, params=p)  # noqa: E731
    names_of = lambda j: [i["full_name"].removeprefix(f"{fam} ") for i in j["items"]]  # noqa: E731
    names = lambda r: names_of(r.json())  # noqa: E731

    # FR-08: active members only
    assert get(pend_h, name=fam).status_code == 403
    assert c.get("/member/directory").status_code == 401

    # FR-65: active members + approved, unlinked relatives of live households; sorted by name.
    # Families, not people: a matched relative shows as the head of the family (Son -> Raj), once
    r = get(name=fam)
    assert r.status_code == 200 and names(r) == ["Amit", "Raj"], r.json()
    assert names(get(name=fam.lower() + " r")) == ["Raj"]  # case-insensitive, matches anywhere
    assert names(get(name=f"{fam} Son")) == ["Raj"]
    assert names(get(name=fam, city_id=str(city_ids[0]))) == ["Raj"]
    assert names(get(family_name=f"{fam} sha")) == ["Amit"]
    assert get(name="%_%" + tag).json()["suggested"]  # wildcards are literal: no exact match, closest shown
    # misspelt: closest names instead of nothing
    r = get(name=f"{fam[:-1]} Rja").json()
    assert r["suggested"] and names_of(r)[0] == "Raj" and r["next_offset"] is None, r
    assert not get(name=fam).json()["suggested"]
    assert get(name="a").status_code == 422

    # paging
    p1 = get(name=fam, limit=2).json()
    assert len(p1["items"]) == 2 and p1["next_offset"] == 2
    p2 = get(name=fam, limit=2, offset=2).json()  # Son is on page 2, shown as Raj again (per-page dedupe)
    assert [i["full_name"] for i in p2["items"]] == [f"{fam} Raj"] and p2["next_offset"] is None

    # FR-66 / FR-68: directory fields only; Raj hid his phone from others but sees it himself
    items = {i["full_name"]: i for i in get(name=fam).json()["items"]}
    rj = items[f"{fam} Raj"]
    assert rj["phone"] is None and rj["phone_hidden"] and rj["address"] == f"{fam} Raj street", rj
    assert items[f"{fam} Amit"]["phone"].startswith("+919") and not items[f"{fam} Amit"]["phone_hidden"]
    son = next(p for p in c.get(f"/member/directory/households/{ids['hx']}", headers=amit_h).json()["people"]
               if p["full_name"] == f"{fam} Son")
    assert son["kind"] == "RELATIVE" and son["relationship"] == "SON" and son["phone"] is None, son
    assert son["photo_url"] is None and "photo_url" in rj, (son, rj)
    assert not {"dob", "mobile_enc", "about", "biodata"} & set(rj), rj
    own = {i["full_name"]: i for i in get(raj_h, name=fam).json()["items"]}[f"{fam} Raj"]
    assert own["phone"] and not own["phone_hidden"], own

    # FR-67: household view
    hv = c.get(f"/member/directory/households/{ids['hx']}", headers=amit_h)
    assert hv.status_code == 200, hv.text
    hv = hv.json()
    assert hv["family_name"] == f"{fam} Patel" and hv["city_name"] == f"DirX-{tag}", hv
    assert [(p["full_name"].removeprefix(f"{fam} "), p["kind"]) for p in hv["people"]] == \
        [("Raj", "MEMBER"), ("Son", "RELATIVE")], hv
    assert c.get(f"/member/directory/households/{ids['gone']}", headers=amit_h).status_code == 404
    assert c.get(f"/member/directory/households/{uuid4()}", headers=amit_h).status_code == 404

    # birthdays: all cities by default (city_id here keeps other dev data out), soonest first,
    # archived household left out, no year of birth
    bd = lambda h=amit_h, **p: [(i["full_name"], i["days_away"])  # noqa: E731  (relatives: Raj's own dob is fixed)
                                for i in c.get("/member/directory/birthdays", headers=h,
                                               params={"city_id": str(city_ids[0]), **p}).json()
                                if i["kind"] == "RELATIVE"]
    assert bd() == [("B0", 0), ("B3", 3)], bd()  # Amit lives in city Y and still sees city X
    assert bd(days=31) == [("B0", 0), ("B3", 3), ("B20", 20)]
    assert bd(city_id=str(city_ids[1])) == []
    assert c.get("/member/directory/birthdays", headers=raj_h, params={"days": 0}).status_code == 200
    one = c.get("/member/directory/birthdays", headers=raj_h, params={"city_id": str(city_ids[0])}).json()[0]
    assert "dob" not in one and one["birthday"] >= date.today().isoformat(), one
    assert c.get("/member/directory/birthdays", headers=pend_h).status_code == 403
    print("ok")
finally:
    with SessionLocal() as db:  # auth_session rows go via ON DELETE CASCADE
        households = select(Household.household_id).where(Household.city_id.in_(city_ids))
        db.execute(delete(FamilyMember).where(FamilyMember.household_id.in_(households)))
        db.execute(delete(Member).where(Member.city_id.in_(city_ids)))
        db.execute(delete(Household).where(Household.city_id.in_(city_ids)))
        db.execute(delete(City).where(City.city_id.in_(city_ids)))
        db.commit()
