"""Admission control: at most `limit` HTTP requests of this process run at once; the rest wait on the event loop.

Why: every endpoint is sync. A request holds its pooled DB connection from its first query to its end, and FastAPI
moves it to a threadpool thread once per sync dependency. With more requests in flight than pool connections, the
requests holding connections wait for threads while the threads wait for connections, and everything stalls until
the 30 s pool timeout. The load test hit this at 250 users (60 of 60 connections 'idle in transaction', API CPU 0).
A request waiting here holds no thread and no connection, so that can't happen; past QUEUE_SECONDS it gets a 503.
"""
import anyio
from starlette.responses import JSONResponse

QUEUE_SECONDS = 10

rejected = 0  # 503s since this process started (GET /superadmin/search/status)


class AdmissionLimit:
    def __init__(self, app, limit: int):
        self.app, self.limit, self._slots = app, limit, None

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if self._slots is None:  # created inside the running event loop
            self._slots = anyio.Semaphore(self.limit)
        try:
            with anyio.fail_after(QUEUE_SECONDS):
                await self._slots.acquire()
        except TimeoutError:
            global rejected
            rejected += 1
            busy = JSONResponse({"detail": "Server busy. Try again in a moment."}, 503, headers={"Retry-After": "2"})
            return await busy(scope, receive, send)
        try:
            await self.app(scope, receive, send)
        finally:
            self._slots.release()
