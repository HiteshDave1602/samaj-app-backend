"""End-to-end admin auth check against the dev DB: python test_auth.py
Creates throwaway admins + a city, runs the login/MFA flow, then deletes them.
Their audit_log rows stay: the table is append-only by design."""
import secrets
from datetime import timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text, update
from sqlalchemy.exc import DBAPIError

from auth.model import AuthSession
from core.config import settings
from core.database import SessionLocal
from core.security import hash_password, totp
from main import app
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser

settings.admin_mfa = True  # this test covers the MFA flow whatever .env says
c = TestClient(app)
PW = "test-password-123"
tag = secrets.token_hex(4)


def ticket_for(email: str) -> str:
    r = c.post("/admin/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    return r.json()["mfa_ticket"]


def verify(ticket: str, code: str):
    return c.post("/admin/auth/mfa/verify", json={"mfa_ticket": ticket, "code": code})


def first_login(email: str) -> tuple[dict, str]:
    """Enrol MFA and log in; returns (auth header, totp secret)."""
    ticket = ticket_for(email)
    assert verify(ticket, "123456").status_code == 400  # not enrolled yet
    r = c.post("/admin/auth/mfa/enroll", json={"mfa_ticket": ticket})
    assert r.status_code == 200, r.text
    secret = r.json()["secret"]
    assert r.json()["otpauth_uri"].startswith("otpauth://totp/")

    r = verify(ticket, f"{(int(totp(secret)) + 500_000) % 1_000_000:06d}")
    assert r.status_code == 401 and "ERR_AUTH_01" in r.text, r.text

    r = verify(ticket, totp(secret))
    assert r.status_code == 200, r.text
    assert c.post("/admin/auth/mfa/enroll", json={"mfa_ticket": ticket}).status_code == 409  # enrolled now
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, secret


def relogin(email: str, secret: str) -> dict:
    r = verify(ticket_for(email), totp(secret))
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


with SessionLocal() as db:
    city = City(name=f"TestCity-{tag}", state="TestState")
    db.add(city)
    db.flush()
    sa = AdminUser(role="SUPER_ADMIN", full_name="Test SA", email=f"sa-{tag}@test.local",
                   password_hash=hash_password(PW))
    ca = AdminUser(role="CITY_ADMIN", city_id=city.city_id, full_name="Test CA",
                   email=f"ca-{tag}@test.local", password_hash=hash_password(PW))
    db.add_all([sa, ca])
    db.commit()
    sa_id, ca_id, city_id = sa.admin_id, ca.admin_id, city.city_id
    sa_email, ca_email = sa.email, ca.email

created_city_ids: list[str] = []
created_admin_ids: list[str] = []
try:
    # wrong password / unknown email
    assert c.post("/admin/auth/login", json={"email": sa_email, "password": "nope"}).status_code == 401
    assert c.post("/admin/auth/login", json={"email": f"x-{tag}@test.local", "password": PW}).status_code == 401

    # no token / junk token
    assert c.get("/superadmin/city-admins").status_code == 401
    assert c.get("/superadmin/city-admins", headers={"Authorization": "Bearer junk"}).status_code == 401

    sa_h, sa_secret = first_login(sa_email)
    ca_h, _ = first_login(ca_email)

    # FR-69: Super Admin allowed, City Admin forbidden
    assert c.get("/superadmin/city-admins", headers=sa_h).status_code == 200
    assert c.get("/superadmin/city-admins", headers=ca_h).status_code == 403

    # FR-70: second active admin for the same city rejected
    r = c.post("/superadmin/city-admins", headers=sa_h, json={
        "city_id": str(city_id), "full_name": "Dup", "email": f"dup-{tag}@test.local", "password": PW})
    assert r.status_code == 409, r.text

    # cities: Super Admin only, case-insensitive uniqueness, deactivation blocks new City Admins
    assert c.get("/superadmin/cities", headers=ca_h).status_code == 403
    r = c.post("/superadmin/cities", headers=sa_h, json={"name": f"  City2-{tag} ", "state": "TestState"})
    assert r.status_code == 201 and r.json()["name"] == f"City2-{tag}", r.text
    city2_id = r.json()["city_id"]
    created_city_ids.append(city2_id)
    r = c.post("/superadmin/cities", headers=sa_h, json={"name": f"city2-{tag}", "state": "teststate"})
    assert r.status_code == 409, r.text
    r = c.put(f"/superadmin/cities/{city2_id}", headers=sa_h, json={"name": f"testcity-{tag}"})
    assert r.status_code == 409, r.text  # clashes with the first test city
    assert c.put(f"/superadmin/cities/{city2_id}", headers=sa_h, json={"is_active": False}).json()["is_active"] is False
    assert city2_id in [x["city_id"] for x in c.get("/superadmin/cities?is_active=false", headers=sa_h).json()]
    assert c.get(f"/superadmin/cities/{city2_id}", headers=sa_h).status_code == 200
    r = c.post("/superadmin/city-admins", headers=sa_h, json={
        "city_id": city2_id, "full_name": "X", "email": f"x2-{tag}@test.local", "password": PW})
    assert r.status_code == 400, r.text  # city inactive

    assert c.get("/superadmin/audit-logs", headers=ca_h).status_code == 403

    # suspending a City Admin kills their session and blocks login
    assert c.put(f"/superadmin/city-admins/{ca_id}", headers=sa_h, json={"status": "SUSPENDED"}).status_code == 200
    assert c.get("/superadmin/city-admins", headers=ca_h).status_code == 401
    assert c.post("/admin/auth/login", json={"email": ca_email, "password": PW}).status_code == 403

    # FR-86/88: audit entries, filters, CSV
    def audit(**params):
        r = c.get("/superadmin/audit-logs", headers=sa_h, params=params)
        assert r.status_code == 200, r.text
        return r.json()

    page = audit(action="CITY_ADMIN_SUSPEND", city_id=str(city_id))
    assert page["total"] == 1, page
    e = page["items"][0]
    assert e["actor_id"] == str(sa_id) and e["actor_name"] == "Test SA" and e["target_id"] == str(ca_id)
    assert e["before_state"] == {"status": "ACTIVE"} and e["after_state"] == {"status": "SUSPENDED"}, e
    assert e["city_name"] == f"TestCity-{tag}"

    city2 = audit(city_id=city2_id)["items"]  # newest first; the 409 create/rename attempts left no entries
    assert [x["action"] for x in city2] == ["CITY_UPDATE", "CITY_CREATE"], city2
    assert city2[0]["before_state"] == {"is_active": True} and city2[0]["after_state"] == {"is_active": False}
    assert audit(actor_id=str(sa_id), limit=1)["total"] == 3
    assert audit(actor_id=str(sa_id), date_to="2026-01-01")["total"] == 0

    r = c.get("/superadmin/audit-logs/export.csv", headers=sa_h, params={"actor_id": str(sa_id)})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv"), r.text
    lines = r.content.decode("utf-8-sig").splitlines()
    assert lines[0].startswith("occurred_at,") and len(lines) == 4 and "CITY_ADMIN_SUSPEND" in lines[1], lines

    # FR-87: append-only, even straight in the DB
    with SessionLocal() as db:
        try:
            db.execute(text("UPDATE samaj.audit_log SET action = 'X' WHERE actor_id = :a"), {"a": sa_id})
            raise AssertionError("audit_log UPDATE should be refused")
        except DBAPIError as exc:
            assert "append-only" in str(exc), exc

    # City Admin lifecycle; the first one is suspended, so the city takes a new active admin
    r = c.post("/superadmin/city-admins", headers=sa_h, json={
        "city_id": str(city_id), "full_name": "New CA", "email": f"new-{tag}@test.local", "password": PW})
    assert r.status_code == 201, r.text
    new = r.json()
    new_id, new_email = new["admin_id"], new["email"]
    created_admin_ids.append(new_id)
    assert new["status"] == "ACTIVE" and new["mfa_enrolled_at"] is None and "password_hash" not in new, new

    assert c.get(f"/superadmin/city-admins/{new_id}", headers=sa_h).json()["email"] == new_email
    assert c.get(f"/superadmin/city-admins/{uuid4()}", headers=sa_h).status_code == 404
    assert c.get(f"/superadmin/city-admins/{sa_id}", headers=sa_h).status_code == 404  # Super Admin isn't one

    ids = lambda q: {x["admin_id"] for x in c.get(f"/superadmin/city-admins?{q}", headers=sa_h).json()}
    assert ids(f"city_id={city_id}") == {str(ca_id), new_id}
    assert ids(f"city_id={city_id}&status=ACTIVE") == {new_id}
    assert ids(f"city_id={city_id}&status=SUSPENDED") == {str(ca_id)}
    assert c.get("/superadmin/city-admins?status=BOGUS", headers=sa_h).status_code == 422

    # FR-70 on reactivation: the city already has an active admin
    r = c.put(f"/superadmin/city-admins/{ca_id}", headers=sa_h, json={"status": "ACTIVE"})
    assert r.status_code == 409, r.text

    # name/email edit
    assert c.put(f"/superadmin/city-admins/{new_id}", headers=sa_h, json={"email": sa_email}).status_code == 409
    new_email = f"renamed-{tag}@test.local"
    r = c.put(f"/superadmin/city-admins/{new_id}", headers=sa_h, json={"full_name": "Renamed CA", "email": new_email})
    assert r.status_code == 200 and r.json()["full_name"] == "Renamed CA", r.text

    # FR-74: MFA reset logs the admin out and lets them enrol a fresh secret
    new_h, old_secret = first_login(new_email)
    assert c.get("/superadmin/cities", headers=new_h).status_code == 403  # logged in, but not a Super Admin
    r = c.post(f"/superadmin/city-admins/{new_id}/reset-mfa", headers=sa_h)
    assert r.status_code == 200 and r.json()["mfa_enrolled_at"] is None, r.text
    assert c.get("/superadmin/cities", headers=new_h).status_code == 401  # session revoked
    r = c.post("/admin/auth/login", json={"email": new_email, "password": PW})
    assert r.json()["mfa_enrolled"] is False, r.text
    new_h, new_secret = first_login(new_email)
    assert new_secret != old_secret

    # password reset logs them out; old password stops working
    new_pw = "another-password-456"
    r = c.post(f"/superadmin/city-admins/{new_id}/reset-password", headers=sa_h, json={"new_password": "short"})
    assert r.status_code == 422, r.text
    r = c.post(f"/superadmin/city-admins/{new_id}/reset-password", headers=sa_h, json={"new_password": new_pw})
    assert r.status_code == 200, r.text
    assert c.get("/superadmin/cities", headers=new_h).status_code == 401
    assert c.post("/admin/auth/login", json={"email": new_email, "password": PW}).status_code == 401
    r = c.post("/admin/auth/login", json={"email": new_email, "password": new_pw})
    assert r.status_code == 200 and r.json()["mfa_enrolled"] is True, r.text

    # deactivation is final
    assert c.put(f"/superadmin/city-admins/{new_id}", headers=sa_h, json={"status": "DEACTIVATED"}).status_code == 200
    for method, path, body in (
        ("put", f"/superadmin/city-admins/{new_id}", {"full_name": "X"}),
        ("put", f"/superadmin/city-admins/{new_id}", {"status": "ACTIVE"}),
        ("post", f"/superadmin/city-admins/{new_id}/reset-mfa", None),
        ("post", f"/superadmin/city-admins/{new_id}/reset-password", {"new_password": new_pw}),
    ):
        r = c.request(method, path, headers=sa_h, json=body)
        assert r.status_code == 400, (path, r.text)

    # every successful change above left exactly one audit entry, oldest last
    trail = [(x["action"], x["before_state"], x["after_state"]) for x in c.get(
        "/superadmin/audit-logs", headers=sa_h, params={"city_id": str(city_id), "limit": 200}).json()["items"]
        if x["target_id"] == new_id]
    assert trail == [
        ("CITY_ADMIN_DEACTIVATE", {"status": "ACTIVE"}, {"status": "DEACTIVATED"}),
        ("ADMIN_PASSWORD_RESET", None, None),
        ("ADMIN_MFA_RESET", None, None),
        ("CITY_ADMIN_UPDATE", {"full_name": "New CA", "email": f"new-{tag}@test.local"},
         {"full_name": "Renamed CA", "email": new_email}),
        ("ROLE_ASSIGN", None, {"role": "CITY_ADMIN", "full_name": "New CA", "email": f"new-{tag}@test.local"}),
    ], trail

    # FR-73: idle past IDLE_TIMEOUT -> 401
    with SessionLocal() as db:
        db.execute(update(AuthSession).where(AuthSession.admin_id == sa_id)
                   .values(last_activity_at=AuthSession.last_activity_at - timedelta(days=5, minutes=1)))
        db.commit()
    r = c.get("/superadmin/city-admins", headers=sa_h)
    assert r.status_code == 401 and "inactivity" in r.text, r.text

    # logout revokes the token
    sa_h = relogin(sa_email, sa_secret)
    assert c.post("/admin/auth/logout", headers=sa_h).status_code == 204
    assert c.get("/superadmin/city-admins", headers=sa_h).status_code == 401
    print("ok")
finally:
    with SessionLocal() as db:  # auth_session rows go via ON DELETE CASCADE
        extra = [(AdminUser, UUID(i)) for i in created_admin_ids] + [(City, UUID(i)) for i in created_city_ids]
        for model, pk in ((AdminUser, sa_id), (AdminUser, ca_id), *extra, (City, city_id)):
            if obj := db.get(model, pk):
                db.delete(obj)
                db.flush()
        db.commit()
