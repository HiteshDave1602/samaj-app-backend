from datetime import datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from member.matrimony import curd as matrimony
from member.matrimony.model import BiodataRequest, MatrimonyProfile
from member.profile.model import Member
from superadmin.audit_log.curd import IST, Denied

RESEND_LOCK = timedelta(days=30)  # FR-39, ASM-08
DAILY_LIMIT = 20  # FR-42, ASM-09: new requests per member per IST calendar day
OPEN = ("PENDING", "ACCEPTED")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def my_profile_id(db: Session, member: Member) -> UUID | None:
    return db.scalar(select(MatrimonyProfile.profile_id).where(MatrimonyProfile.member_id == member.member_id))


def _pair(a: UUID, b: UUID):
    return BiodataRequest.pair_low == func.least(a, b), BiodataRequest.pair_high == func.greatest(a, b)


def latest_between(db: Session, mine: UUID | None, other: UUID) -> dict | None:
    if mine is None:
        return None
    req = db.scalar(select(BiodataRequest).where(*_pair(mine, other))
                    .order_by(BiodataRequest.created_at.desc()).limit(1))
    return req and _state(req, mine)


def _state(req: BiodataRequest, mine: UUID) -> dict:
    return {"request_id": req.request_id, "status": req.status, "sent_by_me": req.requester_profile_id == mine,
            "resend_allowed_at": req.resend_allowed_at}


def _out(req: BiodataRequest, mine: UUID, cards: dict[UUID, dict]) -> dict:
    other = req.recipient_profile_id if req.requester_profile_id == mine else req.requester_profile_id
    return _state(req, mine) | {
        "counterpart_profile_id": other, "counterpart": cards.get(other), "created_at": req.created_at,
        "responded_at": req.responded_at, "withdrawn_at": req.withdrawn_at,
    }


def _cards(db: Session, profile_ids: set[UUID]) -> dict[UUID, dict]:
    rows = db.execute(matrimony.public_query().where(MatrimonyProfile.profile_id.in_(profile_ids)))
    return {r[0].profile_id: matrimony.card(*r) for r in rows}


def send(db: Session, member: Member, profile_id: UUID) -> dict:
    """FR-29: User A asks for User B's biodata from B's profile. Nothing is shared until B accepts."""
    mine = matrimony.own(db, member, lock=True)  # lock: serialises this member's sends for the checks below
    if mine.status != "APPROVED":
        raise HTTPException(409, "Your matrimony profile must be approved before you can send biodata requests")
    if profile_id == mine.profile_id:
        raise HTTPException(400, "You can't send a request to yourself")
    if db.execute(matrimony.public_query().where(MatrimonyProfile.profile_id == profile_id)).first() is None:
        raise HTTPException(404, "Matrimony profile not found")
    pair = _pair(mine.profile_id, profile_id)
    if db.scalar(select(BiodataRequest.request_id).where(*pair, BiodataRequest.status.in_(OPEN))):
        raise HTTPException(409, "Request already exists")  # FR-30, either direction
    locked_until = db.scalar(select(func.max(BiodataRequest.resend_allowed_at)).where(
        BiodataRequest.requester_profile_id == mine.profile_id, BiodataRequest.recipient_profile_id == profile_id,
        BiodataRequest.status == "DECLINED"))
    if locked_until and locked_until > _now():
        raise HTTPException(409, "This member declined your request. You can ask again from "
                                 f"{locked_until.astimezone(IST):%d %b %Y}.")
    today = datetime.combine(_now().astimezone(IST).date(), time(), IST)
    if db.scalar(select(func.count()).where(BiodataRequest.requester_profile_id == mine.profile_id,
                                            BiodataRequest.created_at >= today)) >= DAILY_LIMIT:
        raise HTTPException(429, f"You can send at most {DAILY_LIMIT} biodata requests a day. Try again tomorrow.")
    req = BiodataRequest(requester_profile_id=mine.profile_id, recipient_profile_id=profile_id)
    db.add(req)
    try:
        db.commit()
    except IntegrityError:  # ux_biodata_request_open_pair: B asked A at the same moment
        db.rollback()
        raise HTTPException(409, "Request already exists")
    # ponytail: BIODATA_REQUEST push to User B (FR-31) comes with the notification outbox.
    return _out(req, mine.profile_id, _cards(db, {profile_id}))


def _involving_me(db: Session, member: Member, request_id: UUID) -> tuple[BiodataRequest, UUID]:
    mine = my_profile_id(db, member)
    req = db.get(BiodataRequest, request_id, with_for_update=True)
    if req is None or mine not in (req.requester_profile_id, req.recipient_profile_id):
        raise HTTPException(404, "Request not found")  # other people's requests don't exist for you
    return req, mine


def respond(db: Session, member: Member, request_id: UUID, accept: bool) -> dict:
    """FR-32: only User B answers. Accept grants both sides access (FR-33); decline shares nothing and locks
    resend for 30 days (FR-34, FR-39)."""
    req, mine = _involving_me(db, member, request_id)
    if req.recipient_profile_id != mine:
        raise HTTPException(403, "Only the member who received the request can answer it")
    if req.status != "PENDING":
        raise HTTPException(409, f"This request is already {req.status}")
    req.status, req.responded_at = ("ACCEPTED" if accept else "DECLINED"), _now()
    if not accept:
        req.resend_allowed_at = req.responded_at + RESEND_LOCK
    db.commit()
    # ponytail: BIODATA_RESPONSE push to User A (FR-38) comes with the notification outbox.
    return _out(req, mine, _cards(db, {req.requester_profile_id}))


def withdraw(db: Session, member: Member, request_id: UUID) -> dict:
    """FR-41: either side ends an accepted exchange; access stops for both on the next call."""
    req, mine = _involving_me(db, member, request_id)
    if req.status != "ACCEPTED":
        raise HTTPException(409, "Only an accepted exchange can be withdrawn")
    req.status, req.withdrawn_at, req.withdrawn_by_profile_id = "WITHDRAWN", _now(), mine
    db.commit()
    other = req.recipient_profile_id if req.requester_profile_id == mine else req.requester_profile_id
    return _out(req, mine, _cards(db, {other}))


def list_requests(db: Session, member: Member, box: str, status: str | None, limit: int, offset: int) -> dict:
    """FR-40: Sent and Received tabs, newest first."""
    mine = my_profile_id(db, member)
    if mine is None:
        return {"total": 0, "items": []}
    col = BiodataRequest.requester_profile_id if box == "sent" else BiodataRequest.recipient_profile_id
    q = select(BiodataRequest).where(col == mine)
    if status:
        q = q.where(BiodataRequest.status == status)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    reqs = db.scalars(q.order_by(BiodataRequest.created_at.desc(), BiodataRequest.request_id)
                      .limit(limit).offset(offset)).all()
    cards = _cards(db, {r.recipient_profile_id if box == "sent" else r.requester_profile_id for r in reqs})
    return {"total": total, "items": [_out(r, mine, cards) for r in reqs]}


def read_biodata(db: Session, member: Member, profile_id: UUID) -> dict:
    """FR-33-35: biodata goes only to its owner and the other side of an ACCEPTED request. Every other
    attempt is a 403 logged to security_event with actor, target and endpoint (FR-37)."""
    mine = my_profile_id(db, member)
    allowed = mine is not None and (profile_id == mine or db.scalar(
        select(BiodataRequest.request_id).where(*_pair(mine, profile_id), BiodataRequest.status == "ACCEPTED")))
    if not allowed:
        raise Denied("BIODATA_DENIED", "Biodata is shared only after the member accepts your request", profile_id)
    data = matrimony.biodata_of(db, profile_id)
    if data is None:
        raise HTTPException(404, "This member hasn't added a biodata yet")
    return data
