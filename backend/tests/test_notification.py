"""The bell (member notifications) against the dev DB: python test_notification.py
An admin decision and a biodata request/answer each land in the right member's inbox, nobody else's; live city
news shows for members who want news; POST /read clears the badge. Cleans up after itself; audit_log rows stay."""
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
from member.auth.curd import _start_session, mobile_hash
from member.matrimony.model import MatrimonyProfile
from member.profile.model import Household, Member
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser

c = TestClient(app)
tag = secrets.token_hex(4)
now = datetime.now(timezone.utc)
sms.send_sms = lambda mobile, text: None
N = "/member/notifications"


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# notify_news=False keeps live news (all-city items already in the dev DB too) out of the decision checks
def new_member(db, city: City, name: str, status: str, profile: bool, news: bool = False) -> tuple[dict, Member, str | None]:
    mobile = f"+919{secrets.randbelow(10**9):09d}"
    h = Household(household_id=uuid4(), city_id=city.city_id, family_name=f"{name} family")
    m = Member(member_id=uuid4(), city_id=city.city_id, household_id=h.household_id, is_household_head=True,
               mobile_hash=mobile_hash(mobile), mobile_enc=fernet.encrypt(mobile.encode()), mobile_last4=mobile[-4:],
               full_name=name, gender="FEMALE", dob=date(1997, 1, 1), status=status, notify_news=news)
    db.add(h)
    db.flush()
    db.add(m)
    db.flush()
    pid = None
    if profile:
        p = MatrimonyProfile(profile_id=uuid4(), member_id=m.member_id, location_city_id=city.city_id,
                             education_level="GRADUATE", family_background="JOINT", status="APPROVED")
        db.add(p)
        db.flush()
        pid = str(p.profile_id)
    return bearer(_start_session(db, m)["access_token"]), m, pid


with SessionLocal() as db:
    city = City(name=f"NotiCity-{tag}", state="T")
    db.add(city)
    db.flush()
    ca = AdminUser(role="CITY_ADMIN", city_id=city.city_id, full_name="CA", email=f"noti-{tag}@t.local",
                   password_hash=hash_password(secrets.token_hex(8)))
    db.add(ca)
    db.flush()
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(admin_id=ca.admin_id, refresh_token_hash=hash_token(token), mfa_verified=True,
                       last_activity_at=now, expires_at=now + timedelta(hours=1)))
    ca_h = bearer(token)
    a_h, _, A = new_member(db, city, "Anita", "ACTIVE", True)
    b_h, _, B = new_member(db, city, "Bhavna", "ACTIVE", True)
    p_h, pm, _ = new_member(db, city, "Pooja", "PENDING", False)
    n_h, nm, _ = new_member(db, city, "Nisha", "ACTIVE", False, news=True)
    own = ContentItem(content_type="NEWS", city_id=city.city_id, title="Nisha's own", body="b", status="SCHEDULED",
                      start_at=now - timedelta(minutes=5), end_at=now + timedelta(days=1),
                      created_by_member_id=nm.member_id)  # approved member news, already live
    ad = lambda title, end: ContentItem(  # noqa: E731  Nisha's approved ads
        content_type="AD", creative_format="BANNER", media_key="k", city_id=city.city_id, title=title,
        status="SCHEDULED", start_at=now - timedelta(days=2), end_at=end, created_by_member_id=nm.member_id)
    ended, running = ad("Ended ad", now - timedelta(minutes=1)), ad("Running ad", now + timedelta(days=1))
    db.add_all([own, ended, running])
    db.commit()
    city_id, admin_id, P_id, own_id = city.city_id, ca.admin_id, str(pm.member_id), str(own.content_id)
    ended_id, running_id = str(ended.content_id), str(running.content_id)

inbox = lambda h: c.get(N, headers=h).json()  # noqa: E731
news = lambda title, start: c.post("/cityadmin/content", headers=ca_h, json={  # noqa: E731
    "content_type": "NEWS", "title": title, "body": "b", "start_at": start.isoformat(),
    "end_at": (now + timedelta(days=1)).isoformat()}).json()["content_id"]

try:
    assert c.get(N).status_code == 401
    assert inbox(a_h) == {"total": 0, "unread": 0, "items": []}

    # admin decision -> the member's own inbox
    assert c.post(f"/cityadmin/members/{P_id}/approve", headers=ca_h).status_code == 200
    page = inbox(p_h)
    assert (page["unread"], page["items"][0]["kind"], page["items"][0]["payload"]["approved"]) == \
           (1, "ACCOUNT_DECISION", True), page

    # biodata request -> recipient only, with the requester's public card
    assert c.post(f"/member/matrimony/profiles/{B}/biodata-request", headers=a_h).status_code == 201
    page = inbox(b_h)
    item = page["items"][0]
    assert (page["unread"], item["kind"], item["payload"]["profile_id"], item["counterpart"]["profile_id"]) == \
           (1, "BIODATA_REQUEST", A, A), page
    assert inbox(a_h)["total"] == 0

    # the answer -> requester
    rid = c.get("/member/matrimony/biodata-requests", headers=b_h, params={"box": "received"}).json()["items"][0]
    assert c.post(f"/member/matrimony/biodata-requests/{rid['request_id']}/decline", headers=b_h).status_code == 200
    item = inbox(a_h)["items"][0]
    assert (item["kind"], item["payload"]["accepted"], item["counterpart"]["profile_id"]) == \
           ("BIODATA_RESPONSE", False, B), item

    # opening the screen clears only my badge
    assert c.post(f"{N}/read", headers=b_h).status_code == 204
    page = inbox(b_h)
    assert page["unread"] == 0 and not page["items"][0]["unread"], page
    assert inbox(a_h)["unread"] == 1

    # live city news, while it's live: not before its start, not the member's own post, not with news turned off
    live, later = news("Sammelan", now - timedelta(minutes=1)), news("Later", now + timedelta(hours=1))
    mine = {i["notification_id"]: i for i in inbox(n_h)["items"] if i["kind"] == "NEWS_LIVE"}
    assert live in mine and later not in mine and own_id not in mine, mine
    assert (mine[live]["unread"], mine[live]["payload"]["title"]) == (True, "Sammelan"), mine[live]
    assert not any(i["kind"] == "NEWS_LIVE" for i in inbox(a_h)["items"])
    c.post(f"{N}/read", headers=n_h)
    assert not {i["notification_id"]: i for i in inbox(n_h)["items"]}[live]["unread"]

    # my own ad, once its run is over (not while it's running)
    ads = {i["notification_id"]: i for i in inbox(n_h)["items"] if i["kind"] == "AD_ENDED"}
    assert list(ads) == [ended_id] and running_id not in ads and ads[ended_id]["payload"]["title"] == "Ended ad", ads
    print("ok")
finally:
    with SessionLocal() as db:  # requests go with the profiles, notifications with the members (CASCADE)
        members = select(Member.member_id).where(Member.city_id == city_id)
        db.execute(delete(ContentItem).where(ContentItem.city_id == city_id))
        db.execute(delete(MatrimonyProfile).where(MatrimonyProfile.member_id.in_(members)))
        db.execute(delete(Member).where(Member.city_id == city_id))
        db.execute(delete(Household).where(Household.city_id == city_id))
        db.execute(delete(AdminUser).where(AdminUser.admin_id == admin_id))
        db.execute(delete(City).where(City.city_id == city_id))
        db.commit()
