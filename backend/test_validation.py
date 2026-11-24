"""Input validation, sanitization and security guards against the dev DB: python test_validation.py
core/validation.py rules, core/guard.py (error shape, body cap), and the attacks they must stop: unexpected
properties / mass assignment, malformed JSON, XSS and SQL injection payloads, disguised or oversized uploads, and
duplicate submissions. Cleans up after itself."""
import secrets
import subprocess
import sys
import threading
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError

from cityadmin.content.model import ContentItem
from core import media
from core.database import SessionLocal
from core.security import fernet
from main import app
from member.auth.curd import _start_session, mobile_hash
from member.profile.model import FamilyMember, Household, Member
from superadmin.city.model import City

subprocess.run([sys.executable, "-m", "core.validation"], check=True)  # the rule unit checks

c = TestClient(app, raise_server_exceptions=False)
tag = secrets.token_hex(4)
now = datetime.now(timezone.utc)


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def err(r, status: int, code: str) -> dict:
    """The response is the shared shape: detail kept for old clients, plus error.code / message / fields."""
    body = r.json()
    assert r.status_code == status and "detail" in body and body["error"]["code"] == code, (r.status_code, r.text)
    assert isinstance(body["error"]["message"], str) and body["error"]["message"], body
    return body["error"]


with SessionLocal() as db:
    city = City(name=f"ValCity-{tag}", state="T")
    db.add(city)
    db.flush()
    mobile = f"+919{secrets.randbelow(10**9):09d}"
    h = Household(household_id=uuid4(), city_id=city.city_id, family_name="Valfam")
    m = Member(member_id=uuid4(), city_id=city.city_id, household_id=h.household_id, is_household_head=True,
               mobile_hash=mobile_hash(mobile), mobile_enc=fernet.encrypt(mobile.encode()), mobile_last4=mobile[-4:],
               full_name="Asha Patel", gender="FEMALE", dob=date(1980, 5, 1), status="ACTIVE")
    db.add(h)
    db.flush()
    db.add(m)
    db.flush()
    me_h = bearer(_start_session(db, m)["access_token"])
    db.commit()
    city_id, member_id, household_id = city.city_id, m.member_id, h.household_id

try:
    # --- one error shape everywhere --------------------------------------------------------------------------
    assert err(c.get("/member/me"), 401, "UNAUTHORIZED")
    assert err(c.get("/no/such/route"), 404, "NOT_FOUND")
    assert err(c.get("/superadmin/cities", headers=me_h), 401, "UNAUTHORIZED")  # a member token is no admin token

    # --- malformed JSON and wrong types ----------------------------------------------------------------------
    r = c.put("/member/me", headers={**me_h, "Content-Type": "application/json"}, content=b'{"full_name": "Asha')
    assert err(r, 422, "MALFORMED_JSON")["fields"] == {"body": "The request body isn't valid JSON"}
    for bad in ({"hide_phone": "maybe"}, {"full_name": 123}, {"dob": "yesterday"}, {"gender": "M"}):
        assert c.put("/member/me", headers=me_h, json=bad).status_code == 422, bad
    assert c.put("/member/me", headers=me_h, json=[1, 2]).status_code == 422  # not an object at all

    # --- unexpected properties: mass assignment can't flip status, city or household headship -----------------
    for extra in ({"status": "ACTIVE"}, {"city_id": str(uuid4())}, {"is_household_head": False}, {"member_id": str(uuid4())}):
        e = err(c.put("/member/me", headers=me_h, json={"hide_phone": True, **extra}), 422, "VALIDATION_ERROR")
        assert e["fields"] == {next(iter(extra)): "This field isn't accepted"}, e
    with SessionLocal() as db:
        row = db.get(Member, member_id)
        assert (row.status, row.city_id, row.is_household_head, row.hide_phone) == ("ACTIVE", city_id, True, False)

    # --- field rules, boundaries, and normalization -----------------------------------------------------------
    patch = lambda **f: c.put("/member/me", headers=me_h, json=f)  # noqa: E731
    for junk, why in (("asdfghjkl", "Enter a real name"), ("!!!!!!!", "Use letters only in a name"),
                      ("1111111111", "Use letters only in a name"), ("test", "Enter a real name"),
                      ("<img src=x onerror=alert(1)>", "Use letters only in a name"), ("Raaaaam", None)):
        e = err(patch(full_name=junk), 422, "VALIDATION_ERROR")
        assert why is None or e["fields"]["full_name"] == why, (junk, e)
    assert patch(full_name="Ab" * 60).status_code == 200  # 120: the limit
    assert patch(full_name="Ab" * 60 + "c").status_code == 422  # 121
    assert patch(full_name="   ").status_code == 422  # whitespace only is empty
    r = patch(full_name="  asha ‮  d'souza\x00 ")  # bidi override and NUL out, spaces squeezed
    assert r.status_code == 200 and r.json()["full_name"] == "asha d'souza", r.text
    assert patch(full_name="આશાબેન પટેલ").json()["full_name"] == "આશાબેન પટેલ"  # every script is a name
    r = patch(address="12/B, Gandhi Road #4\n\n\n\nNear <Temple> & Market")  # addresses keep their symbols
    assert r.json()["address"] == "12/B, Gandhi Road #4\n\nNear <Temple> & Market", r.json()["address"]
    assert err(patch(native_place="1234"), 422, "VALIDATION_ERROR")["fields"]["native_place"]
    with SessionLocal() as db:  # the name changes sent the membership back to review (by design); approve it again
        db.get(Member, member_id).status = "ACTIVE"
        db.commit()

    # submitted values never come back in a 422 (no password echo into proxies' logs)
    r = c.post("/admin/auth/login", json={"email": "not-an-email", "password": "hunter2-very-secret"})
    assert r.status_code == 422 and "hunter2-very-secret" not in r.text and "input" not in r.text, r.text

    # registration: the same rules, placeholder numbers included
    reg_mobile = f"+919{secrets.randbelow(10**9):09d}"
    form = {"mobile": reg_mobile, "full_name": "Kiran Shah", "gender": "MALE",
            "dob": "1990-01-01", "city_id": str(city_id), "address": "4 MG Road", "family_name": "Shah",
            "consent": True, "notice_version": "v1"}
    e = err(c.post("/member/auth/register", json=form | {"full_name": "qwerty", "mobile": "+919999999999"}),
            422, "VALIDATION_ERROR")
    assert set(e["fields"]) == {"full_name", "mobile"}, e
    assert err(c.post("/member/auth/otp/send", json={"mobile": "9999999999"}), 422, "VALIDATION_ERROR")

    # --- XSS: kept as typed text, returned as JSON data, never interpreted ---------------------------------------
    key = c.post("/member/news/media", headers=me_h, files={"file": ("b.png", media.png(1200, 600), "image/png")})
    assert key.status_code == 201, key.text
    xss = '<script>alert("x")</script> Diwali mela'
    news = {"title": xss, "body": "Join us <b>tonight</b> & bring sweets", "media_key": key.json()["media_key"]}
    r = c.post("/member/news", headers=me_h, json=news)
    assert r.status_code == 201 and r.headers["content-type"].startswith("application/json"), r.text
    with SessionLocal() as db:
        item = db.get(ContentItem, r.json()["content_id"])
        assert (item.title, item.body) == (xss, news["body"])  # React/RN escape on display; nothing stripped here
    # duplicate submission (double tap): the same pending post is refused
    assert err(c.post("/member/news", headers=me_h, json=news), 409, "CONFLICT")
    assert c.post("/member/news", headers=me_h, json=news | {"status": "LIVE"}).status_code == 422  # can't self-approve
    assert c.post("/member/news", headers=me_h, json=news | {"title": "!!!!!!!!"}).status_code == 422

    # --- SQL injection: search text is data, bound as a parameter ----------------------------------------------
    for q in ("' OR 1=1 --", "'; DROP TABLE samaj.member; --", "%_%", "\\"):
        r = c.get("/member/directory", headers=me_h, params={"name": q + "zz"})
        # nothing matches literally; the directory may still offer its "closest names" fallback (suggested=true)
        assert r.status_code == 200 and (r.json()["items"] == [] or r.json()["suggested"]), (q, r.text[:300])
    with SessionLocal() as db:
        assert db.execute(text("SELECT count(*) FROM samaj.member WHERE member_id = :m"), {"m": member_id}).scalar() == 1

    # --- request size: by Content-Length, and by counting a chunked body ---------------------------------------
    big = b'{"title": "' + b"a" * (1024 * 1024) + b'"}'
    assert err(c.post("/member/news", headers={**me_h, "Content-Type": "application/json"}, content=big),
               413, "PAYLOAD_TOO_LARGE")
    chunks = (b"x" * 65536 for _ in range(20))  # no Content-Length: 1.25 MB streamed
    assert err(c.post("/member/news", headers={**me_h, "Content-Type": "application/json"}, content=chunks),
               413, "PAYLOAD_TOO_LARGE")
    r = c.put("/member/me/photo", headers=me_h, files={"file": ("p.png", b"\x89PNG" + bytes(11 * 1024 * 1024), "image/png")})
    assert err(r, 413, "PAYLOAD_TOO_LARGE")

    # --- uploads: the bytes decide, never the name or the claimed type -----------------------------------------
    disguised = {"gif": b"GIF89a" + bytes(64), "html": b"<html><script>alert(1)</script></html>",
                 "exe": b"MZ\x90\x00" + bytes(64), "svg": b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>'}
    for what, data in disguised.items():
        r = c.put("/member/me/photo", headers=me_h, files={"file": ("photo.png", data, "image/png")})
        assert err(r, 400, "ERR_IMG_UL"), what
    r = c.put("/member/me/photo", headers=me_h, files={"file": ("id.png", b"%PDF-1.4" + bytes(64), "image/png")})
    assert r.status_code == 400  # a PDF is fine as an ID document, not as a photo
    r = c.put("/member/me/photo", headers=me_h, files={"file": ("p.png", media.png(10, 10) + bytes(2 * 1024 * 1024), "image/png")})
    assert err(r, 413, "ERR_IMG_UL")  # over the 2 MB photo limit (under the body cap)

    # --- duplicates the database itself refuses ----------------------------------------------------------------
    rel = {"full_name": "Rohan", "relationship": "SON", "gender": "MALE", "dob": "2010-03-04"}
    gate = threading.Barrier(4)
    codes = []

    def send():
        gate.wait()
        codes.append(c.post("/member/family", headers=me_h, json=rel).status_code)

    threads = [threading.Thread(target=send) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(codes) == [201, 409, 409, 409], codes  # four at once: exactly one gets in
    with SessionLocal() as db:
        db.add(FamilyMember(household_id=household_id, full_name="ROHAN", relationship="SON", gender="MALE",
                            dob=date(2010, 3, 4), status="APPROVED"))
        try:
            db.commit()
            raise AssertionError("ux_family_member_person let a duplicate in")
        except IntegrityError:
            db.rollback()
    print("ok")
finally:
    with SessionLocal() as db:  # auth_session rows go via ON DELETE CASCADE
        db.execute(delete(ContentItem).where(ContentItem.created_by_member_id == member_id))
        db.execute(delete(FamilyMember).where(FamilyMember.household_id == household_id))
        db.execute(delete(Member).where(Member.city_id == city_id))
        db.execute(delete(Household).where(Household.city_id == city_id))
        db.execute(delete(City).where(City.city_id == city_id))
        db.commit()
