import os
import secrets

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Paths that are always public (exact matches)
_UNPROTECTED_EXACT = {"/health", "/openapi.json"}
# Path prefixes that are always public (Swagger UI and its sub-routes)
_UNPROTECTED_PREFIXES = ("/docs", "/redoc")


def _get_api_key() -> str:
    """Read the API key from the environment on every call.

    Reading per-request (rather than at module load time) prevents module-level
    state from leaking between tests and supports dynamic reconfiguration.
    """
    return os.getenv("AIGENT_API_KEY", "")


class BearerTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Always allow CORS preflight requests through
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if path in _UNPROTECTED_EXACT or path.startswith(_UNPROTECTED_PREFIXES):
            return await call_next(request)

        api_key = _get_api_key()
        if not api_key:
            # No key configured → auth disabled (development mode)
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        prefix = "Bearer "
        if not auth_header.startswith(prefix):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

        token = auth_header[len(prefix):]
        if not secrets.compare_digest(token, api_key):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

        return await call_next(request)
