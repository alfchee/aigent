"""API-level tests for the /mcp endpoints.

The global mcp_manager singleton is replaced per-test with a MagicMock so no
real MCP servers are required.
"""
from __future__ import annotations

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.mcp_client import McpServerConfig


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def _make_mgr(**overrides) -> MagicMock:
    """Build a minimal McpManager mock with sensible defaults."""
    mgr = MagicMock()
    mgr.get_server_status = MagicMock(return_value={})
    mgr.get_all_tools = AsyncMock(return_value=[])
    mgr.add_server = MagicMock()
    mgr.add_server_async = AsyncMock()
    mgr.update_server = MagicMock()
    mgr.update_server_async = AsyncMock()
    mgr.disconnect_and_remove_server = AsyncMock()
    mgr.test_connection = AsyncMock(return_value={"ok": True, "tool_count": 0, "tools": []})
    mgr.reconnect_server = AsyncMock(return_value=None)
    mgr.sync_servers = AsyncMock()
    mgr._configs = {}  # used by sync_server existence check via get_server_status
    for key, val in overrides.items():
        setattr(mgr, key, val)
    return mgr


def _stdio_cfg(server_id: str = "test_srv", enabled: bool = False) -> McpServerConfig:
    return McpServerConfig(server_id, {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@test/server"],
        "env_vars": {"TOKEN": "secret"},
        "enabled": enabled,
    })


def _http_cfg(server_id: str = "remote_srv", enabled: bool = False) -> McpServerConfig:
    return McpServerConfig(server_id, {
        "transport": "http",
        "base_url": "https://mcp.example.com",
        "headers": {"Authorization": "Bearer tok"},
        "enabled": enabled,
    })


# ---------------------------------------------------------------------------
# AddServerRequest / UpdateServerRequest Pydantic validation
# ---------------------------------------------------------------------------

class TestRequestValidation:
    def test_invalid_transport_returns_422(self, client):
        response = client.post("/mcp/servers/newsrv", json={
            "transport": "ftp",
            "command": "x",
        })
        assert response.status_code == 422

    def test_stdio_missing_command_returns_422(self, client):
        response = client.post("/mcp/servers/newsrv", json={
            "transport": "stdio",
        })
        assert response.status_code == 422

    def test_http_missing_base_url_returns_422(self, client):
        response = client.post("/mcp/servers/newsrv", json={
            "transport": "http",
        })
        assert response.status_code == 422

    def test_update_invalid_transport_returns_422(self, client):
        mgr = _make_mgr()
        with patch("app.api.mcp.mcp_manager", mgr):
            response = client.put("/mcp/servers/srv", json={"transport": "ftp"})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /mcp/servers
# ---------------------------------------------------------------------------

class TestListServers:
    def test_empty_returns_ok(self, client):
        mgr = _make_mgr()
        with patch("app.api.mcp.mcp_manager", mgr):
            response = client.get("/mcp/servers")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["servers"] == {}

    def test_returns_server_status(self, client):
        status: Dict[str, Any] = {
            "github": {
                "enabled": True,
                "transport": "stdio",
                "connected": False,
                "tool_count": 0,
            }
        }
        mgr = _make_mgr(get_server_status=MagicMock(return_value=status))
        with patch("app.api.mcp.mcp_manager", mgr):
            response = client.get("/mcp/servers")
        assert response.status_code == 200
        assert response.json()["servers"]["github"]["transport"] == "stdio"


# ---------------------------------------------------------------------------
# POST /mcp/servers/{id}
# ---------------------------------------------------------------------------

class TestAddServer:
    def test_add_disabled_server_returns_201(self, client):
        cfg = _stdio_cfg(enabled=False)
        mgr = _make_mgr(add_server_async=AsyncMock(return_value=cfg))
        with patch("app.api.mcp.mcp_manager", mgr):
            response = client.post("/mcp/servers/test_srv", json={
                "transport": "stdio",
                "command": "npx",
                "enabled": False,
            })
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "ok"
        assert data["server_id"] == "test_srv"
        mgr.reconnect_server.assert_not_called()

    def test_add_disabled_server_masks_secrets_in_response(self, client):
        cfg = _stdio_cfg(enabled=False)
        mgr = _make_mgr(add_server_async=AsyncMock(return_value=cfg))
        with patch("app.api.mcp.mcp_manager", mgr):
            response = client.post("/mcp/servers/test_srv", json={
                "transport": "stdio",
                "command": "npx",
                "env_vars": {"TOKEN": "supersecret"},
                "enabled": False,
            })
        assert response.status_code == 201
        # The env_var value must be masked, not returned in plaintext
        env_vars = response.json()["config"].get("env_vars", {})
        assert env_vars.get("TOKEN") != "supersecret"

    def test_add_enabled_server_calls_reconnect(self, client):
        cfg = _stdio_cfg(enabled=True)
        mgr = _make_mgr(add_server_async=AsyncMock(return_value=cfg))
        with patch("app.api.mcp.mcp_manager", mgr):
            response = client.post("/mcp/servers/test_srv", json={
                "transport": "stdio",
                "command": "npx",
                "enabled": True,
            })
        assert response.status_code == 201
        mgr.reconnect_server.assert_awaited_once_with("test_srv")

    def test_add_duplicate_returns_409(self, client):
        mgr = _make_mgr(add_server_async=AsyncMock(side_effect=ValueError("already exists")))
        with patch("app.api.mcp.mcp_manager", mgr):
            response = client.post("/mcp/servers/existing", json={
                "transport": "stdio",
                "command": "npx",
            })
        assert response.status_code == 409

    def test_add_http_server_disabled(self, client):
        cfg = _http_cfg(enabled=False)
        mgr = _make_mgr(add_server_async=AsyncMock(return_value=cfg))
        with patch("app.api.mcp.mcp_manager", mgr):
            response = client.post("/mcp/servers/remote_srv", json={
                "transport": "http",
                "base_url": "https://mcp.example.com",
                "enabled": False,
            })
        assert response.status_code == 201
        assert response.json()["config"]["transport"] == "http"


# ---------------------------------------------------------------------------
# PUT /mcp/servers/{id}
# ---------------------------------------------------------------------------

class TestUpdateServer:
    def test_update_returns_200_and_masked_config(self, client):
        updated_cfg = _stdio_cfg()
        mgr = _make_mgr(update_server_async=AsyncMock(return_value=updated_cfg))
        with patch("app.api.mcp.mcp_manager", mgr):
            response = client.put("/mcp/servers/test_srv", json={
                "command": "node",
            })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["server_id"] == "test_srv"
        # sync_servers called to apply changes
        mgr.sync_servers.assert_awaited_once()

    def test_update_not_found_returns_404(self, client):
        mgr = _make_mgr(update_server_async=AsyncMock(side_effect=KeyError("test_srv")))
        with patch("app.api.mcp.mcp_manager", mgr):
            response = client.put("/mcp/servers/test_srv", json={"command": "x"})
        assert response.status_code == 404

    def test_update_masks_env_vars_in_response(self, client):
        cfg = McpServerConfig("srv", {
            "transport": "stdio",
            "command": "npx",
            "env_vars": {"API_KEY": "real_key"},
        })
        mgr = _make_mgr(update_server_async=AsyncMock(return_value=cfg))
        with patch("app.api.mcp.mcp_manager", mgr):
            response = client.put("/mcp/servers/srv", json={"command": "npx"})
        env_vars = response.json()["config"].get("env_vars", {})
        assert env_vars.get("API_KEY") != "real_key"
        assert env_vars.get("API_KEY") == "***"


# ---------------------------------------------------------------------------
# DELETE /mcp/servers/{id}
# ---------------------------------------------------------------------------

class TestRemoveServer:
    def test_remove_returns_200(self, client):
        mgr = _make_mgr()
        with patch("app.api.mcp.mcp_manager", mgr), \
             patch("app.api.mcp.registry") as mock_reg:
            response = client.delete("/mcp/servers/test_srv")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["deleted_server_id"] == "test_srv"
        mgr.disconnect_and_remove_server.assert_awaited_once_with("test_srv")
        mock_reg.remove_tools_by_prefix.assert_called_once_with("mcp__test_srv__")

    def test_remove_not_found_returns_404(self, client):
        mgr = _make_mgr(
            disconnect_and_remove_server=AsyncMock(side_effect=KeyError("test_srv"))
        )
        with patch("app.api.mcp.mcp_manager", mgr):
            response = client.delete("/mcp/servers/test_srv")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /mcp/servers/{id}/test
# ---------------------------------------------------------------------------

class TestTestServer:
    def test_test_success_returns_tool_count(self, client):
        mgr = _make_mgr(
            test_connection=AsyncMock(return_value={
                "ok": True,
                "tool_count": 3,
                "tools": ["t1", "t2", "t3"],
            })
        )
        with patch("app.api.mcp.mcp_manager", mgr):
            response = client.post("/mcp/servers/github/test")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["tool_count"] == 3
        assert "t1" in data["tools"]

    def test_test_failure_returns_502(self, client):
        mgr = _make_mgr(
            test_connection=AsyncMock(return_value={
                "ok": False,
                "error": "Connection refused",
            })
        )
        with patch("app.api.mcp.mcp_manager", mgr):
            response = client.post("/mcp/servers/github/test")
        assert response.status_code == 502
        assert "Connection refused" in response.json()["detail"]


# ---------------------------------------------------------------------------
# POST /mcp/servers/{id}/sync
# ---------------------------------------------------------------------------

class TestSyncServer:
    def test_sync_success_returns_200(self, client):
        mgr = _make_mgr(
            get_server_status=MagicMock(return_value={"github": {"connected": False}}),
        )
        with patch("app.api.mcp.mcp_manager", mgr), \
             patch("app.api.mcp.registry") as mock_reg:
            mock_reg._tools = {}
            response = client.post("/mcp/servers/github/sync")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["server_id"] == "github"
        mgr.reconnect_server.assert_awaited_once_with("github")

    def test_sync_not_found_returns_404(self, client):
        mgr = _make_mgr(get_server_status=MagicMock(return_value={}))
        with patch("app.api.mcp.mcp_manager", mgr):
            response = client.post("/mcp/servers/ghost/sync")
        assert response.status_code == 404

    def test_sync_reconnect_failure_returns_502(self, client):
        mgr = _make_mgr(
            get_server_status=MagicMock(return_value={"srv": {}}),
            reconnect_server=AsyncMock(side_effect=RuntimeError("process died")),
        )
        with patch("app.api.mcp.mcp_manager", mgr):
            response = client.post("/mcp/servers/srv/sync")
        assert response.status_code == 502


# ---------------------------------------------------------------------------
# GET /mcp/tools
# ---------------------------------------------------------------------------

class TestListTools:
    def test_list_tools_empty(self, client):
        mgr = _make_mgr(get_all_tools=AsyncMock(return_value=[]))
        with patch("app.api.mcp.mcp_manager", mgr):
            response = client.get("/mcp/tools")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["tool_count"] == 0
        assert data["tools"] == []

    def test_list_tools_returns_name_and_description(self, client):
        from pydantic import create_model
        from app.skills.registry import ToolDefinition
        from unittest.mock import AsyncMock as AM

        EmptyArgs = create_model("EmptyArgs")
        fake_tool = ToolDefinition(
            name="mcp__github__list_prs",
            description="List open pull requests",
            args_schema=EmptyArgs,
            func=AM(),
        )
        mgr = _make_mgr(get_all_tools=AsyncMock(return_value=[fake_tool]))
        with patch("app.api.mcp.mcp_manager", mgr):
            response = client.get("/mcp/tools")
        assert response.status_code == 200
        data = response.json()
        assert data["tool_count"] == 1
        tool = data["tools"][0]
        assert tool["name"] == "mcp__github__list_prs"
        assert tool["description"] == "List open pull requests"
        assert "schema" in tool
