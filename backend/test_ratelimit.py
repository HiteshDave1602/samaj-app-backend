"""Request limits against the dev DB: python test_ratelimit.py
SRS System Limits: 60 req/min per member, 10 req/min per IP on OTP endpoints; plus the per-admin budget, the
member file budget, OTP sends per IP per hour and admin login per IP. Limits are lowered here so the run is quick.
Cleans up after itself."""
import secrets
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete

from auth.curd import hash_token
from auth.model import AuthSession
from core import ratelimit, sms
from core.config import settings
from core.database import SessionLocal
from core.security import fernet, hash_password
from main import app
from member.auth.curd import _start_session, mobile_hash
from member.auth.model import OtpChallenge
from member.profile.model import Household, Member
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser

tag = secrets.token_hex(4)
ip = f"198.18.{secrets.randbelow(256)}.{secrets.randbelow(256)}"  # benchmark range: never a real client
c = TestClient(app, client=(ip, 50000))  # the default test client has no IP, and an unknown IP is never limited
now = datetime.now(timezone.utc)
sent: list[str] = []
sms.send_sms = lambda mobile, text: sent.append(mobile)
settings.member_rate_per_minute, settings.member_file_rate_per_minute, settings.admin_rate_per_minute = 5, 3, 4
settings.otp_ip_rate_per_minute, settings.otp_ip_rate_per_hour, settings.auth_ip_rate_per_minute = 3, 30, 3
ratelimit.reset()


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def new_mobile() -> str:
    return f"9{secrets.randbelow(10**9):09d}"


def limited(r) -> bool:
    return r.status_code == 429 and int(r.headers["Retry-After"]) >= 1


with SessionLocal() as db:
    city = City(name=f"RateCity-{tag}", state="T")
    db.add(city)
    db.flush()
    admin = AdminUser(role="CITY_ADMIN", city_id=city.city_id, full_name="RA", email=f"rate-{tag}@t.local",
                      password_hash=hash_password(secrets.token_hex(8)))
    db.add(admin)
    db.flush()
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(admin_id=admin.admin_id, refresh_token_hash=hash_token(token), mfa_verified=True,
                       last_activity_at=now, expires_at=now + timedelta(hours=1)))
    mobile = f"+91{new_mobile()}"
    h = Household(household_id=uuid4(), city_id=city.city_id, family_name="Rate family")
    db.add(h)
    db.flush()
    m = Member(member_id=uuid4(), city_id=city.city_id, household_id=h.household_id, is_household_head=True,
               mobile_hash=mobile_hash(mobile), mobile_enc=fernet.encrypt(mobile.encode()), mobile_last4=mobile[-4:],
               full_name="Rate", gender="FEMALE", dob=date(1997, 1, 1), status="ACTIVE")
    db.add(m)
    db.flush()
    member_h, admin_h = bearer(_start_session(db, m)["access_token"]), bearer(token)
    db.commit()
    city_id, admin_id = city.city_id, admin.admin_id

try:
    # member: 5 calls pass, the 6th is 429 with Retry-After; the file budget is separate
    assert all(c.get("/member/me", headers=member_h).status_code == 200 for _ in range(5))
    assert limited(c.get("/member/me", headers=member_h))
    photo = f"/member/matrimony/photos/{uuid4()}/file"
    assert all(c.get(photo, headers=member_h).status_code != 429 for _ in range(3))
    assert limited(c.get(photo, headers=member_h))

    # admin: own budget, keyed by admin
    assert all(c.get("/admin/auth/me", headers=admin_h).status_code == 200 for _ in range(4))
    assert limited(c.get("/admin/auth/me", headers=admin_h))

    # OTP send per IP, counted in Postgres: different numbers, same IP -> 4th is 429 and sends no SMS
    for _ in range(3):
        assert c.post("/member/auth/otp/send", json={"mobile": new_mobile()}).status_code == 200
    sent.clear()
    r = c.post("/member/auth/otp/send", json={"mobile": new_mobile()})
    assert r.status_code == 429 and "a minute" in r.text and not sent, r.text
    settings.otp_ip_rate_per_minute, settings.otp_ip_rate_per_hour = 100, 3  # the hour limit on its own
    r = c.post("/member/auth/otp/send", json={"mobile": new_mobile()})
    assert r.status_code == 429 and "an hour" in r.text and not sent, r.text

    # OTP verify per IP (in-process count; shares the per-minute setting with send)
    settings.otp_ip_rate_per_minute = 3
    for _ in range(3):
        assert c.post("/member/auth/otp/verify", json={"mobile": new_mobile(), "code": "123456"}).status_code != 429
    assert limited(c.post("/member/auth/otp/verify", json={"mobile": new_mobile(), "code": "123456"}))

    # admin login per IP: a different email each time, so the per-email lock never fires
    for i in range(3):
        r = c.post("/admin/auth/login", json={"email": f"nobody{i}-{tag}@t.local", "password": "x" * 12})
        assert r.status_code == 401, r.text
    assert limited(c.post("/admin/auth/login", json={"email": f"nobody9-{tag}@t.local", "password": "x" * 12}))

    # never limited: health, and clients whose IP is unknown
    assert all(c.get("/health").status_code == 200 for _ in range(10))
    plain = TestClient(app)
    assert all(plain.post("/member/auth/otp/verify", json={"mobile": new_mobile(), "code": "123456"}).status_code
               != 429 for _ in range(5))
    print("ok")
finally:
    with SessionLocal() as db:
        db.execute(delete(OtpChallenge).where(OtpChallenge.request_ip == ip))
        db.execute(delete(Member).where(Member.city_id == city_id))
        db.execute(delete(Household).where(Household.city_id == city_id))
        db.execute(delete(AdminUser).where(AdminUser.admin_id == admin_id))
        db.execute(delete(City).where(City.city_id == city_id))
        db.commit()
