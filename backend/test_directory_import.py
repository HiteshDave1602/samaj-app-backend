"""Super Admin directory import against the dev DB: python test_directory_import.py
Imports a sheet in the Super Admin's template, then checks the people in the app directory. Cleans up after itself
(audit_log rows stay: append-only)."""
import csv
import io
import secrets
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from auth.curd import hash_token
from auth.model import AuthSession
from cityadmin.member_import.model import ImportJob
from core import private_files
from core.database import SessionLocal
from core.security import fernet, hash_password
from main import app
from member.auth.curd import _start_session, mobile_hash
from member.profile.model import FamilyMember, Household, Member
from search.sync import drain
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser
from superadmin.member_import.curd import HEADERS

c = TestClient(app)
tag = secrets.token_hex(4)
now = datetime.now(timezone.utc)
base = "/superadmin/imports"


def sheet(rows, header=HEADERS) -> bytes:
    buf = io.StringIO()
    csv.writer(buf).writerows([header, *rows])
    return buf.getvalue().encode()


def upload(data: bytes, h=None):
    return c.post(base, headers=h or sa_h, files={"file": ("dir.csv", data, "text/csv")})


with SessionLocal() as db:
    city, other = City(name=f"Imp-{tag}", name_i18n={"gu": f"ઇમ્પ-{tag}"}, state="T"), City(name=f"Imp2-{tag}", state="T")
    db.add_all([city, other])
    db.flush()
    pw = hash_password(secrets.token_hex(8))
    sa = AdminUser(role="SUPER_ADMIN", full_name="SA", email=f"dsa-{tag}@t.local", password_hash=pw)
    ca = AdminUser(role="CITY_ADMIN", city_id=city.city_id, full_name="CA", email=f"dca-{tag}@t.local", password_hash=pw)
    db.add_all([sa, ca])
    db.flush()
    hdrs = []
    for a in (sa, ca):
        token = secrets.token_urlsafe(32)
        db.add(AuthSession(admin_id=a.admin_id, refresh_token_hash=hash_token(token), mfa_verified=True,
                           last_activity_at=now, expires_at=now + timedelta(hours=1)))
        hdrs.append({"Authorization": f"Bearer {token}"})
    sa_h, ca_h = hdrs
    # a viewer: an active app member elsewhere
    vh = Household(household_id=uuid4(), city_id=other.city_id, family_name="Viewer")
    db.add(vh)
    db.flush()
    mob = f"+919{secrets.randbelow(10**9):09d}"
    viewer = Member(member_id=uuid4(), city_id=other.city_id, household_id=vh.household_id, is_household_head=True,
                    mobile_hash=mobile_hash(mob), mobile_enc=fernet.encrypt(mob.encode()), mobile_last4=mob[-4:],
                    full_name="Viewer", gender="MALE", dob=date(1980, 1, 1), status="ACTIVE")
    db.add(viewer)
    db.flush()
    member_h = {"Authorization": f"Bearer {_start_session(db, viewer)['access_token']}"}
    db.commit()
    city_ids, admin_ids, viewer_id = [city.city_id, other.city_id], [sa.admin_id, ca.admin_id], viewer.member_id

fam = f"Zx{tag}"
head_mobile = f"9{secrets.randbelow(10**9):09d}"
try:
    # template is the Super Admin's sheet; City Admins can't use these endpoints
    r = c.get(f"{base}/template", headers=sa_h, params={"file_format": "CSV"})
    assert r.status_code == 200 and r.content.decode("utf-8-sig").splitlines()[0] == ",".join(HEADERS), r.text
    assert c.get(f"{base}/template", headers=ca_h).status_code == 403
    assert upload(sheet([]), ca_h).status_code == 403

    # headers: spacing/case forgiven, a missing column refused
    assert upload(sheet([["x"]], HEADERS[:-1])).status_code == 400
    loose = [h.upper().replace(" / ", "/") for h in HEADERS]

    e = [""] * 8  # Gotra / Vatan .. Address left empty
    r = upload(sheet([
        [f"imp-{tag}", f"Ramesh {fam}", "Self", "Kashyap / Sojitra", "15/08/1975", "B.Com", "Married",
         "Business", "Reading", "B+", "12 Gandhi Road", head_mobile],  # 2 NEW head (city name any case)
        [f"Imp-{tag}", f"Sita {fam}", "Wife", "", "1979-03-02", "", "Married", "", "", "O+", "", ""],  # 3 NEW
        [f"Imp-{tag}", f"Kavi {fam}", "Daughter-in-law", *e, ""],  # 4 NEW
        [f"Imp-{tag}", f"Solo {fam}", "Self", *e, ""],  # 5 NEW head of a second family
        [f"Imp-{tag}", f"Mira {fam}", "Bhabhi", *e, ""],  # 6 NEW in Solo's family
        ["", "X", "Son", "", "31/02/1990", "", "", "", "", "", "", "123"],  # 7 ERROR
        [f"Imp-{tag}", f"mira  {fam}", "Bhabhi", *e, ""],  # 8 ERROR duplicate of 6
        [f"Imp2-{tag}", f"Away {fam}", "Son", *e, ""],  # 9 ERROR other city than its head
    ], loose))
    assert r.status_code == 201, r.text
    job = r.json()
    assert (job["city_id"], job["new_count"], job["updated_count"], job["error_count"]) == (None, 5, 0, 3), job
    jid = job["import_job_id"]
    rows = {x["row_number"]: x for x in c.get(f"{base}/{jid}/rows", headers=sa_h).json()["items"]}
    assert rows[2]["mobile_last4"] == head_mobile[-4:] and rows[3]["mobile_last4"] is None
    assert "Section (City)" in rows[7]["error_message"], rows[7]
    assert rows[8]["error_message"].startswith("Same person as row 6"), rows[8]
    assert "head's row 5" in rows[9]["error_message"], rows[9]
    # a family member with no head above, and members under a broken head row, are refused
    r = upload(sheet([[f"Imp-{tag}", "Lost", "Son", *e, ""], ["", "Bad Head", "Self", *e, ""],
                      [f"Imp-{tag}", "Orphan", "Wife", *e, ""]]))
    errs = [x["error_message"] for x in c.get(f"{base}/{r.json()['import_job_id']}/rows", headers=sa_h).json()["items"]]
    assert errs[0].startswith("No family head") and errs[2].startswith("No family head"), errs
    # a hand-made Gujarati sheet: blank leftover column, Gujarati city + relations, "-" for empty
    gu = lambda row: [row[0], "", *row[1:], "1"]  # noqa: E731 - blank column B, extra "Page" column
    # ...and a head with a bad Date of Birth / Mobile is still imported, those two left blank
    r = upload(sheet([gu([f"ઇમ્પ-{tag}", "અભય", "પોતે", "-", "80 વર્ષ", *[""] * 6, "9429020114 9484598232"]),
                      gu([f"ઇમ્પ-{tag}", "અલકા", "પત્ની", *e, ""]),
                      gu([f"ઇમ્પ-{tag}", "આયાં", "પુત્રવધૂ", *e, ""])], gu(HEADERS)))
    assert r.status_code == 201 and (r.json()["new_count"], r.json()["error_count"]) == (3, 0), r.text
    head = c.get(f"{base}/{r.json()['import_job_id']}/rows", headers=sa_h).json()["items"][0]
    assert head["mobile_last4"] is None and all(s in head["error_message"] for s in ("Date of Birth", "Mobile")), head
    # a city the app doesn't have yet: fine in the dry run, created (once) on commit
    r = upload(sheet([[f"Nyu-{tag}", f"Nav N{tag}", "Self", *e, ""], [f"NYU-{tag}", f"Nita N{tag}", "Wife", *e, ""]]))
    assert (r.json()["new_count"], r.json()["error_count"]) == (2, 0), r.json()
    with SessionLocal() as db:
        assert db.scalar(select(City).where(City.name == f"Nyu-{tag}")) is None  # dry run made nothing
    assert c.post(f"{base}/{r.json()['import_job_id']}/commit", headers=sa_h).status_code == 200
    with SessionLocal() as db:
        nyu = db.scalars(select(City).where(func.lower(City.name) == f"nyu-{tag}")).all()
        assert len(nyu) == 1, nyu
        city_ids.append(nyu[0].city_id)
        nav = db.scalar(select(FamilyMember).where(FamilyMember.full_name == f"Nita N{tag}"))
        assert db.get(Household, nav.household_id).city_id == nyu[0].city_id
    assert c.get(f"{base}/{jid}", headers=ca_h).status_code == 403
    assert c.get("/cityadmin/imports", headers=ca_h).json()["total"] == 0  # not in the City Admin's list

    r = c.post(f"{base}/{jid}/commit", headers=sa_h)
    assert r.status_code == 200 and r.json()["status"] == "COMMITTED", r.text
    assert c.post(f"{base}/{jid}/commit", headers=sa_h).status_code == 409

    with SessionLocal() as db:
        h7 = db.get(Household, db.scalar(select(FamilyMember.household_id)
                                         .where(FamilyMember.full_name == f"Ramesh {fam}")))
        assert h7.family_name == fam
        ppl = {f.full_name: f for f in db.scalars(select(FamilyMember).where(FamilyMember.household_id == h7.household_id))}
        assert set(ppl) == {f"Ramesh {fam}", f"Sita {fam}", f"Kavi {fam}"}
        assert (ppl[f"Sita {fam}"].relationship, ppl[f"Sita {fam}"].gender) == ("SPOUSE", "FEMALE")
        assert (ppl[f"Kavi {fam}"].relationship, ppl[f"Kavi {fam}"].gender) == ("DAUGHTER_IN_LAW", "FEMALE")
        assert all(f.status == "APPROVED" and f.requested_by_member_id is None for f in ppl.values())
        solo, mira = (db.scalar(select(FamilyMember).where(FamilyMember.full_name == f"{n} {fam}")) for n in ("Solo", "Mira"))
        assert (solo.relationship, mira.relationship, mira.gender) == ("SELF", "BHABHI", None)
        assert mira.household_id == solo.household_id != h7.household_id
        assert db.scalar(select(Member).where(Member.city_id == city_ids[0])) is None  # no app accounts made
        hid = str(h7.household_id)
    drain()

    # the app directory lists them, with phone and details
    r = c.get("/member/directory", headers=member_h, params={"family_name": fam})
    assert r.status_code == 200, r.text
    items = {i["full_name"]: i for i in r.json()["items"]}
    assert set(items) == {f"Ramesh {fam}", f"Sita {fam}", f"Kavi {fam}", f"Solo {fam}", f"Mira {fam}"}, items
    ramesh = items[f"Ramesh {fam}"]
    assert (ramesh["kind"], ramesh["is_household_head"], ramesh["phone"], ramesh["address"]) == (
        "RELATIVE", True, "+91" + head_mobile, "12 Gandhi Road"), ramesh
    assert (ramesh["gotra"], ramesh["education"], ramesh["occupation"], ramesh["blood_group"]) == (
        "Kashyap / Sojitra", "B.Com", "Business", "B+")
    assert items[f"Sita {fam}"]["phone"] is None
    r = c.get(f"/member/directory/households/{hid}", headers=member_h)
    assert r.status_code == 200 and [p["full_name"] for p in r.json()["people"]][0] == f"Ramesh {fam}", r.text

    # re-import: same head (name + mobile) finds the family; same name updates, a new name joins it
    r = upload(sheet([[f"Imp-{tag}", f"Ramesh {fam}", "Self", *e, head_mobile],
                      [f"Imp-{tag}", f"Sita {fam}", "Wife", "", "", "M.A.", "Married", "Teacher", "", "", "", ""],
                      [f"Imp-{tag}", f"Ravi {fam}", "Son", *e, ""]]))
    assert (r.json()["new_count"], r.json()["updated_count"]) == (1, 2), r.json()
    assert c.post(f"{base}/{r.json()['import_job_id']}/commit", headers=sa_h).status_code == 200
    with SessionLocal() as db:
        sita = db.scalar(select(FamilyMember).where(FamilyMember.full_name == f"Sita {fam}"))
        assert (sita.education, sita.occupation, str(sita.household_id)) == ("M.A.", "Teacher", hid)
        ravi = db.scalar(select(FamilyMember).where(FamilyMember.full_name == f"Ravi {fam}"))
        assert (str(ravi.household_id), ravi.gender) == (hid, "MALE")
    assert c.get(base, headers=sa_h).json()["total"] >= 2
    print("ok")
finally:
    with SessionLocal() as db:
        hids = select(Household.household_id).where(Household.city_id.in_(city_ids))
        file_keys = db.scalars(select(ImportJob.file_key).where(ImportJob.uploaded_by_admin_id.in_(admin_ids))).all()
        db.execute(delete(ImportJob).where(ImportJob.uploaded_by_admin_id.in_(admin_ids)))
        db.execute(delete(FamilyMember).where(FamilyMember.household_id.in_(hids)))
        db.execute(delete(Member).where(Member.member_id == viewer_id))
        db.execute(delete(Household).where(Household.city_id.in_(city_ids)))
        db.execute(delete(AdminUser).where(AdminUser.admin_id.in_(admin_ids)))
        db.execute(delete(City).where(City.city_id.in_(city_ids)))
        db.commit()
    for key in file_keys:
        private_files.delete(key)
