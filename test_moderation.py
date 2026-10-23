"""End-to-end City Admin moderation check against the dev DB: python test_moderation.py
ID documents (FR-09/10), family additions (SF-03), matrimony photo moderation (SF-04) and the
security_event log of denied cross-city access. Creates two cities, admins, members and requests, then
deletes them. audit_log and security_event rows stay: both tables are append-only by design."""
import secrets
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from auth.curd import hash_token
from auth.model import AuthSession
from core import media, private_files
from core.database import SessionLocal
from core.security import fernet, hash_password
from main import app
from member.auth.curd import mobile_hash
from member.matrimony.model import MatrimonyPhoto, MatrimonyProfile
from member.profile.model import FamilyMember, Household, IdentityDocument, Member
from superadmin.audit_log.model import SecurityEvent
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser

c = TestClient(app)
tag = secrets.token_hex(4)
now = datetime.now(timezone.utc)
keys: list[str] = []


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def admin_session(db, admin: AdminUser) -> dict:
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(admin_id=admin.admin_id, refresh_token_hash=hash_token(token), mfa_verified=True,
                       last_activity_at=now, expires_at=now + timedelta(hours=1)))
    return bearer(token)


def stored(data: bytes) -> str:
    keys.append(private_files.save(data))
    return keys[-1]


def member(db, city: City, name: str, status: str = "ACTIVE") -> Member:
    mobile = f"+919{secrets.randbelow(10**9):09d}"
    h = Household(household_id=uuid4(), city_id=city.city_id, family_name=f"{name} family")
    m = Member(member_id=uuid4(), city_id=city.city_id, household_id=h.household_id, is_household_head=True,
               mobile_hash=mobile_hash(mobile), mobile_enc=fernet.encrypt(mobile.encode()), mobile_last4=mobile[-4:],
               full_name=name, gender="FEMALE", dob=date(1998, 5, 1), status=status)
    db.add(h)
    db.flush()
    db.add(m)
    db.flush()
    return m


ID_PDF = b"%PDF-1.4 test id"
PHOTOS = [media.png(400, 500 + i) for i in range(4)]

with SessionLocal() as db:
    city_x, city_y = City(name=f"MX-{tag}", state="T"), City(name=f"MY-{tag}", state="T")
    db.add_all([city_x, city_y])
    db.flush()
    pw = hash_password(secrets.token_hex(8))
    sa = AdminUser(role="SUPER_ADMIN", full_name="SA", email=f"msa-{tag}@t.local", password_hash=pw)
    ca_x = AdminUser(role="CITY_ADMIN", city_id=city_x.city_id, full_name="CA X", email=f"mx-{tag}@t.local",
                     password_hash=pw)
    ca_y = AdminUser(role="CITY_ADMIN", city_id=city_y.city_id, full_name="CA Y", email=f"my-{tag}@t.local",
                     password_hash=pw)
    db.add_all([sa, ca_x, ca_y])
    db.flush()
    sa_h, x_h, y_h = admin_session(db, sa), admin_session(db, ca_x), admin_session(db, ca_y)
    mx, my, px = member(db, city_x, "Asha"), member(db, city_y, "Yamini"), member(db, city_x, "Pending P", "PENDING")
    db.add(IdentityDocument(member_id=px.member_id, storage_key=stored(ID_PDF), mime_type="application/pdf",
                            size_bytes=len(ID_PDF), sha256="0" * 64))
    fams = [FamilyMember(family_member_id=uuid4(), household_id=hh, requested_by_member_id=req, full_name=n,
                         relationship="SON", gender="MALE", dob=date(2015, 1, 1), created_at=now - timedelta(hours=h))
            for hh, req, n, h in [(mx.household_id, mx.member_id, "Fam One", 3),
                                  (mx.household_id, mx.member_id, "Fam Two", 2),
                                  (my.household_id, my.member_id, "Fam Y", 1)]]
    db.add_all(fams)
    profiles = {m.member_id: MatrimonyProfile(profile_id=uuid4(), member_id=m.member_id, location_city_id=m.city_id,
                                              education_level="GRADUATE", family_background="JOINT",
                                              status="PENDING_MODERATION", managed_by="PARENT")
                for m in (mx, my)}
    db.add_all(profiles.values())
    db.flush()
    px_id = profiles[mx.member_id].profile_id
    photos = [MatrimonyPhoto(photo_id=uuid4(), profile_id=px_id, storage_key=stored(PHOTOS[i]), mime_type="image/png",
                             size_bytes=len(PHOTOS[i]), sort_order=i + 1) for i in range(3)]
    db.add_all(photos)
    db.commit()
    py_id = profiles[my.member_id].profile_id
    ids = {k: str(v) for k, v in dict(mx=mx.member_id, my=my.member_id, px=px.member_id, f1=fams[0].family_member_id,
                                      f2=fams[1].family_member_id, fy=fams[2].family_member_id, prof_x=px_id,
                                      prof_y=py_id, ph1=photos[0].photo_id, ph2=photos[1].photo_id,
                                      ph3=photos[2].photo_id).items()}
    city_ids, admin_ids = [city_x.city_id, city_y.city_id], [sa.admin_id, ca_x.admin_id, ca_y.admin_id]
    ca_x_id, ca_y_id = str(ca_x.admin_id), ca_y.admin_id

try:
    # FR-10: ID document, own city only; a denied attempt is 403 and logged
    m = "/cityadmin/members"
    d = c.get(f"{m}/{ids['px']}", headers=x_h).json()
    assert d["id_document"]["mime_type"] == "application/pdf" and d["id_document"]["size_bytes"] == len(ID_PDF), d
    r = c.get(f"{m}/{ids['px']}/id-document", headers=x_h)
    assert r.status_code == 200 and r.content == ID_PDF and r.headers["content-type"] == "application/pdf", r.text
    assert r.headers["cache-control"] == "no-store"
    assert c.get(f"{m}/{ids['px']}/id-document", headers=y_h).status_code == 403
    assert c.get(f"{m}/{ids['mx']}/id-document", headers=x_h).status_code == 404  # none uploaded
    assert c.get(f"{m}/{ids['mx']}", headers=x_h).json()["id_document"] is None
    assert c.get(f"{m}/{ids['px']}", headers=y_h).status_code == 403  # plain cross-city
    assert c.post(f"{m}/{ids['px']}/approve", headers=x_h).status_code == 200
    with SessionLocal() as db:  # the decision marks the ID as reviewed
        doc = db.scalar(select(IdentityDocument).where(IdentityDocument.member_id == px.member_id))
        assert str(doc.reviewed_by_admin_id) == ca_x_id and doc.reviewed_at is not None

    # SF-03: family additions, PENDING queue by default, own city, oldest first
    f = "/cityadmin/family-additions"
    names = lambda h=x_h, **p: [i["full_name"] for i in c.get(f, headers=h, params=p).json()["items"]]
    assert names() == ["Fam One", "Fam Two"] and names(y_h) == ["Fam Y"]
    one = c.get(f"{f}/{ids['f1']}", headers=x_h).json()
    assert (one["family_name"], one["requested_by_name"], one["relationship"]) == ("Asha family", "Asha", "SON"), one
    r = c.post(f"{f}/{ids['f1']}/approve", headers=x_h)
    assert r.status_code == 200 and r.json()["status"] == "APPROVED" and r.json()["reviewed_by_admin_id"] == ca_x_id
    assert c.post(f"{f}/{ids['f1']}/approve", headers=x_h).status_code == 409
    assert c.post(f"{f}/{ids['f2']}/reject", headers=x_h, json={"reason": " "}).status_code == 422
    r = c.post(f"{f}/{ids['f2']}/reject", headers=x_h, json={"reason": "Not part of this household"})
    assert r.status_code == 200 and r.json()["rejection_reason"] == "Not part of this household", r.text
    assert names() == [] and names(status="APPROVED") == ["Fam One"] and names(status="REJECTED") == ["Fam Two"]
    assert c.post(f"{f}/{ids['fy']}/approve", headers=x_h).status_code == 403
    assert c.get(f"{f}/{uuid4()}", headers=x_h).status_code == 404
    assert c.get(f, headers=x_h, params={"status": "BOGUS"}).status_code == 422

    # SF-04: matrimony queue, own city; public summary only, never biodata (FR-36)
    mt = "/cityadmin/matrimony"
    queue = c.get(f"{mt}/profiles", headers=x_h, params={"status": "PENDING_MODERATION"}).json()
    assert [p["profile_id"] for p in queue["items"]] == [ids["prof_x"]], queue
    assert queue["items"][0]["pending_photo_count"] == 3 and queue["items"][0]["managed_by"] == "PARENT"
    prof = c.get(f"{mt}/profiles/{ids['prof_x']}", headers=x_h).json()
    assert [p["sort_order"] for p in prof["photos"]] == [1, 2, 3] and "biodata" not in str(prof).lower(), prof
    assert prof["age"] == date.today().year - 1998 - (date.today() < date(date.today().year, 5, 1))
    r = c.get(prof["photos"][0]["file_url"], headers=x_h)
    assert r.status_code == 200 and r.content == PHOTOS[0] and r.headers["content-type"] == "image/png"
    assert c.get(prof["photos"][0]["file_url"], headers=y_h).status_code == 403
    assert c.get(f"{mt}/profiles/{ids['prof_x']}", headers=y_h).status_code == 403

    # FR-23: reject one photo with a reason, then approve the profile with the rest
    r = c.post(f"{mt}/photos/{ids['ph2']}/reject", headers=x_h, json={"reason": "Group photo; show only the candidate"})
    assert r.status_code == 200 and [p["status"] for p in r.json()["photos"]] == ["PENDING", "REJECTED", "PENDING"]
    assert c.post(f"{mt}/photos/{ids['ph2']}/approve", headers=x_h).status_code == 409
    r = c.post(f"{mt}/profiles/{ids['prof_x']}/approve", headers=x_h)
    assert r.status_code == 200 and r.json()["status"] == "APPROVED", r.text
    assert [p["status"] for p in r.json()["photos"]] == ["APPROVED", "REJECTED", "APPROVED"]
    assert r.json()["photos"][1]["rejection_reason"] == "Group photo; show only the candidate"
    assert c.post(f"{mt}/profiles/{ids['prof_x']}/approve", headers=x_h).status_code == 409
    assert c.get(f"{mt}/profiles", headers=x_h, params={"pending_photos": True}).json()["total"] == 0

    # a new photo on an approved profile goes back through moderation on its own
    with SessionLocal() as db:
        new_photo = MatrimonyPhoto(profile_id=px_id, storage_key=stored(PHOTOS[3]), mime_type="image/png",
                                   size_bytes=len(PHOTOS[3]), sort_order=4)
        db.add(new_photo)
        db.commit()
        ph4 = str(new_photo.photo_id)
    pending = c.get(f"{mt}/profiles", headers=x_h, params={"pending_photos": True}).json()["items"]
    assert [(p["profile_id"], p["status"], p["pending_photo_count"]) for p in pending] == [(ids["prof_x"], "APPROVED", 1)]
    r = c.post(f"{mt}/photos/{ph4}/approve", headers=x_h)
    assert r.status_code == 200 and r.json()["photos"][3]["status"] == "APPROVED"
    assert c.post(f"{mt}/photos/{ph4}/approve", headers=y_h).status_code == 403

    # City Y rejects its own profile; reason required
    assert c.post(f"{mt}/profiles/{ids['prof_y']}/reject", headers=y_h, json={}).status_code == 422
    r = c.post(f"{mt}/profiles/{ids['prof_y']}/reject", headers=y_h, json={"reason": "Photo is not of the candidate"})
    assert r.status_code == 200 and r.json()["status"] == "REJECTED" and r.json()["photos"] == [], r.text
    assert c.post(f"{mt}/profiles/{ids['prof_x']}/reject", headers=y_h, json={"reason": "x"}).status_code == 403
    assert c.get(f"{mt}/profiles", headers=y_h).json()["total"] == 1

    # FR-86: every decision audited under City Admin X
    actions = sorted(e["action"] for e in c.get("/superadmin/audit-logs", headers=sa_h,
                                                params={"actor_id": ca_x_id, "limit": 200}).json()["items"])
    assert actions == ["FAMILY_APPROVE", "FAMILY_REJECT", "MATRIMONY_APPROVE", "MEMBER_APPROVE", "PHOTO_APPROVE",
                       "PHOTO_REJECT"], actions

    # every cross-city 403 by City Admin Y is in security_event, with endpoint and target
    with SessionLocal() as db:
        events = db.execute(select(SecurityEvent.event_type, SecurityEvent.endpoint, SecurityEvent.target_id)
                            .where(SecurityEvent.actor_id == ca_y_id)).all()
    assert ("ID_DOC_DENIED", f"GET {m}/{ids['px']}/id-document", ids["px"]) in events, events
    assert ("CROSS_CITY_DENIED", f"GET {m}/{ids['px']}", ids["px"]) in events
    assert ("CROSS_CITY_DENIED", f"POST {mt}/photos/{ph4}/approve", ids["prof_x"]) in events  # target: its profile
    assert len(events) == 6, events  # id-document, member, photo file, profile, photo approve, profile reject
    print("ok")
finally:
    with SessionLocal() as db:  # FK order; auth_session, photos and ID documents go via ON DELETE CASCADE
        member_ids = select(Member.member_id).where(Member.city_id.in_(city_ids))
        db.execute(delete(MatrimonyProfile).where(MatrimonyProfile.member_id.in_(member_ids)))
        db.execute(delete(FamilyMember).where(FamilyMember.requested_by_member_id.in_(member_ids)))
        db.execute(delete(Member).where(Member.city_id.in_(city_ids)))
        db.execute(delete(Household).where(Household.city_id.in_(city_ids)))
        db.execute(delete(AdminUser).where(AdminUser.admin_id.in_(admin_ids)))
        db.execute(delete(City).where(City.city_id.in_(city_ids)))
        db.commit()
    for key in keys:
        private_files.delete(key)
