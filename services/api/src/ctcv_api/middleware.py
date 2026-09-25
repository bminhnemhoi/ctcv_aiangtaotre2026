"""Pure-ASGI middleware: request-id propagation.

Implemented at the ASGI level (not ``BaseHTTPMiddleware``) so streaming responses
such as SSE are not buffered and the ``request_id`` context variable is visible
to every log line emitted while handling the request.
"""

from __future__ import annotations

import re
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ctcv_core.logging import request_id_var

REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def new_request_id() -> str:
    """Return a fresh opaque request id."""
    return uuid.uuid4().hex


def pick_request_id(incoming: str | None) -> str:
    """Reuse a well-formed client-supplied id, otherwise generate one."""
    if incoming and _SAFE_REQUEST_ID.match(incoming):
        return incoming
    return new_request_id()


class RequestIdMiddleware:
    """Attach ``X-Request-ID`` to every HTTP response and to the logging context."""

    def __init__(self, app: ASGIApp, header: str = REQUEST_ID_HEADER) -> None:
        """Wrap ``app``; ``header`` is the request/response header name."""
        self.app = app
        self.header = header

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Set the request id for the duration of one HTTP request."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = pick_request_id(Headers(scope=scope).get(self.header))
        token = request_id_var.set(request_id)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message).append(self.header, request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)
