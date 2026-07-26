"""WebSocket auth tests for /ws/{session_id}.

Verifies the handshake closes with code 1008 when ``AIGENT_API_KEY`` is
configured and the ``token`` query parameter is missing or wrong, and that a
correct token allows the connection through to the message loop (ping/pong).
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.websockets import manager

KEY = "ws-secret-key"


def _extract_code(exc: Exception):
    return getattr(exc, "code", None)


def test_ws_no_token_rejected_when_auth_enabled(monkeypatch):
    monkeypatch.setenv("AIGENT_API_KEY", KEY)
    client = TestClient(app)
    with pytest.raises(Exception) as exc_info:
        with client.websocket_connect("/ws/s1"):
            pass
    # Handshake rejected before accept → Starlette raises with code 1008.
    assert _extract_code(exc_info.value) == 1008


def test_ws_wrong_token_rejected(monkeypatch):
    monkeypatch.setenv("AIGENT_API_KEY", KEY)
    client = TestClient(app)
    with pytest.raises(Exception) as exc_info:
        with client.websocket_connect("/ws/s1?token=not-the-key"):
            pass
    assert _extract_code(exc_info.value) == 1008


def test_ws_correct_token_accepted(monkeypatch):
    """A matching token passes auth and reaches the message loop (ping→pong)."""
    monkeypatch.setenv("AIGENT_API_KEY", KEY)
    client = TestClient(app)
    # Use a unique session id so we don't collide with other connections.
    sid = "ws-auth-ok"
    try:
        with client.websocket_connect(f"/ws/{sid}?token={KEY}") as ws:
            ws.send_text('{"type":"ping","ts":1}')
            msg = ws.receive_json()
            assert msg["type"] == "pong"
    finally:
        # Clean up any connection the manager retained for this session.
        for conns in manager.active_connections.values():
            for c in list(conns):
                try:
                    manager.disconnect(c, sid)
                except Exception:
                    pass


def test_ws_no_token_allowed_when_auth_disabled(monkeypatch):
    """With no key configured, auth is disabled and the WS connects freely."""
    monkeypatch.delenv("AIGENT_API_KEY", raising=False)
    client = TestClient(app)
    sid = "ws-auth-disabled"
    try:
        with client.websocket_connect(f"/ws/{sid}") as ws:
            ws.send_text('{"type":"ping","ts":2}')
            msg = ws.receive_json()
            assert msg["type"] == "pong"
    finally:
        for conns in manager.active_connections.values():
            for c in list(conns):
                try:
                    manager.disconnect(c, sid)
                except Exception:
                    pass