"""Load-test tables from loadtest/.out (k6 summaries + resource samples): python -m loadtest.report [label-prefix]
Prints Markdown: one row per run, then per-request-kind p95 for each run."""
import json
import sys
from pathlib import Path

OUT = Path(__file__).parent / ".out"
ES_BOX, PG_BOX = "samaj-search-elasticsearch-1", "samaj-search-postgres-test-1"


def load(label: str):
    s = json.loads((OUT / f"summary-{label}.json").read_text(encoding="utf-8"))
    p = OUT / f"samples-{label}.json"
    return s["metrics"], json.loads(p.read_text()) if p.exists() else []


def peak(samples, f):
    vals = [v for v in (f(s) for s in samples) if v is not None]
    return max(vals) if vals else None


def avg(samples, f):
    vals = [v for v in (f(s) for s in samples) if v is not None]
    return sum(vals) / len(vals) if vals else None


def fmt(v, d=0):
    return "-" if v is None else f"{v:,.{d}f}"


def row(label: str) -> str:
    m, smp = load(label)
    d = m["http_req_duration"]["values"]
    rejected = [s["es_search_rejected"] for s in smp if "es_search_rejected" in s]
    return "| " + " | ".join([
        label, fmt(m["http_reqs"]["values"]["rate"], 1), fmt(d["avg"], 1), fmt(d["med"], 1), fmt(d["p(95)"], 1),
        fmt(d["p(99)"], 1), fmt(d["max"]), f'{m["http_req_failed"]["values"]["rate"] * 100:.2f}%',
        fmt(m.get("timeouts", {}).get("values", {}).get("count", 0)),
        fmt(m["hidden_members_returned"]["values"]["count"]),
        f'{fmt(avg(smp, lambda s: s["api_cpu_pct"]))} / {fmt(peak(smp, lambda s: s["api_cpu_pct"]))}',
        fmt(peak(smp, lambda s: s["api_mem_mib"])),
        fmt(peak(smp, lambda s: s["docker"].get(ES_BOX, {}).get("cpu_pct"))),
        fmt(peak(smp, lambda s: s.get("es_heap_pct"))),
        fmt(rejected[-1] - rejected[0] if rejected else None),
        fmt(peak(smp, lambda s: s["docker"].get(PG_BOX, {}).get("cpu_pct"))),
        f'{fmt(peak(smp, lambda s: sum(s["db_conns"].values())))} '
        f'({fmt(peak(smp, lambda s: s["db_conns"].get("active")))} active)',
    ]) + " |"


HEAD = ("| run | req/s | avg ms | p50 | p95 | p99 | max | errors | timeouts | hidden leaked | API CPU % avg / peak "
        "| API MiB | ES CPU % peak | ES heap % | ES rejected | PG CPU % peak | DB conns peak |\n"
        "|" + "---|" * 17)


def kinds(label: str) -> str:
    m, _ = load(label)
    cells = {k[len("http_req_duration{kind:"):-1]: v["values"] for k, v in m.items() if k.startswith("http_req_duration{kind:")}
    return "| " + label + " | " + " | ".join(
        f'{k}: {fmt(v["p(95)"], 0)}' for k, v in sorted(cells.items()) if v.get("max")) + " |"


if __name__ == "__main__":
    prefix = sys.argv[1] if len(sys.argv) > 1 else ""
    labels = sorted((p.stem[len("summary-"):] for p in OUT.glob(f"summary-{prefix}*.json") if "warmup" not in p.stem),
                    key=lambda l: (l.rsplit("-", 1)[0], int(l.rsplit("-", 1)[1]) if l.rsplit("-", 1)[1].isdigit() else 0))
    print(HEAD)
    for label in labels:
        print(row(label))
    print("\n| run | p95 ms by request kind |\n|---|---|")
    for label in labels:
        print(kinds(label))
