"""Biodata request + privacy suite (SF-06, FR-29-42) against the dev DB: python test_biodata.py
The SRS makes this a release gate: biodata reaches only the two members of an ACCEPTED request -- never a third
member, a City Admin or the Super Admin -- and every denied read is logged. Cleans up after itself;
security_event rows stay (append-only)."""
import secrets
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update

from auth.curd import hash_token
from auth.model import AuthSession
from core.database import SessionLocal
from core.security import fernet, hash_password
from main import app
from member.auth.curd import _start_session, mobile_hash
from member.biodata_request import curd as requests_curd
from member.matrimony.model import BiodataRequest, MatrimonyProfile
from member.profile.model import Household, Member
from superadmin.audit_log.model import SecurityEvent
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser

c = TestClient(app)
tag = secrets.token_hex(4)
now = datetime.now(timezone.utc)
M = "/member/matrimony"


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def admin_session(db, admin: AdminUser) -> dict:
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(admin_id=admin.admin_id, refresh_token_hash=hash_token(token), mfa_verified=True,
                       last_activity_at=now, expires_at=now + timedelta(hours=1)))
    return bearer(token)


def new_member(db, city: City, name: str, profile_status: str | None) -> tuple[Member, dict, str | None]:
    mobile = f"+919{secrets.randbelow(10**9):09d}"
    h = Household(household_id=uuid4(), city_id=city.city_id, family_name=f"{name} family")
    m = Member(member_id=uuid4(), city_id=city.city_id, household_id=h.household_id, is_household_head=True,
               mobile_hash=mobile_hash(mobile), mobile_enc=fernet.encrypt(mobile.encode()), mobile_last4=mobile[-4:],
               full_name=name, gender="FEMALE", dob=date(1997, 1, 1), status="ACTIVE")
    db.add(h)
    db.flush()
    db.add(m)
    db.flush()
    pid = None
    if profile_status:
        p = MatrimonyProfile(profile_id=uuid4(), member_id=m.member_id, location_city_id=city.city_id,
                             education_level="GRADUATE", family_background="JOINT", status=profile_status)
        db.add(p)
        db.flush()
        pid = str(p.profile_id)
    return m, bearer(_start_session(db, m)["access_token"]), pid


with SessionLocal() as db:
    city = City(name=f"BioCity-{tag}", state="T")
    db.add(city)
    db.flush()
    pw = hash_password(secrets.token_hex(8))
    ca = AdminUser(role="CITY_ADMIN", city_id=city.city_id, full_name="CA", email=f"bio-{tag}@t.local", password_hash=pw)
    sa = AdminUser(role="SUPER_ADMIN", full_name="SA", email=f"biosa-{tag}@t.local", password_hash=pw)
    db.add_all([ca, sa])
    db.flush()
    ca_h, sa_h = admin_session(db, ca), admin_session(db, sa)
    ma, a_h, A = new_member(db, city, "Anita", "APPROVED")
    mb, b_h, B = new_member(db, city, "Bhavna", "APPROVED")
    mc, c_h, C = new_member(db, city, "Chitra", "APPROVED")
    _, d_h, _ = new_member(db, city, "Divya", "PENDING_MODERATION")
    _, e_h, _ = new_member(db, city, "Esha", None)  # no matrimony profile
    db.commit()
    city_id, admin_ids = city.city_id, [ca.admin_id, sa.admin_id]
    member_ids = {"A": ma.member_id, "B": mb.member_id, "C": mc.member_id}

# each member's biodata carries a marker that must never appear where it shouldn't
SECRET = {k: f"Secret{k}{tag}" for k in "ABC"}
for k, h in (("A", a_h), ("B", b_h), ("C", c_h)):
    assert c.put(f"{M}/biodata", headers=h, json={"father_name": SECRET[k], "gotra": "Kashyap"}).status_code == 200

bio = lambda h, pid: c.get(f"{M}/profiles/{pid}/biodata", headers=h)  # noqa: E731
send = lambda h, pid: c.post(f"{M}/profiles/{pid}/biodata-request", headers=h)  # noqa: E731
act = lambda h, rid, verb: c.post(f"{M}/biodata-requests/{rid}/{verb}", headers=h)  # noqa: E731
tab = lambda h, box, **p: c.get(f"{M}/biodata-requests", headers=h, params={"box": box} | p).json()  # noqa: E731
denied: list[tuple[str, str]] = []  # (member key, target profile id) of every expected 403


def must_deny(who: str, h: dict, pid: str):
    r = bio(h, pid)
    assert r.status_code == 403 and SECRET["A"] not in r.text and SECRET["B"] not in r.text, (who, r.text)
    denied.append((who, pid))


try:
    # FR-29: who may send
    assert send(d_h, B).status_code == 409  # own profile not approved yet
    assert send(e_h, B).status_code == 404  # no matrimony profile
    assert send(a_h, A).status_code == 400
    assert send(a_h, str(uuid4())).status_code == 404
    r = send(a_h, B)
    assert r.status_code == 201 and (r.json()["status"], r.json()["sent_by_me"]) == ("PENDING", True), r.text
    req = r.json()["request_id"]
    # FR-30: one open request per pair, either direction
    assert send(a_h, B).json()["detail"] == "Request already exists"
    assert send(b_h, A).status_code == 409

    # FR-34: nothing shared while pending -- not even to A or B
    must_deny("A", a_h, B)
    must_deny("B", b_h, A)
    must_deny("C", c_h, A)

    # button state on the public profile, from both sides
    assert c.get(f"{M}/profiles/{B}", headers=a_h).json()["biodata_request"]["sent_by_me"] is True
    st = c.get(f"{M}/profiles/{A}", headers=b_h).json()["biodata_request"]
    assert (st["status"], st["sent_by_me"]) == ("PENDING", False), st
    assert c.get(f"{M}/profiles/{A}", headers=c_h).json()["biodata_request"] is None

    # FR-40: tabs
    sent, received = tab(a_h, "sent"), tab(b_h, "received")
    assert [i["request_id"] for i in sent["items"]] == [req] == [i["request_id"] for i in received["items"]]
    assert received["items"][0]["counterpart_profile_id"] == A and received["items"][0]["counterpart"]["age"]
    assert tab(c_h, "received")["total"] == 0 and tab(a_h, "received")["total"] == 0
    assert tab(e_h, "sent") == {"total": 0, "items": []}

    # FR-32: only B answers; C can't even see it
    assert act(a_h, req, "accept").status_code == 403
    assert act(c_h, req, "accept").status_code == 404

    # FR-33: accept -> mutual access, for exactly these two
    r = act(b_h, req, "accept")
    assert r.status_code == 200 and r.json()["status"] == "ACCEPTED" and r.json()["responded_at"], r.text
    assert act(b_h, req, "accept").status_code == 409
    assert bio(a_h, B).json()["father_name"] == SECRET["B"]
    assert bio(b_h, A).json()["father_name"] == SECRET["A"]
    assert bio(a_h, A).json()["father_name"] == SECRET["A"]  # own, via the same endpoint
    must_deny("C", c_h, A)
    must_deny("C", c_h, B)

    # FR-35 / FR-36: admins never get biodata -- member endpoints refuse admin tokens, admin views omit it
    for h in (ca_h, sa_h):
        assert bio(h, A).status_code == 401 and bio(h, B).status_code == 401
    for path in (f"/cityadmin/matrimony/profiles/{A}", f"/cityadmin/members/{member_ids['A']}",
                 "/cityadmin/matrimony/profiles"):
        r = c.get(path, headers=ca_h)
        assert r.status_code == 200 and SECRET["A"] not in r.text and SECRET["B"] not in r.text, (path, r.text)
    # ... and neither do search or public profiles for anyone
    for h in (a_h, b_h, c_h):
        for r in (c.get(f"{M}/profiles", headers=h, params={"city_id": str(city_id)}),
                  c.get(f"{M}/profiles/{A}", headers=h), c.get(f"{M}/profiles/{B}", headers=h)):
            assert r.status_code == 200 and not any(s in r.text for s in SECRET.values()), r.text

    # FR-41: either side withdraws; access ends for both at once
    assert act(c_h, req, "withdraw").status_code == 404
    r = act(b_h, req, "withdraw")
    assert r.status_code == 200 and r.json()["status"] == "WITHDRAWN" and r.json()["withdrawn_at"], r.text
    assert act(a_h, req, "withdraw").status_code == 409
    must_deny("A", a_h, B)
    must_deny("B", b_h, A)

    # FR-39: decline shares nothing and locks A -> B resends for 30 days (day 29 no, day 31 yes)
    req2 = send(a_h, B).json()["request_id"]
    r = act(b_h, req2, "decline")
    assert r.status_code == 200 and r.json()["status"] == "DECLINED", r.text
    lock = datetime.fromisoformat(r.json()["resend_allowed_at"])
    assert timedelta(days=29, hours=23) < lock - datetime.fromisoformat(r.json()["responded_at"]) <= timedelta(days=30)
    must_deny("A", a_h, B)
    assert tab(a_h, "sent", status="DECLINED")["items"][0]["request_id"] == req2
    r = send(a_h, B)
    assert r.status_code == 409 and "ask again" in r.text, r.text
    with SessionLocal() as db:  # day 29 of 30: still locked
        db.execute(update(BiodataRequest).where(BiodataRequest.request_id == req2)
                   .values(resend_allowed_at=datetime.now(timezone.utc) + timedelta(days=1)))
        db.commit()
    assert send(a_h, B).status_code == 409
    with SessionLocal() as db:  # day 31
        db.execute(update(BiodataRequest).where(BiodataRequest.request_id == req2)
                   .values(resend_allowed_at=datetime.now(timezone.utc) - timedelta(days=1)))
        db.commit()
    assert send(a_h, B).status_code == 201

    # FR-42: daily cap (lowered for the test)
    requests_curd.DAILY_LIMIT, limit = 1, requests_curd.DAILY_LIMIT
    try:
        assert send(c_h, A).status_code == 201
        r = send(c_h, B)
        assert r.status_code == 429 and "a day" in r.text, r.text
    finally:
        requests_curd.DAILY_LIMIT = limit

    # FR-37: every denied read is one security_event row with actor, target, endpoint and time
    with SessionLocal() as db:
        events = db.execute(select(SecurityEvent.actor_id, SecurityEvent.actor_type, SecurityEvent.target_id,
                                   SecurityEvent.endpoint, SecurityEvent.occurred_at)
                            .where(SecurityEvent.event_type == "BIODATA_DENIED",
                                   SecurityEvent.actor_id.in_(member_ids.values()))).all()
    got = sorted((str(a), t, e) for a, kind, t, e, at in events if kind == "MEMBER" and at)
    want = sorted((str(member_ids[w]), pid, f"GET {M}/profiles/{pid}/biodata") for w, pid in denied)
    assert got == want, (got, want)
    print("ok")
finally:
    with SessionLocal() as db:  # requests and biodata go with the profiles (CASCADE)
        members = select(Member.member_id).where(Member.city_id == city_id)
        db.execute(delete(MatrimonyProfile).where(MatrimonyProfile.member_id.in_(members)))
        db.execute(delete(Member).where(Member.city_id == city_id))
        db.execute(delete(Household).where(Household.city_id == city_id))
        db.execute(delete(AdminUser).where(AdminUser.admin_id.in_(admin_ids)))
        db.execute(delete(City).where(City.city_id == city_id))
        db.commit()
