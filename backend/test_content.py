"""End-to-end News & Ads check (SF-07) against the dev DB: python test_content.py
Creates two cities, their City Admins, a Super Admin, members and content, then deletes them.
Their audit_log rows stay: the table is append-only by design."""
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, or_, update

from auth.curd import hash_token
from auth.model import AuthSession
from cityadmin.content.model import ContentItem
from core import media
from core.database import SessionLocal
from core.security import fernet, hash_password
from main import app
from member.auth.curd import _start_session, mobile_hash
from member.profile.model import Member
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser

c = TestClient(app)
tag = secrets.token_hex(4)
now = datetime.now(timezone.utc)
iso = lambda dt: dt.isoformat()


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def admin_session(db, admin: AdminUser) -> dict:
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(admin_id=admin.admin_id, refresh_token_hash=hash_token(token), mfa_verified=True,
                       last_activity_at=now, expires_at=now + timedelta(hours=1)))
    return bearer(token)


def member(db, city: City, status: str) -> Member:
    mobile = f"+919{secrets.randbelow(10**9):09d}"
    m = Member(city_id=city.city_id, mobile_hash=mobile_hash(mobile), mobile_enc=fernet.encrypt(mobile.encode()),
               mobile_last4=mobile[-4:], full_name="M", gender="FEMALE", status=status)
    db.add(m)
    return m


with SessionLocal() as db:
    city_x, city_y = City(name=f"CX-{tag}", state="T"), City(name=f"CY-{tag}", state="T")
    city_z = City(name=f"CZ-{tag}", state="T", is_active=False)
    db.add_all([city_x, city_y, city_z])
    db.flush()
    pw = hash_password(secrets.token_hex(8))
    sa = AdminUser(role="SUPER_ADMIN", full_name="SA", email=f"csa-{tag}@t.local", password_hash=pw)
    ca_x = AdminUser(role="CITY_ADMIN", city_id=city_x.city_id, full_name="CA X", email=f"cx-{tag}@t.local",
                     password_hash=pw)
    ca_y = AdminUser(role="CITY_ADMIN", city_id=city_y.city_id, full_name="CA Y", email=f"cy-{tag}@t.local",
                     password_hash=pw)
    m_x, m_y = member(db, city_x, "ACTIVE"), member(db, city_y, "PENDING")
    db.add_all([sa, ca_x, ca_y])
    db.flush()
    sa_h, x_h, y_h = admin_session(db, sa), admin_session(db, ca_x), admin_session(db, ca_y)
    db.commit()
    mx_h = bearer(_start_session(db, m_x)["access_token"])
    my_h = bearer(_start_session(db, m_y)["access_token"])
    city_ids, admin_ids = [city_x.city_id, city_y.city_id, city_z.city_id], [sa.admin_id, ca_x.admin_id, ca_y.admin_id]
    cz = str(city_z.city_id)
    cx, cy, sa_id, ca_x_id = str(city_x.city_id), str(city_y.city_id), sa.admin_id, str(ca_x.admin_id)

base = "/cityadmin/content"
keys: list[str] = []


def upload(data: bytes, h=x_h):
    r = c.post(f"{base}/media", headers=h, files={"file": ("img.png", data, "image/png")})
    if r.status_code == 201:
        keys.append(r.json()["media_key"])
    return r


def news(title: str, start: datetime, end: datetime | None = None, h=x_h, path=base, **extra):
    return c.post(path, headers=h, json={"content_type": "NEWS", "title": title, "body": f"{title} body",
                                         "start_at": iso(start), "end_at": iso(end or now + timedelta(hours=2)),
                                         **extra})


def feed(h) -> list[str]:
    r = c.get("/member/feed", headers=h)
    assert r.status_code == 200, r.text
    return [i["title"] for i in r.json()]


try:
    # media: JPEG/PNG only, 5 MB max, City Admin only; dimensions read by the server
    r = upload(media.png(1080, 1920))
    assert r.status_code == 201 and (r.json()["width"], r.json()["height"]) == (1080, 1920), r.text
    tall_key = r.json()["media_key"]
    assert c.get(r.json()["media_url"]).content == media.png(1080, 1920)  # served
    square_key = upload(media.png(1080, 1080)).json()["media_key"]
    assert upload(b"GIF89a" + bytes(30)).status_code == 400
    assert upload(media.png(10, 10) + bytes(media.MAX_BYTES)).status_code == 413
    assert upload(media.png(10, 10), h=sa_h).status_code == 403

    # FR-43: news saved with all six fields; live right away
    r = news("N1", now - timedelta(minutes=60))
    assert r.status_code == 201, r.text
    n1 = r.json()
    assert (n1["status"], n1["city_id"], n1["created_by_admin_id"]) == ("LIVE", cx, ca_x_id), n1
    r = news("Pic", now - timedelta(minutes=59), media_key=square_key)
    assert r.status_code == 201 and r.json()["media_url"] == f"/media/{square_key}", r.text

    # FR-46 / validation
    assert news("Bad", now, now).status_code == 422  # end == start
    assert news("Bad", now - timedelta(hours=3), now - timedelta(hours=2)).status_code == 400  # already over
    assert c.post(base, headers=x_h, json={"content_type": "NEWS", "title": "No body", "start_at": iso(now),
                                           "end_at": iso(now + timedelta(hours=1))}).status_code == 422
    assert news("Naive", datetime(2030, 1, 1), datetime(2030, 1, 2)).status_code == 422  # needs a timezone

    # FR-44/45: ads need media + format; full-screen must be 1080x1920
    ad = lambda fmt, key, **kw: c.post(base, headers=x_h, json={
        "content_type": "AD", "title": f"Ad {fmt}", "creative_format": fmt, "media_key": key,
        "start_at": iso(now - timedelta(minutes=30)), "end_at": iso(now + timedelta(hours=2)), **kw})
    r = ad("FULLSCREEN", square_key)
    assert r.status_code == 400 and "1080x1920" in r.text, r.text
    assert ad("FULLSCREEN", tall_key).status_code == 201
    r = ad("BANNER", square_key, start_at=iso(now - timedelta(minutes=20)))  # newer than the full-screen ad
    assert r.status_code == 201, r.text
    banner_id = r.json()["content_id"]
    assert ad("BANNER", None).status_code == 422
    assert ad("BANNER", "../.env").status_code == 400 and ad("BANNER", f"{uuid4().hex}.png").status_code == 400
    r = c.put(f"{base}/{banner_id}", headers=x_h, json={"creative_format": "FULLSCREEN"})
    assert r.status_code == 400, r.text  # the stored square image doesn't fit full-screen

    # FR-48: own city only
    assert news("Y's", now, city_id=cy).status_code == 403
    assert news("Own", now - timedelta(minutes=58), city_id=cx).status_code == 201

    # FR-47: scheduled -> live -> expired by time; drafts never show
    future = news("Future", now + timedelta(hours=1)).json()
    assert future["status"] == "SCHEDULED"
    draft = news("Draft", now - timedelta(minutes=50), status="DRAFT").json()
    assert draft["status"] == "DRAFT"
    assert "Future" not in feed(mx_h) and "Draft" not in feed(mx_h)
    r = c.put(f"{base}/{future['content_id']}", headers=x_h, json={"start_at": iso(now - timedelta(minutes=1))})
    assert r.status_code == 200 and r.json()["status"] == "LIVE", r.text
    assert c.put(f"{base}/{future['content_id']}", headers=x_h,
                 json={"end_at": iso(now - timedelta(hours=1))}).status_code == 400  # end before start
    with SessionLocal() as db:  # let N1 run out
        db.execute(update(ContentItem).where(ContentItem.title == "N1", ContentItem.city_id == city_ids[0])
                   .values(end_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
        db.commit()
    assert c.get(f"{base}/{n1['content_id']}", headers=x_h).json()["status"] == "EXPIRED"
    assert "N1" not in feed(mx_h)
    assert c.put(f"{base}/{n1['content_id']}", headers=x_h, json={"title": "x"}).status_code == 409

    # cancel is final
    r = c.put(f"{base}/{draft['content_id']}", headers=x_h, json={"status": "CANCELLED"})
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED", r.text
    assert c.put(f"{base}/{draft['content_id']}", headers=x_h, json={"status": "SCHEDULED"}).status_code == 409

    # FR-71: another city's content is 403 for every action; lists are own city only
    assert c.get(f"{base}/{banner_id}", headers=y_h).status_code == 403
    assert c.put(f"{base}/{banner_id}", headers=y_h, json={"title": "hijack"}).status_code == 403
    assert c.get(f"{base}/{uuid4()}", headers=x_h).status_code == 404
    assert c.get(base, headers=y_h).json()["total"] == 0
    lst = lambda **p: sorted(i["title"] for i in c.get(base, headers=x_h, params=p).json()["items"])
    assert lst(content_type="AD") == ["Ad BANNER", "Ad FULLSCREEN"]
    assert lst(status="LIVE") == ["Ad BANNER", "Ad FULLSCREEN", "Future", "Own", "Pic"]
    assert lst(status="EXPIRED") == ["N1"] and lst(status="CANCELLED") == ["Draft"]
    assert c.get(base, headers=x_h, params={"status": "BOGUS"}).status_code == 422

    # FR-49/50: member feed = own city + all-city, newest first, an ad after every 5 news
    # Super Admin (FR-48): no city_id = every city; or one named city; unknown/inactive cities refused
    sa_base = "/superadmin/content"
    r = news("All cities", now - timedelta(minutes=40), h=sa_h, path=sa_base)
    assert r.status_code == 201 and r.json()["city_id"] is None and r.json()["status"] == "LIVE", r.text
    all_id = r.json()["content_id"]
    r = news("SA for Y", now - timedelta(minutes=30), h=sa_h, path=sa_base, city_id=cy)
    assert r.status_code == 201 and r.json()["city_id"] == cy, r.text
    assert news("x", now, h=sa_h, path=sa_base, city_id=str(uuid4())).status_code == 404
    assert news("x", now, h=sa_h, path=sa_base, city_id=cz).status_code == 400  # inactive
    r = c.post(f"{sa_base}/media", headers=sa_h, files={"file": ("a.png", media.png(1080, 1920), "image/png")})
    assert r.status_code == 201, r.text
    keys.append(r.json()["media_key"])
    # City Admins can't touch all-city items
    assert c.get(f"{base}/{all_id}", headers=x_h).status_code == 403
    assert c.put(f"{base}/{all_id}", headers=x_h, json={"title": "mine"}).status_code == 403
    for i in range(3):
        assert news(f"Late{i}", now - timedelta(minutes=10 - i)).status_code == 201
    assert news("Y news", now - timedelta(minutes=5), h=y_h).status_code == 201
    x_feed = c.get("/member/feed", headers=mx_h).json()
    titles = [i["title"] for i in x_feed]
    # news newest first: Future(-1m) Late2 Late1 Late0 All cities | ad | Own Pic, ads rotate newest first
    assert titles == ["Future", "Late2", "Late1", "Late0", "All cities", "Ad BANNER", "Own", "Pic"], titles
    assert x_feed[5]["creative_format"] == "BANNER" and "created_by_admin_id" not in x_feed[0]
    assert feed(my_h) == ["Y news", "SA for Y", "All cities"]  # PENDING members see news too (FR-08)
    assert c.get("/member/feed").status_code == 401

    # Super Admin sees and manages every city's content
    sa_lst = lambda **p: sorted(i["title"] for i in c.get(sa_base, headers=sa_h, params=p).json()["items"])
    assert sa_lst(all_cities=True) == ["All cities"]
    assert sa_lst(city_id=cy) == ["SA for Y", "Y news"]
    assert sa_lst(city_id=cx) == lst()  # same as City Admin X's own view
    assert {"All cities", "SA for Y", "Y news", "Pic"} <= set(sa_lst(limit=200))
    r = c.put(f"{sa_base}/{banner_id}", headers=sa_h, json={"status": "CANCELLED"})  # X's ad
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED", r.text
    assert "Ad BANNER" not in feed(mx_h)
    assert c.get(f"{sa_base}/{uuid4()}", headers=sa_h).status_code == 404
    sa_actions = sorted(e["action"] for e in c.get("/superadmin/audit-logs", headers=sa_h,
                                                   params={"actor_id": str(sa_id), "limit": 200}).json()["items"])
    assert sa_actions == ["CONTENT_CANCEL", "CONTENT_CREATE", "CONTENT_CREATE"], sa_actions

    # FR-86: every change audited under the City Admin, with city
    actions = sorted(e["action"] for e in c.get("/superadmin/audit-logs", headers=sa_h,
                                                params={"actor_id": ca_x_id, "limit": 200}).json()["items"])
    assert actions == ["CONTENT_CANCEL"] + ["CONTENT_CREATE"] * 10 + ["CONTENT_UPDATE"], actions

    # member news: submitted PENDING, out of the feed until City Admin X approves
    def m_upload(h=mx_h):
        r = c.post("/member/news/media", headers=h, files={"file": ("img.png", media.png(800, 400), "image/png")})
        if r.status_code == 201:
            keys.append(r.json()["media_key"])
        return r
    assert m_upload(my_h).status_code == 403  # PENDING members can't post
    banner, extra = m_upload().json()["media_key"], m_upload().json()["media_key"]
    post = lambda **kw: c.post("/member/news", headers=mx_h,
                               json={"title": "Member news", "body": "B", "media_key": banner} | kw)
    assert post(extra_media_keys=["nope.png"]).status_code == 400
    assert post(media_key="nope.png").status_code == 400
    assert post(extra_media_keys=[extra] * 6).status_code == 422
    r = post(extra_media_keys=[extra])
    assert r.status_code == 201 and r.json()["status"] == "PENDING", r.text
    mn = r.json()["content_id"]
    assert "Member news" not in feed(mx_h)
    assert [i["title"] for i in c.get(base, headers=x_h, params={"status": "PENDING"}).json()["items"]] == ["Member news"]
    assert c.put(f"{base}/{mn}", headers=x_h, json={"status": "SCHEDULED"}).status_code == 409  # approve, not edit
    assert c.post(f"{base}/{mn}/approve", headers=y_h).status_code == 403  # other city
    r = c.post(f"{base}/{mn}/approve", headers=x_h)
    assert r.status_code == 200 and r.json()["status"] == "LIVE" and r.json()["created_by_member_id"], r.text
    assert c.post(f"{base}/{mn}/approve", headers=x_h).status_code == 409
    item = next(i for i in c.get("/member/feed", headers=mx_h).json() if i["title"] == "Member news")
    assert item["extra_media_urls"] == [f"/media/{extra}"], item
    rn = post(title="Spam").json()["content_id"]
    assert c.post(f"{base}/{rn}/reject", headers=x_h, json={"reason": ""}).status_code == 422
    r = c.post(f"{base}/{rn}/reject", headers=x_h, json={"reason": "Off topic"})
    assert r.status_code == 200 and r.json()["status"] == "REJECTED", r.text
    assert "Spam" not in feed(mx_h)
    print("ok")
finally:
    with SessionLocal() as db:  # auth_session rows go via ON DELETE CASCADE
        db.execute(delete(ContentItem).where(or_(ContentItem.created_by_admin_id.in_(admin_ids),
                                                 ContentItem.city_id.in_(city_ids))))
        db.execute(delete(Member).where(Member.city_id.in_(city_ids)))
        db.execute(delete(AdminUser).where(AdminUser.admin_id.in_(admin_ids)))
        db.execute(delete(City).where(City.city_id.in_(city_ids)))
        db.commit()
    for key in keys:
        (media.MEDIA_DIR / key).unlink(missing_ok=True)
