from __future__ import annotations

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

request_id_context: ContextVar[str] = ContextVar(
    "request_id",
    default="-",
)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(
            "X-Request-ID",
            str(uuid.uuid4()),
        )

        request_id_context.set(request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        return response
