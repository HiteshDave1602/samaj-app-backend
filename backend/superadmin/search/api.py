from elasticsearch import ApiError, TransportError
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.deps import require_super_admin
from core import admission
from core.database import get_db
from search import es, sync

router = APIRouter(prefix="/superadmin/search", tags=["Super Admin: Search"], dependencies=[Depends(require_super_admin)])


@router.get("/status")
def status(db: Session = Depends(get_db)):
    """Search engine health for operators. `requests` counts this API process only, since it started.
    outbox.dead > 0: events gave up (see search_outbox.last_error); fix, then python -m search.worker --retry-dead."""
    out = {"enabled": es.enabled(), "requests": es.snapshot() | {"server_busy_503": admission.rejected},
           "outbox": sync.outbox_stats(db)}
    if not es.enabled():
        return out
    try:
        c = es.client().options(request_timeout=2)
        h = c.cluster.health()
        out["cluster"] = {k: h[k] for k in ("status", "number_of_nodes", "active_shards", "unassigned_shards")}
        out["indexes"] = {}
        for spec in sync.INDEXES:
            index = es.current(spec)
            out["indexes"][spec.NAME] = index and {"index": index, "documents": c.count(index=index)["count"]}
        pools = [n["thread_pool"] for n in c.nodes.stats(metric="thread_pool")["nodes"].values()]
        out["cluster"]["rejected"] = {p: sum(t[p]["rejected"] for t in pools) for p in ("search", "write")}
    except (ApiError, TransportError) as e:
        out["cluster"] = {"status": "unreachable", "error": type(e).__name__}
    return out
