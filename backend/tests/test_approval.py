"""End-to-end City Admin approval queue check (SF-02) against the dev DB: python test_approval.py
Creates two cities, their City Admins, a Super Admin and pending members, then deletes them.
Their audit_log rows stay: the table is append-only by design."""
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, update

from auth.curd import hash_token
from auth.model import AuthSession
from core import sms
from core.database import SessionLocal
from core.security import fernet, hash_password
from main import app
from member.auth.curd import _start_session, mobile_hash
from member.profile.model import Household, Member
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser

c = TestClient(app)
tag = secrets.token_hex(4)
outbox: dict[str, str] = {}
sms.send_sms = lambda mobile, text: outbox.__setitem__(mobile, text)


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def admin_session(db, admin: AdminUser) -> dict:
    # Login + MFA is covered by test_auth.py; here a session row is enough.
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    db.add(AuthSession(admin_id=admin.admin_id, refresh_token_hash=hash_token(token), mfa_verified=True,
                       last_activity_at=now, expires_at=now + timedelta(hours=1)))
    return bearer(token)


def pending_member(db, city: City, name: str, age_hours: float = 0) -> Member:
    mobile = f"+919{secrets.randbelow(10**9):09d}"
    m = Member(city_id=city.city_id, mobile_hash=mobile_hash(mobile), mobile_enc=fernet.encrypt(mobile.encode()),
               mobile_last4=mobile[-4:], full_name=name, gender="MALE",
               address_enc=fernet.encrypt(b"1 Test Lane"),
               created_at=datetime.now(timezone.utc) - timedelta(hours=age_hours))
    db.add(m)
    return m


with SessionLocal() as db:
    city_x, city_y = City(name=f"X-{tag}", state="T"), City(name=f"Y-{tag}", state="T")
    db.add_all([city_x, city_y])
    db.flush()
    pw = hash_password(secrets.token_hex(8))
    sa = AdminUser(role="SUPER_ADMIN", full_name="SA", email=f"sa-{tag}@t.local", password_hash=pw)
    ca_x = AdminUser(role="CITY_ADMIN", city_id=city_x.city_id, full_name="CA X", email=f"x-{tag}@t.local",
                     password_hash=pw)
    ca_y = AdminUser(role="CITY_ADMIN", city_id=city_y.city_id, full_name="CA Y", email=f"y-{tag}@t.local",
                     password_hash=pw)
    db.add_all([sa, ca_x, ca_y])
    db.flush()
    sa_h, x_h, y_h = admin_session(db, sa), admin_session(db, ca_x), admin_session(db, ca_y)
    # X: oldest is 80 h (overdue), then 10 h, 5 h, 4 h, 3 h; Y: one 2 h
    old = pending_member(db, city_x, "Old Overdue", 80)
    household = Household(city_id=city_x.city_id, family_name="Shah_Family")  # no tag: hex could match the searches below
    db.add(household)
    db.flush()
    a = pending_member(db, city_x, "A", 10)
    a.household_id = household.household_id
    b1, b2, b3 = (pending_member(db, city_x, f"B{i}", 5 - i) for i in range(3))
    y1 = pending_member(db, city_y, "Y One", 2)
    db.commit()
    ids = {k: str(v.member_id) for k, v in dict(old=old, a=a, b1=b1, b2=b2, b3=b3, y1=y1).items()}
    city_ids, admin_ids = [city_x.city_id, city_y.city_id], [sa.admin_id, ca_x.admin_id, ca_y.admin_id]
    ca_x_id = str(ca_x.admin_id)

base = "/cityadmin/members"
try:
    # FR-69: City Admin only
    assert c.get(f"{base}/pending", headers=sa_h).status_code == 403
    assert c.get(f"{base}/pending").status_code == 401

    # FR-12: own city only, oldest first
    page = c.get(f"{base}/pending", headers=x_h).json()
    assert page["total"] == 5 and [m["full_name"] for m in page["items"]] == ["Old Overdue", "A", "B0", "B1", "B2"]
    assert [m["member_id"] for m in c.get(f"{base}/pending", headers=y_h).json()["items"]] == [ids["y1"]]
    assert c.get(f"{base}/pending?limit=2&offset=1", headers=x_h).json()["items"][0]["full_name"] == "A"

    # FR-71: full member list, own city only, by name; filter by status, search name or family name
    names = lambda **p: [m["full_name"] for m in c.get(base, headers=x_h, params=p).json()["items"]]
    assert names() == ["A", "B0", "B1", "B2", "Old Overdue"]
    assert c.get(base, headers=y_h).json()["total"] == 1
    assert names(q="b") == ["B0", "B1", "B2"] and names(q="  OVERDUE ") == ["Old Overdue"]
    assert names(q="shah_family") == ["A"]  # family name
    assert names(q="%") == [] and names(q="Shah%") == []  # wildcards are literal
    assert names(status="PENDING", limit=2, offset=1) == ["B0", "B1"] and names(status="ACTIVE") == []
    assert c.get(base, headers=x_h, params={"status": "BOGUS"}).status_code == 422
    assert c.get(base, headers=x_h, params={"q": "  "}).status_code == 422
    assert c.get(base, headers=sa_h).status_code == 403 and c.get(base).status_code == 401

    # FR-12: City Y's member is 403 for City X's admin, for every action
    assert c.get(f"{base}/{ids['y1']}", headers=x_h).status_code == 403
    assert c.post(f"{base}/{ids['y1']}/approve", headers=x_h).status_code == 403
    assert c.post(f"{base}/{ids['y1']}/reject", headers=x_h, json={"reason": "x"}).status_code == 403
    assert c.get(f"{base}/{uuid4()}", headers=x_h).status_code == 404

    # detail shows the full number for verification
    d = c.get(f"{base}/{ids['a']}", headers=x_h).json()
    assert d["mobile"].startswith("+91") and d["address"] == "1 Test Lane" and d["status"] == "PENDING", d

    # FR-13: approve -> ACTIVE, reviewer recorded, member notified (FR-14 SMS fallback), not twice
    outbox.clear()
    r = c.post(f"{base}/{ids['a']}/approve", headers=x_h)
    assert r.status_code == 200 and r.json()["status"] == "ACTIVE" and r.json()["reviewed_by_admin_id"] == ca_x_id
    assert "approved" in outbox[d["mobile"]]
    assert c.post(f"{base}/{ids['a']}/approve", headers=x_h).status_code == 409
    assert c.post(f"{base}/{ids['a']}/reject", headers=x_h, json={"reason": "late"}).status_code == 409

    # FR-15: reject needs a reason, which the member then sees in the app
    assert c.post(f"{base}/{ids['old']}/reject", headers=x_h, json={"reason": "   "}).status_code == 422
    assert c.post(f"{base}/{ids['old']}/reject", headers=x_h, json={}).status_code == 422
    r = c.post(f"{base}/{ids['old']}/reject", headers=x_h, json={"reason": "Could not verify family details"})
    assert r.status_code == 200 and r.json()["status"] == "REJECTED", r.text
    with SessionLocal() as db:
        tokens = _start_session(db, db.get(Member, old.member_id))
    me = c.get("/member/me", headers=bearer(tokens["access_token"])).json()
    assert me["status"] == "REJECTED" and me["rejection_reason"] == "Could not verify family details", me

    # FR-16: bulk approve is all-or-nothing; a cross-city id rolls the batch back
    batch = [ids["b1"], ids["b2"], ids["b3"]]
    assert c.post(f"{base}/bulk-approve", headers=x_h, json={"member_ids": batch + [ids["y1"]]}).status_code == 403
    assert c.get(f"{base}/pending", headers=x_h).json()["total"] == 3
    assert c.post(f"{base}/bulk-approve", headers=x_h, json={"member_ids": []}).status_code == 422
    r = c.post(f"{base}/bulk-approve", headers=x_h, json={"member_ids": batch + [ids["b1"]]})  # duplicate ignored
    assert r.status_code == 200 and r.json() == {"approved": 3}, r.text
    assert c.get(f"{base}/pending", headers=x_h).json()["total"] == 0
    assert names(status="ACTIVE") == ["A", "B0", "B1", "B2"] and names(status="REJECTED") == ["Old Overdue"]

    # FR-86: one audit entry per decision, actor = City Admin, with city
    entries = c.get("/superadmin/audit-logs", headers=sa_h,
                    params={"actor_id": ca_x_id, "limit": 200}).json()["items"]
    assert sorted(e["action"] for e in entries) == ["MEMBER_APPROVE"] * 4 + ["MEMBER_REJECT"], entries
    assert all(e["city_name"] == f"X-{tag}" and e["before_state"] == {"status": "PENDING"} for e in entries)
    rej = next(e for e in entries if e["action"] == "MEMBER_REJECT")
    assert rej["after_state"] == {"status": "REJECTED", "rejection_reason": "Could not verify family details"}

    # FR-16 escalation: pending > 72 h shows for the Super Admin with the city's admin; City Admins can't see it
    with SessionLocal() as db:
        db.execute(update(Member).where(Member.member_id == y1.member_id)
                   .values(created_at=datetime.now(timezone.utc) - timedelta(hours=72, minutes=1)))
        db.commit()
    assert c.get("/superadmin/pending-members/overdue", headers=x_h).status_code == 403
    overdue = [o for o in c.get("/superadmin/pending-members/overdue", headers=sa_h).json()
               if o["city_id"] in map(str, city_ids)]
    assert [(o["member_id"], o["city_admin_name"]) for o in overdue] == [(ids["y1"], "CA Y")], overdue
    print("ok")
finally:
    with SessionLocal() as db:  # auth_session rows go via ON DELETE CASCADE
        db.execute(delete(Member).where(Member.city_id.in_(city_ids)))
        db.execute(delete(Household).where(Household.city_id.in_(city_ids)))
        db.execute(delete(AdminUser).where(AdminUser.admin_id.in_(admin_ids)))
        db.execute(delete(City).where(City.city_id.in_(city_ids)))
        db.commit()
