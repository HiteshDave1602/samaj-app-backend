"""Panchang manual override check (SF-09, FR-60–63) against the dev DB: python test_panchang.py
Uses dates in 2099 so real days are never touched; deletes them after. audit_log rows stay (append-only)."""
import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from auth.curd import hash_token
from auth.model import AuthSession
from cityadmin.panchang import curd
from cityadmin.panchang.model import PanchangDay, PanchangRevision
from core.database import SessionLocal
from core.security import hash_password
from main import app
from superadmin.audit_log.curd import IST
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser

c = TestClient(app)
tag = secrets.token_hex(4)
now = datetime.now(timezone.utc)
D1, D2, D3 = date(2099, 1, 5), date(2099, 1, 6), date(2099, 1, 7)
base = "/cityadmin/panchang"


def admin_session(db, admin: AdminUser) -> dict:
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(admin_id=admin.admin_id, refresh_token_hash=hash_token(token), mfa_verified=True,
                       last_activity_at=now, expires_at=now + timedelta(hours=1)))
    return {"Authorization": f"Bearer {token}"}


def put(d: date, h: dict, **body):
    return c.put(f"{base}/{d}", headers=h, json={"tithi": "Panchami", "nakshatra": "Rohini", "yoga": "Siddhi",
                                                 "verified_against_calendar": True} | body)


with SessionLocal() as db:
    cx, cy = City(name=f"PX-{tag}", state="T"), City(name=f"PY-{tag}", state="T")
    db.add_all([cx, cy])
    db.flush()
    pw = hash_password(secrets.token_hex(8))
    sa = AdminUser(role="SUPER_ADMIN", full_name="SA", email=f"psa-{tag}@t.local", password_hash=pw)
    ca_x = AdminUser(role="CITY_ADMIN", city_id=cx.city_id, full_name="CA X", email=f"px-{tag}@t.local", password_hash=pw)
    ca_y = AdminUser(role="CITY_ADMIN", city_id=cy.city_id, full_name="CA Y", email=f"py-{tag}@t.local", password_hash=pw)
    db.add_all([sa, ca_x, ca_y])
    db.flush()
    sa_h, x_h, y_h = admin_session(db, sa), admin_session(db, ca_x), admin_session(db, ca_y)
    # D2 already has API values, as the fetch job will store them
    api_day = PanchangDay(panchang_date=D2, tithi="Shashthi", nakshatra="Mrigashira", yoga="Vyatipata", source="API",
                          fetched_at=now, published_at=now)
    db.add(api_day)
    db.flush()
    db.add(PanchangRevision(panchang_id=api_day.panchang_id, tithi="Shashthi", nakshatra="Mrigashira",
                            yoga="Vyatipata", source="API", api_status="OK"))
    db.commit()
    city_ids, admin_ids, ca_x_id = [cx.city_id, cy.city_id], [sa.admin_id, ca_x.admin_id, ca_y.admin_id], ca_x.admin_id

try:
    assert c.get(f"{base}/{D1}", headers=x_h).status_code == 404

    # FR-63: saving needs the "verified against the Samaj calendar" tick; all three values required
    assert put(D1, x_h, verified_against_calendar=False).status_code == 422
    assert c.put(f"{base}/{D1}", headers=x_h, json={"tithi": "x", "nakshatra": "y", "yoga": "z"}).status_code == 422
    assert put(D1, x_h, yoga="  ").status_code == 422

    # FR-61: a new day is saved and published at once
    r = put(D1, x_h)
    assert r.status_code == 200, r.text
    day = r.json()
    assert (day["source"], day["edited_by_name"], day["tithi"]) == ("MANUAL", "CA X", "Panchami"), day
    assert day["published_at"] and [v["source"] for v in day["revisions"]] == ["MANUAL"]

    # FR-62: manual beats API for the same date; history shows both, newest first, with the editor
    r = put(D2, y_h, tithi="Saptami")  # any city's admin: one Panchang for the deployment (ASM-05)
    assert r.status_code == 200 and r.json()["source"] == "MANUAL" and r.json()["tithi"] == "Saptami", r.text
    revs = r.json()["revisions"]
    assert [(v["source"], v["edited_by_name"], v["tithi"]) for v in revs] == [
        ("MANUAL", "CA Y", "Saptami"), ("API", None, "Shashthi")], revs
    assert revs[1]["api_status"] == "OK"
    r = put(D1, y_h, nakshatra="Ardra")  # a correction
    assert [v["nakshatra"] for v in r.json()["revisions"]] == ["Ardra", "Rohini"] and r.json()["edited_by_name"] == "CA Y"

    # list by date range
    lst = c.get(base, headers=x_h, params={"date_from": str(D1), "date_to": str(D3)}).json()
    assert [(d["panchang_date"], d["source"]) for d in lst] == [(str(D1), "MANUAL"), (str(D2), "MANUAL")], lst
    assert c.get(base, headers=x_h, params={"date_from": str(D2), "date_to": str(D1)}).status_code == 400
    assert c.get(base, headers=x_h, params={"date_from": str(D1), "date_to": str(D1 + timedelta(days=93))}).status_code == 400
    assert c.get(base, headers=x_h).status_code == 200  # default: this week
    assert c.get(f"{base}/status", headers=x_h).status_code == 200 and put(D1, sa_h).status_code == 403

    # FR-60: ERR_API_PN from 04:00 IST when the day is still missing
    at = lambda d, h, m: datetime(d.year, d.month, d.day, h, m, tzinfo=IST)
    with SessionLocal() as db:
        s = curd.status(db, at(D1, 4, 30).astimezone(timezone.utc))
        assert (s["available"], s["source"], s["tomorrow_available"], s["error_code"]) == (True, "MANUAL", True, None), s
        s = curd.status(db, at(D3, 3, 59))
        assert (s["date"], s["available"], s["error_code"]) == (D3, False, None), s  # not yet: before the cut-off
        s = curd.status(db, at(D3, 4, 0))
        assert s["error_code"] == "ERR_API_PN" and "manually" in s["message"] and not s["tomorrow_available"], s
        s = curd.status(db, datetime(2099, 1, 6, 23, 0, tzinfo=timezone.utc))  # = 04:30 on D3 in IST
        assert s["date"] == D3 and s["error_code"] == "ERR_API_PN", s

    # FR-86: one PANCHANG_OVERRIDE per save; overriding API values keeps them in before_state
    entries = c.get("/superadmin/audit-logs", headers=sa_h,
                    params={"action": "PANCHANG_OVERRIDE", "city_id": str(city_ids[1]), "limit": 50}).json()["items"]
    assert len(entries) == 2, entries
    over_api = next(e for e in entries if e["after_state"]["panchang_date"] == str(D2))
    assert over_api["before_state"]["source"] == "API" and over_api["after_state"]["tithi"] == "Saptami"
    print("ok")
finally:
    with SessionLocal() as db:
        day_ids = select(PanchangDay.panchang_id).where(PanchangDay.panchang_date.in_([D1, D2, D3]))
        db.execute(delete(PanchangRevision).where(PanchangRevision.panchang_id.in_(day_ids)))
        db.execute(delete(PanchangDay).where(PanchangDay.panchang_date.in_([D1, D2, D3])))
        db.execute(delete(AdminUser).where(AdminUser.admin_id.in_(admin_ids)))
        db.execute(delete(City).where(City.city_id.in_(city_ids)))
        db.commit()
