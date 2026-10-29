import hashlib
from datetime import date
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from core import media, private_files
from core.security import fernet
from core.translit import localized
from member.profile.model import Household, IdentityDocument, Member
from member.profile.schema import MemberUpdate
from superadmin.city.model import City

ID_MAX_BYTES = 2 * 1024 * 1024  # FR-09
IDENTITY_FIELDS = ("full_name", "dob")  # ASM-10: changing these on a verified profile sends it back to review
HOUSEHOLD_FIELDS = ("family_name", "native_place")
PREFERENCE_FIELDS = ("hide_phone", "hide_address", "notify_news", "language")


def age(dob: date | None) -> int | None:
    if dob is None:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def latest_document(db: Session, member_id: UUID) -> IdentityDocument | None:
    return db.scalar(select(IdentityDocument).where(IdentityDocument.member_id == member_id)
                     .order_by(IdentityDocument.created_at.desc()).limit(1))


def to_profile(db: Session, member: Member) -> dict:
    household = db.get(Household, member.household_id) if member.household_id else None
    doc = latest_document(db, member.member_id)
    city = db.get(City, member.city_id)
    return {
        "member_id": member.member_id,
        "full_name": member.full_name,
        "full_name_i18n": member.full_name_i18n,
        "gender": member.gender,
        "dob": member.dob,
        "mobile_last4": member.mobile_last4,
        "mobile": fernet.decrypt(member.mobile_enc).decode() if member.mobile_enc else None,
        "photo_url": media.url(member.photo_key),
        "address": fernet.decrypt(member.address_enc).decode() if member.address_enc else None,
        "city_id": member.city_id,
        "city_name": city.name,
        "city_name_i18n": city.name_i18n,
        "household_id": member.household_id,
        "family_name": household.family_name if household else None,
        "family_name_i18n": household.family_name_i18n if household else {},
        "native_place": household.native_place if household else None,
        "native_place_i18n": household.native_place_i18n if household else {},
        "is_household_head": member.is_household_head,
        "status": member.status,
        "rejection_reason": member.rejection_reason,
        "hide_phone": member.hide_phone,
        "hide_address": member.hide_address,
        "notify_news": member.notify_news,
        "language": member.language,
        "id_document": doc and {"document_id": doc.document_id, "mime_type": doc.mime_type,
                                "size_bytes": doc.size_bytes, "created_at": doc.created_at},
        "created_at": member.created_at,
    }


def _correct(obj, field: str, fix: dict):
    """Merges spelling corrections into the stored translations; a changed English text re-derives the rest first."""
    renamed = inspect(obj).attrs[field].history.has_changes()
    base = localized(getattr(obj, field)) if renamed else getattr(obj, f"{field}_i18n")
    setattr(obj, f"{field}_i18n", {**base, **fix})


def _back_to_review(member: Member):
    # Lands in the City Admin's pending queue again; the last decision stays in reviewed_* and the audit log.
    member.status = "PENDING"
    member.rejection_reason = None


def update_me(db: Session, member: Member, data: MemberUpdate) -> dict:
    """FR-97: a member corrects their own details."""
    changes = data.model_dump(exclude_unset=True)
    fixes = {f: changes.pop(f"{f}_i18n") for f in ("full_name", *HOUSEHOLD_FIELDS) if f"{f}_i18n" in changes}
    household = None
    if any(f in changes or f in fixes for f in HOUSEHOLD_FIELDS):
        if not member.is_household_head or member.household_id is None:
            raise HTTPException(403, "Only the head of the household can change family details")
        household = db.get(Household, member.household_id)
        for f in HOUSEHOLD_FIELDS:
            if f in changes:
                setattr(household, f, changes.pop(f))
    reverify = any(f in changes and changes[f] != getattr(member, f) for f in IDENTITY_FIELDS)
    profile_edit = bool(data.model_fields_set - set(PREFERENCE_FIELDS))
    if "address" in changes:
        member.address_enc = fernet.encrypt(changes.pop("address").encode())
    for f, v in changes.items():
        setattr(member, f, v)
    for f, fix in fixes.items():
        _correct(household if f in HOUSEHOLD_FIELDS else member, f, fix)
    # A rejected member fixes their profile and resubmits; their number can't register again.
    if (member.status == "ACTIVE" and reverify) or (member.status == "REJECTED" and profile_edit):
        _back_to_review(member)
    db.commit()
    return to_profile(db, member)


def upload_photo(db: Session, member: Member, data: bytes) -> dict:
    """Replaces the member's profile photo."""
    if len(data) > ID_MAX_BYTES:
        raise HTTPException(413, "ERR_IMG_UL: The photo is larger than 2 MB. Compress it and upload again.")
    try:
        key = media.save(data)[0]
    except ValueError:
        raise HTTPException(400, "ERR_IMG_UL: Upload the photo as a JPG or PNG image")
    old, member.photo_key = member.photo_key, key
    db.commit()
    if old:
        (media.MEDIA_DIR / old).unlink(missing_ok=True)
    return to_profile(db, member)


def _id_mime(data: bytes) -> str:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    try:
        ext = media.image_info(data)[0]
    except ValueError:
        raise HTTPException(400, "ERR_IMG_UL: Upload the ID as a JPG, PNG or PDF file")
    return {"png": "image/png", "jpg": "image/jpeg"}[ext]


def upload_id_document(db: Session, member: Member, data: bytes) -> dict:
    """FR-09: optional ID for the City Admin's review. A new upload replaces one not yet reviewed."""
    if member.status not in ("PENDING", "REJECTED"):
        raise HTTPException(409, "Your membership is already verified")
    if len(data) > ID_MAX_BYTES:
        raise HTTPException(413, "ERR_IMG_UL: The file is larger than 2 MB. Compress it and upload again.")
    mime = _id_mime(data)
    old = db.scalars(select(IdentityDocument).where(IdentityDocument.member_id == member.member_id,
                                                    IdentityDocument.reviewed_at.is_(None))).all()
    for doc in old:
        db.delete(doc)
    db.add(IdentityDocument(member_id=member.member_id, storage_key=private_files.save(data), mime_type=mime,
                            size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    if member.status == "REJECTED":
        _back_to_review(member)
    db.commit()
    for doc in old:  # files go only once the rows are gone
        private_files.delete(doc.storage_key)
    return to_profile(db, member)
