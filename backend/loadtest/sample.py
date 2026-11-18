"""Samples resource use during a load run into loadtest/.out/samples-<label>.json (docs/search.md, "Load testing").

    python -m loadtest.sample <label> <api_port | api_container>     until loadtest/.out/stop-<label> appears

Backend: CPU and memory of the uvicorn process tree on <api_port>, or of <api_container>. Elasticsearch: node CPU, heap and
thread-pool rejections. Postgres: container CPU/memory (docker stats) and connections by state (pg_stat_activity).
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import psutil
from sqlalchemy import text

from core.database import SessionLocal, engine
from search import es, sync

OUT = Path(__file__).parent / ".out"
INTERVAL = 2.0


def api_procs(port: int) -> list[psutil.Process]:
    for c in psutil.net_connections("tcp"):
        if c.laddr and c.laddr.port == port and c.status == psutil.CONN_LISTEN and c.pid:
            root = psutil.Process(c.pid)
            while root.parent() and root.parent().name().lower().startswith("python"):
                root = root.parent()
            return [root, *root.children(recursive=True)]
    return []


def docker_stats() -> dict:
    out = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}"],
                         capture_output=True, text=True, timeout=20).stdout
    stats = {}
    for line in out.splitlines():
        name, cpu, mem = line.split("|")
        used = mem.split("/")[0].strip()
        mib = float(used[:-3]) * {"GiB": 1024, "MiB": 1, "KiB": 1 / 1024}[used[-3:]]
        stats[name] = {"cpu_pct": float(cpu.rstrip("%")), "mem_mib": round(mib)}
    return stats


def main(label: str, target: str):
    """target: the API's port (uvicorn on this machine) or its container name."""
    container = None if target.isdigit() else target
    procs, samples, stop = [] if container else api_procs(int(target)), [], OUT / f"stop-{label}"
    for p in procs:
        p.cpu_percent()  # prime
    while not stop.exists():
        time.sleep(INTERVAL)
        s = {"t": time.time(), "docker": docker_stats()}
        if container:
            s["api_cpu_pct"], s["api_mem_mib"] = (s["docker"].get(container, {}).get(k) for k in ("cpu_pct", "mem_mib"))
        else:
            alive = [p for p in procs if p.is_running()]
            s["api_cpu_pct"] = round(sum(p.cpu_percent() for p in alive), 1)  # 100 = one core
            s["api_mem_mib"] = round(sum(p.memory_info().rss for p in alive) / 2**20)
        with engine.connect() as c:
            s["db_conns"] = dict(c.execute(text("SELECT coalesce(state, 'other'), count(*) FROM pg_stat_activity "
                                                "WHERE datname = current_database() GROUP BY 1")).all())
        with SessionLocal() as db:
            s["outbox"] = sync.outbox_stats(db)  # pending events and the oldest one's age = index lag
        if es.enabled():
            node = next(iter(es.client().nodes.stats(metric="os,process,jvm,thread_pool")["nodes"].values()))
            s["es_cpu_pct"] = node["process"]["cpu"]["percent"]
            s["es_heap_pct"] = node["jvm"]["mem"]["heap_used_percent"]
            s["es_search_rejected"] = node["thread_pool"]["search"]["rejected"]
            s["es_search_queue"] = node["thread_pool"]["search"]["queue"]
        samples.append(s)
    stop.unlink()
    (OUT / f"samples-{label}.json").write_text(json.dumps(samples))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
