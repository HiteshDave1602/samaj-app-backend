from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from cityadmin.content import curd
from cityadmin.content.schema import MediaOut, NewsSubmit, NewsSubmitted
from core import media
from core.database import get_db
from member.auth.deps import get_active_member
from member.profile.model import Member

# Members post news for their city (Active members only, FR-08).
# Flow: POST /media (banner, extras) -> POST "" -> PENDING until the City Admin approves it into the feed.
router = APIRouter(prefix="/member/news", tags=["Member News"])


@router.post("/media", response_model=MediaOut, status_code=201)
def upload_media(file: UploadFile, member: Member = Depends(get_active_member)):
    return curd.upload_media(file.file.read(media.MAX_BYTES + 1))


@router.post("", response_model=NewsSubmitted, status_code=201)
def submit(data: NewsSubmit, member: Member = Depends(get_active_member), db: Session = Depends(get_db)):
    return curd.submit(db, member, data)
