"""Transactional outbox for the search index.

Every flush that changes something search shows inserts an event row in the same transaction, so a committed change
always reaches ES and a rolled-back one never does, whichever code path made it (app, admin panel, import).
Events carry only an id: the worker (search/sync.py) reads the current state from Postgres when it applies them.
Bulk UPDATE/DELETE statements bypass the session and send no events; `python -m search.reindex --rebuild` reconciles.
"""
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, DateTime, Identity, Index, SmallInteger, String, Uuid, event, insert, inspect,
    text,
)
from sqlalchemy.orm import Session

from core.config import settings
from core.database import Base

ENTITIES = ("member", "relative", "household", "matrimony")


class SearchOutbox(Base):
    __tablename__ = "search_outbox"
    __table_args__ = (
        CheckConstraint(f"entity IN ({','.join(repr(e) for e in ENTITIES)})", name="ck_search_outbox_entity"),
        Index("ix_search_outbox_due", "next_attempt_at", postgresql_where=text("processed_at IS NULL AND dead_at IS NULL")),
        Index("ix_search_outbox_processed", "processed_at", postgresql_where=text("processed_at IS NOT NULL")),
    )

    id = Column(BigInteger, Identity(), primary_key=True)  # also the ES external version: a later event always wins
    entity = Column(String(12), nullable=False)
    entity_id = Column(Uuid, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    attempts = Column(SmallInteger, nullable=False, server_default=text("0"))
    next_attempt_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    last_error = Column(String(500))
    processed_at = Column(DateTime(timezone=True))  # kept a day: a rebuild replays what landed while it ran
    dead_at = Column(DateTime(timezone=True))  # gave up after sync.MAX_ATTEMPTS; python -m search.worker --retry-dead


# table -> (entity, primary key, columns that change what search shows or who it shows; None = any column)
WATCH = {
    "member": ("member", "member_id",
               {"status", "deleted_at", "full_name", "full_name_i18n", "gender", "dob", "city_id", "household_id"}),
    "family_member": ("relative", "family_member_id",
                      {"status", "linked_member_id", "full_name", "full_name_i18n", "gender", "household_id"}),
    "household": ("household", "household_id",
                  {"family_name", "family_name_i18n", "native_place", "native_place_i18n", "city_id"}),
    "matrimony_profile": ("matrimony", "profile_id", None),
}


def _enqueue(session: Session, _ctx):
    # after_flush: primary keys (server defaults) are known and attribute history still shows what changed
    events = set()
    dirty = session.dirty  # once: the property walks the whole identity map on every call
    for obj in (*session.new, *dirty, *session.deleted):
        spec = WATCH.get(getattr(obj, "__tablename__", None))
        if spec is None:
            continue
        entity, pk, columns = spec
        state = inspect(obj)
        if obj in dirty and not (session.is_modified(obj) if columns is None
                                 else any(state.attrs[c].history.has_changes() for c in columns)):
            continue  # e.g. last_login_at: nothing search shows
        events.add((entity, getattr(obj, pk)))
        if entity == "member":  # a member's status decides whether the household's relatives are listed
            h = state.attrs.household_id.history
            events.update(("household", hid) for hid in (*h.added, *h.unchanged, *h.deleted) if hid)
    if events:
        session.connection().execute(insert(SearchOutbox.__table__),
                                     [{"entity": e, "entity_id": i} for e, i in sorted(events, key=str)])


if settings.elasticsearch_url:  # no search engine configured: nothing would ever read the events
    event.listen(Session, "after_flush", _enqueue)
