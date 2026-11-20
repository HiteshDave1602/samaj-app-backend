"""Search engine end to end (docs/search.md): python test_search.py   (needs ELASTICSEARCH_URL)
Outbox sync, matching, filters, sorting, paging, visibility, versioning, retries and dead events, ES downtime,
rebuild with replay, rate limit, status page, concurrent searches while indexing.
Uses its own indexes (prefix samaj_test_<tag>), deleted at the end. Stop any running search worker first: it would
apply this test's events to the dev indexes instead. Cleans up its rows."""
import os
import secrets

tag = secrets.token_hex(4)
os.environ["ELASTICSEARCH_INDEX_PREFIX"] = f"samaj_test_{tag}"  # before core.config reads it

import json  # noqa: E402
import socket  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402
from datetime import date, datetime, timedelta, timezone  # noqa: E402
from uuid import uuid4  # noqa: E402

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from elasticsearch import Elasticsearch  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete, func, select, update  # noqa: E402

from auth.curd import hash_token  # noqa: E402
from auth.model import AuthSession  # noqa: E402
from core.config import settings  # noqa: E402
from core.database import SessionLocal  # noqa: E402
from core.security import fernet, hash_password  # noqa: E402
from core.translit import localized  # noqa: E402
from main import app  # noqa: E402
from member.auth.curd import _start_session, mobile_hash  # noqa: E402
from member.directory import search as directory  # noqa: E402
from member.matrimony import search as matrimony  # noqa: E402
from member.matrimony.model import MatrimonyProfile  # noqa: E402
from member.profile.model import FamilyMember, Household, Member  # noqa: E402
from search import es, sync  # noqa: E402
from search.outbox import SearchOutbox  # noqa: E402
from superadmin.city.model import City  # noqa: E402
from superadmin.city_admin.model import AdminUser  # noqa: E402

assert es.enabled(), "set ELASTICSEARCH_URL"
c = TestClient(app)
now = datetime.now(timezone.utc)
fam = f"Zq{tag}"
D, MAT = "/member/directory", "/member/matrimony/profiles"
DIR, MATI = es.alias("directory"), es.alias("matrimony")
dead_es = Elasticsearch("http://127.0.0.1:9", request_timeout=1, max_retries=0)  # nothing listens on port 9


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def new_member(db, city, household, name, status="ACTIVE", head=False, gender="MALE"):
    mobile = f"+919{secrets.randbelow(10**9):09d}"
    m = Member(member_id=uuid4(), city_id=city.city_id, household_id=household.household_id, is_household_head=head,
               mobile_hash=mobile_hash(mobile), mobile_enc=fernet.encrypt(mobile.encode()), mobile_last4=mobile[-4:],
               full_name=name, gender=gender, dob=date(1996, 3, 1), status=status,
               address_enc=fernet.encrypt(b"12 Secret Street"))
    db.add(m)
    db.flush()
    return m, mobile


def set_member(member_id, **values):
    with SessionLocal() as db:
        m = db.get(Member, member_id)
        for k, v in values.items():
            setattr(m, k, v)
        db.commit()


with SessionLocal() as db:
    x, y = City(name=f"SrchX-{tag}", state="T"), City(name=f"SrchY-{tag}", state="T")
    db.add_all([x, y])
    db.flush()
    hx = Household(household_id=uuid4(), city_id=x.city_id, family_name=f"{fam} Mehta")
    hy = Household(household_id=uuid4(), city_id=y.city_id, family_name=f"{fam} Patel")
    hs = Household(household_id=uuid4(), city_id=y.city_id, family_name=f"Other{tag}")
    db.add_all([hx, hy, hs])
    db.flush()
    rahul, rahul_mobile = new_member(db, x, hx, f"Rahul {fam}", head=True)
    priya, _ = new_member(db, x, hx, f"Priya {fam}", gender="FEMALE")
    neel, _ = new_member(db, y, hy, f"Neel {fam}", head=True)
    pend, _ = new_member(db, y, hy, f"Pending {fam}", status="PENDING")
    searcher, _ = new_member(db, y, hs, f"Searcher Other{tag}", head=True)
    db.add(FamilyMember(household_id=hx.household_id, requested_by_member_id=rahul.member_id,
                        full_name=f"Arjun {fam}", relationship="SON", gender="MALE", status="APPROVED"))
    db.add_all([MatrimonyProfile(member_id=priya.member_id, location_city_id=x.city_id, education_level="GRADUATE",
                                 family_background="JOINT", occupation="Engineer", gotra="Kashyap", status="APPROVED"),
                MatrimonyProfile(member_id=neel.member_id, location_city_id=y.city_id, education_level="DOCTORATE",
                                 family_background="NUCLEAR", occupation="Doctor", status="APPROVED")])
    sa = AdminUser(role="SUPER_ADMIN", full_name="SA", email=f"srch-{tag}@t.local",
                   password_hash=hash_password(secrets.token_hex(8)))
    db.add(sa)
    db.flush()
    sa_token = secrets.token_urlsafe(32)
    db.add(AuthSession(admin_id=sa.admin_id, refresh_token_hash=hash_token(sa_token), mfa_verified=True,
                       last_activity_at=now, expires_at=now + timedelta(hours=1)))
    db.commit()
    ids = {k: v.member_id for k, v in
           {"rahul": rahul, "priya": priya, "neel": neel, "pend": pend, "searcher": searcher}.items()}
    s_h, n_h = (bearer(_start_session(db, m)["access_token"]) for m in (searcher, neel))
    city_ids, sa_id, sa_h, hx_id = [x.city_id, y.city_id], sa.admin_id, bearer(sa_token), hx.household_id

get = lambda h=s_h, **p: c.get(D, headers=h, params=p)  # noqa: E731
names_of = lambda j: [i["full_name"].removesuffix(f" {fam}") for i in j["items"]]  # noqa: E731
names = lambda r: names_of(r.json())  # noqa: E731


def mat(h=s_h, **p) -> set[str]:
    r = c.get(MAT, headers=h, params={"city_id": [str(i) for i in city_ids]} | p)
    assert r.status_code == 200, r.text
    return {i["full_name"].removesuffix(f" {fam}") for i in r.json()["items"]}


def events_for(member_id) -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).where(SearchOutbox.entity_id == member_id))


ghost_id = uuid4()  # set below; here so cleanup can always name it
try:
    sync.drain()  # creates the test indexes and applies the fixtures' events

    # connection, index creation: versioned physical index behind the alias, strict mapping
    assert es.health() in ("green", "yellow")
    for spec in sync.INDEXES:
        index = es.current(spec)
        assert index.startswith(f"samaj_test_{tag}_{spec.NAME}_v{spec.VERSION}_"), index
        mapping = es.client().indices.get_mapping(index=index)[index]["mappings"]
        assert mapping["dynamic"] == "strict" and mapping["_meta"]["version"] == spec.VERSION, mapping

    # outbox: written in the business transaction; a rollback leaves none; unrelated columns send none
    with SessionLocal() as db:
        ghost, _ = new_member(db, db.get(City, city_ids[0]), db.get(Household, hx_id), f"Ghost {fam}")
        ghost_id = ghost.member_id
        db.rollback()
    assert events_for(ids["rahul"]) >= 1 and events_for(ghost_id) == 0
    before = events_for(ids["rahul"])
    set_member(ids["rahul"], last_login_at=now)
    assert events_for(ids["rahul"]) == before

    # documents hold search fields only: no phone, address, DOB
    doc = es.client().get(index=DIR, id=f"MEMBER:{ids['rahul']}")["_source"]
    assert set(doc) <= set(directory.PROPERTIES) and rahul_mobile not in json.dumps(doc) and "Secret" not in str(doc)
    mdoc = es.client().get(index=MATI, id=es.search("matrimony", query={"match_all": {}}, size=1)[0]["_id"])["_source"]
    assert set(mdoc) <= set(matrimony.PROPERTIES) and "biodata" not in str(mdoc), mdoc

    # who is listed: active members + approved relatives; pending never. Sorted by name.
    assert names(get(family_name=fam)) == ["Arjun", "Neel", "Priya", "Rahul"]
    # substring, any case; typo; Gujarati and Hindi spellings
    assert names(get(name=f"AHUL {fam[:4].lower()}")) == ["Rahul"]
    assert names(get(name="Rahl", family_name=fam)) == ["Rahul"]  # one letter missing
    assert names(get(name="Pryia", family_name=fam)) == ["Priya"]  # two letters swapped
    assert names(get(name=localized(f"Rahul {fam}")["gu"].split()[0], family_name=fam)) == ["Rahul"]
    assert names(get(family_name=localized(f"{fam} Mehta")["hi"])) == ["Arjun", "Priya", "Rahul"]
    # filters combine; wildcards are literal; validation
    assert names(get(family_name=fam, city_id=str(city_ids[1]))) == ["Neel"]
    assert get(name="*" + tag).json()["suggested"] and get(name=f"?ahul {fam}").json()["suggested"]  # no exact match
    # misspelt past typo distance (first letter wrong): closest names instead of nothing, on ES and on Postgres
    for down in (0, time.monotonic() + 60):
        es._down_until = down
        r = get(name="Pahul", family_name=fam).json()
        assert r["suggested"] and names_of(r)[:1] == ["Rahul"] and r["next_offset"] is None, (down, r)
        m = c.get(MAT, headers=s_h, params={"q": "Gashyap"}).json()
        assert m["suggested"] and [i["full_name"].removesuffix(f" {fam}") for i in m["items"]][:1] == ["Priya"], m
    es._down_until = 0
    assert not get(name="Rahul", family_name=fam).json()["suggested"]
    assert get(name="R").status_code == 422 and get(limit=51).status_code == 422
    # offset paging
    p1, p2 = get(family_name=fam, limit=2).json(), get(family_name=fam, limit=2, offset=2).json()
    assert [i["full_name"] for i in p1["items"] + p2["items"]] == [f"{n} {fam}" for n in ("Arjun", "Neel", "Priya", "Rahul")]
    assert (p1["next_offset"], p2["next_offset"]) == (2, None), (p1, p2)
    # response identical to the Postgres search's, decrypted phone included
    es_items = get(family_name=fam).json()["items"]
    es._down_until = time.monotonic() + 60  # force the Postgres path
    pg_items = get(family_name=fam).json()["items"]
    es._down_until = 0
    assert es_items == pg_items, (es_items, pg_items)

    # matrimony: filters, never your own, free text with typos / prefixes / Gujarati, keyset paging
    assert mat() == {"Priya", "Neel"} and mat(n_h) == {"Priya"}
    assert mat(q="Enginer") == {"Priya"} and mat(q="engi") == {"Priya"} and mat(q="kashyap") == {"Priya"}
    assert mat(q=localized(f"Priya {fam}")["gu"].split()[0]) == {"Priya"}
    assert mat(q="Doctor", gender="MALE") == {"Neel"} and mat(q="Doctor", gender="FEMALE") == set()
    assert mat(education_level="DOCTORATE") == {"Neel"} and mat(age_min=40) == set()
    assert c.get(MAT, headers=s_h, params={"q": "x"}).status_code == 422
    seen, after = [], None
    while True:
        page = c.get(MAT, headers=s_h, params={"city_id": [str(i) for i in city_ids], "limit": 1}
                     | ({"after": after} if after else {})).json()
        seen += [i["profile_id"] for i in page["items"]]
        if not (after := page["next_after"]):
            break
    assert len(seen) == 2 and seen == sorted(seen), seen

    # a stale document never shows: PG re-checks every hit
    es.client().index(index=DIR, id=f"MEMBER:{ids['pend']}", refresh=True, document={
        "kind": "MEMBER", "id": str(ids["pend"]), "city_id": str(city_ids[1]), "full_name": f"Pending {fam}",
        "family_name": f"{fam} Patel"})
    assert names(get(family_name=fam)) == ["Arjun", "Neel", "Priya", "Rahul"]

    # updates and deletes flow through the outbox
    set_member(ids["rahul"], full_name=f"Rohan {fam}")
    set_member(ids["priya"], status="ARCHIVED")
    sync.drain()
    assert names(get(name="Rohan", family_name=fam)) == ["Rohan"] and names(get(name="Rahul", family_name=fam)) == []
    assert not es.client().exists(index=DIR, id=f"MEMBER:{ids['priya']}")
    assert mat() == {"Neel"}  # her matrimony document went with her
    set_member(ids["rahul"], status="ARCHIVED")  # the household's last active member...
    sync.drain()
    assert names(get(family_name=fam)) == ["Neel"]  # ...so its relative Arjun is unlisted too

    # versions: an older event can't overwrite or delete what ES got from a newer one; re-applying is harmless
    stray = f"MEMBER:{uuid4()}"
    es.client().index(index=DIR, id=stray, version=10**12, version_type="external", refresh=True,
                      document={"kind": "MEMBER", "id": stray[7:], "full_name": "Stray"})
    with SessionLocal() as db:
        assert sync.apply(db, [(5, "member", stray[7:])]) == {} == sync.apply(db, [(5, "member", stray[7:])])
    assert es.client().exists(index=DIR, id=stray)

    # retries with backoff, then dead after MAX_ATTEMPTS; --retry-dead re-queues
    set_member(ids["neel"], full_name=f"Neel B {fam}")
    real, es._client = es._client, dead_es
    try:
        with SessionLocal() as db:
            sync.process_batch(db)
        with SessionLocal() as db:
            pending = db.scalars(select(SearchOutbox).where(SearchOutbox.entity_id == ids["neel"],
                                                            SearchOutbox.processed_at.is_(None))).all()
            assert pending and all(e.attempts == 1 and "Connection" in e.last_error and e.next_attempt_at > now
                                   for e in pending), [(e.attempts, e.last_error) for e in pending]
            db.execute(update(SearchOutbox).where(SearchOutbox.id.in_([e.id for e in pending]))
                       .values(attempts=sync.MAX_ATTEMPTS - 1, next_attempt_at=func.now()))
            db.commit()
            sync.process_batch(db)
            assert sync.outbox_stats(db)["dead"] >= len(pending)
            assert db.scalar(select(func.count()).where(SearchOutbox.entity_id == ids["neel"],
                                                         SearchOutbox.dead_at.is_not(None))) == len(pending)
    finally:
        es._client = real
    with SessionLocal() as db:
        assert sync.retry_dead(db) >= len(pending)
    sync.drain()
    assert names(get(family_name=fam)) == ["Neel B"]

    # ES down: same answer from Postgres, health says degraded, the breaker skips ES for a while
    real, es._client = es._client, dead_es
    try:
        assert names(get(family_name=fam)) == ["Neel B"] and mat() == {"Neel B"}
        assert mat(q="doctor") == {"Neel B"} and mat(q="doctr") == {"Neel B"}  # substring, else closest (trigram)
        snap = es.snapshot()
        assert snap["fallback"] >= 1 and snap["postgres_only_for_s"] > 0, snap
        assert c.get("/health").json() == {"status": "ok", "search": "degraded"}
        get(family_name=fam)
        assert es.snapshot()["fallback"] == snap["fallback"]  # not even tried
    finally:
        es._client, es._down_until = real, 0

    # rate limit per member
    settings.search_rate_per_minute, es._window[:] = 3, [0, {}]
    codes = [get(family_name=fam).status_code for _ in range(6)]
    settings.search_rate_per_minute = 60
    assert 429 in codes and codes[0] == 200, codes

    # status page: Super Admin only
    assert c.get("/superadmin/search/status", headers=n_h).status_code == 401
    st = c.get("/superadmin/search/status", headers=sa_h).json()
    assert st["enabled"] and st["cluster"]["status"] in ("green", "yellow"), st
    assert st["indexes"]["directory"]["documents"] >= 1 and set(st["cluster"]["rejected"]) == {"search", "write"}, st
    assert {"pending", "retrying", "dead", "oldest_pending_s"} == set(st["outbox"]), st

    # backfill: re-running is idempotent (event-written copies win) and nothing fails
    with SessionLocal() as db:
        assert sync.backfill(db, directory, es.current(directory))[1] == 0

    # rebuild: new index, alias switched atomically, stale/stray documents gone, and a change the worker applied
    # to the old index during the copy is replayed into the new one
    old, original_batch = es.current(directory), directory.batch

    def batch_then_change(db, after, size):
        rows = original_batch(db, after, size)
        if after is None:
            set_member(ids["neel"], full_name=f"Neel C {fam}")
            with SessionLocal() as s:
                sync.process_batch(s)  # the worker, writing to the old index mid-copy
        return rows

    directory.batch = batch_then_change
    try:
        assert sync.rebuild(directory)
    finally:
        directory.batch = original_batch
    new = es.current(directory)
    assert new != old and not es.client().indices.exists(index=old), (old, new)
    assert not es.client().exists(index=DIR, id=stray) and not es.client().exists(index=DIR, id=f"MEMBER:{ids['pend']}")
    assert es.client().get(index=DIR, id=f"MEMBER:{ids['neel']}")["_source"]["full_name"] == f"Neel C {fam}"
    assert names(get(family_name=fam)) == ["Neel C"]

    # concurrent searches on a real server while the index is being written
    settings.search_rate_per_minute = 10**6
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    stop = threading.Event()

    def writer():  # flips an indexed field that doesn't change these results, and indexes it, over and over
        n = 0
        while not stop.is_set():
            n += 1
            set_member(ids["neel"], gender=("MALE", "OTHER")[n % 2])
            sync.drain()

    def one(i):
        r = httpx.get(f"http://127.0.0.1:{port}{D}", params={"family_name": fam}, headers=(s_h, n_h)[i % 2],
                      timeout=15)
        return r.status_code, names(r) if r.status_code == 200 else r.text

    w = threading.Thread(target=writer)
    w.start()
    started = time.perf_counter()
    try:
        with ThreadPoolExecutor(25) as pool:
            results = list(pool.map(one, range(500)))
    finally:
        stop.set()
        w.join()
        server.should_exit = True
    took = time.perf_counter() - started
    bad = [r for r in results if r != (200, ["Neel C"])]
    assert not bad, bad[:3]
    print(f"ok (500 searches from 25 threads while indexing: {took:.1f} s, {500 / took:.0f}/s)")
finally:
    settings.search_rate_per_minute = 60
    try:
        for index in es.client().indices.get(index=f"samaj_test_{tag}_*"):
            es.client().indices.delete(index=index)
    finally:
        es.close()
    with SessionLocal() as db:
        households = select(Household.household_id).where(Household.city_id.in_(city_ids))
        touched = [*ids.values(), ghost_id, *db.scalars(households),  # this test's outbox events only
                   *db.scalars(select(FamilyMember.family_member_id).where(FamilyMember.household_id.in_(households))),
                   *db.scalars(select(MatrimonyProfile.profile_id).where(MatrimonyProfile.member_id.in_(ids.values())))]
        db.execute(delete(MatrimonyProfile).where(MatrimonyProfile.member_id.in_(ids.values())))
        db.execute(delete(FamilyMember).where(FamilyMember.household_id.in_(households)))
        db.execute(delete(Member).where(Member.city_id.in_(city_ids)))
        db.execute(delete(Household).where(Household.city_id.in_(city_ids)))
        db.execute(delete(AdminUser).where(AdminUser.admin_id == sa_id))
        db.execute(delete(City).where(City.city_id.in_(city_ids)))
        db.execute(delete(SearchOutbox).where(SearchOutbox.entity_id.in_(touched)))
        db.commit()
