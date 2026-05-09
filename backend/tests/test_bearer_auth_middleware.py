"""Tests for BearerTokenMiddleware (app/middleware/auth.py)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.auth import BearerTokenMiddleware


def _make_app() -> FastAPI:
    """Build a minimal FastAPI app with BearerTokenMiddleware wired in."""
    app = FastAPI()
    app.add_middleware(BearerTokenMiddleware)

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
    def test_protected_allowed_without_token(self, monkeypatch):
        monkeypatch.delenv("AIGENT_API_KEY", raising=False)
        client = TestClient(_make_app())
        assert client.get("/protected").status_code == 200

    def test_health_allowed(self, monkeypatch):
        monkeypatch.delenv("AIGENT_API_KEY", raising=False)
        client = TestClient(_make_app())
        assert client.get("/health").status_code == 200


# ---------------------------------------------------------------------------
# Auth enabled
# ---------------------------------------------------------------------------

KEY = "test-secret-key-12345"


class TestAuthEnabled:
    @pytest.fixture(autouse=True)
    def _set_key(self, monkeypatch):
        monkeypatch.setenv("AIGENT_API_KEY", KEY)
        self.client = TestClient(_make_app())

    # Unprotected paths must be publicly accessible

    def test_health_no_token(self):
        assert self.client.get("/health").status_code == 200

    def test_openapi_no_token(self):
        assert self.client.get("/openapi.json").status_code == 200

    def test_docs_exact_no_token(self):
        assert self.client.get("/docs").status_code == 200

    def test_docs_subpath_no_token(self):
        """Swagger oauth2-redirect must not require auth."""
        assert self.client.get("/docs/oauth2-redirect").status_code == 200

    def test_redoc_no_token(self):
        assert self.client.get("/redoc").status_code == 200

    # Protected paths

    def test_protected_no_token_returns_401(self):
        assert self.client.get("/protected").status_code == 401

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
        assert resp.status_code != 401

