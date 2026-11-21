"""Elasticsearch for the member directory and matrimony search (docs/search.md).

Postgres is the source of truth. ES holds only the fields search filters, matches and sorts on: never phone, address
or other encrypted data. A search asks ES for ids in order, then reads those rows from Postgres through the same
visibility filter as before, so a stale document is dropped, never shown. When ES is off, failing or slow, the request
is answered by the original Postgres query instead.
"""
import logging
import threading
import time
from collections import deque
from datetime import datetime, timezone

from elasticsearch import ApiError, Elasticsearch, NotFoundError, TransportError

from core.config import settings

log = logging.getLogger("search")

SEARCH_TIMEOUT = 2.0  # seconds per ES call from an API request; a slower answer comes from Postgres instead
BREAK_SECONDS = 30  # after an ES outage, skip ES for this long rather than make every request wait on it
MAX_WINDOW = 10_000  # index.max_result_window: offset + limit past it is answered by Postgres
FUZZY = "AUTO:4,7"  # typo tolerance: exact under 4 letters, 1 edit for 4-6, 2 edits from 7
CLOSEST_SIMILARITY = 0.3  # Postgres fallback's "closest match" floor (pg_trgm word_similarity, 0..1)

KEYWORD = {"type": "keyword"}
ANALYSIS = {
    "analyzer": {"folded": {"type": "custom", "tokenizer": "standard", "filter": ["lowercase", "asciifolding"]}},
    "normalizer": {"folded": {"type": "custom", "filter": ["lowercase", "asciifolding"]}},
}
TEXT = {"type": "text", "analyzer": "folded"}


def name_field(sort: bool = False) -> dict:
    """Words (typo-tolerant match), `.sub` for substring match like Postgres ILIKE '%x%', `.sort` to order by."""
    f = TEXT | {"fields": {"sub": {"type": "wildcard"}}}
    if sort:
        f["fields"]["sort"] = {"type": "keyword", "normalizer": "folded"}
    return f


I18N = {"properties": {"gu": name_field(), "hi": name_field()}}  # Gujarati and Hindi spellings (core.translit)


def i18n(value: dict | None) -> dict:
    return {k: value[k] for k in ("gu", "hi") if value and value.get(k)}


def name_query(text: str, field: str) -> dict:
    """Matches when the English, Gujarati or Hindi spelling contains the text, or every word is within typo distance."""
    pattern = "*" + text.replace("\\", "\\\\").replace("*", "\\*").replace("?", "\\?") + "*"
    should = []
    for f in (field, f"{field}_i18n.gu", f"{field}_i18n.hi"):
        should.append({"wildcard": {f"{f}.sub": {"value": pattern, "case_insensitive": True}}})
        should.append({"match": {f: {"query": text, "operator": "and", "fuzziness": FUZZY, "prefix_length": 1}}})
    return {"bool": {"should": should, "minimum_should_match": 1}}


def closest_query(text: str, fields: list[str]) -> dict:
    """Last resort when nothing matched: any word within 2 edits, first letter included. Sort by _score (best first)."""
    return {"multi_match": {"query": text, "fields": fields, "fuzziness": 2, "prefix_length": 0}}


# ---- client -------------------------------------------------------------------------------------------------------

_client: Elasticsearch | None = None
_lock = threading.Lock()


def enabled() -> bool:
    return bool(settings.elasticsearch_url)


def client() -> Elasticsearch:
    """The process's one client. Thread-safe; its HTTP connections are pooled and reused by every request."""
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                auth = settings.elasticsearch_username and (settings.elasticsearch_username,
                                                            settings.elasticsearch_password)
                _client = Elasticsearch(
                    settings.elasticsearch_url, basic_auth=auth or None,
                    ca_certs=settings.elasticsearch_ca_certs or None,
                    request_timeout=SEARCH_TIMEOUT, max_retries=1, retry_on_timeout=False,
                    connections_per_node=settings.elasticsearch_max_connections)
    return _client


def close():
    global _client
    if _client is not None:
        _client.close()
        _client = None


# ---- indexes: versioned physical names behind one alias ------------------------------------------------------------

def alias(name: str) -> str:
    return f"{settings.elasticsearch_index_prefix}_{name}"


def create_index(spec) -> str:
    """A new, empty physical index for spec, not yet behind the alias: <alias>_v<VERSION>_<UTC time>."""
    index = f"{alias(spec.NAME)}_v{spec.VERSION}_{datetime.now(timezone.utc):%Y%m%d%H%M%S%f}"
    # One primary shard: tens of MB of documents; ES suggests up to ~50 GB a shard. Replicas add read capacity and HA.
    client().indices.create(
        index=index,
        settings={"number_of_shards": 1, "number_of_replicas": settings.elasticsearch_replicas, "analysis": ANALYSIS},
        mappings={"dynamic": "strict", "_meta": {"version": spec.VERSION}, "properties": spec.PROPERTIES})
    return index


def current(spec) -> str | None:
    """The physical index behind spec's alias, or None when there is none yet."""
    try:
        return next(iter(client().indices.get_alias(name=alias(spec.NAME))))
    except NotFoundError:
        return None


def ensure(spec) -> str:
    """Creates the alias with an empty index when missing; logs when its mapping is older than the code's."""
    index = current(spec)
    if index is None:
        index = create_index(spec)
        client().indices.put_alias(index=index, name=alias(spec.NAME))
        log.warning("search: created empty %s; fill it with python -m search.reindex", alias(spec.NAME))
        return index
    meta = client().indices.get_mapping(index=index)[index]["mappings"].get("_meta", {})
    if meta.get("version") != spec.VERSION:
        log.error("search: %s has mapping v%s, the code expects v%s; run python -m search.reindex --rebuild",
                  index, meta.get("version"), spec.VERSION)
    return index


class Incomplete(Exception):
    """ES answered, but not from every shard or not within its timeout: paging over it would skip results."""


def search(name: str, **body) -> list[dict]:
    """Hits (ids and sort values only) from the alias of index `name`."""
    res = client().search(index=alias(name), source=False, track_total_hits=False,
                          timeout=f"{int(SEARCH_TIMEOUT * 1000) - 500}ms", **body)
    if res.get("timed_out") or res["_shards"].get("failed"):
        raise Incomplete
    return res["hits"]["hits"]


# ---- answering: ES with Postgres fallback, rate limit, counters -----------------------------------------------------

_down_until = 0.0
_counts = {"es": 0, "postgres": 0, "fallback": 0, "rate_limited": 0}
_latency = {"es": deque(maxlen=5000), "postgres": deque(maxlen=5000)}  # ms per search, hydration included
_window: list = [0, {}]  # rate limit: [minute, {member_id: searches this minute}]


def _record(backend: str, started: float):
    ms = (time.perf_counter() - started) * 1000
    with _lock:
        _counts[backend] += 1
        _latency[backend].append(ms)
    if ms > 1000:
        log.warning("search: slow %s answer, %d ms", backend, ms)  # no query text: it can hold a person's name


def answer(es_call, pg_call):
    """es_call when ES is up, pg_call (the original Postgres query) when it's off, failing, or failed < 30 s ago."""
    global _down_until
    if enabled() and time.monotonic() >= _down_until:
        started = time.perf_counter()
        try:
            result = es_call()
        except (ApiError, TransportError, Incomplete) as e:
            with _lock:
                _counts["fallback"] += 1
            if isinstance(e, ApiError) and e.status_code == 400:  # our query is wrong: a bug, not an outage
                log.error("search: ES rejected the query (%s); answered from Postgres", e.error)
            else:
                _down_until = time.monotonic() + BREAK_SECONDS
                log.warning("search: ES unavailable (%s); Postgres answers for %d s", type(e).__name__, BREAK_SECONDS)
        else:
            _record("es", started)
            return result
    started = time.perf_counter()
    result = pg_call()
    _record("postgres", started)
    return result


def allow(member_id) -> bool:
    """Fixed one-minute window per member. ponytail: per API process; put a global limit in the proxy too."""
    minute = int(time.monotonic() // 60)
    with _lock:
        if _window[0] != minute:
            _window[:] = [minute, {}]
        n = _window[1][member_id] = _window[1].get(member_id, 0) + 1
        if n > settings.search_rate_per_minute:
            _counts["rate_limited"] += 1
            return False
    return True


def health() -> str:
    """off | green | yellow | red | degraded (unreachable: searches are being answered by Postgres)."""
    if not enabled():
        return "off"
    if time.monotonic() < _down_until:
        return "degraded"
    try:
        return client().options(request_timeout=1).cluster.health()["status"]
    except (ApiError, TransportError):
        return "degraded"


def snapshot() -> dict:
    """This process's search counters and latency percentiles since it started."""
    with _lock:
        counts, samples = dict(_counts), {k: sorted(v) for k, v in _latency.items()}
    pct = {k: {f"p{p}": round(v[min(len(v) - 1, len(v) * p // 100)], 1) for p in (50, 95, 99)} if v else None
           for k, v in samples.items()}
    return counts | {"latency_ms": pct, "postgres_only_for_s": max(0, round(_down_until - time.monotonic()))}
