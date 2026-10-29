from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session

from core.database import get_db
from member.auth.deps import get_active_member
from member.auth.schema import Gender
from member.biodata_request import curd as requests
from member.matrimony import curd
from member.matrimony.schema import (
    BiodataIn, BiodataOut, EducationLevel, FamilyBackground, MyProfileOut, ProfileCreate, ProfileUpdate,
    PublicProfileOut, SearchPage,
)
from member.profile.model import Member

# Own matrimony profile (SF-04), Active members only (FR-19).
# Flow: POST /profile (DRAFT) -> POST /photos (1-5) -> PUT /biodata (private) -> POST /profile/submit
# -> City Admin approves -> searchable. A rejection's reason is in GET /profile; fix it and submit again.
# Browsing (SF-05): GET /profiles (filters) -> GET /profiles/{id} -> photo file_urls.
router = APIRouter(prefix="/member/matrimony", tags=["Member Matrimony"])


@router.get("/profile", response_model=MyProfileOut)
def get_profile(member: Member = Depends(get_active_member), db: Session = Depends(get_db)):
    return curd.my_profile(db, member)


@router.post("/profile", response_model=MyProfileOut, status_code=201)
def create_profile(data: ProfileCreate, member: Member = Depends(get_active_member), db: Session = Depends(get_db)):
    return curd.create_profile(db, member, data)


@router.put("/profile", response_model=MyProfileOut)
def update_profile(data: ProfileUpdate, member: Member = Depends(get_active_member), db: Session = Depends(get_db)):
    return curd.update_profile(db, member, data)


@router.post("/profile/submit", response_model=MyProfileOut)
def submit_profile(member: Member = Depends(get_active_member), db: Session = Depends(get_db)):
    return curd.submit(db, member)


@router.get("/profiles", response_model=SearchPage)
def search(
    age_min: int | None = Query(None, ge=18, le=100),
    age_max: int | None = Query(None, ge=18, le=100),
    gender: Gender | None = None,  # optional: whether search is opposite-gender only is still open (OQ-13)
    education_level: list[EducationLevel] = Query([]),
    city_id: list[UUID] = Query([]),
    family_background: list[FamilyBackground] = Query([]),
    after: UUID | None = None,
    limit: int = Query(20, ge=1, le=50),
    member: Member = Depends(get_active_member),
    db: Session = Depends(get_db),
):
    """Approved profiles only, your own included; public summary only (FR-25-26).
    Repeat a parameter for "any of": ?education_level=GRADUATE&education_level=POSTGRADUATE."""
    if age_min is not None and age_max is not None and age_min > age_max:
        raise HTTPException(422, "age_min can't be more than age_max")
    return curd.search(db, member, age_min=age_min, age_max=age_max, gender=gender,
                       education_level=education_level, city_id=city_id, family_background=family_background,
                       after=after, limit=limit)


@router.get("/profiles/{profile_id}", response_model=PublicProfileOut)
def public_profile(profile_id: UUID, member: Member = Depends(get_active_member), db: Session = Depends(get_db)):
    """What other members see: public summary, approved photos and where your biodata request stands."""
    return curd.public_profile(db, profile_id) | {
        "biodata_request": requests.latest_between(db, requests.my_profile_id(db, member), profile_id)}


@router.post("/photos", response_model=MyProfileOut, status_code=201)
def upload_photo(file: UploadFile, member: Member = Depends(get_active_member), db: Session = Depends(get_db)):
    """JPG or PNG up to 2 MB; at most 5 per profile. Each new photo is reviewed by the City Admin."""
    return curd.upload_photo(db, member, file.file.read(curd.PHOTO_MAX_BYTES + 1))


@router.delete("/photos/{photo_id}", response_model=MyProfileOut)
def delete_photo(photo_id: UUID, member: Member = Depends(get_active_member), db: Session = Depends(get_db)):
    return curd.delete_photo(db, member, photo_id)


@router.get("/photos/{photo_id}/file", response_class=Response,
            responses={200: {"content": {"image/jpeg": {}, "image/png": {}}}})
def photo_file(photo_id: UUID, member: Member = Depends(get_active_member), db: Session = Depends(get_db)):
    data, mime_type = curd.photo_file(db, member, photo_id)
    return Response(data, media_type=mime_type, headers={"Cache-Control": "no-store"})


@router.get("/biodata", response_model=BiodataOut, response_model_exclude_none=True)
def get_biodata(member: Member = Depends(get_active_member), db: Session = Depends(get_db)):
    """Your own biodata. Others see it only after accepting a biodata request (SF-06)."""
    return curd.get_biodata(db, member)


@router.put("/biodata", response_model=BiodataOut, response_model_exclude_none=True)
def put_biodata(data: BiodataIn, member: Member = Depends(get_active_member), db: Session = Depends(get_db)):
    return curd.put_biodata(db, member, data)
