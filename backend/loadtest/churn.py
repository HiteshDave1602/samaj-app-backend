"""Writes during a load run: python -m loadtest.churn <seconds> <renames_per_second>
Renames random LoadCity members through the ORM, so each commit queues outbox events exactly as the app does;
the search worker must keep up while k6 searches. Prints how many it wrote."""
import random
import sys
import time

from sqlalchemy import select

from core.database import SessionLocal
from loadtest.seed import FEMALE, MALE, STATE
from member.profile.model import Member
from superadmin.city.model import City


def main(seconds: float, rate: float):
    with SessionLocal() as db:
        ids = db.scalars(select(Member.member_id).where(
            Member.city_id.in_(select(City.city_id).where(City.state == STATE)), Member.status == "ACTIVE")
            .limit(20000)).all()
    rnd, written, end = random.Random(), 0, time.monotonic() + seconds
    while time.monotonic() < end:
        tick = time.monotonic()
        with SessionLocal() as db:
            m = db.get(Member, rnd.choice(ids))
            first, rest = m.full_name.split(" ", 1)
            m.full_name = f"{rnd.choice(MALE if m.gender == 'MALE' else FEMALE)} {rest}"
            db.commit()  # the after_flush listener has queued member + household events in this transaction
        written += 1
        time.sleep(max(0.0, 1 / rate - (time.monotonic() - tick)))
    print(f"{written} renames in {seconds:.0f} s")


if __name__ == "__main__":
    main(float(sys.argv[1]), float(sys.argv[2]))
