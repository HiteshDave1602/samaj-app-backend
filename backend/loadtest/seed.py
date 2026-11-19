"""Synthetic community for load tests (docs/search.md, "Load testing"). Never run it against production.

    python -m loadtest.seed --members 50000     households, members, relatives, matrimony profiles in LoadCity 1..10
    python -m loadtest.seed --tokens 1000       fresh member access tokens for k6 (they live 15 minutes)
    python -m loadtest.seed --drop              remove everything it created

Rows go in with bulk inserts, which skip the ORM flush and so the search outbox: run
`python -m search.reindex` afterwards; that is the initial-indexing test.
Every 100th member is ARCHIVED or PENDING and named Zzhidden...: no search may ever return one.
"""
import argparse
import json
import random
import time
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, insert, select

from core.database import SessionLocal
from core.security import fernet
from core.translit import localized
from member.auth.curd import _seal, mobile_hash
from member.matrimony.model import MatrimonyProfile
from member.profile.model import FamilyMember, Household, Member
from superadmin.city.model import City

OUT = Path(__file__).parent / ".out"  # gitignored: tokens are live credentials
STATE = "LT"  # LoadCity rows are recognised by this state code
MALE = ["Rahul", "Amit", "Nilesh", "Hitesh", "Jignesh", "Ketan", "Mehul", "Paresh", "Bhavesh", "Chirag", "Dhaval",
        "Hardik", "Kamlesh", "Manish", "Nikhil", "Parth", "Rakesh", "Sanjay", "Tushar", "Vipul", "Yash", "Harsh",
        "Kunal", "Mitesh", "Pratik", "Jayesh", "Alpesh", "Mukesh", "Dinesh", "Sagar"]
FEMALE = ["Priya", "Asha", "Bina", "Dipti", "Ekta", "Falguni", "Hetal", "Jalpa", "Kinjal", "Komal", "Mansi", "Nisha",
          "Pooja", "Riddhi", "Sejal", "Shital", "Trupti", "Urvi", "Vaishali", "Krupa", "Heena", "Bhumi", "Jinal",
          "Rupal", "Darshana", "Nidhi", "Payal", "Rekha", "Sonal", "Varsha"]
SURNAMES = ["Patel", "Shah", "Mehta", "Desai", "Joshi", "Parikh", "Trivedi", "Pandya", "Bhatt", "Modi", "Gandhi",
            "Thakkar", "Soni", "Vyas", "Dave", "Raval", "Chauhan", "Rana", "Solanki", "Parmar", "Panchal", "Sheth",
            "Doshi", "Kothari", "Vora", "Mistry", "Prajapati", "Jani", "Upadhyay", "Acharya"]
PLACES = ["Surat", "Rajkot", "Bhavnagar", "Jamnagar", "Junagadh", "Anand", "Nadiad", "Mehsana", "Palanpur", "Bhuj"]
JOBS = ["Engineer", "Doctor", "Teacher", "Accountant", "Lawyer", "Designer", "Pharmacist", "Banker", "Architect",
        "Software Developer", "Business Owner", "Chartered Accountant"]
EDU = ["SCHOOL", "DIPLOMA", "GRADUATE", "POSTGRADUATE", "DOCTORATE", "OTHER"]
RELATIONS = [("SON", "MALE"), ("DAUGHTER", "FEMALE"), ("FATHER", "MALE"), ("MOTHER", "FEMALE")]
_i18n: dict = {}


def i18n(text: str) -> dict:
    if text not in _i18n:
        _i18n[text] = localized(text)
    return _i18n[text]


def seed(n_members: int):
    rnd = random.Random(42)
    started = time.perf_counter()
    with SessionLocal() as db:
        cities = [{"city_id": uuid4(), "name": f"LoadCity {i}", "state": STATE} for i in range(1, 11)]
        db.execute(insert(City), [c | {"name_i18n": i18n(c["name"])} for c in cities])
        households, members, relatives, profiles = [], [], [], []
        while len(members) < n_members:
            city, surname = rnd.choice(cities)["city_id"], rnd.choice(SURNAMES)
            hid, place = uuid4(), rnd.choice(PLACES)
            households.append({"household_id": hid, "city_id": city, "family_name": surname,
                               "family_name_i18n": i18n(surname), "native_place": place,
                               "native_place_i18n": i18n(place)})
            father = rnd.choice(MALE)
            for k in range(rnd.choice((1, 2, 2, 3, 3, 4))):
                gender = rnd.choice(("MALE", "FEMALE"))
                first = rnd.choice(MALE if gender == "MALE" else FEMALE)
                n = len(members)
                status = "ACTIVE" if n % 100 else rnd.choice(("ARCHIVED", "PENDING"))
                name = f"{first} {father} {surname}" if status == "ACTIVE" else f"Zzhidden {first} {surname}"
                mobile = f"+917{n:09d}"
                dob = date(1950, 1, 1) + timedelta(days=rnd.randrange(54 * 365))
                members.append({
                    "member_id": uuid4(), "city_id": city, "household_id": hid, "is_household_head": k == 0,
                    "mobile_hash": mobile_hash(mobile), "mobile_enc": fernet.encrypt(mobile.encode()),
                    "mobile_last4": mobile[-4:], "full_name": name, "full_name_i18n": i18n(name), "gender": gender,
                    "dob": dob, "address_enc": fernet.encrypt(f"{n} Load Street, {place}".encode()),
                    "status": status, "source": "IMPORT", "rejection_reason": None})
                age = (date.today() - dob).days // 365
                if status == "ACTIVE" and 21 <= age <= 38 and rnd.random() < 0.35:
                    profiles.append({"profile_id": uuid4(), "member_id": members[-1]["member_id"],
                                     "location_city_id": city, "education_level": rnd.choice(EDU),
                                     "family_background": rnd.choice(("JOINT", "NUCLEAR")),
                                     "occupation": rnd.choice(JOBS), "gotra": rnd.choice(("Kashyap", "Bharadwaj",
                                                                                          "Vashishtha", None)),
                                     "status": "APPROVED"})
            for _ in range(rnd.choice((0, 0, 1, 1, 2, 3))):
                relation, gender = rnd.choice(RELATIONS)
                name = f"{rnd.choice(MALE if gender == 'MALE' else FEMALE)} {surname}"
                relatives.append({"household_id": hid, "requested_by_member_id": members[-1]["member_id"],
                                  "full_name": name, "full_name_i18n": i18n(name), "relationship": relation,
                                  "gender": gender, "status": "APPROVED"})
        for model, rows in ((Household, households), (Member, members), (FamilyMember, relatives),
                            (MatrimonyProfile, profiles)):
            for i in range(0, len(rows), 2000):
                db.execute(insert(model), rows[i:i + 2000])
            print(f"  {model.__tablename__}: {len(rows)}", flush=True)
        db.commit()
    print(f"seeded in {time.perf_counter() - started:.0f} s; now run: python -m search.reindex")


def tokens(n: int):
    """Access tokens for n random ACTIVE load members, plus one PENDING member's (expected 403)."""
    with SessionLocal() as db:
        load = select(City.city_id).where(City.state == STATE)
        active = db.scalars(select(Member.member_id).where(Member.city_id.in_(load), Member.status == "ACTIVE")
                            .order_by(Member.member_id).limit(n)).all()
        pending = db.scalar(select(Member.member_id).where(Member.city_id.in_(load), Member.status == "PENDING"))
        cities = [str(c) for c in db.scalars(load)]
    seal = lambda m: _seal("access", sid=str(uuid4()), mid=str(m))  # noqa: E731  (members are not checked for a session)
    OUT.mkdir(exist_ok=True)
    words = {"first": MALE + FEMALE, "surnames": SURNAMES, "places": PLACES, "jobs": JOBS, "edu": EDU,
             "cities": cities, "gu_first": [i18n(f)["gu"] for f in MALE + FEMALE],
             "pending_token": seal(pending)}
    (OUT / "tokens.json").write_text(json.dumps([seal(m) for m in active]), encoding="utf-8")
    (OUT / "words.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    print(f"{len(active)} tokens -> {OUT / 'tokens.json'} (valid 15 minutes)")


def drop():
    with SessionLocal() as db:
        load = select(City.city_id).where(City.state == STATE)
        hh = select(Household.household_id).where(Household.city_id.in_(load))
        members = select(Member.member_id).where(Member.city_id.in_(load))
        db.execute(delete(MatrimonyProfile).where(MatrimonyProfile.member_id.in_(members)))
        db.execute(delete(FamilyMember).where(FamilyMember.household_id.in_(hh)))
        db.execute(delete(Member).where(Member.city_id.in_(load)))
        db.execute(delete(Household).where(Household.city_id.in_(load)))
        db.execute(delete(City).where(City.state == STATE))
        db.commit()
    print("dropped; run python -m search.reindex --rebuild to clear their documents")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--members", type=int)
    p.add_argument("--tokens", type=int)
    p.add_argument("--drop", action="store_true")
    a = p.parse_args()
    if a.drop:
        drop()
    if a.members:
        seed(a.members)
    if a.tokens:
        tokens(a.tokens)
