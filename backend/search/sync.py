"""Keeps the search indexes in line with Postgres: applies outbox events, backfills, rebuilds (docs/search.md).

Applying is idempotent: for each touched document it reads the current state from Postgres and writes or deletes it
with the event id as an external version, so ES drops anything older than what it has. Several workers, a drain and
a rebuild replay can therefore run at once, and a duplicate or re-ordered event can't leave an older state behind.
"""
import logging
import time

from elasticsearch import ApiError, TransportError, helpers
from sqlalchemy import case, delete, func, select, update
from sqlalchemy.orm import Session

from core.database import SessionLocal
from member.directory import search as directory
from member.matrimony import search as matrimony
from search import es
from search.outbox import SearchOutbox as O

log = logging.getLogger("search")

INDEXES = (directory, matrimony)
BATCH = 500  # events per claim; each becomes one bulk request per index
MAX_ATTEMPTS = 10  # backoff 2, 4, 8 ... capped at 300 s: about 25 minutes of retries, then dead
BACKFILL_VERSION = 1  # events write id + 1, so any event beats a backfilled copy
KEEP_DAYS = 1  # processed events are kept this long: a rebuild replays those applied while it ran


def _ok(op: str, item: dict) -> bool:
    # 409: ES already holds a newer version (a later event got there first); 404 on delete: already gone
    return item["status"] < 300 or item["status"] == 409 or (op == "delete" and item["status"] == 404)


def apply(db: Session, events, specs=INDEXES) -> dict[int, str]:
    """Make the indexes match Postgres for everything these (id, entity, entity_id) events touch.
    Returns {event_id: error} for events with a document that didn't land; the rest are done."""
    failed = {}
    for spec in specs:
        targets = spec.targets(db, events)
        if not targets:
            continue
        current = spec.docs(db, list(targets))
        actions = [{"_op_type": "index", "_id": doc_id, "_source": current[doc_id]} if doc_id in current
                   else {"_op_type": "delete", "_id": doc_id} for doc_id in targets]
        for a in actions:
            a |= {"_index": es.alias(spec.NAME), "version": max(targets[a["_id"]]) + 1, "version_type": "external"}
        # require_alias: a missing alias fails the write instead of auto-creating an index with guessed mappings
        for _, result in helpers.streaming_bulk(es.client().options(request_timeout=30), actions, chunk_size=BATCH,
                                                max_retries=3, raise_on_error=False, require_alias=True):
            op, item = next(iter(result.items()))
            if not _ok(op, item):
                err = f"{spec.NAME} {item['_id']}: {item.get('error', {}).get('type', item['status'])}"
                failed.update(dict.fromkeys(targets[item["_id"]], err))
    return failed


def process_batch(db: Session) -> int:
    """Claim up to BATCH due events (SKIP LOCKED: other workers take the next ones), apply, record. Returns how many."""
    rows = db.execute(select(O.id, O.entity, O.entity_id)
                      .where(O.processed_at.is_(None), O.dead_at.is_(None), O.next_attempt_at <= func.now())
                      .order_by(O.id).limit(BATCH).with_for_update(skip_locked=True)).all()
    if not rows:
        db.commit()
        return 0
    started = time.perf_counter()
    try:
        failed = apply(db, rows)
    except (ApiError, TransportError) as e:  # ES unreachable or refusing: retry the whole batch later
        failed = dict.fromkeys((r.id for r in rows), f"{type(e).__name__}: {e}"[:500])
    except Exception as e:  # a bug: count it as an attempt, so a poison event ends up dead, not retried forever
        log.exception("search: applying %d events failed", len(rows))
        failed = dict.fromkeys((r.id for r in rows), f"{type(e).__name__}: {e}"[:500])
    done = [r.id for r in rows if r.id not in failed]
    if done:
        db.execute(update(O).where(O.id.in_(done)).values(processed_at=func.clock_timestamp()))
    for err in set(failed.values()):
        attempts = O.attempts + 1
        db.execute(update(O).where(O.id.in_([i for i, e in failed.items() if e == err])).values(
            attempts=attempts, last_error=err[:500],
            next_attempt_at=func.clock_timestamp() + func.make_interval(0, 0, 0, 0, 0, 0, func.least(
                func.power(2, attempts), 300)),
            dead_at=case((attempts >= MAX_ATTEMPTS, func.clock_timestamp()))))
    db.commit()
    ms = (time.perf_counter() - started) * 1000
    if failed:
        log.error("search: %d of %d events failed and will be retried: %s", len(failed), len(rows),
                  next(iter(failed.values())))
    log.info("search: applied %d events in %d ms", len(done), ms)
    return len(rows)


def drain():
    """Apply every due event now and refresh, so the changes are searchable. For tests and scripts."""
    if not es.enabled():
        return
    for spec in INDEXES:
        es.ensure(spec)
    with SessionLocal() as db:
        while process_batch(db):
            pass
    es.client().indices.refresh(index=",".join(es.alias(s.NAME) for s in INDEXES))


def retry_dead(db: Session) -> int:
    """Put dead events back in the queue with a fresh set of attempts."""
    n = db.execute(update(O).where(O.dead_at.is_not(None))
                   .values(dead_at=None, attempts=0, next_attempt_at=func.now())).rowcount
    db.commit()
    return n


def clean(db: Session) -> int:
    """Drop events processed more than KEEP_DAYS ago."""
    n = db.execute(delete(O).where(O.processed_at < func.now() - func.make_interval(0, 0, 0, KEEP_DAYS))).rowcount
    db.commit()
    return n


def outbox_stats(db: Session) -> dict:
    pending, retrying, dead, oldest = db.execute(select(
        func.count().filter(O.processed_at.is_(None), O.dead_at.is_(None)),
        func.count().filter(O.processed_at.is_(None), O.dead_at.is_(None), O.attempts > 0),
        func.count().filter(O.dead_at.is_not(None)),
        func.min(O.created_at).filter(O.processed_at.is_(None), O.dead_at.is_(None)))).one()
    lag = db.scalar(select(func.extract("epoch", func.now() - oldest))) if oldest else 0
    return {"pending": pending, "retrying": retrying, "dead": dead, "oldest_pending_s": round(float(lag), 1)}


def backfill(db: Session, spec, index: str, after: str | None = None) -> tuple[int, int]:
    """Copy every searchable row of spec into index in keyset batches of 1000; never holds the table in memory.
    Re-running is safe: documents are written with BACKFILL_VERSION, which loses to any event-written copy.
    Returns (indexed, failed); prints progress with the id to pass as --resume-after."""
    indexed = failed = 0
    while batch := spec.batch(db, after, 1000):
        db.rollback()  # end the read transaction between batches: no long-held snapshot
        actions = [{"_index": index, "_id": doc_id, "_source": doc, "version": BACKFILL_VERSION,
                    "version_type": "external"} for doc_id, doc in batch]
        for _, result in helpers.streaming_bulk(es.client().options(request_timeout=60), actions, chunk_size=1000,
                                                max_retries=3, raise_on_error=False):
            op, item = next(iter(result.items()))
            if _ok(op, item):
                indexed += 1
            else:
                failed += 1
                log.error("search: %s %s not indexed: %s", spec.NAME, item["_id"], item.get("error", {}).get("type"))
        after = batch[-1][0]
        print(f"  {spec.NAME}: {indexed} indexed, {failed} failed, last id {after}", flush=True)
    print(f"  {spec.NAME}: done, {indexed} indexed, {failed} failed", flush=True)
    return indexed, failed


def rebuild(spec) -> bool:
    """Fresh index from Postgres, then an atomic alias switch; searches keep using the old index until then.
    Reconciles everything: documents for rows changed by bulk SQL, mapping changes, orphans. False: not switched."""
    c = es.client()
    alias, old = es.alias(spec.NAME), es.current(spec)
    for leftover in c.indices.get(index=f"{alias}_v*", expand_wildcards="all"):
        if leftover != old:  # an earlier rebuild that stopped half way
            c.indices.delete(index=leftover)
    with SessionLocal() as db:
        started = db.scalar(select(func.clock_timestamp()))
        new = es.create_index(spec)
        indexed, failed = backfill(db, spec, new)
    if failed:
        log.error("search: %d documents failed; %s stays on %s and %s is dropped", failed, alias, old, new)
        c.indices.delete(index=new)
        return False
    c.indices.refresh(index=new)
    c.indices.update_aliases(actions=[{"add": {"index": new, "alias": alias}}]
                             + ([{"remove": {"index": old, "alias": alias}}] if old else []))
    # The worker kept writing to the old index while we copied: replay what it applied since we started.
    with SessionLocal() as db:
        events = db.execute(select(O.id, O.entity, O.entity_id).where(O.processed_at >= started)).all()
        if events and (errors := apply(db, events, specs=[spec])):
            log.error("search: replaying %d events: %d failed (%s); the worker's next run covers changes after this",
                      len(events), len(errors), next(iter(errors.values())))
    if old:
        c.indices.delete(index=old)
    print(f"  {alias} -> {new} ({indexed} documents, {len(events)} events replayed)", flush=True)
    return True
