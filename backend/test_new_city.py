"""Registering for a city the Super Admin hasn't created yet, against the dev DB: python test_new_city.py
The registration waits with no city; no City Admin sees it; the Super Admin creates the city, then approves."""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from auth.curd import hash_token
from auth.model import AuthSession
from core import sms
from core.database import SessionLocal
from core.security import hash_password
from main import app
from member.auth.curd import NOTICE_VERSION, mobile_hash
from member.profile.model import Consent, Household, Member
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser

c = TestClient(app)
tag = secrets.token_hex(4)
sms.send_sms = lambda mobile, text: None
new_city = f"Newtown{tag}"  # letters only: the city name validator


def admin_session(db, admin: AdminUser) -> dict:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    db.add(AuthSession(admin_id=admin.admin_id, refresh_token_hash=hash_token(token), mfa_verified=True,
                       last_activity_at=now, expires_at=now + timedelta(hours=1)))
    return {"Authorization": f"Bearer {token}"}


mobiles = [f"+919{secrets.randbelow(10**9):09d}" for _ in range(4)]


def member_id(mobile: str) -> str:
    with SessionLocal() as db:
        return str(db.scalar(select(Member.member_id).where(Member.mobile_hash == mobile_hash(mobile))))


def register(mobile: str, **city):
    return c.post("/member/auth/register", json={
        "mobile": mobile, "full_name": "Asha Patel", "gender": "FEMALE",
        "dob": "1998-04-12", "address": "1 Test Lane", "family_name": "Patel", "consent": True,
        "notice_version": NOTICE_VERSION} | city)


with SessionLocal() as db:
    other = City(name=f"Other-{tag}", state="T")
    db.add(other)
    db.flush()
    pw = hash_password(secrets.token_hex(8))
    sa = AdminUser(role="SUPER_ADMIN", full_name="SA", email=f"sa-{tag}@t.local", password_hash=pw)
    ca = AdminUser(role="CITY_ADMIN", city_id=other.city_id, full_name="CA", email=f"ca-{tag}@t.local", password_hash=pw)
    db.add_all([sa, ca])
    db.flush()
    sa_h, ca_h = admin_session(db, sa), admin_session(db, ca)
    db.commit()
    city_ids, admin_ids = [other.city_id], [sa.admin_id, ca.admin_id]

try:
    # city_id or a typed city + state, never both or half
    assert register(mobiles[0]).status_code == 422
    assert register(mobiles[0], requested_city=new_city).status_code == 422
    assert register(mobiles[0], city_id=str(other.city_id), requested_city=new_city, requested_state="G").status_code == 422

    # a typed city that already exists (any case) joins it, as if picked
    r = register(mobiles[0], requested_city=f"OTHER-{tag}", requested_state="t")
    assert r.is_success, r.text
    me = c.get(f"/superadmin/members/{member_id(mobiles[0])}", headers=sa_h).json()
    assert me["city_id"] == str(other.city_id) and me["requested_city"] is None, me

    # an unknown city: PENDING, no city, the typed name shown back
    r = register(mobiles[1], requested_city=new_city, requested_state="Gujarat")
    assert r.is_success and r.json()["member_status"] == "PENDING", r.text
    mid = member_id(mobiles[1])
    me = c.get(f"/superadmin/members/{mid}", headers=sa_h).json()
    assert me["city_id"] is None and me["city_name"] == new_city and me["requested_state"] == "Gujarat", me
    assert register(mobiles[2], requested_city=new_city, requested_state="Gujarat").is_success
    rej_id = member_id(mobiles[2])

    # no City Admin sees it; the Super Admin does, in the no-city queue and the bell (with the typed city)
    assert mid not in [m["member_id"] for m in c.get("/cityadmin/members/pending", headers=ca_h).json()["items"]]
    assert c.get(f"/cityadmin/members/{mid}", headers=ca_h).status_code == 403
    page = c.get("/superadmin/members/pending", headers=sa_h, params={"no_city": True}).json()
    assert {mid, rej_id} <= {m["member_id"] for m in page["items"]} and all(m["city_id"] is None for m in page["items"])
    bell = {i["id"]: i for i in c.get("/admin/requests", headers=sa_h, params={"limit": 200}).json()["items"]}
    assert bell[mid]["kind"] == "REGISTRATION" and bell[mid]["detail"] == new_city, bell[mid]
    assert mid not in {i["id"] for i in c.get("/admin/requests", headers=ca_h).json()["items"]}

    # approve needs an active city; a member of a set-up city stays with its City Admin
    assert c.post(f"/superadmin/members/{mid}/approve", headers=sa_h, json={}).status_code == 422
    other_mid = c.get("/cityadmin/members/pending", headers=ca_h).json()["items"][0]["member_id"]
    assert c.post(f"/superadmin/members/{other_mid}/approve", headers=sa_h,
                  json={"city_id": str(other.city_id)}).status_code == 409
    assert c.post(f"/superadmin/members/{mid}/approve", headers=ca_h, json={"city_id": str(other.city_id)}).status_code == 403

    # the Super Admin creates the city, then approves into it: member and household move in
    r = c.post("/superadmin/cities", headers=sa_h, json={"name": new_city, "state": "Gujarat"})
    assert r.status_code in (200, 201), r.text
    city_ids.append(r.json()["city_id"])
    r = c.post(f"/superadmin/members/{mid}/approve", headers=sa_h, json={"city_id": city_ids[-1]})
    assert r.status_code == 200 and r.json()["status"] == "ACTIVE" and r.json()["city_id"] == city_ids[-1], r.text
    with SessionLocal() as db:
        assert str(db.get(Household, db.get(Member, mid).household_id).city_id) == city_ids[-1]
    assert c.post(f"/superadmin/members/{mid}/approve", headers=sa_h, json={"city_id": city_ids[-1]}).status_code == 409

    # reject keeps the member out of any city, with the reason
    r = c.post(f"/superadmin/members/{rej_id}/reject", headers=sa_h, json={"reason": "Not a samaj member"})
    assert r.status_code == 200 and r.json()["status"] == "REJECTED" and r.json()["city_id"] is None, r.text
    assert c.post(f"/superadmin/members/{rej_id}/approve", headers=sa_h,
                  json={"city_id": city_ids[-1]}).status_code == 409
    print("ok")
finally:
    with SessionLocal() as db:  # auth_session rows go via ON DELETE CASCADE
        ids = list(db.scalars(select(Member.member_id).where(Member.mobile_hash.in_(map(mobile_hash, mobiles)))))
        hh = list(db.scalars(select(Member.household_id).where(Member.member_id.in_(ids))))
        db.execute(delete(Consent).where(Consent.member_id.in_(ids)))
        db.execute(delete(Member).where(Member.member_id.in_(ids)))
        db.execute(delete(Household).where(Household.household_id.in_(hh)))
        db.execute(delete(AdminUser).where(AdminUser.admin_id.in_(admin_ids)))
        db.execute(delete(City).where(City.city_id.in_(city_ids)))
        db.commit()
