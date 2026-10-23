from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from auth.deps import client_ip
from core.database import get_db
from member.auth import curd
from member.auth.schema import OtpSendIn, OtpSendOut, OtpVerifyIn, OtpVerifyOut, RefreshIn, RegisterIn, TokenOut

# Flow: POST /otp/send -> POST /otp/verify -> registered: session | new: registration_ticket -> POST /register.
# Then send access_token as Bearer; when it expires (15 min) POST /refresh with the refresh_token.
router = APIRouter(prefix="/member/auth", tags=["Member Auth"])


@router.post("/otp/send", response_model=OtpSendOut)
def send_otp(data: OtpSendIn, request: Request, db: Session = Depends(get_db)):
    return curd.send_otp(db, data.mobile, client_ip(request))


@router.post("/otp/verify", response_model=OtpVerifyOut, response_model_exclude_none=True)
def verify_otp(data: OtpVerifyIn, db: Session = Depends(get_db)):
    return curd.verify_otp(db, data.mobile, data.code)


@router.post("/register", response_model=TokenOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    return curd.register(db, data)


@router.post("/refresh", response_model=TokenOut)
def refresh(data: RefreshIn, db: Session = Depends(get_db)):
    return curd.refresh(db, data.refresh_token)


@router.post("/logout", status_code=204)
def logout(data: RefreshIn, db: Session = Depends(get_db)):
    curd.logout(db, data.refresh_token)
