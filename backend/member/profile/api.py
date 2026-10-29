from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from core.database import get_db
from member.auth.deps import get_current_member
from member.profile import curd
from member.profile.model import Member
from member.profile.schema import MemberOut, MemberUpdate

router = APIRouter(prefix="/member", tags=["Member Profile"])


@router.get("/me", response_model=MemberOut)
def get_me(member: Member = Depends(get_current_member), db: Session = Depends(get_db)):
    return curd.to_profile(db, member)


@router.put("/me", response_model=MemberOut)
def update_me(data: MemberUpdate, member: Member = Depends(get_current_member), db: Session = Depends(get_db)):
    """Changing name or date of birth on a verified profile returns it to City Admin review (ASM-10).
    Any profile edit by a rejected member resubmits it. hide_*/notify_news never trigger a review."""
    return curd.update_me(db, member, data)


@router.put("/me/photo", response_model=MemberOut)
def upload_photo(file: UploadFile, member: Member = Depends(get_current_member), db: Session = Depends(get_db)):
    """JPG or PNG up to 2 MB; replaces the current photo."""
    return curd.upload_photo(db, member, file.file.read(curd.ID_MAX_BYTES + 1))


@router.put("/me/id-document", response_model=MemberOut)
def upload_id_document(file: UploadFile, member: Member = Depends(get_current_member),
                       db: Session = Depends(get_db)):
    """JPG, PNG or PDF up to 2 MB, while the membership is pending or rejected."""
    return curd.upload_id_document(db, member, file.file.read(curd.ID_MAX_BYTES + 1))
