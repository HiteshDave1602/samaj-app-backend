import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from cryptography.fernet import InvalidToken
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.curd import hash_token
from auth.model import AuthSession
from core import sms
from core.config import settings
from core.security import fernet, hash_password, verify_password
from member.auth.model import OtpChallenge
from member.auth.schema import RegisterIn
from member.profile.model import Consent, Household, Member
from superadmin.city.model import City

OTP_TTL = timedelta(minutes=5)  # FR-03
OTP_MAX_ATTEMPTS = 3  # FR-03
OTP_SENDS_PER_HOUR = 5  # FR-04
ACCESS_TTL_SECONDS = 15 * 60  # NFR-16
REFRESH_TTL = timedelta(days=30)  # NFR-16
TICKET_TTL_SECONDS = 15 * 60  # time to fill the profile form after the OTP
NOTICE_VERSION = "v1"  # bump when the consent notice text changes; the app must show the matching text


def _now() -> datetime:
    return datetime.now(timezone.utc)


def mobile_hash(mobile_e164: str) -> bytes:
    return hmac.digest(settings.mobile_pepper.encode(), mobile_e164.encode(), "sha256")


def _seal(kind: str, **claims) -> str:
    # "t" keeps a registration ticket from being used as an access token, and vice versa.
    return fernet.encrypt(json.dumps({"t": kind, **claims}).encode()).decode()


def _unseal(token: str, kind: str, ttl: int) -> dict:
    try:
        claims = json.loads(fernet.decrypt(token.encode(), ttl=ttl))
    except (InvalidToken, ValueError):
        claims = None
    if not isinstance(claims, dict) or claims.get("t") != kind:
        raise HTTPException(401, "Token is invalid or expired")
    return claims


def _member_by_mobile(db: Session, mh: bytes) -> Member | None:
    return db.scalar(select(Member).where(Member.mobile_hash == mh))


def send_otp(db: Session, mobile: str, ip: str | None) -> dict:
    mh = mobile_hash(mobile)
    now = _now()
    # ponytail: two simultaneous sends can both pass this count; fine for a cost limit of 5/hour.
    sent = db.scalar(select(func.count()).where(
        OtpChallenge.mobile_hash == mh, OtpChallenge.created_at > now - timedelta(hours=1)))
    if sent >= OTP_SENDS_PER_HOUR:
        raise HTTPException(429, "Too many OTP requests for this number. Try again in an hour.")

    registered = _member_by_mobile(db, mh) is not None
    code = f"{secrets.randbelow(10**6):06d}"
    db.add(OtpChallenge(
        mobile_hash=mh,
        purpose="LOGIN" if registered else "REGISTER",
        code_hash=hash_password(code),
        expires_at=now + OTP_TTL,
        request_ip=ip,
    ))
    db.commit()
    sms.send_sms(mobile, f"{code} is your Samaj verification code. It expires in 5 minutes. Do not share it.")
    return {"registered": registered, "expires_in_seconds": int(OTP_TTL.total_seconds())}


def verify_otp(db: Session, mobile: str, code: str) -> dict:
    mh = mobile_hash(mobile)
    # Only the newest code counts; sending a new one retires the old. FOR UPDATE serialises parallel guesses.
    ch = db.scalar(
        select(OtpChallenge)
        .where(OtpChallenge.mobile_hash == mh, OtpChallenge.purpose.in_(("LOGIN", "REGISTER")))
        .order_by(OtpChallenge.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    if ch is None or ch.consumed_at is not None or _now() >= ch.expires_at:
        raise HTTPException(400, "OTP expired. Request a new one.")
    if ch.attempts >= OTP_MAX_ATTEMPTS:
        raise HTTPException(400, "OTP locked after 3 wrong attempts. Request a new one.")
    if not verify_password(code, ch.code_hash):
        ch.attempts += 1
        db.commit()
        left = OTP_MAX_ATTEMPTS - ch.attempts
        raise HTTPException(400, f"Incorrect OTP. {left} attempt(s) left." if left else
                                 "Incorrect OTP. Request a new one.")
    ch.consumed_at = _now()

    member = _member_by_mobile(db, mh)
    if member is None:
        db.commit()
        return {"registered": False, "registration_ticket": _seal("reg", m=mobile)}
    if member.deleted_at is not None:
        db.commit()
        raise HTTPException(403, "This account was deleted. Contact your City Admin to recover it.")
    # ponytail: ARCHIVED members log in as-is; re-approval on return (FR-95) lands with archiving (SF-15).
    return {"registered": True, "session": _start_session(db, member)}


def register(db: Session, data: RegisterIn) -> dict:
    mobile = _unseal(data.registration_ticket, "reg", TICKET_TTL_SECONDS)["m"]
    if data.notice_version != NOTICE_VERSION:
        raise HTTPException(409, "The consent notice has changed. Show the current notice and ask again.")
    city = db.get(City, data.city_id)
    if city is None or not city.is_active:
        raise HTTPException(400, "Select an active city")
    mh = mobile_hash(mobile)
    if _member_by_mobile(db, mh):
        raise HTTPException(409, "Number already registered. Log in instead.")

    # ponytail: every registrant heads a new household; joining an existing one comes with family addition (SF-03).
    household = Household(household_id=uuid4(), city_id=city.city_id,
                          family_name=data.family_name, native_place=data.native_place)
    member = Member(
        member_id=uuid4(),
        city_id=city.city_id,
        household_id=household.household_id,
        is_household_head=True,
        mobile_enc=fernet.encrypt(mobile.encode()),
        mobile_hash=mh,
        mobile_last4=mobile[-4:],
        full_name=data.full_name,
        gender=data.gender,
        dob=data.dob,
        address_enc=fernet.encrypt(data.address.encode()),
    )
    try:
        # Flushed one by one: without relationship()s SQLAlchemy doesn't order inserts by FK.
        for row in (household, member, Consent(member_id=member.member_id, purpose="MEMBERSHIP",
                                               notice_version=NOTICE_VERSION)):
            db.add(row)
            db.flush()
    except IntegrityError:  # same number registered in parallel
        db.rollback()
        raise HTTPException(409, "Number already registered. Log in instead.")
    return _start_session(db, member)  # PENDING members can log in; the app limits them to Panchang and News


def _tokens(sess: AuthSession, member: Member, refresh_token: str) -> dict:
    return {
        "access_token": _seal("access", sid=str(sess.session_id), mid=str(member.member_id)),
        "refresh_token": refresh_token,
        "access_expires_in_seconds": ACCESS_TTL_SECONDS,
        "member_status": member.status,
    }


def _start_session(db: Session, member: Member) -> dict:
    now = _now()
    refresh_token = secrets.token_urlsafe(32)
    sess = AuthSession(session_id=uuid4(), member_id=member.member_id, refresh_token_hash=hash_token(refresh_token),
                       last_activity_at=now, expires_at=now + REFRESH_TTL)
    member.last_login_at = now
    db.add(sess)
    db.commit()
    db.refresh(member)
    return _tokens(sess, member, refresh_token)


def _live_session(db: Session, refresh_token: str) -> AuthSession | None:
    return db.scalar(select(AuthSession).where(
        AuthSession.refresh_token_hash == hash_token(refresh_token),
        AuthSession.member_id.is_not(None),
        AuthSession.revoked_at.is_(None),
    ).with_for_update())


def refresh(db: Session, refresh_token: str) -> dict:
    sess = _live_session(db, refresh_token)
    now = _now()
    if sess is None or now >= sess.expires_at:
        raise HTTPException(401, "Session expired. Log in again.")
    member = db.get(Member, sess.member_id)
    if member.deleted_at is not None:
        sess.revoked_at = now
        db.commit()
        raise HTTPException(401, "Session expired. Log in again.")
    # Rotation: the old refresh token stops working. ponytail: a replayed old token just gets 401;
    # revoking the whole session on replay (security_event TOKEN_REUSE) comes with that table.
    new_token = secrets.token_urlsafe(32)
    sess.refresh_token_hash = hash_token(new_token)
    sess.last_activity_at = now
    sess.expires_at = now + REFRESH_TTL
    db.commit()
    return _tokens(sess, member, new_token)


def logout(db: Session, refresh_token: str):
    # The access token stays valid until it expires (max 15 min); that's the cost of not hitting the DB per request.
    if sess := _live_session(db, refresh_token):
        sess.revoked_at = _now()
    db.commit()


def member_from_access_token(db: Session, token: str) -> Member:
    claims = _unseal(token, "access", ACCESS_TTL_SECONDS)
    member = db.get(Member, UUID(claims["mid"]))
    if member is None or member.deleted_at is not None:
        raise HTTPException(401, "Token is invalid or expired")
    return member
