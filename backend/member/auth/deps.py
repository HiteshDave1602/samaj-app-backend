from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from core.database import get_db
from member.auth import curd
from member.profile.model import Member
from search import es

_bearer = HTTPBearer(auto_error=False)


def get_current_member(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Member:
    """Any logged-in member, PENDING included."""
    if creds is None:
        raise HTTPException(401, "Not authenticated")
    member = curd.member_from_access_token(db, creds.credentials)
    request.state.member_id = member.member_id  # for log_denied
    return member


def get_active_member(member: Member = Depends(get_current_member)) -> Member:
    """FR-08: features beyond Panchang and News wait for City Admin approval."""
    if member.status != "ACTIVE":
        raise HTTPException(403, "Available after your membership is approved")
    return member


def get_searching_member(member: Member = Depends(get_active_member)) -> Member:
    """get_active_member, plus a per-member limit on directory and matrimony searches (SEARCH_RATE_PER_MINUTE)."""
    if not es.allow(member.member_id):
        raise HTTPException(429, "Too many searches. Try again in a minute.")
    return member
