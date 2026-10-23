"""Empty-input sweep against the dev DB: python test_empty_values.py
Calls every API route, as a role allowed to use it, with empty input: no body, {}, every field null,
every field "", every query param "". Fails on any 5xx; prints writes that accepted empty input.
Creates a city, two admins and a member (same setup as test_permissions.py), then deletes them."""
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

c = TestClient(app, raise_server_exceptions=False)  # a crash is a 500 to record, not an abort
tag = secrets.token_hex(4)
spec = app.openapi()


def role(path: str) -> str:
    if path.startswith("/superadmin/"):
        return "SUPER_ADMIN"
    if path.startswith(("/cityadmin/", "/admin/auth/me", "/admin/auth/logout")):
        return "CITY_ADMIN"
    if path.startswith("/member/") and not path.startswith("/member/auth/"):
        return "MEMBER"
    return "ANON"


def body_fields(op: dict) -> tuple[str | None, list[str]]:
    """(content type, top-level field names) of the operation's request body."""
    content = op.get("requestBody", {}).get("content", {})
    for ctype, media in content.items():
        schema = media.get("schema", {})
        if "$ref" in schema:
            schema = spec["components"]["schemas"][schema["$ref"].rsplit("/", 1)[1]]
        return ctype, list(schema.get("properties", {}))
    return None, []


def variants(op: dict):
    ctype, fields = body_fields(op)
    query = {p["name"]: "" for p in op.get("parameters", []) if p["in"] == "query"}
    yield "no body", {}
    if query:
        yield "query ''", {"params": query}
    if ctype == "application/json":
        yield "{}", {"json": {}}
        if fields:
            yield "all null", {"json": dict.fromkeys(fields)}
            yield "all ''", {"json": dict.fromkeys(fields, "")}
    elif ctype:  # multipart / form
        yield "form ''", {"data": dict.fromkeys(fields, "")}


with SessionLocal() as db:
    city = City(name=f"Empty-{tag}", state="T")
    db.add(city)
    db.flush()
    pw = hash_password(secrets.token_hex(8))
    sa = AdminUser(role="SUPER_ADMIN", full_name="SA", email=f"esa-{tag}@t.local", password_hash=pw)
    ca = AdminUser(role="CITY_ADMIN", city_id=city.city_id, full_name="CA", email=f"eca-{tag}@t.local",
                   password_hash=pw)
    mobile = f"+919{secrets.randbelow(10**9):09d}"
    m = Member(city_id=city.city_id, mobile_hash=mobile_hash(mobile), mobile_enc=fernet.encrypt(mobile.encode()),
               mobile_last4=mobile[-4:], full_name="M", gender="MALE", status="ACTIVE")
    db.add_all([sa, ca, m])
    db.flush()
    now = datetime.now(timezone.utc)
    callers = {"ANON": {}}
    for who, admin in (("SUPER_ADMIN", sa), ("CITY_ADMIN", ca)):
        token = secrets.token_urlsafe(32)
        db.add(AuthSession(admin_id=admin.admin_id, refresh_token_hash=hash_token(token), mfa_verified=True,
                           last_activity_at=now, expires_at=now + timedelta(hours=1)))
        callers[who] = {"Authorization": f"Bearer {token}"}
    db.commit()
    callers["MEMBER"] = {"Authorization": f"Bearer {_start_session(db, m)['access_token']}"}
    city_id, admin_ids = city.city_id, [sa.admin_id, ca.admin_id]

crashes, accepted, rows = [], [], []
try:
    for route_path, ops in spec["paths"].items():
        if route_path == "/admin/auth/logout":
            continue  # would end the session the sweep uses
        path = re.sub(r"\{[^}]+}", str(uuid4()), route_path)  # path params: valid but unknown UUIDs
        headers = callers[role(route_path)]
        for method, op in ops.items():
            for label, kw in variants(op):
                r = c.request(method, path, headers=headers, **kw)
                rows.append((r.status_code, method.upper(), route_path, label))
                if r.status_code >= 500:
                    crashes.append((method.upper(), route_path, label, r.text[:200]))
                elif r.status_code < 300 and method != "get":
                    accepted.append((method.upper(), route_path, label, r.text[:120]))

    for row in rows:
        print(*row, sep="\t")
    print(f"\n{len(rows)} calls, {len(crashes)} 5xx, {len(accepted)} writes accepted empty input")
    for a in accepted:
        print("ACCEPTED", *a, sep="\t")
    for x in crashes:
        print("CRASH", *x, sep="\t")
    assert not crashes
finally:
    with SessionLocal() as db:  # auth_session rows go via ON DELETE CASCADE
        db.execute(delete(Member).where(Member.city_id == city_id))
        db.execute(delete(AdminUser).where(AdminUser.admin_id.in_(admin_ids)))
        db.execute(delete(City).where(City.city_id == city_id))
        db.commit()
