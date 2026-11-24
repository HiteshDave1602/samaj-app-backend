"""The admin bell against the dev DB: python test_admin_requests.py
A City Admin sees only their own city's pending member requests; the Super Admin sees every city's;
a decided request drops out. Cleans up after itself; audit_log rows stay."""
import secrets
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from auth.curd import hash_token
from auth.model import AuthSession
from cityadmin.content.model import ContentItem
from core import sms
from core.database import SessionLocal
from core.security import fernet, hash_password
from main import app
from member.auth.curd import mobile_hash
from member.profile.model import FamilyMember, Household, Member
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser

c = TestClient(app)
tag = secrets.token_hex(4)
now = datetime.now(timezone.utc)
sms.send_sms = lambda mobile, text: None


def admin(db, role: str, city: City | None) -> tuple[dict, AdminUser]:
    a = AdminUser(role=role, city_id=city.city_id if city else None, full_name=role, email=f"req-{role}-{tag}@t.local",
                  password_hash=hash_password(secrets.token_hex(8)))
    db.add(a)
    db.flush()
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(admin_id=a.admin_id, refresh_token_hash=hash_token(token), mfa_verified=True,
                       last_activity_at=now, expires_at=now + timedelta(hours=1)))
    return {"Authorization": f"Bearer {token}"}, a


def member(db, city: City, name: str, status: str) -> Member:
    mobile = f"+919{secrets.randbelow(10**9):09d}"
    h = Household(household_id=uuid4(), city_id=city.city_id, family_name=f"{name} family")
    m = Member(member_id=uuid4(), city_id=city.city_id, household_id=h.household_id, is_household_head=True,
               mobile_hash=mobile_hash(mobile), mobile_enc=fernet.encrypt(mobile.encode()), mobile_last4=mobile[-4:],
               full_name=name, gender="FEMALE", dob=date(1997, 1, 1), status=status)
    db.add(h)
    db.flush()
    db.add(m)
    db.flush()
    return m


with SessionLocal() as db:
    city, other = City(name=f"ReqCity-{tag}", state="T"), City(name=f"ReqOther-{tag}", state="T")
    db.add_all([city, other])
    db.flush()
    ca_h, ca = admin(db, "CITY_ADMIN", city)
    sa_h, sa = admin(db, "SUPER_ADMIN", None)
    pending = member(db, city, "Pooja", "PENDING")
    active = member(db, city, "Anita", "ACTIVE")
    elsewhere = member(db, other, "Olga", "PENDING")
    db.add(FamilyMember(household_id=active.household_id, requested_by_member_id=active.member_id,
                        full_name="Baby Anita", relationship="DAUGHTER", status="PENDING"))
    db.add(ContentItem(content_type="NEWS", city_id=city.city_id, title="Garba night", body="b", status="PENDING",
                       start_at=now, end_at=now + timedelta(days=1), created_by_member_id=active.member_id))
    db.commit()
    ids = dict(city=city.city_id, other=other.city_id, admins=[ca.admin_id, sa.admin_id], pending=str(pending.member_id),
               elsewhere=str(elsewhere.member_id))

inbox = lambda h: c.get("/admin/requests", headers=h).json()  # noqa: E731

try:
    assert c.get("/admin/requests").status_code == 401
    page = inbox(ca_h)
    kinds = {(i["kind"], i["member_name"], i["detail"]) for i in page["items"]}
    assert kinds == {("REGISTRATION", "Pooja", None), ("FAMILY", "Anita", "Baby Anita"),
                     ("NEWS", "Anita", "Garba night")}, page  # not Olga: another city
    assert page["total"] == 3 and page["items"][0]["city_name"] == f"ReqCity-{tag}"
    assert page["unread"] == 3 and all(i["unread"] for i in page["items"]), page

    sa_ids = {i["id"] for i in c.get("/admin/requests?limit=200", headers=sa_h).json()["items"]}
    assert ids["elsewhere"] in sa_ids and ids["pending"] in sa_ids

    # opening the bell clears only my badge, on every device (it's stored server-side)
    assert c.post("/admin/requests/read", headers=ca_h).status_code == 204
    page = inbox(ca_h)
    assert page["unread"] == 0 and page["total"] == 3 and not any(i["unread"] for i in page["items"]), page
    assert inbox(sa_h)["unread"] >= 4
    with SessionLocal() as db:  # a request sent after that is new again
        member(db, db.get(City, ids["city"]), "Late", "PENDING")
        db.commit()
    page = inbox(ca_h)
    assert page["unread"] == 1 and page["items"][0]["member_name"] == "Late" and page["items"][0]["unread"], page

    assert c.post(f"/cityadmin/members/{ids['pending']}/approve", headers=ca_h).status_code == 200
    assert ids["pending"] not in {i["id"] for i in inbox(ca_h)["items"]}
    print("ok")
finally:
    with SessionLocal() as db:
        for cid in (ids["city"], ids["other"]):
            db.execute(delete(ContentItem).where(ContentItem.city_id == cid))
            db.execute(delete(FamilyMember).where(FamilyMember.household_id.in_(
                select(Household.household_id).where(Household.city_id == cid))))
            db.execute(delete(Member).where(Member.city_id == cid))
            db.execute(delete(Household).where(Household.city_id == cid))
        db.execute(delete(AdminUser).where(AdminUser.admin_id.in_(ids["admins"])))
        db.execute(delete(City).where(City.city_id.in_([ids["city"], ids["other"]])))
        db.commit()
