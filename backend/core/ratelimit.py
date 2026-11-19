"""Per-client request limits (SRS System Limits: 60 req/min per member, 10 req/min per IP on OTP endpoints).

check() counts one request for (bucket, key) in a fixed window and raises 429 + Retry-After past the limit.
A key of None (client IP unknown, e.g. the test client) is never limited.
ponytail: counters live in this process; with N uvicorn workers a client gets up to N x the limit, and a restart
resets them. Fine for abuse limits; move to Redis when exact quotas or several API servers matter. Limits that
guard money (OTP SMS sends) are counted in Postgres instead (member/auth/curd.py).
"""
import threading
import time

from fastapi import HTTPException

_lock = threading.Lock()  # endpoints are sync: dependencies run on threadpool threads
_counts: dict[tuple, tuple[float, int]] = {}  # (bucket, key) -> (window end, requests in window)
MAX_KEYS = 100_000  # past this, expired windows are dropped
rejected = 0  # 429s from this module since the process started


def check(bucket: str, key, limit: int, per: int = 60) -> None:
    if key is None:
        return
    now = time.time()
    with _lock:
        end, n = _counts.get((bucket, key), (0.0, 0))
        if now >= end:
            end, n = (now // per + 1) * per, 0
        n += 1
        _counts[(bucket, key)] = (end, n)
        if len(_counts) > MAX_KEYS:
            for k in [k for k, (e, _) in _counts.items() if e <= now]:
                del _counts[k]
        if n <= limit:
            return
        global rejected
        rejected += 1
    wait = int(end - now) + 1
    raise HTTPException(429, f"Too many requests. Try again in {wait} seconds.", headers={"Retry-After": str(wait)})


def reset() -> None:
    """Tests: start every counter from zero."""
    with _lock:
        _counts.clear()


if __name__ == "__main__":
    for _ in range(3):
        check("t", "k", 3)
    try:
        check("t", "k", 3)
        raise AssertionError("4th call should be limited")
    except HTTPException as e:
        assert e.status_code == 429 and int(e.headers["Retry-After"]) >= 1
    check("t", "other", 3)  # other keys have their own count
    check("t", None, 0)  # unknown key: never limited
    reset()
    check("t", "k", 3)
    print("ok")
