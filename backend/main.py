from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from auth.api import router as auth_router
from auth.deps import log_denied
from cityadmin.content.api import router as content_router
from cityadmin.family_addition.api import router as family_addition_router
from cityadmin.matrimony.api import router as matrimony_router
from cityadmin.member_approval.api import router as member_approval_router
from cityadmin.member_export.api import router as member_export_router
from cityadmin.member_import.api import router as member_import_router
from cityadmin.panchang.api import router as panchang_router
from core import media
from core.admission import AdmissionLimit
from core.config import settings
from core.database import get_db
from member.auth.api import router as member_auth_router
from member.biodata_request.api import router as member_biodata_request_router
from member.directory.api import router as member_directory_router
from member.family.api import router as member_family_router
from member.feed.api import router as member_feed_router
from member.matrimony.api import router as member_matrimony_router
from member.news.api import router as member_news_router
from member.notification.api import router as member_notification_router
from member.panchang.api import router as member_panchang_router
from member.profile.api import router as member_profile_router
from superadmin.audit_log.api import router as audit_log_router
from superadmin.city.api import router as city_router
from superadmin.city_admin.api import router as city_admin_router
from superadmin.content.api import router as superadmin_content_router
from superadmin.audit_log.curd import Denied
from superadmin.pending_member.api import router as pending_member_router
from superadmin.search.api import router as search_status_router
from search import es
import search.outbox  # noqa: F401  registers the listener that queues search-index updates with each commit


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if es.enabled():
        es.client()  # the process's one ES client; requests share its connection pool
    yield
    es.close()


app = FastAPI(title="Samaj API", lifespan=lifespan)
# One slot fewer than the DB pool: log_denied and the feed's translation task each open a second session.
app.add_middleware(AdmissionLimit, limit=settings.db_pool_size + settings.db_max_overflow - 1)
app.add_exception_handler(Denied, log_denied)  # cross-city / ID-document 403s go to security_event
app.include_router(auth_router)
app.include_router(city_router)
app.include_router(city_admin_router)
app.include_router(audit_log_router)
app.include_router(pending_member_router)
app.include_router(member_approval_router)
app.include_router(member_auth_router)
app.include_router(member_profile_router)
app.include_router(member_family_router)
app.include_router(member_matrimony_router)
app.include_router(member_biodata_request_router)
app.include_router(content_router)
app.include_router(family_addition_router)
app.include_router(matrimony_router)
app.include_router(panchang_router)
app.include_router(member_import_router)
app.include_router(member_export_router)
app.include_router(superadmin_content_router)
app.include_router(member_feed_router)
app.include_router(member_news_router)
app.include_router(member_directory_router)
app.include_router(member_panchang_router)
app.include_router(member_notification_router)
app.include_router(search_status_router)
app.mount("/media", StaticFiles(directory=media.MEDIA_DIR), name="media")  # news/ad images; random keys


@app.get("/health")
def health(db: Session = Depends(get_db)):
    """search: off | green | yellow | red | degraded. Degraded is still up: searches are answered by Postgres."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "search": es.health()}
