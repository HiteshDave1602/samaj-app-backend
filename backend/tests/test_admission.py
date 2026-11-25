"""Admission control (core/admission.py): python test_admission.py   No database needed.
At most `limit` requests run at once, the rest queue, and past QUEUE_SECONDS a queued one gets 503."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from core import admission

running = peak = 0
lock = threading.Lock()


def slow(_request):  # sync, like the API's endpoints: runs in the threadpool
    global running, peak
    with lock:
        running += 1
        peak = max(peak, running)
    time.sleep(0.3)
    with lock:
        running -= 1
    return PlainTextResponse("ok")


admission.QUEUE_SECONDS = 1
app = admission.AdmissionLimit(Starlette(routes=[Route("/", slow)]), limit=2)
server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8799, log_level="warning"))
threading.Thread(target=server.run, daemon=True).start()
while not server.started:
    time.sleep(0.05)
try:
    with ThreadPoolExecutor(12) as pool:
        codes = list(pool.map(lambda _: httpx.get("http://127.0.0.1:8799/", timeout=10).status_code, range(12)))
    # 12 requests of 0.3 s through 2 slots: ~6 finish within the 1 s queue limit, the rest are turned away
    assert peak == 2, peak
    assert codes.count(200) >= 4 and codes.count(503) >= 4 and set(codes) == {200, 503}, codes
    assert admission.rejected == codes.count(503)
    print(f"ok ({codes.count(200)} served, {codes.count(503)} busy)")
finally:
    server.should_exit = True
