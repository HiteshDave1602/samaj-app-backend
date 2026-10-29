"""End-to-end member matrimony profile (SF-04) against the dev DB: python test_matrimony.py
Create -> photos -> biodata -> submit -> City Admin moderates -> member sees the outcome. Cleans up after
itself; audit_log rows stay (append-only)."""
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
from member.auth.curd import _start_session, mobile_hash
from member.matrimony.curd import _years_ago
from member.matrimony.model import Biodata, MatrimonyPhoto, MatrimonyProfile
from member.matrimony.schema import BiodataIn, ProfileCard
from member.profile.curd import age
from member.profile.model import Household, Member
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser

c = TestClient(app)
tag = secrets.token_hex(4)
now = datetime.now(timezone.utc)
M = "/member/matrimony"


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def new_member(db, city: City, name: str, status: str) -> tuple[Member, dict]:
    mobile = f"+919{secrets.randbelow(10**9):09d}"
    h = Household(household_id=uuid4(), city_id=city.city_id, family_name=f"{name} family")
    m = Member(member_id=uuid4(), city_id=city.city_id, household_id=h.household_id, is_household_head=True,
               mobile_hash=mobile_hash(mobile), mobile_enc=fernet.encrypt(mobile.encode()), mobile_last4=mobile[-4:],
               full_name=name, gender="FEMALE", dob=date(1998, 5, 1), status=status)
    db.add(h)
    db.flush()
    db.add(m)
    db.flush()
    return m, bearer(_start_session(db, m)["access_token"])


with SessionLocal() as db:
    city = City(name=f"MatCity-{tag}", state="T")
    closed = City(name=f"MatClosed-{tag}", state="T", is_active=False)
    db.add_all([city, closed])
    db.flush()
    ca = AdminUser(role="CITY_ADMIN", city_id=city.city_id, full_name="CA", email=f"mat-{tag}@t.local",
                   password_hash=hash_password(secrets.token_hex(8)))
    db.add(ca)
    db.flush()
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(admin_id=ca.admin_id, refresh_token_hash=hash_token(token), mfa_verified=True,
                       last_activity_at=now, expires_at=now + timedelta(hours=1)))
    _, a_h = new_member(db, city, "Asha", "ACTIVE")
    _, b_h = new_member(db, city, "Bina", "ACTIVE")
    _, p_h = new_member(db, city, "Pari", "PENDING")

    # SF-05 seed: (name, gender, age, education, background, city, profile status, member status)
    city2 = City(name=f"MatCity2-{tag}", state="T")
    db.add(city2)
    db.flush()
    seed = {}
    for name, gender, years, edu, bg, cty, pstatus, mstatus in [
        ("S1", "MALE", 25, "GRADUATE", "JOINT", city, "APPROVED", "ACTIVE"),
        ("S2", "MALE", 30, "POSTGRADUATE", "NUCLEAR", city2, "APPROVED", "ACTIVE"),
        ("S3", "FEMALE", 28, "DOCTORATE", "JOINT", city, "APPROVED", "ACTIVE"),
        ("S4", "MALE", 27, "GRADUATE", "JOINT", city, "APPROVED", "ARCHIVED"),  # member archived: hidden
        ("S5", "MALE", 26, "GRADUATE", "JOINT", city, "PENDING_MODERATION", "ACTIVE"),  # not approved: hidden
    ]:
        m, _ = new_member(db, cty, name, mstatus)
        m.gender, m.dob = gender, _years_ago(years) - timedelta(days=10)
        prof = MatrimonyProfile(profile_id=uuid4(), member_id=m.member_id, location_city_id=cty.city_id,
                                education_level=edu, family_background=bg, status=pstatus)
        db.add(prof)
        db.flush()
        seed[name] = (str(prof.profile_id), gender, years, edu, bg, cty.city_id)
    s1_photos = [MatrimonyPhoto(photo_id=uuid4(), profile_id=seed["S1"][0], storage_key=private_files.save(data),
                                mime_type="image/png", size_bytes=len(data), sort_order=i + 1, status=st)
                 for i, (data, st) in enumerate([(media.png(9, 9), "PENDING"), (media.png(8, 8), "APPROVED")])]
    db.add_all(s1_photos)
    db.commit()
    s1_pending, s1_approved = (str(ph.photo_id) for ph in s1_photos)
    ca_h, city_id, closed_id, admin_id = bearer(token), city.city_id, closed.city_id, ca.admin_id
    city2_id = city2.city_id

PNG = [media.png(400, 500 + i) for i in range(7)]
upload = lambda data, h=a_h: c.post(f"{M}/photos", headers=h, files={"file": ("p", data)})  # noqa: E731
base = {"education_level": "GRADUATE", "family_background": "JOINT", "occupation": "Engineer"}
try:
    # FR-19: Active members only
    assert c.post(f"{M}/profile", headers=p_h, json=base).status_code == 403
    assert c.get(f"{M}/profile", headers=a_h).status_code == 404
    assert c.post(f"{M}/profile", headers=a_h, json=base | {"education_level": "PHD"}).status_code == 422
    assert c.post(f"{M}/profile", headers=a_h, json=base | {"location_city_id": str(closed_id)}).status_code == 400
    r = c.post(f"{M}/profile", headers=a_h, json=base | {"managed_by": "PARENT"})
    assert r.status_code == 201, r.text
    p = r.json()
    assert (p["status"], p["location_city_id"], p["managed_by"], p["full_name"]) == \
        ("DRAFT", str(city_id), "PARENT", "Asha"), p  # FR-21; city defaults to the member's
    assert p["photos"] == [] and p["has_biodata"] is False and p["age"] >= 18, p
    profile_id = p["profile_id"]
    assert c.post(f"{M}/profile", headers=a_h, json=base).status_code == 409

    # partial update; required fields can't be nulled, optional ones can
    r = c.put(f"{M}/profile", headers=a_h, json={"occupation": None, "about": "Loves music"})
    assert r.status_code == 200 and r.json()["occupation"] is None and r.json()["about"] == "Loves music", r.text
    assert c.put(f"{M}/profile", headers=a_h, json={"education_level": None}).status_code == 422

    # submit needs a photo
    assert c.post(f"{M}/profile/submit", headers=a_h).status_code == 400

    # FR-24: JPG/PNG <= 2 MB, ERR_IMG_UL otherwise; max 5, a removed photo frees its slot
    r = upload(b"GIF89a" + bytes(20))
    assert r.status_code == 400 and "ERR_IMG_UL" in r.text, r.text
    r = upload(PNG[0] + bytes(2 * 1024 * 1024))
    assert r.status_code == 413 and "ERR_IMG_UL" in r.text, r.text
    for i in range(5):
        assert upload(PNG[i]).status_code == 201
    assert upload(PNG[5]).status_code == 409
    photos = c.get(f"{M}/profile", headers=a_h).json()["photos"]
    assert [ph["sort_order"] for ph in photos] == [1, 2, 3, 4, 5] and {ph["status"] for ph in photos} == {"PENDING"}
    r = c.delete(f"{M}/photos/{photos[1]['photo_id']}", headers=a_h)
    assert r.status_code == 200 and [ph["sort_order"] for ph in r.json()["photos"]] == [1, 3, 4, 5]
    assert [ph["sort_order"] for ph in upload(PNG[5]).json()["photos"]] == [1, 2, 3, 4, 5]

    # own photo file; anyone else's is a 404
    f = c.get(photos[0]["file_url"], headers=a_h)
    assert f.status_code == 200 and f.content == PNG[0] and f.headers["cache-control"] == "no-store"
    assert c.get(photos[0]["file_url"], headers=b_h).status_code == 404
    assert c.delete(f"{M}/photos/{photos[0]['photo_id']}", headers=b_h).status_code == 404

    # FR-20: biodata, separate and encrypted; PUT replaces it whole
    assert c.get(f"{M}/biodata", headers=a_h).status_code == 404
    assert c.put(f"{M}/biodata", headers=a_h, json={"favourite_colour": "blue"}).status_code == 422
    assert c.put(f"{M}/biodata", headers=a_h, json={"birth_time": "25:00"}).status_code == 422
    bio = {"father_name": "Ramesh Patel", "gotra": "Kashyap", "height_cm": 160, "contact_phone": "98765 43210",
           "contact_email": "asha@example.com", "manglik": "NO"}
    r = c.put(f"{M}/biodata", headers=a_h, json=bio)
    assert r.status_code == 200 and r.json()["contact_phone"] == "+919876543210" and "diet" not in r.json(), r.text
    with SessionLocal() as db:
        row = db.get(Biodata, profile_id)
        assert b"Ramesh" not in row.payload_enc and row.key_id == "fernet-v1" and row.schema_version == 1
    r = c.put(f"{M}/biodata", headers=a_h, json={"father_name": "Ramesh Patel", "diet": "JAIN"})
    assert set(r.json()) == {"father_name", "diet", "updated_at"}, r.json()
    assert c.get(f"{M}/profile", headers=a_h).json()["has_biodata"] is True

    # submit -> City Admin queue; admins never see biodata (FR-36)
    r = c.post(f"{M}/profile/submit", headers=a_h)
    assert r.status_code == 200 and r.json()["status"] == "PENDING_MODERATION", r.text
    assert c.post(f"{M}/profile/submit", headers=a_h).status_code == 409
    queue = c.get("/cityadmin/matrimony/profiles", headers=ca_h, params={"status": "PENDING_MODERATION"}).json()
    assert {i["profile_id"] for i in queue["items"]} == {profile_id, seed["S5"][0]}, queue
    adm = c.get(f"/cityadmin/matrimony/profiles/{profile_id}", headers=ca_h).text
    assert "Ramesh" not in adm and "JAIN" not in adm

    # FR-23: one photo rejected with a reason; profile approved with the rest
    first = photos[0]["photo_id"]
    assert c.post(f"/cityadmin/matrimony/photos/{first}/reject", headers=ca_h,
                  json={"reason": "Sunglasses; face must be visible"}).status_code == 200
    assert c.post(f"/cityadmin/matrimony/profiles/{profile_id}/approve", headers=ca_h).status_code == 200
    p = c.get(f"{M}/profile", headers=a_h).json()
    assert p["status"] == "APPROVED", p
    assert [(ph["status"], ph["rejection_reason"]) for ph in p["photos"]][0] == \
        ("REJECTED", "Sunglasses; face must be visible"), p["photos"]

    # a new photo on an approved profile is reviewed alone; the profile stays approved
    assert c.delete(f"{M}/photos/{first}", headers=a_h).status_code == 200
    p = upload(PNG[6]).json()
    assert p["status"] == "APPROVED" and [ph["status"] for ph in p["photos"]][0] == "PENDING", p
    assert c.post(f"{M}/profile/submit", headers=a_h).status_code == 409

    # rejected profile: member sees the reason, fixes it and resubmits
    c.post(f"{M}/profile", headers=b_h, json=base)
    upload(PNG[0], b_h)
    c.post(f"{M}/profile/submit", headers=b_h)
    b_id = c.get(f"{M}/profile", headers=b_h).json()["profile_id"]
    assert c.post(f"/cityadmin/matrimony/profiles/{b_id}/reject", headers=ca_h,
                  json={"reason": "About text has a phone number"}).status_code == 200
    p = c.get(f"{M}/profile", headers=b_h).json()
    assert (p["status"], p["moderation_reason"]) == ("REJECTED", "About text has a phone number"), p
    p = c.post(f"{M}/profile/submit", headers=b_h).json()
    assert (p["status"], p["moderation_reason"]) == ("PENDING_MODERATION", None), p

    # decision history outlives status changes and deleted photos, newest first
    log = c.get("/cityadmin/matrimony/decisions", headers=ca_h).json()
    assert log["total"] == 3 and all(d["admin_name"] for d in log["items"]), log
    assert [(d["action"], d["full_name"], d["profile_id"], d["reason"]) for d in log["items"]] == [
        ("MATRIMONY_REJECT", "Bina", b_id, "About text has a phone number"),
        ("MATRIMONY_APPROVE", "Asha", profile_id, None),
        ("PHOTO_REJECT", None, None, "Sunglasses; face must be visible"),  # photo deleted by the member
    ], log

    # SF-05 / FR-25: each filter combination returns exactly the expected profiles (Bina searching).
    # Scoped to this test's two cities, so other dev data can't leak in.
    visible = {k: v for k, v in seed.items() if k in ("S1", "S2", "S3")}
    visible["Asha"] = (profile_id, "FEMALE", age(date(1998, 5, 1)), "GRADUATE", "JOINT", city_id)
    by_id = {v[0]: k for k, v in visible.items()}

    def found(h=b_h, **params) -> set[str]:
        r = c.get(f"{M}/profiles", headers=h, params={"city_id": [str(city_id), str(city2_id)]} | params)
        assert r.status_code == 200, r.text
        return {by_id.get(i["profile_id"], i["profile_id"]) for i in r.json()["items"]}

    def expect(age_min=0, age_max=200, gender=None, edu=None, bg=None, cities=None) -> set[str]:
        return {k for k, (_, g, a, e, b, cty) in visible.items()
                if age_min <= a <= age_max and gender in (None, g) and (not edu or e in edu)
                and (not bg or b in bg) and (not cities or cty in cities)}

    assert found() == expect() == {"Asha", "S1", "S2", "S3"}  # S4 (archived), S5 (pending) never
    assert found(age_min=26, age_max=29) == expect(26, 29)
    assert found(age_min=30) == expect(age_min=30) == {"S2"}
    assert found(education_level=["GRADUATE", "POSTGRADUATE"]) == expect(edu={"GRADUATE", "POSTGRADUATE"})
    assert found(city_id=[str(city2_id)]) == {"S2"}
    assert found(family_background="NUCLEAR") == expect(bg={"NUCLEAR"}) == {"S2"}
    assert found(gender="MALE") == expect(gender="MALE") == {"S1", "S2"}
    assert found(age_min=24, age_max=30, education_level="GRADUATE", family_background="JOINT") == \
        expect(24, 30, edu={"GRADUATE"}, bg={"JOINT"})
    assert found(a_h) == {"Asha", "S1", "S2", "S3"}  # your own approved profile shows too
    assert c.get(f"{M}/profiles", headers=b_h, params={"age_min": 30, "age_max": 25}).status_code == 422
    assert c.get(f"{M}/profiles", headers=b_h, params={"education_level": "PHD"}).status_code == 422
    assert c.get(f"{M}/profiles", headers=p_h).status_code == 403

    # keyset paging walks the same set, 2 at a time
    seen, after = [], None
    while True:
        page = c.get(f"{M}/profiles", headers=b_h, params={"city_id": [str(city_id), str(city2_id)], "limit": 2}
                     | ({"after": after} if after else {})).json()
        seen += [i["profile_id"] for i in page["items"]]
        if not (after := page["next_after"]):
            break
    assert len(seen) == 4 and set(seen) == set(by_id), seen

    # FR-26: public summary only, by contract
    card = c.get(f"{M}/profiles", headers=b_h, params={"city_id": str(city2_id)}).json()["items"][0]
    assert set(card) == set(ProfileCard.model_fields), card
    assert not set(card) & set(BiodataIn.model_fields) and "full_name" not in card

    # public detail: approved photos only; hidden profiles are 404
    s1 = c.get(f"{M}/profiles/{seed['S1'][0]}", headers=b_h).json()
    assert [ph["photo_id"] for ph in s1["photos"]] == [s1_approved], s1
    assert s1["cover_photo_url"] == f"{M}/photos/{s1_approved}/file", s1
    assert c.get(f"{M}/photos/{s1_approved}/file", headers=b_h).content == media.png(8, 8)
    assert c.get(f"{M}/photos/{s1_pending}/file", headers=b_h).status_code == 404
    for hidden in ("S4", "S5"):
        assert c.get(f"{M}/profiles/{seed[hidden][0]}", headers=b_h).status_code == 404
    print("ok")
finally:
    with SessionLocal() as db:  # biodata and photos go with the profile (CASCADE); auth_session with the member
        cities = [city_id, city2_id]
        members = select(Member.member_id).where(Member.city_id.in_(cities))
        profiles = select(MatrimonyProfile.profile_id).where(MatrimonyProfile.member_id.in_(members))
        for key in db.scalars(select(MatrimonyPhoto.storage_key).where(MatrimonyPhoto.profile_id.in_(profiles))):
            private_files.delete(key)
        db.execute(delete(MatrimonyProfile).where(MatrimonyProfile.member_id.in_(members)))
        db.execute(delete(Member).where(Member.city_id.in_(cities)))
        db.execute(delete(Household).where(Household.city_id.in_(cities)))
        db.execute(delete(AdminUser).where(AdminUser.admin_id == admin_id))
        db.execute(delete(City).where(City.city_id.in_(cities + [closed_id])))
        db.commit()
