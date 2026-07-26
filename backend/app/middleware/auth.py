import os
import secrets
from typing import Awaitable, Callable

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


def verify_token(token: str) -> bool:
    """Constant-time comparison of a candidate token against the configured key.

    Returns ``True`` when auth is disabled (no key configured) or when the
    token matches. Used by both the HTTP middleware and the WebSocket
    handshake so the two paths share identical comparison semantics.
    """
    api_key = _get_api_key()
    if not api_key:
        # Auth disabled — no key configured (development mode)
        return True
    if not token:
        return False
    return secrets.compare_digest(token, api_key)


class BearerTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable]):
        # Always allow CORS preflight requests through. This OPTIONS bypass is
        # the real safeguard for CORS regardless of middleware ordering.
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if path in _UNPROTECTED_EXACT or path.startswith(_UNPROTECTED_PREFIXES):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        prefix = "Bearer "
        token = auth_header[len(prefix):] if auth_header.startswith(prefix) else ""
        if not verify_token(token):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

        return await call_next(request)