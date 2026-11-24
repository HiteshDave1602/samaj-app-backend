"""Admins deleting members and matrimony profiles, against the dev DB: python test_delete.py
A City Admin deletes in their own city, the Super Admin in any. Deleted members can't log in, refresh, register
again or use a live token; a removed matrimony profile is gone from search and its owner can't open or recreate it."""
import secrets
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from auth.curd import hash_token
from auth.model import AuthSession
from core import sms
from core.database import SessionLocal
from core.security import fernet, hash_password
from main import app
from member.auth.curd import NOTICE_VERSION, _start_session, mobile_hash
from member.matrimony.model import MatrimonyProfile
from member.profile.model import Consent, Household, Member
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser

c = TestClient(app)
tag = secrets.token_hex(4)
sms.send_sms = lambda mobile, text: None


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def admin_session(db, admin: AdminUser) -> dict:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    db.add(AuthSession(admin_id=admin.admin_id, refresh_token_hash=hash_token(token), mfa_verified=True,
                       last_activity_at=now, expires_at=now + timedelta(hours=1)))
    return bearer(token)


def active_member(db, city: City, name: str, gender: str) -> tuple[Member, str]:
    mobile = f"+919{secrets.randbelow(10**9):09d}"
    m = Member(member_id=uuid4(), city_id=city.city_id, mobile_hash=mobile_hash(mobile),
               mobile_enc=fernet.encrypt(mobile.encode()), mobile_last4=mobile[-4:], full_name=name, gender=gender,
               dob=date(1996, 1, 1), status="ACTIVE", reviewed_at=datetime.now(timezone.utc))
    db.add(m)
    db.flush()
    db.add(MatrimonyProfile(member_id=m.member_id, location_city_id=city.city_id, education_level="GRADUATE",
                            family_background="JOINT", status="APPROVED"))
    return m, mobile


with SessionLocal() as db:
    x, y = City(name=f"DelX-{tag}", state="T"), City(name=f"DelY-{tag}", state="T")
    db.add_all([x, y])
    db.flush()
    pw = hash_password(secrets.token_hex(8))
    sa = AdminUser(role="SUPER_ADMIN", full_name="SA", email=f"sa-{tag}@t.local", password_hash=pw)
    ca_x = AdminUser(role="CITY_ADMIN", city_id=x.city_id, full_name="CA X", email=f"x-{tag}@t.local", password_hash=pw)
    ca_y = AdminUser(role="CITY_ADMIN", city_id=y.city_id, full_name="CA Y", email=f"y-{tag}@t.local", password_hash=pw)
    db.add_all([sa, ca_x, ca_y])
    db.flush()
    sa_h, x_h, y_h = admin_session(db, sa), admin_session(db, ca_x), admin_session(db, ca_y)
    (a, a_mobile), (b, _), (yy, _) = (active_member(db, x, "Asha", "FEMALE"), active_member(db, x, "Bharat", "MALE"),
                                      active_member(db, y, "Yash", "MALE"))
    db.commit()
    a_s, b_s = _start_session(db, a), _start_session(db, b)
    ids = {k: str(v.member_id) for k, v in dict(a=a, b=b, y=yy).items()}
    prof = {k: str(db.scalar(select(MatrimonyProfile.profile_id).where(MatrimonyProfile.member_id == v.member_id)))
            for k, v in dict(a=a, b=b, y=yy).items()}
    city_ids, admin_ids = [x.city_id, y.city_id], [sa.admin_id, ca_x.admin_id, ca_y.admin_id]

a_h, b_h = bearer(a_s["access_token"]), bearer(b_s["access_token"])
M = "/member/matrimony"
try:
    # other city's City Admin: 403 for both; members can't call admin deletes
    assert c.delete(f"/cityadmin/matrimony/profiles/{prof['a']}", headers=y_h).status_code == 403
    assert c.delete(f"/cityadmin/members/{ids['a']}", headers=y_h).status_code == 403
    assert c.delete(f"/cityadmin/members/{ids['a']}", headers=a_h).status_code == 401

    # matrimony: City Admin X removes Asha's profile
    # (the profile page uses the same "searchable" filter as search, which may be async Elasticsearch here)
    assert c.get(f"{M}/profiles/{prof['a']}", headers=b_h).status_code == 200
    assert c.delete(f"/cityadmin/matrimony/profiles/{prof['a']}", headers=x_h).status_code == 204
    assert c.get(f"{M}/profiles/{prof['a']}", headers=b_h).status_code == 404
    r = c.get(f"{M}/profile", headers=a_h)
    assert r.status_code == 403 and "removed" in r.text, r.text
    assert c.post(f"{M}/profile", headers=a_h, json={"education_level": "GRADUATE", "family_background": "JOINT"}
                  ).status_code == 403
    assert c.get(f"{M}/biodata", headers=a_h).status_code == 403
    assert prof["a"] not in {p["profile_id"] for p in c.get("/cityadmin/matrimony/profiles", headers=x_h).json()["items"]}
    assert c.get(f"/cityadmin/matrimony/profiles/{prof['a']}", headers=x_h).status_code == 404
    assert c.delete(f"/cityadmin/matrimony/profiles/{prof['a']}", headers=x_h).status_code == 404
    assert c.get("/member/me", headers=a_h).status_code == 200  # the account itself stays
    # the Super Admin removes in any city
    assert c.delete(f"/superadmin/matrimony/profiles/{prof['y']}", headers=sa_h).status_code == 204

    # member: City Admin X deletes Asha; her live token and refresh stop, and the number is free again
    assert c.delete(f"/cityadmin/members/{ids['a']}", headers=x_h).status_code == 204
    assert c.get("/member/me", headers=a_h).status_code == 401
    assert c.post("/member/auth/refresh", json={"refresh_token": a_s["refresh_token"]}).status_code == 401
    assert c.post("/member/auth/otp/send", json={"mobile": a_mobile, "intent": "login"}).status_code == 404
    assert ids["a"] not in {m["member_id"] for m in c.get("/cityadmin/members", headers=x_h).json()["items"]}
    assert c.get(f"/superadmin/members/{ids['a']}", headers=sa_h).status_code == 404
    assert c.delete(f"/superadmin/members/{ids['a']}", headers=sa_h).status_code == 404
    register = lambda mobile: c.post("/member/auth/register", json={  # noqa: E731
        "mobile": mobile, "full_name": "Asha Patel", "gender": "FEMALE", "dob": "1996-01-01",
        "city_id": str(x.city_id), "address": "1 Lane", "family_name": "Patel", "consent": True,
        "notice_version": NOTICE_VERSION})
    r = register(a_mobile)  # same number, a new account that waits for approval like anyone new
    assert r.status_code == 201 and r.json()["member_status"] == "PENDING", r.text
    assert register(a_mobile).status_code == 409  # but only one live account per number
    with SessionLocal() as db:
        again = db.scalar(select(Member).where(Member.mobile_hash == mobile_hash(a_mobile), Member.deleted_at.is_(None)))
        assert str(again.member_id) != ids["a"]
        again.status, again.reviewed_at = "ACTIVE", datetime.now(timezone.utc)
        db.commit()
        a2_s = _start_session(db, again)
    a2_h = bearer(a2_s["access_token"])

    # the member deletes their own account: same effect, audited as the member, and they can come back
    assert c.delete("/member/me").status_code == 401
    assert c.delete("/member/me", headers=a2_h).status_code == 204
    assert c.get("/member/me", headers=a2_h).status_code == 401
    assert c.post("/member/auth/refresh", json={"refresh_token": a2_s["refresh_token"]}).status_code == 401
    assert c.get(f"/superadmin/members/{again.member_id}", headers=sa_h).status_code == 404
    own = c.get("/superadmin/audit-logs", headers=sa_h, params={"actor_id": str(again.member_id)}).json()["items"]
    assert [e["action"] for e in own] == ["MEMBER_SELF_DELETE"], own
    assert register(a_mobile).status_code == 201

    # the Super Admin deletes a member of any city; a deleted member's matrimony profile leaves search too
    assert prof["b"] in {p["profile_id"] for p in c.get("/superadmin/matrimony/profiles", headers=sa_h,
                                                           params={"limit": 200}).json()["items"]}
    assert c.delete(f"/superadmin/members/{ids['b']}", headers=sa_h).status_code == 204
    assert c.get(f"/superadmin/matrimony/profiles/{prof['b']}", headers=sa_h).status_code == 404
    assert c.delete(f"/superadmin/members/{ids['y']}", headers=sa_h).status_code == 204

    # both deletions are in the audit log
    actions = [e["action"] for e in c.get("/superadmin/audit-logs", headers=sa_h,
                                          params={"actor_id": str(ca_x.admin_id)}).json()["items"]]
    assert sorted(actions) == ["MATRIMONY_DELETE", "MEMBER_DELETE"], actions
    print("ok")
finally:
    with SessionLocal() as db:  # auth_session rows go via ON DELETE CASCADE
        mids = list(db.scalars(select(Member.member_id).where(Member.city_id.in_(city_ids))))
        hids = list(db.scalars(select(Member.household_id).where(Member.member_id.in_(mids))))
        db.execute(delete(MatrimonyProfile).where(MatrimonyProfile.member_id.in_(mids)))
        db.execute(delete(Consent).where(Consent.member_id.in_(mids)))  # the re-registrations made these
        db.execute(delete(Member).where(Member.member_id.in_(mids)))
        db.execute(delete(Household).where(Household.household_id.in_(hids)))
        db.execute(delete(AdminUser).where(AdminUser.admin_id.in_(admin_ids)))
        db.execute(delete(City).where(City.city_id.in_(city_ids)))
        db.commit()
