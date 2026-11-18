# Search engine (Elasticsearch)

The member directory (`GET /member/directory`) and matrimony search (`GET /member/matrimony/profiles`) can run on
Elasticsearch. PostgreSQL stays the source of truth: ES holds a copy of only the fields search needs, and both
endpoints fall back to their original Postgres queries whenever ES is off, down or slow. Load-test results are in
[search-loadtest.md](search-loadtest.md).

## 1. Architecture

```
 app ──► API (FastAPI, N processes)
          │  GET /member/directory, /member/matrimony/profiles
          │   1. auth (Postgres)
          │   2. ES: matching ids, in order ─────────────► Elasticsearch  (alias samaj_directory / samaj_matrimony
          │   3. Postgres: those rows, re-checked for          ▲            → samaj_<name>_v<N>_<time>)
          │      visibility; phone/address decrypted           │
          │   ES off / failing / slow ─► original Postgres query
          │                                                    │ bulk index / delete (external versions)
          │  any write (app, admin panel, import)              │
          └─► Postgres: business rows + search_outbox ──► search worker (python -m search.worker)
              rows, in the same transaction
```

- **What ES stores:** names (English, Gujarati, Hindi), family name, city, household, gender, kind. For matrimony it
  adds DOB, education, background, occupation, gotra and native place. Never phone, address, ID documents, biodata
  or anything encrypted. Those are read from Postgres for the 20–50 rows on the page.
- **Who is listed** is decided only by the existing Postgres queries (`member/directory/curd.py`,
  `member/matrimony/curd.py::public_query`). Documents are built from them, and every page of ES hits is read back
  through them. A hit for someone archived a second ago is dropped, never shown.
- **Tenancy:** cities are the tenant boundary. The directory and matrimony search are cross-city by design (the city
  is a filter, FR-65/FR-25); the City Admin lists are city-scoped and stay on Postgres. The member, and therefore
  the visibility rules, always come from the authenticated token, never from a parameter.

| Code | What it does |
|---|---|
| [search/es.py](../backend/search/es.py) | the client (one per process), index create/alias helpers, Postgres fallback and circuit breaker, rate limit, counters |
| [search/outbox.py](../backend/search/outbox.py) | `search_outbox` table + the session listener that writes it |
| [search/sync.py](../backend/search/sync.py) | apply events, backfill, rebuild, drain |
| [search/worker.py](../backend/search/worker.py), [search/reindex.py](../backend/search/reindex.py) | the two command-line tools |
| [member/directory/search.py](../backend/member/directory/search.py), [member/matrimony/search.py](../backend/member/matrimony/search.py) | mappings, queries, document builders per index |
| [superadmin/search/api.py](../backend/superadmin/search/api.py) | `GET /superadmin/search/status` |

## 2. Installation and setup (dev)

Needs Docker Desktop. From `backend/`:

```powershell
pip install -r requirements.txt          # adds the elasticsearch client
# add the four ELASTICSEARCH_* lines to backend/.env (section 3)
docker compose up -d                     # one ES node on 127.0.0.1:9200
alembic upgrade head                     # search_outbox table
python -m search.reindex                 # creates both indexes and copies every searchable row
python -m search.worker                  # keep running next to uvicorn: applies changes ~1 s after commit
```

Leave `ELASTICSEARCH_URL` empty and nothing changes: no outbox rows, and every search runs on Postgres as before.

## 3. Environment variables (`backend/.env`)

| Variable | Default | Meaning |
|---|---|---|
| `ELASTICSEARCH_URL` | empty | `http://127.0.0.1:9200` in dev, `https://<private ip>:9200` in prod. Empty = Postgres only. On Windows use `127.0.0.1`, not `localhost` (see Troubleshooting). |
| `ELASTICSEARCH_USERNAME` | empty | `samaj_backend`: the restricted user, never `elastic` |
| `ELASTICSEARCH_PASSWORD` | empty | its password; docker compose creates the user from these two values |
| `ELASTICSEARCH_INDEX_PREFIX` | `samaj` | index names start `<prefix>_`; must start with `samaj` (that is all the role grants) |
| `ELASTICSEARCH_CA_CERTS` | empty | prod: path to the cluster CA (`ca.crt`) |
| `ELASTICSEARCH_REPLICAS` | `0` | replicas per index, applied when an index is created (prod: `1`) |
| `ELASTICSEARCH_MAX_CONNECTIONS` | `40` | pooled HTTP connections per API process (= AnyIO's 40 request threads) |
| `SEARCH_RATE_PER_MINUTE` | `60` | directory + matrimony searches per member per minute, per API process; 429 above |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` | `5`, `10` | SQLAlchemy pool per API process. Keep processes × (size + overflow) under Postgres `max_connections`. Also sets how many requests a process runs at once: size + overflow − 1 (below) |

**Admission control** ([core/admission.py](../backend/core/admission.py), all endpoints). Each API process runs at
most `DB_POOL_SIZE + DB_MAX_OVERFLOW − 1` requests at once (14 by default). The rest wait on the event loop, holding
no thread and no DB connection, and get `503 Server busy` with `Retry-After: 2` after 10 s. Without it, sync
endpoints deadlock under load: requests holding pooled connections wait for threadpool threads while the threads
wait for connections. The first load test hit exactly that at 250 users (see search-loadtest.md).

Fixed in code (`search/es.py`, `search/sync.py`, `search/worker.py`): a 2 s ES timeout per search, a 30 s circuit
breaker, 500 events per worker batch, 10 attempts before an event is dead, and a 1 s worker poll.

## 4. Docker

**Dev**: [backend/docker-compose.yml](../backend/docker-compose.yml)

- One node, 1 GB heap, 2 GB memory limit, data in the `esdata` volume, health check, `restart: unless-stopped`.
- Bound to `127.0.0.1` only. Security on, HTTP TLS off (dev only).
- The backend user is created at container start from `.env` via the file realm, with the role in
  [deploy/elasticsearch/roles.yml](../backend/deploy/elasticsearch/roles.yml). No superuser password is needed.
- `docker compose --profile test up -d` also starts `postgres-test` on 127.0.0.1:5433, a throwaway database on tmpfs
  for the test scripts and load tests.

**Production**: [backend/deploy/docker-compose.prod.yml](../backend/deploy/docker-compose.prod.yml), see section 13.

## 5. Index mappings

Both indexes: one primary shard (the data is tens of MB; ES's guidance is up to ~50 GB per shard), replicas from
`ELASTICSEARCH_REPLICAS`, `dynamic: strict` (an unexpected field fails loudly instead of growing the mapping) and
`_meta.version`.

| Field type | Used for |
|---|---|
| `keyword` | ids, city, gender, education, background: exact filters |
| `text`, analyzer `folded` (standard tokenizer + lowercase + ASCII folding) | words, case-insensitive, typo-tolerant (`fuzziness AUTO:4,7`: exact under 4 letters, 1 edit for 4–6, 2 from 7; first letter must match) |
| `.sub` subfield, type `wildcard` | substring anywhere, like Postgres `ILIKE '%x%'`; `*` and `?` in input are escaped |
| `.sort` subfield, `keyword` + lowercase normalizer | ordering by name |
| `*_i18n.gu`, `*_i18n.hi` | Gujarati and Hindi spellings (from `core.translit`), same text + `.sub` |

**directory** (one document per listed person, id `MEMBER:<member_id>` or `RELATIVE:<family_member_id>`):
`kind, id, city_id, household_id, gender, full_name(+_i18n), family_name(+_i18n)`.
Query: every given filter must match; a name matches if any spelling contains it or every word is within typo
distance. Sorted by `full_name.sort`, then `id`.

**matrimony** (id `profile_id`): `profile_id, member_id, gender, dob, education_level, family_background,
location_city_id, full_name(+_i18n), occupation, gotra, education_detail, native_place(+_i18n)`.
Filters as before; your own profile is excluded. The new `q` matches whole words with typos, or word prefixes, in
any one of the text fields. Sorted by `profile_id`, paged with `search_after` (section 7).

**Changing a mapping:** never edit a live index. Bump `VERSION` in the module, deploy, run
`python -m search.reindex --rebuild`. Until then the worker logs `has mapping vN, the code expects vM`.

## 6. Database synchronisation

1. A request validates and writes as usual. In the same transaction, an `after_flush` listener
   ([search/outbox.py](../backend/search/outbox.py)) inserts `search_outbox` rows `(entity, entity_id)`. That
   happens for `member`, `family_member` and `household` rows when a column search uses changes, and for any change
   to `matrimony_profile`. A member change also queues their household, because a member's status decides whether
   the household's relatives are listed. Changes such as `last_login_at` queue nothing.
2. Commit: the change and its events land together, or neither does (transactional outbox).
3. The worker claims up to 500 due events (`FOR UPDATE SKIP LOCKED`), works out the touched documents (a household
   event covers everyone in it and their matrimony profiles), reads their **current** state from Postgres, and sends
   one bulk request per index: index the listed ones, delete the rest.
4. Each write carries `version = event id + 1` with `version_type=external`. ES rejects anything older than what
   it holds, so duplicate, re-ordered or concurrent processing (several workers, a drain, a rebuild replay) can't
   leave an older state. A 409 (newer already there) or a 404 on delete counts as done. Bulk writes use
   `require_alias`, so a missing index fails instead of being auto-created with guessed mappings.
5. Failures: the event's `attempts` goes up, `last_error` is kept, and it is retried after 2, 4, 8 … 300 s. After 10
   attempts it is **dead** (`dead_at`), counted on the status page, and never silently dropped.
   `python -m search.worker --retry-dead` re-queues dead events.
6. Processed events are kept for a day, then purged by the worker. A rebuild replays the ones processed while it ran.

**Lag:** a change is searchable about 1–2 s after commit (1 s poll + 1 s ES refresh) while the worker runs.
Removals take effect at once regardless, because hits are re-checked in Postgres.

**Not covered by the outbox:** bulk `UPDATE`/`DELETE` statements (`db.execute(update(Member)...)`), raw SQL and
manual database edits. No app code path does this today (the test scripts' clean-up does). Run
`python -m search.reindex --rebuild` after such edits; until then stale hits are hidden by the Postgres re-check.

## 7. Search API

Routes and response shapes are unchanged. Both endpoints need an ACTIVE member token (401/403 as before) and
return 429 `Too many searches. Try again in a minute.` above `SEARCH_RATE_PER_MINUTE`.

**`GET /member/directory`** `?name=&family_name=&city_id=&offset=0&limit=20` (limit ≤ 50; name and family name
2–120 characters) → `{"items": [...], "next_offset": 40 | null}`.
With ES, `name`/`family_name` also match small typos and Gujarati/Hindi script. Pages that reach past 10,000 results
(`offset + limit` over ES's window) are answered by Postgres, which pages any offset.

**`GET /member/matrimony/profiles`** `?q=&age_min=&age_max=&gender=&education_level=&city_id=&family_background=&after=&limit=20`
→ `{"items": [...], "next_after": "<profile_id>" | null}`.
`q` (new, optional, 2–120 characters) searches name, occupation, gotra, education detail and native place. Paging
is a keyset cursor: `after` is the last profile id, run as ES `search_after`. Profile ids sort the same in ES and
Postgres, so a cursor carries over if a request falls back mid-scroll.

**Fallback:** on a connection error, timeout (2 s), 5xx/429, a missing index or a partial result, the request is
answered by the Postgres query and ES is skipped for 30 s. Clients see results, never ES errors. On Postgres,
matching is plain substring: no typo tolerance and no Gujarati/Hindi matching. A 400 from ES (a bug in our query)
falls back for that request only and is logged as an error.

## 8. Initial indexing

```powershell
python -m search.reindex                       # both indexes; creates them if missing
python -m search.reindex --only directory      # one of them
python -m search.reindex --only directory --resume-after MEMBER:<uuid>   # continue a stopped run
```

- It reads Postgres in keyset batches of 1000 (no OFFSET, never the whole table in memory) and writes with the Bulk
  API, printing progress and the id to resume after.
- A document that fails is logged and counted, and the run carries on. The exit code is 1 if any failed.
- Re-running is safe and creates no duplicates: ids are deterministic, and backfilled copies are written with
  version 1, so they never overwrite a newer copy from the worker.
- Measured: 73,057 directory and 5,172 matrimony documents in 17 s on a laptop.

## 9. Rebuilding an index

```powershell
python -m search.reindex --rebuild             # or --rebuild --only matrimony
```

1. Creates a new `<alias>_v<VERSION>_<time>` index and copies everything into it, while searches keep using the old
   one.
2. If any document failed, it stops there: the alias stays put, the new index is dropped, and the exit code is 1.
3. Otherwise it moves the alias in one atomic `_aliases` call.
4. It re-applies every event the worker processed since the rebuild started (those went to the old index).
5. It deletes the old index. Leftovers from an interrupted earlier rebuild are deleted first.

Use it for mapping changes, after bulk SQL edits, or whenever you want a clean copy. The worker can keep running.

## 10. Monitoring

| Where | What |
|---|---|
| `GET /health` | `{"status": "ok", "search": "green"\|"yellow"\|"red"\|"degraded"\|"off"}`. `degraded` means ES is unreachable and searches are served by Postgres; the API is still up. |
| `GET /superadmin/search/status` (Super Admin) | cluster status, nodes, shards, thread-pool **rejections** (search/write), documents per index, outbox `pending` / `retrying` / `dead` / `oldest_pending_s` (= index lag), and this API process's counters: searches answered by ES / Postgres, fallbacks, rate-limited, `server_busy_503` (admission control turned a request away), latency p50/p95/p99 |
| API logs (`search` logger) | `ES unavailable (...)`, `ES rejected the query`, `slow es answer, N ms` (over 1 s). Never the query text, which can be a person's name. |
| worker logs | `applied N events in M ms`, `N of M events failed and will be retried: <error>`, purges |

Alert on: `search` ≠ green in `/health`, `outbox.dead > 0`, `outbox.oldest_pending_s > 60`, rejections increasing.
The counters are per process and reset on restart. Scrape every process, or add a metrics exporter if you run
Prometheus. ES's own CPU, heap and disk are in `GET _nodes/stats` (or Kibana/Stack Monitoring).

## 11. Tests

The test scripts run against whatever `DATABASE_URL` points at. Use the throwaway one: `docker compose --profile
test up -d`, then `DATABASE_URL=postgresql+psycopg2://samaj:samaj-test@127.0.0.1:5433/samaj` and `alembic upgrade head`.

- `python test_search.py`: the search engine end to end, on its own indexes (`samaj_test_<random>_*`, deleted
  afterwards). It covers outbox atomicity, document contents, matching (substring, typo, Gujarati, Hindi), filters,
  sorting, both paging styles, identical ES/Postgres responses, stale-document filtering, update and delete sync,
  household rules, external versions, retries → dead → retry-dead, ES down (fallback, breaker, health), rate limit,
  the status page, idempotent backfill, rebuild with replay, and 500 concurrent searches on a real server while
  indexing. **Stop the search worker first**, or it will apply the test's events to the dev indexes.
- `python test_admission.py`: admission control (slot limit, queueing, 503), no database needed.
- The existing `test_*.py` scripts pass with ES on and with `ELASTICSEARCH_URL` empty. `test_directory.py` and
  `test_matrimony.py` call `search.sync.drain()` (a no-op without ES) before searching.

## 12. Load testing

Tools: k6 (from Docker), plus [backend/loadtest/](../backend/loadtest/). From `backend/`:

```powershell
pip install -r loadtest/requirements.txt                           # psutil, for the resource sampler
docker compose --profile test up -d; $env:DATABASE_URL="postgresql+psycopg2://samaj:samaj-test@127.0.0.1:5433/samaj"
$env:ELASTICSEARCH_INDEX_PREFIX="samaj_load"; alembic upgrade head
python -m loadtest.seed --members 50000; python -m search.reindex  # synthetic community + initial indexing
docker build -t samaj-api:dev .                                    # the API as a Linux container
.\loadtest\run.ps1 -InDocker -Backends pg,es -Levels 10,25,50,75,100,250,500,1000
.\loadtest\run.ps1 -InDocker -Backends pg,es -Levels 250 -Mix same     # everyone runs the same search
.\loadtest\run.ps1 -InDocker -Backends es -Levels 250 -Churn 20 -Tag churn-   # 20 renames/s + worker
.\loadtest\run.ps1 -InDocker -Backends es -Levels 250 -Duration 90s -RestartEsAfter 30 -Tag outage-
python -m loadtest.report                                          # Markdown tables
```

- `run.ps1 -InDocker` runs the API (4 uvicorn workers, limited to `-ApiCpus 4` cores) in a container next to ES and
  `postgres-test`, and k6 on the same Docker network. Once per backend (`pg` = ES off, the baseline) it warms up,
  then for each level: fresh tokens, resource sampler, one k6 run.
- Without `-InDocker` it runs uvicorn on Windows. Don't use that for numbers: uvicorn's worker processes fail there
  (`WinError 10022`) and restart.
- Each simulated user searches about once a second (0.5–1.5 s think time).
- Mixes: `mixed` (name, partial, typo, Gujarati, family + city, deep page, matrimony filters with and without `q`),
  `same`, `filters`, `large` (broad queries, deep pages).
- Every run also checks auth (no token 401, pending member 403) and that no archived or pending member
  (`Zzhidden…`) is ever returned.
- `python -m loadtest.seed --drop` removes the synthetic data.

## 13. Production

- **Cluster:** [deploy/docker-compose.prod.yml](../backend/deploy/docker-compose.prod.yml).
  - Three nodes with TLS on HTTP and transport (certificates from a one-shot `certs` service), the file-realm
    `samaj_backend` user on every node, a volume per node, memory limits and locked heap.
  - Only `es01:9200` is published, on `ES_BIND_IP` (a private interface). Firewall it to the API hosts.
  - On each Docker host: `sysctl -w vm.max_map_count=262144` (persist it in `/etc/sysctl.d`).
  - Delete `cluster.initial_master_nodes` after the first start.
  - For real HA, put one node per host (same file, `discovery.seed_hosts` = the other hosts) or use a managed cluster.
- **Sizing:** heap = half the container memory, at most ~30 GB. The two indexes are tens of MB, so 2–4 GB heaps are
  plenty at this scale. One primary shard per index; `ELASTICSEARCH_REPLICAS=1` so every node can serve reads and a
  node can fail. More API traffic: add replicas and nodes. More shards don't help at this size.
- **API servers:**
  - `ELASTICSEARCH_URL=https://<ES_BIND_IP>:9200`, `ELASTICSEARCH_CA_CERTS=/etc/samaj/es-ca.crt` (copy `ca/ca.crt`
    from the `certs` volume), `ELASTICSEARCH_REPLICAS=1`.
  - Run uvicorn with several workers (`--workers` ≈ CPU cores; measured numbers in search-loadtest.md) and size
    `DB_POOL_*` so workers × pool stays under Postgres `max_connections`.
  - Put a per-IP and per-token rate limit in the reverse proxy too: the app's limit is per process.
- **Image:** [backend/Dockerfile](../backend/Dockerfile) builds the API (`docker build -t samaj-api .`; settings
  from `--env-file`, never baked in). The same image runs the worker.
- **Worker:** run `python -m search.worker` as a service (systemd/supervisor/container) with the API's environment.
  For example: `docker run -d --restart unless-stopped --env-file prod.env samaj-api python -m search.worker`.
  One is enough; a second for redundancy is safe.
- **First deploy:** `alembic upgrade head`, start the worker, then `python -m search.reindex`.
- **Backup and recovery:** Postgres is the source of truth, so the recovery for any index problem is
  `python -m search.reindex --rebuild` (seconds at this size). For faster restores of a large cluster, register a
  snapshot repository on the shared `/snapshots` volume and a nightly SLM policy, as the `elastic` superuser
  (`docker compose exec es01 bin/elasticsearch-reset-password -u elastic`):
  ```
  PUT _snapshot/samaj_fs  {"type": "fs", "settings": {"location": "/snapshots"}}
  PUT _slm/policy/nightly {"schedule": "0 30 1 * * ?", "name": "<samaj-{now/d}>", "repository": "samaj_fs",
                           "config": {"indices": ["samaj*"]}, "retention": {"expire_after": "30d", "min_count": 5}}
  ```
  A restored snapshot (`POST _snapshot/samaj_fs/<snapshot>/_restore`) misses every change made after it was taken.
  Searches work meanwhile, since hidden people are filtered by Postgres, but new or renamed ones are missing. So
  follow a restore with `--rebuild` anyway. Snapshots only pay off once a rebuild takes too long to wait for.
- **Never** expose 9200 publicly or give the backend the `elastic` user.

## Security

- **Only the backend reaches ES.**
  - Dev binds 127.0.0.1. Prod publishes one node on a private interface, which you firewall to the API hosts.
  - TLS on HTTP and between nodes in prod.
  - Authentication is always on: anonymous requests get 401.
- **Least privilege:** the API and worker log in as `samaj_backend`
  ([roles.yml](../backend/deploy/elasticsearch/roles.yml)): all rights on `samaj*` indices, cluster `monitor`, nothing
  else. Other indices get 403, and the `elastic` superuser isn't used by the app.
- **No sensitive data in the index:** no phone, address, DOB of relatives, photos, ID documents or biodata.
  `test_search.py` asserts the document fields and that the member's mobile number appears nowhere in them.
- **Who can see whom** comes from the authenticated member (ACTIVE only), never from a parameter. Every hit is
  re-read through the Postgres visibility queries, so a forged, stale or mis-synced document can't expose a pending,
  rejected or archived person (tested). Your own matrimony profile is filtered out in both the ES query and the
  Postgres read.
- **Input:**
  - Every parameter is typed and bounded (text 2–120 characters, `limit` ≤ 50, enums for filters).
  - The query JSON is built server-side; users never supply query DSL. `*`, `?` and `\` are escaped in substring
    patterns.
- **Cost limits:**
  - At most 51 hits per call, no total-hits counting, and a 1.5 s shard / 2 s client timeout.
  - Offsets past ES's 10,000 window go to Postgres.
  - A per-member search rate limit, and a per-process admission limit.
- **Errors:** clients never see ES errors. They get results (from Postgres if needed) or the usual 4xx. Logs record
  the error type only.
- **Logs:**
  - The `search` logger never logs query text.
  - uvicorn's access log records full URLs, including the names searched for. The Docker image runs with
    `--no-access-log`. The dev command in the README still logs them, so keep that to dev.
- **Secrets** come only from the environment: `.env` is gitignored, and `.dockerignore` keeps it out of the image.

## 14. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Clients get `503 Server busy` | Every API process has had all its slots busy for 10 s. Add uvicorn workers or API hosts. Raising `DB_POOL_*` only helps if Postgres has CPU to spare (`server_busy_503` on the status page counts them). |
| `/health` shows `search: degraded` | ES unreachable from the API. `docker compose ps`, check `ELASTICSEARCH_URL` and credentials. Searches still work (Postgres). |
| New members don't appear in search | Worker not running, or events failing: `GET /superadmin/search/status` → `outbox`. Start `python -m search.worker`. |
| `outbox.dead > 0` | See `last_error` in `samaj.search_outbox` where `dead_at IS NOT NULL`. Fix the cause, then `python -m search.worker --retry-dead`. |
| Worker logs `has mapping vN, the code expects vM` | `python -m search.reindex --rebuild`. |
| Worker logs `created empty samaj_directory` | First run; `python -m search.reindex` fills it. |
| Requests take ~2 s more on Windows | `localhost` resolves to `::1` first; Docker listens on 127.0.0.1 only, and Windows waits ~2 s before falling back. Use `http://127.0.0.1:9200`. |
| ES container exits / `max virtual memory areas vm.max_map_count [65530] is too low` | Multi-node only: set `vm.max_map_count=262144` on the host. |
| `401` from ES | `.env` username/password differ from the ones the container started with: `docker compose up -d --force-recreate`. |
| `403 ... unauthorized for indices [x]` | `ELASTICSEARCH_INDEX_PREFIX` doesn't start with `samaj`; the role only covers `samaj*`. |
| Disk full / indexes read-only (`flood stage`) | Free disk; then `PUT _all/_settings {"index.blocks.read_only_allow_delete": null}`. |
| Search results and Postgres disagree | Bulk SQL edits bypass the outbox: `python -m search.reindex --rebuild`. |
| Tests fail with `could not load library ... citext.dll` | Windows Application Control blocks the host Postgres's citext extension; run the tests on `postgres-test` (section 11). |
