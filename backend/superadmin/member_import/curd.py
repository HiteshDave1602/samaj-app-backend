"""Super Admin directory import. One sheet row = one person. A family is a Self (head) row and the rows below it,
up to the next Self row; it is matched again on later imports by city + the head's name and mobile.
People are added as approved relatives (family_member, no app account), so they show in the app directory with
their phone and details. To log in they register in the app; a member can also add them to their family tree.
The City Admin member import (cityadmin/member_import) is separate and unchanged; both share the job tables."""
import csv
import io
import json
import re
from collections import Counter
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import openpyxl
from fastapi import HTTPException
from sqlalchemy import func, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cityadmin.member_import.curd import MAX_BYTES, MAX_ROWS, _date, _job_out, _payload, _read
from cityadmin.member_import.model import ImportJob, ImportRow
from core import private_files
from core.security import fernet
from member.auth.schema import to_e164
from member.profile.model import FamilyMember, Household
from superadmin.audit_log import curd as audit
from superadmin.city.model import City
from superadmin.city_admin.model import AdminUser

TEMPLATE_VERSION = "dir-v1"  # also tells these jobs apart from City Admin member imports
HEADERS = ["Section (City)", "Name", "Relation", "Gotra / Vatan", "Date of Birth", "Education",
           "Marital Status", "Occupation", "Hobby", "Blood Group", "Address", "Mobile"]
KEYS = ["city", "full_name", "relation", "gotra", "dob", "education", "marital_status", "occupation",
        "hobby", "blood_group", "address", "mobile"]
EXAMPLES = [["Surat", "Ramesh Patel", "Self", "Kashyap / Sojitra", "15/08/1975", "B.Com", "Married",
             "Business", "Reading", "B+", "12 Gandhi Road", "9876543210"],
            ["Surat", "Sita Patel", "Wife", "Kashyap / Sojitra", "02/03/1979", "B.A.", "Married",
             "Homemaker", "Cooking", "O+", "12 Gandhi Road", ""]]
LIMITS = {"full_name": 120, "relation": 30, "gotra": 120, "education": 120, "marital_status": 30,
          "occupation": 120, "hobby": 200, "blood_group": 10, "address": 500}
# Relation -> (stored relationship, gender). Words not listed are kept as written, gender left empty.
RELATIONS = {
    "self": ("SELF", None), "head": ("SELF", None), "wife": ("SPOUSE", "FEMALE"), "husband": ("SPOUSE", "MALE"),
    "spouse": ("SPOUSE", None), "son": ("SON", "MALE"), "daughter": ("DAUGHTER", "FEMALE"),
    "father": ("FATHER", "MALE"), "mother": ("MOTHER", "FEMALE"), "brother": ("BROTHER", "MALE"),
    "sister": ("SISTER", "FEMALE"), "grandfather": ("GRANDFATHER", "MALE"), "grandmother": ("GRANDMOTHER", "FEMALE"),
    "grandson": ("GRANDSON", "MALE"), "granddaughter": ("GRANDDAUGHTER", "FEMALE"),
    "son in law": ("SON_IN_LAW", "MALE"), "daughter in law": ("DAUGHTER_IN_LAW", "FEMALE"),
    # Gujarati
    "પોતે": ("SELF", None), "પત્ની": ("SPOUSE", "FEMALE"), "પતિ": ("SPOUSE", "MALE"), "પુત્ર": ("SON", "MALE"),
    "દીકરો": ("SON", "MALE"), "પુત્રી": ("DAUGHTER", "FEMALE"), "દીકરી": ("DAUGHTER", "FEMALE"),
    "પિતા": ("FATHER", "MALE"), "માતા": ("MOTHER", "FEMALE"), "ભાઈ": ("BROTHER", "MALE"),
    "બહેન": ("SISTER", "FEMALE"), "દાદા": ("GRANDFATHER", "MALE"), "દાદી": ("GRANDMOTHER", "FEMALE"),
    "પૌત્ર": ("GRANDSON", "MALE"), "પૌત્રી": ("GRANDDAUGHTER", "FEMALE"), "જમાઈ": ("SON_IN_LAW", "MALE"),
    "પુત્રવધૂ": ("DAUGHTER_IN_LAW", "FEMALE"), "પુત્રવધુ": ("DAUGHTER_IN_LAW", "FEMALE"),
    "પૂત્રવધૂ": ("DAUGHTER_IN_LAW", "FEMALE"), "વહુ": ("DAUGHTER_IN_LAW", "FEMALE"), "દિકરી": ("DAUGHTER", "FEMALE"),
}


def _relation(s: str) -> str:
    return " ".join(s.replace("-", " ").replace("_", " ").split()).casefold()


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s).casefold()


def template(file_format: str) -> bytes:
    if file_format == "CSV":
        buf = io.StringIO()
        csv.writer(buf).writerows([HEADERS, *EXAMPLES])
        return buf.getvalue().encode("utf-8-sig")
    wb = openpyxl.Workbook()
    for r in [HEADERS, *EXAMPLES]:
        wb.active.append(r)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _is_head(cells: list[str]) -> bool:
    return len(cells) > 2 and RELATIONS.get(_relation(cells[2]), ("",))[0] == "SELF"


def _clean(cells: list[str], cities: dict[str, UUID]) -> tuple[dict | None, str | None]:
    # "-" means "nothing to fill in" in hand-made sheets
    v = {k: "" if c.strip() in ("-", "—") else " ".join(c.split()) for k, c in zip(KEYS, cells + [""] * len(KEYS))}
    errors = []
    # a city not in the app yet is created on commit; "new:<name>" stands in for its id until then
    city_id = cities.get(v["city"].casefold()) or (v["city"] and f"new:{v['city'].casefold()}")
    if not city_id:
        errors.append("Section (City) is required")
    for k, label in (("full_name", "Name"), ("relation", "Relation")):
        if not v[k]:
            errors.append(f"{label} is required")
    errors += [f"{HEADERS[KEYS.index(k)]} is limited to {n} characters" for k, n in LIMITS.items() if len(v[k]) > n]
    # a bad Date of Birth or Mobile doesn't drop the person (or, on a head row, their family): it's left blank
    notes = []
    dob = _date(v["dob"]) if v["dob"] else None
    if v["dob"] and (dob is None or not date(1900, 1, 1) <= dob <= date.today()):
        dob = None
        notes.append(f"Date of Birth '{v['dob']}' left blank (use a date like 15/08/1975)")
    mobile = None
    if v["mobile"]:
        try:
            mobile = to_e164(v["mobile"])
        except ValueError:
            notes.append(f"Mobile '{v['mobile']}' left blank (not a valid mobile number)")
    if any(cells[len(KEYS):]):
        errors.append("this row has values beyond the template's columns")
    if errors:
        return None, "; ".join(errors)
    relationship, gender = RELATIONS.get(_relation(v["relation"]),(v["relation"].upper().replace(" ", "_")[:30], None))
    return {**{k: v[k] or None for k in KEYS[3:11]}, "city_id": str(city_id), "city_name": v["city"],
            "full_name": v["full_name"], "relationship": relationship, "gender": gender, "mobile": mobile,
            "dob": dob and dob.isoformat(), "note": "; ".join(notes) or None}, None


def _existing(db: Session, keys: set[tuple[str, str]]) -> dict[tuple[str, str], tuple[UUID, set[str]]]:
    """(city_id, family_key) -> (household_id, casefolded names of the people already in it)."""
    out = {}
    pairs = [(UUID(c), f) for c, f in keys if not c.startswith("new:")]  # a city not created yet has no families
    for i in range(0, len(pairs), 1000):
        for h in db.execute(select(Household.household_id, Household.city_id, Household.family_key)
                            .where(tuple_(Household.city_id, Household.family_key).in_(pairs[i:i + 1000]))):
            out[(str(h.city_id), h.family_key)] = (h.household_id, set())
    by_id = {hid: names for hid, names in out.values()}
    if by_id:
        for hid, name in db.execute(select(FamilyMember.household_id, FamilyMember.full_name)
                                    .where(FamilyMember.household_id.in_(by_id))):
            by_id[hid].add(name.casefold())
    return out


def _cities(db: Session) -> dict[str, UUID]:
    """A city matches by its English name or any translated name (અમદાવાદ = Ahmedabad); active ones win."""
    out = {}
    for c in db.scalars(select(City).order_by(City.is_active)):  # inactive first, so active overwrite them
        for n in [c.name, *(c.name_i18n or {}).values()]:
            if n:
                out[n.casefold()] = c.city_id
    return out


def upload(db: Session, admin: AdminUser, filename: str, data: bytes) -> dict:
    """Validate into a dry-run report. Nothing touches the directory until commit()."""
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "The file is larger than 10 MB")
    file_format, rows = _read(filename, data)
    # read only the template's columns; blank or extra ones (e.g. "Page") are ignored
    wanted = {_norm(h) for h in HEADERS}
    keep = [i for i, h in enumerate(rows[0] if rows else []) if _norm(h) in wanted]
    rows = [[r[i] if i < len(r) else "" for i in keep] for r in rows]
    header = rows[0] if rows else []
    if [_norm(h) for h in header] != [_norm(h) for h in HEADERS]:
        raise HTTPException(400, f"Column headers must be: {', '.join(HEADERS)}. Download the template. "
                                 "Nothing was imported.")
    body = [(n, r) for n, r in enumerate(rows[1:], start=2) if any(r)]
    if not body:
        raise HTTPException(400, "The file has no rows")
    if len(body) > MAX_ROWS:
        raise HTTPException(400, f"At most {MAX_ROWS} rows per file; split it and upload the parts")

    cities = _cities(db)
    cleaned, first_row = [], {}  # (city, family_key, name) -> row it first appeared in
    head = None  # payload of the Self row the following rows belong to; None after a bad Self row
    for n, cells in body:
        payload, error = _clean(cells, cities)
        if payload and payload["relationship"] == "SELF":
            # ponytail: two heads with the same name and no mobile in one city merge; add an ID column if that happens
            payload["family_key"] = f"{payload['full_name'].casefold()}|{payload['mobile'] or ''}"[:200]
        elif payload and head is None:
            payload, error = None, "No family head above this row: put the head (Relation: Self) first"
        elif payload and payload["city_id"] != head["city_id"]:
            payload, error = None, f"Section (City) differs from the family head's row {head['row']}"
        elif payload:
            payload["family_key"] = head["family_key"]
        if payload:
            person = (payload["city_id"], payload["family_key"], payload["full_name"].casefold())
            if person in first_row:
                payload, error = None, f"Same person as row {first_row[person]} in this family"
            else:
                first_row[person] = n
        if (payload or {}).get("relationship") == "SELF":
            head = payload | {"row": n}
        elif error and _is_head(cells):
            head = None  # its family's rows would otherwise join the family above
        cleaned.append((n, payload, error))
    existing = _existing(db, {(c, f) for c, f, _ in first_row})

    job = ImportJob(import_job_id=uuid4(), city_id=None, uploaded_by_admin_id=admin.admin_id,
                    file_key=private_files.save(data), file_format=file_format, template_version=TEMPLATE_VERSION,
                    status="DRY_RUN_READY", total_rows=len(body))
    counts, import_rows = Counter(), []
    for n, payload, error in cleaned:
        if payload is None:
            outcome = "ERROR"
        else:
            known = existing.get((payload["city_id"], payload["family_key"]))
            outcome = "UPDATE" if known and payload["full_name"].casefold() in known[1] else "NEW"
        counts[outcome] += 1
        import_rows.append(ImportRow(import_job_id=job.import_job_id, row_number=n, outcome=outcome,
                                     error_message=error or (payload or {}).get("note"),  # note: what was left blank
                                     payload_enc=fernet.encrypt(json.dumps(payload).encode()) if payload else None))
    job.new_count, job.updated_count, job.error_count = counts["NEW"], counts["UPDATE"], counts["ERROR"]
    db.add(job)
    db.flush()
    db.add_all(import_rows)
    db.commit()
    return _job_out(job)


def _get_job(db: Session, job_id: UUID, lock: bool = False) -> ImportJob:
    job = db.get(ImportJob, job_id, with_for_update=lock)
    if job is None or job.template_version != TEMPLATE_VERSION:
        raise HTTPException(404, "Import not found")
    return job


def get_job(db: Session, job_id: UUID) -> dict:
    return _job_out(_get_job(db, job_id))


def list_jobs(db: Session, limit: int, offset: int) -> dict:
    q = select(ImportJob).where(ImportJob.template_version == TEMPLATE_VERSION)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    jobs = db.scalars(q.order_by(ImportJob.created_at.desc()).limit(limit).offset(offset))
    return {"total": total, "items": [_job_out(j) for j in jobs]}


def list_rows(db: Session, job_id: UUID, limit: int, offset: int, outcome: str | None = None) -> dict:
    _get_job(db, job_id)
    q = select(ImportRow).where(ImportRow.import_job_id == job_id)
    if outcome:
        q = q.where(ImportRow.outcome == outcome)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    items = []
    for r in db.scalars(q.order_by(ImportRow.row_number).limit(limit).offset(offset)):
        p = _payload(r)
        items.append({c.name: getattr(r, c.name) for c in ImportRow.__table__.columns} | {
            "full_name": p and p["full_name"], "mobile_last4": p and p["mobile"] and p["mobile"][-4:]})
    return {"total": total, "items": items}


def _fill(fm: FamilyMember, p: dict):
    fm.full_name, fm.relationship, fm.gender = p["full_name"], p["relationship"], p["gender"]
    fm.dob = date.fromisoformat(p["dob"]) if p["dob"] else None
    fm.mobile_enc = fernet.encrypt(p["mobile"].encode()) if p["mobile"] else None
    fm.address_enc = fernet.encrypt(p["address"].encode()) if p["address"] else None
    for k in ("gotra", "education", "marital_status", "occupation", "hobby", "blood_group"):
        setattr(fm, k, p[k])


def commit(db: Session, admin: AdminUser, actor: audit.Actor, job_id: UUID) -> dict:
    """NEW rows become approved relatives in their family's household; UPDATE rows overwrite the person."""
    job = _get_job(db, job_id, lock=True)  # lock: a double-click can't import twice
    if job.status != "DRY_RUN_READY":
        raise HTTPException(409, f"This import is already {job.status}")
    now = datetime.now(timezone.utc)
    rows = db.scalars(select(ImportRow).where(ImportRow.import_job_id == job_id,
                                              ImportRow.outcome.in_(("NEW", "UPDATE")))
                      .order_by(ImportRow.row_number)).all()
    payloads = [(r, _payload(r)) for r in rows]
    # create the cities this file names that the app doesn't have yet (or that were added since the dry run)
    cities, new_cities = _cities(db), []
    for r, p in payloads:
        if p["city_id"].startswith("new:"):
            key = p["city_name"].casefold()
            if key not in cities:
                # ponytail: state left blank, the sheet has none; the Super Admin fills it in Cities
                city = City(city_id=uuid4(), name=p["city_name"][:80], state="")
                db.add(city)
                new_cities.append(city.name)
                cities[key] = city.city_id
            p["city_id"] = str(cities[key])
    db.flush()  # cities before the households pointing at them (no relationship() orders the inserts)
    families = {}  # (city_id, family_key) -> payloads, file order
    for r, p in payloads:
        families.setdefault((p["city_id"], p["family_key"]), []).append(p)
    existing = _existing(db, set(families))
    households, people = {}, {}  # households: key -> Household; people: (household_id, name) -> FamilyMember
    for key, ps in families.items():
        if key in existing:
            households[key] = db.get(Household, existing[key][0])
            continue
        head = next((p for p in ps if p["relationship"] == "SELF"), ps[0])
        # ponytail: family name = the head's last name word; add a Family Name column if surnames come first
        households[key] = Household(household_id=uuid4(), city_id=UUID(key[0]), family_key=key[1],
                                    family_name=head["full_name"].split()[-1])
    hids = [h.household_id for h in households.values()]
    for fm in db.scalars(select(FamilyMember).where(FamilyMember.household_id.in_(hids))) if hids else []:
        people[(fm.household_id, fm.full_name.casefold())] = fm
    created = updated = 0
    try:
        db.add_all([h for k, h in households.items() if k not in existing])
        db.flush()  # households before the people pointing at them
        for r, p in payloads:
            h = households[(p["city_id"], p["family_key"])]
            fm = people.get((h.household_id, p["full_name"].casefold()))
            if fm is None:
                fm = FamilyMember(household_id=h.household_id, status="APPROVED", reviewed_by_admin_id=admin.admin_id,
                                  reviewed_at=now)
                db.add(fm)
                people[(h.household_id, p["full_name"].casefold())] = fm
                created += 1
            else:
                updated += 1
            _fill(fm, p)
            r.resolution = "APPLIED"
        job.status, job.committed_at = "COMMITTED", now
        audit.log(db, actor, "DIRECTORY_IMPORT", "import_job", job_id, None, None, {
            "created": created, "updated": updated, "households": len(households), "errors": job.error_count,
            "cities_created": new_cities})
        db.commit()
    except IntegrityError:  # the same family created by another import since the dry run
        db.rollback()
        raise HTTPException(409, "The directory changed since this file was checked. Upload it again.")
    return _job_out(job)
