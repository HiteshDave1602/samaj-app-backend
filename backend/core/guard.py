"""Request guards shared by every route: body size cap, one error shape, and input-failure logging.

Error shape (every 4xx/5xx). `detail` stays exactly as before, so existing clients keep working:
    {"detail": ..., "error": {"code": "VALIDATION_ERROR", "message": "...", "fields": {"email": "..."}}}

Logs (logger "samaj.input") carry the route, field names and error types, never the submitted values."""
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("samaj.input")

JSON_BYTES = 1024 * 1024  # largest real JSON body: a 10,000-character news post, ~30 KB in Gujarati
UPLOAD_BYTES = 10 * 1024 * 1024 + 64 * 1024  # the 10 MB import file plus multipart framing; images cap lower
CODES = {400: "BAD_REQUEST", 401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED",
         409: "CONFLICT", 413: "PAYLOAD_TOO_LARGE", 415: "UNSUPPORTED_MEDIA_TYPE", 422: "VALIDATION_ERROR",
         429: "RATE_LIMITED", 500: "INTERNAL_ERROR", 503: "UNAVAILABLE"}
# Worth a warning: a normal client never sends these, a hand-made or hostile one does.
SUSPICIOUS = {"json_invalid", "extra_forbidden", "model_attributes_type", "dict_type"}


def envelope(status: int, detail, code: str | None = None, fields: dict | None = None, headers=None) -> JSONResponse:
    message = detail if isinstance(detail, str) else "Please correct the highlighted fields."
    if code is None and isinstance(detail, str) and detail.startswith("ERR_") and ":" in detail:
        code, message = detail.split(":", 1)[0], detail.split(":", 1)[1].strip()  # SOP codes, e.g. ERR_IMG_UL
    error = {"code": code or CODES.get(status, "ERROR"), "message": message}
    if fields:
        error["fields"] = fields
    return JSONResponse({"detail": detail, "error": error}, status, headers=headers)


def _ip(request: Request) -> str:
    return request.client.host if request.client else "-"


def _msg(e: dict) -> str:
    if e["type"] == "extra_forbidden":
        return "This field isn't accepted"
    if e["type"] == "json_invalid":
        return "The request body isn't valid JSON"
    return e["msg"].removeprefix("Value error, ")


async def on_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # input and ctx are dropped: echoing them would hand a password or a payload straight back (and into proxies' logs)
    errors = [{"type": e["type"], "loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
    fields = {}
    for e in errors:
        path = ".".join(str(p) for p in e["loc"][1:]) if e["type"] != "json_invalid" else "body"
        fields.setdefault(path or "body", _msg(e))  # first problem per field; model-level rules land on "body"
    types = sorted({e["type"] for e in errors})
    code = "MALFORMED_JSON" if types == ["json_invalid"] else "VALIDATION_ERROR"
    level = logging.WARNING if SUSPICIOUS & set(types) else logging.INFO
    log.log(level, "input_rejected method=%s path=%s ip=%s fields=%s types=%s", request.method,
            request.url.path, _ip(request), ",".join(fields), ",".join(types))
    return envelope(422, errors, code, fields)


async def on_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code in (413, 415) or (isinstance(exc.detail, str) and exc.detail.startswith("ERR_IMG_UL")):
        log.warning("upload_rejected method=%s path=%s ip=%s status=%s", request.method, request.url.path,
                    _ip(request), exc.status_code)
    return envelope(exc.status_code, exc.detail, headers=getattr(exc, "headers", None))


async def on_crash(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled method=%s path=%s", request.method, request.url.path)  # traceback stays server-side
    return envelope(500, "Something went wrong on our side. Try again.")


class BodyLimit:
    """413 before a too-big body is read: by Content-Length up front, or by counting a chunked one as it streams."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        upload = headers.get(b"content-type", b"").startswith(b"multipart/")
        limit = UPLOAD_BYTES if upload else JSON_BYTES
        too_big = f"The request is larger than {limit // (1024 * 1024)} MB"
        length = headers.get(b"content-length")
        if length is not None and (not length.isdigit() or int(length) > limit):
            log.warning("body_too_large path=%s length=%s", scope["path"], length[:20].decode(errors="replace"))
            bad = envelope(413 if length.isdigit() else 400, too_big if length.isdigit() else "Bad Content-Length")
            return await bad(scope, receive, send)
        seen = 0

        async def counted():
            nonlocal seen
            message = await receive()
            seen += len(message.get("body", b""))
            if seen > limit:
                raise HTTPException(413, too_big)  # FastAPI re-raises HTTPExceptions from body reading
            return message

        await self.app(scope, counted, send)


def install(app: FastAPI):
    app.add_exception_handler(RequestValidationError, on_validation_error)
    app.add_exception_handler(StarletteHTTPException, on_http_error)
    app.add_exception_handler(Exception, on_crash)
    app.add_middleware(BodyLimit)  # added last = outermost: an oversized body never takes an admission slot
