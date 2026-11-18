"""Fill or rebuild the search indexes from Postgres.

    python -m search.reindex                        add every searchable row to the current indexes (creates
                                                    them if missing); safe to repeat, newer copies are kept
    python -m search.reindex --resume-after ID      continue a stopped run from the last id it printed
    python -m search.reindex --rebuild              new versioned index, full copy, atomic alias switch, old dropped:
                                                    for mapping changes and to clear stale documents
    --only directory|matrimony                      one index instead of both
"""
import argparse
import logging
import sys

from core.database import SessionLocal
from search import es, sync


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rebuild", action="store_true")
    p.add_argument("--only", choices=[s.NAME for s in sync.INDEXES])
    p.add_argument("--resume-after", metavar="ID", help="with --only: the last id a stopped run printed")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("elastic_transport").setLevel(logging.WARNING)
    if not es.enabled():
        raise SystemExit("ELASTICSEARCH_URL is empty: nothing to index into")
    if args.resume_after and (args.rebuild or not args.only):
        raise SystemExit("--resume-after needs --only and can't be used with --rebuild")
    ok = True
    for spec in sync.INDEXES:
        if args.only and spec.NAME != args.only:
            continue
        print(f"{es.alias(spec.NAME)}:", flush=True)
        if args.rebuild:
            ok &= sync.rebuild(spec)
        else:
            with SessionLocal() as db:
                ok &= sync.backfill(db, spec, es.ensure(spec), args.resume_after)[1] == 0
    es.close()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
