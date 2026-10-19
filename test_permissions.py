"""FR-69 role-permission matrix against the dev DB: python test_permissions.py
Calls every API route as anonymous, Super Admin, City Admin and member, and checks each is refused
unless the route's policy allows that role. A new route fails here until it is added to policy().
Creates a city, two admins and a member, then deletes them."""
import re
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete

from auth.curd import hash_token
from auth.model import AuthSession
from core.database import SessionLocal
from core.security import fernet, hash_password
from main import app
from member.auth.curd import _start_session, mobile_hash
from member.profile.model import Member
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser

c = TestClient(app)
tag = secrets.token_hex(4)


def policy(path: str) -> str:
    if path.startswith("/superadmin/"):
        return "SUPER_ADMIN"
    if path.startswith("/cityadmin/"):
        return "CITY_ADMIN"
    if path in ("/admin/auth/me", "/admin/auth/logout"):
        return "ANY_ADMIN"
    if path == "/health" or path.startswith(("/admin/auth/", "/member/auth/")):
        return "PUBLIC"
    if path.startswith("/member/"):
        return "MEMBER"
    raise AssertionError(f"{path}: add it to policy() in test_permissions.py")


# Routes where an allowed role still gets 403 for an object it has no right to (here: no accepted biodata
# request with that profile, FR-35). Role checks on them are still enforced below.
OBJECT_LEVEL_403 = {"/member/matrimony/profiles/{profile_id}/biodata"}


def admin_session(db, admin: AdminUser) -> dict:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    db.add(AuthSession(admin_id=admin.admin_id, refresh_token_hash=hash_token(token), mfa_verified=True,
                       last_activity_at=now, expires_at=now + timedelta(hours=1)))
    return {"Authorization": f"Bearer {token}"}


with SessionLocal() as db:
    city = City(name=f"Perm-{tag}", state="T")
    db.add(city)
    db.flush()
    pw = hash_password(secrets.token_hex(8))
    sa = AdminUser(role="SUPER_ADMIN", full_name="SA", email=f"psa-{tag}@t.local", password_hash=pw)
    ca = AdminUser(role="CITY_ADMIN", city_id=city.city_id, full_name="CA", email=f"pca-{tag}@t.local",
                   password_hash=pw)
    mobile = f"+919{secrets.randbelow(10**9):09d}"
    m = Member(city_id=city.city_id, mobile_hash=mobile_hash(mobile), mobile_enc=fernet.encrypt(mobile.encode()),
               mobile_last4=mobile[-4:], full_name="M", gender="MALE", status="ACTIVE")
    db.add_all([sa, ca, m])
    db.flush()
    callers = {"SUPER_ADMIN": admin_session(db, sa), "CITY_ADMIN": admin_session(db, ca)}
    db.commit()
    callers["MEMBER"] = {"Authorization": f"Bearer {_start_session(db, m)['access_token']}"}
    callers["ANON"] = {}
    city_id, ca_id, admin_ids = city.city_id, ca.admin_id, [sa.admin_id, ca.admin_id]

try:
    checked = 0
    # The OpenAPI schema lists every route (app.routes nests included routers in this FastAPI version).
    for route_path, methods in app.openapi()["paths"].items():
        rule = policy(route_path)
        if rule == "PUBLIC":
            continue
        path = re.sub(r"\{[^}]+}", str(uuid4()), route_path)  # every path param is a UUID
        for method in methods:
            for who, headers in callers.items():
                allowed = who == rule or (rule == "ANY_ADMIN" and who.endswith("_ADMIN"))
                if allowed and route_path == "/admin/auth/logout":
                    continue  # would end the session the rest of the matrix uses
                # Random ids and an empty body: an allowed caller gets 200/404/422, never a write.
                status = c.request(method, path, headers=headers, json={}).status_code
                if allowed:
                    refused = (401,) if route_path in OBJECT_LEVEL_403 else (401, 403)
                    assert status not in refused, (method, route_path, who, status)
                else:
                    expected = 403 if who.endswith("_ADMIN") and rule != "MEMBER" else 401
                    assert status == expected, (method, route_path, who, status, expected)
                checked += 1
    assert checked > 50, checked

    # who am I: role and city for the dashboard
    me = c.get("/admin/auth/me", headers=callers["CITY_ADMIN"]).json()
    assert me == {"admin_id": str(ca_id), "role": "CITY_ADMIN", "full_name": "CA", "email": f"pca-{tag}@t.local",
                  "city_id": str(city_id), "city_name": f"Perm-{tag}"}, me
    me = c.get("/admin/auth/me", headers=callers["SUPER_ADMIN"]).json()
    assert me["role"] == "SUPER_ADMIN" and me["city_id"] is None and me["city_name"] is None, me
    print(f"ok ({checked} calls)")
finally:
    with SessionLocal() as db:  # auth_session rows go via ON DELETE CASCADE
        db.execute(delete(Member).where(Member.city_id == city_id))
        db.execute(delete(AdminUser).where(AdminUser.admin_id.in_(admin_ids)))
        db.execute(delete(City).where(City.city_id == city_id))
        db.commit()
