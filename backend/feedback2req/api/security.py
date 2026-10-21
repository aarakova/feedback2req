import threading
from collections import deque
from time import monotonic
from uuid import uuid4

from starlette.datastructures import Headers
from starlette.responses import JSONResponse

from feedback2req.config import Settings


def error_response(status, code, message, request_id):
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": {},
                "request_id": request_id,
            }
        },
    )


class LoginLimiter:
    """Bounded per-process IP limiter for the single API process in I1."""

    def __init__(self, limit, window):
        self.limit, self.window = limit, window
        self.buckets = {}
        self.lock = threading.Lock()

    def allow(self, key):
        with self.lock:
            now = monotonic()
            for existing in list(self.buckets):
                queue = self.buckets[existing]
                while queue and queue[0] <= now - self.window:
                    queue.popleft()
                if not queue:
                    del self.buckets[existing]
            if key not in self.buckets and len(self.buckets) >= 4096:
                return False
            queue = self.buckets.setdefault(key, deque())
            if len(queue) >= self.limit:
                return False
            queue.append(now)
            return True


class RequestSecurity:
    def __init__(self, app, settings: Settings):
        self.app, self.settings = app, settings
        self.limiter = LoginLimiter(settings.login_limit, settings.login_window_seconds)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        headers = Headers(scope=scope)
        response_started = False

        async def send_with_headers(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                message.setdefault("headers", []).extend(
                    [
                        (b"x-request-id", request_id.encode()),
                        (b"cache-control", b"no-store"),
                        (b"x-content-type-options", b"nosniff"),
                    ]
                )
            await send(message)

        async def reject(status, code, message):
            await error_response(status, code, message, request_id)(
                scope, receive, send_with_headers
            )

        mutating = scope["method"] not in {"GET", "HEAD", "OPTIONS"}
        if mutating and headers.get("origin") != self.settings.allowed_origin:
            return await reject(403, "origin_rejected", "Allowed Origin is required")
        anonymous_auth = scope["method"] == "POST" and scope["path"] in {
            "/api/v1/auth/register",
            "/api/v1/auth/session",
        }
        if anonymous_auth:
            if (
                headers.get("content-type", "").split(";", 1)[0].strip().lower()
                != "application/json"
            ):
                return await reject(422, "json_required", "JSON content type is required")
            client = scope.get("client")
            if not self.limiter.allow(client[0] if client else "unknown"):
                return await reject(429, "rate_limited", "Authentication rate limit exceeded")
        # Bound actual streamed bytes too; Content-Length alone is not trusted.
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.settings.max_body_bytes:
                return await reject(413, "body_too_large", "Request body limit exceeded")
            if not message.get("more_body", False):
                break
        consumed = False

        async def replay():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        # JSON parsing errors are handled by FastAPI without returning the submitted values.
        try:
            await self.app(scope, replay, send_with_headers)
        except Exception:
            if response_started:
                raise
            # Do not expose exception text, SQL parameters, credentials or submitted bodies.
            await reject(500, "internal_error", "Internal server error")
