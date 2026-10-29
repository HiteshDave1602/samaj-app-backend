"""End-to-end member registration / OTP login check against the dev DB: python test_member.py
Creates a throwaway city and members, runs SF-01 (FR-01..FR-08), then deletes them."""
import secrets
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update

from core import media, private_files, sms
from core.config import settings
from core.database import SessionLocal
from core.security import fernet
from main import app
from member.auth.curd import NOTICE_VERSION, mobile_hash
from member.auth.model import OtpChallenge
from member.profile.model import Consent, Household, IdentityDocument, Member
from superadmin.city.model import City

c = TestClient(app)
tag = secrets.token_hex(4)
outbox: dict[str, str] = {}
sms.send_sms = lambda mobile, text: outbox.__setitem__(mobile, text.split()[0])  # capture codes, send nothing
settings.otp_bypass = False  # the wrong-code checks below need real verification


def new_mobile() -> str:
    return f"9{secrets.randbelow(10**9):09d}"


def send(mobile: str):
    return c.post("/member/auth/otp/send", json={"mobile": mobile})


def verify(mobile: str, code: str):
    return c.post("/member/auth/otp/verify", json={"mobile": mobile, "code": code})


def otp_for(mobile: str) -> str:
    assert send(mobile).status_code == 200
    return outbox["+91" + mobile[-10:]]


def wrong(code: str) -> str:
    return f"{(int(code) + 1) % 1_000_000:06d}"


with SessionLocal() as db:
    city = City(name=f"MemberCity-{tag}", state="TestState")
    closed = City(name=f"ClosedCity-{tag}", state="TestState", is_active=False)
    db.add_all([city, closed])
    db.commit()
    city_id, closed_id = str(city.city_id), str(closed.city_id)

mobile, flood_mobile = new_mobile(), new_mobile()
e164 = "+91" + mobile
try:
    # mobile validation: spaces/dashes normalised, junk rejected
    for bad in ("12345", "+911234567890", "abcdefghij"):
        assert send(bad).status_code == 422, bad
    r = send(f"{mobile[:5]} {mobile[5:]}")
    assert r.status_code == 200 and r.json() == {"registered": False, "expires_in_seconds": 300}, r.text
    code = outbox[e164]

    # FR-03: 3 wrong attempts lock the code, even the right one after that
    assert "2 attempt(s) left" in verify(mobile, wrong(code)).text
    assert "1 attempt(s) left" in verify(mobile, wrong(code)).text
    assert "Request a new one" in verify(mobile, wrong(code)).text
    r = verify(mobile, code)
    assert r.status_code == 400 and "locked" in r.text, r.text

    # FR-03: expired code
    code = otp_for(mobile)
    with SessionLocal() as db:
        db.execute(update(OtpChallenge).where(OtpChallenge.mobile_hash == mobile_hash(e164))
                   .values(created_at=OtpChallenge.created_at - timedelta(minutes=6),
                           expires_at=OtpChallenge.created_at - timedelta(minutes=1)))  # both use the old value
        db.commit()
    r = verify(mobile, code)
    assert r.status_code == 400 and "expired" in r.text, r.text

    # new number + right code -> registration ticket; a used code can't be replayed
    code = otp_for(mobile)
    r = verify(mobile, code)
    assert r.status_code == 200 and r.json()["registered"] is False and "session" not in r.json(), r.text
    ticket = r.json()["registration_ticket"]
    assert verify(mobile, code).status_code == 400

    profile = {
        "registration_ticket": ticket, "full_name": "Asha Patel", "gender": "FEMALE", "dob": "1998-04-12",
        "city_id": city_id, "address": "12 MG Road, Pune", "family_name": "Patel", "native_place": "Surat",
        "consent": True, "notice_version": NOTICE_VERSION,
    }
    reg = lambda **over: c.post("/member/auth/register", json=profile | over)  # noqa: E731

    # city picker: public, active cities only
    ids = {x["city_id"] for x in c.get("/member/auth/cities").json()}
    assert city_id in ids and closed_id not in ids, ids

    # FR-06/FR-07: mandatory fields, consent, current notice, valid city
    assert reg(full_name="  ").status_code == 422
    assert reg(consent=False).status_code == 422
    assert reg(dob=str(date.today() + timedelta(days=1))).status_code == 422
    assert reg(notice_version="v0").status_code == 409
    assert reg(city_id=closed_id).status_code == 400
    assert reg(registration_ticket="junk").status_code == 401

    # FR-08: registered as PENDING and logged in straight away
    r = reg()
    assert r.status_code == 201 and r.json()["member_status"] == "PENDING", r.text
    tokens = r.json()
    me_h = {"Authorization": f"Bearer {tokens['access_token']}"}
    me = c.get("/member/me", headers=me_h).json()
    assert me["full_name"] == "Asha Patel" and me["status"] == "PENDING" and me["mobile_last4"] == mobile[-4:], me
    assert me["address"] == "12 MG Road, Pune" and me["family_name"] == "Patel" and me["is_household_head"], me
    assert me["city_name"] == f"MemberCity-{tag}", me
    assert me["mobile"] == e164 and me["photo_url"] is None, me
    # names are auto-transliterated on write; a correction sticks until the English name changes
    assert me["full_name_i18n"] == {"gu": "અશા પતેલ", "hi": "अशा पतेल"}, me["full_name_i18n"]
    assert me["family_name_i18n"]["gu"] == "પતેલ" and me["city_name_i18n"]["hi"], me
    me = c.put("/member/me", headers=me_h, json={"full_name_i18n": {"gu": "આશા પટેલ"}}).json()
    assert me["full_name_i18n"] == {"gu": "આશા પટેલ", "hi": "अशा पतेल"}, me["full_name_i18n"]
    assert c.put("/member/me", headers=me_h, json={"full_name_i18n": {"fr": "x"}}).status_code == 422

    # profile photo: JPG/PNG <= 2 MB; a new one replaces the old file
    photo = lambda data: c.put("/member/me/photo", headers=me_h, files={"file": ("p", data)})  # noqa: E731
    assert photo(b"GIF89a" + bytes(20)).status_code == 400
    first = photo(media.png(300, 300)).json()["photo_url"]
    second = photo(media.png(400, 400)).json()["photo_url"]
    assert first != second and c.get(second).status_code == 200 and c.get(first).status_code == 404, (first, second)

    # FR-05: same number can't register twice (ticket replay); send now says "registered"
    assert reg().status_code == 409
    assert send(mobile).json()["registered"] is True

    # FR-97: edit own profile
    patch = lambda **body: c.put("/member/me", headers=me_h, json=body)  # noqa: E731
    assert patch(full_name=None).status_code == 422 and patch(dob="2999-01-01").status_code == 422
    r = patch(address="  7 FC Road, Pune ", native_place=None, family_name="Patel-Shah", hide_phone=True)
    assert r.status_code == 200, r.text
    me = r.json()
    assert (me["address"], me["native_place"], me["family_name"]) == ("7 FC Road, Pune", None, "Patel-Shah"), me
    assert me["hide_phone"] and me["status"] == "PENDING" and me["id_document"] is None, me

    def set_member(**values):
        with SessionLocal() as db:
            db.execute(update(Member).where(Member.mobile_hash == mobile_hash(e164)).values(**values))
            db.commit()

    set_member(is_household_head=False)  # household fields belong to the head
    assert patch(family_name="X").status_code == 403
    set_member(is_household_head=True, status="ACTIVE")
    # ASM-10: preferences, gender or the same name keep ACTIVE; a new name goes back to review
    assert patch(hide_address=True, notify_news=False, gender="FEMALE", full_name="Asha Patel").json()["status"] \
        == "ACTIVE"
    # app language is a preference: saved, validated, never sends the profile to review
    assert me["language"] == "en" and patch(language="fr").status_code == 422 and patch(language=None).status_code == 422
    r = patch(language="gu").json()
    assert r["language"] == "gu" and r["status"] == "ACTIVE", r
    assert patch(full_name="Asha P. Shah").json()["status"] == "PENDING"
    # a rejected member resubmits by editing; a preference toggle alone doesn't resubmit
    set_member(status="REJECTED", rejection_reason="Blurry ID")
    assert patch(hide_phone=False).json()["status"] == "REJECTED"
    me = patch(address="8 FC Road, Pune").json()
    assert me["status"] == "PENDING" and me["rejection_reason"] is None, me

    # FR-09: ID document, JPG/PNG/PDF <= 2 MB, ERR_IMG_UL otherwise; a new upload replaces an unreviewed one
    up = lambda data: c.put("/member/me/id-document", headers=me_h, files={"file": ("id", data)})  # noqa: E731
    r = up(b"GIF89a" + bytes(20))
    assert r.status_code == 400 and "ERR_IMG_UL" in r.text, r.text
    r = up(b"%PDF-1.4" + bytes(2 * 1024 * 1024))
    assert r.status_code == 413 and "ERR_IMG_UL" in r.text, r.text
    assert up(b"%PDF-1.4 first").json()["id_document"]["mime_type"] == "application/pdf"
    r = up(media.png(600, 400))
    assert r.status_code == 200 and r.json()["id_document"]["mime_type"] == "image/png", r.text
    with SessionLocal() as db:
        docs = db.scalars(select(IdentityDocument).join(Member).where(Member.mobile_hash == mobile_hash(e164))).all()
        assert len(docs) == 1 and private_files.load(docs[0].storage_key) == media.png(600, 400), docs
    set_member(status="ACTIVE")
    assert up(media.png(600, 400)).status_code == 409
    set_member(status="PENDING")

    # PII at rest: number and address only encrypted / hashed; consent row recorded
    with SessionLocal() as db:
        m = db.scalar(select(Member).where(Member.mobile_hash == mobile_hash(e164)))
        assert fernet.decrypt(m.mobile_enc).decode() == e164 and mobile.encode() not in m.mobile_enc
        assert m.source == "APP" and m.last_login_at is not None
        consent = db.scalar(select(Consent).where(Consent.member_id == m.member_id))
        assert consent.purpose == "MEMBERSHIP" and consent.notice_version == NOTICE_VERSION

    # FR-02: login with OTP
    r = verify(mobile, outbox[e164])
    assert r.status_code == 200 and r.json()["registered"] is True, r.text
    login = r.json()["session"]
    assert login["member_status"] == "PENDING" and "registration_ticket" not in r.json()

    # NFR-16: refresh rotates; the old refresh token dies
    r = c.post("/member/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert r.status_code == 200, r.text
    rotated = r.json()
    assert c.post("/member/auth/refresh", json={"refresh_token": login["refresh_token"]}).status_code == 401
    assert c.get("/member/me", headers={"Authorization": f"Bearer {rotated['access_token']}"}).status_code == 200

    # logout kills the refresh token
    assert c.post("/member/auth/logout", json={"refresh_token": rotated["refresh_token"]}).status_code == 204
    assert c.post("/member/auth/refresh", json={"refresh_token": rotated["refresh_token"]}).status_code == 401

    # token confusion: junk, a registration ticket, or an admin token are not member access tokens
    for bad in ("junk", ticket, secrets.token_urlsafe(32)):
        assert c.get("/member/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401
    assert c.get("/member/me").status_code == 401

    # FR-04: 6th send within an hour -> 429 and no SMS
    for _ in range(5):
        assert send(flood_mobile).status_code == 200
    outbox.clear()
    assert send(flood_mobile).status_code == 429 and not outbox
    print("ok")
finally:
    with SessionLocal() as db:  # auth_session rows go via ON DELETE CASCADE
        hashes = [mobile_hash("+91" + x) for x in (mobile, flood_mobile)]
        ids = list(db.scalars(select(Member.member_id).where(Member.mobile_hash.in_(hashes))))
        for key in db.scalars(select(IdentityDocument.storage_key).where(IdentityDocument.member_id.in_(ids))):
            private_files.delete(key)  # rows go via ON DELETE CASCADE
        db.execute(delete(Consent).where(Consent.member_id.in_(ids)))
        db.execute(delete(Member).where(Member.member_id.in_(ids)))
        db.execute(delete(Household).where(Household.city_id.in_([city_id, closed_id])))
        db.execute(delete(OtpChallenge).where(OtpChallenge.mobile_hash.in_(hashes)))
        db.execute(delete(City).where(City.city_id.in_([city_id, closed_id])))
        db.commit()
