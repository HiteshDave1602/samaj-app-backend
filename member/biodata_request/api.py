from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.database import get_db
from member.auth.deps import get_active_member
from member.biodata_request import curd
from member.biodata_request.schema import BiodataRequestOut, BiodataRequestPage
from member.matrimony.schema import BiodataOut
from member.profile.model import Member

# Consent-based biodata exchange (SF-06). Flow: A: POST /profiles/{B}/biodata-request -> B: GET
# /biodata-requests?box=received -> POST .../accept -> both: GET /profiles/{other}/biodata.
# Biodata never reaches anyone else, admins included (FR-35, FR-36).
router = APIRouter(prefix="/member/matrimony", tags=["Member Biodata Requests"])


@router.post("/profiles/{profile_id}/biodata-request", response_model=BiodataRequestOut, status_code=201)
def send(profile_id: UUID, member: Member = Depends(get_active_member), db: Session = Depends(get_db)):
    """Your own profile must be approved. One open request per pair; 30 days after a decline; 20 a day."""
    return curd.send(db, member, profile_id)


@router.get("/biodata-requests", response_model=BiodataRequestPage)
def list_requests(
    box: Literal["received", "sent"],
    status: Literal["PENDING", "ACCEPTED", "DECLINED", "WITHDRAWN"] | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    member: Member = Depends(get_active_member),
    db: Session = Depends(get_db),
):
    return curd.list_requests(db, member, box, status, limit, offset)


@router.post("/biodata-requests/{request_id}/accept", response_model=BiodataRequestOut)
def accept(request_id: UUID, member: Member = Depends(get_active_member), db: Session = Depends(get_db)):
    return curd.respond(db, member, request_id, accept=True)


@router.post("/biodata-requests/{request_id}/decline", response_model=BiodataRequestOut)
def decline(request_id: UUID, member: Member = Depends(get_active_member), db: Session = Depends(get_db)):
    return curd.respond(db, member, request_id, accept=False)


@router.post("/biodata-requests/{request_id}/withdraw", response_model=BiodataRequestOut)
def withdraw(request_id: UUID, member: Member = Depends(get_active_member), db: Session = Depends(get_db)):
    """Either side ends an accepted exchange; neither can open the other's biodata after this."""
    return curd.withdraw(db, member, request_id)


@router.get("/profiles/{profile_id}/biodata", response_model=BiodataOut, response_model_exclude_none=True)
def read_biodata(profile_id: UUID, member: Member = Depends(get_active_member), db: Session = Depends(get_db)):
    """Only with an ACCEPTED request between you; anything else is 403 and logged."""
    return curd.read_biodata(db, member, profile_id)
