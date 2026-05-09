import os
import secrets

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Paths that are always public (exact matches)
_UNPROTECTED_EXACT = {"/health", "/openapi.json"}
# Path prefixes that are always public (Swagger UI and its sub-routes)
_UNPROTECTED_PREFIXES = ("/docs", "/redoc")

STATIC_API_KEY = os.getenv("AIGENT_API_KEY", "")


class BearerTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Always allow CORS preflight requests through
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if path in _UNPROTECTED_EXACT or path.startswith(_UNPROTECTED_PREFIXES):
            return await call_next(request)

        if not STATIC_API_KEY:
            # No key configured → auth disabled (development mode)
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        prefix = "Bearer "
        if not auth_header.startswith(prefix):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

        token = auth_header[len(prefix):]
        if not secrets.compare_digest(token, STATIC_API_KEY):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

        return await call_next(request)
