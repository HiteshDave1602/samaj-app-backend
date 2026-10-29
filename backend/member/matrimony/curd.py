import json
from datetime import date
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core import media, private_files
from core.security import fernet
from member.matrimony.model import Biodata, MatrimonyPhoto, MatrimonyProfile
from member.matrimony.schema import BiodataIn, ProfileCreate, ProfileUpdate
from member.profile.curd import age
from member.profile.model import Member
from superadmin.city.model import City

PHOTO_MAX_BYTES = 2 * 1024 * 1024  # FR-24
MAX_PHOTOS = 5  # DDD: sort_order 1..5
PHOTO_URL = "/member/matrimony/photos/{}/file"
BIODATA_KEY_ID = "fernet-v1"
BIODATA_SCHEMA_VERSION = 1


def own(db: Session, member: Member, lock: bool = False) -> MatrimonyProfile:
    q = select(MatrimonyProfile).where(MatrimonyProfile.member_id == member.member_id)
    profile = db.scalar(q.with_for_update() if lock else q)
    if profile is None:
        raise HTTPException(404, "Create your matrimony profile first")
    return profile


def _check_city(db: Session, city_id: UUID):
    city = db.get(City, city_id)
    if city is None or not city.is_active:
        raise HTTPException(400, "Select an active city")


def my_profile(db: Session, member: Member) -> dict:
    profile = own(db, member)
    photos = db.scalars(select(MatrimonyPhoto).where(MatrimonyPhoto.profile_id == profile.profile_id)
                        .order_by(MatrimonyPhoto.sort_order))
    return {c.name: getattr(profile, c.name) for c in MatrimonyProfile.__table__.columns} | {
        "full_name": member.full_name, "gender": member.gender, "age": age(member.dob),
        "photos": [{"photo_id": ph.photo_id, "sort_order": ph.sort_order, "status": ph.status,
                    "rejection_reason": ph.rejection_reason, "file_url": PHOTO_URL.format(ph.photo_id),
                    "created_at": ph.created_at} for ph in photos],
        "has_biodata": db.get(Biodata, profile.profile_id) is not None,
    }


def create_profile(db: Session, member: Member, data: ProfileCreate) -> dict:
    """FR-19: Active members only. Starts as DRAFT; POST /submit sends it to the City Admin."""
    if db.scalar(select(MatrimonyProfile.profile_id).where(MatrimonyProfile.member_id == member.member_id)):
        raise HTTPException(409, "You already have a matrimony profile")
    values = data.model_dump()
    values["location_city_id"] = values["location_city_id"] or member.city_id
    _check_city(db, values["location_city_id"])
    db.add(MatrimonyProfile(member_id=member.member_id, **values))
    try:
        db.commit()
    except IntegrityError:  # unique member_id: a parallel create got there first
        db.rollback()
        raise HTTPException(409, "You already have a matrimony profile")
    return my_profile(db, member)


def update_profile(db: Session, member: Member, data: ProfileUpdate) -> dict:
    # ponytail: edits to an APPROVED profile stay live (PRD FR-11), so a changed "about" isn't re-reviewed.
    profile = own(db, member, lock=True)
    changes = data.model_dump(exclude_unset=True)
    if "location_city_id" in changes:
        _check_city(db, changes["location_city_id"])
    for f, v in changes.items():
        setattr(profile, f, v)
    db.commit()
    return my_profile(db, member)


def submit(db: Session, member: Member) -> dict:
    """DRAFT or REJECTED -> PENDING_MODERATION. Hidden from search until the City Admin approves (FR-22)."""
    profile = own(db, member, lock=True)
    if profile.status not in ("DRAFT", "REJECTED"):
        raise HTTPException(409, f"Your profile is {profile.status}; there is nothing to submit")
    if not db.scalar(select(MatrimonyPhoto.photo_id).where(MatrimonyPhoto.profile_id == profile.profile_id,
                                                           MatrimonyPhoto.status != "REJECTED")):
        raise HTTPException(400, "Add at least one photo before submitting")
    profile.status, profile.moderation_reason = "PENDING_MODERATION", None
    db.commit()
    return my_profile(db, member)


def upload_photo(db: Session, member: Member, data: bytes) -> dict:
    """FR-24. On an APPROVED profile the new photo waits for review while the approved ones stay visible."""
    profile = own(db, member, lock=True)  # lock: two uploads can't take the same slot
    if len(data) > PHOTO_MAX_BYTES:
        raise HTTPException(413, "ERR_IMG_UL: The photo is larger than 2 MB. Compress it and upload again.")
    try:
        ext = media.image_info(data)[0]
    except ValueError:
        raise HTTPException(400, "ERR_IMG_UL: Upload the photo as a JPG or PNG image")
    used = set(db.scalars(select(MatrimonyPhoto.sort_order).where(MatrimonyPhoto.profile_id == profile.profile_id)))
    free = sorted(set(range(1, MAX_PHOTOS + 1)) - used)
    if not free:
        raise HTTPException(409, f"A profile can have at most {MAX_PHOTOS} photos. Remove one first.")
    db.add(MatrimonyPhoto(profile_id=profile.profile_id, storage_key=private_files.save(data),
                          mime_type={"png": "image/png", "jpg": "image/jpeg"}[ext], size_bytes=len(data),
                          sort_order=free[0]))
    db.commit()
    return my_profile(db, member)


def _searchable():
    # FR-22 / FR-27: approved profiles of active, non-deleted members only. Checked live on every query,
    # so a profile hidden or member archived disappears at once.
    return MatrimonyProfile.status == "APPROVED", Member.status == "ACTIVE", Member.deleted_at.is_(None)


_cover = (select(MatrimonyPhoto.photo_id)
          .where(MatrimonyPhoto.profile_id == MatrimonyProfile.profile_id, MatrimonyPhoto.status == "APPROVED")
          .order_by(MatrimonyPhoto.sort_order).limit(1).correlate(MatrimonyProfile).scalar_subquery())


def public_query():
    return (select(MatrimonyProfile, Member.gender, Member.dob, City.name, City.name_i18n, _cover)
            .join(Member, Member.member_id == MatrimonyProfile.member_id)
            .join(City, City.city_id == MatrimonyProfile.location_city_id)
            .where(*_searchable()))


def card(p: MatrimonyProfile, gender: str | None, dob: date | None, city_name: str, city_i18n: dict,
         cover: UUID | None) -> dict:
    return {
        "profile_id": p.profile_id, "gender": gender, "age": age(dob), "education_level": p.education_level,
        "education_detail": p.education_detail, "occupation": p.occupation,
        "family_background": p.family_background, "location_city_id": p.location_city_id,
        "location_city_name": city_name, "location_city_name_i18n": city_i18n, "managed_by": p.managed_by, "about": p.about,
        "cover_photo_url": cover and PHOTO_URL.format(cover),
    }


def _years_ago(n: int) -> date:
    today = date.today()
    try:
        return today.replace(year=today.year - n)
    except ValueError:  # 29 Feb in a non-leap target year
        return today.replace(year=today.year - n, day=28)


def search(db: Session, member: Member, *, age_min: int | None, age_max: int | None, gender: str | None,
           education_level: list[str], city_id: list[UUID], family_background: list[str],
           after: UUID | None, limit: int) -> dict:
    """FR-25: every filter optional, combinable; several values within one filter mean "any of".
    ponytail: live query instead of the DDD's 4-hourly matrimony_search_mv (FR-28 is met with no lag).
    Add the view if search over ~50k profiles drifts past NFR-04's 2 s."""
    q = public_query().where(MatrimonyProfile.member_id != member.member_id)  # FR-27: never your own
    if age_min is not None:
        q = q.where(Member.dob <= _years_ago(age_min))
    if age_max is not None:
        q = q.where(Member.dob > _years_ago(age_max + 1))
    if gender:
        q = q.where(Member.gender == gender)
    if education_level:
        q = q.where(MatrimonyProfile.education_level.in_(education_level))
    if city_id:
        q = q.where(MatrimonyProfile.location_city_id.in_(city_id))
    if family_background:
        q = q.where(MatrimonyProfile.family_background.in_(family_background))
    if after:
        q = q.where(MatrimonyProfile.profile_id > after)
    rows = db.execute(q.order_by(MatrimonyProfile.profile_id).limit(limit + 1)).all()
    items = [card(*r) for r in rows[:limit]]
    return {"items": items, "next_after": items[-1]["profile_id"] if len(rows) > limit else None}


def public_profile(db: Session, profile_id: UUID) -> dict:
    row = db.execute(public_query().where(MatrimonyProfile.profile_id == profile_id)).one_or_none()
    if row is None:
        raise HTTPException(404, "Matrimony profile not found")
    photos = db.scalars(select(MatrimonyPhoto).where(MatrimonyPhoto.profile_id == profile_id,
                                                     MatrimonyPhoto.status == "APPROVED")
                        .order_by(MatrimonyPhoto.sort_order))
    return card(*row) | {"photos": [{"photo_id": ph.photo_id, "sort_order": ph.sort_order,
                                      "file_url": PHOTO_URL.format(ph.photo_id)} for ph in photos]}


def _own_photo(db: Session, member: Member, photo_id: UUID) -> MatrimonyPhoto:
    photo = db.scalar(select(MatrimonyPhoto).join(MatrimonyProfile)
                      .where(MatrimonyPhoto.photo_id == photo_id, MatrimonyProfile.member_id == member.member_id))
    if photo is None:  # someone else's photo is a 404 too, so ids can't be probed
        raise HTTPException(404, "Photo not found")
    return photo


def delete_photo(db: Session, member: Member, photo_id: UUID) -> dict:
    photo = _own_photo(db, member, photo_id)
    key = photo.storage_key
    db.delete(photo)
    db.commit()
    private_files.delete(key)
    return my_profile(db, member)


def photo_file(db: Session, member: Member, photo_id: UUID) -> tuple[bytes, str]:
    """Own photos in any status; anyone else's only when approved on a searchable profile."""
    photo = db.scalar(
        select(MatrimonyPhoto)
        .join(MatrimonyProfile, MatrimonyProfile.profile_id == MatrimonyPhoto.profile_id)
        .join(Member, Member.member_id == MatrimonyProfile.member_id)
        .where(MatrimonyPhoto.photo_id == photo_id,
               or_(MatrimonyProfile.member_id == member.member_id,
                   and_(MatrimonyPhoto.status == "APPROVED", *_searchable()))))
    if photo is None:
        raise HTTPException(404, "Photo not found")
    data = private_files.load(photo.storage_key)
    if data is None:
        raise HTTPException(404, "Photo file not found")
    return data, photo.mime_type


def biodata_of(db: Session, profile_id: UUID) -> dict | None:
    """Decrypted biodata. The only reader: callers must have done the owner / accepted-pair check (FR-35)."""
    row = db.get(Biodata, profile_id)
    return row and json.loads(fernet.decrypt(row.payload_enc)) | {"updated_at": row.updated_at}


def get_biodata(db: Session, member: Member) -> dict:
    data = biodata_of(db, own(db, member).profile_id)
    if data is None:
        raise HTTPException(404, "You haven't added your biodata yet")
    return data


def put_biodata(db: Session, member: Member, data: BiodataIn) -> dict:
    """FR-20: stored apart from the public profile, encrypted. Not moderated: admins never see it (FR-36)."""
    profile = own(db, member, lock=True)
    payload = fernet.encrypt(data.model_dump_json(exclude_none=True).encode())
    row = db.get(Biodata, profile.profile_id)
    if row is None:
        db.add(Biodata(profile_id=profile.profile_id, payload_enc=payload, key_id=BIODATA_KEY_ID,
                       schema_version=BIODATA_SCHEMA_VERSION))
    else:
        row.payload_enc, row.key_id, row.schema_version = payload, BIODATA_KEY_ID, BIODATA_SCHEMA_VERSION
    db.commit()
    return get_biodata(db, member)
