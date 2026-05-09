"""Tests for BearerTokenMiddleware (app/middleware/auth.py)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.auth import BearerTokenMiddleware


def _make_app(api_key: str) -> FastAPI:
    """Build a minimal FastAPI app with BearerTokenMiddleware wired in."""
    import os

    os.environ["AIGENT_API_KEY"] = api_key

    # Re-import so the module picks up the patched env var
    import importlib
    import app.middleware.auth as auth_mod

    importlib.reload(auth_mod)

    app = FastAPI()
    app.add_middleware(auth_mod.BearerTokenMiddleware)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/docs")
    async def fake_docs():
        return {"page": "docs"}

    @app.get("/docs/oauth2-redirect")
    async def fake_oauth2_redirect():
        return {"page": "oauth2-redirect"}

    @app.get("/redoc")
    async def fake_redoc():
        return {"page": "redoc"}

    @app.get("/openapi.json")
    async def fake_openapi():
        return {}

    @app.get("/protected")
    async def protected():
        return {"secret": "data"}

    return app


# ---------------------------------------------------------------------------
# Auth disabled (no key configured)
# ---------------------------------------------------------------------------


class TestAuthDisabled:
    def setup_method(self):
        self.client = TestClient(_make_app(""), raise_server_exceptions=True)

    def test_protected_allowed_without_token(self):
        resp = self.client.get("/protected")
        assert resp.status_code == 200

    def test_health_allowed(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Auth enabled
# ---------------------------------------------------------------------------


KEY = "test-secret-key-12345"


class TestAuthEnabled:
    def setup_method(self):
        self.client = TestClient(_make_app(KEY), raise_server_exceptions=True)

    # Unprotected paths must be publicly accessible

    def test_health_no_token(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200

    def test_openapi_no_token(self):
        resp = self.client.get("/openapi.json")
        assert resp.status_code == 200

    def test_docs_exact_no_token(self):
        resp = self.client.get("/docs")
        assert resp.status_code == 200

    def test_docs_subpath_no_token(self):
        """Swagger oauth2-redirect must not require auth."""
        resp = self.client.get("/docs/oauth2-redirect")
        assert resp.status_code == 200

    def test_redoc_no_token(self):
        resp = self.client.get("/redoc")
        assert resp.status_code == 200

    # Protected paths

    def test_protected_no_token_returns_401(self):
        resp = self.client.get("/protected")
        assert resp.status_code == 401

    def test_protected_wrong_token_returns_401(self):
        resp = self.client.get("/protected", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 401

    def test_protected_malformed_header_returns_401(self):
        resp = self.client.get("/protected", headers={"Authorization": KEY})
        assert resp.status_code == 401

    def test_protected_valid_token_returns_200(self):
        resp = self.client.get("/protected", headers={"Authorization": f"Bearer {KEY}"})
        assert resp.status_code == 200

    # CORS preflight

    def test_options_preflight_allowed_without_token(self):
        """OPTIONS requests must never be blocked by auth."""
        resp = self.client.options(
            "/protected",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Should not be 401 regardless of missing auth header
        assert resp.status_code != 401
