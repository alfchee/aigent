import os

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

_UNPROTECTED_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}

STATIC_API_KEY = os.getenv("AIGENT_API_KEY", "")


class BearerTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in _UNPROTECTED_PATHS:
            return await call_next(request)

        if not STATIC_API_KEY:
            # No key configured → auth disabled (development mode)
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if auth_header != f"Bearer {STATIC_API_KEY}":
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

        return await call_next(request)
