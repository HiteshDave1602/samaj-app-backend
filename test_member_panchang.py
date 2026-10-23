"""Member Panchang (SF-09: FR-59, FR-64) against the dev DB: python test_member_panchang.py
Cleans up after itself."""
import secrets
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete

from cityadmin.panchang.model import PanchangDay
from core.database import SessionLocal
from core.security import fernet
from main import app
from member.auth.curd import _start_session, mobile_hash
from member.profile.model import Member
from superadmin.audit_log.curd import IST
from superadmin.city.model import City

c = TestClient(app)
tag = secrets.token_hex(4)
published = date(2090, 1, 1) + timedelta(days=secrets.randbelow(3000))  # far future: no real rows there
unpublished = published + timedelta(days=1)

with SessionLocal() as db:
    city = City(name=f"PanCity-{tag}", state="T")
    db.add(city)
    db.flush()
    mobile = f"+919{secrets.randbelow(10**9):09d}"
    m = Member(member_id=uuid4(), city_id=city.city_id, mobile_hash=mobile_hash(mobile),
               mobile_enc=fernet.encrypt(mobile.encode()), mobile_last4=mobile[-4:], full_name="P", status="PENDING")
    db.add(m)
    db.flush()
    h = {"Authorization": f"Bearer {_start_session(db, m)['access_token']}"}
    db.add_all([
        PanchangDay(panchang_id=uuid4(), panchang_date=published, tithi="Shukla Pratipada", nakshatra="Ashwini",
                    yoga="Vishkambha", source="API", published_at=datetime.now(timezone.utc)),
        PanchangDay(panchang_id=uuid4(), panchang_date=unpublished, tithi="T", nakshatra="N", yoga="Y",
                    source="API"),  # fetched but not yet published
    ])
    db.commit()
    city_id, days = city.city_id, [published, unpublished]

try:
    assert c.get("/member/panchang").status_code == 401

    # FR-08: a PENDING member can see it; FR-64: any date
    r = c.get("/member/panchang", headers=h, params={"date": str(published)})
    assert r.status_code == 200, r.text
    assert r.json() == {"panchang_date": str(published), "tithi": "Shukla Pratipada", "nakshatra": "Ashwini",
                        "yoga": "Vishkambha"}, r.json()  # no admin / source fields

    assert c.get("/member/panchang", headers=h, params={"date": str(unpublished)}).status_code == 404
    assert c.get("/member/panchang", headers=h, params={"date": "2090-13-01"}).status_code == 422

    # FR-59: no date means today in IST
    r = c.get("/member/panchang", headers=h)
    assert r.status_code == 404 or r.json()["panchang_date"] == str(datetime.now(IST).date()), r.text
    print("ok")
finally:
    with SessionLocal() as db:  # auth_session rows go via ON DELETE CASCADE
        db.execute(delete(PanchangDay).where(PanchangDay.location_code == "DEFAULT",
                                             PanchangDay.panchang_date.in_(days)))
        db.execute(delete(Member).where(Member.city_id == city_id))
        db.execute(delete(City).where(City.city_id == city_id))
        db.commit()
