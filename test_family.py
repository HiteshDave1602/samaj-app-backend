"""End-to-end member family additions (SF-03) against the dev DB: python test_family.py
Member requests -> City Admin queue -> approve / reject -> member's household view. Cleans up after itself;
audit_log rows stay (append-only)."""
import secrets
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from auth.curd import hash_token
from auth.model import AuthSession
from core.database import SessionLocal
from core.security import fernet, hash_password
from main import app
from member.auth.curd import _start_session, mobile_hash
from member.profile.model import FamilyMember, Household, Member
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser

c = TestClient(app)
tag = secrets.token_hex(4)
now = datetime.now(timezone.utc)


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def new_member(db, city: City, name: str, status: str) -> tuple[Member, dict]:
    mobile = f"+919{secrets.randbelow(10**9):09d}"
    h = Household(household_id=uuid4(), city_id=city.city_id, family_name=f"{name} family")
    m = Member(member_id=uuid4(), city_id=city.city_id, household_id=h.household_id, is_household_head=True,
               mobile_hash=mobile_hash(mobile), mobile_enc=fernet.encrypt(mobile.encode()), mobile_last4=mobile[-4:],
               full_name=name, gender="FEMALE", dob=date(1980, 5, 1), status=status)
    db.add(h)
    db.flush()
    db.add(m)
    db.flush()
    return m, bearer(_start_session(db, m)["access_token"])


with SessionLocal() as db:
    city = City(name=f"FamCity-{tag}", state="T")
    db.add(city)
    db.flush()
    ca = AdminUser(role="CITY_ADMIN", city_id=city.city_id, full_name="CA", email=f"fam-{tag}@t.local",
                   password_hash=hash_password(secrets.token_hex(8)))
    db.add(ca)
    db.flush()
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(admin_id=ca.admin_id, refresh_token_hash=hash_token(token), mfa_verified=True,
                       last_activity_at=now, expires_at=now + timedelta(hours=1)))
    head, head_h = new_member(db, city, "Meera", "ACTIVE")
    _, pending_h = new_member(db, city, "Nina", "PENDING")
    db.commit()
    ca_h, city_id, admin_id, head_id = bearer(token), city.city_id, ca.admin_id, str(head.member_id)

try:
    son = {"full_name": "Rohan", "relationship": "SON", "gender": "MALE", "dob": "2010-03-04"}
    add = lambda h=head_h, **over: c.post("/member/family", headers=h, json=son | over)  # noqa: E731

    # FR-17: Active members only; all four fields required and validated
    assert add(pending_h).status_code == 403
    assert c.post("/member/family").status_code == 401
    for bad in ({"relationship": "COUSIN_TWICE_REMOVED"}, {"gender": "X"}, {"dob": "2999-01-01"}, {"full_name": " "}):
        assert add(**bad).status_code == 422, bad
    r = add()
    assert r.status_code == 201 and r.json()["status"] == "PENDING" and r.json()["requested_by_member_id"] == head_id
    rohan = r.json()["family_member_id"]
    assert add(full_name="rohan").status_code == 409  # same person, case-insensitive
    priya = add(full_name="Priya", relationship="DAUGHTER", gender="FEMALE").json()["family_member_id"]

    # it is in the City Admin's queue
    queue = c.get("/cityadmin/family-additions", headers=ca_h).json()["items"]
    assert [i["full_name"] for i in queue] == ["Rohan", "Priya"], queue

    # FR-18: approved shows as APPROVED in the household; rejected shows the reason
    assert c.post(f"/cityadmin/family-additions/{rohan}/approve", headers=ca_h).status_code == 200
    assert c.post(f"/cityadmin/family-additions/{priya}/reject", headers=ca_h,
                  json={"reason": "Already registered as a member"}).status_code == 200
    hh = c.get("/member/family", headers=head_h).json()
    assert hh["family_name"] == "Meera family", hh
    assert hh["members"] == [{"member_id": head_id, "full_name": "Meera", "is_household_head": True}], hh
    rel = {r["full_name"]: (r["status"], r["rejection_reason"], r["relationship"]) for r in hh["relatives"]}
    assert rel == {"Rohan": ("APPROVED", None, "SON"),
                   "Priya": ("REJECTED", "Already registered as a member", "DAUGHTER")}, rel

    # a rejected relative can be requested again; an approved one can't
    assert add(full_name="Priya", relationship="DAUGHTER", gender="FEMALE").status_code == 201
    assert add().status_code == 409

    # a pending member can still see their own (empty) household
    hh = c.get("/member/family", headers=pending_h).json()
    assert hh["relatives"] == [] and hh["members"][0]["full_name"] == "Nina", hh
    print("ok")
finally:
    with SessionLocal() as db:  # auth_session rows go via ON DELETE CASCADE
        households = select(Household.household_id).where(Household.city_id == city_id)
        db.execute(delete(FamilyMember).where(FamilyMember.household_id.in_(households)))
        db.execute(delete(Member).where(Member.city_id == city_id))
        db.execute(delete(Household).where(Household.city_id == city_id))
        db.execute(delete(AdminUser).where(AdminUser.admin_id == admin_id))
        db.execute(delete(City).where(City.city_id == city_id))
        db.commit()
