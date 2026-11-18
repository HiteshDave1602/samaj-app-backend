"""Search index worker: applies outbox events to Elasticsearch, about a second after each change commits.

    python -m search.worker               run until Ctrl+C (one per deployment is plenty; more are safe)
    python -m search.worker --retry-dead  put dead events back in the queue, then exit
"""
import argparse
import logging
import time

from elasticsearch import ApiError, TransportError

from core.database import SessionLocal
from search import es, sync

POLL_SECONDS = 1.0  # idle wait between claims. ponytail: polling; LISTEN/NOTIFY if sub-second lag ever matters
CLEAN_EVERY = 600  # seconds between purges of old processed events

log = logging.getLogger("search")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--retry-dead", action="store_true", help="re-queue events that exhausted their retries")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("elastic_transport").setLevel(logging.WARNING)  # one INFO line per HTTP call otherwise
    if not es.enabled():
        raise SystemExit("ELASTICSEARCH_URL is empty: nothing to sync to")
    if args.retry_dead:
        with SessionLocal() as db:
            print(f"{sync.retry_dead(db)} dead events re-queued")
        return

    while True:  # the indexes must exist before events can land (bulk writes require the alias)
        try:
            for spec in sync.INDEXES:
                es.ensure(spec)
            break
        except (ApiError, TransportError) as e:
            log.warning("search worker: ES not ready (%s); retrying in 5 s", type(e).__name__)
            time.sleep(5)
    log.info("search worker: running")
    last_clean = 0.0
    try:
        while True:
            try:
                with SessionLocal() as db:
                    n = sync.process_batch(db)
                    if time.monotonic() - last_clean > CLEAN_EVERY:
                        last_clean = time.monotonic()
                        log.info("search worker: purged %d processed events", sync.clean(db))
            except Exception:  # Postgres gone, say: events stay queued; try again shortly
                log.exception("search worker: batch failed; retrying in 5 s")
                time.sleep(5)
                continue
            if n < sync.BATCH:
                time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        log.info("search worker: stopped")
    finally:
        es.close()


if __name__ == "__main__":
    main()
